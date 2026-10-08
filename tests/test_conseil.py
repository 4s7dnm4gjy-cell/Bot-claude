import json
from datetime import date, datetime, timedelta, timezone

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


class FauxGitHub:
    """Remplace l'API GitHub : garde les tickets, commentaires et fermetures en mémoire."""

    tickets: dict = {}
    commentaires: list = []

    def __init__(self):
        self.repo, self.token = "moi/depot", "x"

    actif = True
    mention = "@moi"

    def creer_ticket(self, titre, corps, label="proposition"):
        n = 100 + len(FauxGitHub.tickets)
        FauxGitHub.tickets[n] = {"titre": titre, "corps": corps, "ouvert": True}
        return n

    def commenter(self, numero, texte):
        FauxGitHub.commentaires.append((numero, texte))

    def fermer(self, numero):
        FauxGitHub.tickets[numero]["ouvert"] = False

    def est_ouvert(self, numero):
        return FauxGitHub.tickets.get(numero, {}).get("ouvert", False)


@pytest.fixture
def gh(monkeypatch):
    FauxGitHub.tickets, FauxGitHub.commentaires = {}, []
    monkeypatch.setattr(conseil, "GitHub", FauxGitHub)
    return FauxGitHub


SAINE = {"revenueGrowth": 0.06, "earningsGrowth": 0.14, "recommendationMean": 1.6, "numberOfAnalystOpinions": 19,
         "targetMeanPrice": 120, "currentPrice": 100, "forwardPE": 14, "trailingPE": 17,
         "profitMargins": 0.11, "debtToEquity": 60, "forwardEps": 6.0, "trailingEps": 5.0}
FRAGILE = {"revenueGrowth": -0.04, "earningsGrowth": -0.30, "recommendationMean": 3.0, "numberOfAnalystOpinions": 9,
           "targetMeanPrice": 98, "currentPrice": 100, "forwardPE": 35, "profitMargins": -0.02, "debtToEquity": 250}


def preparer_radar(cfg_radar, monkeypatch, rp=None, taux=None, cfg=None, infos=None):
    """Conseil du soir (sans GitHub) : écrit la liste des candidats du mode express."""
    from invest_bot import radar

    monkeypatch.setattr(radar.Opportunite, "favorable", property(lambda self: True))
    px = marche()  # marché calme : pas de proposition sur les ETF
    px.iloc[-60:] *= np.linspace(1, 1.3, 60)[:, None]
    lire = (lambda t: infos.get(t, SAINE)) if isinstance(infos, dict) else (lambda t: SAINE)
    assert conseil.lancer_conseil(cfg or cfg_radar, px, px["WORLD"], date(2025, 6, 3),
                                  prix_radar=rp if rp is not None else radar_prix(), taux=taux,
                                  lire_fondamentaux=lire) is None
    return px


MIDI = datetime(2025, 6, 3, 10, 0, tzinfo=timezone.utc)  # 12 h à Paris


def test_radar_express_propose_puis_oui(cfg_radar, monkeypatch, gh):
    preparer_radar(cfg_radar, monkeypatch)
    assert "Radar" in json.loads(conseil.A_PUBLIER.read_text())["bulletin"]
    prop = conseil.lancer_express(cfg_radar, MIDI)
    assert prop["type"] == "opportunite" and prop["ordres"][0]["ticker"] == "SOLDE"
    ticket = gh.tickets[prop["ticket"]]
    assert "Soldée SA" in ticket["titre"] and "biais du survivant" in ticket["corps"]
    assert ticket["corps"].startswith("@moi")
    etat = conseil.charger_etat(cfg_radar)
    assert etat["opportunite"]["ticket"] == prop["ticket"] and etat["proposition"] is None
    conseil.executer_commande(cfg_radar, etat, "oui", prop["ticket"], date(2025, 6, 3))
    assert "SOLDE" in etat["satellites"] and "SOLDE" not in etat["positions"]
    assert etat["apport_en_attente"] == 200  # l'apport du mois n'a pas été consommé
    assert etat["opportunite"] is None


def test_radar_express_30_minutes_puis_titre_suivant_jamais_deux_fois(cfg_radar, monkeypatch, gh):
    from dataclasses import replace

    rp = radar_prix()
    rp["SOLDE2"] = rp["SOLDE"] * 1.01
    liste = {**cfg_radar.radar["liste"], "SOLDE2": {"nom": "Soldée Bis", "isin": "FR0000000009", "devise": "EUR"}}
    c = replace(cfg_radar, radar={**cfg_radar.radar, "liste": liste})
    preparer_radar(cfg_radar, monkeypatch, rp=rp, cfg=c)

    p1 = conseil.lancer_express(c, MIDI)
    assert conseil.lancer_express(c, MIDI + timedelta(minutes=20)) is None  # on laisse 30 min
    p2 = conseil.lancer_express(c, MIDI + timedelta(minutes=31))
    assert p2["ordres"][0]["ticker"] != p1["ordres"][0]["ticker"]
    assert not gh.tickets[p1["ticket"]]["ouvert"]  # l'ancien ticket est fermé, avec un mot
    assert any("Pas de réponse" in t for n, t in gh.commentaires if n == p1["ticket"])
    # Plus de candidat neuf : rien n'est reproposé, même des heures plus tard.
    assert conseil.lancer_express(c, MIDI + timedelta(minutes=62)) is None
    etat = conseil.charger_etat(c)
    assert sorted(etat["radar_proposes"]) == ["SOLDE", "SOLDE2"]


