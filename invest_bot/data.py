"""Récupération des cours (Yahoo Finance via yfinance), avec cache CSV local."""

from __future__ import annotations

import hashlib
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("data_cache")


def fetch_prices(tickers: list[str], start: str = "2000-01-01", use_cache: bool = True, strict: bool = True,
                 incremental: bool = False) -> pd.DataFrame:
    """Clôtures ajustées (dividendes réinvestis), une colonne par ticker.

    `incremental` : reprend le cache existant et ne télécharge que les derniers
    jours (le cache est vidé chaque mois par le workflow, ce qui réintègre les
    ajustements de dividendes).
    """
    CACHE_DIR.mkdir(exist_ok=True)
    cle = hashlib.sha1(f"{'_'.join(sorted(tickers))}_{start}".encode()).hexdigest()[:16]
    cache = CACHE_DIR / f"cours_{cle}.csv"  # empreinte : le nom reste court même avec 2 000 titres
    if use_cache and cache.exists():
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        if not df.empty and df.index[-1].date() >= date.today() - timedelta(days=1):
            return df
    if incremental:  # fichier fixe : la liste de titres peut changer d'un jour à l'autre
        cache = CACHE_DIR / f"incremental_{start}.csv"
    if incremental and cache.exists():
        ancien = pd.read_csv(cache, index_col=0, parse_dates=True)
        connus = [t for t in tickers if t in ancien and ancien[t].notna().any()]
        nouveaux = [t for t in tickers if t not in connus]
        debut = (ancien.index[-1] - timedelta(days=10)).date().isoformat()
        recent = _telecharger(connus, debut, strict=False) if connus else pd.DataFrame()
        complet = _telecharger(nouveaux, start, strict) if nouveaux else pd.DataFrame()
        df = recent.combine_first(ancien[connus]) if not recent.empty else ancien[connus]
        if not complet.empty:
            df = df.join(complet, how="outer")
        df = df.sort_index().dropna(how="all")
        df.to_csv(cache)
        print(f"Cours : {len(connus)} titres mis à jour depuis le cache, {len(nouveaux)} téléchargés en entier")
        return df
    closes = _telecharger(tickers, start, strict)
    closes.to_csv(cache)
    return closes


def _telecharger(tickers: list[str], start: str, strict: bool) -> pd.DataFrame:

    import yfinance as yf  # import tardif : inutile pour les tests

    t0 = time.time()
    series = {}
    paquet = 100  # téléchargement par lots : ~10 fois plus rapide qu'un par un
    for i in range(0, len(tickers), paquet):
        lot = tickers[i:i + paquet]
        try:
            # Parallèle au sein du lot (rapide) ; les titres en échec sont repris un par un plus bas.
            raw = yf.download(lot, start=start, auto_adjust=True, progress=False, threads=8)
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
    print(f"  {len(series)}/{len(tickers)} titres téléchargés en {time.time() - t0:.0f} s", flush=True)
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
    return pd.DataFrame(series).dropna(how="all")
