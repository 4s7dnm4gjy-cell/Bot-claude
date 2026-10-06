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
    # Pas de réseau en test : actualités calmes par défaut.
    from invest_bot import news

    monkeypatch.setattr(news, "lire_flux", lambda nom, jours=30: [news.Article(f"{nom} ouvre un magasin", "https://ex.com", "2026-10-01", "Test")])


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
        "HAUT": {"nom": "Haut SA", "isin": "FR0000000001", "devise": "EUR"},
        "SOLDE": {"nom": "Soldée SA", "isin": "FR0000000002", "devise": "EUR"},
        "DECLIN": {"nom": "Déclin SA", "isin": "FR0000000003", "devise": "EUR"},
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


def test_radar_scandale_bloque_l_alerte(cfg_radar, monkeypatch):
    from invest_bot import news, radar

    monkeypatch.setattr(radar.Opportunite, "favorable", property(lambda self: True))
    monkeypatch.setattr(news, "lire_flux", lambda nom, jours=30: [
        news.Article(f"{nom} : fraude comptable, perquisition au siège", "https://ex.com/a", "2026-10-01", "AFP"),
        news.Article(f"{nom} bankruptcy fears grow", "https://ex.com/b", "2026-09-30", "Reuters"),
    ])
    px = marche()
    px.iloc[-60:] *= np.linspace(1, 1.3, 60)[:, None]
    assert conseil.lancer_conseil(cfg_radar, px, px["WORLD"], date(2025, 6, 3), prix_radar=radar_prix()) is None
    bulletin = json.loads(conseil.A_PUBLIER.read_text())["bulletin"]
    assert "⛔" in bulletin and "Soldée SA" in bulletin


def test_radar_ticket_montre_les_actualites(cfg_radar, monkeypatch):
    from invest_bot import news, radar

    monkeypatch.setattr(radar.Opportunite, "favorable", property(lambda self: True))
    monkeypatch.setattr(news, "lire_flux", lambda nom, jours=30: [
        news.Article(f"{nom} faces lawsuit over pricing", "https://ex.com/a", "2026-10-01", "Reuters"),
    ])
    px = marche()
    px.iloc[-60:] *= np.linspace(1, 1.3, 60)[:, None]
    prop = conseil.lancer_conseil(cfg_radar, px, px["WORLD"], date(2025, 6, 3), prix_radar=radar_prix())
    assert prop["type"] == "opportunite"
    corps = json.loads(conseil.A_PUBLIER.read_text())["corps"]
    assert "Pourquoi Soldée SA baisse" in corps and "https://ex.com/a" in corps


def test_devises_et_conversion_en_euros():
    from invest_bot.radar import devise, en_euros, tickers_change

    assert devise("AAPL") == "USD" and devise("MC.PA") == "EUR" and devise("AZN.L") == "GBp"
    assert devise("7203.T") == "JPY" and devise("NOVO-B.CO") == "DKK"
    assert tickers_change({"USD", "GBp", "EUR"}) == {"USD": "EURUSD=X", "GBp": "EURGBP=X"}
    taux = {"USD": 1.10, "GBP": 0.85, "JPY": 160.0}
    assert en_euros(110, "USD", taux) == pytest.approx(100)
    assert en_euros(8500, "GBp", taux) == pytest.approx(100)  # 8 500 pence = 85 £
    assert en_euros(16000, "JPY", taux) == pytest.approx(100)
    assert en_euros(100, "SEK", taux) is None  # taux manquant : pas de proposition chiffrée


def test_radar_titre_etranger_quantite_en_euros(cfg_radar, monkeypatch):
    from dataclasses import replace
    from invest_bot import radar

    monkeypatch.setattr(radar.Opportunite, "favorable", property(lambda self: True))
    liste = {"SOLDE.T": {"nom": "Soldée KK", "isin": "JP0000000001"}}
    c = replace(cfg_radar, radar={**cfg_radar.radar, "liste": liste, "montant": 150})
    rp = radar_prix().rename(columns={"SOLDE": "SOLDE.T"})[["SOLDE.T"]] * 100  # cours en yens
    px = marche()
    px.iloc[-60:] *= np.linspace(1, 1.3, 60)[:, None]
    prop = conseil.lancer_conseil(c, px, px["WORLD"], date(2025, 6, 3), prix_radar=rp, taux={"JPY": 160.0})
    o = prop["ordres"][0]
    assert o["price"] == pytest.approx(rp["SOLDE.T"].iloc[-1] / 160)  # prix en euros
    assert o["quantity"] * o["price"] <= 2 * 150
    assert "JPY" in json.loads(conseil.A_PUBLIER.read_text())["corps"]


def test_comparaison_au_marche_sans_effet_de_change():
    from invest_bot.radar import ecart_marche, en_euros_serie

    idx = pd.bdate_range("2025-01-01", periods=100)
    marche_eur = pd.Series(100.0, index=idx)
    action_usd = pd.Series(110.0, index=idx)  # stable en dollars…
    eurusd = pd.Series(np.linspace(1.10, 1.21, 100), index=idx)  # …mais le dollar baisse de 10 %
    en_eur = en_euros_serie(action_usd, "USD", {"USD": eurusd})
    assert ecart_marche(en_eur, marche_eur) == pytest.approx(-0.06, abs=0.02)  # effet de change visible
    assert ecart_marche(action_usd, marche_eur) == pytest.approx(0.0)
    assert en_euros_serie(action_usd, "SEK", {}) is None


def test_mention_du_proprietaire_pour_l_inbox(cfg, monkeypatch):
    envois = []

    class FauxGitHub(conseil.GitHub):
        def __init__(self):
            self.token, self.repo, self.api = "x", "moi/depot", ""

        def creer_ticket(self, titre, corps, label="proposition"):
            envois.append(("ticket", corps))
            return 10 if label == "proposition" else 1

        def commenter(self, numero, texte):
            envois.append(("commentaire", texte))

        def est_ouvert(self, numero):
            return True

    px = marche(final_drop=0.25)
    conseil.lancer_conseil(cfg, px, px["WORLD"], date(2025, 6, 3))
    monkeypatch.setattr(conseil, "GitHub", FauxGitHub)
    assert conseil.publier(cfg) == 10
    assert all(texte.startswith("@moi") for _, texte in envois)  # ticket, bulletin : mention partout
    assert {genre for genre, _ in envois} == {"ticket", "commentaire"}
