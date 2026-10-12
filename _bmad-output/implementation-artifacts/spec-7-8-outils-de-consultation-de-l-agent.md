---
title: 'Story 7.8 : Outils de consultation de l''Agent'
type: 'feature'
created: '2026-10-13'
status: 'done'
baseline_revision: '28dee5784c9b71cca415ca4ad6599f469530d3a0'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred:
  - summary: >-
      get_tendance n'a pas de limite : sans filtre, tous les points de Tendance partent vers le fournisseur.
    evidence: |-
      ArgumentsGetTendance (contrats 1.7) n'a ni limite ni total ; sur le Programme complet, la liste peut atteindre plusieurs centaines de points. À borner en 7.9 (passerelle ou contrat 1.x additif).
    location: >-
      src/usine/ia/agent/outils.py (get_tendance)
    severity: medium
---

<intent-contract>

## Intent

**Problem:** l'Agent (Story 7.9) n'a encore aucun outil : `ia/agent` ne contient que la sous-application Typer vide. Sans outils servis par `Consultation`, il ne peut répondre à partir des chiffres d'un Passage, pour une Date d'arrêté donnée (FR-39, FR-41).

**Approach:** créer `ia/agent/outils.py`, qui expose exactement cinq outils en lecture seule (`get_meteo`, `list_anomalies`, `get_tendance`, `get_prevision`, `get_risques`). Chacun prend un `Arguments*` de `contrats.agent`, rend un `Resultat*` lu par `Consultation`, ou `AucuneDonnee` si la date n'est pas couverte. Les contrats passent en 1.7.0 par un ajout additif, dans un commit dédié : filtre `statut` de `ArgumentsListAnomalies` et résultat `AucuneDonnee`.

## Boundaries & Constraints

**Always:** lecture par le seul port `Consultation` (AD-11) ; `ia/agent` n'importe que `contrats`, `ports` et `consultation` (import-linter) ; aucun chiffre calculé hors `Consultation` (le filtre `statut` ne fait que sélectionner des lignes, `total` compte les Anomalies filtrées avant la limite) ; textes en français ; tests sans LLM ni Jira.

**Never:** outil d'écriture (Jira, mail, configuration), accès à `SourceTickets` ou à `url_ticket`, import de `pydantic_ai` ; enveloppe passerelle, Pseudonymisation, trace ou conversation (Story 7.9) ; modification de `ports/consultation.py`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Date absente | `date_arrete=None` | Date d'arrêté du manifeste, résultat rempli | — |
| Date disponible | date ∈ `dates_disponibles()` | `Resultat*` à cette date | — |
| Date sans Passage | date ∉ `dates_disponibles()` (ou aucune date) | `AucuneDonnee(date_arrete=date, message="aucune donnée pour cette date")` | pas d'exception |
| Filtre statut | `statut=en_cours`, `limite=2` | seules les Anomalies de ce statut, au plus 2 ; `total` = nombre filtré | — |
| Arguments JSON | dict d'arguments invalides | `ValidationError` Pydantic remontée par `executer` | à la passerelle (7.9) |

</intent-contract>

## Code Map

- `src/usine/contrats/agent.py` -- `ArgumentsListAnomalies` (domaine mais pas statut) ; ajouter `statut: StatutAnomalie | None = None` et `class AucuneDonnee` (date_arrete, message fixe).
- `src/usine/contrats/versions.py:9` -- `CONTRATS_VERSION` → `1.7.0` ; tests de version : `tests/unit/contrats/test_{evenements,llm,passage,versions}.py` ; inventaire `tests/unit/contrats/test_inventaire.py:90` (ajouter `AucuneDonnee`).
- `src/usine/ports/consultation.py` -- lecture seule : `dates_disponibles`, `manifeste`, `meteo`, `evolution_meteo`, `anomalies(limite=None)`, `tendances` (DataFrame `_COLONNES_MESURE` = champs de `PointTendance`), `previsions`, `risques`.
- `src/usine/consultation/passage.py:386` -- `anomalies` trie par clé et compte avant limite ; réutilisé avec `limite=None` quand `statut` est filtré.
- `src/usine/contrats/llm.py:140` -- `OutilAgent` (nom, description, arguments, executer → str) : forme cible de 7.9, que la passerelle construira à partir de nos définitions.
- `tests/contrat/consultation/fabriques.py` -- `passage_palier_2()` : Passage réel avec Prévisions et Risques pour un test d'intégration.
- `pyproject.toml:195` -- contrat import-linter `ia` (adaptateurs, httpx déjà interdits).

## Tasks & Acceptance

