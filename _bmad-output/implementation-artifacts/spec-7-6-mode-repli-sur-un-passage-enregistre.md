---
title: 'Story 7.6 : Mode repli sur un Passage enregistré'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'e559056c658e71eec72534df27a5f6e14a395fc6'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-7-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-7-5-ecran-ce-qu-il-faut-pour-le-faire-en-vrai.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** En Mode repli, l'UI affiche seulement un bandeau et désactive les liens Jira : elle lit toujours `sorties/passages/`, absent d'un clone frais, et rien ne permet d'activer le mode depuis la page. Si Jira ou le réseau tombe, la démo s'arrête (Story 7.6, FR-45, NFR-12, AD-11, AD-19, H-30).

**Approach:** Versionner sous `demo/repli/passage/` la copie d'un Passage publié entièrement fictif (graine 42, généré le 2026-10-12, arrêté le 2026-10-09). Le Mode repli effectif vaut `USINE_MODE_REPLI` (lu par `charger_secrets`) **ou** une bascule manuelle de la barre latérale. Quand il est actif, la carte, le détail et l'avant / après lisent cette copie via `ConsultationPassage` (sans URL Jira), et le lancement de la Chaîne est désactivé.

## Boundaries & Constraints

**Always:**
- **Copie versionnée.** `demo/repli/passage/` contient les fichiers d'un Passage publié par `usine rapport` : `manifeste.json`, tables, `meteo.json`, `previsions.json`, `trace/` et les rapports. Le manifeste porte palier 1, `classification_initiale: false` et les Scénarios A (rouge), B (rouge) et C (orange) au 09/10/2026. Les données sont entièrement fictives.
- **Services** (`ui/cli.py`, racine de composition). `REPERTOIRE_REPLI = Path("demo/repli/passage")`. `consultation_repli(racine) -> Consultation | None` renvoie `ConsultationPassage(racine / REPERTOIRE_REPLI, racine_passages=<même répertoire>, url_jira=None)`, ou `None` si `manifeste.json` est absent. La copie se lit uniquement via `Consultation`, jamais en ouvrant ses fichiers dans `app.py`.
- **Mode effectif.** `afficher_bandeau(racine) -> bool` renvoie l'état effectif. La variable d'environnement active force la bascule à l'état activé, désactivée. Sinon, la bascule `st.sidebar.toggle("Mode repli", key=navigation.CLE_REPLI)` décide. Une variable illisible donne `st.error` (comme aujourd'hui), puis la bascule décide. Le bandeau reste le premier élément de la zone principale. Il nomme `demo/repli/passage/` et précise que les liens Jira sont inactifs.
- **Écrans en Mode repli.** La carte et le détail lisent `consultation_repli`. L'avant / après mesure le manifeste de la copie, avec les mêmes messages : `SEULE_CLASSIFICATION_INITIALE` si la copie porte une classification initiale. L'outillage ne change pas. Le lancement affiche `st.info(LANCEMENT_REPLI)` et garde le bouton « Lancer la Chaîne » visible mais désactivé.
- **Copie absente.** `st.error(REPLI_ABSENT)` nomme `demo/repli/passage/`, sans exception et sans repli silencieux vers `sorties/passages/`.
- **Aucune détection automatique (H-30).** Sans variable ni bascule, la page lit `sorties/passages/` même si ce répertoire est vide ou si Jira est injoignable. Aucune sonde réseau.
- **Couches.** `app.py` n'importe ni `ports`, ni `config`, ni `consultation`. Les tests passent par `streamlit.testing.v1.AppTest`.

**Never:**
- Modifier `src/usine/contrats/`, `src/usine/ports/`, `composition.py`, `config/`, `pyproject.toml` ou `uv.lock`, ou écrire hors de `src/usine/ui/`, `tests/unit/ui/` et `demo/`.
- Lire `.env` dans les tests, ou lire `os.environ` pour le Mode repli : seul `charger_secrets` le lit.
- Désactiver le Mode repli depuis la page quand la variable d'environnement l'impose.
- Lancer la Chaîne ou écrire sous `sorties/` en Mode repli.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Repli par variable | `USINE_MODE_REPLI=1`, copie présente, pas de `sorties/` | bandeau en tête ; carte de la copie (ENT-A à ENT-J, date 09/10/2026), clés `DEMO-` sans lien ; bascule activée et désactivée | N/A |
| Repli par bascule | pas de variable ; bascule activée | mêmes effets que par variable ; bascule désactivée : retour à `sorties/passages/` et bandeau retiré | N/A |
| Clone frais sans réseau | racine = `demo/repli/passage/` + `config/demo.yaml`, connexions réseau interdites | carte, détail d'ENT-A (Prévision, Risque, Règles sans lien) et avant / après affichés, sans erreur ni exception | N/A |
| Lancement en repli | repli actif | `LANCEMENT_REPLI`, bouton désactivé, aucun sous-processus | N/A |
| Copie absente | repli actif, pas de `demo/repli/passage/manifeste.json` | `REPLI_ABSENT` sur la carte, le détail et l'avant / après | pas d'exception |
| Pas de détection | aucune variable ni bascule, pas de Passage publié, copie présente | « Aucun Passage publié », pas de bandeau | N/A |
| Copie illisible | `meteo.json` de la copie corrompu | « Lecture du dernier Passage impossible : … » | pas d'exception |

