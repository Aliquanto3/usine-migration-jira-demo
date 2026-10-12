---
title: 'Story 3.4 : Grille de météo complète et validation'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '9688d4d01624f95a9808c547f797bed210fe9210'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** `config/grille_meteo.yaml` ne porte que IND-1 (walking skeleton), et une Grille incohérente (orange plus sévère que rouge) est acceptée au chargement, ce qui produirait une Météo absurde (FR-15, FR-18).

**Approach:** Livrer la Grille par défaut complète (IND-1 à IND-8, PRD § 4.4, seuils en fractions de l'addendum D), commentée en français clé par clé ; ajouter au domaine une vérification pure de cohérence des seuils entre couleurs, appelée par la racine de composition juste après le chargement, avec un message nommant fichier, règle et valeur fautive.

## Boundaries & Constraints

**Always:** seuils au format existant `"<op> <décimal>"` (`>=` ou `>`), convertis en `Fraction` exacte par `contrats.config` ; un commentaire français non vide par clé (NFR-10, contrôlé par `tests/unit/config/test_commentaires.py`) ; vérification pure dans `domaine/meteo.py` (pas d'I/O, le nom du fichier arrive en paramètre `str`) ; toutes les règles vérifiées, actives ou non ; erreur `UsineErreur` en français ; `version_grille` = `contrats.versions.version_grille` des octets du fichier.

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` (gelés) ; calculer IND-2 à IND-8 (Story 3.5) ; activer dans le YAML livré un indicateur que `domaine/meteo.py` refuse encore (la Chaîne casserait) ; refuser des seuils égaux entre deux couleurs (FR-18 ne refuse que « plus sévère ») ; écrire hors lane au-delà de `src/usine/composition.py` et `tests/unit/test_composition.py`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Grille livrée | `config/grille_meteo.yaml` | 8 indicateurs aux seuils du PRD, garde-fous 20 et 5, IND-1 actif, IND-2 à IND-8 inactifs ; vérification sans erreur | — |
| Orange plus sévère | IND-1 rouge `>= 3`, orange `>= 4` | — | `UsineErreur` nommant le fichier, `IND-1`, `orange`, `>= 4` |
| Jaune plus sévère qu'orange | IND-3 orange `>= 10`, jaune `>= 12` | — | `UsineErreur` nommant `IND-3`, `jaune` |
| Paire non adjacente | jaune `>= 5`, rouge `>= 3`, sans orange | — | `UsineErreur` nommant `jaune` |
| Opérateur strict | orange `> 3`, rouge `>= 3` | — | refusé (orange plus sévère) |
| Opérateur strict inverse | orange `>= 3`, rouge `> 3` | acceptée | — |
| Seuils égaux | orange `>= 3`, rouge `>= 3` | acceptée | — |
| Règle inactive incohérente | `active: false`, orange > rouge | — | refusée aussi |
| Indicateur inconnu | clé `IND-9` | — | `UsineErreur` de `charger_yaml` nommant fichier et `IND-9` |
| Couleur inconnue | seuil `violet` | — | `UsineErreur` nommant fichier et `violet` |
| Seuil décimal | `">= 0.20"` | `(Operateur.superieur_ou_egal, Fraction(1, 5))` | — |
| Chargement réel | racine dont la Grille a orange > rouge | `composition.construire_rapport` lève avant tout Passage | `UsineErreur` nommant le chemin du fichier |

</intent-contract>

## Code Map

- `config/grille_meteo.yaml` -- à compléter ; forme imposée par `GrilleMeteo` (`src/usine/contrats/config.py:183`, lecture seule) : `version`, `couleurs`, `regle_agregation`, `garde_fous`, `indicateurs.<IND-n>.{libelle, active, seuils}`.
- `src/usine/contrats/config.py:144-180` -- `_analyser_seuil` (regex `>=|>` + décimal → `Fraction`), `RegleIndicateur` (refuse seuil vert, seuils vides) : déjà la conversion exacte ; lecture seule.
- `src/usine/contrats/meteo.py:16` -- `Couleur` ordonnée (`rang`), `CodeIndicateur`, `Operateur` ; lecture seule.
- `src/usine/domaine/meteo.py` -- ajouter `verifier_grille` ; `_COULEURS_DE_REGLE` (l. 38) et `_indicateurs_actifs` (l. 53, refuse tout actif ≠ IND-1) à laisser en place.
- `src/usine/config/chargeur.py:94` -- `charger_yaml` : erreurs Pydantic → `UsineErreur` « <fichier> : clé « indicateurs.IND-9.[key] », valeur 'IND-9' refusée » (inconnus déjà refusés).
- `src/usine/composition.py:214-215` -- seul site de chargement de la Grille (`charger_yaml(chemin_grille, GrilleMeteo)`) ; hors lane.
- `tests/unit/chaine/environnement.py:21` -- `preparer_racine` copie `config/` du dépôt : la Grille livrée tourne dans tous les tests de Chaîne.
- `tests/unit/domaine/test_meteo.py:57` -- `test_grille_livree` suppose IND-1 seul : à réécrire ; `_grille()` (l. 42) réutilisable.
- `tests/unit/test_composition.py:16` -- fixture `racine` (Palier 1, sans Journal ; la Grille est chargée avant le Journal).

## Tasks & Acceptance

**Execution:**
- `config/grille_meteo.yaml` -- Grille par défaut complète : IND-1 `>= 3`/`>= 1` ; IND-2 `> 10`/`> 5` ; IND-3 `>= 20`/`>= 10`/`>= 5` ; IND-4 `>= 0.20`/`>= 0.10`/`>= 0.05` ; IND-5 rouge `>= 1` ; IND-6 orange `>= 2`, jaune `>= 1` ; IND-7 orange `> 1.5`, jaune `> 1.0` ; IND-8 orange `>= 0.05`, jaune `>= 0.03` ; IND-1 `active: true`, autres `active: false` avec commentaire expliquant l'activation ; un commentaire par clé -- FR-15, NFR-10.
- `src/usine/domaine/meteo.py` -- `verifier_grille(grille: GrilleMeteo, source: str) -> GrilleMeteo` : pour chaque indicateur et chaque paire de couleurs présentes (moins grave, plus grave), refuse si le seuil moins grave est strictement plus sévère ; renvoie la Grille -- FR-18.
- `src/usine/composition.py` -- appeler `verifier_grille(grille, str(chemin_grille))` juste après `charger_yaml` -- vérification au chargement réel (hors lane).
- `tests/unit/domaine/test_meteo.py` -- réécrire `test_grille_livree` (8 seuils exacts, activations, garde-fous, `version_grille` 12 hex égal au SHA-256 du fichier, vérification sans erreur) ; un test par ligne de la matrice (inconnus via `charger_yaml` sur un YAML dans `tmp_path`).
- `tests/unit/test_composition.py` -- Grille incohérente dans la racine → `construire_rapport` lève `UsineErreur` nommant le fichier, `IND-1` et la valeur (hors lane).

**Acceptance Criteria:**
- Given `config/grille_meteo.yaml` livré, when il est chargé, then il porte les seuils IND-1 à IND-8 du PRD § 4.4, les garde-fous (20, 5), l'activation de chaque règle et un commentaire français par clé, et `version_grille` vaut le SHA-256 du fichier (12 hex).
- Given une Grille où le seuil orange d'IND-1 est plus sévère que le rouge, when la composition la charge, then une `UsineErreur` nomme le fichier, la règle et la valeur fautive.
- Given les cinq contrôles du dépôt, when on les lance, then ruff, ruff format, mypy, lint-imports et pytest passent.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 18 findings — high 0, medium 0, low 13, false 5, maybe-false 0
- findings:
  - `[low]` `[reject]` (blind) Vérification FR-18 sur le seul chemin `construire_rapport` (`charger_yaml`, `GrilleMeteo.model_validate` non vérifiés) — seul chargeur réel de la Grille (grep) ; le déplacer dans `contrats/config.py` est interdit (gelé) et l'intention autorise « dans le domaine » ; aucun autre appelant aujourd'hui.
  - `[low]` `[reject]` (blind) Seuils égaux acceptés, couleur jamais affichée — choix écrit dans la spec (FR-18 ne refuse que « plus sévère ») ; la Météo reste juste (la plus grave l'emporte) ; le corriger reviendrait à éditer la spec.
  - `[low]` `[reject]` (blind) `> 3` contre `>= 4` refusé sur un indicateur entier alors qu'équivalent — cas rare ; le corriger demande de typer les indicateurs (entier ou taux), complexité non justifiée ; le message explique le refus.
  - `[low]` `[reject]` (blind) Valeur affichée normalisée (`0.2` au lieu de `0.20`) — la valeur est exacte et reconnaissable ; le texte brut n'est pas conservé par le modèle gelé.
  - `[low]` `[patch]` (blind) `.rstrip("0")` mort dans `_decimal_exact` — supprimé.
  - `[low]` `[reject]` (blind) Seule la première incohérence est signalée — usage courant : une correction à la fois ; collecter toutes les erreurs ajoute une structure pour un gain faible.
  - `[false]` `[reject]` (blind) Commentaire par clé non testé — faux : `tests/unit/config/test_commentaires.py::test_chaque_cle_des_yaml_livres_est_commentee[grille_meteo.yaml]` couvre chaque clé du fichier livré (passé).
  - `[low]` `[reject]` (blind) Test SHA-256 proche de l'implémentation — il fixe le critère d'acceptation sur le fichier livré ; `version_grille` est testé dans `tests/unit/contrats/test_versions.py`.
  - `[low]` `[patch]` (blind) `version: 1` non incrémentée malgré l'ajout de règles — groupé avec la ligne edge ci-dessous ; `version: 2`.
  - `[false]` `[reject]` (blind) « Les activer fait échouer la Chaîne » non testé — faux : `test_indicateur_non_implemente` vérifie le refus d'un IND-2 actif par `meteo` et `indicateurs`.
  - `[false]` `[reject]` (blind) Ratio infini d'IND-7 impossible en `Fraction` — faux : `_franchit` (`domaine/meteo.py`) traite `denominateur = 0` avec `numerateur > 0` comme franchi ; IND-7 se calcule en 3.5.
  - `[false]` `[reject]` (blind) Test de composition fragile (premier `replace`) — faux : IND-1 est la première règle, l'assertion préalable et celle sur `IND-1` dans le message échoueraient bruyamment après une réorganisation.
  - `[low]` `[patch]` (edge) `version: 1` non incrémentée — `config/grille_meteo.yaml` passé à `version: 2`.
  - `[low]` `[reject]` (edge) Grille construite hors composition non vérifiée — même cause que la première ligne blind.
  - `[low]` `[reject]` (edge, claim) `charger_yaml` accepte encore une Grille incohérente — même cause que la première ligne blind.
  - `[low]` `[reject]` (intent) Surface `usine.config` (AD-19) non couverte — même cause que la première ligne blind ; l'intention de l'appelant autorise la validation dans le domaine.
  - `[false]` `[reject]` (intent) Flottant YAML non quoté `0.20` non testé — faux comme défaut : un seuil sans opérateur est refusé par `_analyser_seuil` (format « <op> <décimal> »).
  - `[low]` `[reject]` (intent) IND-2 à IND-8 livrés inactifs (lecture « toutes actives ») — l'AC exige l'activation *de chaque règle* comme clé ; les activer avant leur calcul (3.5) casserait la Chaîne ; choix écrit dans les Design Notes.

## Design Notes

**Sévérité** : un seuil `(op, v)` se déclenche sur `[v, ∞)` (`>=`) ou `(v, ∞)` (`>`). Clé de sévérité `(v, 1 si op est > sinon 0)` : plus la clé est grande, plus le seuil est sévère. Une couleur moins grave est fautive si sa clé est strictement plus grande que celle d'une couleur plus grave de la même règle. Égalité acceptée (lecture littérale de FR-18).

**Message** (exemple) : `config/grille_meteo.yaml : règle IND-1 : seuil orange « >= 4 » plus sévère que le seuil rouge « >= 3 » (une couleur moins grave doit se déclencher avant une plus grave)`. Valeur affichée en décimal exact (`Fraction(1, 5)` → `0.2`).

**Unités** : taux et hausses en fractions (addendum D) : IND-4 `0.20` = 20 %, IND-8 `0.05` = +5 points.

**Activation** : IND-2 à IND-8 livrés `active: false` car `domaine/meteo.py` refuse encore tout indicateur actif non calculé ; la Story 3.5 les active en les calculant.

**Fichiers hors lane** : `src/usine/composition.py` (seul site de chargement de la Grille ; sans cet appel, FR-18 « au chargement » n'est pas tenu, et `contrats/config.py` est gelé) ; `tests/unit/test_composition.py` (test de cette surface).

## Verification

**Commands:**
- `uv run pytest -q tests/unit/domaine/test_meteo.py tests/unit/test_composition.py tests/unit/config` -- expected: tous verts
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: succès

## Auto Run Result

- **Résumé :** Grille de météo par défaut complète (IND-1 à IND-8 aux seuils du PRD § 4.4, en fractions ; garde-fous 20 et 5 ; `active` par règle, IND-1 seul actif jusqu'à la Story 3.5 ; commentaire français par clé ; `version: 2`) et vérification pure `verifier_grille` (FR-18) appelée au chargement par la composition : une couleur moins grave plus sévère qu'une plus grave est refusée par une `UsineErreur` nommant fichier, règle et seuils.
- **Fichiers :**
  - `config/grille_meteo.yaml` -- Grille complète commentée.
  - `src/usine/domaine/meteo.py` -- `verifier_grille` et ses aides `_severite`, `_decimal_exact`, `_ecrire_seuil`.
  - `src/usine/composition.py` -- appel de `verifier_grille` après `charger_yaml` (hors lane).
  - `tests/unit/domaine/test_meteo.py` -- `test_grille_livree` réécrit, tests de la matrice (incohérences, acceptations, inconnus, décimal exact).
  - `tests/unit/test_composition.py` -- refus d'une Grille incohérente par `construire_rapport` (hors lane).
- **Revue :** 18 findings ; 2 corrigés (patch, `low` : `version: 2`, `.rstrip` mort supprimé) ; 0 différé ; 16 rejetés (11 low, 5 false), motifs dans le Review Triage Log.
- **Revue de suivi recommandée :** non (patches : 0 high, 0 medium, 2 low).
- **Vérification :** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports` (13 contrats), `uv run pytest -q` (1278 passés, 1 sauté) : tous verts. Audit de matrice : chaque ligne couverte par un test passé.
- **Risques résiduels :** la vérification ne court que sur le chemin `construire_rapport` (seul chargeur actuel) ; un futur chargeur devra appeler `verifier_grille` ; IND-2 à IND-8 restent inactifs jusqu'à la Story 3.5 ; `version_grille` change avec le fichier.
- **Fichiers hors lane :** `src/usine/composition.py`, `tests/unit/test_composition.py` (voir Design Notes).
