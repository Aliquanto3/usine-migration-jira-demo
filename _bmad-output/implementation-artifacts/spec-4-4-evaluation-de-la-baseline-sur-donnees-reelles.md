---
title: 'Story 4.4 : Évaluation de la Baseline sur données réelles'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '2f4750adb938179743fb6aa5cca3088fd4eba951'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** FR-51 / SM-10 exigent de montrer que la Baseline (`domaine.prevision.baseline.prevoir_sortie`) bat une prévision naïve en score de Brier sur des données Jira réelles ; la Story 4.3 fournit les `SerieStock` du Public Jira Dataset mais rien ne les évalue.

**Approach:** Module `evaluation.zenodo.evaluation` : fonctions pures (échantillonnage des unités, cible, découpages, prédicteurs, mesures exactes) et CLI qui lit les Parquet de la 4.3, appelle `prevoir_sortie` telle quelle pour chaque unité et publie les mesures agrégées dans `evaluation/zenodo/resultats/evaluation.json` ; rapport documenté `evaluation/zenodo/RAPPORT.md`.

## Boundaries & Constraints

**Always:** protocole addendum § E et H-21 avec les valeurs par défaut : seuil = règle rouge IND-1 de la Grille par défaut (`>= 3`), horizon N = 10 Jours ouvrés, `ParametresBaseline()` par défaut ; unité = (série, premier Jour ouvré de chaque semaine ISO présent dans la série) où le stock déclenche la règle, avec au moins 20 Jours ouvrés d'historique (profondeur de fourchette) jusqu'à la date et la date + N présente dans la série ; cible = stock sous le seuil (règle non déclenchée) à au moins un des N Jours ouvrés suivants ; Baseline = `probabilite_numerateur / probabilite_denominateur` de la `Prevision` ; référence naïve = taux de la cible sur les unités d'entraînement du projet ; mesures exactes en `Fraction` (Brier, AUC Mann-Whitney avec ex aequo à 1/2, erreur absolue moyenne sur le stock à N) puis publiées arrondies à 6 décimales ; sortie déterministe.

**Never:** copie, variante ou réglage de la Baseline ou de ses paramètres pour l'évaluation (AD-18, SM-10) ; données du dump, Parquet ou résultats par unité dans le dépôt (seulement des agrégats) ; `evaluation/` lancé en CI (AD-20) ; réseau ou MongoDB dans les tests unitaires ; modifier `contrats/`, `ports/` ou `domaine/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Unité retenue | lundi, stock 4, 25 Jours ouvrés d'historique, série au-delà de lundi + 10 | une unité ; cible 1 si un stock < 3 dans les 10 Jours ouvrés suivants, sinon 0 | — |
| Stock sous le seuil | lundi, stock 2 | aucune unité | — |
| Historique court | lundi au 10ᵉ Jour ouvré de la série | aucune unité | — |
| Fin de série | lundi + 10 Jours ouvrés hors série | aucune unité | — |
| Semaine sans lundi ouvré | lundi férié | unité au mardi (premier Jour ouvré de la semaine) | — |
| Séries de fins différentes d'un même dépôt | série A finit avant la dernière date du dépôt | A prolongée jusqu'à la fin du dépôt, stock constant, Entrées et Sorties 0 | — |
| Projet sans unité d'entraînement | projet n'ayant que des unités de test | naïve = taux global d'entraînement | aucun entraînement du tout : `UsineErreur` |
| AUC d'une seule classe | toutes les cibles à 1 | AUC `null` publiée | — |
| Aucune unité | séries trop courtes | — | `UsineErreur` explicite, code de sortie 1 |

</intent-contract>

## Code Map

