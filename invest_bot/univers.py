"""Construction automatique de l'univers du radar à partir des grands indices.

Lit la composition d'une quinzaine d'indices mondiaux (Wikipédia), convertit
chaque titre au format Yahoo Finance, vérifie qu'il a bien des cours, et écrit
`radar_univers.yaml`. Relancé chaque mois par GitHub Actions : les entrées et
sorties d'indice sont suivies automatiquement.
"""

from __future__ import annotations

import re
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yaml

WIKI = "https://en.wikipedia.org/wiki/"

# nom de l'indice -> (page, suffixe Yahoo, transformation éventuelle du code)
INDICES = {
    "S&P 500": ("List_of_S%26P_500_companies", "", "us"),
    "Nasdaq-100": ("Nasdaq-100", "", "us"),
    "Dow Jones": ("Dow_Jones_Industrial_Average", "", "us"),
    "CAC 40": ("CAC_40", ".PA", None),
    "SBF 120": ("SBF_120", ".PA", None),
    "DAX": ("DAX", ".DE", None),
    "MDAX": ("MDAX", ".DE", None),
    "TecDAX": ("TecDAX", ".DE", None),
    "Euro Stoxx 50": ("EURO_STOXX_50", None, None),
    "FTSE 100": ("FTSE_100_Index", ".L", "uk"),
    "FTSE 250": ("FTSE_250_Index", ".L", "uk"),
    "SMI": ("Swiss_Market_Index", ".SW", None),
    "AEX": ("AEX_index", ".AS", None),
    "BEL 20": ("BEL_20", ".BR", None),
    "IBEX 35": ("IBEX_35", ".MC", None),
    "FTSE MIB": ("FTSE_MIB", ".MI", None),
    "OMX Stockholm 30": ("OMX_Stockholm_30", ".ST", "nordique"),
    "OMX Copenhagen 25": ("OMX_Copenhagen_25", ".CO", "nordique"),
    "OMX Helsinki 25": ("OMX_Helsinki_25", ".HE", "nordique"),
    "OBX": ("OBX_Index", ".OL", "nordique"),
    "ATX": ("Austrian_Traded_Index", ".VI", None),
    "PSI": ("PSI-20", ".LS", None),
    "ISEQ 20": ("ISEQ_20", ".IR", None),
    "Nikkei 225": ("Nikkei_225", ".T", "japon"),
    "Hang Seng": ("Hang_Seng_Index", ".HK", "hk"),
    "S&P/TSX 60": ("S%26P/TSX_60", ".TO", "us"),
    "S&P/ASX 50": ("S%26P/ASX_50", ".AX", None),
}

COLS_CODE = ("symbol", "ticker", "ticker symbol", "code", "epic", "stock symbol", "ticker code", "sehk",
             "trading symbol", "stock code", "securities code")
COLS_NOM = ("security", "company", "name", "constituent", "company name", "corporation", "issuer", "firm")

# Dans le texte de la page : « Toyota Motor (TYO: 7203) », « Apple Inc. (Nasdaq: AAPL) ».
MOTIF_TEXTE = re.compile(r"([A-Z][^()\n]{1,60}?)\s*\((?:TYO|TSE|NASDAQ|Nasdaq|NYSE)\s*:\s*([A-Z0-9.]{1,6})\)")

# Bourse indiquée dans les tableaux multi-pays (Euro Stoxx 50) -> suffixe Yahoo.
BOURSES = {
    "euronext paris": ".PA", "paris": ".PA", "xetra": ".DE", "frankfurt": ".DE", "deutsche börse": ".DE",
    "euronext amsterdam": ".AS", "amsterdam": ".AS", "euronext brussels": ".BR", "brussels": ".BR",
    "borsa italiana": ".MI", "milan": ".MI", "bolsa de madrid": ".MC", "madrid": ".MC",
    "euronext dublin": ".IR", "helsinki": ".HE", "nasdaq helsinki": ".HE", "euronext lisbon": ".LS",
}


def _colonne(df: pd.DataFrame, noms: tuple[str, ...]) -> str | None:
    for c in df.columns:
        lc = str(c).strip().lower()
        if lc in noms or any(lc.startswith(n) for n in noms):
            return c
    return None


