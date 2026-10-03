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


@pytest.fixture
def cfg_plan(cfg):
    from dataclasses import replace

    c = replace(
        cfg, mode="plan", reserve_pct=0.0, reserve_tiers=[], jour_plan=2,
        alertes_krach=[{"drawdown": 0.15, "mois": 2}, {"drawdown": 0.25, "mois": 4}],
    )
    c.validate()
    return c


def test_plan_inscrit_le_plan_sans_proposition(cfg_plan):
    px = marche()
    assert conseil.lancer_conseil(cfg_plan, px, px["WORLD"], date(2025, 6, 2)) is None
    etat = conseil.charger_etat(cfg_plan)
    valeur = sum(q * px.iloc[-1][t] for t, q in etat["positions"].items())
    assert valeur == pytest.approx(200, rel=1e-3)  # parts fractionnées du plan
    assert etat["proposition"] is None
    conseil.lancer_conseil(cfg_plan, px, px["WORLD"], date(2025, 6, 3))
    assert conseil.charger_etat(cfg_plan)["positions"] == etat["positions"]  # une fois par mois
    bulletin = json.loads(conseil.A_PUBLIER.read_text())["bulletin"]
    assert "Rien à faire" in bulletin


def test_plan_alerte_krach_une_seule_fois_par_palier(cfg_plan):
    px = marche()
    conseil.lancer_conseil(cfg_plan, px, px["WORLD"], date(2025, 6, 2))
    crash = marche(final_drop=0.30)
    prop = conseil.lancer_conseil(cfg_plan, crash, crash["WORLD"], date(2025, 6, 4))
    assert prop["type"] == "krach_plan" and prop["liberation"] == 800  # palier -25 % : 4 mois
    assert "ne vendez rien" in json.loads(conseil.A_PUBLIER.read_text())["corps"]
    etat = conseil.charger_etat(cfg_plan)
    conseil.executer_commande(cfg_plan, etat, "non", None, date(2025, 6, 4))
    etat["pause_jusqua"] = None
    conseil.sauver_etat(etat)
    assert conseil.lancer_conseil(cfg_plan, crash, crash["WORLD"], date(2025, 6, 5)) is None


def test_plan_reequilibrage(cfg_plan):
    px = marche()
    etat = conseil.etat_vide(cfg_plan)
    etat["positions"] = {"WORLD": 100.0}  # 100 % actions monde pour une cible de 85 %
    etat["dernier_mois_plan"] = "2025-06"
    conseil.sauver_etat(etat)
    prop = conseil.lancer_conseil(cfg_plan, px, px["WORLD"], date(2025, 6, 4))
    assert prop["type"] == "vente"
    assert {o["side"] for o in prop["ordres"]} == {"sell", "buy"}


def test_pas_de_proposition_le_week_end(cfg):
    px = marche(final_drop=0.25)
    assert conseil.lancer_conseil(cfg, px, px["WORLD"], date(2025, 6, 7)) is None  # samedi
    assert "Bourse fermée" in json.loads(conseil.A_PUBLIER.read_text())["bulletin"]


def radar_prix(n: int = 2000) -> pd.DataFrame:
    rng = np.random.default_rng(5)
    idx = pd.bdate_range("2017-01-02", periods=n)
    up = 20 * np.exp(np.cumsum(rng.normal(0.0006, 0.012, n)))
    soldee = up.copy()
    soldee[-40:] *= np.linspace(1, 0.72, 40)  # chute récente de 28 %
    declin = 50 * np.exp(np.cumsum(rng.normal(-0.0008, 0.012, n)))
    declin[-40:] *= np.linspace(1, 0.7, 40)
    return pd.DataFrame({"HAUT": up, "SOLDE": soldee, "DECLIN": declin}, index=idx)


@pytest.fixture
def cfg_radar(cfg):
    from dataclasses import replace

    c = replace(cfg, radar={"liste": {
        "HAUT": {"nom": "Haut SA", "isin": "FR0000000001"},
        "SOLDE": {"nom": "Soldée SA", "isin": "FR0000000002"},
        "DECLIN": {"nom": "Déclin SA", "isin": "FR0000000003"},
    }, "score_min": 70, "score_alerte": 80, "montant": 150})
    c.validate()
    return c


def test_radar_scanner_filtre_et_classe():
    from invest_bot.radar import scanner

    px = radar_prix()
    ops = scanner({t: {} for t in px}, px, 70)
    tickers = [o.ticker for o in ops]
    assert "SOLDE" in tickers
    assert "HAUT" not in tickers  # pas soldée
    assert "DECLIN" not in tickers  # tendance 5 ans négative : écartée


def test_radar_alerte_opportunite_puis_oui(cfg_radar, monkeypatch):
    from invest_bot import radar

    monkeypatch.setattr(radar.Opportunite, "favorable", property(lambda self: True))
    px = marche()  # marché calme : pas de proposition sur les ETF
    px.iloc[-60:] *= np.linspace(1, 1.3, 60)[:, None]
    rp = radar_prix()
    prop = conseil.lancer_conseil(cfg_radar, px, px["WORLD"], date(2025, 6, 3), prix_radar=rp)
    assert prop["type"] == "opportunite" and prop["ordres"][0]["ticker"] == "SOLDE"
    pub = json.loads(conseil.A_PUBLIER.read_text())
    assert "Soldée SA" in pub["titre"] and "biais du survivant" in pub["corps"]
    assert "Radar" in pub["bulletin"]
    etat = conseil.charger_etat(cfg_radar)
    conseil.executer_commande(cfg_radar, etat, "oui", None, date(2025, 6, 4))
    assert "SOLDE" in etat["satellites"] and "SOLDE" not in etat["positions"]
    assert etat["apport_en_attente"] == 200  # l'apport du mois n'a pas été consommé
    conseil.sauver_etat(etat)
    # Pas de nouvelle alerte sur le même titre pendant le délai.
    assert conseil.lancer_conseil(cfg_radar, px, px["WORLD"], date(2025, 6, 5), prix_radar=rp) is None
