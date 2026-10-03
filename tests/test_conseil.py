import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from invest_bot import conseil
from invest_bot.config import Config, ReserveTier


@pytest.fixture
def cfg():
    c = Config(
        targets={"WORLD": 0.85, "EM": 0.15},
        benchmark="WORLD",
        monthly_contribution=200,
        reserve_pct=0.10,
        reserve_tiers=[ReserveTier(0.15, 0.05), ReserveTier(0.30, 0.0)],
        fractional=False,
        min_order_value=10,
        fee_fixed=1.0,
        fee_bps=0,
        score_seuil=60,
        jour_limite=20,
        isin={"WORLD": "IE00B4L5Y983"},
    )
    c.validate()
    return c


def marche(final_drop: float = 0.0, n: int = 900) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    w = 50 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, n)))
    if final_drop:
        w[-30:] *= np.linspace(1, 1 - final_drop, 30)
    idx = pd.bdate_range("2022-01-03", periods=n)
    return pd.DataFrame({"WORLD": w, "EM": w * 0.4}, index=idx)


@pytest.fixture(autouse=True)
def isole(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


def test_crash_propose_achat_puis_oui(cfg):
    px = marche(final_drop=0.25)
    prop = conseil.lancer_conseil(cfg, px, px["WORLD"], date(2025, 6, 3))
    assert prop is not None and prop["type"] == "bon_moment"
    assert all(o["side"] == "buy" for o in prop["ordres"])
    assert all(float(o["quantity"]).is_integer() for o in prop["ordres"])  # parts entières
    pub = json.loads(conseil.A_PUBLIER.read_text())
    assert "IE00B4L5Y983" in pub["corps"] and "oui" in pub["corps"]
    assert conseil.publier(cfg) is None  # hors GitHub : affiché seulement

    etat = conseil.charger_etat(cfg)
    rep = conseil.executer_commande(cfg, etat, "Oui !", None, date(2025, 6, 4))
    assert rep.startswith("✅")
    assert etat["positions"] and etat["proposition"] is None
    assert etat["apport_en_attente"] == 0
    depense = sum(o["quantity"] * o["price"] + 1 for o in prop["ordres"])
    assert etat["cash"] == pytest.approx(200 - depense, abs=0.01)


def test_marche_haut_attend_puis_date_limite(cfg):
    px = marche()
    px.iloc[-60:] *= np.linspace(1, 1.3, 60)[:, None]  # forte hausse : score bas
    assert conseil.lancer_conseil(cfg, px, px["WORLD"], date(2025, 6, 3)) is None
    etat = conseil.charger_etat(cfg)
    assert etat["apport_en_attente"] == 200  # l'apport attend le bon moment
    prop = conseil.lancer_conseil(cfg, px, px["WORLD"], date(2025, 6, 20))
    assert prop is not None and prop["type"] == "date_limite"
    # Pas de deuxième proposition tant que la première est en attente.
    assert conseil.lancer_conseil(cfg, px, px["WORLD"], date(2025, 6, 21)) is None


def test_non_met_en_pause(cfg):
    px = marche(final_drop=0.25)
    conseil.lancer_conseil(cfg, px, px["WORLD"], date(2025, 6, 3))
    etat = conseil.charger_etat(cfg)
    rep = conseil.executer_commande(cfg, etat, "non", None, date(2025, 6, 4))
    assert rep.startswith("👌") and etat["pause_jusqua"] == "2025-06-11"
    conseil.sauver_etat(etat)
    assert conseil.lancer_conseil(cfg, px, px["WORLD"], date(2025, 6, 5)) is None
    assert conseil.lancer_conseil(cfg, px, px["WORLD"], date(2025, 6, 12)) is not None


def test_commandes_reglages(cfg):
    etat = conseil.etat_vide(cfg)
    assert "300" in conseil.executer_commande(cfg, etat, "apport 300", None, date.today())
    assert etat["apport_mensuel"] == 300
    conseil.executer_commande(cfg, etat, "capital 1 500", None, date.today())
    conseil.executer_commande(cfg, etat, "capital 1500", None, date.today())
    assert etat["apport_en_attente"] >= 1500
    conseil.executer_commande(cfg, etat, "possede world 12", None, date.today())
    assert etat["positions"] == {"WORLD": 12}
    assert "inconnu" in conseil.executer_commande(cfg, etat, "possede XYZ 3", None, date.today())
    assert conseil.executer_commande(cfg, etat, "merci beaucoup", None, date.today()) is None


def test_reponse_sur_mauvais_ticket(cfg):
    px = marche(final_drop=0.25)
    conseil.lancer_conseil(cfg, px, px["WORLD"], date(2025, 6, 3))
    etat = conseil.charger_etat(cfg)
    etat["proposition"]["ticket"] = 7
    assert "Aucune" in conseil.executer_commande(cfg, etat, "oui", 8, date(2025, 6, 4))
    assert etat["proposition"] is not None
