---
title: "Story 7.4 : Avant / après"
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '45db0b02ea5f5bc38bba270a036c7913acb9b527'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-7-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-7-3-lancement-de-la-chaine-et-progression.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** L'écran « Avant / après » n'est qu'un emplacement (« Écran livré par la Story 7.4 »). Le Sponsor ne voit pas le gain de temps entre le reporting manuel et la Chaîne, argument central de la démo (Story 7.4, FR-44, AD-8, AD-19, Q-5).

**Approach:** Livrer `config/demo.yaml` (clé `temps_manuel_minutes_par_rapport`, modèle gelé `contrats.config.ConfigDemo`, valeur fictive commentée), deux services dans `ui/cli.py` (lecture de cette configuration et des deux derniers manifestes), un module pur `ui/avant_apres.py` qui rend le tableau, et l'écran dans `app.py`.

## Boundaries & Constraints

**Always:**
- **Configuration.** `config/demo.yaml` contient `temps_manuel_minutes_par_rapport: 120`, commenté en français comme valeur déclarative fictive (Q-5). `ui/cli.py` le lit par `config.charger_yaml(racine / "config" / "demo.yaml", ConfigDemo)`. Il renvoie `None` si le fichier est absent, et laisse remonter l'`UsineErreur` de `charger_yaml` si le fichier est invalide (fichier, clé, valeur).
- **Mesure.** Le temps mesuré vaut `horodatage_fin − horodatage_debut` du manifeste rendu par `dernier_passage(sans_classification_initiale=True)` sous `racine/sorties/passages/`. Il s'affiche par `progression.texte_duree` (`3,4 s`). Le temps manuel s'affiche en minutes entières par `formater_entier` (`120 min`). Le cumul vaut 5 fois chaque valeur (`NB_RAPPORTS_CUMUL = 5`).
- **Tableau Markdown** (deux lignes, aucun gain ni ratio calculé) :
  `| Rapport | Reporting manuel (déclaré) | Chaîne (mesuré) |`, puis `| Par Rapport quotidien | 120 min | 3,4 s |` et `| Cumulé sur 5 Rapports | 600 min | 17 s |`. En légende : la Date d'arrêté (`formater_date`) et le `passage_id` mesurés, puis la mention « Temps manuel : valeur déclarative fictive (`config/demo.yaml`, Q-5). »
- **Seule une classification initiale.** S'il existe au moins un Passage publié mais aucun sans classification initiale, l'écran affiche `SEULE_CLASSIFICATION_INITIALE` (avertissement) et aucun temps mesuré ni tableau.
- **Couches.** Seul `ui/cli.py` (racine de composition, exemptée par `ignore_imports`) importe `usine.config`, `usine.consultation` et `usine.ports`. `app.py` et `avant_apres.py` n'importent ni `ports`, ni `config`, ni `yaml`.
- **Tests** par `streamlit.testing.v1.AppTest` sur des racines temporaires (manifestes écrits à la main), et tests purs du module.

**Never:**
- Modifier `src/usine/contrats/`, `src/usine/ports/`, `pyproject.toml`, `uv.lock`, ou écrire hors de `src/usine/ui/`, `tests/unit/ui/` et `config/demo.yaml`.
- Lire `sorties/echecs/`, un répertoire `.en-cours-*` ou `entrepot.duckdb`.
- Afficher un temps mesuré tiré d'un Passage avec classification initiale.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Nominal | demo.yaml 120 ; Passage sans CI de 3,4 s | tableau 120 min / 3,4 s et 600 min / 17 s | N/A |
| CI plus récent | Passage CI récent + ancien sans CI | durée de l'ancien Passage sans CI | N/A |
| Seule CI | un seul Passage, `classification_initiale = true` | `SEULE_CLASSIFICATION_INITIALE`, aucun tableau | N/A |
| Aucun Passage | `sorties/passages/` vide ou absent | info « Aucun Passage publié : lancer la Chaîne pour mesurer son temps. » | N/A |
| Config absente | pas de `config/demo.yaml` | avertissement nommant `config/demo.yaml` et la clé, aucun tableau | N/A |
| Config invalide | `temps_manuel_minutes_par_rapport: 0` | `st.error` avec le message de `charger_yaml` | pas d'exception |
| Racine introuvable | racine absente | même message que la carte | pas d'exception |

</intent-contract>

## Code Map

