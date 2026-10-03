"""Backtest mensuel sans biais d'anticipation.

Décision prise avec les données connues à la clôture du jour J, exécution à la
clôture du jour de bourse suivant.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

from .config import Config
from .strategy import decide


@dataclass
class Result:
    name: str
    equity: pd.Series  # valeur du portefeuille
    invested: float
    twr_index: pd.Series  # performance hors apports (base 1)
    trades: int

    @property
    def final(self) -> float:
        return float(self.equity.iloc[-1])

    @property
    def cagr(self) -> float:
        years = (self.twr_index.index[-1] - self.twr_index.index[0]).days / 365.25
        return float(self.twr_index.iloc[-1] ** (1 / years) - 1) if years > 0 else 0.0

    @property
    def max_drawdown(self) -> float:
        idx = self.twr_index
        return float((1 - idx / idx.cummax()).max())

    def summary(self) -> str:
        return (
            f"{self.name:<28} final {self.final:>12,.0f} | investi {self.invested:>10,.0f} | "
            f"CAGR {self.cagr:6.2%} | pire baisse {self.max_drawdown:6.1%} | ordres {self.trades}"
        )


def run_backtest(
    cfg: Config,
    prices: pd.DataFrame,
    initial_cash: float,
    start: str | None = None,
    name: str = "Bot",
) -> Result:
    prices = prices.ffill()
    warmup = max(cfg.trend_window_days, cfg.drawdown_window_days)
    first = prices.index[warmup] if start is None else max(pd.Timestamp(start), prices.index[warmup])
    days = prices.index[prices.index >= first]
    month_starts = set(pd.Series(days, index=days).groupby([days.year, days.month]).first())

    cash, positions = float(initial_cash), {}
    invested, trades = float(initial_cash), 0
    pending = None  # ordres décidés la veille
    equity, twr = [], []
    unit_value, units = 1.0, None

    for i, d in enumerate(days):
        px = prices.loc[d]
        flow = 0.0
        if pending is not None:
            for o in pending:  # exécution au cours du jour
                p = float(px[o.ticker])
                fee_rate = cfg.fee_bps / 1e4
                if o.side == "buy":
                    qty = min(o.quantity, max(0.0, cash / (p * (1 + fee_rate))))
                    cash -= qty * p * (1 + fee_rate)
                    positions[o.ticker] = positions.get(o.ticker, 0.0) + qty
                else:
                    qty = min(o.quantity, positions.get(o.ticker, 0.0))
                    cash += qty * p * (1 - fee_rate)
                    positions[o.ticker] -= qty
                trades += 1
            pending = None

        if d in month_starts and i > 0 and cfg.monthly_contribution:
            cash += cfg.monthly_contribution
            invested += cfg.monthly_contribution
            flow = cfg.monthly_contribution

        value = cash + sum(q * float(px[t]) for t, q in positions.items())
        # Indice "time-weighted" : neutralise les apports.
        if units is None:
            units = value / unit_value
        else:
            units += flow / unit_value
            unit_value = value / units if units else unit_value
        equity.append(value)
        twr.append(unit_value)

        if d in month_starts and i + 1 < len(days):
            hist = prices.loc[:d]
            pending = decide(cfg, hist, positions, cash, enforce_limits=False).orders

    return Result(name, pd.Series(equity, index=days), invested, pd.Series(twr, index=days), trades)


def compare(cfg: Config, prices: pd.DataFrame, initial_cash: float, start: str | None = None) -> list[Result]:
    """Bot configuré vs. variantes de référence (DCA simple, avec/sans filtre de tendance)."""
    big_band = 10.0  # jamais de vente
    variants = [
        ("DCA simple (achat-conservation)", replace(cfg, reserve_pct=0.0, reserve_tiers=[], trend_filter=False, rebalance_band=big_band)),
        ("Rééquilibrage seul", replace(cfg, reserve_pct=0.0, reserve_tiers=[], trend_filter=False)),
        ("Bot (config)", cfg),
        ("Bot + filtre tendance" if not cfg.trend_filter else "Bot sans filtre tendance",
         replace(cfg, trend_filter=not cfg.trend_filter)),
    ]
    return [run_backtest(c, prices, initial_cash, start, name) for name, c in variants]
