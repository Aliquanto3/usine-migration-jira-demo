---
title: 'Story 7.9 : Agent conversationnel aux chiffres contrôlés'
type: 'feature'
created: '2026-10-13'
status: 'done'
baseline_revision: '8fee01f71a600d3f1d61568a4ed7119b4a17eab8'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: ['oversized']
deferred:
  - summary: >-
      Une exception pendant la conversation (outil, fournisseur, plafond) fait perdre les traces des outils déjà exécutés.
    evidence: |-
      `Passerelle.executer_agent` n'expose ses traces d'outils qu'au retour ; `SessionAgent.repondre` ne les écrit qu'après. Une `UsineErreur` de la Consultation ou une erreur du fournisseur après des appels d'outils laisse le JSONL sans ces lignes. Corriger demande une nouvelle surface (traces partielles sur exception) : à traiter avec 7.10 ou 7.11.
    location: >-
      src/usine/ia/passerelle.py (executer_agent), src/usine/ia/agent/session.py (repondre)
    severity: medium
---

<intent-contract>

## Intent

**Problem:** les cinq outils de l'Agent existent (7.8), mais aucune conversation ne les relie au fournisseur. `Passerelle` n'a pas d'`executer_agent`, l'écran Agent est un emplacement et `get_tendance` peut envoyer tous les points au fournisseur (report de 7.8).

**Approach:** ajouter `Passerelle.executer_agent` (ordre AD-12) qui enveloppe chaque outil en `OutilAgent` pseudonymisé et tracé. Ajouter `ia/agent/session.py` : une session pose une question, borne `get_tendance` à la sérialisation, contrôle nombres et tickets contre les résultats d'outils, et écrit ses traces dans `sorties/agent/<AAAA-MM-JJ>/<session>.jsonl`. Câbler l'écran Agent de l'UI.

## Boundaries & Constraints

**Always:** ordre Pseudonymisation → cache → fournisseur → contrôle → ré-identification → trace ; seuls des textes pseudonymisés atteignent le fournisseur, le cache et les traces ; `executer_agent` du port avec `output_type=str` ; nombres contrôlés par `controler_nombres` (6.7) ; valeurs et tickets autorisés = ceux des messages `outil` de la conversation ; réponses et messages en français ; tests avec `FournisseurFactice` sans LLM ni Jira réel.

**Never:** modifier `contrats/` ou `ports/` (borne de `get_tendance` côté `ia/agent`, sans contrat 1.8) ; écrire dans un Passage ; outil d'écriture ; `pydantic_ai` hors `adaptateurs/llm/` ; réponses enregistrées et Mode repli de l'Agent (Story 7.11) ; suite d'évaluation (7.10).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Question de la démo | script : `get_risques` puis texte citant C, l'indicateur et des tickets retournés, chiffres présents dans les résultats | `ReponseAgent` `conforme`, `outils_appeles=("get_risques", …)` | — |
| Chiffre inventé | texte contenant « 42 » absent des résultats | `statut_controle=rejete`, texte = message explicite nommant « 42 » | pas d'exception |
| Ticket non retourné | texte citant `MIG-999` non présent dans les résultats | rejet, message explicite | — |
| Sans réponse | aucun outil, texte « Les données ne permettent pas de répondre. » | `conforme` | — |
| Arguments invalides | le modèle appelle un outil avec des arguments faux | l'outil rend « erreur : arguments invalides pour <outil> » au modèle | `ValidationError` captée |
| Tendance volumineuse | `get_tendance` sans filtre, plus de `LIMITE_POINTS_TENDANCE` (60) points | les 60 plus récents, plus `points_omis` | — |
| Traces | session terminée | une ligne `EntreeTrace` par outil exécuté et par réponse dans `sorties/agent/<date>/<session>.jsonl`, textes pseudonymisés | — |
| Cache | même question rejouée | réponse servie du cache, `depuis_cache=True`, sans appel au fournisseur | — |

</intent-contract>

## Code Map

