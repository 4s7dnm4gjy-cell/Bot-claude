"""Backtest quotidien sans biais d'anticipation.

Chaque jour, le bot décide avec les seules données connues à la clôture ;
les ordres sont exécutés à la clôture du jour de bourse suivant (comme vous,
qui validez la proposition le lendemain dans l'application).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

from .config import Config
from .score import moment_score
from .strategy import decide, reserve_target_pct


@dataclass
class Result:
    name: str
    equity: pd.Series  # valeur du portefeuille
    invested: float
    twr_index: pd.Series  # performance hors apports (base 1)
    trades: int
    fees: float
    invested_curve: pd.Series  # cumul de l'argent versé

    @property
    def final(self) -> float:
        return float(self.equity.iloc[-1])

    @property
    def gain(self) -> float:
        return self.final - self.invested

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
            f"{self.name:<34} final {self.final:>11,.0f} | investi {self.invested:>9,.0f} | "
            f"gain {self.gain:>10,.0f} | CAGR {self.cagr:6.2%} | pire baisse {self.max_drawdown:6.1%} | "
            f"ordres {self.trades} | frais {self.fees:,.0f}"
        )


def first_tradable_day(cfg: Config, prices: pd.DataFrame) -> pd.Timestamp:
    """Premier jour où tous les actifs ont assez d'historique pour les signaux."""
    starts = [prices[t].first_valid_index() for t in cfg.tickers]
    begin = max(starts)
    warmup = max(cfg.trend_window_days, cfg.drawdown_window_days)
    days = prices.index[prices.index >= begin]
    return days[min(warmup, len(days) - 1)]


def run_backtest(
    cfg: Config,
    prices: pd.DataFrame,
    initial_cash: float,
    start: str | None = None,
    name: str = "Bot",
    timing: str = "meilleur_moment",  # ou "debut_mois"
    scores: pd.Series | None = None,
) -> Result:
    prices = prices[cfg.tickers].ffill()
    if scores is None:
        scores = moment_score(prices[cfg.benchmark])["score"]
    first = first_tradable_day(cfg, prices)
    if start is not None:
        first = max(first, pd.Timestamp(start))
    days = prices.index[prices.index >= first]

    cash, waiting, positions = 0.0, float(initial_cash), {}
    invested, trades, fees = float(initial_cash), 0, 0.0
    pending = None
    applied_reserve = None
    month = None
    equity, twr, inv_curve = [], [], []
    unit_value, units = 1.0, None
    fee_rate = cfg.fee_bps / 1e4

    for i, d in enumerate(days):
        px = prices.loc[d]
        flow = 0.0
        if pending is not None:
            for o in pending:
                p = float(px[o.ticker])
                if o.side == "buy":
                    qty = min(o.quantity, max(0.0, (cash - cfg.fee_fixed) / (p * (1 + fee_rate))))
                    if qty <= 0:
                        continue
                    fee = qty * p * fee_rate + cfg.fee_fixed
                    cash -= qty * p + fee
                    positions[o.ticker] = positions.get(o.ticker, 0.0) + qty
                else:
                    qty = min(o.quantity, positions.get(o.ticker, 0.0))
                    fee = qty * p * fee_rate + cfg.fee_fixed
                    cash += qty * p - fee
                    positions[o.ticker] -= qty
                trades += 1
                fees += fee
            pending = None

        new_month = (d.year, d.month) != month
        if new_month:
            month = (d.year, d.month)
            if i > 0 and cfg.monthly_contribution:
                waiting += cfg.monthly_contribution
                invested += cfg.monthly_contribution
                flow = cfg.monthly_contribution

        value = cash + waiting + sum(q * float(px[t]) for t, q in positions.items())
        if units is None:
            units = value / unit_value
        else:
            units += flow / unit_value
            unit_value = value / units if units else unit_value
        equity.append(value)
        inv_curve.append(invested)
        twr.append(unit_value)

        if i + 1 >= len(days):
            continue
        sc = scores.get(d, float("nan"))
        if timing == "debut_mois":
            release = waiting > 0 and new_month
        else:
            release = waiting > 0 and (sc >= cfg.score_seuil or d.day >= cfg.jour_limite or i == 0)

        hist = prices.loc[:d]
        if release:
            cash += waiting
            waiting = 0.0
            dec = decide(cfg, hist, positions, cash, enforce_limits=False)
        else:
            # Hors apport : on ne bouge que sur un vrai signal (palier de krach, bande dépassée).
            dec = decide(cfg, hist, positions, cash, enforce_limits=False)
            pct = reserve_target_pct(cfg, dec.drawdown)
            has_sell = any(o.side == "sell" for o in dec.orders)
            if not has_sell and (pct == applied_reserve or not positions):
                continue
        applied_reserve = reserve_target_pct(cfg, dec.drawdown)
        pending = dec.orders or None

    return Result(
        name, pd.Series(equity, index=days), invested, pd.Series(twr, index=days), trades, fees,
        pd.Series(inv_curve, index=days),
    )


def compare(cfg: Config, prices: pd.DataFrame, initial_cash: float, start: str | None = None) -> list[Result]:
    """Le bot face aux alternatives simples, avec les mêmes apports."""
    scores = moment_score(prices[cfg.benchmark])["score"]
    never_sell = 10.0
    simple = replace(cfg, reserve_pct=0.0, reserve_tiers=[], trend_filter=False, rebalance_band=never_sell)
    if cfg.mode == "plan":
        # Le plan achète des fractions sans frais ; le rééquilibrage, lui, coûte ~1 € par ordre.
        plan = replace(simple, fee_fixed=0.0, fractional=True)
        variants = [
            ("Plan d'épargne seul (gratuit)", plan, "debut_mois"),
            (f"Plan + rééquilibrage ({cfg.rebalance_band:.0%} de bande)",
             replace(plan, rebalance_band=cfg.rebalance_band), "debut_mois"),
            ("Pour comparaison : achat au meilleur moment", simple, "meilleur_moment"),
        ]
        return [run_backtest(c, prices, initial_cash, start, n, timing, scores) for n, c, timing in variants]
    variants = [
        ("Plan d'épargne le 1er (gratuit)", replace(simple, fee_fixed=0.0), "debut_mois"),
        ("Achat au meilleur moment du mois", simple, "meilleur_moment"),
        ("Bot complet", cfg, "meilleur_moment"),
        (
            "Bot complet + filtre tendance" if not cfg.trend_filter else "Bot sans filtre tendance",
            replace(cfg, trend_filter=not cfg.trend_filter),
            "meilleur_moment",
        ),
    ]
    return [run_backtest(c, prices, initial_cash, start, n, timing, scores) for n, c, timing in variants]
