---
title: "Story 6.11 : [BONUS] Détection de doublons"
type: 'feature'
created: '2026-10-13'
status: 'review'
baseline_revision: '38201b9'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---
## Intent

**Problem:** Le Pilote ne voit pas quelles Anomalies ouvertes décrivent le même problème (FR-36) ; il nettoie le stock à l'aveugle.

**Approach:** Tâche locale `doublons` : textes des Anomalies ouvertes pseudonymisés (aperçu), similarité de Jaccard sur les jetons, paires au-dessus d'un seuil. Contrats 1.9 en premier commit dédié (`Tache.doublons`, `PaireDoublon`, `SortieDoublons`), code ensuite.

## Boundaries & Constraints

**Always:** textes passés par `Pseudonymiseur.apercu` avant comparaison ; seules les Anomalies ouvertes entrent ; paires triées par score décroissant (`cle_a` précède `cle_b` par rang) ; aucun appel LLM.

**Never:** fusion, fermeture ou écriture dans Jira ; écriture dans le Passage ou dans la table de correspondance ; fichier de Passage nouveau.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Deux Anomalies au texte proche | score ≥ seuil (0,6) | une `PaireDoublon` avec son score | — |
| Cas de test, Certification, ticket fermé | hors `ouvertes` ou non Anomalie | ignorés | — |
| Textes vides | jetons vides | score 0, aucune paire | — |
| Plus de paires que `limite` (50) | — | les `limite` meilleures | — |
| Seuil hors [0, 1], limite ≤ 0 | — | — | `UsineErreur` |
| Clé `USINE_CLE_PSEUDO` absente | commande CLI | — | `UsineErreur` nommant la variable |

</intent-contract>

## Code Map

- `src/usine/contrats/llm.py` -- `Tache.doublons`, `PaireDoublon`, `SortieDoublons` ; `CONTRATS_VERSION` 1.9.0 (commit « Feat: contrats 1.8, détection de doublons » ; 1.8.0 était déjà prise par `en_echec` de la 6.10-b). Spine : liste des tâches d'AD-12 et amendement.
- `src/usine/ia/doublons.py` -- `detecter_doublons` (pure, pseudonymiseur injecté), `score_similarite`.
- `src/usine/composition.py` -- `doublons_passage` (consultation du Passage, aperçu de pseudonymisation).
- `src/usine/ia/cli.py` -- `usine ia doublons REPERTOIRE [--seuil] [--limite]`.

## Choix de conception

Similarité lexicale locale plutôt qu'appel LLM ou plongements : zéro coût et zéro fuite, résultat déterministe et rejouable ; la tâche reste dans la liste d'AD-12 mais n'emprunte pas la passerelle (ni cache, ni trace LLM). Pas de `Reponse<Tache>`, faute de schéma demandé au fournisseur.

## Tests

`tests/unit/ia/test_doublons.py` (score, tri, seuil, limite, filtrage, pseudonymisation, paramètres, composition sans écriture, CLI) ; contrats : `test_llm`, `test_inventaire`, versions réalignées.

## Reports

- Affichage des paires dans l'UI (onglet Anomalies) et publication en fichier de Passage (`doublons.json`) : hors périmètre, nécessitent un contrat de Passage.
- Similarité sémantique (plongements ou LLM) pour les doublons reformulés : à évaluer si le Jaccard lexical manque trop de paires.