- `src/usine/ia/passerelle.py` -- `Passerelle.executer_structure` (l. 200-308) : modèle à suivre ; factoriser la vérification du plafond (`_verifier_plafond`) ; `cle_cache`, `jetons_de`, `_reidentifier` réutilisables. Ajouter `OutilSource` (outil non enveloppé : `executer → str` brut), `ResultatAgent` (sortie, statut, traces) et `executer_agent(messages, outils, parametres, contexte, controler)`. Le cache stocke `ReponseAgentBrute.model_dump_json()` dans `EnveloppeCache.brut`.
- `src/usine/contrats/llm.py` -- `MessageAgent`, `AppelOutil`, `OutilAgent` (`executer: Mapping → str`), `ReponseAgentBrute`, `ReponseAgent`, `Tache.agent`, `StatutControle` ; lecture seule.
- `src/usine/contrats/trace.py` -- `EntreeTrace` : trace LLM ⇒ `tache`, `fournisseur`, `version_prompt`, `version_modele`, `statut_controle` obligatoires.
- `src/usine/ia/controles.py` -- `controler_nombres(texte, valeurs)`, `ValeurAutorisee = int | Fraction | Decimal | date`, `projet(cle)` ; `MOTIF_CLE_TICKET` dans `contrats/tickets.py`.
- `src/usine/ia/agent/outils.py` -- `outils_consultation(consultation)` → `DefinitionOutil` (5 outils, résultat `Enregistrement`) ; la session les sérialise en JSON.
- `src/usine/contrats/versions.py:46` -- `version_prompt(octets)` ; modèle : `ia/explication.py:62` (`lire_prompt`).
- `tests/doublures/fournisseur_factice.py:83` -- `executer_agent` scripté (appels puis texte) ; voir le constructeur pour scripter un tour.
- `src/usine/composition.py:474` -- `_passerelle_evaluation(racine, fournisseur, pseudonymiseur)` : passerelle réelle ou doublures, cache mémoire ; à réutiliser pour `construire_session_agent`.
- `src/usine/ui/cli.py:60` -- `consultation_dernier_passage` ; `src/usine/ui/app.py:382,583` -- emplacement `afficher_a_venir` ; `ui/navigation.py:23` `STORY_A_VENIR` (retirer `Ecran.agent`) ; tests `tests/unit/ui/test_app.py:157,188`, `test_navigation.py:31`.

## Tasks & Acceptance

