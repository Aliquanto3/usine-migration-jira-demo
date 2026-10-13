---
title: 'Story 4.7 : [BONUS] Facteurs explicatifs du Modèle ML'
type: 'feature'
created: '2026-10-13'
status: 'review'
baseline_revision: 'a/4-7 depuis 4.6'
context: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** FR-23 / AD-18 : une `Prevision` `methode=ml` doit être défendable devant un Sponsor bancaire, avec au plus 5 facteurs en mots simples.

**Approach:** les contributions de variables de LightGBM (`pred_contrib`, log-cotes, sans SHAP) deviennent des `FacteurExplicatif` libellés en français par `domaine.prevision.ml`.

## Boundaries & Constraints

**Always:** `FacteurExplicatif` existe déjà (contrats inchangés) ; au plus 5 facteurs, classés par |contribution| décroissante puis nom, contributions nulles écartées ; valeur = contribution arrondie au millième (numérateur/dénominateur exacts), signe positif = favorise la sortie du rouge ; libellé « <variable en français> : favorise|freine la sortie du rouge » ; une variable sans libellé français est refusée (`UsineErreur`) : garde-fou SM-C4, un gain d'AUC obtenu avec une variable qu'on ne sait pas dire n'est pas retenu ; une Prévision `regle_non_projetable` n'a pas de facteurs.

**Never:** modifier `contrats/` ou `ports/` ; ajouter SHAP ; changer le modèle, ses paramètres ou ses mesures (SM-8 de la 4.6 inchangé).

## Code Map

- `src/usine/domaine/prevision/ml.py` -- `libelle_variable`, `facteurs_depuis_contributions`, paramètre optionnel `contributions` de `prevoir_sortie_ml`.
- `evaluation/zenodo/modele_ml.py` -- `contributions_variables` (`pred_contrib`, hors biais), branché dans `prevoir_entites`.
- Tests : `tests/unit/domaine/prevision/test_ml.py`, `tests/unit/evaluation/zenodo/test_modele_ml.py` (additivité contributions + biais = score brut).

## Acceptance (vérifiée)

- Given une `Prevision` ml via `prevoir_entites`, then 1 à 5 facteurs en français, additivité des contributions vérifiée contre `raw_score`.
- Given plus de 5 contributions, then les 5 plus fortes en valeur absolue ; nulles écartées ; variable inconnue refusée.

## Reports

- Contributions en log-cotes d'une bloquante : l'effet sur la probabilité d'Entité (agrégation binomiale) n'est pas décomposé.
- `predire_ml` (évaluation SM-8) ne calcule pas les facteurs ; `pred_contrib` n'y est exercé qu'en test.
- Affichage des facteurs ML dans les rendus : Epic 5.

## Verification

- `uv run pytest -q tests/unit/domaine/prevision/test_ml.py tests/unit/evaluation/zenodo/test_modele_ml.py`