- `src/usine/contrats/config.py:489` -- `ConfigDemo` gelé, `temps_manuel_minutes_par_rapport: int > 0` (lecture seule).
- `src/usine/config/chargeur.py:75` -- `charger_yaml` : message d'erreur fichier/clé/valeur (réutiliser).
- `src/usine/consultation/passage.py:232` -- `dernier_passage(sans_classification_initiale)` (lecture seule).
- `src/usine/contrats/passage.py:88` -- `ManifestePassage` (`horodatage_debut`, `horodatage_fin`, `classification_initiale`, `passage_id`, `date_arrete`).
- `src/usine/ui/cli.py:43` -- `consultation_dernier_passage` : modèle des services ; ajouter `config_demo(racine)` et `manifestes_avant_apres(racine) -> (dernier sans CI, dernier tous Passages)`.
- `src/usine/ui/progression.py:136` -- `texte_duree` (réutiliser).
- `src/usine/ui/navigation.py:22` -- retirer `Ecran.avant_apres` de `STORY_A_VENIR`.
- `src/usine/ui/app.py:148,330` -- `afficher_a_venir` et `principal` : brancher `afficher_avant_apres(racine)`. Le message « Racine introuvable » de `_lecture` est à factoriser.
- `tests/unit/ui/test_app.py:126` -- `test_navigation` : l'écran avant / après n'est plus un emplacement.
- `tests/unit/ui/test_navigation.py:28` -- attendu de `STORY_A_VENIR`.
- `tests/unit/ui/conftest.py` -- `racine_publiee` copie `config/` du dépôt, donc `demo.yaml`.
- `tests/unit/config/test_commentaires.py` -- impose un commentaire sur chaque clé des YAML livrés.

## Tasks & Acceptance

**Execution:**
- `config/demo.yaml` -- clé commentée, valeur fictive 120.
- `src/usine/ui/cli.py` -- `config_demo`, `manifestes_avant_apres`.
- `src/usine/ui/avant_apres.py` -- `NB_RAPPORTS_CUMUL`, `SEULE_CLASSIFICATION_INITIALE`, `duree_mesuree`, `tableau_avant_apres`, `legende`.
- `src/usine/ui/navigation.py`, `src/usine/ui/app.py` -- écran branché selon la matrice.
- `tests/unit/ui/test_avant_apres.py` -- fonctions pures (durée, tableau, cumul).
- `tests/unit/ui/test_cli.py` -- `config_demo` (absent, valide, invalide) et `manifestes_avant_apres` (CI exclu).
- `tests/unit/ui/test_app.py`, `test_navigation.py` -- matrice I/O par `AppTest`.

**Acceptance Criteria:**
- Given le dépôt, when `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest -q`, then tout passe.
- Given `racine_publiee` (vraie Chaîne, `config/demo.yaml` du dépôt), when le Pilote ouvre « Avant / après », then le tableau affiche 120 min et 600 min, et la légende cite le 09/10/2026.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 22 findings — high 0, medium 0, low 15, false 7, maybe-false 0
- findings:
  - `[low]` `[patch]` (edge) `OSError` (droits) au parcours de `sorties/passages` non intercepté — `_passage_mesure` intercepte `(UsineErreur, OSError)` ; test `test_avant_apres_passages_illisibles`.
  - `[low]` `[reject]` (edge) Deux parcours de `dernier_passage` non atomiques — publication pendant l'affichage rare ; la relance suivante corrige ; un parcours unique réimplémenterait `dernier_passage`.
  - `[low]` `[reject]` (edge) Lien symbolique cassé vu comme « Configuration absente » — cas improbable dans un dépôt de démo, garde supplémentaire.
  - `[low]` `[reject]` (edge) Durée < 0,05 s affichée « 0 s » — format imposé (`texte_duree`, 7.3) ; une vraie Chaîne dure plusieurs secondes.
  - `[low]` `[patch]` (verification-gap) Branche `except UsineErreur` inatteignable et non testée — même correctif que la première ligne.
  - `[low]` `[patch]` (blind) Cumul extrapolé présenté sous « Chaîne (mesuré) » — légende complétée par `MENTION_CUMUL` « Cumul : 5 × le temps d'un Rapport. ».
  - `[false]` `[reject]` (blind) `config_demo` contourne `MODELES` — `charger_yaml` est l'API publique de `usine.config` ; `MODELES` est hors lane et sans usage ici.
  - `[low]` `[patch]` (blind) Chemin `config/demo.yaml` écrit deux fois — `config_demo` lit `racine / avant_apres.FICHIER_CONFIG`.
  - `[low]` `[reject]` (blind) Double parcours des Passages — doublon du rejet edge ci-dessus.
  - `[false]` `[reject]` (blind) Durée négative possible — `ManifestePassage._coherence` refuse `horodatage_fin < horodatage_debut`.
  - `[low]` `[reject]` (blind) Unités différentes (min / s) — format fixé par la spec ; la différence d'ordre de grandeur est le message de la démo.
  - `[low]` `[patch]` (blind) Branche d'erreur de lecture non testée — même correctif que la première ligne.
  - `[low]` `[patch]` (blind) Erreur de configuration sans préfixe — « Configuration de la démo invalide : … ».
  - `[low]` `[reject]` (blind) Aides de test importées d'un autre module de test — `tests` est déjà un paquet importé ainsi (`tests.unit.chaine.environnement`) ; déplacement sans gain.
  - `[low]` `[reject]` (blind) `test_aucun_gain_ni_ratio` limité au tableau — la légende est figée par `test_legende` au texte exact.
  - `[low]` `[reject]` (blind) `questions_repli` absent de `demo.yaml` — clé des Stories 7.6/7.11, défaut `()`.
  - `[false]` `[reject]` (intent) Cumul : somme de 5 Passages réels plutôt que 5 × un Passage — le critère mesure « le dernier Passage » ; le cumul porte sur ce temps.
  - `[low]` `[reject]` (intent) « Semaine » absente de l'écran — le critère dit « cumulé sur 5 Rapports », libellé repris tel quel.
  - `[false]` `[reject]` (intent) Gain non affiché — contrainte « aucun chiffre dérivé dans l'UI » ; les deux temps côte à côte répondent au critère.
  - `[false]` `[reject]` (intent) « Réussi » non filtré — un Passage en échec va sous `sorties/echecs/`, jamais sous `sorties/passages/`.
  - `[false]` `[reject]` (intent) Commentaire de `demo.yaml` non testé — `tests/unit/config/test_commentaires.py` parcourt tous les YAML de `config/`.
  - `[false]` `[reject]` (intent) Tests par `AppTest` et non navigateur — moyen de test imposé par la consigne.

