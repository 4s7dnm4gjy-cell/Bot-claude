"""Radar d'opportunités : actions et ETF disponibles sur Trade Republic.

Chaque jour, le bot calcule pour chaque titre de la liste le même score du
moment (0-100 : 100 = parmi ses prix les plus « soldés » de son histoire) et
les statistiques de ce qui a suivi, sur l'historique de CE titre.

Il retient les titres :
  * au score élevé (repli marqué par rapport à leur propre historique) ;
  * dont la tendance de long terme reste positive (plus haut qu'il y a 5 ans),
    pour éviter les entreprises en déclin durable.

Limites, affichées dans chaque alerte : la liste contient des entreprises qui
ont *réussi* jusqu'ici (biais du survivant), donc les statistiques passées
sont flatteuses ; une action seule peut perdre beaucoup plus qu'un ETF.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .score import moment_score, score_stats

JOURS_5_ANS = 252 * 5


@dataclass
class Opportunite:
    ticker: str
    nom: str
    isin: str
    type: str  # "action" | "ETF"
    prix: float
    score: float
    baisse: float  # depuis le plus haut sur 1 an
    perf_5ans: float
    tranche: str | None
    moy_12m: float  # rendement moyen 12 mois après, dans cette tranche
    pos_12m: float
    n_12m: int
    base_moy_12m: float  # tous jours confondus
    pire_12m: float

    @property
    def favorable(self) -> bool:
        """Historiquement, acheter à ce niveau de score a fait mieux que la moyenne."""
        return self.n_12m >= 100 and self.moy_12m > self.base_moy_12m

    def ligne(self) -> str:
        etoile = "⭐ " if self.favorable else ""
        return (
            f"{etoile}**{self.nom}** ({self.type}, ISIN `{self.isin}`) — score **{self.score:.0f}/100**, "
            f"{-self.baisse:+.0%} depuis son plus haut ; historiquement à ce niveau : "
            f"{self.moy_12m:+.0%} à 12 mois en moyenne, positif {self.pos_12m:.0%} des cas "
            f"(moyenne du titre : {self.base_moy_12m:+.0%})"
        )


def analyser_titre(ticker: str, info: dict, prix: pd.Series) -> Opportunite | None:
    s = prix.dropna()
    if len(s) < JOURS_5_ANS + 252:
        return None  # historique trop court pour des statistiques fiables
    feats = moment_score(s)
    score = float(feats["score"].iloc[-1])
    if np.isnan(score):
        return None
    stats = score_stats(s, feats["score"])
    from .conseil import tranche  # import local : évite une dépendance circulaire

    t = tranche(score)
    ligne = stats.loc[t] if t in stats.index else None
    base = stats.loc["Tous les jours"]
    return Opportunite(
        ticker=ticker,
        nom=info.get("nom", ticker),
        isin=info.get("isin", ticker),
        type=info.get("type", "action"),
        prix=float(s.iloc[-1]),
        score=score,
        baisse=float(feats["baisse"].iloc[-1]),
        perf_5ans=float(s.iloc[-1] / s.iloc[-JOURS_5_ANS] - 1),
        tranche=t,
        moy_12m=float(ligne["moy_12m"]) if ligne is not None else np.nan,
        pos_12m=float(ligne["pos_12m"]) if ligne is not None else np.nan,
        n_12m=int(ligne["n_12m"]) if ligne is not None else 0,
        base_moy_12m=float(base["moy_12m"]),
        pire_12m=float(ligne["pire_12m"]) if ligne is not None else np.nan,
    )


def scanner(liste: dict[str, dict], prix: pd.DataFrame, score_min: float) -> list[Opportunite]:
    """Titres au score >= score_min et en tendance longue positive, du plus soldé au moins soldé."""
    out = []
    for ticker, info in liste.items():
        if ticker not in prix:
            continue
        o = analyser_titre(ticker, info, prix[ticker])
        if o and o.score >= score_min and o.perf_5ans > 0:
            out.append(o)
    return sorted(out, key=lambda o: (o.favorable, o.score), reverse=True)
