"""Analyse fondamentale : l'action est-elle bon marché et saine, ou seulement en baisse ?

Le score du moment (0-100) mesure une baisse par rapport au passé du titre. Il
dit « le cours a baissé », pas « l'entreprise est bonne et pas chère ». Ce module
ajoute un score fondamental (0-100) à partir des données publiques de Yahoo
Finance :

  * croissance du chiffre d'affaires   (sur un an)              20 pts
  * croissance des bénéfices           (sur un an)              20 pts
  * avis des analystes + potentiel vers leur objectif de cours  30 pts
  * valorisation : P/E sur les bénéfices attendus               15 pts
  * santé : marge nette et endettement                          15 pts

Forte baisse face au marché (plus de 20 % en 3 mois) : voir `sanction_du_marche`,
qui distingue une braderie (perspectives intactes, bonus) d'une vraie dégradation.

Une donnée manquante compte pour la moitié des points de son critère (ni bonus
ni pénalité). Sans aucune donnée, le score est inconnu et le titre n'est pas
proposé (sauf ETF, qui n'ont pas de bénéfices propres).
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Callable

CHAMPS = ("revenueGrowth", "earningsGrowth", "recommendationMean", "numberOfAnalystOpinions",
          "targetMeanPrice", "currentPrice", "forwardPE", "trailingPE", "profitMargins", "debtToEquity",
          "forwardEps", "trailingEps")


ERREURS: list[str] = []  # pour le journal : pourquoi une lecture a échoué


def lire_infos(ticker: str, essais: int = 3) -> dict:
    """Données fondamentales Yahoo (vide si indisponible), avec relances espacées."""
    import time

    for essai in range(essais):
        try:
            import yfinance as yf

            infos = yf.Ticker(ticker).info or {}
            time.sleep(0.4)  # Yahoo limite les appels rapprochés
            utiles = {k: infos.get(k) for k in CHAMPS if infos.get(k) is not None}
            if not utiles:
                ERREURS.append(f"{ticker}: réponse sans donnée utile ({len(infos)} champs : {list(infos)[:8]})")
            return utiles
        except Exception as e:  # réseau, limite d'appels, titre inconnu… : on ne bloque pas le bot
            ERREURS.append(f"{ticker}: {type(e).__name__}: {str(e)[:120]}")
            time.sleep(3 * (essai + 1))
    return {}


def _nombre(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def score_fondamental(infos: dict) -> tuple[float | None, list[str]]:
    """Score 0-100 et explications lisibles ; None si aucune donnée exploitable.

    Barème (100 pts) : passé (CA 15, bénéfices 15), avenir (bénéfices attendus 15),
    analystes (avis 15, objectif de cours 10), valorisation 15, santé 15.
    """
    g = {k: _nombre(infos.get(k)) for k in CHAMPS}
    if all(v is None for v in g.values()):
        return None, ["aucune donnée fondamentale disponible"]
    pts, notes = 0.0, []

    ca = g["revenueGrowth"]
    if ca is None:
        pts += 7.5
    else:
        pts += 15 if ca > 0.05 else 7.5 if ca > 0 else 0
        notes.append(f"chiffre d'affaires {ca:+.1%} sur un an")

    bpa = g["earningsGrowth"]
    if bpa is None:
        pts += 7.5
    else:
        pts += 15 if bpa > 0.10 else 7.5 if bpa > 0 else 0
        notes.append(f"bénéfices {bpa:+.1%} sur un an")

    # Regard vers l'avenir : bénéfice par action attendu sur 12 mois vs dernier connu.
    fe, te = g["forwardEps"], g["trailingEps"]
    if fe is None or te is None or te <= 0:
        pts += 7.5 if fe is None or te is None else (15 if fe and fe > 0 else 0)
    else:
        attendu = fe / te - 1
        pts += 15 if attendu > 0.08 else 7.5 if attendu > 0 else 0
        notes.append(f"bénéfices attendus {attendu:+.0%} sur 12 mois")

    reco, n = g["recommendationMean"], g["numberOfAnalystOpinions"] or 0
    if reco is None or n < 3:
        pts += 7.5
    else:
        pts += 15 if reco <= 1.8 else 11 if reco <= 2.3 else 5 if reco <= 2.8 else 0
        avis = "achat fort" if reco <= 1.8 else "achat" if reco <= 2.3 else "conserver" if reco <= 2.8 else "vendre"
        notes.append(f"analystes : « {avis} » ({reco:.1f}/5, {int(n)} avis)")
    cible, cours = g["targetMeanPrice"], g["currentPrice"]
    if cible and cours:
        potentiel = cible / cours - 1
        if potentiel > 0.5:  # écart irréaliste : objectifs pas encore révisés après une chute
            pts += 3
            notes.append(f"objectif des analystes {potentiel:+.0%} : peu crédible, probablement pas encore révisé")
        else:
            pts += 10 if potentiel > 0.15 else 5 if potentiel > 0.05 else 0
            notes.append(f"objectif moyen des analystes : {potentiel:+.0%}")
    else:
        pts += 5

    fpe, tpe = g["forwardPE"], g["trailingPE"]
    if fpe is None or fpe <= 0:
        pts += 7.5 if fpe is None else 0
        if fpe is not None:
            notes.append("bénéfices attendus négatifs")
    else:
        pts += 15 if fpe < 15 else 10 if fpe < 22 else 5 if fpe < 30 else 0
        txt = f"P/E attendu {fpe:.1f}"
        if tpe and tpe > 0:
            txt += f" (actuel {tpe:.1f})"
        notes.append(txt)

    marge, dette = g["profitMargins"], g["debtToEquity"]
    pts += 5 if marge is None else 10 if marge > 0.08 else 5 if marge > 0 else 0
    if marge is not None:
        notes.append(f"marge nette {marge:.0%}")
    pts += 2.5 if dette is None else 5 if dette < 100 else 2 if dette < 200 else 0
    if dette is not None:
        notes.append(f"dette / capitaux propres {dette:.0f} %")
    return round(pts, 1), notes


def sanction_du_marche(vs_marche_3m: float | None, infos: dict | None = None) -> tuple[float, str | None, bool]:
    """Forte baisse face au marché : vraie mauvaise nouvelle, ou braderie ?

    Une chute de 20-30 % de plus que le marché n'est pas forcément méritée. On
    regarde ce que disent les prévisions les plus récentes :
      * braderie : bénéfices attendus en hausse, bénéfices du dernier trimestre en
        hausse, analystes à l'achat -> le prix a baissé, pas l'entreprise (bonus ;
        jamais au-delà de −45 % : une chute pareille cache trop souvent un vrai problème) ;
      * dégradation : bénéfices attendus en baisse, bénéfices qui reculent ou
        analystes à la vente -> le marché a sans doute raison (malus complet) ;
      * doute : pas assez d'éléments pour trancher (demi-malus, complet au-delà de −40 %).
    Retourne (points, explication, braderie).
    """
    if vs_marche_3m is None or vs_marche_3m >= -0.20:
        return 0.0, None, False
    g = {k: _nombre((infos or {}).get(k)) for k in CHAMPS}
    fe, te, bpa = g["forwardEps"], g["trailingEps"], g["earningsGrowth"]
    reco, n = g["recommendationMean"], g["numberOfAnalystOpinions"] or 0
    attendu = fe / te - 1 if fe is not None and te and te > 0 else None
    chute = f"{vs_marche_3m:+.0%} vs marché en 3 mois"
    plein = -25.0 if vs_marche_3m < -0.30 else -12.0

    degrade = ((attendu is not None and attendu < 0) or (fe is not None and fe <= 0)
               or (bpa is not None and bpa < 0) or (reco is not None and n >= 3 and reco > 2.8))
    if degrade:
        return plein, f"⚠️ sanction du marché méritée : {chute}, et les perspectives se dégradent ({plein:+.0f} pts)", False
    braderie = (vs_marche_3m >= -0.45 and attendu is not None and attendu >= 0.05 and (bpa is None or bpa >= 0)
                and reco is not None and n >= 3 and reco <= 2.3)
    if braderie:
        bonus = 8.0
        return bonus, (f"🏷️ braderie probable : {chute}, alors que les bénéfices attendus montent "
                       f"({attendu:+.0%}) et que les analystes restent à l'achat ({bonus:+.0f} pts)"), True
    demi = plein / 2 if vs_marche_3m >= -0.40 else plein  # chute extrême inexpliquée : prudence maximale
    return demi, f"⚠️ chute de {chute} sans explication claire dans les chiffres ({demi:+.0f} pts)", False


def enrichir(candidats: list[dict], lire: Callable[[str], dict] = lire_infos, nb_max: int = 150,
             poids_fondamental: float = 0.6, cache: Path | None = None, aujourdhui: date | None = None,
             jours_frais: int = 7, jours_max: int = 45, lectures_max: int = 100) -> list[dict]:
    """Ajoute fondamentaux et score global, puis trie du meilleur au moins bon.

    `cache` : fichier où garder les données de chaque titre. Elles ne sont relues
    chez Yahoo qu'au-delà de `jours_frais` jours ; si Yahoo refuse (ce qui arrive
    depuis les serveurs GitHub), les dernières données connues (moins de
    `jours_max` jours) sont réutilisées.
    """
    aujourdhui = aujourdhui or date.today()
    memo = json.loads(cache.read_text(encoding="utf-8")) if cache and cache.exists() else {}
    lectures = reutilisees = 0
    for c in candidats[:nb_max]:
        if c.get("type", "action") != "action":
            c["fondamental"], c["fondamental_notes"] = None, ["ETF : pas d'analyse d'entreprise"]
        else:
            infos, entree = {}, memo.get(c["ticker"])
            age = (aujourdhui - date.fromisoformat(entree["date"])).days if entree else None
            if entree and age <= jours_frais:
                infos = entree["infos"]
            elif lectures < lectures_max:
                lectures += 1
                infos = lire(c["ticker"])
                if infos:
                    memo[c["ticker"]] = {"date": aujourdhui.isoformat(), "infos": infos}
            if not infos and entree and age <= jours_max:
                infos, reutilisees = entree["infos"], reutilisees + 1
            c["fondamental"], c["fondamental_notes"] = score_fondamental(infos)
            ajust, note, braderie = sanction_du_marche(c.get("vs_marche_3m"), infos)
            c["braderie"] = braderie and c["fondamental"] is not None
            if c["fondamental"] is not None and note:
                c["fondamental"] = min(100.0, max(0.0, c["fondamental"] + ajust))
                c["fondamental_notes"].append(note)
            if entree and infos is entree["infos"] and age and age > jours_frais:
                c["fondamental_notes"].append(f"données du {entree['date']} (Yahoo indisponible aujourd'hui)")
        f = c["fondamental"] if c["fondamental"] is not None else 60.0  # ETF / inconnu : neutre
        c["score_global"] = round((1 - poids_fondamental) * c["score"] + poids_fondamental * f, 1)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(memo, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    analyses = candidats[:nb_max]
    ok = sum(1 for c in analyses if c["fondamental"] is not None)
    print(f"Fondamentaux : {ok}/{len(analyses)} titres notés ({lectures} lectures Yahoo, "
          f"{reutilisees} reprises de la mémoire)", flush=True)
    if ERREURS:
        print(f"  {len(ERREURS)} erreur(s), ex. : {ERREURS[:3]}", flush=True)
    return sorted(analyses, key=lambda c: c["score_global"], reverse=True)
