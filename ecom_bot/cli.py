"""python -m ecom_bot [--simulation]"""
from __future__ import annotations

import argparse
import os
import sys

from .aliexpress import AliExpress
from .config import EcomConfig
from .ebay import Ebay
from .pipeline import charger_etat, ecrire_rapport, executer, rapport, sauver_etat
from .shopify import Shopify


def _requis(*noms: str) -> list[str]:
    return [n for n in noms if not os.environ.get(n)]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ecom_bot", description=__doc__)
    p.add_argument("--simulation", action="store_true",
                   help="cherche et calcule les marges sans rien créer dans Shopify")
    args = p.parse_args(argv)
    cfg = EcomConfig.charger()

    manquants = _requis("EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET",
                        "ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET")
    if manquants:
        print("Secrets manquants : " + ", ".join(manquants) + " (voir ECOM.md)")
        return 1
    ebay = Ebay(os.environ["EBAY_CLIENT_ID"], os.environ["EBAY_CLIENT_SECRET"], cfg.marketplace)
    ali = AliExpress(os.environ["ALIEXPRESS_APP_KEY"], os.environ["ALIEXPRESS_APP_SECRET"])

    shopify = None
    simulation = args.simulation
    if not simulation:
        boutique = os.environ.get("SHOPIFY_STORE", "")
        jeton = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
        cid, secret = os.environ.get("SHOPIFY_CLIENT_ID", ""), os.environ.get("SHOPIFY_CLIENT_SECRET", "")
        if boutique and (jeton or (cid and secret)):
            shopify = Shopify(boutique, jeton=jeton, client_id=cid, client_secret=secret)
        else:
            print("Shopify non configuré (SHOPIFY_STORE + SHOPIFY_ACCESS_TOKEN) : simulation.")
            simulation = True

    etat = charger_etat()
    retenus = executer(cfg, ebay, ali, shopify, etat)
    if not simulation:
        sauver_etat(etat)
    texte = rapport(retenus, simulation, cfg)
    ecrire_rapport(texte)
    print(texte)
    erreurs = [r for r in retenus if r.erreur]
    return 1 if erreurs and len(erreurs) == len(retenus) else 0


if __name__ == "__main__":
    sys.exit(main())
