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
deferred: ['Câblage dans la Chaîne : Etape, fichier llm/doublons.json, méthode du port Consultation, vue UI', 'Passage à l''échelle du préfiltre au-delà de quelques centaines d''Anomalies par Entité']
---

<intent-contract>

## Intent

**Problem:** Le stock d'Anomalies ouvertes contient des doublons que le Pilote doit nettoyer à la main, sans aide (FR-36). La tâche LLM `doublons` et son contrat de sortie n'existent pas.

**Approach:** Ajouter aux contrats (1.9.0, additif, commit dédié) `Tache.doublons`, `ReponseDoublons`, `PaireDoublonBrute` et `SortieDoublon` ; une tâche `ia/doublons.py` (prompt `ia/prompts/doublons.md`) qui, par Entité, présélectionne de façon déterministe les paires d'Anomalies ouvertes aux textes proches, les fait scorer par le LLM via la passerelle et publie les paires contrôlées. Aucune fusion, aucune écriture dans Jira.

## Boundaries & Constraints

**Always:** passer par `Passerelle.executer_structure` (Pseudonymisation, cache, contrôle, trace) ; un appel par Entité ayant au moins une paire candidate ; textes de tickets entre délimiteurs (`_donnee`) ; `version_prompt` calculée sur les octets du gabarit ; sortie triée par Entité puis score décroissant ; prompt en français.

**Never:** fusionner, clore ou écrire quoi que ce soit dans Jira ; modifier `ports/`, `rendu/`, `ia/passerelle.py`, `ia/controles.py` ; faire calculer le score par autre chose que le LLM ; changement non additif des contrats.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Doublon probable | deux Anomalies aux textes proches, score 0,9 | `SortieDoublon(cle_a < cle_b, score 0,9, conforme)` | — |
| Paire inversée, répétée, inconnue ou non candidate | réponse du fournisseur | écartée, statut `corrige` | — |
| Score hors de 0 à 1 ou NaN | réponse du fournisseur | paire écartée, `corrige` | — |
| Score sous 0,5 | réponse du fournisseur | paire non publiée | — |
| Anomalie non ouverte | clé absente de `ouvertes` | non comparée | — |
| Cas de test, Certification | `type_ticket` autre | ignorés | — |
| Aucune paire candidate | textes éloignés | aucun appel, sortie vide | — |
| Plafond de coût | `PlafondCoutAtteint` | Entité sans paire, avertissement, pas d'échec | — |

</intent-contract>

## Code Map

- `src/usine/contrats/llm.py` -- `Tache.doublons`, `PaireDoublonBrute`, `ReponseDoublons`, `SortieDoublon` ; `versions.py` → `1.9.0` ; tests de version et `test_inventaire.py`. Amendement consigné au spine.
- `src/usine/ia/doublons.py` (nouveau) -- `paires_candidates` (Jaccard des mots ≥ 0,25, 15 paires par Entité au plus), `_Controleur`, `detecter_doublons(passerelle, textes, date_arrete, contexte, version_grille, ouvertes)`.
- `src/usine/ia/prompts/doublons.md` (nouveau) -- consigne, bloc de paires, rappel « proposer seulement ».
- `tests/unit/ia/test_doublons.py` -- matrice I/O.

## Tasks & Acceptance

**Execution:**
- `contrats/llm.py`, `versions.py`, tests de version -- tâche et contrat de sortie, 1.9.0 (commit `Feat: contrats 1.8, détection de doublons`, intitulé imposé par la lane).
- `ia/doublons.py`, `ia/prompts/doublons.md`, `tests/unit/ia/test_doublons.py` -- AC 1.

**Acceptance Criteria:**
- Given des Anomalies ouvertes pseudonymisées, when la détection s'exécute, then elle produit des paires `SortieDoublon` avec un score de 0 à 1, à revoir par le Pilote, sans fusion ni écriture dans Jira (le module n'importe aucun port d'écriture).
- Given une réponse du fournisseur hors des paires candidates, when le contrôle s'applique, then ces paires sont écartées et le statut est `corrige`.

## Spec Change Log

- 2026-10-13 : les contrats portent la version 1.9.0 (1.8.0 déjà pris par la Story 6.10-b) ; le commit garde l'intitulé « contrats 1.8 » demandé.

## Design Notes

Le préfiltre lexical borne le coût (un appel par Entité, 15 paires au plus) et rend la liste des candidates vérifiable : le LLM ne peut pas inventer une paire. Le score vient du seul LLM ; le seuil de publication (0,5) est une constante du module.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports` -- expected: aucun écart
- `uv run pytest -q` -- expected: tout vert

## Reports

- Câblage dans la Chaîne (`Etape`, `llm/doublons.json`, `CONTENUS_JSON`, méthode `doublons()` du port `Consultation`, onglet UI) : hors périmètre de cette story (ports et `Etape` gelés), à planifier avec une PR dédiée.
- Préfiltre en O(n²) par Entité : suffisant pour quelques centaines d'Anomalies par Entité, à remplacer par un index inversé au-delà.