**Execution:**
- `src/usine/ia/prompts/agent.md` -- consignes système en français : n'utiliser que les outils, ne calculer aucun chiffre, citer les tickets retournés, dire « Les données ne permettent pas de répondre » sinon.
- `src/usine/ia/passerelle.py` -- `executer_agent` : pseudonymise les messages, enveloppe chaque `OutilSource` (exécution, erreur d'arguments rendue en texte, Pseudonymisation du résultat, trace `tache=agent`, `cible=<nom outil>`, `statut_controle=non_controle`), cache, plafond, fournisseur, contrôle, ré-identification (jetons de toute la conversation pseudonymisée), trace finale.
- `src/usine/ia/agent/session.py` -- `serialiser_resultat` (JSON, borne `LIMITE_POINTS_TENDANCE=60` avec `points_omis`), `controler_reponse` (nombres et dates des messages `outil` → `controler_nombres` ; tickets cités hors des retournés → rejet ; message `MESSAGE_REJET` explicite), `SessionAgent.repondre(question) -> ReponseAgent` et écriture JSONL des traces.
- `src/usine/composition.py`, `src/usine/ui/cli.py` -- `construire_session_agent(racine, consultation, fournisseur=None, pseudonymiseur=None)` ; `ui/cli.session_agent`.
- `src/usine/ui/app.py`, `ui/navigation.py` -- écran Agent : formulaire, réponse, statut, outils appelés ; en Mode repli, message renvoyant à la Story 7.11 ; erreur explicite si la session ne peut être construite.
- `tests/unit/ia/test_passerelle_agent.py`, `tests/unit/ia/agent/test_session.py`, tests UI -- matrice I/O avec `FournisseurFactice` et pseudonymiseur factice, dont la question de la démo sur `passage_palier_2()`.

**Acceptance Criteria:**
- Given l'écran Agent avec une session factice, when le Pilote pose la question de la démo, then la réponse s'affiche avec son statut et les outils appelés.
- Given un pseudonymiseur factice qui marque ses entrées, when un outil est exécuté, then le fournisseur ne reçoit que le résultat pseudonymisé et une trace de l'outil est produite avant la réponse.
- Given une session, when elle se termine, then `sorties/agent/<AAAA-MM-JJ>/<session>.jsonl` contient ses traces et aucun répertoire de Passage n'est modifié.

## Spec Change Log

## Review Triage Log

### 2026-10-13 — Review pass
- Couches lancées : Edge Case Hunter seul (mode économique) ; Blind Hunter, Verification Gap et Intent Alignment ignorés.
- verdicts: 14 findings — high 0, medium 2, low 9, false 1, maybe-false 0 (+ 2 rejets de conception)
- findings:
  - `[medium]` `[patch]` chiffres des clés de ticket et des jetons dans les chaînes d'outils autorisés (`MIG-42` autorisait « 42 ») — clés et jetons masqués avant la lecture des nombres ; test `test_chiffres_d_une_cle_ou_d_un_jeton_non_autorises`.
  - `[low]` `[patch]` décimales françaises des chaînes d'outils (« 12,5 ») non reconnues — motif `\d+(?:[.,]\d+)?`, virgule lue comme point ; même test.
  - `[low]` `[reject]` jetons en forme de clé (`UTF-8`, `ISO-8601`) comptés comme tickets — rare dans une réponse de l'Agent ; le correctif (projets connus) ajoute une branche.
  - `[low]` `[reject]` chiffres ou tickets de la question refusés — conforme à l'AC : seuls les résultats d'outils autorisent un chiffre.
  - `[low]` `[patch]` réponse vide affichée comme conforme — rejet avec le motif « réponse vide » ; test `test_reponse_vide_rejetee`.
  - `[low]` `[reject]` la borne de Tendance coupe des séries — signalée par `points_omis`, chaque point gardé reste exact ; borne voulue (report 7.8).
  - `[medium]` `[defer]` outil qui lève une erreur hors `ValidationError` : pas de trace, conversation interrompue — groupé avec les deux constats suivants (voir `deferred`).
  - `[medium]` `[defer]` traces d'outils perdues si `executer_agent` lève — même cause (traces exposées au retour seulement).
  - `[low]` `[patch]` exception hors `UsineErreur` dans `repondre` → page d'erreur Streamlit — `except Exception` avec message explicite dans `afficher_agent`.
  - `[low]` `[reject]` session au-delà de minuit, traces dans le dossier de la veille — cas improbable pendant une démo de 10 minutes.
  - `[low]` `[reject]` fournisseurs non fermés en Mode repli ou en fin de session navigateur — fuite bornée à un client par session ; ajout de cycle de vie disproportionné.
  - `[false]` `[reject]` arguments des `appels_outils` en entrée non pseudonymisés — la session n'envoie que des messages `systeme` et `utilisateur`, sans `appels_outils`.
  - `[low]` `[reject]` ré-identification limitée à l'entrée et aux messages `outil` (écart à « toute la conversation ») — écart voulu et testé : un jeton inventé par le modèle ne doit pas être ré-identifié.
  - `[medium]` `[defer]` matrice « une trace par outil exécuté » non tenue en cas d'exception — même cause que les deux reports ci-dessus.

## Design Notes

Chaque question est indépendante (pas d'historique entre questions) : les valeurs autorisées sont celles des outils appelés pour cette question. Les nombres autorisés viennent des valeurs JSON numériques des résultats (`float` lu via `Decimal(repr)`), des nombres écrits dans leurs chaînes et des dates ISO. Les tickets autorisés sont les clés trouvées dans ces résultats. Un ticket cité est une clé `MOTIF_CLE_TICKET` dont le projet n'est ni `IND`, ni `ENT`, ni `J`.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert

## Auto Run Result

Status: done

- **Changement** : `Passerelle.executer_agent` suit l'ordre AD-12. Chaque outil est enveloppé : son résultat est pseudonymisé et tracé avant d'atteindre le fournisseur, et des arguments invalides sont rendus en texte. `SessionAgent` (`ia/agent/session.py`) pose une question avec les cinq outils, borne `get_tendance` à 60 points avec `points_omis` (report 7.8, sans changer les contrats), puis contrôle chiffres et tickets contre les résultats d'outils (`controler_nombres`). Une réponse fautive est rejetée par un message explicite. Les traces vont dans `sorties/agent/<AAAA-MM-JJ>/<session>.jsonl`. L'écran Agent de l'UI est livré.
- **Fichiers** :
  - `src/usine/ia/passerelle.py` : `executer_agent`, `OutilSource`, `ResultatAgent`, `_verifier_plafond` factorisé.
  - `src/usine/ia/agent/session.py` : sérialisation, contrôle, session et traces JSONL.
  - `src/usine/ia/prompts/agent.md` : consignes.
  - `src/usine/composition.py` et `src/usine/ui/cli.py` : `construire_session_agent` et `session_agent`.
  - `src/usine/ui/agent.py`, `ui/app.py` et `ui/navigation.py` : l'écran Agent.
  - Tests : `tests/unit/ia/test_passerelle_agent.py`, `tests/unit/ia/agent/test_session.py`, `tests/unit/ui/test_app_agent.py`, plus des mises à jour de `test_app.py`, `test_navigation.py` et `test_outils.py`.
- **Revue** (Edge Case Hunter seul) : 4 patchs (1 medium et 3 low), 1 report medium (traces perdues sur exception, 3 constats), 8 rejets motivés dans le journal de triage.
- **Suivi recommandé** : non, un seul medium a été patché, et il est couvert par un test.
- **Vérification** : ruff, format, mypy et lint-imports sont verts (15 contrats respectés). pytest donne 2718 passés et 1 ignoré.
- **Écarts** :
  - La ré-identification n'admet que les jetons de l'entrée et des messages `outil`, ce qui est plus strict que la spec.
  - Le Passage de test n'a de Risque que sur ENT-A. Le test de la question de la démo cite donc l'Entité retournée, et non C.
- **Risques résiduels** :
  - Les traces sont perdues sur exception (voir `deferred`).
  - Les fournisseurs réels restent ouverts dans `session_state` jusqu'au changement de Passage.
  - Le Mode repli de l'Agent est reporté à la Story 7.11.
