"""Une passe complète : eBay -> AliExpress -> Shopify."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from .aliexpress import AliExpress, ProduitAli
from .config import RACINE, EcomConfig
from .ebay import AnnonceEbay, Ebay
from .selection import meilleur_fournisseur, prix_de_vente, requete
from .shopify import Shopify, fiche_produit

ETAT = RACINE / "etat" / "ecom_importes.json"
RAPPORT = RACINE / "rapports" / "ecom.md"


@dataclass
class Retenu:
    ebay: AnnonceEbay
    ali: ProduitAli
    prix: float
    marge: float
    shopify_id: str = ""
    erreur: str = ""


def charger_etat(chemin: Path = ETAT) -> dict:
    if chemin.exists():
        return json.loads(chemin.read_text(encoding="utf-8"))
    return {"importes": {}, "ebay_vus": {}}


def sauver_etat(etat: dict, chemin: Path = ETAT) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(etat, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def sources(cfg: EcomConfig) -> list[tuple[str, str, str]]:
    """(mot-clé, vendeur, catégorie) à interroger. eBay exige un mot-clé ou une catégorie."""
    cibles = [(m, "") for m in cfg.mots_cles] + [("", c) for c in cfg.categories]
    if not cibles:
        raise ValueError("Ajoutez au moins un mot-clé ou une catégorie dans ecom_config.yaml")
    vendeurs = cfg.vendeurs or [""]
    return [(m, v, c) for v in vendeurs for m, c in cibles]


def _recent(vu, jours: int) -> bool:
    try:
        return date.fromisoformat(vu["date"]) > date.today() - timedelta(days=jours)
    except (TypeError, KeyError, ValueError):
        return False


def annonces_qui_vendent(ebay: Ebay, cfg: EcomConfig, deja_vus: dict, log=print) -> list[AnnonceEbay]:
    trouvees: dict[str, AnnonceEbay] = {}
    for mots, vendeur, categorie in sources(cfg):
        nom = " / ".join(x for x in (vendeur and f"vendeur {vendeur}", mots and f"« {mots} »",
                                      categorie and f"catégorie {categorie}") if x)
        try:
            lot = ebay.rechercher(mots=mots, vendeur=vendeur, categorie=categorie,
                                 limite=cfg.annonces_par_recherche,
                                 prix_min=cfg.prix_ebay_min, prix_max=cfg.prix_ebay_max)
        except Exception as e:  # une source en panne ne bloque pas les autres
            log(f"  ! eBay {nom} : {e}")
            continue
        log(f"  eBay {nom} : {len(lot)} annonces")
        for a in lot:
            if not _recent(deja_vus.get(a.item_id), cfg.revoir_apres_jours):
                trouvees.setdefault(a.item_id, a)
    qui_vendent = []
    for a in trouvees.values():
        try:
            a.vendus = ebay.ventes(a.item_id)
        except Exception as e:
            log(f"  ! ventes {a.item_id} : {e}")
            continue
        deja_vus[a.item_id] = {"date": str(date.today()), "vendus": a.vendus}
        if a.vendus >= cfg.ventes_min:
            qui_vendent.append(a)
    qui_vendent.sort(key=lambda a: a.vendus, reverse=True)
    return qui_vendent


def executer(cfg: EcomConfig, ebay: Ebay, ali: AliExpress, shopify: Shopify | None,
             etat: dict, log=print) -> list[Retenu]:
    """shopify=None : simulation, rien n'est créé dans la boutique."""
    vus = etat.setdefault("ebay_vus", {})
    for k in [k for k, v in vus.items() if not _recent(v, max(30, cfg.revoir_apres_jours))]:
        del vus[k]  # l'état reste léger
    log("1/3 Recherche des produits qui se vendent sur eBay…")
    annonces = annonces_qui_vendent(ebay, cfg, vus, log)
    log(f"   {len(annonces)} annonces avec au moins {cfg.ventes_min} ventes")

    log("2/3 Recherche d'un fournisseur AliExpress…")
    importes = etat.setdefault("importes", {})
    retenus: list[Retenu] = []
    for a in annonces:
        if len(retenus) >= cfg.produits_par_jour:
            break
        try:
            candidats = ali.rechercher(requete(a.titre), pays=cfg.pays_livraison,
                                       langue=cfg.langue, devise=cfg.devise)
        except Exception as e:
            log(f"  ! AliExpress « {a.titre[:40]} » : {e}")
            continue
        f = meilleur_fournisseur(a.titre, a.prix, candidats, cfg)
        if f is None or f.product_id in importes or any(r.ali.product_id == f.product_id for r in retenus):
            continue
        prix, marge = prix_de_vente(f.prix + cfg.frais_port_estimes, a.prix, cfg)
        if marge < cfg.marge_min:
            continue
        retenus.append(Retenu(a, f, prix, marge))
    log(f"   {len(retenus)} produits rentables (marge ≥ {cfg.marge_min:.0f} €)")

    log("3/3 Ajout à la boutique Shopify…" if shopify else "3/3 Simulation : rien n'est ajouté à Shopify")
    for r in retenus:
        if shopify is None:
            continue
        tag = f"ali-{r.ali.product_id}"
        try:
            if shopify.existe(tag):
                importes[r.ali.product_id] = {"date": str(date.today()), "shopify": "déjà présent"}
                continue
            fiche = fiche_produit(
                titre=r.ali.titre, prix=r.prix, prix_barre=r.ebay.prix,
                sku=tag, images=[r.ali.image] + r.ali.images,
                tags=[tag, "ecom-bot", f"ebay-{r.ebay.item_id}"], statut=cfg.statut,
                type_produit=cfg.type_produit, collection_id=cfg.collection_id,
            )
            r.shopify_id = shopify.creer(fiche)
            importes[r.ali.product_id] = {
                "date": str(date.today()), "shopify": r.shopify_id, "ebay": r.ebay.item_id,
                "fournisseur": r.ali.url, "cout": r.ali.prix, "prix": r.prix,
            }
            log(f"  + {r.ali.titre[:60]} — {r.prix:.2f} € (marge {r.marge:.2f} €)")
        except Exception as e:
            r.erreur = str(e)
            log(f"  ! Shopify « {r.ali.titre[:40]} » : {e}")
    return retenus


