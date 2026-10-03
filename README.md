# Bot d'investissement long terme

Un bot **basé sur des règles fixes** : il achète et revend selon des seuils
définis à l'avance, sans émotion ni prédiction. Ce n'est pas du trading : il
agit au plus une fois par mois et, la plupart du temps, il ne fait rien.

> ⚠️ Aucun algorithme ne connaît « le bon moment ». Ce bot applique des règles
> éprouvées (investissement programmé, réserve déployée dans les krachs,
> rééquilibrage) qui retirent l'émotion de la décision. Elles ne garantissent
> aucun gain. Commencez en mode papier, et faites un backtest sur de vraies
> données avant d'engager de l'argent réel. Ceci n'est pas un conseil financier.

## Les règles

| Situation | Action du bot |
|---|---|
| Chaque mois | L'apport va aux actifs **sous-pondérés**, donc à ce qui a baissé. |
| Marché au plus haut | 10 % du portefeuille restent en **réserve de cash**. |
| Marché −15 % / −25 % / −35 % | La réserve est **déployée par paliers**, ce qui revient à acheter pendant la peur. |
| Un actif dépasse sa cible de plus de 5 points | Le bot **vend l'excédent**, donc il vend ce qui a monté. |
| Krach, panique | **Aucune vente panique.** Le bot ne vend jamais parce que « ça baisse ». |
| (optionnel) Actif sous sa moyenne 200 jours | Le bot **sort** vers un actif défensif (filtre de tendance). |

Toutes les décisions sont enregistrées avec leur justification dans
`journal/decisions.jsonl`.

## Installation

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml   # puis adaptez l'allocation et l'apport mensuel
```

## Utilisation

```bash
# 1. Tester la stratégie sur l'historique (données Yahoo Finance)
python -m invest_bot backtest --start 2007-01-01 --initial 10000

# 2. Simuler en local (argent fictif)
python -m invest_bot deposit 10000
python -m invest_bot plan          # affiche les ordres sans rien exécuter
python -m invest_bot run           # exécute sur le portefeuille papier

# 3. Compte papier Alpaca (vrais cours, argent fictif)
export ALPACA_API_KEY=... ALPACA_SECRET_KEY=...
python -m invest_bot run --broker alpaca

# 4. Argent réel : trois verrous successifs
export INVEST_BOT_ALLOW_LIVE=1
python -m invest_bot run --broker alpaca --live   # demande de taper "OUI"
```

Le backtest compare la configuration à un investissement programmé simple
(achat-conservation), à un rééquilibrage seul et à la variante avec ou sans
filtre de tendance. Gardez ce qui fonctionne sur **vos** actifs.

### Exécution automatique (1er jour ouvré du mois, 16h heure de New York)

```cron
30 15 1-3 * 1-5  cd /chemin/Bot-claude && INVEST_BOT_ALLOW_LIVE=1 python -m invest_bot run --broker alpaca --live --yes
```

Le bot n'exécute **qu'une fois par mois** (verrou dans `state/last_run.json`),
donc relancer la commande plusieurs jours de suite ne pose pas de problème.

## Garde-fous

- Le mode papier est utilisé par défaut. Le mode réel exige `--live`, la variable `INVEST_BOT_ALLOW_LIVE=1` et une confirmation.
- Le bot s'arrête si une exécution échangerait plus de 50 % du portefeuille (`max_turnover_pct`) ou passerait trop d'ordres. Ce cas signale presque toujours des données ou une configuration erronées.
- Aucun ordre n'est envoyé quand le marché est fermé, et les ordres inférieurs à `min_order_value` sont ignorés.
- Les ventes passent avant les achats. Pour éviter un biais d'anticipation, le backtest exécute chaque décision le jour de bourse suivant.

## Courtier et fiscalité (France)

- Alpaca donne accès aux ETF américains (VTI, VXUS, BND…). Ces ETF ne sont pas éligibles au PEA, et un particulier européen peut souvent ne pas pouvoir acheter d'ETF américains (réglementation PRIIPs/KID). Vérifiez votre accès.
- Pour les ETF UCITS (ex. `CW8.PA`), le backtest fonctionne avec les tickers Yahoo. L'exécution demande un connecteur courtier dédié : il suffit d'implémenter la classe `Broker` dans `invest_bot/brokers.py` (par exemple pour Interactive Brokers).
- Chaque vente peut déclencher de l'impôt sur un CTO. Le filtre de tendance vend plus souvent : intégrez ce coût avant de l'activer.

## Tests

```bash
python -m pytest -q
```

## Structure

```
invest_bot/
  config.py     configuration et validation
  strategy.py   règles de décision (pures, testables)
  backtest.py   simulation historique + comparaison
  brokers.py    PaperBroker (local) et AlpacaBroker
  data.py       cours Yahoo Finance + cache
  cli.py        commandes backtest / plan / run / deposit
```
