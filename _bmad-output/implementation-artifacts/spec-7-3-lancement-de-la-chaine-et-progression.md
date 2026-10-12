---
title: "Story 7.3 : Lancement de la Chaîne et progression"
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '0f52648ecee83cc4c29e01c3c20483fb0fb2f6ff'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-7-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-7-2-detail-d-une-entite-palier-1.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** L'écran Lancement (Story 0.8, repris par la 7.1) affiche le statut de chaque étape mais ni sa durée, ni le nom de l'étape fautive en cas d'échec. Le suivi s'arrête dès qu'on quitte l'écran, et après un succès il faut cliquer sur « Carte météo » pour voir le nouveau Passage (écarts consignés par la 7.1 ; Story 7.3, FR-43, FR-25, AD-8).

**Approach:** `ui/progression.py` gagne des fonctions pures : suivi par étape (statut et durée lus dans `sorties/progression/<passage_id>.jsonl`) et étape en échec. L'écran Lancement les affiche, nomme l'étape fautive, et affiche la carte du nouveau Passage sous le message de succès. Sur les autres écrans, un résumé dans la barre latérale continue de sonder la Chaîne et relance la page à la fin, pour que la carte relise le dernier Passage.

## Boundaries & Constraints

**Always:**
- **Durée.** Elle vaut l'horodatage du dernier événement final de l'étape (`reussie`, `sautee`, `echouee`) moins celui de son dernier `en_cours`, et s'écrit avec `contrats.format.formater_nombre(secondes, 1)` suivi de ` s` (`0,3 s`). Une étape en cours ou en attente n'a pas de durée. Ligne affichée : `- **kpi** : Réussie (0,3 s)`, ou `- **kpi** : En cours` sans durée.
- **Échec.** Quand le sous-processus finit avec un code non nul, le message d'erreur commence par `Échec de la Chaîne à l'étape « <etape> » (code N)` si la progression contient une étape `echouee`, sinon par `Échec de la Chaîne hors d'une étape (code N)`. Il est suivi des dernières lignes de l'erreur standard (règle existante, `LIGNES_ERREUR_MAX`). Aucune carte ni rapport n'est affiché sur l'écran Lancement, seulement le message `AUCUN_RAPPORT` : « Aucun rapport publié par ce lancement : la carte météo reste celle du dernier Passage publié. »
- **Succès.** Sous « Chaîne terminée : Passage publié. », l'écran Lancement affiche la carte météo du dernier Passage publié (`afficher_carte`), sans clic.
- **Suivi hors de l'écran Lancement.** Si un lancement de cette session existe et que l'écran affiché n'est pas Lancement, la barre latérale montre un résumé. Pendant le run, c'est un fragment sondé toutes les `INTERVALLE_SONDAGE` secondes : « Chaîne en cours : étape « X » », ou « Chaîne en cours… » avant le premier événement. À la fin, il lit l'erreur standard une seule fois, puis relance la page entière une seule fois (`_FIN_VUE`). Le résumé final vaut « Dernier lancement : Passage publié. » ou « Dernier lancement en échec à l'étape « X ». » (ou « hors d'une étape »).
- **Fichiers.** La lecture de la progression reste en ouvrir-lire-fermer (`lire_progression`). Les clés de `session_state` et `_lancer` de la 0.8 sont conservés.
- **Couches.** `usine.ui` n'importe ni `ports`, ni `domaine`, ni `consultation`.
- **Tests** par `streamlit.testing.v1.AppTest`, `Popen` factice (`_Lanceur`). Le test de bout en bout de la 7.1 (`test_bout_en_bout.py`, vrai `usine rapport`) est étendu : durées présentes et carte affichée sur l'écran Lancement sans changer d'écran.

**Never:**
- Modifier `src/usine/contrats/`, `src/usine/ports/`, `pyproject.toml`, `uv.lock`, ou écrire hors de `src/usine/ui/` et `tests/unit/ui/`.
- Lire un Passage en échec (`sorties/echecs/`) ou un répertoire `.en-cours-*`, ou afficher une carte sur l'écran Lancement après un échec.
- Changer d'écran à la place du Pilote.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| En cours | `extraction` en_cours puis reussie (+0,5 s), `instantanes` en_cours | `extraction` : Réussie (0,5 s) ; `instantanes` : En cours ; `kpi` : En attente | N/A |
| Sautée | `classification` en_cours puis sautee (même instant) | `classification` : Sautée (0,0 s) | N/A |
| Échec d'étape | `kpi` echouee, code 1 | erreur « Échec de la Chaîne à l'étape « kpi » (code 1) : … », `AUCUN_RAPPORT`, aucun tableau de carte | N/A |
| Échec hors étape | aucun `echouee`, code 1 | « Échec de la Chaîne hors d'une étape (code 1) » | N/A |
| Succès | code 0, Passage publié | succès, puis carte (Date d'arrêté, tableau des Entités) sur l'écran Lancement | N/A |
| Hors écran, en cours | lancement puis écran Carte | barre latérale « Chaîne en cours : étape « … » » | N/A |
| Hors écran, fin | code passe à 0 pendant l'écran Carte | une seule relance ; résumé « Dernier lancement : Passage publié. » ; carte relue | N/A |
| Final sans `en_cours` | `reussie` seul | statut sans durée | N/A |

</intent-contract>

## Code Map

- `src/usine/ui/progression.py:73` -- `etat_des_etapes` : base du nouveau suivi par étape (garder). Ajouter `SuiviEtape` (étape, état, durée `timedelta | None`), `suivi_des_etapes`, `etape_en_echec`, `texte_duree`.
- `src/usine/ui/app.py:186` -- `_suivre` : rendu des étapes, message de fin et `st.rerun()` unique. Il faut extraire la lecture (fichier et événements) et la fin (`_erreur`, `_FIN_VUE`, rerun) pour les partager avec le résumé latéral.
- `src/usine/ui/app.py:221` -- `afficher_lancement` : ajouter `AUCUN_RAPPORT` ou `afficher_carte` après le fragment, quand le processus est terminé.
- `src/usine/ui/app.py:238` -- `principal` : résumé latéral (`with st.sidebar:` puis fragment) quand l'écran n'est pas Lancement.
- `src/usine/chaine/execution.py:74` -- source des événements : `en_cours` avant l'étape, statut final après, `echouee` en cas d'exception (lecture seule).
- `src/usine/contrats/passage.py:56` -- `EvenementProgression` (`horodatage` UTC), `StatutEtape` (lecture seule).
- `tests/unit/ui/test_app.py:495` -- `_ProcessusFactice`, `_Lanceur`, `_installer`, `_ligne` (à étendre d'un horodatage) ; tests 0.8 de lancement à garder verts.
- `tests/unit/ui/test_bout_en_bout.py` -- vrai `usine rapport` (7.1), à étendre.
- `tests/unit/ui/test_progression.py` -- tests purs de la progression.

## Tasks & Acceptance

**Execution:**
- `src/usine/ui/progression.py` -- `SuiviEtape`, `suivi_des_etapes`, `etape_en_echec`, `texte_duree`.
- `src/usine/ui/app.py` -- lignes avec durée, message d'échec nommant l'étape, `AUCUN_RAPPORT`, carte après succès, résumé latéral sondé hors de l'écran Lancement.
- `tests/unit/ui/test_progression.py` -- matrice I/O en fonctions pures (durées, sautée, échec, final sans `en_cours`).
- `tests/unit/ui/test_app.py` -- échec nommé sans carte, échec hors étape, carte après succès sur l'écran Lancement, résumé latéral en cours puis relance unique à la fin.
- `tests/unit/ui/test_bout_en_bout.py` -- durées affichées, carte du 09/10/2026 sur l'écran Lancement.

**Acceptance Criteria:**
- Given le dépôt, when `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest -q`, then tout passe.
- Given un vrai `usine rapport` lancé depuis l'écran Lancement, when il se termine, then chaque étape d'`Etape` est affichée « Réussie » ou « Sautée » avec une durée, et la carte du 09/10/2026 apparaît sans changer d'écran.
- Given une Chaîne lancée puis l'écran Carte affiché, when le processus se termine avec succès, then la page se relance une seule fois et la carte relit le dernier Passage.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 26 findings — high 0, medium 0, low 19, false 7, maybe-false 0
- findings:
  - `[low]` `[patch]` (verification-gap) Résumé latéral avec progression illisible jamais testé — ajouté `test_resume_lateral_progression_invalide` (écran Carte, ligne invalide, aucune exception, « Chaîne en cours… »).
  - `[low]` `[patch]` (verification-gap) `AUCUN_RAPPORT` mort et dupliqué dans `app.py` — copie supprimée, seule `progression.AUCUN_RAPPORT` reste.
  - `[low]` `[reject]` (verification-gap) Progression illisible et échec : le résumé latéral dit « hors d'une étape » — cumul rare (fichier corrompu et échec) ; l'écran Lancement affiche l'erreur de lecture ; le correctif ajoute un état.
  - `[low]` `[reject]` (intent) Tests surtout sur `Popen` factice, sondage `run_every` non exercé en temps réel — le bout en bout lance un vrai `usine rapport` et sonde la page jusqu'à la fin ; `AppTest` ne joue pas le temps réel.
  - `[low]` `[reject]` (intent) Échec non joué avec la vraie CLI ; un test fige « hors d'une étape » quand stderr nomme l'étape — `execution.py:120` écrit `echouee` sur toute exception ; le cas « hors d'une étape » ne survient que sur un arrêt brutal.
  - `[false]` `[reject]` (intent) Durée à lire dans le manifeste (AD-8/AD-9) — le critère dit « lue dans `sorties/progression/<passage_id>.jsonl` » et le manifeste n'existe qu'après publication.
  - `[low]` `[reject]` (intent) `test_lancement_succes` ne distingue pas nouvelle et ancienne carte — distingué par `test_resume_lateral_relit_la_carte` et le bout en bout (racine vide).
  - `[false]` `[reject]` (intent) Résumé latéral hors du périmètre du critère — il traite les deux écarts consignés par la 7.1 pour cette story.
  - `[low]` `[patch]` (intent) Constante `AUCUN_RAPPORT` morte dans `app.py` — même correctif que ci-dessus.
  - `[low]` `[patch]` (blind) Constante dupliquée et morte — même correctif.
  - `[low]` `[reject]` (blind) Processus tué en cours d'étape : « hors d'une étape » — arrêt brutal seulement (voir ci-dessus) ; le repli sur l'étape `en_cours` ajoute une branche.
  - `[low]` `[reject]` (blind) Étape interrompue affichée « En cours » après la fin — même cause rare ; le message d'échec reste affiché.
  - `[low]` `[patch]` (blind) Le résumé latéral nomme une étape déjà terminée (dernier événement quel que soit son statut) — `_resumer` ne nomme que l'étape mise `en_cours` sans événement final depuis, sinon « Chaîne en cours… » ; test étendu.
  - `[false]` `[reject]` (blind) Durées dupliquant le manifeste — voir la ligne intent : source imposée par le critère, manifeste absent pendant le run.
  - `[false]` `[reject]` (blind) `SuiviEtape.etat` typé `str` — `StatutEtape` est un `StrEnum`, même convention que `etat_des_etapes` ; aucune comparaison fausse possible.
  - `[low]` `[reject]` (blind) Regex du bout en bout sans espace insécable de milliers — aucune étape du mini-jeu n'approche 1 000 s.
  - `[low]` `[reject]` (blind) Secondes seulement, « 0 s » pour < 50 ms — format imposé par la spec (`formater_nombre(secondes, 1)`).
  - `[false]` `[reject]` (blind) Succès sans nouveau Passage montrerait l'ancienne carte — `usine rapport` ne sort en 0 qu'après `ecrivain.publier` (sinon `UsineErreur`, code non nul).
  - `[low]` `[patch]` (blind) Chemin d'erreur du résumé latéral non testé — même correctif que la ligne verification-gap ; les sous-points (AUCUN_RAPPORT pendant le run, cache stderr) rejetés : comportements gardés par `if en_cours: return` et `_erreur` partagé.
  - `[false]` `[reject]` (blind) Course sur `_FIN_VUE` partagé — `st.rerun()` suit immédiatement la pose du drapeau ; une navigation relance de toute façon la page entière, qui relit la carte.
  - `[low]` `[patch]` (edge) Constante morte — même correctif.
  - `[low]` `[reject]` (edge) Progression illisible + échec dans le résumé — doublon du rejet verification-gap.
  - `[low]` `[reject]` (edge) Écran Lancement : progression illisible → « hors d'une étape » — l'erreur de lecture est affichée juste au-dessus.
  - `[low]` `[patch]` (edge) Résumé latéral nommant une étape finie — même correctif que la ligne blind.
  - `[false]` `[reject]` (edge) Durée faussée par une reprise d'étape — la Chaîne exécute chaque `Etape` une seule fois (`execution.py:71`).
  - `[low]` `[reject]` (edge) Matrice « Sautée (0,0 s) » contre « 0 s » affiché — la règle Always impose `formater_nombre`, qui retire le zéro non significatif ; l'exemple de la matrice est inexact, la règle prime (correction = édition de spec).

## Design Notes

**Pourquoi la carte sur l'écran Lancement.** Changer d'écran à la place du Pilote demanderait d'écrire la clé du radio depuis un fragment, ce que Streamlit refuse pour un widget déjà créé. Afficher la carte sous le succès répond au critère « la carte météo affiche le nouveau Passage » sans surprise de navigation. L'écran Carte relit de toute façon le dernier Passage à chaque exécution.

**Durée.** Elle provient des horodatages de la progression, car le manifeste n'existe qu'après la publication. Les durées du manifeste servent à l'avant / après (Story 7.4).

**Fichiers hors lane.** Aucun.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check .` -- expected: aucun écart.
- `uv run mypy` -- expected: aucune erreur.
- `uv run lint-imports` -- expected: tous les contrats KEPT.
- `uv run pytest -q tests/unit/ui` puis `uv run pytest -q` -- expected: tout vert.

## Auto Run Result

Status: done

- **Résumé.** L'écran Lancement affiche chaque étape avec son statut et sa durée (horodatages de la progression), nomme l'étape fautive en cas d'échec sans montrer de carte (`AUCUN_RAPPORT`), et affiche la carte du nouveau Passage sous le succès, sans clic. Hors de cet écran, un résumé latéral continue de sonder la Chaîne et relance la page une seule fois à la fin : la carte relit le dernier Passage. Les deux écarts consignés par la 7.1 sont traités.
- **Fichiers.**
  - `src/usine/ui/progression.py` — `SuiviEtape`, `suivi_des_etapes`, `etape_en_echec`, `texte_duree`, `ligne_suivi`, `AUCUN_RAPPORT`.
  - `src/usine/ui/app.py` — durées, échec nommé, carte après succès, résumé latéral sondé (`afficher_resume`, `_resumer`), fin partagée (`_finir`).
  - `tests/unit/ui/test_progression.py`, `test_app.py`, `test_bout_en_bout.py` — matrice I/O, échec nommé sans carte, résumé latéral (en cours, relance unique, carte relue, échec, progression illisible), vrai `usine rapport` avec durées et carte sur l'écran Lancement.
- **Revue (une passe, mode économique).** 26 constats : 8 patchés (tous `low`, regroupés en 3 correctifs : constante morte, étape nommée par le résumé, test du résumé sur progression illisible), 0 différé, 18 rejetés (11 `low`, 7 `false` ; motifs dans le Triage Log).
- **Revue de suivi recommandée :** non (aucun `high` ni `medium` patché).
- **Vérification.** `ruff check`, `ruff format --check`, `mypy`, `lint-imports` (13 contrats KEPT), `pytest -q` : 2101 passed, 1 skipped.
- **Écart et risques résiduels.** Une durée nulle s'affiche « 0 s » (règle `formater_nombre`) et non « 0,0 s » comme l'exemple de la matrice. Un processus tué brutalement en cours d'étape est annoncé « hors d'une étape ». Le sondage `run_every` n'est exercé qu'au travers d'`AppTest` (pas en temps réel).
