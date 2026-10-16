from datetime import date

from ecom_bot.aliexpress import ProduitAli, signer
from ecom_bot.config import EcomConfig
from ecom_bot.ebay import AnnonceEbay
from ecom_bot.pipeline import executer, rapport
from ecom_bot.selection import meilleur_fournisseur, prix_de_vente, requete, ressemblance
from ecom_bot.shopify import fiche_produit


def cfg(**kw) -> EcomConfig:
    base = dict(mots_cles=["lampe"], ventes_min=10, note_min=90, commandes_min=50,
                ressemblance_min=0.25, marge_min=5, coefficient=2.5)
    base.update(kw)
    return EcomConfig(**base)


def ali(pid="1", titre="Lampe LED sans fil rechargeable USB", prix=6.0, commandes=500, note=97.0):
    return ProduitAli(pid, titre, prix, "https://img/1.jpg", ["https://img/2.jpg"], commandes, note,
                      f"https://aliexpress.com/item/{pid}.html")


class FauxEbay:
    def __init__(self, annonces, ventes):
        self.annonces, self._ventes, self.appels = annonces, ventes, 0

    def rechercher(self, **kw):
        return list(self.annonces)

    def ventes(self, item_id):
        self.appels += 1
        return self._ventes[item_id]


class FauxAli:
    def __init__(self, produits):
        self.produits = produits

    def rechercher(self, mots, **kw):
        return list(self.produits)


class FauxShopify:
    def __init__(self, deja=()):
        self.crees, self.deja = [], set(deja)

    def existe(self, tag):
        return tag in self.deja

    def creer(self, fiche):
        self.crees.append(fiche)
        return f"gid://shopify/Product/{len(self.crees)}"


def test_requete_retire_les_mots_inutiles():
    assert requete("NEUF Lampe LED sans fil - Livraison GRATUITE France") == "lampe led fil"


def test_ressemblance():
    assert ressemblance("Lampe LED sans fil", "lampe led rechargeable") > 0.3
    assert ressemblance("Lampe LED", "Chaussettes laine") == 0


def test_prix_plafonne_sous_ebay_et_marge():
    c = cfg()
    prix, marge = prix_de_vente(6.0, 29.90, c)
    assert prix == 14.99                      # 6 x 2,5 = 15 -> 14,99
    assert marge == round(14.99 - 6 - (14.99 * 0.029 + 0.30), 2)
    prix, _ = prix_de_vente(10.0, 20.0, c)    # 25 € > 19 € (eBay - 5 %) -> plafonné
    assert prix <= 19.0


def test_fournisseur_filtre_note_commandes_titre_et_prix():
    c = cfg()
    titre = "Lampe LED sans fil rechargeable"
    candidats = [
        ali("a", note=80),                        # trop mal noté
        ali("b", commandes=3),                    # pas assez vendu
        ali("c", titre="Tapis de yoga"),          # autre produit
        ali("d", prix=40),                        # plus cher qu'eBay
        ali("e", prix=7), ali("f", prix=5),
    ]
    assert meilleur_fournisseur(titre, 25, candidats, c).product_id == "f"
    assert meilleur_fournisseur(titre, 25, candidats[:4], c) is None


def test_fiche_shopify_sans_contenu_ebay():
    f = fiche_produit("Lampe <LED>", 14.99, 29.9, "ali-1", ["https://a.jpg", "https://a.jpg", "//x"],
                      ["ali-1"], "DRAFT")
    assert f["variants"][0]["price"] == "14.99"
    assert f["variants"][0]["compareAtPrice"] == "29.90"
    assert [x["originalSource"] for x in f["files"]] == ["https://a.jpg"]
    assert "&lt;LED&gt;" in f["descriptionHtml"]
    assert f["status"] == "DRAFT"


def test_pipeline_complet_et_doublons():
    annonces = [AnnonceEbay("e1", "Lampe LED sans fil rechargeable", 29.9, "EUR", "v", "u"),
                AnnonceEbay("e2", "Lampe LED sans fil USB", 27.0, "EUR", "v", "u"),
                AnnonceEbay("e3", "Lampe LED sans fil", 29.0, "EUR", "v", "u")]
    ebay = FauxEbay(annonces, {"e1": 120, "e2": 40, "e3": 2})
    shop = FauxShopify()
    etat = {}
    retenus = executer(cfg(), ebay, FauxAli([ali("1")]), shop, etat, log=lambda *_: None)
    # e3 ne se vend pas ; e1 et e2 pointent vers le même fournisseur -> un seul produit
    assert len(retenus) == 1 and len(shop.crees) == 1
    assert retenus[0].ebay.item_id == "e1"
    assert "1" in etat["importes"]
    assert "ali-1" in shop.crees[0]["tags"]

    # 2e passage le même jour : annonces déjà vues, fournisseur déjà importé
    ebay.appels = 0
    assert executer(cfg(), ebay, FauxAli([ali("1")]), shop, etat, log=lambda *_: None) == []
    assert ebay.appels == 0 and len(shop.crees) == 1
    assert "Aucun produit" in rapport([], False, cfg())


def test_simulation_ne_cree_rien_et_limite_journaliere():
    annonces = [AnnonceEbay(f"e{i}", "Lampe LED sans fil rechargeable", 29.9, "EUR", "v", "u")
                for i in range(5)]
    ebay = FauxEbay(annonces, {f"e{i}": 50 for i in range(5)})

    class AliVarie(FauxAli):
        n = 0

        def rechercher(self, mots, **kw):
            AliVarie.n += 1
            return [ali(str(AliVarie.n))]

    etat = {"ebay_vus": {"vieux": {"date": "2000-01-01"}}}
    retenus = executer(cfg(produits_par_jour=3), ebay, AliVarie([]), None, etat, log=lambda *_: None)
    assert len(retenus) == 3 and not any(r.shopify_id for r in retenus)
    assert "vieux" not in etat["ebay_vus"]
    assert etat["ebay_vus"]["e0"]["date"] == str(date.today())


def test_deja_dans_shopify_pas_recree():
    annonces = [AnnonceEbay("e1", "Lampe LED sans fil rechargeable", 29.9, "EUR", "v", "u")]
    shop = FauxShopify(deja={"ali-1"})
    executer(cfg(), FauxEbay(annonces, {"e1": 99}), FauxAli([ali("1")]), shop, {}, log=lambda *_: None)
    assert shop.crees == []


def test_signature_aliexpress_stable():
    s = signer({"b": "2", "a": "1"}, "secret")
    assert s == signer({"a": "1", "b": "2"}, "secret") and s.isupper() and len(s) == 64


def test_config_fichier_valide():
    c = EcomConfig.charger()
    assert c.statut in ("DRAFT", "ACTIVE") and (c.mots_cles or c.categories)
