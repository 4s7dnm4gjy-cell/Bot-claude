# Bot d'investissement long terme pour Trade Republic

Le bot surveille le marché **tous les jours** et vous propose le
**meilleur moment** pour investir ou vendre, chiffres à l'appui. Vous passez
l'ordre dans l'application Trade Republic, puis vous répondez `oui` ou `non`.
Tout tourne seul sur GitHub : rien à installer, rien à coller.

📊 **[Tableau de bord du jour](rapports/tableau-de-bord.md)** ·
🧪 **[Backtest sur données réelles](rapports/backtest.md)** ·
📬 **[Propositions](../../issues?q=label%3Aproposition)**

## Comment ça marche pour vous

1. **Chaque jour**, le bot poste un point marché sur le ticket « 📅 Bulletin quotidien » : score du moment, ce qu'il y a à faire (ou non), valeur du portefeuille. Vous recevez une notification GitHub (application mobile ou e-mail).
2. Quand c'est le moment d'agir, le bot ouvre un **ticket de proposition** (onglet *Issues*).
3. Le ticket indique quoi acheter ou vendre, en quelle **quantité**, l'**ISIN** à chercher dans Trade Republic, **pourquoi maintenant**, et ce qui s'est passé historiquement dans une situation similaire.
4. Vous passez l'ordre dans l'application et répondez en commentaire :
   - `oui` : c'est fait, le bot l'enregistre dans votre portefeuille ;
   - `non` : le bot ignore la proposition et en refait une 7 jours plus tard.

Autres commandes, à taper en commentaire de n'importe quel ticket :

| Commande | Effet |
|---|---|
| `apport 300` | change l'apport mensuel (200 € par défaut) |
| `capital 2000` | ajoute une somme ponctuelle, investie au meilleur moment |
| `possede EUNL.DE 12` | déclare des parts que vous avez déjà |
| `aide` | affiche l'aide |

Le bot n'obéit qu'au propriétaire du dépôt.

Vous préférez le plan d'épargne gratuit avec seulement des alertes krach et rééquilibrage ? C'est l'autre dépôt : **bot-epargne-trade-republic**.

## Les règles du bot

| Situation | Proposition |
|---|---|
| Score du moment ≥ 60/100 (marché en repli) | 🟢 Investir l'apport du mois maintenant |
| Pas de repli avant le 20 du mois | 🟡 Investir quand même : c'est le meilleur moment *disponible*, car attendre plus coûte en moyenne |
| Marché −15 % / −25 % / −35 % | 🔵 Déployer la réserve de cash gardée pour les krachs |
| Un ETF dépasse sa part cible de plus de 5 points | 🟠 Vendre l'excédent (prise de bénéfices) |
| Krach, panique | Jamais de vente panique |

**Score du moment (0-100).** Il compare la situation du jour à tout l'historique *passé* :
- la baisse depuis le plus haut sur un an ;
- l'écart à la moyenne des 200 derniers jours ;
- le RSI, un indicateur de survente sur 14 jours.