def test_radar_express_respecte_les_horaires(cfg_radar, monkeypatch, gh):
    preparer_radar(cfg_radar, monkeypatch)
    nuit = datetime(2025, 6, 3, 1, 0, tzinfo=timezone.utc)  # 3 h à Paris
    assert conseil.lancer_express(cfg_radar, nuit) is None
    assert conseil.lancer_express(cfg_radar, MIDI) is not None


def test_non_sur_une_opportunite_ne_bloque_pas_les_propositions(cfg_radar, monkeypatch, gh):
    preparer_radar(cfg_radar, monkeypatch)
    prop = conseil.lancer_express(cfg_radar, MIDI)
    etat = conseil.charger_etat(cfg_radar)
    rep = conseil.executer_commande(cfg_radar, etat, "non", prop["ticket"], date(2025, 6, 3))
    assert "plus jamais" in rep and etat["pause_jusqua"] is None and etat["opportunite"] is None


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


def test_radar_ticket_montre_les_actualites(cfg_radar, monkeypatch, gh):
    from invest_bot import news

    preparer_radar(cfg_radar, monkeypatch)
    monkeypatch.setattr(news, "lire_flux", lambda nom, jours=30: [
        news.Article(f"{nom} faces lawsuit over pricing", "https://ex.com/a", "2026-10-01", "Reuters"),
    ])
    prop = conseil.lancer_express(cfg_radar, MIDI)
    corps = gh.tickets[prop["ticket"]]["corps"]
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


def test_radar_titre_etranger_quantite_en_euros(cfg_radar, monkeypatch, gh):
    from dataclasses import replace

    liste = {"SOLDE.T": {"nom": "Soldée KK", "isin": "JP0000000001"}}
    c = replace(cfg_radar, radar={**cfg_radar.radar, "liste": liste, "montant": 150})
    rp = radar_prix().rename(columns={"SOLDE": "SOLDE.T"})[["SOLDE.T"]] * 100  # cours en yens
    preparer_radar(c, monkeypatch, rp=rp, taux={"JPY": 160.0}, cfg=c)
    prop = conseil.lancer_express(c, MIDI)
    o = prop["ordres"][0]
    assert o["price"] == pytest.approx(rp["SOLDE.T"].iloc[-1] / 160)  # prix en euros
    assert o["quantity"] * o["price"] <= 2 * 150
    assert "JPY" in gh.tickets[prop["ticket"]]["corps"]


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


def test_score_fondamental_distingue_baisse_et_qualite():
    from invest_bot.fondamentaux import score_fondamental

    bon, notes = score_fondamental(SAINE)
    mauvais, _ = score_fondamental(FRAGILE)
    assert bon >= 95 and mauvais <= 25
    assert any("achat fort" in n for n in notes) and any("P/E attendu 14.0" in n for n in notes)
    assert score_fondamental({}) == (None, ["aucune donnée fondamentale disponible"])
    neutre, _ = score_fondamental({"forwardPE": 20})
    assert 45 <= neutre <= 60  # données manquantes : ni bonus ni pénalité


def test_express_ecarte_une_action_en_baisse_aux_fondamentaux_faibles(cfg_radar, monkeypatch, gh):
    from dataclasses import replace

    rp = radar_prix()
    rp["SOLDE2"] = rp["SOLDE"] * 1.01
    liste = {**cfg_radar.radar["liste"], "SOLDE2": {"nom": "Soldée Saine", "isin": "FR0000000009", "devise": "EUR"}}
    c = replace(cfg_radar, radar={**cfg_radar.radar, "liste": liste})
    preparer_radar(cfg_radar, monkeypatch, rp=rp, cfg=c, infos={"SOLDE": FRAGILE, "SOLDE2": SAINE})
    candidats = json.loads(conseil.CANDIDATS.read_text())["candidats"]
    assert [x["ticker"] for x in candidats][0] == "SOLDE2"  # classée devant grâce aux fondamentaux
    prop = conseil.lancer_express(c, MIDI)
    assert prop["ordres"][0]["ticker"] == "SOLDE2"
    corps = gh.tickets[prop["ticket"]]["corps"]
    assert "Score global" in corps and "achat fort" in corps
    # La fragile n'est jamais proposée, même quand il n'y a plus d'autre candidat.
    assert conseil.lancer_express(c, MIDI + timedelta(minutes=31)) is None


