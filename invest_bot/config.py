"""Chargement et validation de la configuration YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ReserveTier:
    """Quand le marché a chuté d'au moins `drawdown`, la réserve cible tombe à `reserve_pct`."""

    drawdown: float
    reserve_pct: float


RADAR_DEFAUTS = {
    "liste": {},          # ticker Yahoo -> {nom, isin, type}
    "fichier": None,      # fichier YAML avec la liste (ajoutée à `liste`)
    "fichiers": [],       # plusieurs fichiers (le premier est prioritaire)
    "score_min": 70,      # affiché dans le bulletin à partir de ce score
    "score_alerte": 85,   # ticket « opportunité » à partir de ce score
    "montant": 150,       # montant suggéré par opportunité (€)
    "part_max": 0.20,     # part maximale du portefeuille en titres « radar »
    "delai_jours": 30,    # pas deux alertes sur le même titre avant ce délai
    "actualites": True,   # lire l'actualité avant d'alerter (scandale, fraude…)
    "actualites_nb": 5,   # nombre de titres du radar dont on lit l'actualité chaque jour
    "fondamental_min": 70,      # score fondamental minimum pour proposer une action
    "express_minutes": 30,      # mode express : délai avant de passer au titre suivant
    "express_heures": [7, 23],  # heures de Paris où le mode express propose (bourse ouverte côté Trade Republic)
}


@dataclass
class Config:
    targets: dict[str, float]
    benchmark: str
    monthly_contribution: float = 0.0
    defensive_asset: str | None = None  # None = rester en cash

    # "Acheter au bon moment" : réserve de cash déployée quand le marché baisse.
    reserve_pct: float = 0.10
    reserve_tiers: list[ReserveTier] = field(default_factory=list)

    # "Revendre au bon moment" : rééquilibrage par bandes + filtre de tendance optionnel.
    rebalance_band: float = 0.05
    trend_filter: bool = False
    trend_window_days: int = 200

    drawdown_window_days: int = 252
    min_order_value: float = 50.0
    fractional: bool = True
    fee_bps: float = 0.0
    fee_fixed: float = 1.0  # Trade Republic : 1 € par ordre

    # "Meilleur moment du mois" : l'apport mensuel est proposé dès que le score
    # atteint `score_seuil`, au plus tard le `jour_limite` du mois.
    score_seuil: float = 60.0
    jour_limite: int = 20
    stats_ticker: str = "^GSPC"  # long historique pour les statistiques du score

    # "timing" : le bot propose l'apport du mois au meilleur moment.
    # "plan"   : l'apport passe par le plan d'épargne gratuit ; le bot surveille
    #            et alerte seulement (krach, rééquilibrage).
    mode: str = "timing"
    jour_plan: int = 2  # jour d'exécution du plan d'épargne Trade Republic
    alertes_krach: list[dict] = field(default_factory=list)  # [{drawdown: 0.15, mois: 2}, ...]
    bulletin_quotidien: bool = True  # un message par jour sur le ticket « Bulletin quotidien »

    # Radar d'opportunités (actions/ETF de Trade Republic) : voir radar.py.
    radar: dict = field(default_factory=dict)

    # Pour retrouver les actifs dans l'application du courtier.
    noms: dict[str, str] = field(default_factory=dict)
    isin: dict[str, str] = field(default_factory=dict)

    # Garde-fous d'exécution
    max_orders_per_run: int = 20
    max_turnover_pct: float = 0.50  # part max du portefeuille vendue en une fois

    def validate(self) -> None:
        if not self.targets:
            raise ValueError("`targets` ne peut pas être vide")
        total = sum(self.targets.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Les poids cibles doivent sommer à 1.0 (actuel : {total:.4f})")
        if any(w < 0 for w in self.targets.values()):
            raise ValueError("Les poids cibles doivent être positifs")
        if not 0 <= self.reserve_pct < 1:
            raise ValueError("`reserve_pct` doit être dans [0, 1[")
        if self.rebalance_band <= 0:
            raise ValueError("`rebalance_band` doit être > 0")
        for t in self.reserve_tiers:
            if not 0 < t.drawdown < 1 or not 0 <= t.reserve_pct <= self.reserve_pct:
                raise ValueError(f"Palier de réserve invalide : {t}")
        self.reserve_tiers.sort(key=lambda t: t.drawdown)
        if self.mode not in ("timing", "plan"):
            raise ValueError("`mode` doit valoir 'timing' ou 'plan'")
        self.alertes_krach.sort(key=lambda a: a["drawdown"])
        if self.radar:
            self.radar = {**RADAR_DEFAUTS, **self.radar}

    @property
    def tickers(self) -> list[str]:
        out = list(self.targets)
        for extra in (self.benchmark, self.defensive_asset):
            if extra and extra not in out:
                out.append(extra)
        return out


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    tiers = [ReserveTier(**t) for t in raw.pop("reserve_tiers", []) or []]
    radar = raw.get("radar") or {}
    fichiers = radar.get("fichiers") or ([radar["fichier"]] if radar.get("fichier") else [])
    if fichiers:
        liste: dict = {}
        for nom in fichiers:  # les premiers fichiers sont prioritaires (ISIN, noms vérifiés)
            chemin = Path(path).parent / nom
            if chemin.exists():
                for t, info in (yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}).items():
                    liste.setdefault(t, info)
        radar["liste"] = {**liste, **(radar.get("liste") or {})}
    cfg = Config(reserve_tiers=tiers, **raw)
    cfg.validate()
    return cfg