def rapport(retenus: list[Retenu], simulation: bool, cfg: EcomConfig) -> str:
    lignes = [
        f"# Bot e-commerce — {date.today():%d/%m/%Y}",
        "",
        "**Mode simulation** : aucun produit n'a été ajouté." if simulation else
        f"Produits ajoutés à Shopify en statut **{cfg.statut}**"
        + (" (brouillons : vérifiez-les puis passez-les en « Actif »)." if cfg.statut == "DRAFT" else "."),
        "",
        "| Produit | Vendus eBay | Prix eBay | Coût AliExpress | Votre prix | Marge nette | Statut |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in retenus:
        statut = "❌ " + r.erreur[:60] if r.erreur else ("✅ ajouté" if r.shopify_id else "—")
        lignes.append(
            f"| [{r.ali.titre[:60]}]({r.ali.url}) | [{r.ebay.vendus}]({r.ebay.url}) | "
            f"{r.ebay.prix:.2f} | {r.ali.prix:.2f} | {r.prix:.2f} | {r.marge:.2f} | {statut} |"
        )
    if not retenus:
        lignes.append("| Aucun produit rentable trouvé aujourd'hui | | | | | | |")
    lignes += ["", f"Total : {len(retenus)} produit(s), marge cumulée par vente "
               f"{sum(r.marge for r in retenus):.2f} €."]
    return "\n".join(lignes) + "\n"



def ecrire_rapport(texte: str, chemin: Path = RAPPORT) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")


def resume(retenus: list[Retenu]) -> list[dict]:
    return [asdict(r) for r in retenus]
