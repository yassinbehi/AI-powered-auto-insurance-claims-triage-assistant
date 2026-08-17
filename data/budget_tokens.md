# Budget tokens - Assurance

Modele par defaut: Claude Haiku 4.5.

## Budget recommande

| Usage | Nombre | Tokens input moyens | Tokens output moyens | Cout estime Haiku |
| --- | ---: | ---: | ---: | ---: |
| Construction prompts | 50 | 1 400 | 300 | 0.15 USD |
| Tests tools et erreurs | 70 | 1 700 | 280 | 0.22 USD |
| Evals automatisees | 10 x 24 cas | 1 250 | 260 | 0.61 USD |
| Judge qualite message client | 50 | 900 | 120 | 0.08 USD |
| Demo finale | 20 | 2 000 | 450 | 0.09 USD |

Budget plafond: 5 USD. Budget cible: 1.50 a 2.75 USD.

Optimisations attendues:

- Cacher les regles sinistres.
- Utiliser des evals code-gradees avant le judge.
- Ne pas envoyer l'historique complet de tous les sinistres dans chaque appel.
- Utiliser batch pour evals completes non urgentes.