## Design Notes

**Clé de configuration.** La clé existe dans le contrat gelé `ConfigDemo` (contrats v1). Aucun modèle local n'est donc nécessaire : la consigne Q-5 ne prévoyait un modèle local que si la clé manquait. `ui` ne peut importer ni `yaml` ni `usine.config`, mais `ui/cli.py` le peut (racine de composition de la lane), comme pour `mode_repli`.

**Dérivations.** Le cumul ×5 et la différence fin − début sont exigés par le critère. Aucun gain ni ratio n'est calculé, pour respecter « aucun chiffre dérivé dans l'UI » au-delà du critère.

**Fichiers hors lane.** `tests/unit/contrats/test_config.py` (une ligne) : `test_yaml_livres_en_e0` fige la liste des YAML de `config/`. Livrer `config/demo.yaml` (fichier de L7) exige d'y ajouter `"demo.yaml"`, comme l'a fait la Story 1.6 pour `jira.yaml` (009d311). Ajout indispensable, non prévu au plan, hors de `src/usine/contrats/` et `src/usine/ports/`.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check .` -- expected: aucun écart.
- `uv run mypy` -- expected: aucune erreur.
- `uv run lint-imports` -- expected: tous les contrats KEPT.
- `uv run pytest -q tests/unit/ui tests/unit/config` puis `uv run pytest -q` -- expected: tout vert.

## Auto Run Result

Status: done

- **Résumé.** L'écran « Avant / après » affiche le temps de reporting manuel déclaré (`config/demo.yaml`, 120 min fictives, Q-5, modèle gelé `ConfigDemo`) à côté du temps mesuré de la Chaîne (`horodatage_fin − horodatage_debut` du dernier Passage publié sans classification initiale), par Rapport quotidien et cumulé sur 5 Rapports. Si seul un Passage avec classification initiale existe, un avertissement remplace le temps. Aucun gain ni ratio n'est calculé.
- **Fichiers.**
  - `config/demo.yaml` — clé commentée, valeur fictive.
  - `src/usine/ui/avant_apres.py` — module pur : tableau, légende, messages.
  - `src/usine/ui/cli.py` — `config_demo`, `manifestes_avant_apres`.
  - `src/usine/ui/app.py`, `navigation.py` — écran branché, message « Racine introuvable » partagé.
  - `tests/unit/ui/test_avant_apres.py`, `test_cli.py`, `test_app.py`, `test_navigation.py` — matrice I/O complète par `AppTest`.
  - `tests/unit/contrats/test_config.py` — hors lane, une ligne (voir Design Notes).
- **Revue (une passe, mode économique).** 22 constats : 6 patchés (tous `low`, regroupés en 4 correctifs : `OSError` intercepté et testé, mention du cumul en légende, chemin de configuration unique, préfixe de l'erreur de configuration), 0 différé, 16 rejetés (9 `low`, 7 `false` ; motifs dans le Triage Log).
- **Revue de suivi recommandée :** non (aucun `high` ni `medium` patché).
- **Vérification.** `ruff check`, `ruff format --check`, `mypy`, `lint-imports` (13 contrats KEPT), `pytest -q` : 2171 passed, 1 skipped.
- **Risques résiduels.** Le Mode repli n'a pas de traitement propre (Story 7.6). Les unités diffèrent (min / s). Une publication entre les deux lectures des Passages peut donner une paire incohérente le temps d'une exécution.
