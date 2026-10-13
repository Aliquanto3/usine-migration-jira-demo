---
title: "Story 6.10 : Recette Palier 2"
type: 'feature'
created: '2026-10-13'
status: 'in-progress'
baseline_revision: '38d1faf858e561cf1b70f736eb791daf8be5493b'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Le Sponsor doit juger la couche LLM sur pièces : un vrai Passage Palier 2 (classification, répartition, explications, narration) en moins de 10 minutes, pour moins de 1 €, sans fuite d'identifiant (SM-7), rejouable sans appel. Report de la 6.9 : un `UnexpectedModelBehavior` de Haiku sur une seule Anomalie fait échouer toute la classification, donc le Passage.

**Approach:** Rendre `classer` tolérant aux échecs isolés du fournisseur. Ajouter deux outils de recette : `outils/prechauffer_cache.py`, qui fait la première classification du stock hors Passage par tranches bornées dans le temps (le « cache de classification initialisé » de l'AC), et `outils/balayer_sm7.py` (balayage SM-7 des traces et du cache). Exécuter ensuite la recette réelle dans une racine isolée, avec le Journal du Corpus définitif. La même classification du stock fournit la source « générateur » de SM-9 (6.9), rejouée par `--reponses`.

## Boundaries & Constraints

**Always:** une Anomalie dont l'appel échoue (`UsineErreur`, hors plafond) reste sans suggestion et est consignée au journal. `MAX_ECHECS_CONSECUTIFS` (3) échecs d'affilée font échouer l'étape en nommant la tâche (panne franche). La suite d'évaluation garde un `classer` strict (`tolerer_echecs=False`) : sa propre tolérance, Anomalie par Anomalie, reste inchangée. Le préchauffage passe par la composition (même passerelle, même Pseudonymisation, même part de plafond qu'un Passage), tient le verrou du Passage et n'exige que le Palier 2. Budget réel : Anthropic ≤ 1 € et Mistral ≤ 1 € pour toute la story, plafond du Passage de recette à 0,50 €. Appels réels lancés uniquement depuis le dépôt principal (`uv run --env-file .env`).

**Never:** écrire dans Jira ; toucher `rendu/`, `ia/agent`, `contrats/` ; modifier `config/chaine.yaml` versionné (le Palier 2 de recette vit dans la racine isolée `sorties/recette-6-10/`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Échec isolé | 1 appel en `UsineErreur` parmi N | N−1 sorties, avertissement nommant la clé, Passage poursuivi | — |
| Échecs non consécutifs | échecs séparés par un succès | compteur remis à zéro | — |
| Panne franche | 3 échecs d'affilée | — | `UsineErreur` « classification : 3 échecs consécutifs… » |
| Suite d'évaluation | `tolerer_echecs=False` | — | premier échec propagé |
| Préchauffage borné | durée max atteinte | Anomalies restantes non classées, code 3 | — |
| Préchauffage en Palier 1 | `palier: 1` | — | `UsineErreur` « exige le palier 2 », code 2 |
| Balayage conforme | traces et cache pseudonymisés | 0 fuite, jetons comptés, code 0 | — |
| Fuite | valeur injectée (ou IBAN compacté) | fuite nommant la source et le type, code 1 | fichier illisible : code 2 |

</intent-contract>

## Code Map

- `src/usine/ia/classification.py` -- `classer` : tolérance (`MAX_ECHECS_CONSECUTIFS`, `tolerer_echecs`), arrêt (`arreter`) ; `EtapeClassification.prechauffer`.
- `src/usine/composition.py` -- `Classificateur.__call__` (strict), `BilanPrechauffage`, `prechauffer_classification` (textes du Journal par `domaine.instantanes.tickets_textes`).
- `src/usine/adaptateurs/llm/registre.py` -- tarifs Sonnet 5.5 (2/10 $) et Opus 5.5 (4/20 $) relevés le 13/10/2026 (point d'Anaël).
- `outils/prechauffer_cache.py`, `outils/balayer_sm7.py` -- outils de recette ; `outils/verifier_rejeu.py` (existant) pour le rejeu.
- `evals/classification/` -- SM-9 : `--reel --source manuels`, puis `--source generateur --reponses`.

## Tasks & Acceptance

**Execution:**
- `src/usine/ia/classification.py`, `src/usine/composition.py` -- tolérance, mode strict de l'évaluation, préchauffage.
- `outils/prechauffer_cache.py`, `outils/balayer_sm7.py` -- outils CLI (codes 0/1/2/3).
- `tests/unit/ia/test_classification.py`, `tests/unit/chaine/test_execution.py`, `tests/unit/outils/test_balayer_sm7.py`, `tests/unit/outils/test_prechauffer_cache.py` -- matrice I/O.
- Recette réelle (racine `sorties/recette-6-10/`, ignorée par git) : Journal du Corpus définitif (`usine donnees generer --date-generation 2026-10-12`), préchauffage par tranches, Passage Palier 2 chronométré, rejeu, `verifier_rejeu`, `balayer_sm7`, SM-9 ; résultats consignés ci-dessous et au journal.

**Acceptance Criteria:**
- Given le Journal généré, au plus 4 Entités rouges ou oranges et un cache de classification initialisé, when `usine rapport` s'exécute en Palier 2, then le Passage est produit en moins de 10 minutes pour un `cout_llm_eur` inférieur à 1 €.
- Given les traces du Passage et le cache LLM, when `balayer_sm7` recherche les identifiants injectés, then il n'en trouve aucun.
- Given le même Passage rejoué, when il s'exécute, then aucun appel frais n'est émis et `verifier_rejeu` est conforme.

## Spec Change Log

## Review Triage Log

## Design Notes

Coût mesuré sur les 30 tickets manuels (Haiku 5.5) : 0,0075 €, soit ~0,25 m€ par Anomalie. Le README de la 6.9 l'estimait à ~0,11 m€ : prompt réel plus long. Le stock de 3 114 Anomalies coûte donc ~0,77 € et dure ~95 min (≈ 1,8 s par appel). D'où une seule classification du stock, partagée : elle initialise le cache de la recette et donne les propositions de SM-9 « générateur ». Le prompt, le modèle et les textes (`tickets_textes` à la date de génération) sont ceux de la suite. Le préchauffage hors Passage évite de payer à chaque tranche les explications, dont l'entrée change avec la répartition.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert.
