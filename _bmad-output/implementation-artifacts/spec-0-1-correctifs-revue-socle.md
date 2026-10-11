---
title: 'Story 0.1 (E0-1) : correctifs de la revue du socle'
type: 'bugfix'
created: '2026-10-11'
status: 'done'
baseline_commit: '97eaf4c784a52a4ac4f2dc0f2e58c9eeb1072396'
baseline_snapshot: 'ffe732f99a574545e73bef825a901da0b29c367b' # commit hors branche : arbre de travail non commité de la Story 0.1 avant correctifs
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-0-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** La revue de la Story 0.1 (findings : `scratchpad/revue-story-0.1-findings.json`) montre que les garde-fous du socle laissent passer des cas réels : injection shell par `head_ref` en CI, contrôle des lanes qui refuse des tests légitimes et accepte des renommages ou des branches `lane/` mal formées, contrats `forbidden` non testés et sans interdits externes, chargeur YAML et CLI qui laissent fuir des exceptions brutes, contrôle NFR-10 fondé sur des regex.

**Approach:** Corriger chaque point de la liste ci-dessous, chacun avec un test qui échoue sans le correctif. Les autres findings de la revue restent hors périmètre.

## Boundaries & Constraints

**Always:**
- `ci.yml` : la branche passe par `env: BRANCHE: ${{ github.head_ref || github.ref_name }}`, jamais interpolée dans `run`.
- `controle_lanes.py` : un module `<dir>/<nom>` d'une lane admet aussi le test plat `tests/unit/<dir>/test_<nom>.py` ; `src/usine/adaptateurs/cli` appartient à la lane 2 ; la liste des fichiers vient de `git -c core.quotepath=off diff --name-only -z --no-renames` (découpe sur `\0`) ; une branche qui commence par `lane/` sans correspondre à `lane/<n>-` renvoie 1.
- `ConfigChaine` : `ConfigDict(frozen=True, extra="forbid", strict=True)`.
- Chargeur : `OSError` et `UnicodeDecodeError` deviennent une `UsineErreur` qui nomme le fichier ; une clé dupliquée devient une `UsineErreur` qui nomme le fichier, la clé et la ligne.
- `usine.cli:main` appelle `app()` et traduit toute `UsineErreur` en message sur stderr et code de sortie 1 ; `[project.scripts] usine = "usine.cli:main"`.
- `cles_sans_commentaire` trouve les clés via `yaml.compose` (toutes les clés de mapping, quelle que soit leur forme) ; un `#` n'est un commentaire que hors d'un scalaire.
- Tests de non-régression import-linter paramétrés sur chaque contrat `forbidden` lu dans `pyproject.toml` : une violation par module interdit, et chaque contrat doit être signalé BROKEN.
- Interdits externes (décision : liste blanche) : chaque couche a droit à pydantic, polars et la stdlib ; en plus `config` : yaml, pydantic_settings ; `rendu` : openpyxl, pptx ; `ui` : streamlit ; `adaptateurs` : bibliothèques d'I/O et de LLM (httpx, duckdb, pydantic_ai, anthropic, mistralai, presidio_analyzer, presidio_anonymizer, spacy, pymongo). `generateur`, `chaine`, `consultation`, `ia`, `ports`, `domaine` : aucune autre. `domaine` interdit en plus os, pathlib, io, time, uuid, shutil, tempfile. Hors produit : pas d'interdit externe. Un test échoue si une dépendance directe de `pyproject.toml` (groupes compris) n'est pas classée.

**Never:**
- Modifier le tableau des couches du spine, `layers`, ou les autres findings (secrets découpés, garde réseau, gitleaks, `concurrency`, fixtures `jira_*`, `--import-mode`).
- Ajouter une dépendance.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Test plat | lane 2, `tests/unit/adaptateurs/test_jira_cloud.py` ; lane 3, `tests/unit/domaine/test_kpi.py` | dans la lane | N/A |
| CLI lane 2 | lane 2, `src/usine/adaptateurs/cli.py` | dans la lane | N/A |
| Fichier hors lane | branche `lane/2-extraction`, diff `src/usine/domaine/kpi.py` | `main` renvoie 1 et liste le fichier | N/A |
| Branche mal formée | `lane/3`, `lane/3_calcul`, `lane/x-y` | `main` renvoie 1 | message nommant la branche |
| Renommage et accents | dépôt git temporaire : `contrats/a.py` renommé, `docs/é.md` ajouté | les deux chemins du renommage et `docs/é.md` non échappé | N/A |
| Type strict | `palier: true`, `palier: 2.0` | `UsineErreur` nommant fichier, clé, valeur | N/A |
| Fichier illisible | YAML en cp1252, répertoire à la place du fichier | `UsineErreur` nommant le fichier | N/A |
| Clé dupliquée | `palier: 1` deux fois | `UsineErreur` nommant fichier, clé, ligne | N/A |
| CLI | `app` lève `UsineErreur("x")` | stderr contient `x`, code 1 | N/A |
| Commentaires | clé entre guillemets, clé `12:`, flow mapping, BOM, valeur avec ` #`, liste d'URL, bloc littéral `Note: …` | clés réelles détectées ; ni URL ni ligne de bloc comptées comme clés ; ` #` dans une valeur n'est pas un commentaire | N/A |

