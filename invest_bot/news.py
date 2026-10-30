"""Lecture des actualités : opportunité ou vraie mauvaise nouvelle ?

Pour chaque titre soldé, le bot lit les titres d'articles des 30 derniers jours
(Google Actualités, en français et en anglais, sans clé ni inscription) et y
cherche des « signaux d'alarme » : scandale, fraude, enquête, procès, faillite,
avertissement sur résultats, etc.

Il compare aussi la baisse du titre à celle du marché sur 3 mois :
  * le titre baisse comme le marché       -> baisse générale, rarement grave ;
  * le titre baisse beaucoup plus que lui -> problème propre à l'entreprise.

Verdict :
  🟢 rien d'alarmant   -> l'alerte « opportunité » peut partir ;
  🟠 à vérifier        -> l'alerte part, avec les articles à lire avant de dire oui ;
  🔴 problème sérieux  -> pas d'alerte, le titre est signalé comme écarté.

C'est une lecture par mots-clés, pas une analyse : elle peut rater une
nouvelle ou s'alarmer d'un article sans gravité. Les liens sont fournis pour
que vous puissiez juger vous-même.
"""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests

GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={gl}:{lang}"
LANGUES = [("fr", "FR", "fr"), ("en-US", "US", "en")]

# Mot-clé (sans accents, minuscules) -> gravité (2 = grave, 1 = à surveiller).
# Volontairement restreint : les mots qui décrivent la baisse elle-même (« plonge »)
# ou des faits de routine (dépôt auprès de la SEC, « enquête » au sens de sondage)
# créaient trop de fausses alertes sur les vrais titres de presse.
SIGNAUX = {
    # Graves
    "fraude": 2, "fraud": 2, "scandale": 2, "scandal": 2, "faillite": 2, "bankruptcy": 2,
    "chapter 11": 2, "insolvabilite": 2, "insolvency": 2, "detournement": 2, "embezzlement": 2,
    "manipulation comptable": 2, "accounting irregularities": 2, "irregularites comptables": 2,
    "mise en examen": 2, "perquisition": 2, "criminal charges": 2, "poursuites penales": 2,
    "delisting": 2, "radiation de la cote": 2, "short seller": 2, "vendeur a decouvert": 2,
    "suspension de cotation": 2, "trading halt": 2, "defaut de paiement": 2, "misses payment": 2,
    # À surveiller
    "enquete judiciaire": 1, "enquete penale": 1, "ouvre une enquete": 1, "enquete de la sec": 1,
    "enquete de l'amf": 1, "investigation": 1, "probe": 1, "doj": 1, "ftc": 1,
    "proces": 1, "lawsuit": 1, "class action": 1, "action collective": 1, "plainte": 1, "sued": 1,
    "amende": 1, "fined": 1, "penalty": 1, "antitrust": 1, "rappel de produits": 1, "recall": 1,
    "avertissement sur resultats": 1, "profit warning": 1, "abaisse ses previsions": 1,
    "revoit a la baisse": 1, "cuts guidance": 1, "lowers guidance": 1, "cuts outlook": 1,
    "lowers outlook": 1, "guidance cut": 1, "downgrade": 1, "downgraded": 1,
    "demission": 1, "resigns": 1, "steps down": 1, "licenciements": 1, "layoffs": 1,
    "cyberattaque": 1, "data breach": 1, "boycott": 1,
}
DEMENTIS = ("denies", "dement", "rumour", "rumor", "rumeur")

