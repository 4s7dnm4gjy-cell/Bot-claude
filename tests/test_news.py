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


def test_verdicts():
    calme = analyser([art("Walmart beats estimates"), art("Walmart opens new stores")], -0.02)
    assert calme.verdict == "vert"
    a_voir = analyser([art("SEC probe into X"), art("X faces lawsuit"), art("X recall")], -0.05)
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
    act = analyser([art("SEC probe into X")], -0.2)
    assert news.Actualites.from_dict(act.to_dict()) == act
