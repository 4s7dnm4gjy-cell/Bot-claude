# Bot e-commerce : eBay → AliExpress → Shopify

Ce bot fait la même chose que les outils du type « Ecom Autopilot » :

1. il **scanne eBay** (des boutiques précises et/ou des mots-clés) et garde les annonces qui ont **déjà au moins 10 ventes** ;
2. il **cherche le même produit sur AliExpress** : bien noté (≥ 90 %), déjà beaucoup commandé, moins cher ;
3. il **calcule votre prix** (coût × 2,5, toujours 5 % sous le prix eBay) et ignore le produit si la marge nette est sous 8 € ;
4. il **ajoute le produit à votre boutique Shopify** (photos et titre du fournisseur), jusqu'à 100 par jour.

Il tourne seul sur GitHub chaque matin vers 7 h. Le résultat du jour : **[rapports/ecom.md](rapports/ecom.md)**.

Par défaut, les produits arrivent en **brouillon** (`DRAFT`) : vous les vérifiez dans Shopify, puis vous les passez en « Actif ». Une fois que vous avez confiance, mettez `statut: ACTIVE` dans `ecom_config.yaml`.

## Pourquoi Shopify et pas eBay

- Le règlement d'eBay **interdit** d'acheter un produit chez un autre marchand (AliExpress, Amazon…) pour qu'il l'expédie directement à votre client. Le compte peut être limité ou suspendu.
- Sur Shopify, c'est votre boutique : vous choisissez vos fournisseurs et vos prix.
- Amazon n'est pas utilisé comme fournisseur : son règlement interdit lui aussi ce type de dropshipping, et son API produits demande un compte affilié qui a déjà des ventes.

## L'abonnement Shopify

Oui, il faut un abonnement pour vendre. Le forfait **Basic** coûte environ **27 € par mois si vous payez à l'année** et **36 € par mois au mois** (tarifs Europe, à vérifier sur shopify.com/fr/tarifs). Shopify propose souvent un essai gratuit, puis 1 € par mois pendant les premiers mois. Il faut aussi compter les frais de paiement (environ 2,9 % + 0,30 € par vente, déjà inclus dans le calcul de marge) et un nom de domaine (environ 15 € par an, facultatif).

Sur eBay, il n'y a pas d'abonnement obligatoire. Des boutiques eBay payantes existent, mais elles ne servent à rien ici puisque le bot ne vend pas sur eBay.

## Mise en route (environ 20 minutes, une seule fois)

Les clés se mettent dans **Settings → Secrets and variables → Actions → New repository secret** de ce dépôt GitHub.

| Secret | Où l'obtenir |
|---|---|
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` | [developer.ebay.com](https://developer.ebay.com) → créer un compte → *Application Keys* → **Production** : *App ID* et *Cert ID*. Gratuit. |
| `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET` | [openservice.aliexpress.com](https://openservice.aliexpress.com) → s'inscrire comme *Affiliate* → créer une app → *App Key* et *App Secret*. Gratuit (validation sous quelques jours). |
| `SHOPIFY_ACCESS_TOKEN` | Admin Shopify → *Paramètres → Applications → Développer des applications* → créer une app → droits Admin API `write_products` et `read_products` → installer → copier le jeton `shpat_…` |
| ou `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET` | si Shopify vous envoie vers le *Dev Dashboard* : créer l'app, accès `write_products, read_products`, l'installer sur la boutique, copier *Client ID* et *Client secret* |

Ensuite :

1. Onglet **Actions** → *Bot e-commerce* → **Run workflow**, case « Simulation » cochée. Le bot cherche et calcule les marges sans rien créer. Lisez `rapports/ecom.md`.
2. Ajustez `ecom_config.yaml` : vos mots-clés, les pseudos des boutiques eBay à espionner, la marge minimum…
3. Relancez avec « Simulation » décochée. Ensuite, le bot tourne seul chaque matin.

## Quand un client commande

Le bot ajoute les produits, mais il **ne passe pas les commandes** chez le fournisseur. Pour ça, installez l'application gratuite **DSers** (partenaire officiel d'AliExpress) dans Shopify. Elle retrouve chaque produit grâce au lien fournisseur noté dans `etat/ecom_importes.json` et commande en un clic.

Pensez aussi aux délais (souvent 7 à 15 jours depuis la Chine), à l'obligation de les afficher, au droit de rétractation de 14 jours en Europe, et aux produits interdits ou contrefaits (marques, électronique sans marquage CE). Vérifiez chaque brouillon avant de le publier.

## En local

```bash
pip install -r requirements.txt
export EBAY_CLIENT_ID=… EBAY_CLIENT_SECRET=… ALIEXPRESS_APP_KEY=… ALIEXPRESS_APP_SECRET=…
python -m ecom_bot --simulation
```
