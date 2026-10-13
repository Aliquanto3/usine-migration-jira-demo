---
title: 'Story 6.11 : [BONUS] Détection de doublons'
type: 'feature'
created: '2026-10-13'
status: 'review'
baseline_revision: '962ff54'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Le stock d'Anomalies ouvertes contient des doublons que le Pilote ne voit pas (FR-36, bonus). Aucune tâche LLM ne les cherche, et aucun contrat ne porte une paire avec un score.

**Approach:** Ajouter aux contrats (1.9.0, additif, commit dédié) la tâche `doublons`, son schéma fournisseur `ReponseDoublons` et sa sortie `SortieDoublons` (une paire, un score de 0 à 100). Puis `ia/doublons.py` : présélection locale déterministe des paires proches (Jaccard sur les mots du titre et de la description des Anomalies ouvertes, bornée à `MAX_PAIRES`), un appel LLM par paire par la passerelle, contrôle déterministe de la justification, publication des paires de score au moins `SEUIL_SCORE`. Aucune fusion, aucune écriture dans Jira.

## Boundaries & Constraints

**Always:** passer par `Passerelle.executer_structure` (Pseudonymisation, cache, contrôle, trace) ; ne comparer que des Anomalies ouvertes ; borner le coût (`MAX_PAIRES`, plafond du Passage) ; une paire range ses clés dans l'ordre de `rang_cle` ; prompt en français, données entre délimiteurs.

**Never:** fusionner ou écrire dans Jira ; modifier `ports/`, `passerelle.py`, `rendu/` ; changement non additif des contrats ; câbler une étape de la Chaîne (voir Design Notes).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Paire probable | deux Anomalies ouvertes proches, score ≥ 70 | `SortieDoublons(cle_a < cle_b, score)` publiée, une trace | — |
| Paire douteuse | score < 70 | non publiée, trace gardée | — |
| Aucune paire proche | similarité < 0,3 partout | aucun appel, `((), ())` | — |
| Anomalie fermée, Cas de test | hors `ouvertes` ou non Anomalie | jamais dans une paire | — |
| Justification fautive | cite une autre clé de ticket | phrase retirée, `corrige` | — |
| Rejeu | mêmes textes, même Date d'arrêté | zéro appel, mêmes sorties, `depuis_cache` | — |
| Plafond de coût | `PlafondCoutAtteint` | paires restantes non demandées, journal | pas d'échec |
| Échec isolé | `UsineErreur` sur une paire | paire sans score, trace d'échec, journal | — |
| Échecs d'affilée | 3 `UsineErreur` consécutives | `UsineErreur` nommant la tâche | échoue |

</intent-contract>

## Code Map

- `src/usine/contrats/llm.py` -- `Tache.doublons`, `ReponseDoublons(score, justification)`, `SortieDoublons(cle_a, cle_b, score, justification, statut_controle)` ; `versions.py` → `1.9.0` ; tests `tests/unit/contrats/test_{llm,inventaire,passage,evenements,versions}.py`.
- `src/usine/ia/doublons.py` (nouveau) -- `mots`, `similarite`, `preselectionner`, `detecter_doublons`, `ContexteDoublons`, `lire_prompt`.
- `src/usine/ia/prompts/doublons.md` (nouveau) -- score de 0 à 100, justification, jetons recopiés.
- `tests/unit/ia/test_doublons.py` (nouveau) -- matrice I/O.

## Tasks & Acceptance

**Execution:**
- Contrats : tâche, schéma, sortie, version 1.9.0 (commit `Feat: contrats 1.8, détection de doublons`).
- `ia/doublons.py`, `ia/prompts/doublons.md`, `tests/unit/ia/test_doublons.py` (commit `Feat: Story 6.11, …`).

**Acceptance Criteria:**
- Given les Anomalies ouvertes pseudonymisées, when la détection s'exécute, then elle produit des paires avec un score, à revoir par le Pilote, sans fusion ni écriture dans Jira (aucun port d'écriture n'est utilisé ; seule la passerelle est appelée).
- Given la nouvelle tâche, when la PR de contrats est faite, then la tâche et son contrat de sortie sont ajoutés par un commit dédié avant le code de la lane.

## Design Notes

- Le LLM ne reçoit que des paires présélectionnées localement : un appel par paire, pas de n² appels. `SEUIL_PRESELECTION = 0,3`, `MAX_PAIRES = 50`, `SEUIL_SCORE = 70` sont des constantes du module, à calibrer sur le corpus.
- Cible de cache `CLE_A|CLE_B` : la clé de cache d'une tâche autre que la classification contient la Date d'arrêté, donc un Passage d'un autre jour relance les appels (non modifié : `passerelle.py` hors périmètre).
- Contrats 1.9.0 et non 1.8 : la 1.8.0 est déjà prise par la 6.10-b ; le message du commit garde l'intitulé demandé.

## Reports

- Étape `doublons` de la Chaîne, fichier de sortie du Passage (`llm/doublons.json`), lecture par `Consultation` et écran de revue du Pilote : demandent `Etape`, `contrats/passage.py` et le port `Consultation` (gelés), à traiter par une PR de contrats dédiée.
- Clé de cache sans Date d'arrêté pour les paires (comme la classification), et réglage des seuils dans `config/` plutôt qu'en constantes.
- Suite d'évaluation de la détection (vérité terrain de doublons absente du générateur).

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports` -- expected: aucun écart
- `uv run pytest -q` -- expected: tout vert
