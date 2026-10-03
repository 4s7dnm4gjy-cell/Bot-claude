"""Conseiller semi-automatique pour un courtier sans API (Trade Republic).

Chaque soir de bourse (GitHub Actions) :
  1. le bot analyse le marché et met à jour le tableau de bord ;
  2. s'il y a quelque chose à faire, il ouvre un ticket « proposition » :
     quoi acheter/vendre, combien, pourquoi maintenant, avec les statistiques ;
  3. vous passez l'ordre dans l'application, puis répondez `oui` (ou `non`)
     en commentaire du ticket ; le bot met à jour votre portefeuille.

L'état est stocké dans `etat/portefeuille.json` (versionné dans le dépôt).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

from . import rapport
from .config import Config
from .score import BUCKET_LABELS, BUCKETS, label, moment_score, score_stats
from .strategy import Order, decide, drawdown, reserve_target_pct

ETAT = Path("etat/portefeuille.json")
A_PUBLIER = Path("etat/a_publier.json")
RAPPORTS = Path("rapports")
EXPIRATION_JOURS = 5
PAUSE_APRES_NON = 7

AIDE = """**Commandes** (en commentaire de n'importe quel ticket) :
- `oui` : j'ai passé les ordres proposés → le bot les enregistre
- `non` : je ne fais rien → le bot repropose dans 7 jours
- `apport 300` : changer l'apport mensuel (en €)
- `capital 2000` : ajouter une somme ponctuelle à investir
- `possede EUNL.DE 12` : déclarer des parts que vous avez déjà
- `aide` : afficher cette aide"""


# --------------------------------------------------------------------------- état

def etat_vide(cfg: Config) -> dict:
    return {
        "positions": {},
        "cash": 0.0,
        "apport_en_attente": 0.0,
        "apport_mensuel": cfg.monthly_contribution,
        "dernier_mois_apport": None,
        "reserve_pct_appliquee": None,
        "pause_jusqua": None,
        "proposition": None,
        "dernier_mois_plan": None,
        "palier_alerte": 0,
        "bulletin_ticket": None,
        "achats": [],
        "historique": [],
    }


def charger_etat(cfg: Config) -> dict:
    if ETAT.exists():
        return {**etat_vide(cfg), **json.loads(ETAT.read_text(encoding="utf-8"))}
    return etat_vide(cfg)


def sauver_etat(etat: dict) -> None:
    ETAT.parent.mkdir(parents=True, exist_ok=True)
    ETAT.write_text(json.dumps(etat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- GitHub

class GitHub:
    """Client minimal de l'API GitHub (jeton fourni automatiquement par Actions)."""

    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN")
        self.repo = os.environ.get("GITHUB_REPOSITORY")
        self.api = os.environ.get("GITHUB_API_URL", "https://api.github.com")

    @property
    def actif(self) -> bool:
        return bool(self.token and self.repo)

    def _req(self, method: str, path: str, **kw):
        r = requests.request(
            method, f"{self.api}/repos/{self.repo}{path}", timeout=30,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}, **kw,
        )
        r.raise_for_status()
        return r.json() if r.text else {}

    def creer_ticket(self, titre: str, corps: str, label: str = "proposition") -> int:
        owner = self.repo.split("/")[0]
        try:
            return self._req("POST", "/issues", json={"title": titre, "body": corps, "labels": [label], "assignees": [owner]})["number"]
        except requests.HTTPError:  # libellé ou assignation refusés : on crée le ticket simple
            return self._req("POST", "/issues", json={"title": titre, "body": corps})["number"]

    def commenter(self, numero: int, texte: str) -> None:
        self._req("POST", f"/issues/{numero}/comments", json={"body": texte})

    def fermer(self, numero: int) -> None:
        self._req("PATCH", f"/issues/{numero}", json={"state": "closed"})

    def est_ouvert(self, numero: int) -> bool:
        return self._req("GET", f"/issues/{numero}")["state"] == "open"


# --------------------------------------------------------------------------- analyse

