# Backtest sur données réelles

Période : 12/06/2015 → 30/10/2026. Actifs : iShares Core MSCI World  iShares Core MSCI EM IMI. Versement initial 1 000 € puis 200 € par mois. Frais Trade Republic : 1 € par ordre (le plan d'épargne est gratuit).

| Méthode | Valeur finale | Argent versé | Gain | Rendement annuel | Pire baisse | Ordres | Frais |
|---|---:|---:|---:|---:|---:|---:|---:|
| Plan d'épargne le 1er (gratuit) | 60 731 € | 28 200 € | +32 531 € | 10.69% | -33.3% | 205 | 0 € |
| Achat au meilleur moment du mois | 60 240 € | 28 200 € | +32 040 € | 10.46% | -33.3% | 194 | 194 € |
| Bot complet | 57 321 € | 28 200 € | +29 121 € | 9.84% | -31.2% | 171 | 171 € |
| Bot complet + filtre tendance | 41 411 € | 28 200 € | +13 211 € | 4.75% | -20.9% | 176 | 176 € |

![Backtest](backtest.png)

*Rendement annuel* : performance hors apports (pondérée dans le temps). *Pire baisse* : plus forte chute du portefeuille entre un plus haut et un plus bas.

## Le score sur ^GSPC depuis 1950

| Score | Jours | Rendement moyen à 3 mois | à 12 mois | Positif à 12 mois | Pire cas à 12 mois |
|---|---:|---:|---:|---:|---:|
| 0-20 (cher) | 2 696 | +2.0% | +11.1% | 81% | -37.1% |
| 20-40 | 4 230 | +2.4% | +9.1% | 76% | -42.2% |
| 40-60 | 4 365 | +2.6% | +8.7% | 74% | -44.7% |
| 60-80 | 3 995 | +2.2% | +8.3% | 70% | -46.3% |
| 80-100 (soldé) | 3 094 | +1.8% | +10.4% | 71% | -48.8% |
| Tous les jours | 18 380 | +2.2% | +9.3% | 74% | -48.8% |

## Le score sur iShares Core MSCI World

| Score | Jours | Rendement moyen à 3 mois | à 12 mois | Positif à 12 mois | Pire cas à 12 mois |
|---|---:|---:|---:|---:|---:|
| 0-20 (cher) | 646 | +2.3% | +9.1% | 82% | -14.8% |
| 20-40 | 789 | +2.3% | +11.0% | 85% | -18.5% |
| 40-60 | 714 | +2.7% | +12.2% | 86% | -13.1% |
| 60-80 | 749 | +3.9% | +16.4% | 90% | -8.7% |
| 80-100 (soldé) | 494 | +6.0% | +18.0% | 95% | -4.5% |
| Tous les jours | 3 392 | +3.2% | +13.1% | 87% | -18.5% |

Les performances passées ne préjugent pas des performances futures.
