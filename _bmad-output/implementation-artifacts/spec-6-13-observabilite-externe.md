---
title: "Story 6.13 : [BONUS] Observabilité externe"
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
## Intent

**Problem:** L'auteur veut analyser latences et coûts des appels LLM dans un outil dédié (FR-38), sans affaiblir la règle « aucun identifiant sensible ne part vers un tiers » (NFR-5, SM-7).

**Approach:** La passerelle transmet chaque `EntreeTrace` à un observateur facultatif, en plus du Journal. L'adaptateur Langfuse (4.17.0, auto-hébergé) l'envoie comme une génération. Désactivé par défaut. Aucun contrat ni port modifié.

## Boundaries & Constraints

**Always:** l'observateur ne reçoit que la trace : entrée pseudonymisée, sortie avant ré-identification, métadonnées (versions, `passage_id`, jetons, coût). Un échec de l'observateur ou de Langfuse est journalisé (type d'exception, jamais le contenu) et ignoré. Le client réel n'est construit que si `USINE_LANGFUSE=true`.

**Never:** envoyer un texte ré-identifié ; faire échouer ou ralentir un Passage quand Langfuse est absent ; appel réseau en test.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Appel réussi, envoi actif | `EntreeTrace` LLM | une génération Langfuse (`input`, `output`, `model`, `usage_details`, `cost_details`, `metadata`), puis `flush` | — |
| Trace d'échec, d'outil d'Agent | `en_echec` ou `cible=<outil>` | envoyée comme les autres | — |
| Trace de Prévision | `type_trace=prevision` | ignorée | — |
| Langfuse en panne | client lève | appel LLM inchangé, avertissement sans contenu | exception avalée |
| Envoi activé sans hôte ou clé | `USINE_LANGFUSE=true` | `UsineErreur` nommant les variables manquantes | avant tout Passage |
| Paquet absent | groupe `bonus` non installé | `UsineErreur` « uv sync --group bonus » | — |
| Balayage SM-7 | données envoyées au client simulé | aucune fuite, jetons de Pseudonymisation comptés | fuite : détectée (témoin positif) |

## Code Map

- `src/usine/adaptateurs/observabilite/langfuse.py` -- `ObservateurLangfuse`, `construire_observateur` (import de `langfuse` à la demande).
- `src/usine/ia/passerelle.py` -- paramètre `observateur`, `_observer` appelé à chaque trace (succès, échec, outils, réponse d'Agent).
- `src/usine/config/secrets.py` -- `USINE_LANGFUSE` (défaut `false`), `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`.
- `src/usine/composition.py` -- `_observateur_langfuse`, branché sur la passerelle des Passages.
- `pyproject.toml`, `tests/depot/test_import_linter.py` -- `langfuse` permis à la couche `adaptateurs`.

## Tests

`tests/unit/adaptateurs/observabilite/test_langfuse.py` : envoi, balayage SM-7 (`outils.balayer_sm7.balayer`) sur les données du client simulé, témoin de fuite, panne, configuration.

## Reports

- Le balayage SM-7 s'applique aux données envoyées par un client simulé ; le CLI `outils/balayer_sm7.py` ne balaie pas encore un export Langfuse réel (aucun serveur disponible ici).
- Les appels du client `langfuse.Langfuse` (`start_observation`, `flush`) suivent la documentation 4.x sans avoir été exécutés contre un serveur ni contre le paquet installé (groupe `bonus` absent de l'environnement).
- Les passerelles d'évaluation (`_passerelle_evaluation`) n'envoient rien à Langfuse.
- Un `flush` par trace : simple et sans perte à la fermeture, à regrouper si la latence gêne.
