---
title: "Story 6.10-b : Correctifs reportés de la 6.10"
type: 'feature'
created: '2026-10-13'
status: 'done'
baseline_revision: 'ea5a169'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---
## Intent

**Problem:** Trois constats reportés par la revue de la 6.10 : (1) et (2) le coût majoré d'un appel en échec (`executer_structure`, `executer_agent`) est imputé au plafond mais n'apparaît ni dans les traces ni dans `cout_llm_eur`, et SM-7 ne voit pas ces appels ; (3) le préchauffage redemande à chaque relance une Anomalie qui échoue toujours (échecs non mis en cache, `passage_id` neuf par tranche).

**Approach:** Une `EntreeTrace` d'échec produite par un seul mécanisme de la passerelle (`_tracer_echec`, utilisé par les deux appels), via `en_echec` (contrats 1.8.0, additif). Relances du préchauffage bornées par un compteur d'échecs persistant.

## Boundaries & Constraints

**Always:** la trace d'échec porte la même entrée pseudonymisée qu'un succès, `sortie=""`, jetons et coût majorés (3 requêtes, 2 caractères par jeton, `max_jetons_sortie` ×3), `statut_controle=non_controle`, `en_echec=true`. `cout_llm_eur` = somme des traces, échecs compris. `classification_initiale` ignore les traces d'échec. Aucun appel LLM réel.

**Never:** modifier le comportement de repli des tâches (l'erreur est relancée telle quelle) ; toucher `rendu/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Échec de classification toléré | 1 appel en `UsineErreur` | trace `en_echec` ajoutée à celles de l'étape, coût dans `cout_llm_eur` et au plafond | — |
| Échec de l'Agent | `executer_agent` en `UsineErreur` | coût majoré au plafond, trace `en_echec` envoyée à `sur_trace` | erreur relancée |
| Contrat ancien | trace sans `en_echec` | relue avec `en_echec=false` | — |
| Balayage SM-7 | trace d'échec | balayée comme les autres lignes de `trace/llm.jsonl` | fuite : code 1 |
| Relance du préchauffage | Anomalie en échec `max_echecs` (2) fois aux relances précédentes | sautée sans appel, comptée « abandonnée » ; stock couvert (code 0) si classées + abandonnées = Anomalies | prompt changé : compteurs remis à zéro |

</intent-contract>

## Code Map

- `src/usine/contrats/trace.py` -- `EntreeTrace.en_echec` (optionnel, défaut `false`) ; `CONTRATS_VERSION` 1.8.0 (commit « Feat: contrats 6.10-b »).
- `src/usine/ia/passerelle.py` -- `_tracer_echec` (impute le coût, produit la trace : `sur_trace` pour l'Agent, sinon tampon `vider_traces_echec`).
- `src/usine/ia/classification.py` -- `classer` ajoute les traces d'échec, accepte `ignorer` et `echouees` ; `EtapeClassification.version_prompt`, `prechauffer`.
- `src/usine/composition.py` -- `prechauffer_classification` : compteur `donnees/prechauffage_echecs.json`, `BilanPrechauffage.abandonnees`.
- `outils/prechauffer_cache.py` -- `--max-echecs` (défaut 2), sortie « abandonnée(s) ».
- `src/usine/chaine/execution.py` -- `classification_initiale` ignore `en_echec`.

## Choix de conception

Relances bornées par un petit fichier JSON de compteurs plutôt que par le cache LLM : le cache est un port gelé consulté par clé de réponse, alors que le compteur est propre à l'outil de préchauffage ; il est lié à `version_prompt` (prompt modifié : compteurs remis à zéro) et se réinitialise en supprimant le fichier.

## Tests

`test_classification` (trace d'échec, coût, `ignorer`/`echouees`), `test_passerelle_agent` (plafond et trace de l'Agent), `test_execution` (Passage : trace d'échec et `cout_llm_eur` ; préchauffage : abandon après 2 échecs), `test_balayer_sm7` (trace d'échec balayée), `test_prechauffer_cache`.

## Reports

Aucun. Les échecs d'`executer_structure` d'explication et de narration font échouer le Passage : leur trace n'est pas publiée (hors périmètre).

## Revue

- Medium, corrigé : `classer` avec `tolerer_echecs=False` levait avant `vider_traces_echec()` ; la trace d'échec restait au tampon et fuyait vers un `classer` suivant de la même passerelle. Le tampon est désormais vidé avant la levée (test ajouté).
- Medium, corrigé : `vider_traces_echec()` reprenait aussi les échecs d'autres tâches (narration, explication, qui ne vident pas le tampon). Il filtre maintenant par `tache` ; `classer` passe `Tache.classification`.
- Medium, corrigé : préchauffage, le compteur d'échecs n'était pas écrit quand `classer` levait (échecs consécutifs), ce qui annulait la borne des relances ; écriture dans un `finally`, et atomique (fichier temporaire puis remplacement).
- Rejeté (low) : traces d'échec perdues quand `classer` lève pour trop d'échecs ; le Passage échoue alors, le coût reste au plafond.
- Vérifié, sans défaut : pas de double imputation (coût imputé une fois dans `_tracer_echec`, le succès n'est pas imputé), entrée pseudonymisée (SM-7), Agent via `sur_trace` sans tampon, anciennes traces relues (`en_echec` défaut `false`), compteur illisible ou `version_prompt` changé : remis à zéro, code de sortie.
