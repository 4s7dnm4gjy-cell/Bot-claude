"""Shopify Admin GraphQL API : créer les produits dans la boutique.

Deux façons de s'authentifier :
- SHOPIFY_ACCESS_TOKEN (jeton « shpat_… » d'une app personnalisée) ;
- SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET (app du Dev Dashboard installée
  sur la boutique) : le bot demande lui-même un jeton valable 24 h.
"""
from __future__ import annotations

import html

import requests

VERSION = "2025-10"

PRODUCT_SET = """
mutation productSet($input: ProductSetInput!) {
  productSet(input: $input, synchronous: true) {
    product { id handle }
    userErrors { field message }
  }
}
"""

PAR_TAG = """
query parTag($q: String!) {
  products(first: 1, query: $q) { nodes { id } }
}
"""


class Shopify:
    def __init__(self, boutique: str, jeton: str = "", client_id: str = "", client_secret: str = "",
                 session: requests.Session | None = None):
        self.boutique = boutique.replace("https://", "").strip("/")
        if not self.boutique.endswith(".myshopify.com"):
            self.boutique += ".myshopify.com"
        self.http = session or requests.Session()
        self._jeton = jeton
        self.client_id, self.client_secret = client_id, client_secret

    def _token(self) -> str:
        if not self._jeton:
            r = self.http.post(
                f"https://{self.boutique}/admin/oauth/access_token",
                data={"grant_type": "client_credentials", "client_id": self.client_id,
                      "client_secret": self.client_secret},
                timeout=30,
            )
            r.raise_for_status()
            self._jeton = r.json()["access_token"]
        return self._jeton

    def graphql(self, requete: str, variables: dict) -> dict:
        r = self.http.post(
            f"https://{self.boutique}/admin/api/{VERSION}/graphql.json",
            json={"query": requete, "variables": variables},
            headers={"X-Shopify-Access-Token": self._token()},
            timeout=60,
        )
        r.raise_for_status()
        donnees = r.json()
        if donnees.get("errors"):
            raise RuntimeError(f"Shopify : {donnees['errors']}")
        return donnees["data"]

    def existe(self, tag: str) -> bool:
        noeuds = self.graphql(PAR_TAG, {"q": f"tag:'{tag}'"})["products"]["nodes"]
        return bool(noeuds)

    def creer(self, produit: dict) -> str:
        res = self.graphql(PRODUCT_SET, {"input": produit})["productSet"]
        if res["userErrors"]:
            raise RuntimeError("; ".join(e["message"] for e in res["userErrors"]))
        return res["product"]["id"]


def fiche_produit(titre: str, prix: float, prix_barre: float, sku: str, images: list[str],
                  tags: list[str], statut: str, type_produit: str = "",
                  collection_id: str = "") -> dict:
    """Fiche Shopify (ProductSetInput). Texte et photos viennent du fournisseur, jamais de l'annonce eBay."""
    description = f"<p>{html.escape(titre)}</p>"
    entree = {
        "title": titre[:255],
        "descriptionHtml": description,
        "status": statut,
        "tags": tags,
        "productOptions": [{"name": "Title", "values": [{"name": "Default Title"}]}],
        "variants": [{
            "optionValues": [{"optionName": "Title", "name": "Default Title"}],
            "price": f"{prix:.2f}",
            "compareAtPrice": f"{prix_barre:.2f}" if prix_barre > prix else None,
            "sku": sku,
            "inventoryPolicy": "CONTINUE",  # dropshipping : pas de stock local
        }],
        "files": [{"originalSource": u, "contentType": "IMAGE", "alt": titre[:120]}
                  for u in dict.fromkeys(i for i in images if i.startswith("https://"))][:8],
    }
    if entree["variants"][0]["compareAtPrice"] is None:
        del entree["variants"][0]["compareAtPrice"]
    if type_produit:
        entree["productType"] = type_produit
    if collection_id:
        entree["collections"] = [collection_id]
    return entree
