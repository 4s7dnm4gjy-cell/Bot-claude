import numpy as np
import pandas as pd
import pytest

from invest_bot.backtest import compare, run_backtest
from invest_bot.brokers import PaperBroker
from invest_bot.config import Config, ReserveTier
from invest_bot.strategy import decide, drawdown, in_downtrend


def make_cfg(**kw) -> Config:
    base = dict(
        targets={"STK": 0.8, "BND": 0.2},
        benchmark="STK",
        monthly_contribution=500,
        reserve_pct=0.10,
        reserve_tiers=[ReserveTier(0.15, 0.05), ReserveTier(0.30, 0.0)],
        rebalance_band=0.05,
        drawdown_window_days=50,
        trend_window_days=50,
        min_order_value=10,
    )
    base.update(kw)
    cfg = Config(**base)
    cfg.validate()
    return cfg


def prices(stk: list[float], bnd: float = 100.0) -> pd.DataFrame:
    idx = pd.bdate_range("2020-01-01", periods=len(stk))
    return pd.DataFrame({"STK": stk, "BND": [bnd] * len(stk)}, index=idx)


def test_config_rejects_bad_weights():
    with pytest.raises(ValueError):
        make_cfg(targets={"STK": 0.5, "BND": 0.2})


def test_signals():
    s = pd.Series([100] * 40 + [80] * 10, dtype=float)
    assert drawdown(s, 50) == pytest.approx(0.20)
    assert in_downtrend(s, 50)
    assert not in_downtrend(s, 100)  # historique insuffisant -> pas de signal


def test_first_investment_keeps_reserve():
    cfg = make_cfg()
    d = decide(cfg, prices([100.0] * 60), {}, 10_000)
    spent = sum(o.value for o in d.orders if o.side == "buy")
    assert all(o.side == "buy" for o in d.orders)
    assert spent == pytest.approx(9_000, rel=0.01)  # 10 % gardés en réserve
    by = {o.ticker: o.value for o in d.orders}
    assert by["STK"] / spent == pytest.approx(0.8, rel=0.01)


def test_crash_deploys_reserve_without_selling():
    cfg = make_cfg()
    # Portefeuille investi + 10 % de cash, puis krach de 35 %.
    hist = prices([100.0] * 50 + [65.0] * 10)
    positions = {"STK": 72.0, "BND": 18.0}
    d = decide(cfg, hist, positions, cash=1_000)
    assert d.drawdown == pytest.approx(0.35)
    assert not any(o.side == "sell" for o in d.orders)  # jamais de vente panique
    assert any(o.side == "buy" and o.ticker == "STK" for o in d.orders)
    assert sum(o.value for o in d.orders) == pytest.approx(1_000, rel=0.01)


def test_rally_sells_overweight_only_beyond_band():
    cfg = make_cfg(reserve_pct=0.0, reserve_tiers=[])
    # STK a fortement monté : 90 % du portefeuille pour une cible de 80 %.
    d = decide(cfg, prices([100.0] * 60), {"STK": 90.0, "BND": 10.0}, cash=0)
    sells = [o for o in d.orders if o.side == "sell"]
    assert [o.ticker for o in sells] == ["STK"]
    assert sells[0].value == pytest.approx(1_000, rel=0.01)
    # Petit écart (83 %) : à l'intérieur de la bande, on ne touche à rien.
    d2 = decide(cfg, prices([100.0] * 60), {"STK": 83.0, "BND": 17.0}, cash=0)
    assert not d2.orders


def test_trend_filter_exits_to_defensive():
    cfg = make_cfg(
        targets={"STK": 0.8, "BND": 0.2}, defensive_asset="BND", trend_filter=True,
        reserve_pct=0.0, reserve_tiers=[],
    )
    hist = prices([100.0] * 50 + [90.0] * 5)
    d = decide(cfg, hist, {"STK": 80.0, "BND": 20.0}, cash=0, enforce_limits=False)
    assert d.downtrend == ["STK"]
    assert any(o.side == "sell" and o.ticker == "STK" for o in d.orders)
    assert any(o.side == "buy" and o.ticker == "BND" for o in d.orders)