def nom(cfg: Config, t: str) -> str:
    return cfg.noms.get(t, t)


def tranche(score: float) -> str | None:
    if pd.isna(score):
        return None
    for lo, hi, lab in zip(BUCKETS, BUCKETS[1:], BUCKET_LABELS):
        if lo <= score < hi:
            return lab
    return None


def analyser(cfg: Config, prix: pd.DataFrame, prix_stats: pd.Series) -> dict:
    feats = moment_score(prix[cfg.benchmark])
    feats_long = moment_score(prix_stats)
    return {
        "feats": feats,
        "stats_long": score_stats(prix_stats, feats_long["score"]),
        "stats_bench": score_stats(prix[cfg.benchmark], feats["score"]),
        "jour": feats.index[-1],
        "score": float(feats["score"].iloc[-1]),
    }


def pourquoi(cfg: Config, a: dict) -> str:
    f = a["feats"].iloc[-1]
    return (
        f"Score du moment : **{a['score']:.0f}/100 — {label(a['score'])}**. "
        f"{nom(cfg, cfg.benchmark)} est à {-f['baisse']:+.1%} de son plus haut sur 1 an, "
        f"{f['ecart_sma']:+.1%} par rapport à sa moyenne 200 jours, RSI {f['rsi']:.0f}."
    )


def resume_stats(cfg: Config, a: dict) -> str:
    t = tranche(a["score"])
    if t is None:
        return ""
    s, base = a["stats_long"].loc[t], a["stats_long"].loc["Tous les jours"]
    return (
        f"Historiquement ({cfg.stats_ticker} depuis {a['stats_long'].attrs.get('debut', '1950')}), quand le score était "
        f"dans la tranche {t} : **{rapport.pct(s['moy_12m'])} en moyenne 12 mois plus tard**, positif dans "
        f"{rapport.pct(s['pos_12m'], False)} des cas (tous jours confondus : {rapport.pct(base['moy_12m'])}, "
        f"{rapport.pct(base['pos_12m'], False)})."
    )


# --------------------------------------------------------------------------- décision

def evaluer(cfg: Config, etat: dict, prix: pd.DataFrame, a: dict, aujourdhui: date) -> dict | None:
    """Retourne une proposition (dict) ou None s'il n'y a rien à faire aujourd'hui."""
    mois = aujourdhui.strftime("%Y-%m")
    if cfg.mode == "plan":
        enregistrer_plan(cfg, etat, prix, aujourdhui)
    elif etat["dernier_mois_apport"] != mois:
        etat["apport_en_attente"] += float(etat["apport_mensuel"])
        etat["dernier_mois_apport"] = mois

    if etat["proposition"] is not None:
        return None
    if etat["pause_jusqua"] and aujourdhui.isoformat() < etat["pause_jusqua"]:
        return None
    if aujourdhui.weekday() >= 5:
        return None  # week-end : bourse fermée, on ne propose pas d'ordre sur des prix figés
    if cfg.mode == "plan":
        return evaluer_plan(cfg, etat, prix, a, aujourdhui)

    attente = etat["apport_en_attente"]
    liberer = attente > 0 and (a["score"] >= cfg.score_seuil or aujourdhui.day >= cfg.jour_limite)
    liberation = attente if liberer else 0.0

    d = decide(cfg, prix, etat["positions"], etat["cash"] + liberation)
    pct = reserve_target_pct(cfg, d.drawdown)
    vente = any(o.side == "sell" for o in d.orders)
    palier = bool(etat["positions"]) and etat["reserve_pct_appliquee"] is not None and pct < etat["reserve_pct_appliquee"]
    if not (liberer or vente or palier) or not d.orders:
        if liberer and not d.orders:
            d.notes.append("Montant trop faible pour un ordre : il s'accumule pour le mois suivant.")
        return None

    if vente and not any(o.side == "buy" for o in d.orders):
        type_ = "vente"
    elif palier:
        type_ = "krach"
    elif a["score"] >= cfg.score_seuil:
        type_ = "bon_moment"
    else:
        type_ = "date_limite"
    return {
        "type": type_,
        "date": aujourdhui.isoformat(),
        "liberation": liberation,
        "reserve_pct": pct,
        "score": a["score"],
        "ordres": [asdict(o) for o in d.orders],
        "notes": d.notes,
        "total": d.total_value,
    }


