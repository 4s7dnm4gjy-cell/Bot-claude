"""Graphiques (PNG) et tableaux Markdown pour les propositions et le backtest."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

# Palette catégorielle validée (ordre fixe) + encres de texte.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9)


def chart_market(feats: pd.DataFrame, name: str, seuil: float, buys: list[dict], path: Path, years: int = 3) -> None:
    f = feats.loc[feats.index >= feats.index[-1] - pd.DateOffset(years=years)]
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 6.2), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]}, facecolor=SURFACE
    )
    _style(ax1)
    _style(ax2)
    ax1.plot(f.index, f["prix"], color=SERIES[0], linewidth=2, label=name)
    ax1.plot(f.index, f["sma200"], color=SERIES[1], linewidth=2, label="Moyenne 200 jours")
    pts = [(pd.Timestamp(b["date"]), b["prix"]) for b in buys if pd.Timestamp(b["date"]) >= f.index[0]]
    if pts:
        ax1.scatter(*zip(*pts), s=64, color=SERIES[2], edgecolor=SURFACE, linewidth=2, zorder=3, label="Vos achats")
    ax1.set_title(f"{name} — prix et score du moment d'achat", loc="left", color=INK, fontsize=12)
    ax1.legend(frameon=False, fontsize=9, labelcolor=INK_2, loc="upper left")

    ax2.plot(f.index, f["score"], color=SERIES[0], linewidth=2)
    ax2.axhline(seuil, color=INK_2, linewidth=1, linestyle="--")
    ax2.text(f.index[0], seuil + 3, f"seuil d'achat {seuil:.0f}", color=INK_2, fontsize=8)
    last = f["score"].dropna()
    if not last.empty:
        ax2.scatter([last.index[-1]], [last.iloc[-1]], s=64, color=SERIES[0], edgecolor=SURFACE, linewidth=2, zorder=3)
        ax2.annotate(f"{last.iloc[-1]:.0f}", (last.index[-1], last.iloc[-1]), xytext=(6, 0),
                     textcoords="offset points", color=INK, fontsize=10, va="center")
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("Score (0-100)", color=INK_2, fontsize=9)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def chart_backtest(results, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5), facecolor=SURFACE)
    _style(ax)
    for r, color in zip(results, SERIES):
        ax.plot(r.equity.index, r.equity.values, color=color, linewidth=2, label=r.name)
    inv = results[0].invested_curve
    ax.plot(inv.index, inv.values, color=INK_2, linewidth=1.5, linestyle="--", label="Argent versé")
    ax.set_title("Valeur du portefeuille selon la méthode (mêmes apports)", loc="left", color=INK, fontsize=12)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f} €".replace(",", " ")))
    ax.legend(frameon=False, fontsize=9, labelcolor=INK_2, loc="upper left")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def pct(x: float, signed: bool = True) -> str:
    if pd.isna(x):
        return "—"
    return f"{x:+.1%}" if signed else f"{x:.0%}"


def stats_table(stats: pd.DataFrame, highlight: str | None = None) -> str:
    lines = [
        "| Score | Jours | Rendement moyen à 3 mois | à 12 mois | Positif à 12 mois | Pire cas à 12 mois |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for tranche, r in stats.iterrows():
        name = f"**{tranche} ← aujourd'hui**" if tranche == highlight else tranche
        lines.append(
            f"| {name} | {int(r['n_12m']):,} | {pct(r['moy_3m'])} | {pct(r['moy_12m'])} | "
            f"{pct(r['pos_12m'], False)} | {pct(r['pire_12m'])} |".replace(",", " ")
        )
    return "\n".join(lines)


def backtest_table(results) -> str:
    lines = [
        "| Méthode | Valeur finale | Argent versé | Gain | Rendement annuel | Pire baisse | Ordres | Frais |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r.name} | {r.final:,.0f} € | {r.invested:,.0f} € | {r.gain:+,.0f} € | {r.cagr:.2%} | "
            f"-{r.max_drawdown:.1%} | {r.trades} | {r.fees:,.0f} € |".replace(",", " ")
        )
    return "\n".join(lines)