À 100, le marché est parmi les plus « soldés » de son histoire. À 0, il est au plus haut. Chaque proposition affiche les rendements observés ensuite, dans le passé, pour ce niveau de score (sur le S&P 500 depuis 1950 et sur l'ETF lui-même). Ce n'est pas une prédiction.

**Allocation par défaut** (modifiable dans `config.yaml`) :
- 85 % iShares Core MSCI World (`IE00B4L5Y983`) ;
- 15 % iShares Core MSCI Emerging Markets IMI (`IE00BKM4GZ66`).

Les ordres portent sur des parts entières, avec 1 € de frais par ordre (tarif Trade Republic).

## 🔎 Radar d'opportunités

Chaque jour, le bot scanne **environ 2 700 actions et ETF du monde entier** :
- **~220 titres choisis à la main**, avec leur ISIN (`radar_liste.yaml`) ;
- **la composition complète des grands indices**, relue chaque mois automatiquement (`radar_univers.yaml`) :
  - États-Unis : S&P 500, MidCap 400, SmallCap 600 ;
  - Royaume-Uni : FTSE 100 et 250 ;
  - Japon : Nikkei 225 ;
  - Hong Kong : Hang Seng ;
  - Allemagne : DAX, MDAX, TecDAX ;
  - Espagne, Italie, Pays-Bas, Belgique, Portugal, Irlande : IBEX, FTSE MIB, AEX, BEL 20, PSI, ISEQ ;
  - Suède, Danemark, Finlande, Norvège : OMX, OBX ;
  - Canada et Australie : TSX 60, ASX 50.

Les prix étrangers sont convertis en euros pour chiffrer les achats. Pour les titres de l'univers automatique, le ticket indique le nom à chercher dans l'application, pas l'ISIN. Trade Republic ne propose peut-être pas toutes les petites valeurs.

- **Dans le bulletin quotidien :** les 3 titres les plus « soldés » par rapport à leur propre historique, avec ce qui a suivi par le passé à ce niveau de prix. Exemple : « +18 % à 12 mois en moyenne, positif 85 % des cas ».
- **Ticket 🔎 Opportunité :** quand un titre devient très soldé (score ≥ 85) et que l'historique est favorable, le bot ouvre un ticket avec l'achat suggéré (~150 €, ISIN, quantité). Vous répondez `oui` ou `non`, comme pour les autres propositions.

**Garde-fous :**
- les titres en déclin sur 5 ans sont écartés ;
- les titres individuels sont limités à 20 % du portefeuille ;
- un même titre ne fait l'objet que d'une alerte par mois ;
- le bot ne revend jamais ces titres à votre place.

**📰 Lecture des actualités : opportunité ou vraie mauvaise nouvelle ?**
Avant chaque alerte, le bot lit les articles des 30 derniers jours sur le titre (Google Actualités, en français et en anglais). Il y cherche des signaux d'alarme : scandale, fraude, enquête, procès, faillite, avertissement sur résultats… Il compare aussi la baisse du titre à celle du marché.
- 🟢 **Rien d'alarmant** : la baisse ressemble à un mouvement de marché, l'alerte part.
- 🟠 **À vérifier** : l'alerte part, avec les articles inquiétants en lien, à lire avant de répondre `oui`.
- 🔴 **Problème sérieux** : pas d'alerte. Le titre apparaît « ⛔ écarté » dans le bulletin, avec la raison.

C'est une lecture par mots-clés, pas une analyse : elle peut se tromper. Les liens sont là pour que vous jugiez vous-même.

⚠️ Une action seule est bien plus risquée qu'un ETF. Les statistiques sont flatteuses, car la liste ne contient que des entreprises qui ont réussi jusqu'ici. Une forte baisse peut avoir une bonne raison.

## Pourquoi pas d'exécution automatique sur Trade Republic ?

Trade Republic n'a **pas d'API officielle**. Il existe une bibliothèque non officielle (`pytr`), mais elle exige :
- votre numéro de téléphone et votre PIN, stockés sur un serveur ;
- une double authentification qui expire régulièrement ;
- un accès dans une zone grise des conditions d'utilisation.

Une validation manuelle d'un clic est plus sûre. Elle sert aussi de garde-fou : aucun ordre ne part sans vous.

## Automatisations (GitHub Actions)

| Workflow | Quand | Rôle |
|---|---|---|
| `conseil.yml` | tous les jours à 18h45, heure de Paris | analyse, bulletin quotidien, proposition éventuelle (jamais le week-end, bourse fermée) |
| `validation.yml` | à chacun de vos commentaires | enregistre `oui`, `non` et les réglages |
| `backtest.yml` | le 1er de chaque mois, et à la demande | teste la stratégie sur les vrais cours |
| `tests.yml` | à chaque modification du code | tests automatiques |

Pour lancer une analyse ou un backtest tout de suite : onglet **Actions**, choisir le workflow, puis **Run workflow**.

## Avertissement

Aucun algorithme ne connaît l'avenir. Ce bot applique des règles fixes qui
retirent l'émotion de la décision ; il ne garantit aucun gain. Ceci n'est pas
un conseil financier.

## Pour les développeurs

```bash
pip install -r requirements.txt
python -m pytest -q
python -m invest_bot backtest --rapport rapports/backtest.md --stats-ticker
python -m invest_bot conseil      # analyse du jour (affiche la proposition hors GitHub)
```

```
invest_bot/
  score.py      score du moment d'achat + statistiques
  strategy.py   règles de décision (pures, testables)
  conseil.py    propositions, tickets GitHub, commandes oui/non
  backtest.py   simulation quotidienne sans biais d'anticipation
  rapport.py    graphiques et tableaux
  brokers.py    portefeuille papier local, Alpaca (non utilisé pour Trade Republic)
```