def enregistrer_plan(cfg: Config, etat: dict, prix: pd.DataFrame, aujourdhui: date) -> None:
    """Le plan d'épargne Trade Republic achète tout seul : le bot l'inscrit au portefeuille."""
    mois = aujourdhui.strftime("%Y-%m")
    if etat["dernier_mois_plan"] == mois or aujourdhui.day < cfg.jour_plan:
        return
    dernier = prix.ffill().iloc[-1]
    montant = float(etat["apport_mensuel"])
    for t, w in cfg.targets.items():
        px = float(dernier[t])
        qty = round(montant * w / px, 6)  # le plan achète des fractions de parts
        etat["positions"][t] = round(etat["positions"].get(t, 0.0) + qty, 6)
        etat["achats"].append({"date": aujourdhui.isoformat(), "ticker": t, "prix": px, "quantite": qty, "plan": True})
    etat["historique"].append({"type": "plan", "date": aujourdhui.isoformat(), "montant": montant})
    etat["dernier_mois_plan"] = mois


def evaluer_plan(cfg: Config, etat: dict, prix: pd.DataFrame, a: dict, aujourdhui: date) -> dict | None:
    dd = drawdown(prix[cfg.benchmark], cfg.drawdown_window_days)
    if dd < 0.05:
        etat["palier_alerte"] = 0  # marché revenu près de ses plus hauts : alertes réarmées
    palier = sum(1 for al in cfg.alertes_krach if dd >= al["drawdown"])
    base = {"date": aujourdhui.isoformat(), "reserve_pct": 0.0, "score": a["score"]}

    if palier > etat["palier_alerte"]:
        etat["palier_alerte"] = palier
        alerte = cfg.alertes_krach[palier - 1]
        montant = alerte["mois"] * float(etat["apport_mensuel"])
        d = decide(cfg, prix, etat["positions"], montant)
        if d.orders:
            return {**base, "type": "krach_plan", "liberation": montant, "ordres": [asdict(o) for o in d.orders],
                    "notes": d.notes + [f"Baisse de {dd:.0%} : palier -{alerte['drawdown']:.0%} franchi"],
                    "total": d.total_value, "baisse": dd}

    if etat["positions"]:
        d = decide(cfg, prix, etat["positions"], 0.0)
        if any(o.side == "sell" for o in d.orders):
            return {**base, "type": "vente", "liberation": 0.0, "ordres": [asdict(o) for o in d.orders],
                    "notes": d.notes, "total": d.total_value}
    return None


TITRES = {
    "bon_moment": "🟢 Bon moment pour investir {montant} (score {score:.0f}/100)",
    "date_limite": "🟡 Investissement du mois : {montant} (score {score:.0f}/100, meilleur moment du mois)",
    "krach": "🔵 Le marché a chuté : déployer la réserve, {montant} (score {score:.0f}/100)",
    "vente": "🟠 Prendre des bénéfices : rééquilibrage (score {score:.0f}/100)",
    "krach_plan": "🔵 Krach : versement exceptionnel conseillé de {montant} (score {score:.0f}/100)",
}

EXPLICATIONS = {
    "bon_moment": "Le marché est en repli par rapport à son historique : c'est le meilleur moment du mois "
                  "pour placer votre apport.",
    "date_limite": "Le marché n'a pas offert de repli marqué ce mois-ci. Attendre davantage coûte plus "
                   "(en moyenne) que d'acheter maintenant : c'est le meilleur moment *disponible*.",
    "krach": "Le marché a franchi un palier de baisse. Le bot puise dans la réserve gardée pour ce moment "
             "et achète pendant que les prix sont bas.",
    "vente": "Un actif a tellement monté qu'il dépasse sa part cible. Le bot vend l'excédent "
             "pour sécuriser une partie du gain et revenir à l'équilibre.",
    "krach_plan": "Le marché a nettement chuté. Surtout, ne vendez rien et ne coupez pas votre plan d'épargne. "
                  "Si vous avez de l'épargne disponible, c'est le moment d'un versement exceptionnel : "
                  "historiquement, acheter pendant les krachs a été très payant.",
}


