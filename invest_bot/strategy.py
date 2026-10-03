"""Logique de décision pure : historique de prix + portefeuille -> ordres.

Aucune dépendance au broker ni au réseau : tout est testable et rejouable.

Principes (sans émotion, sans prédiction) :
  * Acheter : chaque apport va d'abord aux actifs sous-pondérés (on achète ce qui a
    baissé). Une réserve de cash est gardée en marché haut et déployée par paliers
    quand l'indice de référence chute (ex. -15 %, -25 %, -35 %).
  * Vendre : uniquement quand un actif dépasse sa cible de plus de `rebalance_band`
    (on vend ce qui a monté), ou — si activé — quand il passe sous sa moyenne
    mobile longue (filtre de tendance, protège des grands krachs).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from .config import Config


@dataclass
class Order:
    ticker: str
    side: str  # "buy" | "sell"
    quantity: float
    price: float
    reason: str

    @property
    def value(self) -> float:
        return self.quantity * self.price


@dataclass
class Decision:
    orders: list[Order]
    total_value: float
    drawdown: float
    reserve_target: float
    effective_targets: dict[str, float]
    downtrend: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def drawdown(series: pd.Series, window: int) -> float:
    """Baisse du dernier cours par rapport au plus haut sur `window` séances (>= 0)."""
    s = series.dropna().iloc[-window:]
    if s.empty:
        return 0.0
    peak = s.max()
    return float(max(0.0, 1 - s.iloc[-1] / peak)) if peak > 0 else 0.0


def in_downtrend(series: pd.Series, window: int) -> bool:
    s = series.dropna()
    if len(s) < window:
        return False  # historique insuffisant : on ne vend pas sur un signal incomplet
    return bool(s.iloc[-1] < s.iloc[-window:].mean())


def reserve_target_pct(cfg: Config, dd: float) -> float:
    pct = cfg.reserve_pct
    for tier in cfg.reserve_tiers:  # triés par drawdown croissant
        if dd >= tier.drawdown:
            pct = tier.reserve_pct
    return pct


def _round_qty(qty: float, fractional: bool) -> float:
    if fractional:
        return math.floor(qty * 1e4) / 1e4
    return float(math.floor(qty))


def decide(
    cfg: Config,
    history: pd.DataFrame,
    positions: dict[str, float],
    cash: float,
    enforce_limits: bool = True,
) -> Decision:
    """Calcule les ordres à passer.

    `history` : cours de clôture (index = dates, colonnes = tickers), uniquement
    les données connues au moment de la décision.
    """
    prices = history.ffill().iloc[-1]
    for t, qty in positions.items():
        if qty and (t not in prices or pd.isna(prices[t])):
            raise ValueError(f"Pas de prix pour la position {t}")

    holdings = {t: q * float(prices[t]) for t, q in positions.items() if q}
    total = cash + sum(holdings.values())
    notes: list[str] = []

    dd = drawdown(history[cfg.benchmark], cfg.drawdown_window_days)
    reserve_pct = reserve_target_pct(cfg, dd)
    reserve_target = reserve_pct * total
    notes.append(
        f"Drawdown {cfg.benchmark}: {dd:.1%} -> réserve cible {reserve_pct:.0%} ({reserve_target:,.0f})"
    )

    # Poids effectifs (filtre de tendance éventuel).
    targets = dict(cfg.targets)
    downtrend: list[str] = []
    if cfg.trend_filter:
        for t in list(targets):
            if t != cfg.defensive_asset and in_downtrend(history[t], cfg.trend_window_days):
                downtrend.append(t)
                w = targets.pop(t)
                if cfg.defensive_asset:
                    targets[cfg.defensive_asset] = targets.get(cfg.defensive_asset, 0.0) + w
                targets.setdefault(t, 0.0)
                if not cfg.defensive_asset:
                    reserve_target += w * total * (1 - reserve_pct)
        if downtrend:
            notes.append("Sous moyenne mobile (sortie) : " + ", ".join(downtrend))

    invest_scale = 1 - reserve_pct
    desired = {t: w * invest_scale * total for t, w in targets.items()}
    all_tickers = set(desired) | set(holdings)
    current = {t: holdings.get(t, 0.0) for t in all_tickers}

    orders: list[Order] = []

    # 1) Ventes : seulement hors bande (ou sortie de tendance / actif retiré de la cible).
    proceeds = 0.0
    for t in sorted(all_tickers):
        want = desired.get(t, 0.0)
        have = current[t]
        if have <= want or total <= 0:
            continue
        drift = (have - want) / total
        forced = t in downtrend or t not in cfg.targets and t != cfg.defensive_asset
        if forced or drift > cfg.rebalance_band:
            sell_value = have - want
            px = float(prices[t])
            qty = min(positions[t], _round_qty(sell_value / px, cfg.fractional))
            if want == 0:
                qty = positions[t]  # sortie complète
            if qty * px >= cfg.min_order_value:
                reason = (
                    "sortie tendance" if t in downtrend
                    else "hors cible" if t not in cfg.targets
                    else f"surpondéré de {drift:.1%} (> bande {cfg.rebalance_band:.0%})"
                )
                orders.append(Order(t, "sell", qty, px, reason))
                proceeds += qty * px * (1 - cfg.fee_bps / 1e4)
                current[t] -= qty * px

    # 2) Achats : cash disponible au-delà de la réserve, vers les actifs sous-pondérés.
    budget = cash + proceeds - reserve_target
    gaps = {t: desired[t] - current.get(t, 0.0) for t in desired if desired[t] > current.get(t, 0.0)}
    gap_total = sum(gaps.values())
    if budget > 0 and gap_total > 0:
        spend = min(budget, gap_total)
        for t, gap in sorted(gaps.items(), key=lambda kv: -kv[1]):
            px = float(prices[t])
            alloc = spend * gap / gap_total / (1 + cfg.fee_bps / 1e4)
            qty = _round_qty(alloc / px, cfg.fractional)
            if qty * px >= cfg.min_order_value:
                orders.append(Order(t, "buy", qty, px, f"sous-pondéré de {gap / total:.1%}"))
    elif budget <= 0:
        notes.append("Pas d'achat : cash entièrement affecté à la réserve")

    # 3) Garde-fous.
    turnover = sum(o.value for o in orders)
    if not enforce_limits:
        return Decision(orders, total, dd, reserve_target, targets, downtrend, notes)
    if total > 0 and turnover > cfg.max_turnover_pct * total and holdings:
        raise RuntimeError(
            f"Garde-fou : volume {turnover:,.0f} > {cfg.max_turnover_pct:.0%} du portefeuille. "
            "Vérifiez les données/la config avant de relancer."
        )
    if len(orders) > cfg.max_orders_per_run:
        raise RuntimeError(f"Garde-fou : {len(orders)} ordres > max {cfg.max_orders_per_run}")

    return Decision(orders, total, dd, reserve_target, targets, downtrend, notes)