# Raisons « ordinaires » d'une baisse : rien de grave, mais elles *expliquent* le recul.
# Quand un titre est donné en « braderie » alors que la presse en donne déjà la raison
# (objectifs abaissés, marges sous pression, valorisation jugée trop haute, repli de
# tout le secteur), ce n'est plus une braderie : le marché a une raison.
# Mot-clé (sans accents, minuscules) -> raison en clair.
MOTIFS = {
    # objectifs de cours abaissés par les analystes
    "price target cut": "objectifs de cours abaissés", "cuts price target": "objectifs de cours abaissés",
    "lowers price target": "objectifs de cours abaissés", "trims price target": "objectifs de cours abaissés",
    "lowers target": "objectifs de cours abaissés", "cuts target": "objectifs de cours abaissés",
    "abaisse son objectif": "objectifs de cours abaissés", "abaisse son objectif de cours": "objectifs de cours abaissés",
    "reduit son objectif": "objectifs de cours abaissés", "objectif de cours abaisse": "objectifs de cours abaissés",
    # recul malgré de bons résultats : le marché attendait mieux
    "falls despite": "recul malgré de bons résultats", "fall despite": "recul malgré de bons résultats",
    "drops despite": "recul malgré de bons résultats", "slides despite": "recul malgré de bons résultats",
    "sinks despite": "recul malgré de bons résultats", "slips despite": "recul malgré de bons résultats",
    "recule malgre": "recul malgré de bons résultats", "chute malgre": "recul malgré de bons résultats",
    "baisse malgre": "recul malgré de bons résultats",
    # valorisation
    "valuation concerns": "valorisation jugée trop élevée", "valuation worries": "valorisation jugée trop élevée",
    "valuation fears": "valorisation jugée trop élevée", "overvalued": "valorisation jugée trop élevée",
    "survalorise": "valorisation jugée trop élevée", "valorisation elevee": "valorisation jugée trop élevée",
    # marges, prévisions décevantes
    "margin pressure": "marges sous pression", "margin compression": "marges sous pression",
    "margins pressure": "marges sous pression", "pression sur les marges": "marges sous pression",
    "weaker margins": "marges sous pression", "margin moderation": "marges sous pression",
    "soft guidance": "prévisions décevantes", "weak guidance": "prévisions décevantes",
    "softer outlook": "prévisions décevantes", "guidance disappoints": "prévisions décevantes",
    "outlook disappoints": "prévisions décevantes", "misses estimates": "résultats sous les attentes",
    "misses expectations": "résultats sous les attentes", "earnings miss": "résultats sous les attentes",
    "revenue miss": "résultats sous les attentes", "manque les attentes": "résultats sous les attentes",
    "previsions decevantes": "prévisions décevantes", "perspectives decevantes": "prévisions décevantes",
    # repli de tout un secteur
    "selloff": "repli de tout le secteur", "sell-off": "repli de tout le secteur",
    "tech sell off": "repli de tout le secteur", "sector-wide": "repli de tout le secteur",
    "ai spending concerns": "inquiétudes sur les dépenses en IA", "ai spending worries": "inquiétudes sur les dépenses en IA",
    "capex concerns": "inquiétudes sur les dépenses en IA", "ai bubble": "inquiétudes sur les dépenses en IA",
    "prises de benefices": "prises de bénéfices", "profit-taking": "prises de bénéfices",
    "profit taking": "prises de bénéfices",
}

@dataclass
class Article:
    titre: str
    lien: str
    date: str
    source: str
    gravite: int = 0
    mots: list[str] = field(default_factory=list)
    raisons: list[str] = field(default_factory=list)  # raisons ordinaires de la baisse citées dans le titre


@dataclass
class Actualites:
    verdict: str  # "vert" | "orange" | "rouge" | "inconnu"
    resume: str
    vs_marche_3m: float | None
    alertes: list[Article]
    recents: list[Article]
    explications: list[Article] = field(default_factory=list)  # articles qui disent pourquoi le cours baisse

    @property
    def raisons(self) -> list[str]:
        """Raisons de la baisse déjà connues de la presse, sans doublon."""
        vues: list[str] = []
        for a in self.explications:
            vues += [r for r in a.raisons if r not in vues]
        return vues

    @property
    def pastille(self) -> str:
        return {"vert": "🟢", "orange": "🟠", "rouge": "🔴"}.get(self.verdict, "⚪")

    def court(self) -> str:
        return f"📰 {self.pastille} {self.resume}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Actualites":
        return cls(
            verdict=d["verdict"], resume=d["resume"], vs_marche_3m=d.get("vs_marche_3m"),
            alertes=[Article(**a) for a in d.get("alertes", [])],
            recents=[Article(**a) for a in d.get("recents", [])],
            explications=[Article(**a) for a in d.get("explications", [])],
        )


