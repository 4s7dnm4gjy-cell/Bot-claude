"""API AliExpress (Open Platform, programme affilié) : trouver un fournisseur.

Clés gratuites sur https://openservice.aliexpress.com (créer une app « Affiliates »).
"""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass, field

import requests

API = "https://api-sg.aliexpress.com/sync"


@dataclass
class ProduitAli:
    product_id: str
    titre: str
    prix: float
    image: str
    images: list[str] = field(default_factory=list)
    commandes: int = 0
    note: float = 0.0
    url: str = ""


def https(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[7:]
    return url


def signer(params: dict, secret: str) -> str:
    texte = "".join(f"{k}{params[k]}" for k in sorted(params))
    return hmac.new(secret.encode(), texte.encode(), hashlib.sha256).hexdigest().upper()


def _nombre(valeur, defaut: float = 0.0) -> float:
    try:
        return float(str(valeur).replace("%", "").replace(",", ".").strip())
    except (TypeError, ValueError):
        return defaut


class AliExpress:
    def __init__(self, app_key: str, app_secret: str, session: requests.Session | None = None):
        self.app_key = app_key
        self.app_secret = app_secret
        self.http = session or requests.Session()

    def rechercher(self, mots: str, pays: str = "BE", langue: str = "FR",
                   devise: str = "EUR", limite: int = 20) -> list[ProduitAli]:
        params = {
            "method": "aliexpress.affiliate.product.query",
            "app_key": self.app_key,
            "timestamp": str(int(time.time() * 1000)),
            "sign_method": "sha256",
            "keywords": mots,
            "ship_to_country": pays,
            "target_language": langue,
            "target_currency": devise,
            "sort": "LAST_VOLUME_DESC",
            "page_size": str(limite),
        }
        params["sign"] = signer(params, self.app_secret)
        r = self.http.post(API, data=params, timeout=30)
        r.raise_for_status()
        reponse = r.json()
        if "error_response" in reponse:
            raise RuntimeError(f"AliExpress : {reponse['error_response'].get('msg')}")
        resultat = (reponse.get("aliexpress_affiliate_product_query_response", {})
                    .get("resp_result", {}).get("result") or {})
        produits = []
        for p in (resultat.get("products") or {}).get("product", []):
            prix = _nombre(p.get("target_sale_price") or p.get("sale_price"))
            if prix <= 0:
                continue
            autres = (p.get("product_small_image_urls") or {}).get("string", [])
            produits.append(ProduitAli(
                product_id=str(p.get("product_id")),
                titre=p.get("product_title", ""),
                prix=prix,
                image=https(p.get("product_main_image_url", "")),
                images=[https(u) for u in autres][:6],
                commandes=int(_nombre(p.get("lastest_volume"))),
                note=_nombre(p.get("evaluate_rate")),
                url=p.get("product_detail_url", ""),
            ))
        return produits