</intent-contract>

## Code Map

- `src/usine/ui/cli.py:39` -- `mode_repli` (variable seule, inchangé). `:47` -- `consultation_dernier_passage` : modèle de `consultation_repli`. `:74` -- `manifestes_avant_apres`.
- `src/usine/ui/app.py:42` -- `afficher_bandeau` : renvoyer le mode effectif et ajouter la bascule. `:71` -- `_lecture(racine)` : ajouter `repli`. `:182` -- `_passage_mesure` : manifeste de la copie en repli. `:346` -- `afficher_lancement` : branche repli. `:391` -- `principal` : propager `repli`.
- `src/usine/ui/navigation.py:30` -- clés `session_state` : ajouter `CLE_REPLI`.
- `src/usine/consultation/passage.py:131` -- `ConsultationPassage(repertoire, racine_passages=, url_jira=)` ; `url_ticket` renvoie `None` sans `url_jira` (lecture seule).
- `tests/unit/ui/conftest.py` -- `racine_publiee` : copier aussi `demo/repli/passage/` du dépôt.
- `tests/unit/ui/test_app.py:121,133,229,468` -- tests du Mode repli existants, qui lisent désormais la copie (Entités ENT-A à ENT-J).
- Procédure de production de la copie : clone sans secrets Jira, `USINE_MODE_REPLI=1`, `usine donnees generer --graine 42 --date-generation 2026-10-12`, `usine rapport --date-arrete 2026-10-09`, puis copie de `sorties/passages/2026-10-09/<passage_id>/` vers `demo/repli/passage/`.

## Tasks & Acceptance

**Execution:**
- `demo/repli/passage/` -- ajouter la copie produite par la procédure ci-dessus -- source du Mode repli, versionnée.
- `src/usine/ui/cli.py` -- `REPERTOIRE_REPLI`, `consultation_repli`.
- `src/usine/ui/navigation.py` -- `CLE_REPLI`.
- `src/usine/ui/app.py` -- bascule, mode effectif, constantes `REPLI_ABSENT` et `LANCEMENT_REPLI`, écrans branchés selon la matrice, docstring mise à jour.
- `tests/unit/ui/conftest.py` -- copie de `demo/repli/passage/` dans `racine_publiee`.
- `tests/unit/ui/test_repli.py` -- validité de la copie : manifeste lisible, palier 1, sans classification initiale, A et B rouges et C orange au 09/10/2026, Prévisions non vides, `url_ticket` à `None`, `passage_id` cohérent avec `trace/` ; plus `consultation_repli` sans copie.
- `tests/unit/ui/test_app.py` -- matrice I/O par `AppTest`, dont le clone frais avec `socket.socket.connect` qui lève ; mise à jour des tests de repli existants.

