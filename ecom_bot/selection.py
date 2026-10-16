"""Rapprochement eBay <-> AliExpress et calcul du prix de vente."""
from __future__ import annotations

import math
import re
import unicodedata

from .aliexpress import ProduitAli
from .config import EcomConfig

MOTS_VIDES = {
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "en", "pour", "avec", "sans",
    "au", "aux", "a", "the", "and", "for", "with", "of", "to", "in", "on", "by",
    "neuf", "new", "lot", "pcs", "pc", "piece", "pieces", "livraison", "gratuite", "free",
    "shipping", "rapide", "fast", "france", "stock", "promo", "top", "qualite", "quality",
    "original", "authentique", "garantie", "envoi", "offert", "2024", "2025", "2026",
}


def mots(titre: str) -> list[str]:
    texte = unicodedata.normalize("NFKD", titre.lower()).encode("ascii", "ignore").decode()
    vus, sortie = set(), []
    for m in re.findall(r"[a-z0-9]+", texte):
        if len(m) > 1 and m not in MOTS_VIDES and m not in vus:
            vus.add(m)
            sortie.append(m)
    return sortie


def requete(titre: str, nb: int = 6) -> str:
    """Mots-clés courts pour retrouver le produit chez le fournisseur."""
    return " ".join(mots(titre)[:nb])


def ressemblance(a: str, b: str) -> float:
    ma, mb = set(mots(a)), set(mots(b))
    if not ma or not mb:
        return 0.0
    return len(ma & mb) / len(ma | mb)


def meilleur_fournisseur(titre_ebay: str, prix_ebay: float, candidats: list[ProduitAli],
                         cfg: EcomConfig) -> ProduitAli | None:
    valides = [
        p for p in candidats
        if p.note >= cfg.note_min and p.commandes >= cfg.commandes_min
        and ressemblance(titre_ebay, p.titre) >= cfg.ressemblance_min
        and p.prix + cfg.frais_port_estimes < prix_ebay
    ]
    if not valides:
        return None
    # le plus ressemblant d'abord, puis le moins cher, puis le plus vendu
    return max(valides, key=lambda p: (round(ressemblance(titre_ebay, p.titre), 1),
                                       -p.prix, p.commandes))


def arrondi_99(x: float) -> float:
    return math.ceil(x) - 0.01


def prix_de_vente(cout: float, prix_ebay: float, cfg: EcomConfig) -> tuple[float, float]:
    """Retourne (prix de vente, marge nette)."""
    plafond = prix_ebay * (1 - cfg.sous_prix_ebay)
    prix = min(cout * cfg.coefficient, plafond)
    prix = arrondi_99(prix) if arrondi_99(prix) <= plafond else round(prix, 2)
    frais = prix * cfg.frais_paiement_pct / 100 + cfg.frais_paiement_fixe
    return round(prix, 2), round(prix - cout - frais, 2)