- `src/usine/domaine/prevision/baseline.py:85` -- `prevoir_sortie(serie, meteo, parametres)` ; exige une Météo rouge et une série dense finissant à D ; lecture seule. Probabilité et facteur `velocite_nette` (numérateur/dénominateur) sont lus dans la `Prevision` renvoyée.
- `src/usine/contrats/meteo.py:86,125` -- `RegleDeclenchante` (valide que la valeur franchit le seuil), `MeteoEntite` ; construction comme `tests/unit/evaluation/zenodo/test_conversion.py:274`.
- `src/usine/contrats/calendrier.py` -- `est_jour_ouvre`, `jours_ouvres` (prolongation des séries) ; `src/usine/domaine/prevision/commun.py` -- `declenche(valeur, operateur, seuil)`, réutilisable pour la cible.
- `config/grille_meteo.yaml:28` -- IND-1 rouge `>= 3` (valeur par défaut reprise en constante, pas de lecture de config).
- `evaluation/zenodo/conversion.py`, `chargement.py`, `README.md` -- 4.3 ; Parquet sous `usine-lanes/externe/series/` (Hyperledger, JFrog déjà produits ; Spring, IntelDAOS, SecondLife à produire avec `--priorite` du README).
- `.github/scripts/controle_lanes.py:59` -- lane 4 : `src/usine/domaine/prevision`, `evaluation` (+ `tests/unit/` correspondants).

## Tasks & Acceptance

**Execution:**
- `evaluation/zenodo/evaluation.py` -- dataclass `Unite` (serie, depot, date, stock, cible, stock_a_horizon) ; `prolonger_par_depot(series)` ; `unites(series, *, seuil, horizon, historique)` ; `decouper(unites)` (projets tenus à l'écart : sha256 du nom de série ≡ 0 mod 4 ; coupure temporelle par dépôt au 70ᵉ centile des dates d'unités non tenues à l'écart ; entraînement = unités dont date + N < coupure ; test temporel = date ≥ coupure) ; `predire_baseline(serie_projet, unite)` (appel de `prevoir_sortie`, probabilité et stock projeté max(0, S − v·N)) ; naïve (probabilité = taux d'entraînement du projet, repli taux global ; stock projeté = stock courant) ; `brier`, `auc`, `erreur_absolue_moyenne` ; `evaluer(series) -> dict` ; `main` : `python -m evaluation.zenodo.evaluation --series A.parquet … --sortie chemin.json`, imprime le résumé et un avertissement SM-10 si la Baseline ne bat pas la naïve en Brier sur un jeu de test.
- `tests/unit/evaluation/zenodo/test_evaluation.py` -- séries synthétiques construites en code ; une ligne de matrice par test ; mesures sur exemples calculés à la main ; espion prouvant que l'appel passe par `usine.domaine.prevision.baseline.prevoir_sortie` ; découpage déterministe ; CLI sur Parquet temporaires (succès, aucune unité).
- `evaluation/zenodo/resultats/evaluation.json` -- produit par le CLI sur les 5 dépôts restaurés (agrégats seulement).
- `evaluation/zenodo/RAPPORT.md` -- protocole retenu (choix ci-dessus), données, résultats par jeu de test pour les deux prédicteurs, verdict SM-10, limites ; lien depuis `evaluation/zenodo/README.md`.