def corps_ticket(cfg: Config, prop: dict, a: dict, image_url: str | None) -> str:
    lignes = [
        "| Action | Actif | ISIN (à chercher dans l'app) | Quantité | Prix indicatif | Montant ~ |",
        "|---|---|---|---:|---:|---:|",
    ]
    for o in prop["ordres"]:
        sens = "**ACHETER**" if o["side"] == "buy" else "**VENDRE**"
        lignes.append(
            f"| {sens} | {nom(cfg, o['ticker'])} | `{cfg.isin.get(o['ticker'], o['ticker'])}` | "
            f"{o['quantity']:g} | {o['price']:,.2f} € | {o['quantity'] * o['price']:,.2f} € |".replace(",", " ")
        )
    frais = cfg.fee_fixed * len(prop["ordres"])
    t = tranche(prop["score"])
    parts = [
        f"### {EXPLICATIONS[prop['type']]}",
        "#### Ce que je vous propose dans Trade Republic",
        "\n".join(lignes),
        f"Frais estimés : {frais:.0f} € ({cfg.fee_fixed:.0f} € par ordre). Ordre au marché, à passer de préférence "
        "pendant les heures d'ouverture de Xetra (9h-17h30).",
        "#### Pourquoi maintenant",
        pourquoi(cfg, a),
        resume_stats(cfg, a),
        "<details><summary>Statistiques complètes du score</summary>\n\n"
        f"**{cfg.stats_ticker}** (long historique) :\n\n{rapport.stats_table(a['stats_long'], t)}\n\n"
        f"**{nom(cfg, cfg.benchmark)}** :\n\n{rapport.stats_table(a['stats_bench'], t)}\n\n"
        "Les rendements passés ne préjugent pas des rendements futurs.\n</details>",
    ]
    if image_url:
        parts.append(f"![Graphique]({image_url})")
    parts += [
        "#### Votre décision",
        "Après avoir passé (ou non) les ordres, répondez **en commentaire** :\n"
        "- `oui` → c'est fait, j'enregistre dans votre portefeuille\n"
        f"- `non` → j'ignore et je repropose dans {PAUSE_APRES_NON} jours\n\n"
        f"Sans réponse, la proposition expire dans {EXPIRATION_JOURS} jours.",
        "<details><summary>Détails techniques</summary>\n\n" + "\n".join(f"- {n}" for n in prop["notes"]) + "\n</details>",
    ]
    return "\n\n".join(p for p in parts if p)


def titre_ticket(prop: dict) -> str:
    achats = sum(o["quantity"] * o["price"] for o in prop["ordres"] if o["side"] == "buy")
    montant = f"{achats:,.0f} €".replace(",", " ")
    return TITRES[prop["type"]].format(montant=montant, score=prop["score"])


# --------------------------------------------------------------------------- commandes

def appliquer(cfg: Config, etat: dict, prop: dict) -> None:
    etat["apport_en_attente"] = max(0.0, etat["apport_en_attente"] - prop["liberation"])
    etat["cash"] += prop["liberation"]
    pos = etat["positions"]
    for o in map(lambda d: Order(**d), prop["ordres"]):
        frais = cfg.fee_fixed + o.value * cfg.fee_bps / 1e4
        if o.side == "buy":
            etat["cash"] -= o.value + frais
            pos[o.ticker] = round(pos.get(o.ticker, 0.0) + o.quantity, 6)
            etat["achats"].append({"date": prop["date"], "ticker": o.ticker, "prix": o.price, "quantite": o.quantity})
        else:
            etat["cash"] += o.value - frais
            pos[o.ticker] = round(pos.get(o.ticker, 0.0) - o.quantity, 6)
    etat["positions"] = {t: q for t, q in pos.items() if q > 1e-9}
    etat["cash"] = round(max(etat["cash"], 0.0), 2)
    etat["reserve_pct_appliquee"] = prop["reserve_pct"]


