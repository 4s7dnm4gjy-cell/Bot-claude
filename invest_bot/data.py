"""Récupération des cours (Yahoo Finance via yfinance), avec cache CSV local."""

from __future__ import annotations

import hashlib
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("data_cache")


def fetch_prices(tickers: list[str], start: str = "2000-01-01", use_cache: bool = True, strict: bool = True) -> pd.DataFrame:
    """Clôtures ajustées (dividendes réinvestis), une colonne par ticker."""
    CACHE_DIR.mkdir(exist_ok=True)
    cle = hashlib.sha1(f"{'_'.join(sorted(tickers))}_{start}".encode()).hexdigest()[:16]
    cache = CACHE_DIR / f"cours_{cle}.csv"  # empreinte : le nom reste court même avec 200 titres
    if use_cache and cache.exists():
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        if not df.empty and df.index[-1].date() >= date.today() - timedelta(days=1):
            return df

    import yfinance as yf  # import tardif : inutile pour les tests

    series = {}
    paquet = 100  # téléchargement par lots : ~10 fois plus rapide qu'un par un
    for i in range(0, len(tickers), paquet):
        lot = tickers[i:i + paquet]
        try:
            raw = yf.download(lot, start=start, auto_adjust=True, progress=False, threads=False)
        except Exception as e:
            print(f"Lot {i // paquet + 1} en échec ({type(e).__name__}), reprise titre par titre")
            raw = pd.DataFrame()
        if not raw.empty:
            close = raw["Close"]
            if not isinstance(close, pd.DataFrame):
                close = close.to_frame(lot[0])
            for t in lot:
                if t in close and close[t].notna().any():
                    series[t] = close[t]
    for t in [t for t in tickers if t not in series]:  # rattrapage un par un
        for essai in range(4 if strict else 2):
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