</frozen-after-approval>

## Code Map

- `.github/workflows/ci.yml:36-42` -- step lane : `head_ref` interpolé dans `run`.
- `.github/scripts/controle_lanes.py` -- `LANES` (lane 2), `_miroir_tests`, `fichiers_hors_lane`, `_fichiers_modifies`, `main`.
- `tests/depot/test_controle_lanes.py` -- réutiliser `lanes = _charger_script()` et les paramétrages existants.
- `src/usine/contrats/config.py` -- `ConfigChaine`.
- `src/usine/config/chargeur.py` -- `charger_yaml` : lecture, `yaml.safe_load`, `_chemin_cle`.
- `src/usine/config/commentaires.py` -- `cles_sans_commentaire` à réécrire, même signature `list[tuple[int, str]]`.
- `src/usine/cli.py` ; `pyproject.toml:31-32` -- point d'entrée.
- `pyproject.toml:117-246` -- contrats `forbidden`.
- `tests/depot/test_import_linter.py` -- réutiliser `_copie_du_depot`, `_lint_imports`.
- `tests/unit/config/test_chargeur.py`, `test_commentaires.py`, `tests/unit/test_cli.py` -- à compléter.

## Tasks & Acceptance

**Execution:**
- [x] `.github/workflows/ci.yml` -- passer la branche par `env` -- injection shell.
- [x] `.github/scripts/controle_lanes.py` + `tests/depot/test_controle_lanes.py` -- tests plats, cli lane 2, git `-z --no-renames quotepath=off`, branche mal formée ; tests du chemin `return 1` (monkeypatch de `_fichiers_modifies`) et d'un dépôt git temporaire.
- [x] `src/usine/contrats/config.py` -- `strict=True`.
- [x] `src/usine/config/chargeur.py` -- `OSError`/`UnicodeDecodeError` et chargeur `SafeLoader` qui refuse les clés dupliquées.
- [x] `src/usine/cli.py`, `pyproject.toml` -- `main()` et script ; `uv sync` pour régénérer le lanceur.
- [x] `src/usine/config/commentaires.py` -- `yaml.compose` + repérage des commentaires hors scalaires.
- [x] `pyproject.toml` -- interdits externes par couche (liste blanche).
- [x] `tests/depot/test_import_linter.py` -- un seul `lint-imports` sur une copie où chaque couche source d'un contrat `forbidden` reçoit un module `violation.py` important tous ses modules interdits ; test paramétré par contrat (BROKEN + chaque `violation -> module`) ; test de classement des dépendances directes.
- [x] tests unitaires de la matrice I/O.

**Acceptance Criteria:**
- Given le dépôt corrigé, when `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest`, then tout passe.
- Given un module interdit retiré d'un contrat `forbidden`, when pytest tourne, then un test échoue.

## Implementation Notes

- `strict=True` ne suffit pas pour `palier: Literal[1, 2]` : pydantic-core accepte `True` et `2.0` (égaux à 1 et 2) même en mode strict, et `Strict()` ne s'applique pas à un `Literal`. `ConfigChaine.palier` ajoute donc un `BeforeValidator` qui exige un `int` exact ; le message garde fichier, clé et valeur.
- Les modules `usine.*.cli` (racines de composition) importent typer : chaque contrat qui ignorait déjà `usine.*.cli -> usine.**` ignore aussi `usine.*.cli -> typer` (et `usine.*.*.cli -> typer` pour `ia`).
- Univers externe classé dans `tests/depot/test_import_linter.py` (`MODULES_DES_DEPENDANCES`) : dépendances directes et groupes `dev`, `bonus` ; `pydantic-ai-slim` apporte `pydantic_ai`, `anthropic`, `mistralai` ; `types-pyyaml` n'a pas de module. `test_interdits_conformes_a_la_liste_blanche` recalcule les interdits attendus (tableau des couches + liste blanche) et compare à `pyproject.toml` : retirer un interdit fait échouer ce test.
- Les titres des contrats `rendu`, `adaptateurs`, `config`, `ui` nomment leurs externes permis ; titres sans accent pour une sortie console sûre sous Windows.
- `cles_sans_commentaire` : jetons `yaml.scan` pour repérer les `#` hors scalaires ; l'en-tête d'un bloc littéral (`|  # commentaire`) est exclu de la couverture du jeton.