def executer_commande(cfg: Config, etat: dict, texte: str, numero: int | None, aujourdhui: date) -> str | None:
    """Traite le commentaire de l'utilisateur ; renvoie la réponse du bot (ou None)."""
    mots = re.sub(r"[^\w.,\s-]", " ", texte.strip().lower()).split()
    if not mots:
        return None
    cmd, args = mots[0], mots[1:]
    prop = etat["proposition"]

    if cmd in ("oui", "ok", "fait", "valide", "validé"):
        if not prop or (numero and numero not in (prop.get("ticket"), etat.get("bulletin_ticket"))):
            return "Aucune proposition en attente sur ce ticket."
        appliquer(cfg, etat, prop)
        etat["historique"].append({**prop, "decision": "oui", "decide_le": aujourdhui.isoformat()})
        etat["proposition"] = None
        return "✅ Enregistré. " + resume_portefeuille(cfg, etat)
    if cmd in ("non", "refus", "annule", "annuler"):
        if not prop or (numero and numero not in (prop.get("ticket"), etat.get("bulletin_ticket"))):
            return "Aucune proposition en attente sur ce ticket."
        etat["historique"].append({**prop, "decision": "non", "decide_le": aujourdhui.isoformat()})
        etat["proposition"] = None
        etat["pause_jusqua"] = (aujourdhui + timedelta(days=PAUSE_APRES_NON)).isoformat()
        return f"👌 Ignoré. L'argent prévu reste en attente ; prochaine proposition au plus tôt le {etat['pause_jusqua']}."
    if cmd == "apport" and args:
        etat["apport_mensuel"] = _nombre(args[0])
        return f"✅ Apport mensuel fixé à {etat['apport_mensuel']:,.0f} €.".replace(",", " ")
    if cmd == "capital" and args:
        montant = _nombre(args[0])
        etat["apport_en_attente"] += montant
        return f"✅ {montant:,.0f} € ajoutés : ils seront proposés au meilleur moment.".replace(",", " ")
    if cmd in ("possede", "possède") and len(args) >= 2:
        ticker = args[0].upper()
        connus = {t.upper(): t for t in cfg.targets}
        if ticker not in connus:
            return f"Actif inconnu : {ticker}. Actifs suivis : {', '.join(cfg.targets)}."
        etat["positions"][connus[ticker]] = _nombre(args[1])
        return "✅ Position enregistrée. " + resume_portefeuille(cfg, etat)
    if cmd == "aide":
        return AIDE
    return None


def _nombre(s: str) -> float:
    v = float(s.replace(",", "."))
    if v < 0 or v > 10_000_000:
        raise ValueError(f"Montant invalide : {s}")
    return v


def resume_portefeuille(cfg: Config, etat: dict) -> str:
    pos = ", ".join(f"{q:g} × {nom(cfg, t)}" for t, q in etat["positions"].items()) or "aucune position"
    return (
        f"Portefeuille suivi : {pos} ; réserve {etat['cash']:,.0f} € ; "
        f"en attente d'investissement {etat['apport_en_attente']:,.0f} €.".replace(",", " ")
    )


# --------------------------------------------------------------------------- rapport du jour

