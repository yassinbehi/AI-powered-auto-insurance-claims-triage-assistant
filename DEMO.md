# Démonstration guidée — 10 minutes

Parcours à dérouler devant un public. Chaque étape indique **ce qu'on montre**
et **ce qu'il faut dire** — la seconde partie compte autant que la première :
plusieurs écrans se ressemblent, et ce qui les distingue ne se voit pas.

**Coût de la démonstration : environ 0,04 USD.** Deux analyses réelles
seulement — l'étape 4 dans l'interface et l'étape 7 en terminal, à ~0,018 USD
chacune sur Claude Haiku 4.5. Tout le reste du parcours passe par des
endpoints gratuits.

---

## Avant de commencer

```bash
# Terminal 1
.venv/Scripts/python -m uvicorn api:app --app-dir backend/src --port 8000

# Terminal 2
cd frontend && npm run dev
```

Vérifiez que l'API répond avant d'ouvrir le navigateur :

```bash
curl http://127.0.0.1:8000/api/health
# {"status":"ok","model":"claude-haiku-4-5-20251001","api_key_configured":true}
```

**Préparez vos fichiers.** L'application ne contient aucune donnée au départ,
c'est voulu. Il vous faut un CSV de déclarations et un CSV de contrats. Les
colonnes attendues sont rappelées sur l'écran de dépôt, et deux fichiers
d'exemple valides s'y téléchargent en un clic — c'est le moyen le plus sûr de
partir d'un format correct.

> Les identifiants `CLM-001` à `CLM-008` cités plus bas sont ceux du jeu de
> référence du dépôt (`data/claims_auto.csv`). Vous pouvez le déposer tel quel
> pour reproduire exactement ce parcours.

---

## 1. L'écran de dépôt — 1 min

**Montrer :** l'application démarre sur une demande de fichiers, pas sur des
données.

**Dire :** « Il n'y a aucun repli silencieux sur les fichiers du dépôt. Ces
fichiers-là sont les jeux d'essai des évaluations. Si l'application les
affichait faute de mieux, un gestionnaire croirait travailler sur ses dossiers
en regardant des données de test. »

Déposez les deux fichiers, **donnez un nom au jeu** — par exemple
« Démonstration ». Le nom est obligatoire : il permet de revenir sur ce jeu
plus tard et de le distinguer d'un autre, ce que deux fichiers tous deux
appelés `claims.csv` ne permettent pas.

Si des lignes n'ont pas pu être lues, l'écran suivant les nomme, avec leur
numéro de ligne dans le tableur et la raison. Elles ne sont pas supprimées en
silence.

## 2. La file d'attente — 2 min

**Montrer :** la colonne **Urgence**, en premier.

**Dire :** « C'est la seule valeur calculée de ce tableau, au milieu de faits
lus dans le fichier. Elle est produite par `urgence.py`, sans aucun appel de
modèle, donc gratuitement. Ce n'est pas une décision — seulement un ordre de
lecture proposé : par où commencer. »

Montrer la recherche et les filtres : ils vivent dans l'URL. **Copiez le lien
d'une file filtrée** et collez-le dans un nouvel onglet — c'est le même écran.
Cliquez un en-tête de colonne pour trier.

**Dire :** « Filtrer et trier sont des décisions d'affichage, pas des règles
métier. C'est pour cela que ce code peut vivre côté frontend alors que tout
jugement reste en Python. »

## 3. Un dossier, gratuitement — 2 min

Ouvrez **CLM-001**. Rien n'a encore coûté un centime : la fiche dossier
déroule les cinq tools avec `use_classifier=False`, donc sans aucun appel de
modèle.

**Montrer :** la couverture, la fourchette de réparation, les signaux de
fraude — tous déjà calculés.

**Dire :** « Les cinq tools sont déterministes : ce sont des lectures de CSV et
des règles. L'interface peut donc les dérouler sans modèle. Le modèle
n'intervient que pour arbitrer et rédiger. »

Ouvrez ensuite **CLM-002**. Son message client contient une tentative
d'injection.

**Montrer :** le message brut du client est affiché au gestionnaire, avec sa
mention de signalement — et il est **écarté** de ce que reçoit le modèle.

**Dire :** « Le filtre a détecté "approuver le paiement" et "sans vérifier",
et il a rendu son verdict `INJECTION` sans appeler le moindre modèle.
Le texte reste lisible par un humain, parce qu'un gestionnaire doit pouvoir
juger ce que son client a écrit. Mais le modèle, lui, reçoit un texte de
remplacement neutre et instruit le dossier sur les seuls champs structurés.
La détection est ici gratuite : les marqueurs sont attrapés par du code, la
couche [1], sans aucun appel de modèle. »

## 4. Une analyse en direct — 3 min

Revenez sur **CLM-005** (incendie, devis 9 800 TND, blessure déclarée).
Choisissez le modèle si vous voulez montrer le sélecteur, puis lancez
l'analyse.

**Montrer :** l'avancement s'écrit au fil de l'eau — lecture de la
déclaration, vérification du contrat, analyse de la couverture, estimation,
contrôle des anomalies, rédaction.

