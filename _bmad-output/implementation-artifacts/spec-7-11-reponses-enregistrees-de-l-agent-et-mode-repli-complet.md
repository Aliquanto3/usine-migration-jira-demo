---
title: "Story 7.11 : Réponses enregistrées de l'Agent et Mode repli complet"
type: 'feature'
created: '2026-10-13'
status: 'review'
baseline_revision: 'c9dd263'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: ['enregistrement réel `usine agent --enregistrer` (appel LLM payant, à lancer par Anaël)', 'réenregistrement si la copie du Mode repli passe au Palier 2 (Story 6.10)']
---

<intent-contract>

## Intent

**Problem:** en Mode repli, l'écran Agent affiche seulement un message (7.9) : la démo n'est pas jouable de bout en bout sans réseau (FR-45, NFR-12, AD-24).

**Approach:** `usine agent --enregistrer` pose les questions de la démo à l'Agent sur la copie `demo/repli/passage/` et écrit une `ReponseAgentEnregistree` (`contrats.llm`) par question dans `demo/repli/agent/<rang>.json`, versionnés. En Mode repli, l'écran Agent propose ces questions en choix fermés et rejoue la réponse choisie avec la mention « Mode repli ». Une réponse d'un autre `passage_id` que la copie est refusée avec un message explicite.

## Boundaries & Constraints

**Always:** ne lire que la copie `demo/repli/passage/` (via `Consultation`) et `demo/repli/agent/` en Mode repli ; aucun LLM ni réseau en Mode repli ; aucune saisie libre en Mode repli ; une réponse rejetée par le contrôle n'est jamais enregistrée ; textes en français.

**Never:** modifier `contrats/` ou `ports/` ; importer `evals` depuis `usine` ; lancer un appel LLM réel dans ce run ; repli silencieux vers `sorties/passages/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Enregistrement | `usine agent --enregistrer`, copie présente | 5 fichiers `01.json`…`05.json`, `passage_id` de la copie ; anciens `*.json` remplacés | — |
| Réponse rejetée | une question rejetée par le contrôle | rien n'est écrit | `UsineErreur` nommant la question |
| Copie absente | pas de `demo/repli/passage/manifeste.json` | arrêt | `UsineErreur`, code 1 |
| Rejeu nominal | Mode repli, écran Agent | radio des 5 questions, bouton « Rejouer la réponse », texte, statut, outils, mention « Mode repli : réponse enregistrée le … sur le Passage …, rejouée sans LLM » | — |
| Passage différent | un fichier porte un autre `passage_id` | erreur nommant le fichier et les deux identifiants, aucun choix proposé | `st.error` |
| Aucune réponse | `demo/repli/agent/` vide ou absent | erreur invitant à lancer `usine agent --enregistrer` | `st.error` |

</intent-contract>

## Code Map

- `src/usine/contrats/llm.py:254` -- `ReponseAgentEnregistree` (inchangé).
- `src/usine/ia/agent/cli.py` -- sous-application `usine agent`, jusqu'ici vide.
- `src/usine/ui/app.py:386` -- `afficher_agent`, branche Mode repli à remplacer.
- `src/usine/ui/cli.py` -- services de la page (`consultation_repli`, `session_agent`).
- `evals/agent/` (7.10) -- tours enregistrés des 15 questions, rejoués par la vraie `SessionAgent` sans réseau.

## Tasks & Acceptance

**Execution:**
- `src/usine/ia/agent/repli.py` -- `QUESTIONS_DEMO` (q01, q02, q03, q08, q14 de la suite 7.10), `REPERTOIRE_REPONSES`, `enregistrer_reponses(session, repertoire, horloge)`, `charger_reponses(repertoire, passage_id)`.
- `src/usine/ia/agent/cli.py` -- option `--enregistrer` : session réelle (`composition.construire_session_agent`) sur la copie, écriture dans `demo/repli/agent/`.
- `src/usine/ui/cli.py` -- service `reponses_repli(racine, passage_id)`.
- `src/usine/ui/agent.py`, `src/usine/ui/navigation.py`, `src/usine/ui/app.py` -- libellés, `mention_repli`, clé `CLE_CHOIX_AGENT`, `_afficher_agent_repli` (radio + bouton), `_afficher_reponse` partagé.
- `demo/repli/agent/01.json`…`05.json` -- produits sans appel réel : `enregistrer_reponses` sur une `SessionAgent` dont le fournisseur rejoue les tours de `evals/agent/questions.json` (outils et contrôle réels).
- `tests/unit/ia/agent/test_repli.py`, `tests/unit/ui/test_app_agent.py`, `tests/unit/ui/conftest.py` -- matrice ci-dessus.

**Acceptance Criteria:**
- Given la copie `demo/repli/passage/`, when l'auteur lance `usine agent --enregistrer`, then des `ReponseAgentEnregistree` portant son `passage_id` sont écrites dans `demo/repli/agent/*.json` et versionnées.
- Given le Mode repli actif, when le Pilote ouvre l'écran Agent, then les questions enregistrées sont proposées en choix fermés, sans saisie libre, et la réponse est rejouée avec la mention « Mode repli ».
- Given des réponses dont le `passage_id` diffère de la copie, when l'UI les charge, then elles sont refusées avec un message explicite.

## Design Notes

Passage de repli : `20261012T221158Z-96c621` (Palier 1). Les questions retenues n'exigent pas le Palier 2 (même Passage que la suite 7.10, où elles sont réussies) : pas de régénération. Si la Story 6.10 remplace la copie par un Passage Palier 2, l'UI refusera les réponses actuelles (`passage_id` différent) : il faudra ajouter les tours rejoués de 7.10 sur le nouveau Passage ou lancer `usine agent --enregistrer` en réel.

Les fichiers versionnés sont donc des réponses rejouées et non des réponses d'un vrai modèle (`version_modele` des traces : `enregistre:rejeu`). Coût d'un enregistrement réel : environ 5 questions × 0,03 à 0,06 €, soit 0,15 à 0,30 €.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert
- `USINE_MODE_REPLI=1 uv run usine ui` -- expected: écran Agent jouable sans réseau