def convertir(code: str, suffixe: str, regle: str | None) -> str | None:
    """Code d'un tableau Wikipédia -> ticker Yahoo."""
    code = re.sub(r"\[.*?\]", "", str(code)).strip()
    code = re.sub(r"^[A-Za-z][A-Za-z .]{0,15}:\s*", "", code).strip()  # « NYSE: KO », « OSE: DNB »…
    if not code or code.lower() == "nan" or len(code) > 15:
        return None
    if regle == "us":
        return code.replace(".", "-").upper() + suffixe
    if regle == "uk":
        code = code.rstrip(".").replace(".", "-")
        return code.upper() + suffixe
    if regle == "japon":
        chiffres = re.sub(r"\D", "", code)
        return f"{chiffres}{suffixe}" if len(chiffres) == 4 else None
    if regle == "hk":
        chiffres = re.sub(r"\D", "", code)
        return f"{int(chiffres):04d}{suffixe}" if chiffres else None
    if regle == "nordique":
        code = code.strip().replace(" ", "-")
    if suffixe and code.upper().endswith(suffixe.upper()):
        return code.upper()
    if "." in code and suffixe:
        code = code.split(".")[0]
    return code.upper() + (suffixe or "")


def lire_indice(nom: str, page: str, suffixe: str | None, regle: str | None) -> dict[str, dict]:
    html = requests.get(WIKI + page, timeout=30, headers={"User-Agent": "Mozilla/5.0 (bot-investissement)"}).text
    meilleur: dict[str, dict] = {}
    for df in pd.read_html(StringIO(html)):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [" ".join(str(x) for x in c if "Unnamed" not in str(x)).strip() for c in df.columns]
        c_code, c_nom = _colonne(df, COLS_CODE), _colonne(df, COLS_NOM)
        if c_code is None or c_nom is None or len(df) < 10:
            continue
        c_bourse = _colonne(df, ("exchange", "stock exchange", "listing", "main listing"))
        titres = {}
        for _, ligne in df.iterrows():
            suf = suffixe
            if suf is None:  # indice multi-pays : suffixe selon la bourse indiquée
                bourse = str(ligne.get(c_bourse, "")).lower() if c_bourse else ""
                suf = next((s for b, s in BOURSES.items() if b in bourse), None)
                if suf is None:
                    continue
            t = convertir(ligne[c_code], suf, regle)
            if t:
                titres[t] = {"nom": re.sub(r"\[.*?\]", "", str(ligne[c_nom])).strip(), "indice": nom}
        if len(titres) > len(meilleur):
            meilleur = titres
    if len(meilleur) < 10:  # pas de tableau exploitable : on cherche les codes dans le texte
        texte = re.sub(r"<[^>]+>", "", html)
        for nom_societe, code in MOTIF_TEXTE.findall(texte):
            t = convertir(code, suffixe or "", regle)
            if t:
                meilleur.setdefault(t, {"nom": nom_societe.strip(" ,;"), "indice": nom})
    if not meilleur:  # aide au diagnostic dans le journal
        tables = [list(map(str, df.columns))[:6] for df in pd.read_html(StringIO(html)) if len(df) >= 10]
        print(f"  {nom} : colonnes des tableaux trouvés : {tables[:4]}")
    return meilleur


def valider(tickers: list[str], paquet: int = 100) -> set[str]:
    """Garde les tickers qui ont des cours récents sur Yahoo."""
    import yfinance as yf

    ok = set()
    for i in range(0, len(tickers), paquet):
        lot = tickers[i:i + paquet]
        df = yf.download(lot, period="1mo", auto_adjust=True, progress=False, threads=False)
        if df.empty:
            continue
        close = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Close"]].set_axis(lot, axis=1)
        ok |= {t for t in close.columns if close[t].notna().sum() >= 5}
    return ok


def construire(sortie: str | Path = "radar_univers.yaml", deja: dict | None = None) -> dict[str, dict]:
    univers: dict[str, dict] = {}
    for nom, (page, suffixe, regle) in INDICES.items():
        try:
            titres = lire_indice(nom, page, suffixe, regle)
        except Exception as e:  # une page qui change de format ne doit pas tout bloquer
            print(f"{nom:<20} ÉCHEC : {type(e).__name__}: {e}")
            continue
        print(f"{nom:<20} {len(titres):>4} titres  ex. {list(titres)[:4]}")
        for t, info in titres.items():
            univers.setdefault(t, info)
    candidats = sorted(t for t in univers if t not in (deja or {}))
    valides = valider(candidats)
    rejetes = sorted(set(candidats) - valides)
    print(f"\nTotal : {len(univers)} titres lus, {len(valides)} validés sur Yahoo, {len(rejetes)} écartés.")
    if rejetes:
        print("Écartés :", ", ".join(rejetes[:80]), "…" if len(rejetes) > 80 else "")
    final = {t: univers[t] for t in sorted(valides)}
    entete = (
        "# Fichier généré automatiquement (python -m invest_bot univers) à partir des\n"
        "# compositions d'indices : ne pas modifier à la main, utilisez radar_liste.yaml.\n"
    )
    Path(sortie).write_text(entete + yaml.safe_dump(final, allow_unicode=True, sort_keys=True, width=200),
                            encoding="utf-8")
    return final
