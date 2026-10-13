---
title: 'Story 6.11 : [BONUS] Détection de doublons'
type: 'feature'
created: '2026-10-13'
status: 'review'
baseline_revision: '962ff5453a900b4a4180082493318d46fde9e167'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred:
  - 'Étape de la Chaîne : `Etape.doublons`, fichier de Passage, lecture `Consultation.doublons()` et affichage (Excel, UI) exigent un nouveau contrat et un changement de port (PR dédiée sur `main`), hors périmètre de la story.'
  - 'Cache incrémental inter-jours : la Date d''arrêté entre dans la clé de cache de la tâche (AD-12), donc une paire inchangée est redemandée à chaque nouvelle Date d''arrêté (au plus `MAX_PAIRES` appels). Une clé sans date, comme la classification, toucherait `ia/passerelle.py`.'
  - 'Pré-filtre en O(n²) par Entité : suffisant au volume cible, un index inversé des mots serait à prévoir au-delà de quelques milliers d''Anomalies par Entité.'
---

<intent-contract>

## Intent

**Problem:** Le stock d'Anomalies contient des doublons que le Pilote ne voit pas (FR-36). Aucune tâche LLM ne les cherche et aucun contrat ne porte leur résultat.

**Approach:** Une tâche `doublons` (contrats 1.9.0, commit dédié « Feat: contrats 1.8, détection de doublons » : `Tache.doublons`, `ReponseDoublon`, `SortieDoublon`). Un pré-filtre déterministe local (indice de Jaccard des mots, par Entité, au plus 50 paires) borne le coût ; chaque paire retenue passe par la passerelle (Pseudonymisation, cache, contrôle, trace) et reçoit un score de 0 à 1. La commande `usine ia doublons --passage <répertoire>` écrit les paires de score ≥ 0,5 dans `sorties/doublons/<passage_id>.json` et la trace dans `.trace.jsonl`.

## Boundaries & Constraints

**Always:** appel par `Passerelle.executer_structure` ; lecture par le port `Consultation` (`manifeste`, `anomalies`, `textes_tickets`) ; textes entre délimiteurs dans le prompt ; seules les Anomalies ouvertes sont comparées, jamais entre Entités ; `version_prompt` calculée sur les octets du gabarit envoyé.

**Never:** fusionner ou supprimer une Anomalie ; écrire dans Jira ; modifier `ports/`, `ia/passerelle.py`, `rendu/` ; changement non additif des contrats ; appel LLM réel dans les tests.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Paire proche | deux Anomalies ouvertes, même Entité, Jaccard ≥ 0,3 | un appel ; `SortieDoublon` si score ≥ 0,5, `conforme` | — |
| Score faible | score < 0,5 | paire absente de la sortie, trace conservée | — |
| Justification hors paire | clé d'un troisième ticket citée | phrase retirée, `corrige` | — |
| Anomalie fermée, Cas de test, Certification | hors `ouvertes` ou non Anomalie | jamais comparée | — |
| Entités différentes | mêmes textes, Entités distinctes | aucune paire | — |
| Trop de paires | plus de 50 candidates | les 50 plus proches, départage par clés | — |
| Rejeu | mêmes textes, même Date d'arrêté | zéro appel, `depuis_cache` | — |
| Plafond de coût | `PlafondCoutAtteint` | détection arrêtée, paires déjà scorées publiées | warning journalisé |
| Échec isolé | `UsineErreur` du fournisseur | paire sans score, trace `en_echec` | warning journalisé |
| 3 échecs d'affilée | fournisseur injoignable | `UsineErreur` « doublons : 3 échecs consécutifs… » | la commande échoue |
| Données sensibles | numéro de compte dans un texte | jeton dans le prompt et la trace, valeur restituée en sortie | — |

</intent-contract>

## Code Map

- `src/usine/contrats/llm.py` -- `Tache.doublons`, `ReponseDoublon(score, justification)`, `SortieDoublon(cle_a, cle_b, score, justification, statut_controle)` ; `versions.py` → `1.9.0` (1.8.0 déjà prise par la 6.10-b) ; spine : amendement et liste des tâches d'AD-12.
- `src/usine/ia/doublons.py`, `src/usine/ia/prompts/doublons.md` -- `mots`, `similarite`, `candidats`, `detecter_doublons`, `DetecteurDoublons` ; réutilise `anomalies` (classification), `rendre_prompt` et `_donnee` (explication), `retirer_citations_hors`.
- `src/usine/composition.py` -- `Doublons`, `construire_doublons` (passerelle de `_passerelle_evaluation`, cache en mémoire).
- `src/usine/ia/cli.py` -- commande `usine ia doublons --passage`.
- `tests/unit/ia/test_doublons.py`, `tests/unit/contrats/*` -- matrice I/O, contrats, versions.

## Tasks & Acceptance

**Execution:**
- Contrats 1.9.0 et tests -- commit `Feat: contrats 1.8, détection de doublons`.
- `ia/doublons.py`, prompt, composition, commande, tests -- commit `Feat: Story 6.11, …`.

**Acceptance Criteria:**
- Given les Anomalies ouvertes pseudonymisées, when la détection s'exécute, then elle produit des paires avec un score, à revoir par le Pilote (`sorties/doublons/<passage_id>.json`), sans aucune fusion ni écriture dans Jira.
- Given la nouvelle tâche et son contrat de sortie, then ils sont ajoutés par un commit dédié de `contrats/` (liste des tâches d'AD-12) avant le code de la lane.

## Design Notes

L'étape n'entre pas dans la Chaîne : `Etape`, `FICHIERS_PASSAGE` et le port `Consultation` sont gelés et une nouvelle étape serait un changement de contrat plus large que la story. La commande lit donc un Passage publié et écrit hors Passage, comme l'Agent (`sorties/agent/`). Le score est une probabilité de jugement, bornée par le schéma (0 à 1) : le LLM ne calcule aucun chiffre du Rapport.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports` -- expected: aucun écart
- `uv run pytest -q` -- expected: tout vert

## Auto Run Result

Status: review

**Changement :** tâche `doublons` bonus, pré-filtre local et score par la passerelle, commande `usine ia doublons`.

**Risques résiduels :** voir `deferred`. Le seuil de similarité (0,3) et le score minimal (0,5) sont des valeurs de départ, à régler sur un stock réel.
