"""Lecture de ecom_config.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "ecom_config.yaml"


@dataclass
class EcomConfig:
    # eBay : où chercher les produits qui se vendent
    marketplace: str = "EBAY_FR"
    vendeurs: list[str] = field(default_factory=list)
    mots_cles: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)  # n° de catégories eBay
    revoir_apres_jours: int = 7  # une annonce déjà analysée est revue après ce délai
    annonces_par_recherche: int = 50
    ventes_min: int = 10
    prix_ebay_min: float = 10.0
    prix_ebay_max: float = 150.0
    # AliExpress : comment choisir le fournisseur
    pays_livraison: str = "BE"
    langue: str = "FR"
    devise: str = "EUR"
    note_min: float = 90.0          # % d'avis positifs
    commandes_min: int = 50         # ventes du fournisseur sur 30 jours
    ressemblance_min: float = 0.25  # 0-1, mots en commun entre titres
    frais_port_estimes: float = 0.0
    # Prix de vente sur Shopify
    coefficient: float = 2.5        # prix = coût x coefficient...
    sous_prix_ebay: float = 0.05    # ...plafonné à 5 % sous le prix eBay
    marge_min: float = 8.0          # € de marge nette minimum, sinon on n'importe pas
    frais_paiement_pct: float = 2.9
    frais_paiement_fixe: float = 0.30
    # Shopify
    produits_par_jour: int = 100
    statut: str = "DRAFT"           # DRAFT = brouillon à valider, ACTIVE = en vente direct
    type_produit: str = ""
    collection_id: str = ""

    @classmethod
    def charger(cls, chemin: Path = FICHIER) -> "EcomConfig":
        if not chemin.exists():
            return cls()
        brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
        plat = {}
        for section in brut.values():
            if isinstance(section, dict):
                plat.update(section)
        connus = set(cls.__dataclass_fields__)
        inconnus = set(plat) - connus
        if inconnus:
            raise ValueError(f"Réglages inconnus dans {chemin.name} : {', '.join(sorted(inconnus))}")
        cfg = cls(**plat)
        if cfg.statut not in ("DRAFT", "ACTIVE"):
            raise ValueError("shopify.statut doit valoir DRAFT ou ACTIVE")
        return cfg