## Spec Change Log

## Review Triage Log

Passe 1 (blind-hunter, edge-case-hunter, verification-gap) :

| # | Finding | Verdict | Preuve | Route |
|---|---------|---------|--------|-------|
| 1 | Liste « blanche » = liste noire des dépendances directes : click, rich, openai, jinja2, requests… importables depuis le noyau | medium | `lint-imports` ne connaît que les modules nommés ; rien n'interdit un transitif | patch (test grimp : externes importés par couche ⊆ base + permis + stdlib) |
| 2 | Clé de fusion `<<` signalée comme clé sans commentaire | low | `_cles` liste toutes les clés de `MappingNode`, `<<` compris, alors que le chargeur accepte la fusion | patch |
| 3 | Clé `=` (étiquette `tag:yaml.org,2002:value`) construite avant `flatten_mapping` : YAML accepté par `safe_load` devient « illisible » | low | `construct_object` sur ce tag lève `ConstructorError` | patch |
| 4 | `lane/3-` (nom vide) acceptée par `^lane/(\d+)-` | low | regex | patch |
| 5 | Chemin git non UTF-8 : `UnicodeDecodeError` dans `_fichiers_modifies` | low | `encoding="utf-8"` strict | patch (`errors="surrogateescape"`) |
| 6 | Correctif d'injection de `ci.yml` sans test (intention : « chacun avec un test ») | medium | aucun test ne relit `ci.yml` | patch |
| 7 | Caractères invisibles littéraux (U+2028, U+2029, U+FEFF) dans `commentaires.py` et ses tests | low | fragiles à l'édition | patch (échappements) |
| 8 | Test git temporaire sensible à la config git globale (gpgsign, hooks) | low | `_git` n'isole pas la config | patch (`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_NOSYSTEM`) |
| 9 | Spine (AD-21, tableau des couches) non mis à jour : tests plats, `adaptateurs/cli` en lane 2, liste blanche externe | medium | `ARCHITECTURE-SPINE.md:289` | defer (artefact de planification → correct-course) |
| 10 | Découpage des lignes non-LF de `cles_sans_commentaire` non testé | low | tests en LF seulement ; `.gitattributes` force LF | defer (disposition du relecteur) |
| 11 | `cles_sans_commentaire` lève `yaml.YAMLError` sur YAML invalide | low | seuls appelants : tests, échec bruyant | rejeté |
| 12 | `include-group` / `optional-dependencies` non gérés | false | absents de `pyproject.toml` ; échec bruyant si ajoutés | rejeté |
| 13 | `source_modules[0]` seul vérifié | false | le contrat hors produit partage une liste ; `test_chaque_interdit_casse_son_contrat` couvre chaque source | rejeté |
| 14 | `usine.*.*.cli -> typer` absent hors `ia` | low | aucun cli imbriqué hors `ia/agent` aujourd'hui (même limite préexistante pour `usine.**`) | rejeté |
| 15 | Assertion « copie saine passe » supprimée | false | l'étape CI `lint-imports` tourne sur le dépôt réel | rejeté |
| 16 | `strict=True` gênera de futurs champs (Path, date…) | false | exigé par l'intention ; un seul champ aujourd'hui | rejeté |
| 17 | Listes interdites recopiées dans 11 contrats | low | dérive attrapée par `test_interdits_conformes_a_la_liste_blanche` | rejeté |
| 18 | `test_main_traduit_une_usine_erreur` remplace `app` par un stub | low | `Typer.__call__` 0.27.3 relance l'exception (vérifié par verification-gap) | rejeté |
| 19 | `UsineErreur` à l'import des sous-applications hors `try` | false | aucun chargement au niveau module | rejeté |
| 20 | `core.quotepath=off` redondant avec `-z` | low | exigé par l'intention | rejeté |
| 21 | `lane/9-x` sans message | false | `main` affiche « lane 9 inconnue » et renvoie 1 | rejeté |
| 22 | Test plat racine `tests/unit/test_ia.py` pour une lane qui possède un répertoire | low | sans effet nuisible | rejeté |
| 23 | Erreur non UTF-8 sans numéro de ligne | low | cosmétique | rejeté |

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest` -- expected: tout vert.
- `uv run usine --help` -- expected: code 0 via `usine.cli:main`.
