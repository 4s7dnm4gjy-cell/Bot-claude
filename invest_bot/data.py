"""Récupération des cours (Yahoo Finance via yfinance), avec cache CSV local."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("data_cache")


def fetch_prices(tickers: list[str], start: str = "2000-01-01", use_cache: bool = True) -> pd.DataFrame:
    """Clôtures ajustées (dividendes réinvestis), une colonne par ticker."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache = CACHE_DIR / f"{'_'.join(sorted(tickers))}_{start}.csv"
    if use_cache and cache.exists():
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        if not df.empty and df.index[-1].date() >= date.today() - timedelta(days=1):
            return df

    import yfinance as yf  # import tardif : inutile pour les tests

    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False)
    if raw.empty:
        raise RuntimeError(f"Aucune donnée reçue pour {tickers}")
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    if not isinstance(raw.columns, pd.MultiIndex):
        closes.columns = tickers
    missing = [t for t in tickers if t not in closes or closes[t].dropna().empty]
    if missing:
        raise RuntimeError(f"Tickers sans données : {missing}")
    closes = closes[tickers].dropna(how="all")
    closes.to_csv(cache)
    return closes
