"""eBay Browse API (officielle) : trouver les annonces qui se vendent.

Clés gratuites sur https://developer.ebay.com (Application Keys, environnement Production).
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

import requests

API = "https://api.ebay.com"


@dataclass
class AnnonceEbay:
    item_id: str
    titre: str
    prix: float
    devise: str
    vendeur: str
    url: str
    vendus: int = 0


class Ebay:
    def __init__(self, client_id: str, client_secret: str, marketplace: str = "EBAY_FR",
                 session: requests.Session | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.marketplace = marketplace
        self.http = session or requests.Session()
        self._jeton: str | None = None

    def _token(self) -> str:
        if self._jeton is None:
            auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            r = self.http.post(
                f"{API}/identity/v1/oauth2/token",
                headers={"Authorization": f"Basic {auth}",
                         "Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials",
                      "scope": "https://api.ebay.com/oauth/api_scope"},
                timeout=30,
            )
            r.raise_for_status()
            self._jeton = r.json()["access_token"]
        return self._jeton

    def _get(self, chemin: str, params: dict | None = None) -> dict:
        r = self.http.get(
            f"{API}{chemin}", params=params, timeout=30,
            headers={"Authorization": f"Bearer {self._token()}",
                     "X-EBAY-C-MARKETPLACE-ID": self.marketplace},
        )
        r.raise_for_status()
        return r.json()

    def rechercher(self, mots: str = "", vendeur: str = "", categorie: str = "", limite: int = 50,
                   prix_min: float = 0, prix_max: float = 0) -> list[AnnonceEbay]:
        filtres = ["buyingOptions:{FIXED_PRICE}", "conditions:{NEW}"]
        if vendeur:
            filtres.append(f"sellers:{{{vendeur}}}")
        if prix_max:
            filtres.append(f"price:[{prix_min}..{prix_max}]")
        params = {"limit": min(limite, 200), "filter": ",".join(filtres)}
        if mots:
            params["q"] = mots
        if categorie:
            params["category_ids"] = categorie
        if not (mots or categorie):
            raise ValueError("eBay exige un mot-clé ou une catégorie")
        donnees = self._get("/buy/browse/v1/item_summary/search", params)
        annonces = []
        for it in donnees.get("itemSummaries", []):
            prix = it.get("price") or {}
            if "value" not in prix:
                continue
            annonces.append(AnnonceEbay(
                item_id=it["itemId"],
                titre=it.get("title", ""),
                prix=float(prix["value"]),
                devise=prix.get("currency", ""),
                vendeur=(it.get("seller") or {}).get("username", ""),
                url=it.get("itemWebUrl", ""),
            ))
        return annonces

    def ventes(self, item_id: str) -> int:
        """Nombre d'exemplaires déjà vendus (estimatedSoldQuantity)."""
        donnees = self._get(f"/buy/browse/v1/item/{item_id}")
        return sum(int(d.get("estimatedSoldQuantity") or 0)
                   for d in donnees.get("estimatedAvailabilities", []))
