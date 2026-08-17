# Projet 2 - Assurance: Assistant de triage des sinistres auto

Client fictif: Neopolis Development pour une compagnie d'assurance IARD.

## Objectif

Construire une application qui trie les declarations de sinistre auto, detecte les dossiers incomplets ou suspects, recommande la prochaine action et prepare une reponse client structuree. L'assistant ne doit jamais valider un paiement automatiquement.

## Travail estime: 30 heures

| Phase | Duree | Resultat attendu |
| --- | ---: | --- |
| Cadrage sinistre et donnees | 3 h | Cartographie des tables et regles metier. |
| Prompt et JSON contract | 4 h | Sortie structuree validee par schema. |
| Tools metier | 6 h | Tools `get_policy`, `get_claim`, `check_coverage`, `estimate_repair_band`, `detect_fraud_signals`. |
| Workflow agentique | 5 h | Triage, demande de pieces, escalade expert si necessaire. |
| Streaming et retry | 3 h | Streaming reponse client et gestion d'erreurs garage/API. |
| Evals et tracing | 6 h | Eval suite, traces par etape, seuils mesurables. |
| Packaging final | 3 h | README, demo, rapport cout/securite. |

## Fonctionnalites minimales

- Charger une police depuis `data/policies_auto.csv`.
- Charger une declaration depuis `data/claims_auto.csv`.
- Appliquer `data/regles_sinistres.md`.
- Produire une decision de triage: `traitement_standard`, `pieces_manquantes`, `expertise_requise`, `suspicion_fraude`, `hors_garantie`.
- Generer une reponse client courte, non juridique, avec pieces attendues.
- Bloquer toute action irreversible: indemnisation, rejet definitif, cloture.

## Competences Claude a appliquer

- System prompt avec separation forte entre regles internes et declaration client.
- Tool descriptions avec conditions d'usage et exclusions.
- Structured output JSON.
- Agent loop avec tool_result correctement rattache au tool_use.
- Gestion erreurs: service garage indisponible, statut 429 simule, piece jointe illisible.
- Evals code-gradees et judge optionnel pour la qualite de la reponse client.
- Securite: prompt injection dans declaration, limitation des actions, validation humaine.

## Resultats mesurables

- 95% JSON parseable.
- 85% de bons statuts de triage sur les cas d'eval.
- 90% des pieces manquantes attendues retrouvees.
- 100% des cas d'indemnisation/rejet definitif marques comme validation humaine obligatoire.
- Cout total inferieur a 5 USD.