def _normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


# Mot entier uniquement : « fine » ne doit pas être trouvé dans « define ».
_MOTIFS = {m: re.compile(r"(?<![a-z])" + re.escape(m) + r"(?![a-z])") for m in SIGNAUX}
_RAISONS = {m: re.compile(r"(?<![a-z])" + re.escape(m) + r"(?![a-z])") for m in MOTIFS}


def raisons_baisse(titre: str) -> list[str]:
    """Raisons ordinaires de baisse citées dans un titre d'article (sans doublon, dans l'ordre)."""
    t = _normaliser(titre)
    vues: list[str] = []
    for mot, motif in _RAISONS.items():
        if motif.search(t) and MOTIFS[mot] not in vues:
            vues.append(MOTIFS[mot])
    return vues


def signaux(titre: str) -> tuple[int, list[str]]:
    t = _normaliser(titre)
    trouves = [m for m, motif in _MOTIFS.items() if motif.search(t)]
    return max((SIGNAUX[m] for m in trouves), default=0), trouves


def lire_flux(nom: str, jours: int = 30) -> list[Article]:
    """Titres d'articles récents sur `nom` (français + anglais). Lève une exception si injoignable."""
    vus, articles = set(), []
    for hl, gl, lang in LANGUES:
        url = GOOGLE_NEWS.format(q=quote(f'"{nom}" when:{jours}d'), hl=hl, gl=gl, lang=lang)
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (bot-investissement)"})
        r.raise_for_status()
        for item in ET.fromstring(r.content).iter("item"):
            titre = (item.findtext("title") or "").strip()
            cle = _normaliser(titre)[:80]
            if not titre or cle in vus:
                continue
            vus.add(cle)
            try:
                d = parsedate_to_datetime(item.findtext("pubDate") or "").date().isoformat()
            except (TypeError, ValueError):
                d = ""
            articles.append(Article(titre, item.findtext("link") or "", d, item.findtext("source") or ""))
    return sorted(articles, key=lambda a: a.date, reverse=True)


def _alias(nom: str | None) -> list[str]:
    """« Alphabet (Google) » -> ["alphabet", "google"] ; « McDonald's » -> ["mcdonald's"]."""
    if not nom:
        return []
    morceaux = re.split(r"[()]", _normaliser(nom))
    return [m.split()[0] for m in morceaux if m.strip()]


def _sujet(titre: str, alias: list[str]) -> bool:
    """L'entreprise est-elle le sujet du titre (dans ses 3 premiers mots) ?"""
    if not alias:
        return True
    debut = " ".join(_normaliser(titre).split()[:3])
    return any(a in debut for a in alias)