**Acceptance Criteria:**
- Given les `SerieStock` Zenodo, when l'auteur lance le CLI, then chaque prédiction Baseline provient d'un appel à `domaine.prevision.baseline.prevoir_sortie` avec `ParametresBaseline()` (AD-18), comparée à la naïve sur un test temporel et un test de projets tenus à l'écart.
- Given l'évaluation terminée, when on lit `evaluation/zenodo/resultats/evaluation.json` et `RAPPORT.md`, then ils donnent Brier, AUC et erreur absolue moyenne sur le stock projeté pour la Baseline et la naïve, avec les effectifs.
- Given un Brier de la Baseline non meilleur, then le résultat est publié tel quel, l'écart est signalé (rapport et sortie du CLI) pour arbitrage de l'auteur (SM-10), sans retouche de la Baseline.
- Given les cinq contrôles et `controle_lanes.py --branche lane/4-zenodo --base main`, then tout passe sans fichier hors lane.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 28 findings — high 0, medium 2, low 19, false 7, maybe-false 0
- findings:
  - `[low]` `[patch]` (blind) prolongation par dépôt : unités négatives des projets à l'abandon, non mesurées — fidèle à l'historique (aucun événement, stock inchangé) ; limite et biais probable ajoutés à `RAPPORT.md` § Limites.
  - `[low]` `[reject]` (blind) naïve sans effectif minimal ni lissage — définition H-21 retenue par la spec (taux brut du projet) ; un lissage changerait la référence.
  - `[low]` `[patch]` (blind) `horizon`/`historique` dupliqués, `evaluer(horizon=5)` incohérent — constantes tirées de `ParametresBaseline()`, `evaluer` refuse un autre horizon, testé.
  - `[low]` `[patch]` (blind) aucune incertitude sur l'écart de Brier — pas de bootstrap (fonctionnalité additionnelle) ; limite explicite ajoutée au rapport.
  - `[low]` `[reject]` (blind) pas de ventilation par dépôt ou série des mesures — fonctionnalité additionnelle hors intention.
  - `[low]` `[patch]` (blind) résultat non traçable (version du dataset, `--priorite`, joker shell) — entrées du run et version Zenodo consignées dans `RAPPORT.md`.
  - `[low]` `[reject]` (blind) doublons ou trous non contrôlés à l'entrée — les Parquet 4.3 sont denses ; un doublon ou un trou fait échouer bruyamment la Baseline, nommant la série.
  - `[low]` `[patch]` (blind) CLI ne capture pas les erreurs polars — `PolarsError` capturée, code 1, testé.
  - `[medium]` `[patch]` (blind) tests manquants (avertissement SM-10 en sortie, cas calculé à la main) — même cause que les constats verification-gap ci-dessous ; tests ajoutés.
  - `[low]` `[reject]` (blind) avertissement SM-10 affiché en valeurs arrondies — cosmétique, ex aequo à 6 décimales improbable.
  - `[false]` `[reject]` (blind) semaine sautée si son premier Jour ouvré n'est pas rouge — échantillonnage voulu et spécifié (premier Jour ouvré de la semaine), décrit au rapport.
  - `[low]` `[reject]` (blind) Baseline revalide toute la série à chaque unité — run complet en 10 s.
  - `[low]` `[reject]` (edge) trous de Jours ouvrés non contrôlés — même rejet que la ligne « doublons ou trous ».
  - `[low]` `[reject]` (edge) même série dans deux Parquet — idem.
  - `[low]` `[reject]` (edge) doublon (série, date) dans la prolongation — idem.
  - `[low]` `[patch]` (edge) horizon différent de la Baseline — même correctif que plus haut.
  - `[low]` `[patch]` (edge) Parquet corrompu : exception polars — même correctif que plus haut.
  - `[low]` `[patch]` (edge) écriture du JSON hors du `try` — mkdir et écriture déplacés dans le `try`.
  - `[false]` `[reject]` (edge) `predire_baseline` renommé `predire_sortie` — imposé par `test_baseline_unique_ad_18` (AD-18) ; corriger = modifier la spec.
  - `[medium]` `[patch]` (verification-gap) verdict SM-10 et étiquettes Baseline/naïve non épinglés — `test_evaluer_calcule_a_la_main` (valeurs publiées calculées à la main) et cohérence verdict/Brier sur chaque jeu.
  - `[low]` `[patch]` (verification-gap) affichage CLI de l'avertissement SM-10 non testé — `test_cli_succes` et `test_cli_avertissement_sm10`.
  - `[low]` `[patch]` (verification-gap) exclusion des projets tenus à l'écart du calcul de coupure non épinglée — `test_decoupage` place six unités tenues à l'écart au dernier lundi.
  - `[low]` `[patch]` (intent) unités sur dates prolongées — même entrée que la première ligne.
  - `[false]` `[reject]` (intent) naïve globale pour les projets tenus à l'écart — l'historique d'un projet tenu à l'écart est par définition indisponible ; choix consigné au rapport.
  - `[false]` `[reject]` (intent) stock projeté recalculé hors Baseline — la `Prevision` ne porte pas de stock projeté ; S − v·N à partir de son facteur vélocité est la projection définie par l'addendum.
  - `[false]` `[reject]` (intent) seuil `>= 3` commun — valeur par défaut de la Grille, limite consignée.
  - `[false]` `[reject]` (intent) 5 dépôts sur 16 — périmètre de la 4.3, limite consignée.
  - `[false]` `[reject]` (intent) signalement à l'auteur seulement dans l'artefact — rapport, sortie CLI et journal du run (intégration) ; pas d'autre canal prévu dans la lane.

