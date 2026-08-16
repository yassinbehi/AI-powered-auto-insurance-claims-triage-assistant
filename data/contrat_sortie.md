# Contrat de sortie JSON

```json
{
  "claim_id": "CLM-001",
  "triage": "traitement_standard | pieces_manquantes | expertise_requise | suspicion_fraude | hors_garantie",
  "priorite": "basse | normale | haute | critique",
  "garantie_applicable": true,
  "pieces_manquantes": ["..."],
  "signaux_fraude": ["..."],
  "fourchette_reparation_tnd": {"min": 0, "max": 0},
  "prochaine_action": "...",
  "message_client": "...",
  "validation_humaine_requise": true
}
```

Regles:

- `message_client` ne doit pas promettre de paiement.
- `validation_humaine_requise` est toujours `true` pour `suspicion_fraude`, `hors_garantie`, montant estime > 5000 TND, blessure, ou rejet.
- `signaux_fraude` peut etre vide mais doit toujours etre present.

