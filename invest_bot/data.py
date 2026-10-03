"""Récupération des cours (Yahoo Finance via yfinance), avec cache CSV local."""

from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("data_cache")


def fetch_prices(tickers: list[str], start: str = "2000-01-01", use_cache: bool = True, strict: bool = True) -> pd.DataFrame:
    """Clôtures ajustées (dividendes réinvestis), une colonne par ticker."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache = CACHE_DIR / f"{'_'.join(sorted(tickers))}_{start}.csv"
    if use_cache and cache.exists():
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        if not df.empty and df.index[-1].date() >= date.today() - timedelta(days=1):
            return df

    import yfinance as yf  # import tardif : inutile pour les tests

    series = {}
    for t in tickers:  # un par un : le téléchargement parallèle de yfinance verrouille son cache
        for essai in range(4):
            raw = yf.download(t, start=start, auto_adjust=True, progress=False, threads=False)
            if not raw.empty:
                break
            time.sleep(2 ** essai)
        if raw.empty:
            if not strict:
                print(f"Avertissement : pas de données pour {t}, ignoré")
                continue
            raise RuntimeError(f"Aucune donnée reçue pour {t}")
        close = raw["Close"]
        series[t] = close.iloc[:, 0] if isinstance(close, pd.DataFrame) else close
    closes = pd.DataFrame(series).dropna(how="all")
    closes.to_csv(cache)
    return closes
