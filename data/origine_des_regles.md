# Origine des regles appliquees par l'assistant

Ce document distingue ce qui est **exige par les documents du projet** de ce qui a ete
**deduit** pendant l'implementation. Il existe parce que le code ne fait pas la difference :
une constante Python a la meme apparence d'autorite, qu'elle transcrive une phrase du client
ou qu'elle traduise un choix d'implementation. Toute ligne marquee "deduit" est discutable et
peut etre modifiee sans contredire le client.

## Regles documentees (transcrites telles quelles)

| Regle | Source | Ou dans le code |
| --- | --- | --- |
| `rc_simple` ne couvre que la responsabilite civile ; `tiers_plus`, `tous_risques`, `flotte_pro` selon garanties listees | `regles_sinistres.md`, "Couverture" | `tools.check_coverage`, `RC_ONLY_FORMULES` |
| Pieces obligatoires par type (collision, vol, incendie, bris de glace) | `regles_sinistres.md`, "Pieces obligatoires" | `tools.DOCUMENTED_REQUIRED_PIECES` |
| Blessure -> `expertise_requise`, priorite `critique` | `regles_sinistres.md`, "Escalade" | `prompts/system_prompt.md`, section 4 |
| Devis > 5000 TND -> expertise obligatoire | `regles_sinistres.md`, "Escalade" | `config.EXPERTISE_REQUIRED_THRESHOLD_TND` |
| Conducteur non declare/non habilite -> validation humaine | `regles_sinistres.md`, "Escalade" | `tools.DRIVER_USAGE_EXCLUSION_KEYWORDS` |
| Instruction client demandant d'ignorer les regles : contenu non fiable | `regles_sinistres.md`, "Escalade" | `src/guard.py` |
| Actions interdites : payer, rejeter definitivement, modifier une police, cloturer | `regles_sinistres.md`, "Actions interdites" | `prompts/system_prompt.md`, section 2 |
| Les 10 champs de sortie, et `validation_humaine_requise` obligatoire pour fraude / hors garantie / > 5000 TND / blessure | `contrat_sortie.md` | `src/schema.py` |
| `message_client` ne promet aucun paiement | `contrat_sortie.md` | `schema.check_no_payment_promise` |
| Modele Claude Haiku 4.5, plafond 5 USD, cacher les regles sinistres | `budget_tokens.md` | `config.py`, `agent._build_cached_system_blocks` |

## Regles deduites (choix d'implementation, a valider)

| Regle | Pourquoi elle a fallu | Statut |
| --- | --- | --- |
| `rc_tiers` (colonne du CSV) correspond a la garantie `rc` | `claims_auto.csv` utilise `rc_tiers`, `regles_sinistres.md` dit `rc` | deduit, isole dans `tools.TYPE_SINISTRE_TO_GARANTIE` |
| "rejet" = triage `hors_garantie` | `contrat_sortie.md` cite "rejet", qui n'est pas une des 5 valeurs de `triage` | deduit, isole dans `schema.REJET_EQUIVALENT_TRIAGE` |
| "incoherence police" = sinistre hors de la periode `date_debut`/`date_fin` | le terme n'est defini nulle part | deduit, `tools.detect_fraud_signals` |
| Bandes de reparation (leger / modere / important / majeur) | `regles_sinistres.md` ne chiffre qu'un seuil, celui de 5000 TND | deduit, `tools.REPAIR_BANDS` |
| Sinistre "juste apres ouverture de police" = 30 jours | aucun delai documente | deduit, `tools.POLICY_RECENT_DAYS` |
| "montant eleve" (signal de fraude) = le seuil des 5000 TND | aucun seuil propre a ce signal | deduit, reutilise le seul seuil chiffre du document |
| Signal "achat recent suivi d'une perte declaree" | motif present dans CLM-007, absent de la liste des 5 facteurs | **ajout**, `tools.SUSPICIOUS_*_KEYWORDS` |
| Nature `administratif` / `comportemental` d'un signal | aide au jugement, ne figure dans aucun document | deduit, `tools.SIGNAL_NATURE` |
| Un type absent de "Pieces obligatoires" (ex. `rc_tiers`) ne peut pas declencher `pieces_manquantes` | le document ne liste que 4 types | deduit, `tools.NON_BLOCKING_RECOMMENDED_PIECES` |
| Liste de marqueurs d'injection | aucune liste fournie | deduit et non exhaustif, `guard.INJECTION_MARKERS` |
| Liste de formulations valant promesse de paiement | aucune liste fournie | deduit et non exhaustif, `schema.PAYMENT_PROMISE_KEYWORDS` |

## Regles retirees

| Regle | Pourquoi elle a ete retiree |
| --- | --- |
| "Combinaison" de signaux de fraude = au moins 2 signaux | seuil chiffre absent du document ; apprecier une combinaison est un jugement, rendu au modele |
| Une police expiree ne compte pas dans la combinaison de fraude | opinion d'implementation ; remplacee par une information neutre (`nature_des_signaux`) |
| Ordre numerote de priorite entre categories de triage | arbre de decision invente ; remplace par des reperes metier que le modele arbitre |

## Points a trancher avec le client

- **CLM-008 / `rc_tiers`** : `cases_evaluation.jsonl` attend a la fois `traitement_standard`
  et `photos` dans `pieces_manquantes`. Or `rc_tiers` ne figure pas dans "Pieces
  obligatoires" : rien n'oblige a reclamer une piece. Les deux attentes sont difficiles a
  satisfaire ensemble ; il faut decider si `rc_tiers` a des pieces obligatoires.
- **`priorite`** : seul le cas de la blessure est documente (`critique`). Les valeurs
  attendues dans `claims_auto.csv` suggerent aussi "devis > 5000 -> haute" et "vol -> haute",
  mais aucune des deux n'est ecrite dans `regles_sinistres.md`.
- **"declaration tardive"** et **"incoherence de lieu"** : cites comme facteurs de fraude,
  mais aucune colonne de `claims_auto.csv` ne permet de les calculer. Ils sont remontes en
  "non evaluables" plutot qu'ignores en silence.
