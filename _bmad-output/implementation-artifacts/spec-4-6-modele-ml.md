---
title: 'Story 4.6 : Modèle ML validé sur données réelles'
type: 'feature'
created: '2026-10-13'
status: 'review'
baseline_revision: '962ff54'
context: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** FR-22 / SM-8 : un Modèle ML doit prédire la résolution des bloquantes sous N Jours ouvrés, battre la Baseline en AUC et Brier sur le jeu tenu à l'écart du Public Jira Dataset, et produire une `Prevision` `methode=ml`.

**Approach:** `domaine.prevision.ml` (pur, sans numpy) agrège la probabilité p d'une bloquante en `Prevision` ; `evaluation.zenodo.modele_ml` (hors CI) entraîne LightGBM selon le protocole de la 4.4 et mesure Modèle ML, Baseline (`prevoir_sortie` telle quelle) et naïve sur les mêmes unités.

## Boundaries & Constraints

**Always:** `MethodePrevision.ml` existe déjà (contrats inchangés) ; N = 10 (horizon de la Baseline) ; agrégation de l'addendum : P(sortie) = P(Binomiale(S, p) ≥ k), k = plus petit nombre de résolutions qui sort S de la règle IND-1 rouge (S − 2 pour `>= 3`), résolutions **indépendantes** de même p, aucune Entrée nouvelle dans l'horizon (hypothèses documentées dans le module) ; probabilité exacte en `Fraction`, publiée avec dénominateur ≤ 10⁶ ; « sortie projetée » dès 1/2, date estimée = fin de l'horizon (le ML prédit une probabilité à N, pas une date) ; mêmes unités, découpage, projets tenus à l'écart et mesures que la 4.4 ; entraînement déterministe (graine 42, un thread) ; aucun réglage sur le jeu de test.

**Never:** modifier `contrats/`, `ports/` ou la Baseline ; données ou résultats par unité dans le dépôt ; LightGBM dans `domaine/` (import-linter) ; lancer `evaluation/` en CI ; facteurs explicatifs (Story 4.7).

## Code Map

- `src/usine/domaine/prevision/ml.py` -- `resolutions_requises`, `probabilite_sortie`, `prevoir_sortie_ml(meteo, p, horizon)`.
- `evaluation/zenodo/modele_ml.py` -- caractéristiques (stock, Entrées/Sorties 5/10/20 jours, variation 10 jours, maximum 20 jours), `entrainer`, `prevoir_entites`, `evaluer_ml`, CLI.
- `evaluation/zenodo/evaluation.py` -- seul ajout : alias public `meteo_de_unite`.
- `tests/unit/domaine/prevision/test_ml.py`, `tests/unit/evaluation/zenodo/test_modele_ml.py` -- valeurs binomiales calculées à la main, données synthétiques ; tests `lent` pour les Scénarios de démo.

## Acceptance (vérifiée)

- Cible d'entraînement : les `SerieStock` n'ont pas de ticket individuel ; pour un jour de stock S ≥ 1, part du stock résolue sous N, min(ΣSorties, S)/S, perte `cross_entropy` pondérée par S, sur les jours des projets non tenus à l'écart dont date + N précède la coupure du dépôt.
- Given les Parquet réels, when `modele_ml` s'exécute (33 s), then SM-8 ci-dessous. Given le Passage de démo (graine 42, D = 2026-10-09) et le modèle réel, then A `sortie_projetee` (p = 0,898), B `pas_de_sortie_projetee` (p = 0,320).

## Résultats SM-8 (5 dépôts, 93 séries, entraînement 2 743 unités)

| Jeu | Effectif (positifs) | Prédicteur | Brier | AUC |
|---|---|---|---|---|
| Projets tenus à l'écart | 1 203 (57) | **ML** | **0,041452** | **0,852684** |
| | | Baseline | 0,047625 | 0,637657 |
| | | Naïve | 0,045207 | 0,5 |
| Test temporel | 1 191 (15) | ML | 0,014966 | 0,88305 |
| | | **Baseline** | **0,011922** | 0,657653 |
| | | Naïve | 0,013638 | 0,400879 |

**Verdict :** sur le jeu de projets tenus à l'écart (SM-8), le ML bat la Baseline en AUC et en Brier. Sur le test temporel, il la bat en AUC mais pas en Brier (0,0150 contre 0,0119) ; publié tel quel, à arbitrer par l'auteur, sans réglage.

## Reports

- Écart de Brier temporel : seulement 15 positifs, sans intervalle de confiance (comme en 4.4) ; calibration (Platt/isotonique) à envisager, non faite.
- Date de sortie ML : fin de l'horizon faute de modèle de date ; fourchette optimiste/pessimiste non produite.
- p identique pour toutes les bloquantes d'une Entité (indépendance) ; cible approchée sans suivi par ticket (les Sorties peuvent viser des bloquantes entrées dans l'horizon).
- Facteurs explicatifs : Story 4.7. Branchement du ML dans la Chaîne (`EtapePrevision`) : hors périmètre, le modèle n'est pas versionné.
- Test des Scénarios de démo avec le modèle réel : `lent` et conditionné à `USINE_SERIES_REELLES`.

## Verification

- `uv run pytest -q tests/unit/domaine/prevision/test_ml.py tests/unit/evaluation/zenodo/test_modele_ml.py`
- `uv run python -m evaluation.zenodo.modele_ml --series ../externe/series/*.parquet --sortie evaluation/zenodo/resultats/modele_ml.json`

## Revue

- `[medium]` corrigé : `prevoir_entites` levait `KeyError`/`ValueError` (Entité ou Date d'arrêté absente de la série) au lieu d'une `UsineErreur` ; test ajouté.
- `[low]` rejeté : projets tenus à l'écart testés sur des dates qui chevauchent l'entraînement des autres projets du même dépôt, c'est le protocole 4.4 imposé (même découpage).
- `[low]` rejeté : cible d'entraînement approchée (Sorties pouvant viser des bloquantes entrées dans l'horizon), déjà en Reports.
- Sans constat : fuite temporelle (caractéristiques rétrospectives, purge date + N < coupure), graine/un thread, agrégation binomiale (k = S − 2) et indépendance conformes, `Prevision` ml valide, Baseline et contrats intacts, lightgbm hors domaine.
