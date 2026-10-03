"""Point d'entrée : python -m invest_bot <commande>.

  backtest  Simule la stratégie sur l'historique et la compare aux références.
  plan      Calcule les ordres du jour sans rien exécuter.
  run       Calcule ET exécute les ordres (papier par défaut, --live pour le réel).
  deposit   Ajoute du cash au portefeuille papier local.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .backtest import compare
from .brokers import AlpacaBroker, Broker, PaperBroker
from .config import Config, load_config
from .data import fetch_prices
from .strategy import Decision, decide

JOURNAL = Path("journal/decisions.jsonl")
LAST_RUN = Path("state/last_run.json")


def make_broker(name: str, cfg: Config, live: bool) -> Broker:
    if name == "paper":
        if live:
            sys.exit("--live n'a pas de sens avec le broker papier local")
        return PaperBroker(fee_bps=cfg.fee_bps, fee_fixed=cfg.fee_fixed)
    if name == "alpaca":
        return AlpacaBroker(live=live)
    sys.exit(f"Broker inconnu : {name}")


def print_decision(d: Decision, positions: dict[str, float], cash: float) -> None:
    print(f"\nValeur totale : {d.total_value:,.2f} | cash : {cash:,.2f}")
    print("Positions :", {t: round(q, 4) for t, q in positions.items()} or "aucune")
    for n in d.notes:
        print("  •", n)
    if not d.orders:
        print("\nAucun ordre : rien à faire, on laisse travailler le temps.")
        return
    print("\nOrdres :")
    for o in d.orders:
        print(f"  {o.side.upper():4} {o.quantity:>10.4f} {o.ticker:<8} ~{o.value:>11,.2f}  ({o.reason})")


def journal(entry: dict) -> None:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def cmd_backtest(args, cfg: Config) -> None:
    if args.csv:
        prices = pd.read_csv(args.csv, index_col=0, parse_dates=True)[cfg.tickers]
    else:
        prices = fetch_prices(cfg.tickers, start=args.data_start)
    print(f"Données : {prices.index[0].date()} -> {prices.index[-1].date()} ({', '.join(cfg.tickers)})")
    print(f"Capital initial {args.initial:,.0f} + {cfg.monthly_contribution:,.0f}/mois\n")
    results = compare(cfg, prices, args.initial, args.start)
    for r in results:
        print(r.summary())
    print("\nCAGR = rendement annuel hors apports. Les performances passées ne garantissent pas "
          "les performances futures.")
    if not args.rapport:
        return

    from . import rapport
    from .score import moment_score, score_stats

    out = Path(args.rapport)
    rapport.chart_backtest(results, out.parent / "backtest.png")
    bench = prices[cfg.benchmark]
    stats_b = score_stats(bench, moment_score(bench)["score"])
    parts = [
        "# Backtest sur données réelles",
        f"Période : {results[0].equity.index[0]:%d/%m/%Y} → {results[0].equity.index[-1]:%d/%m/%Y}. "
        f"Actifs : {', '.join(cfg.noms.get(t, t) for t in cfg.targets)}. "
        f"Versement initial {args.initial:,.0f} € puis {cfg.monthly_contribution:,.0f} € par mois. "
        f"Frais Trade Republic : {cfg.fee_fixed:.0f} € par ordre (le plan d'épargne est gratuit).".replace(",", " "),
        rapport.backtest_table(results),
        "![Backtest](backtest.png)",
        "*Rendement annuel* : performance hors apports (pondérée dans le temps). *Pire baisse* : plus forte "
        "chute du portefeuille entre un plus haut et un plus bas.",
    ]
    if args.stats_ticker:
        long = fetch_prices([cfg.stats_ticker], start="1950-01-01")[cfg.stats_ticker]
        stats_l = score_stats(long, moment_score(long)["score"])
        parts += [f"## Le score sur {cfg.stats_ticker} depuis {long.dropna().index[0].year}", rapport.stats_table(stats_l)]
        print(f"\nScore sur {cfg.stats_ticker} :\n{stats_l.round(3).to_string()}")
    parts += [f"## Le score sur {cfg.noms.get(cfg.benchmark, cfg.benchmark)}", rapport.stats_table(stats_b),
              "Les performances passées ne préjugent pas des performances futures."]
    print(f"\nScore sur {cfg.benchmark} :\n{stats_b.round(3).to_string()}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


def cmd_conseil(args, cfg: Config) -> None:
    from .conseil import lancer_conseil

    prices = fetch_prices(cfg.tickers, start=args.data_start, use_cache=False)
    stats = fetch_prices([cfg.stats_ticker], start="1950-01-01", use_cache=False)[cfg.stats_ticker]
    radar = None
    if cfg.radar and cfg.radar["liste"]:
        radar = fetch_prices(list(cfg.radar["liste"]), start=args.data_start, use_cache=False, strict=False)
    prop = lancer_conseil(cfg, prices, stats, prix_radar=radar)
    print(f"Proposition : {prop['type']} ({len(prop['ordres'])} ordres)" if prop else "Rien à proposer aujourd'hui.")


def cmd_plan_or_run(args, cfg: Config, execute: bool) -> None:
    broker = make_broker(args.broker, cfg, args.live)
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    if execute and not args.force and LAST_RUN.exists():
        if json.loads(LAST_RUN.read_text()).get(f"{args.broker}:{args.live}") == month:
            print(f"Déjà exécuté ce mois-ci ({month}). Utilisez --force pour relancer.")
            return

    prices = fetch_prices(cfg.tickers, start=args.data_start, use_cache=False)
    positions, cash = broker.get_positions(), broker.get_cash()
    decision = decide(cfg, prices, positions, cash)
    print_decision(decision, positions, cash)

    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "broker": args.broker,
        "live": args.live,
        "executed": False,
        "total_value": decision.total_value,
        "drawdown": decision.drawdown,
        "notes": decision.notes,
        "orders": [o.__dict__ for o in decision.orders],
    }
    if not execute or not decision.orders:
        journal(entry)
        return

    if not broker.is_market_open():
        print("\nMarché fermé : aucun ordre envoyé. Relancez pendant les heures d'ouverture.")
        journal({**entry, "notes": entry["notes"] + ["marché fermé"]})
        return

    if args.live:
        if os.environ.get("INVEST_BOT_ALLOW_LIVE") != "1":
            sys.exit("Mode réel refusé : définissez INVEST_BOT_ALLOW_LIVE=1 pour l'autoriser.")
        if not args.yes and input("\nARGENT RÉEL. Tapez 'OUI' pour exécuter : ").strip() != "OUI":
            print("Annulé.")
            return

    ids = []
    # Ventes d'abord pour libérer le cash.
    for o in sorted(decision.orders, key=lambda o: o.side != "sell"):
        ids.append(broker.submit(o))
        print(f"  envoyé : {o.side} {o.quantity:.4f} {o.ticker}")
    journal({**entry, "executed": True, "order_ids": ids})

    LAST_RUN.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(LAST_RUN.read_text()) if LAST_RUN.exists() else {}
    state[f"{args.broker}:{args.live}"] = month
    LAST_RUN.write_text(json.dumps(state, indent=2))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="invest_bot", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--data-start", default="2000-01-01", help="début de l'historique téléchargé")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backtest")
    b.add_argument("--initial", type=float, default=1_000)
    b.add_argument("--start", default=None, help="date de début de la simulation")
    b.add_argument("--csv", default=None, help="cours depuis un CSV (date + une colonne par ticker)")

    for name in ("plan", "run"):
        s = sub.add_parser(name)
        s.add_argument("--broker", choices=["paper", "alpaca"], default="paper")
        s.add_argument("--live", action="store_true", help="argent réel (Alpaca uniquement)")
        if name == "run":
            s.add_argument("--yes", action="store_true", help="pas de confirmation interactive")
            s.add_argument("--force", action="store_true", help="ignorer la limite d'un passage par mois")

    b.add_argument("--rapport", default=None, help="écrire un rapport Markdown + graphique (ex. rapports/backtest.md)")
    b.add_argument("--stats-ticker", action="store_true", help="ajouter les statistiques du score sur le long historique")

    sub.add_parser("conseil", help="analyse du jour + proposition éventuelle (Trade Republic)")
    sub.add_parser("publier", help="publie la proposition préparée en ticket GitHub")
    c = sub.add_parser("commentaire", help="traite une réponse (oui/non/…) laissée sur un ticket")
    c.add_argument("--ticket", type=int, required=True)

    d = sub.add_parser("deposit")
    d.add_argument("amount", type=float)

    args = p.parse_args(argv)
    cfg = load_config(args.config)

    if args.cmd == "backtest":
        cmd_backtest(args, cfg)
    elif args.cmd == "conseil":
        cmd_conseil(args, cfg)
    elif args.cmd == "publier":
        from .conseil import publier

        numero = publier(cfg)
        print(f"Ticket #{numero} créé" if numero else "Rien à publier.")
    elif args.cmd == "commentaire":
        from .conseil import traiter_commentaire

        reponse = traiter_commentaire(cfg, args.ticket, os.environ.get("COMMENTAIRE", ""))
        print(reponse or "Commentaire ignoré (pas une commande).")
    elif args.cmd == "deposit":
        broker = PaperBroker(fee_bps=cfg.fee_bps, fee_fixed=cfg.fee_fixed)
        broker.deposit(args.amount)
        print(f"Cash papier : {broker.get_cash():,.2f}")
    else:
        args.yes = getattr(args, "yes", False)
        args.force = getattr(args, "force", False)
        cmd_plan_or_run(args, cfg, execute=args.cmd == "run")


if __name__ == "__main__":
    main()