## Design Notes

**Choix de protocole (H-21, valeurs par défaut).** L'addendum laisse ouverts le seuil, le jour d'échantillonnage, la coupure et le repli de la naïve ; chaque choix ci-dessus est le plus simple fidèle au texte et est consigné dans le rapport. La naïve d'un projet tenu à l'écart ne peut pas lire l'historique de ce projet : elle prend le taux global d'entraînement. Les entraînements dont la cible chevauche la coupure sont purgés pour éviter toute fuite.

**Stock projeté.** Baseline : S − v·N borné à 0, v = facteur `velocite_nette` de la `Prevision` ; naïve : persistance (stock courant) ; vérité : stock à date + N.

**Prolongation.** Sans `--fin`, la 4.3 arrête chaque série à son dernier événement ; l'évaluation la prolonge jusqu'à la dernière date du dépôt (le stock ne bouge plus), ce qui évite d'exclure les unités en fin de série.

## Verification

**Commands:**
- `uv run pytest -q tests/unit/evaluation` -- expected: tous verts.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: verts.
- `uv run python -m evaluation.zenodo.evaluation --series ../externe/series/*.parquet --sortie evaluation/zenodo/resultats/evaluation.json` -- expected: code 0, JSON produit.

## Auto Run Result

Status: done (revue unique en mode économique, sans revue de suivi).

**Livré.** Module `evaluation.zenodo.evaluation` (unités hebdomadaires, cible, découpage temporel et projets tenus à l'écart, Baseline appelée telle quelle via `prevoir_sortie` et `ParametresBaseline()`, référence naïve H-21, Brier, AUC, erreur absolue moyenne exacts) et CLI ; évaluation réelle sur les 5 dépôts restaurés (93 séries, 5 157 unités) publiée en agrégats.

**Résultats (SM-10).** Test temporel : Brier Baseline 0,011922 contre naïve 0,013638 (gagné). Projets tenus à l'écart : 0,047625 contre 0,045207 (**perdu**) ; publié tel quel, signalé à l'auteur pour arbitrage, Baseline non retouchée. AUC Baseline 0,66 / 0,64 contre 0,40 / 0,50.

**Fichiers.**
- `evaluation/zenodo/evaluation.py` : protocole, prédicteurs, mesures, CLI.
- `tests/unit/evaluation/zenodo/test_evaluation.py` : matrice, mesures calculées à la main, espion AD-18, CLI.
- `evaluation/zenodo/resultats/evaluation.json` : agrégats du run réel.
- `evaluation/zenodo/RAPPORT.md` : protocole, données, résultats, verdict SM-10, limites.
- `evaluation/zenodo/README.md` : lien vers le rapport.

**Écart à la spec.** `predire_baseline` s'appelle `predire_sortie` : `test_baseline_unique_ad_18` interdit tout `def *baseline*` hors du domaine.

**Revue.** 28 constats : corrections appliquées pour 1 entrée medium (tests du verdict SM-10, de l'avertissement CLI, de la coupure) et 6 entrées low (horizon dérivé de la Baseline et contrôlé, erreurs polars et d'écriture capturées, rapport : prolongation, incertitude, traçabilité) ; 0 reporté ; rejets motivés au Review Triage Log.

**Revue de suivi recommandée :** false (patchés : high 0, medium 1, low 6).

**Vérification.** `pytest` complet 2 264 verts ; ruff, ruff format, mypy, lint-imports verts ; CLI réel relancé après correctifs, mêmes chiffres. `mongod` arrêté proprement après production des Parquet.

**Risques résiduels.** Prolongation des séries (unités négatives de projets inactifs, part non mesurée) ; aucune incertitude statistique ; 5 dépôts sur 16 ; seuil de 3 commun à tous les projets.
