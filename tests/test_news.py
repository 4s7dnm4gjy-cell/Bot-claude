from invest_bot import news
from invest_bot.news import Article, analyser, signaux

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>McDonald's : ventes en baisse au troisieme trimestre - Les Echos</title>
<link>https://ex.com/1</link><pubDate>Thu, 01 Oct 2026 10:00:00 GMT</pubDate><source>Les Echos</source></item>
<item><title>SEC opens probe into McDonald's franchise accounting - Reuters</title>
<link>https://ex.com/2</link><pubDate>Wed, 30 Sep 2026 10:00:00 GMT</pubDate><source>Reuters</source></item>
</channel></rss>"""


def art(titre):
    return Article(titre, "https://ex.com", "2026-10-01", "Test")


def test_mots_entiers_et_accents():
    assert signaux("Shares define a new range")[0] == 0
    assert signaux("Fraude : perquisition au siège")[0] == 2
    assert "avertissement sur resultats" in signaux("Avertissement sur résultats pour X")[1]


def test_faux_positifs_de_la_vraie_presse():
    # Titres réels relevés le 03/10/2026 qui déclenchaient à tort une alerte.
    titres = [
        "ENQUÊTE : Les résultats de Costco mettront à l'épreuve la dynamique des ventes - Boursorama",
        "Un initié de Costco Wholesale a vendu des actions pour 733 328 dollars, selon un récent dépôt auprès de la SEC",
        "3 Unpopular Stocks Walking a Fine Line - StockStory",
    ]
    assert all(signaux(t)[0] == 0 for t in titres)
    autre = analyser([art("Spirit Airlines' final Airbus aircraft sold in $668 million bankruptcy deal")], -0.11, "Airbus")
    assert autre.verdict == "vert"  # la faillite est celle de Spirit, pas d'Airbus
    dementi = analyser([art("Procter & Gamble Hygiene Denies Rumours Of Delisting")], -0.06, "Procter & Gamble")
    assert dementi.verdict == "vert"
    vrai = analyser([art("Airbus : soupçons de fraude, perquisition au siège"), art("Airbus scandal widens")], -0.2, "Airbus")
    assert vrai.verdict == "rouge"


def test_beaucoup_d_articles_mineurs_sur_une_grande_entreprise():
    articles = [art("Walmart opens store")] * 40 + [art("FTC probe into Walmart"), art("Walmart recall")]
    assert analyser(articles, -0.09, "Walmart").verdict == "vert"


def test_verdicts():
    calme = analyser([art("Walmart beats estimates"), art("Walmart opens new stores")], -0.02)
    assert calme.verdict == "vert"
    a_voir = analyser([art("FTC probe into X"), art("X faces lawsuit"), art("X recall")], -0.05)
    assert a_voir.verdict == "orange" and a_voir.alertes
    grave = analyser([art("X : fraude comptable"), art("X bankruptcy fears")], -0.30)
    assert grave.verdict == "rouge"
    propre = analyser([art("X news")], -0.25)  # baisse bien pire que le marché, sans article
    assert propre.verdict == "orange"


def test_lecture_flux_et_reseau_indisponible(monkeypatch):
    class R:
        content = RSS

        def raise_for_status(self):
            pass

    monkeypatch.setattr(news.requests, "get", lambda *a, **k: R())
    articles = news.lire_flux("McDonald's")
    assert len(articles) == 2 and articles[0].date == "2026-10-01"  # doublons fr/en fusionnés

    def panne(*a, **k):
        raise ConnectionError("hors ligne")

    monkeypatch.setattr(news.requests, "get", panne)
    act = news.verifier("McDonald's", -0.1)
    assert act.verdict == "inconnu" and "indisponibles" in act.resume


def test_aller_retour_dict():
    act = analyser([art("FTC probe into X")], -0.2)
    assert news.Actualites.from_dict(act.to_dict()) == act


def test_conversion_des_codes_d_indices():
    from invest_bot.univers import convertir

    assert convertir("BRK.B", "", "us") == "BRK-B"
    assert convertir("NYSE: KO", "", "us") == "KO"
    assert convertir("BT.A", ".L", "uk") == "BT-A.L"
    assert convertir("7203", ".T", "japon") == "7203.T"
    assert convertir("SEHK: 5", ".HK", "hk") == "0005.HK"
    assert convertir("ATCO A", ".ST", "nordique") == "ATCO-A.ST"
    assert convertir("MC.PA", ".PA", None) == "MC.PA"
    assert convertir("ADS", ".DE", None) == "ADS.DE"
    assert convertir("nan", ".DE", None) is None
    assert convertir("OSE: DNB", ".OL", "nordique") == "DNB.OL"
    assert convertir("Euronext: ABN", ".AS", None) == "ABN.AS"


def test_plusieurs_fichiers_de_liste(tmp_path):
    from invest_bot.config import load_config

    (tmp_path / "a.yaml").write_text("X.PA: {nom: X verifie, isin: FR1}\n", encoding="utf-8")
    (tmp_path / "b.yaml").write_text("X.PA: {nom: X auto}\nY.DE: {nom: Y}\n", encoding="utf-8")
    (tmp_path / "c.yaml").write_text(
        "targets: {W: 1.0}\nbenchmark: W\nradar:\n  fichiers: [a.yaml, b.yaml, absent.yaml]\n", encoding="utf-8")
    cfg = load_config(tmp_path / "c.yaml")
    assert cfg.radar["liste"] == {"X.PA": {"nom": "X verifie", "isin": "FR1"}, "Y.DE": {"nom": "Y"}}