**Acceptance Criteria:**
- Given `demo/repli/passage/`, when l'auteur active le Mode repli par la bascule ou par `USINE_MODE_REPLI=1`, then toute l'UI lit cette copie via `Consultation`, la mention « Mode repli » est visible en permanence et les liens Jira sont inactifs.
- Given un clone frais sans réseau, when l'auteur lance l'UI en Mode repli, then la carte météo, le détail d'Entité, les Prévisions et l'avant / après fonctionnent.
- Given le Mode repli, when on cherche une détection automatique, then il n'y en a pas : l'activation est toujours manuelle (H-30).
- Given le dépôt, when on lance `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest -q`, then tout passe.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- Diff relu : `src/` et `tests/` en entier. Pour la copie générée `demo/repli/passage/`, seule la liste des fichiers a été relue.
- verdicts : 25 constats — high 0, medium 0, low 20, false 5, maybe-false 0
- findings :
  - `[low]` `[patch]` (blind) Une copie illisible en repli affiche « Lecture du dernier Passage impossible » et désigne la mauvaise source — préfixe propre au repli, qui nomme `demo/repli/passage/`.
  - `[low]` `[reject]` (blind) Le sous-titre « Carte météo du dernier Passage » reste en repli — le bandeau permanent nomme la copie ; cosmétique.
  - `[low]` `[reject]` (blind) Une Chaîne lancée avant l'activation continue d'écrire sous `sorties/` — cas improbable en démo. Le garde évident (bascule bloquée pendant un lancement) empêcherait de basculer justement quand Jira tombe en plein lancement. La docstring est corrigée (dernière ligne edge).
  - `[low]` `[reject]` (blind) Bascule latérale moins testée que la variable (lancement, avant / après) — le même booléen `repli` pilote les écrans quelle que soit sa source ; aller-retour par la bascule testé sur la carte.
  - `[low]` `[reject]` (blind) Variable retirée en cours de session : la bascule reste active — exige une modification de `.env` pendant la démo. Le retour se fait à la main, conformément à H-30.
  - `[false]` `[reject]` (blind) `racine_passages=repertoire` fausserait `dernier_passage` et les tendances — aucun écran n'appelle `dernier_passage` sur cette `Consultation`, et les tendances et dates se lisent dans les fichiers du Passage.
  - `[low]` `[reject]` (blind) Pas de contrôle de complétude de la copie — les fichiers absents sont des tables vides par conception (Palier 1 sans explications) ; `test_repli.py` et le test du clone frais lisent carte, détail et avant / après.
  - `[low]` `[patch]` (blind) Aucune procédure de régénération de la copie dans le dépôt — procédure ajoutée en docstring de `REPERTOIRE_REPLI`.
  - `[low]` `[reject]` (blind) Liste des Entités dupliquée dans deux tests — deux constantes de test ; une régénération de la copie les rendrait rouges toutes les deux.
  - `[low]` `[reject]` (blind) Messages vérifiés par sous-chaîne — `app.py` n'est pas importable (il exécute `principal`) ; les sous-chaînes nomment le répertoire.
  - `[low]` `[patch]` (blind) Déduplication des erreurs non démontrée — même cause que la ligne VG-3 ; assertion de compte ajoutée.
  - `[low]` `[patch]` (blind) Bascule sans aide quand le mode n'est pas imposé — `help` toujours renseigné.
  - `[low]` `[patch]` (verification-gap) Manifeste enregistré illisible non testé sur l'avant / après — `test_repli_avant_apres_manifeste_illisible`.
  - `[low]` `[reject]` (verification-gap) La carte affichée après un lancement réussi n'est jamais testée en repli — suppose un lancement en cours avant l'activation, improbable en démo.
  - `[low]` `[patch]` (verification-gap) `USINE_MODE_REPLI` illisible : le nombre d'erreurs n'est pas vérifié — assertion d'une seule erreur.
  - `[low]` `[reject]` (intent) « Toute l'UI » : les rapports `.pptx` / `.xlsx` de la copie ne sont affichés nulle part — aucun écran de l'Epic 7 n'affiche les rapports, et les fichiers restent dans la copie comme dans tout Passage publié.
  - `[low]` `[reject]` (intent) « Clone frais sans réseau » simulé par `AppTest` et non par un vrai clone avec `usine ui` — `AppTest` est la convention des tests de l'UI. Le vrai clone revient aux répétitions de la Story 7.12.
  - `[false]` `[reject]` (intent) Le chemin « Risque d'entrée en rouge » n'est pas exercé sur la copie — il est couvert par les tests du détail (doublures) ; la copie n'apporte que la source.
  - `[false]` `[reject]` (intent) Le caractère fictif n'est vérifié que par le préfixe `DEMO-` — la copie vient du Journal généré (graine 42), sans aucune donnée réelle ; la procédure est désormais documentée.
  - `[low]` `[reject]` (edge) Chaîne en cours au moment de l'activation — même cause et même motif que la ligne blind 3.
  - `[false]` `[reject]` (edge) La carte de la copie s'affiche après « Passage publié » en repli — c'est voulu : en repli, toute l'UI lit la copie.
  - `[low]` `[reject]` (edge) Variable retirée en cours de session — doublon de la ligne blind 5.
  - `[false]` `[reject]` (edge) Une copie partielle afficherait « aucune Météo » au lieu d'une erreur — `meteo.json` absent donne bien ce message explicite, et le manifeste reste exigé.
  - `[low]` `[reject]` (edge) `OSError` (permission) non capturée dans `_lecture` — cas d'un dépôt cloné aux droits cassés, improbable ; ajouterait une branche.
  - `[low]` `[patch]` (edge) La docstring d'`afficher_lancement` promet « rien n'est écrit sous `sorties/` », ce qui est faux pour une Chaîne lancée avant l'activation — reformulée en « aucun nouveau lancement n'est possible ».