def tableau_de_bord(cfg: Config, etat: dict, prix: pd.DataFrame, a: dict) -> str:
    dernier = prix.ffill().iloc[-1]
    valeur = sum(q * float(dernier[t]) for t, q in etat["positions"].items())
    prop = etat["proposition"]
    statut = (
        f"⏳ Proposition en attente de votre réponse : ticket #{prop['ticket']}" if prop and prop.get("ticket")
        else "⏳ Proposition prête, publication en cours" if prop
        else "✅ Rien à faire aujourd'hui : le bot attend le meilleur moment."
    )
    return "\n\n".join([
        f"# Tableau de bord — {a['jour']:%d/%m/%Y}",
        statut,
        pourquoi(cfg, a),
        resume_stats(cfg, a),
        "![Marché](marche.png)",
        "## Portefeuille suivi",
        resume_portefeuille(cfg, etat) + f" Valeur des positions : {valeur:,.0f} €.".replace(",", " "),
        (f"Apport mensuel : {etat['apport_mensuel']:,.0f} € — proposé dès que le score atteint "
         f"{cfg.score_seuil:.0f}, au plus tard le {cfg.jour_limite} du mois." if cfg.mode == "timing" else
         f"Plan d'épargne : {etat['apport_mensuel']:,.0f} € par mois, exécuté par Trade Republic vers le "
         f"{cfg.jour_plan} du mois (gratuit). Le bot alerte en cas de krach ou de déséquilibre."),
        "## Statistiques du score",
        f"**{cfg.stats_ticker}** :\n\n" + rapport.stats_table(a["stats_long"], tranche(a["score"])),
        AIDE,
    ])


def lancer_conseil(cfg: Config, prix: pd.DataFrame, prix_stats: pd.Series, aujourdhui: date | None = None) -> dict | None:
    aujourdhui = aujourdhui or date.today()
    etat = charger_etat(cfg)
    gh = GitHub()
    a = analyser(cfg, prix, prix_stats)
    a["stats_long"].attrs["debut"] = prix_stats.dropna().index[0].year

    prop = etat["proposition"]
    if prop and prop.get("ticket") and gh.actif:
        if not gh.est_ouvert(prop["ticket"]):
            etat["historique"].append({**prop, "decision": "fermé sans réponse"})
            etat["proposition"] = None
        elif aujourdhui.isoformat() >= (date.fromisoformat(prop["date"]) + timedelta(days=EXPIRATION_JOURS)).isoformat():
            gh.commenter(prop["ticket"], "⌛ Proposition expirée (les prix ont changé). Je vous en ferai une nouvelle.")
            gh.fermer(prop["ticket"])
            etat["historique"].append({**prop, "decision": "expirée"})
            etat["proposition"] = None

    nb_achats = len(etat["achats"])
    nouvelle = evaluer(cfg, etat, prix, a, aujourdhui)
    a_publier = {}
    if nouvelle:
        etat["proposition"] = nouvelle
        image = RAPPORTS / "propositions" / f"{nouvelle['date']}.png"
        rapport.chart_market(a["feats"], nom(cfg, cfg.benchmark), cfg.score_seuil, etat["achats"], image)
        nouvelle["image"] = str(image)
        a_publier.update(titre=titre_ticket(nouvelle), corps=corps_ticket(cfg, nouvelle, a, "{IMAGE_URL}"))
    if cfg.bulletin_quotidien:
        a_publier["bulletin"] = bulletin(cfg, etat, prix, a, aujourdhui, plan_du_jour=len(etat["achats"]) > nb_achats)
    if a_publier:
        A_PUBLIER.parent.mkdir(parents=True, exist_ok=True)
        A_PUBLIER.write_text(json.dumps(a_publier, ensure_ascii=False, indent=2), encoding="utf-8")

    rapport.chart_market(a["feats"], nom(cfg, cfg.benchmark), cfg.score_seuil, etat["achats"], RAPPORTS / "marche.png")
    sauver_etat(etat)
    (RAPPORTS / "tableau-de-bord.md").write_text(tableau_de_bord(cfg, etat, prix, a) + "\n", encoding="utf-8")
    return nouvelle


def valeur_portefeuille(etat: dict, prix: pd.DataFrame) -> float:
    dernier = prix.ffill().iloc[-1]
    return sum(q * float(dernier[t]) for t, q in etat["positions"].items())