def test_cas_ig_group_baisse_forte_et_objectifs_perimes_ecartee():
    """Chiffres passés flatteurs mais cours en chute libre : le bot ne doit plus s'y fier."""
    from invest_bot.fondamentaux import enrichir

    ig = {"revenueGrowth": 0.165, "earningsGrowth": 0.01, "recommendationMean": 1.6, "numberOfAnalystOpinions": 8,
          "targetMeanPrice": 16.1, "currentPrice": 10.0, "forwardPE": 7.3, "trailingPE": 9.0,
          "profitMargins": 0.42, "debtToEquity": 33}
    c = [{"ticker": "IGG.L", "type": "action", "score": 99, "vs_marche_3m": -0.52}]
    (r,) = enrichir(c, lambda t: ig)
    assert r["fondamental"] < 70  # sous le seuil : jamais proposée
    assert any("peu crédible" in n for n in r["fondamental_notes"])
    assert any("sans explication claire" in n for n in r["fondamental_notes"])


def test_express_ecarte_un_avertissement_sur_resultats(cfg_radar, monkeypatch, gh):
    from invest_bot import news

    preparer_radar(cfg_radar, monkeypatch)
    monkeypatch.setattr(news, "lire_flux", lambda nom, jours=30: [
        news.Article(f"{nom} shares plunge after profit warning", "https://ex.com/w", "2026-10-02", "Reuters"),
    ])
    assert conseil.lancer_express(cfg_radar, MIDI) is None
    assert "SOLDE" in conseil.charger_etat(cfg_radar)["radar_proposes"]  # écartée définitivement


def test_memoire_des_fondamentaux_quand_yahoo_refuse(tmp_path):
    from invest_bot.fondamentaux import enrichir

    cache = tmp_path / "fond.json"
    cand = lambda: [{"ticker": "CRH", "type": "action", "score": 96, "vs_marche_3m": -0.05}]  # noqa: E731
    lectures = []

    def yahoo_ok(t):
        lectures.append(t)
        return SAINE

    (r,) = enrichir(cand(), yahoo_ok, cache=cache, aujourdhui=date(2026, 10, 1))
    assert r["fondamental"] >= 95 and lectures == ["CRH"]
    # Trois jours plus tard : données fraîches en mémoire, aucune nouvelle lecture.
    (r,) = enrichir(cand(), yahoo_ok, cache=cache, aujourdhui=date(2026, 10, 4))
    assert lectures == ["CRH"] and r["fondamental"] >= 95
    # Dix jours plus tard, Yahoo refuse : on reprend les dernières données connues.
    (r,) = enrichir(cand(), lambda t: {}, cache=cache, aujourdhui=date(2026, 10, 11))
    assert r["fondamental"] >= 95 and any("Yahoo indisponible" in n for n in r["fondamental_notes"])
    # Trop vieilles (plus de 45 jours) : on ne s'y fie plus.
    (r,) = enrichir(cand(), lambda t: {}, cache=cache, aujourdhui=date(2026, 12, 1))
    assert r["fondamental"] is None


def test_braderie_ou_sanction_meritee():
    """Une chute de 25 % face au marché n'a pas le même sens selon les perspectives."""
    from invest_bot.fondamentaux import enrichir

    degradee = {**SAINE, "forwardEps": 4.0, "trailingEps": 5.0}  # bénéfices attendus en baisse
    floue = {k: v for k, v in SAINE.items() if k not in ("forwardEps", "trailingEps")}
    c = [{"ticker": t, "type": "action", "score": 95, "vs_marche_3m": -0.25} for t in ("B", "D", "F")]
    infos = {"B": SAINE, "D": degradee, "F": floue}
    r = {x["ticker"]: x for x in enrichir(c, lambda t: infos[t])}
    base = {t: enrichir([{"ticker": t, "type": "action", "score": 95, "vs_marche_3m": 0.0}],
                        lambda t: infos[t])[0]["fondamental"] for t in infos}
    assert r["B"]["braderie"] and r["B"]["fondamental"] == min(100, base["B"] + 8)
    assert any("braderie probable" in n for n in r["B"]["fondamental_notes"])
    assert not r["D"]["braderie"] and r["D"]["fondamental"] == base["D"] - 12
    assert any("méritée" in n for n in r["D"]["fondamental_notes"])
    assert r["F"]["fondamental"] == base["F"] - 6
    assert [x["ticker"] for x in enrichir([dict(x) for x in c], lambda t: infos[t])][0] == "B"


def test_titre_du_ticket_braderie():
    prop = {"type": "opportunite", "score": 90, "ordres": [{"side": "buy", "quantity": 1, "price": 100.0}],
            "radar": {"nom": "CRH", "fondamental": 90, "score_global": 92, "braderie": True}}
    assert conseil.titre_ticket(prop).startswith("🏷️ Braderie : CRH")


def test_chute_extreme_jamais_braderie():
    from invest_bot.fondamentaux import enrichir

    (r,) = enrichir([{"ticker": "X", "type": "action", "score": 99, "vs_marche_3m": -0.52}], lambda t: SAINE)
    assert not r["braderie"] and r["fondamental"] < 80
