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
deferred: ['Câblage en étape de la Chaîne (Etape.doublons, llm/doublons.json, Consultation.doublons) : nouveau contrat de Passage, hors de « tâche et contrat de sortie »', 'Configuration d''un modèle dédié à la tâche doublons dans config/llm.yaml (modeles_par_tache)']
---

<intent-contract>

## Intent

**Problem:** Le Pilote n'a aucun moyen de repérer les Anomalies ouvertes probablement en doublon (FR-36) ; le stock ne se nettoie pas.

**Approach:** Ajouter aux contrats (1.9.0, additif, commit dédié) la tâche `doublons`, `ReponseDoublon` (schéma fournisseur) et `SortieDoublon` (paire et score) ; une tâche `ia/doublons.py` (prompt `ia/prompts/doublons.md`) qui retient de façon déterministe les paires candidates puis fait scorer chaque paire par le LLM via la passerelle.

## Boundaries & Constraints

**Always:** passer par `Passerelle.executer_structure` (Pseudonymisation, cache, contrôle, trace) ; Anomalies ouvertes seulement (hors `STATUTS_FERMES`) ; paires d'une même Entité ; paires bornées (`MAX_PAIRES`) ; sortie triée par score décroissant ; prompt en français.

**Never:** fusionner, écrire dans Jira ou dans le Passage ; faire calculer le score de recouvrement au LLM ; modifier `rendu/`, `passerelle.py` ou un contrat existant.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Paires proches | Anomalies ouvertes d'une Entité au recouvrement lexical >= 0,25 | un appel par paire, `SortieDoublon` si score >= 0,5 | — |
| Score faible | score < 0,5 | paire non publiée, trace conservée | — |
| Justification étrangère | phrase citant une autre clé | phrase retirée, `corrige` | — |
| Fermée ou autre Entité | Anomalie fermée / rejetée, ou Entité différente | jamais appariée | — |
| Plafond de coût | `PlafondCoutAtteint` | arrêt, paires déjà scorées publiées | pas d'échec du Passage |
| Échec isolé | `UsineErreur` sur une paire | paire sans score, journalisée | 3 échecs d'affilée : `UsineErreur` |
| Rejeu | mêmes textes et prompt | aucun appel, `depuis_cache` | — |

</intent-contract>

## Code Map

- `src/usine/contrats/llm.py` -- `Tache.doublons`, `ReponseDoublon`, `SortieDoublon` ; `versions.py` → `1.9.0` (1.8.0 prise par la 6.10-b) ; tests de version et `test_inventaire.py`, `test_llm.py`.
- `src/usine/ia/doublons.py` (nouveau) -- `paires_candidates` (Jaccard sur les mots de 3 lettres ou plus du titre et de la description), `detecter(passerelle, textes, ouvertes, date_arrete, contexte, plafond_eur)`, `cles_ouvertes(etats)`, `ContexteDoublons`. Cible de cache : `cle_a+cle_b`.
- `src/usine/ia/prompts/doublons.md` (nouveau) -- consigne : score de 0 à 1, justification courte.
- `tests/unit/ia/test_doublons.py` (nouveau) -- matrice I/O.

## Tasks & Acceptance

**Execution:**
- Contrats 1.9.0 -- commit `Feat: contrats 1.8, détection de doublons`.
- `ia/doublons.py`, prompt, tests -- AC 1.

**Acceptance Criteria:**
- Given les Anomalies ouvertes pseudonymisées, when la détection s'exécute, then elle produit des paires avec un score, à revoir par le Pilote, sans aucune fusion ni écriture dans Jira.
- Given la nouvelle tâche, when elle est ajoutée, then la tâche et son contrat de sortie sont dans un commit de contrats distinct, avant le code de la lane.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports` -- expected: aucun écart
- `uv run pytest -q` -- expected: tout vert

## Auto Run Result

Status: review

**Changement :** tâche `doublons` : paires candidates déterministes (même Entité, recouvrement lexical), score LLM par paire via la passerelle, justification contrôlée, paires >= 0,5 publiées par score décroissant. Aucun accès en écriture.

**Reports :** étape de Chaîne et fichier de Passage (`llm/doublons.json`, `Consultation.doublons`, UI) ; modèle dédié à la tâche dans `config/llm.yaml`. Seuils (0,25 / 0,5 / 50 paires) à calibrer sur un stock réel : le recouvrement lexical peut manquer des doublons reformulés.