def test_turnover_guard():
    cfg = make_cfg(reserve_pct=0.0, reserve_tiers=[], max_turnover_pct=0.05)
    with pytest.raises(RuntimeError):
        decide(cfg, prices([100.0] * 60), {"STK": 100.0}, cash=0)


def test_paper_broker_roundtrip(tmp_path):
    from invest_bot.strategy import Order

    b = PaperBroker(tmp_path / "s.json", initial_cash=1_000, fee_bps=0)
    b.submit(Order("STK", "buy", 5, 100, "t"))
    assert b.get_cash() == 500 and b.get_positions() == {"STK": 5}
    with pytest.raises(RuntimeError):
        b.submit(Order("STK", "buy", 10, 100, "t"))
    b.submit(Order("STK", "sell", 5, 120, "t"))
    assert b.get_cash() == 1_100 and b.get_positions() == {}
    assert PaperBroker(tmp_path / "s.json").get_cash() == 1_100  # persistance


def synthetic_market(seed: int = 0, years: int = 15) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 252 * years
    r = rng.normal(0.07 / 252, 0.18 / np.sqrt(252), n)
    r[800:900] -= 0.005   # krach (~ -40 %)
    r[2500:2560] -= 0.004
    idx = pd.bdate_range("2005-01-03", periods=n)
    stk = 100 * np.exp(np.cumsum(r))
    bnd = 100 * np.exp(np.cumsum(rng.normal(0.02 / 252, 0.04 / np.sqrt(252), n)))
    return pd.DataFrame({"STK": stk, "BND": bnd}, index=idx)


def test_backtest_runs_and_accounts_for_contributions():
    cfg = make_cfg(drawdown_window_days=252, trend_window_days=200)
    px = synthetic_market()
    res = run_backtest(cfg, px, initial_cash=10_000)
    months = len(set(zip(res.equity.index.year, res.equity.index.month)))
    assert res.invested == pytest.approx(10_000 + 500 * (months - 1))
    assert res.final > 0 and res.trades > 0
    assert 0 <= res.max_drawdown < 1
    results = compare(cfg, px, 10_000)
    assert len(results) == 4 and all(r.invested == res.invested for r in results)


def test_backtest_has_no_lookahead():
    """Modifier le futur ne doit pas changer les décisions passées."""
    cfg = make_cfg(drawdown_window_days=252, trend_window_days=200)
    px = synthetic_market(seed=1)
    a = run_backtest(cfg, px, 10_000)
    px2 = px.copy()
    px2.iloc[-100:] *= 0.5
    b = run_backtest(cfg, px2, 10_000)
    cut = px.index[-102]
    pd.testing.assert_series_equal(a.equity.loc[:cut], b.equity.loc[:cut])


def test_cache_incremental(tmp_path, monkeypatch):
    from invest_bot import data

    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    idx = pd.bdate_range("2026-01-01", periods=30)
    appels = []

    def faux(tickers, start, strict):
        appels.append((tuple(tickers), start))
        jours = idx if start == "2000-01-01" else idx[-12:].append(pd.bdate_range(idx[-1], periods=3)[1:])
        return pd.DataFrame({t: np.arange(len(jours), dtype=float) + 1 for t in tickers}, index=jours)

    monkeypatch.setattr(data, "_telecharger", faux)
    premier = data.fetch_prices(["A", "B"], use_cache=False, incremental=True)
    assert len(premier) == 30 and appels[-1] == (("A", "B"), "2000-01-01")
    second = data.fetch_prices(["A", "B", "C"], use_cache=False, incremental=True)
    assert appels[-2][0] == ("A", "B") and appels[-2][1] != "2000-01-01"  # seulement les derniers jours
    assert appels[-1] == (("C",), "2000-01-01")  # nouveau titre : historique complet
    assert len(second) == 32 and list(second.columns) == ["A", "B", "C"]