**Execution:**
- `src/usine/contrats/agent.py`, `versions.py` + tests de version et d'inventaire -- ajout additif 1.7.0 -- commit dédié `Feat: contrats 1.7, …`.
- `src/usine/ia/agent/outils.py` -- `@dataclass(frozen=True) DefinitionOutil(nom, description, arguments: type[Enregistrement], executer: Callable[[Mapping[str, Any]], Enregistrement])` ; `class OutilsConsultation(consultation)` avec les 5 méthodes typées ; `outils_consultation(consultation) -> tuple[DefinitionOutil, ...]` ; constante `NOMS_OUTILS`.
- `pyproject.toml` -- contrat import-linter « ia.agent : lecture seule » interdisant `usine.ports.source_tickets`, `usine.ports.entrepot`, `usine.ports.etape`, `usine.ports.fournisseur_llm`, `usine.ports.cache_llm` à `usine.ia.agent` (hors `cli`).
- `tests/unit/ia/agent/test_outils.py` -- matrice I/O sur une Consultation factice, lecture seule (noms exacts, aucun verbe d'écriture, modules importés), intégration sur `passage_palier_2()`.

**Acceptance Criteria:**
- Given `ia/agent`, when on liste ses outils, then les noms sont exactement les cinq attendus et chaque `arguments`/résultat est une classe de `contrats.agent`.
- Given l'inventaire des outils et le graphe d'imports de `usine.ia.agent`, when le test de lecture seule s'exécute, then aucun outil n'écrit et aucun module de `ia.agent` n'importe un port ou un adaptateur Jira.
- Given une Date d'arrêté sans Passage, when chacun des outils datés est appelé, then il rend `AucuneDonnee` « aucune donnée pour cette date ».

## Spec Change Log

## Review Triage Log

### 2026-10-13 — Review pass
- Couches lancées : Edge Case Hunter seul (mode économique) ; Blind Hunter, Verification Gap et Intent Alignment ignorés.
- verdicts: 7 findings — high 0, medium 1, low 5, false 1, maybe-false 0
- findings:
  - `[low]` `[reject]` `manifeste()` lève si `date_arrete` absente et manifeste manquant — l'Agent ne lit que des Passages publiés (manifeste toujours présent) ; garde supplémentaire inutile en usage courant.
  - `[low]` `[patch]` docstring de `AucuneDonnee.date_arrete` contredite quand une date est demandée sur un Passage sans dates — docstring corrigée (« date demandée, sinon `None` »).
  - `[low]` `[patch]` `executer` ne documente pas la `UsineErreur` de la Consultation — docstring de `DefinitionOutil.executer` complétée.
  - `[false]` `[reject]` fuite de la cause racine Palier 2 dans un Agent Palier 1 — un Passage Palier 1 n'a pas de `classification.json`, `classification()` rend `()` ; l'Agent n'a pas de mode Palier 1 (FR-46 concerne l'UI).
  - `[medium]` `[defer]` `get_tendance` sans borne — contrat sans `limite` ; reporté à 7.9 (voir `deferred`).
  - `[low]` `[reject]` imports relatifs non résolus par le test AST — le dépôt n'utilise que des imports absolus et le contrat import-linter « ia.agent : lecture seule » couvre aussi les imports relatifs.
  - `[low]` `[patch]` `glob` non récursif dans le test de lecture seule — remplacé par `rglob`.

## Design Notes

`get_tendance` n'a pas de date (contrat) : il ne rend jamais `AucuneDonnee`, mais une liste de points éventuellement vide. Les arguments JSON sont validés par `Arguments*.model_validate`. La sérialisation en texte et la Pseudonymisation reviennent à la passerelle (7.9).

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert

## Auto Run Result

Status: done

- **Changement** : `ia/agent/outils.py` expose les cinq outils en lecture seule (`get_meteo`, `list_anomalies`, `get_tendance`, `get_prevision`, `get_risques`). Ils sont servis par `Consultation` et rendent `AucuneDonnee` (« aucune donnée pour cette date ») hors des dates du Passage. Contrats 1.7.0 additifs : `ArgumentsListAnomalies.statut` et `AucuneDonnee`.
- **Fichiers** :
  - `src/usine/contrats/agent.py` et `versions.py` : contrats 1.7.0.
  - Tests de version : `tests/unit/contrats/test_{evenements,llm,passage,versions}.py`, ainsi que les motifs de `tests/unit/adaptateurs/journal/test_source_journal.py` et de `tests/unit/consultation/test_passage.py`.
  - `tests/unit/contrats/test_inventaire.py` : ajout de `AucuneDonnee`.
  - `src/usine/ia/agent/outils.py` : les outils.
  - `pyproject.toml` : contrat import-linter « ia.agent : lecture seule ».
  - `tests/depot/test_import_linter.py` : exclut ce contrat des tests de couches.
  - `tests/unit/ia/agent/test_outils.py` : inventaire, matrice I/O, lecture seule et intégration sur `passage_palier_2()`.
- **Revue** : 3 patchs low, 1 report medium (`get_tendance` sans borne), 3 rejets (voir le journal de triage).
- **Suivi recommandé** : non, aucun constat high ou medium n'a été patché. 0 high, 0 medium et 3 low patchés.
- **Vérification** :
  - ruff, format, mypy et lint-imports sont verts ; pytest donne 2658 passés et 1 ignoré.
  - Après les patchs, `tests/unit/ia/agent` et `tests/unit/contrats` donnent 497 passés.
- **Écart** : la matrice cite `statut=en_cours`, qui n'existe pas dans `StatutAnomalie` ; les tests utilisent `en_analyse`.
- **Risques résiduels** :
  - La Consultation factice simule le manifeste par `cast`.
  - L'enveloppe passerelle (Pseudonymisation, trace, `OutilAgent`) reste à faire en 7.9.