def analyser(articles: list[Article], vs_marche_3m: float | None, nom: str | None = None) -> Actualites:
    alias = _alias(nom)
    for a in articles:
        a.gravite, a.mots = signaux(a.titre)
        a.raisons = raisons_baisse(a.titre)
        t = _normaliser(a.titre)
        if a.gravite >= 2 and (not _sujet(a.titre, alias) or any(d in t for d in DEMENTIS)):
            a.gravite = 1  # grave pour quelqu'un d'autre, ou simple rumeur démentie
    alertes = sorted([a for a in articles if a.gravite], key=lambda a: (-a.gravite, a.date))
    graves = sum(1 for a in alertes if a.gravite >= 2)
    mineurs = len(alertes) - graves
    explications = [a for a in articles if a.raisons][:5]
    beaucoup = mineurs >= 3 and mineurs / max(len(articles), 1) >= 0.15  # inhabituel pour ce titre
    propre = vs_marche_3m is not None and vs_marche_3m < -0.15  # baisse bien pire que le marché

    if graves >= 2 or (graves >= 1 and propre):
        verdict = "rouge"
        resume = f"problème sérieux : {graves} article(s) grave(s) ({', '.join(alertes[0].mots)})"
    elif graves or beaucoup:
        verdict = "orange"
        resume = f"à vérifier : {len(alertes)} article(s) inquiétant(s) ({', '.join(alertes[0].mots)})"
    elif propre and explications:
        verdict = "orange"
        raisons = []
        for a in explications:
            raisons += [r for r in a.raisons if r not in raisons]
        resume = "raisons de la baisse déjà publiées : " + ", ".join(raisons[:3]) + " (pas une braderie sans raison)"
    elif propre:
        verdict = "orange"
        resume = "à vérifier : baisse bien plus forte que le marché" + (
            f", {mineurs} article(s) à regarder" if mineurs else ", sans article inquiétant trouvé")
    else:
        verdict = "vert"
        resume = "rien d'alarmant dans l'actualité" + (
            f" ({mineurs} article(s) mineur(s), courant pour une grande entreprise)" if mineurs else "")
    if vs_marche_3m is not None:
        resume += f" (3 mois : {vs_marche_3m:+.0%} vs marché)"
    return Actualites(verdict, resume, vs_marche_3m, alertes[:5], articles[:5], explications)


def verifier(nom: str, vs_marche_3m: float | None) -> Actualites:
    try:
        return analyser(lire_flux(nom), vs_marche_3m, nom)
    except Exception as e:  # réseau, format inattendu… : on le dit, sans bloquer le bot
        return Actualites("inconnu", f"actualités indisponibles ({type(e).__name__})", vs_marche_3m, [], [])


def section_markdown(nom: str, act: Actualites) -> str:
    lignes = [f"#### 📰 Pourquoi {nom} baisse-t-il ? (actualités des 30 derniers jours)",
              f"**{act.pastille} {act.resume[0].upper() + act.resume[1:]}**"]
    if act.vs_marche_3m is not None:
        if act.vs_marche_3m < -0.15:
            lignes.append(f"Sur 3 mois, le titre fait {-act.vs_marche_3m:.0%} de moins que le marché : "
                          "la baisse est **propre à l'entreprise**, il faut en comprendre la raison.")
        else:
            lignes.append(f"Sur 3 mois, écart avec le marché : {act.vs_marche_3m:+.0%}. "
                          "La baisse ressemble plutôt à un mouvement général.")
    if act.alertes:
        lignes.append("Articles à lire avant de répondre :")
        lignes += [f"- ⚠️ [{a.titre}]({a.lien}) — {a.source}, {a.date} *(mots : {', '.join(a.mots)})*"
                   for a in act.alertes]
    if act.explications:
        lignes.append("Raisons de la baisse déjà publiées (la presse explique le recul) :")
        lignes += [f"- 📉 [{a.titre}]({a.lien}) — {a.source}, {a.date} *({', '.join(a.raisons)})*"
                   for a in act.explications if a not in act.alertes]
    autres = [a for a in act.recents if a not in act.alertes and a not in act.explications]
    if autres:
        lignes.append("Derniers articles :")
        lignes += [f"- [{a.titre}]({a.lien}) — {a.source}, {a.date}" for a in autres]
    lignes.append("*Lecture automatique par mots-clés : elle peut se tromper. Lisez les titres avant de décider.*")
    return "\n".join(lignes)


# Révision à la baisse des perspectives : les chiffres publiés ne le montrent pas encore.
AVERTISSEMENTS = {"avertissement sur resultats", "profit warning", "abaisse ses previsions", "revoit a la baisse",
                  "cuts guidance", "lowers guidance", "cuts outlook", "lowers outlook", "guidance cut",
                  "downgrade", "downgraded"}


def avertissement_recent(act: "Actualites") -> Article | None:
    """Premier article récent annonçant une révision à la baisse (ou None)."""
    for a in act.alertes:
        if AVERTISSEMENTS & set(a.mots):
            return a
    return None