**Dire :** « C'est du SSE. Les étapes sont formulées en termes de dossier, pas
d'outils : un gestionnaire n'a pas à savoir qu'il existe une fonction
`detect_fraud_signals`. Le détail technique — trace des outils, réponse brute,
tokens — part dans la console du navigateur. Ouvrez-la si vous voulez le
voir. »

**Sur le résultat**, montrer dans cet ordre :

1. **Validation humaine requise** — obligatoire ici : il y a blessure et le
   devis dépasse 5 000 TND.
2. **La prochaine action** et **le message client**, les deux blocs qui portent
   la valeur de l'écran.
3. **Le message client ne promet aucun paiement.** Ce n'est pas une
   recommandation au modèle : `schema.py` refuse une sortie qui promettrait un
   remboursement.

**Dire :** « L'assistant ne valide pas un paiement, ne rejette pas
définitivement, ne modifie pas une police, ne clôture pas un dossier. Ces
quatre interdits sont dans le system prompt, et vérifiés en code sur la sortie
produite. »

Montrez le **compteur de coût cumulé** dans le bandeau : il vient d'augmenter.

## 5. L'historique — 1 min

Onglet **Analyses**.

**Montrer :** l'analyse qu'on vient de lancer, avec le nom de l'assuré, le
dossier, le jeu de données. Ouvrez-la.

**Dire :** « La conclusion se relit avec le même composant que juste après
l'analyse : trois jours plus tard, elle se lit comme le jour où elle a été
produite. Sans cet historique, relire une conclusion de la veille demandait de
la racheter — une analyse coûte un appel de modèle et plusieurs dizaines de
secondes. »

Cherchez par nom d'assuré. Précisez que la recherche porte sur ce que l'écran
montre : taper « fraude » trouve la ligne qui affiche « Suspicion de fraude »,
alors que la donnée vaut `suspicion_fraude`.

## 6. Changer de jeu de données — 1 min

Depuis la file, ouvrez le sélecteur de jeux et basculez sur un autre jeu.

**Dire :** « Les jeux déposés sont conservés dans une base SQLite locale. Un
redémarrage du serveur ne fait plus perdre les fichiers. Et changer de jeu
prend le verrou de triage : impossible de remplacer les dossiers sous une
analyse en cours, qui finirait sur un sinistre absent de l'écran. »

Pour appuyer : arrêtez le backend (Ctrl+C), relancez-le, rafraîchissez la
page. Le jeu revient seul, avec sa date de dépôt d'origine.

## 7. Le terminal — 30 s

```bash
.venv/Scripts/python backend/src/main.py CLM-001 | jq .
```

**Dire :** « La même boucle agentique, sans interface. La sortie standard reste
du JSON pur pour être redirigeable ; le rapport de coût part sur la sortie
d'erreur, avec le détail du filtre anti-injection et la comparaison au budget
plafond de 5 USD. »

---

## Si l'on vous pose ces questions

**« Que se passe-t-il si le modèle renvoie autre chose que du JSON ? »**
L'écran affiche que l'analyse n'a pas abouti et propose de relancer. Le
message technique part dans la console. L'exécution est quand même
enregistrée dans l'historique avec son coût : elle a été facturée.

**« Et si le classifieur anti-injection se trompe ? »**
Tout verdict hors des trois valeurs autorisées est traité comme `SUSPECT`,
jamais comme `SAFE` — la couche [3] échoue du côté sûr. Et le classifieur ne
renvoie jamais de texte libre dans le pipeline, seulement un jeton parmi
trois : une injection qui le viserait ne peut, au pire, que produire un
verdict erroné sur un dossier.

**« Combien ça coûte ? »**
Environ 0,018 USD par analyse sur Haiku 4.5, dont un peu moins de la moitié
économisée par la mise en cache du prompt. Chiffres mesurés et détaillés dans
[`RAPPORT_COUT_SECURITE.md`](RAPPORT_COUT_SECURITE.md).

**« Pourquoi l'assurance ne peut-elle pas décider automatiquement ? »**
Parce que le sujet l'interdit, et parce que c'est juste : `validation_humaine_requise`
est imposé pour la suspicion de fraude, le hors-garantie, un montant supérieur
à 5 000 TND, une blessure, ou tout cas équivalent à un rejet. La règle est
vérifiée en code, pas seulement demandée au modèle.

---

## Composition du jeu de référence

Utile pour choisir quoi montrer, une fois `data/claims_auto.csv` réparé :

| Dossier | Type | Devis | Blessure | Triage attendu | Intérêt en démo |
| --- | --- | ---: | --- | --- | --- |
| CLM-001 | collision | 2 400 | non | `traitement_standard` | le cas nominal |
| CLM-002 | bris de glace | 850 | non | `hors_garantie` | **injection** (« approuver le paiement ») |
| CLM-003 | collision | 6 200 | non | `expertise_requise` | seuil des 5 000 TND |
| CLM-004 | vol | 0 | non | `pieces_manquantes` | pièces obligatoires |
| CLM-005 | incendie | 9 800 | **oui** | `expertise_requise` | blessure → priorité critique |
| CLM-006 | collision | 3 100 | non | `hors_garantie` | **injection** (« ignores l'exclusion ») |
| CLM-007 | vol | 7 200 | non | `suspicion_fraude` | faisceau de signaux |
| CLM-008 | RC tiers | 1 300 | non | `traitement_standard` | type sans pièces obligatoires |