## Design Notes

**Lancement désactivé en repli.** La copie est la seule source de l'UI en repli. Un lancement écrirait sous `sorties/` un Passage que l'UI n'afficherait pas, et un clone frais n'a pas de Journal. Les critères de la story ne citent pas le lancement.

**Copie mesurée, horloge réelle.** La copie vient d'une vraie exécution de `usine rapport`. Sa durée mesurée, environ 5 s, alimente l'avant / après. Une horloge figée aurait donné 0 s, ce qui serait trompeur.

**Story 7.11.** Les réponses enregistrées de l'Agent (`demo/repli/agent/`) porteront le `passage_id` de cette copie, `20261012T152755Z-5de91e`.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check .` -- expected: aucun écart.
- `uv run mypy` -- expected: aucune erreur.
- `uv run lint-imports` -- expected: tous les contrats KEPT.
- `uv run pytest -q tests/unit/ui` puis `uv run pytest -q` -- expected: tout vert.

## Auto Run Result

Status: done

- **Résumé.** Le Mode repli s'active à la main, par `USINE_MODE_REPLI` (qui force la bascule à l'état activé et la verrouille) ou par la bascule « Mode repli » de la barre latérale. Une fois actif, la carte, le détail (Prévisions comprises) et l'avant / après lisent via `Consultation` la copie versionnée `demo/repli/passage/`, sans lien Jira. Le bandeau reste en tête de chaque écran et le lancement est désactivé. Copie absente : erreur explicite, sans repli silencieux. Aucune détection automatique (H-30). La copie est un vrai Passage fictif : graine 42, arrêté le 09/10/2026, `passage_id` `20261012T152755Z-5de91e`, 644 Ko, durée mesurée d'environ 5 s.
- **Fichiers.**
  - `demo/repli/passage/` — copie versionnée du Passage publié (tables, Météo, Prévisions, trace, rapports).
  - `src/usine/ui/cli.py` — `REPERTOIRE_REPLI` (procédure de régénération en docstring), `consultation_repli`.
  - `src/usine/ui/navigation.py` — `CLE_REPLI`.
  - `src/usine/ui/app.py` — bascule, mode effectif, bandeau, écrans branchés sur la copie, lancement désactivé, messages d'erreur propres au repli.
  - `tests/unit/ui/conftest.py` — copie de `demo/repli/passage/` dans `racine_publiee`.
  - `tests/unit/ui/test_repli.py` — validité de la copie.
  - `tests/unit/ui/test_app.py` — matrice I/O par `AppTest`, dont un clone frais avec les connexions réseau non locales interdites.
- **Revue (une passe, mode économique).** 25 constats. 7 lignes `low` patchées : message d'erreur du repli, procédure de régénération, assertion de déduplication, aide de la bascule, test du manifeste illisible, docstring du lancement. Aucun différé. 18 rejetés, 13 `low` et 5 `false`, avec leurs motifs dans le Triage Log. La copie générée n'a pas été relue ligne à ligne : seule sa liste de fichiers était dans le diff de revue.
- **Revue de suivi recommandée :** non (aucun `high` ni `medium` patché).
- **Vérification.** `ruff check`, `ruff format --check`, `mypy` et `lint-imports` (13 contrats KEPT) passent. `pytest -q` : 2203 passed, 1 skipped.
- **Risques résiduels.**
  - Une Chaîne lancée avant l'activation du repli continue d'écrire sous `sorties/`, et sa fin affiche la carte de la copie.
  - Si `USINE_MODE_REPLI` est retiré en cours de session, la bascule reste activée jusqu'à ce qu'on la désactive à la main.
  - Le « clone frais sans réseau » est simulé par `AppTest`. Le vrai clone sera éprouvé aux répétitions (Story 7.12).
  - Un changement de version majeure des contrats impose de régénérer la copie, selon la procédure inscrite dans `cli.py`.