def bulletin(cfg: Config, etat: dict, prix: pd.DataFrame, a: dict, aujourdhui: date, plan_du_jour: bool) -> str:
    f = a["feats"].iloc[-1]
    lignes = [f"### 📅 {aujourdhui:%d/%m/%Y} — score {a['score']:.0f}/100 · {label(a['score'])}"]
    lignes.append(
        f"{nom(cfg, cfg.benchmark)} : {-f['baisse']:+.1%} depuis son plus haut sur 1 an, "
        f"{f['ecart_sma']:+.1%} vs moyenne 200 jours (clôture du {a['jour']:%d/%m})."
    )
    if aujourdhui.weekday() >= 5:
        lignes.append("Bourse fermée aujourd'hui.")
    if plan_du_jour:
        lignes.append(f"🧾 Plan d'épargne de {float(etat['apport_mensuel']):,.0f} € inscrit au portefeuille.".replace(",", " "))
    prop = etat["proposition"]
    if prop:
        lignes.append(f"👉 **Action à faire** : {titre_ticket(prop)} — voir le ticket {{TICKET}} et répondre `oui` ou `non`.")
    elif cfg.mode == "timing" and etat["apport_en_attente"] > 0:
        lignes.append(
            f"⏳ Rien à faire : {etat['apport_en_attente']:,.0f} € attendent le meilleur moment "
            f"(score ≥ {cfg.score_seuil:.0f} ou le {cfg.jour_limite} du mois au plus tard).".replace(",", " ")
        )
    else:
        lignes.append("✅ Rien à faire aujourd'hui. Ne touchez à rien : le temps travaille pour vous.")
    if etat["positions"]:
        lignes.append(f"Portefeuille suivi : ~{valeur_portefeuille(etat, prix):,.0f} €.".replace(",", " "))
    return "\n\n".join(lignes)


def publier(cfg: Config) -> int | None:
    """Crée le ticket préparé par `lancer_conseil` (une fois l'image poussée) et poste le bulletin."""
    if not A_PUBLIER.exists():
        return None
    etat = charger_etat(cfg)
    data = json.loads(A_PUBLIER.read_text(encoding="utf-8"))
    A_PUBLIER.unlink()
    gh = GitHub()
    prop = etat["proposition"]
    numero = None
    if not gh.actif:
        if "titre" in data:
            print(f"\n=== {data['titre']} ===\n{data['corps']}")
        if "bulletin" in data:
            print(f"\n--- Bulletin ---\n{data['bulletin']}")
        return None
    if "titre" in data and prop:
        branche = os.environ.get("GITHUB_REF_NAME", "main")
        url = f"https://github.com/{gh.repo}/blob/{branche}/{prop['image']}?raw=true"
        numero = gh.creer_ticket(data["titre"], data["corps"].replace("{IMAGE_URL}", url))
        prop["ticket"] = numero
    if "bulletin" in data:
        b = etat.get("bulletin_ticket")
        if not b or not gh.est_ouvert(b):
            b = gh.creer_ticket(
                "📅 Bulletin quotidien du bot",
                "Chaque jour, le bot poste ici un point sur le marché. Vous recevez une notification "
                "à chaque message.\n\nVous pouvez répondre `oui` / `non` ici aussi quand une action est proposée.\n\n" + AIDE,
                label="bulletin",
            )
            etat["bulletin_ticket"] = b
        ticket = f"#{prop['ticket']}" if prop and prop.get("ticket") else "ouvert"
        gh.commenter(b, data["bulletin"].replace("{TICKET}", ticket))
    sauver_etat(etat)
    return numero


def traiter_commentaire(cfg: Config, numero: int, texte: str) -> str | None:
    etat = charger_etat(cfg)
    try:
        reponse = executer_commande(cfg, etat, texte, numero, date.today())
    except ValueError as e:
        reponse = f"❌ {e}"
    if reponse is None:
        return None
    sauver_etat(etat)
    gh = GitHub()
    if gh.actif:
        gh.commenter(numero, reponse)
        if reponse.startswith(("✅ Enregistré", "👌")):
            gh.fermer(numero)
    return reponse
