---
title: "Story 4.2 : Risque d'entrée en rouge"
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '3c9521f1cb7f0c3002924ea523bb48bfad5748bb'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
warnings: [oversized]
deferred:
  - summary: >-
      La valeur projetée et le motif d'exclusion d'IND-4 ne figurent pas dans le contrat gelé `RisqueEntreeRouge`.
    evidence: |-
      `RisqueEntreeRouge.numerateur/denominateur` porte la valeur courante (docstring du contrat gelé, contrats-v1) et aucun champ ne reçoit la valeur projetée ni les indicateurs écartés. Le domaine les rend à côté (`RisqueProjete.valeur_projetee`, `ResultatRisque.exclus`) ; les publier dans `previsions.json` (étape `prevision`, L5) exige un champ de contrat par PR dédiée sur main (contrats-v2).
    location: >-
      src/usine/contrats/prevision.py (RisqueEntreeRouge)
    severity: medium
  - summary: >-
      Le paramètre H-8 (fenêtre 10, horizon 5) n'est pas lu dans la configuration de la Chaîne.
    evidence: |-
      `contrats/config.py` est gelé (AD-19) ; `risques_entree_rouge` reçoit un `ParametresRisque` à valeurs par défaut, comme `ParametresBaseline` en Story 4.1. Branchement par PR courte sur main lors de l'intégration de l'étape `prevision` (L5).
    location: >-
      src/usine/domaine/prevision/risque.py
    severity: low
  - summary: >-
      `domaine/meteo.py` garde sa propre comparaison de seuil (`_COMPARAISONS`), doublon de `prevision.commun.declenche`.
    evidence: |-
      `src/usine/domaine/meteo.py:57-60` compare `>=` / `>` comme `commun.declenche` ; le module appartient à la lane L3, hors périmètre d'écriture de L4. Une mise en commun (dans le domaine ou dans `contrats.meteo`) relève d'une story L3 ou d'une PR sur main.
    location: >-
      src/usine/domaine/meteo.py:57
    severity: low
---

<intent-contract>

## Intent

**Problem:** FR-21 n'a aucune implémentation : le Pilote n'est pas prévenu qu'une Entité non rouge risque de franchir un seuil rouge la semaine prochaine (H-8 : 5 Jours ouvrés).

**Approach:** une fonction pure `risques_entree_rouge(indicateurs, meteo, grille, parametres)` dans `src/usine/domaine/prevision/risque.py` : régression linéaire exacte (moindres carrés, `Fraction`) sur les 10 derniers Jours ouvrés d'IND-1, IND-3 et IND-4 de l'Entité, projetée de 1 à 5 Jours ouvrés après D ; un `RisqueEntreeRouge` par indicateur dont une projection déclenche la règle rouge de la Grille, accompagné de la valeur projetée ; les indicateurs écartés (non évaluables sur la fenêtre, historique insuffisant, sans seuil rouge actif) sont restitués avec leur motif. Paramètres H-8 dans un `ParametresRisque` (fenêtre 10, horizon 5). Les primitives partagées avec la Baseline (avance de Jours ouvrés, test de déclenchement d'un seuil) passent dans un module commun (AD-18 : une seule implémentation par calcul).

## Boundaries & Constraints

**Always:** arithmétique exacte (`Fraction`) ; Jours ouvrés par `contrats.calendrier` seulement ; seuil et opérateur rouges lus dans `grille.indicateurs[code].seuils[Couleur.rouge]` ; `date_arrete`, `entite`, `version_grille` repris de la `MeteoEntite` ; `RisqueEntreeRouge.numerateur/denominateur` = valeur de l'indicateur à D (docstring du contrat gelé : « Valeur courante ») ; résultats dans l'ordre de `CodeIndicateur` ; fonction pure, déterministe, sans horloge ni hasard.

**Never:** modifier `src/usine/contrats/`, `src/usine/ports/`, `config/` ou la Chaîne ; seconde implémentation de la Baseline ou de la vélocité nette ; projeter un autre indicateur qu'IND-1, IND-3, IND-4 ; numpy ou flottants.

## I/O & Edge-Case Matrix

Table `SCHEMA_INDICATEUR` d'ENT-C sur 10 Jours ouvrés finissant à D ; Météo orange ; Grille par défaut (rouge : IND-1 `>= 3`, IND-3 `>= 20`, IND-4 `>= 1/5`) ; paramètres par défaut. x = 0..9 rang du Jour ouvré, projection à x = 9 + h, h = 1..5.

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Franchissement IND-3 | IND-3 = 10, 11, …, 19 | risque IND-3 : franchissement à D + 1 JO, valeur projetée 20, valeur courante 19/1, seuil 20/1 | — |
| Tendance non linéaire IND-1 | IND-1 = 0,0,0,0,0,1,1,1,2,2 | pente 41/165, ordonnée −23/55 ; h = 4 → 464/165 < 3 ; h = 5 → 101/33 ≥ 3 : risque IND-1 à D + 5 JO, valeur projetée 101/33 | — |
| Hausse insuffisante IND-4 | IND-4 = 5/100, …, 14/100 | h = 5 → 19/100 < 1/5 : aucun risque IND-4 | — |
| Stable ou en baisse | séries constantes ou décroissantes | aucun risque | — |
| IND-4 non évaluable en partie | IND-4 `non_evaluable` (0/0, motif m) sur un JO de la fenêtre | IND-4 exclu, motif nommant la première date et m ; IND-1 et IND-3 projetés | — |
| Historique court | 1 seul JO pour un indicateur | indicateur exclu (« historique insuffisant ») ; 2 à 9 JO : régression sur les JO présents | — |
| Indicateur inactif ou sans seuil rouge | IND-3 `active: false` ou sans seuil rouge | IND-3 exclu avec motif, sans lecture de la table | — |
| Entrées invalides | Météo rouge, D absente pour un indicateur actif, trou ou date non ouvrée, doublon, valeur évaluée de dénominateur 0, paramètre < 1 | — | `UsineErreur` nommant l'Entité et la cause |

</intent-contract>

## Code Map

- `src/usine/contrats/prevision.py` -- `RisqueEntreeRouge` (indicateur ∈ {IND-1, IND-3, IND-4}, `date_franchissement_estimee > date_arrete`, `numerateur/denominateur` = valeur courante, seuil, `horizon_jours_ouvres`, `version_grille`). Gelé.
- `src/usine/contrats/calcul.py:72` -- `SCHEMA_INDICATEUR` (date, entite, code, statut, motif, numerateur, denominateur, couleur) ; `StatutIndicateur.non_evaluable` = 0/0 avec motif. Gelé.
- `src/usine/contrats/config.py:167-205` -- `GrilleMeteo.indicateurs[code]` → `RegleIndicateur(active, seuils: Couleur → (Operateur, Fraction))`. Gelé.
- `src/usine/contrats/meteo.py` -- `MeteoEntite`, `CodeIndicateur`, `Couleur`, `Operateur`. Gelé.
- `src/usine/contrats/calendrier.py:48-64` -- `est_jour_ouvre`, `jour_ouvre_suivant`.
- `src/usine/domaine/meteo.py:471` -- `indicateurs()` produit la table par date ; modèle du test de franchissement.
- `src/usine/domaine/prevision/baseline.py` -- `_avancer` et la comparaison de seuil IND-1 (ligne `rouge = …`) à déplacer dans le module commun ; validation de série par `_jours` à imiter.
- `tests/unit/domaine/prevision/test_baseline.py:416` -- test d'unicité AD-18, à garder vert.
- `.github/scripts/controle_lanes.py:59` -- lane 4 : `src/usine/domaine/prevision`, `evaluation`.

## Tasks & Acceptance

**Execution:**
- `src/usine/domaine/prevision/commun.py` -- `avancer(jour, n)` (Jours ouvrés) et `declenche(valeur, operateur, seuil)` (Fractions) -- primitives uniques partagées.
- `src/usine/domaine/prevision/baseline.py` -- utiliser `commun.avancer` et `commun.declenche` à la place de `_avancer` et de la comparaison locale, sans changement de comportement.
- `src/usine/domaine/prevision/risque.py` -- `ParametresRisque` (dataclass gelée : `fenetre=10`, `horizon=5`, entiers ≥ 1), `RisqueProjete(risque: RisqueEntreeRouge, valeur_projetee: Fraction)`, `IndicateurExclu(code, motif)`, `ResultatRisque(risques, exclus)` et `risques_entree_rouge(indicateurs: pl.DataFrame, meteo: MeteoEntite, grille: GrilleMeteo, parametres: ParametresRisque = ParametresRisque()) -> ResultatRisque` selon la matrice et les Design Notes.
- `tests/unit/domaine/prevision/test_risque.py` -- un test par ligne de la matrice, valeurs exactes calculées à la main ; validité des `RisqueEntreeRouge` (horizon 5, version de Grille) ; déterminisme (deux appels égaux, table non mutée) ; source sans `now(`, `today(`, `random` ; `commun` seul à définir `avancer` dans `domaine/prevision`.

**Acceptance Criteria:**
- Given les séries d'IND-1, IND-3 et IND-4 d'une Entité non rouge sur 10 Jours ouvrés, when `risques_entree_rouge` s'exécute avec les paramètres H-8, then un `RisqueEntreeRouge` est émis pour chaque indicateur dont la projection franchit le seuil rouge dans les 5 Jours ouvrés, avec l'indicateur, la date de franchissement et la valeur projetée (`RisqueProjete.valeur_projetee`).
- Given IND-4 non évaluable sur une partie de la fenêtre, when le risque est calculé, then IND-4 est absent des risques et présent dans `exclus` avec un motif qui reprend celui de l'indicateur.
- Given les tests de la Story 4.1, when ils s'exécutent après la mise en commun, then ils restent verts.
- Given les cinq contrôles, then ruff, ruff format, mypy, lint-imports et pytest passent, et `controle_lanes.py --branche lane/4-prevision --base main` réussit.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 22 findings — high 0, medium 1, low 16, false 5, maybe-false 0
- findings:
  - `[low]` `[reject]` (blind) Indicateur déjà rouge à D signalé comme franchissement à D + 1 — inatteignable depuis `domaine.meteo` : un indicateur évalué au-delà du seuil rouge rend la Météo rouge, refusée en entrée ; seules des entrées incohérentes (autre Grille) le produisent, et la garde ajoute une branche.
  - `[low]` `[reject]` (blind) Aucune vérification Grille ↔ `meteo.version_grille` — `version_grille` est une empreinte SHA-256 du fichier, `grille.version` un entier : rien ne permet la comparaison dans le domaine ; l'appelant (L5) charge les deux ensemble, comme pour la Baseline.
  - `[low]` `[reject]` (blind) Tout l'historique est contrôlé, pas seulement la fenêtre — même règle que la Baseline (4.1) ; la table des indicateurs est dense par construction (Chaîne) ; limiter le contrôle exigerait un calcul de fenêtre calendaire en plus.
  - `[false]` `[reject]` (blind) `declenche` traite tout opérateur autre que `>=` comme `>` — `Operateur` (contrat gelé) n'a que deux valeurs.
  - `[false]` `[reject]` (blind) `avancer` accepte n < 0 — aucun appelant ne passe n < 1 (h ≥ 1, t ≥ 1 par construction).
  - `[low]` `[reject]` (blind) Historique court projeté sans le signaler — comportement fixé par la matrice (2 à 9 JO : régression sur les JO présents) ; le changer revient à éditer la spec.
  - `[low]` `[patch]` (blind) Branche « indicateur absent de la Grille » non testée — `test_indicateur_absent_de_la_grille` ajouté.
  - `[low]` `[patch]` (blind) Opérateur strict jamais testé via `risques_entree_rouge` — `test_operateur_strict` (IND-3 `> 20` : p(1) = 20 ne déclenche pas, p(2) = 21 à D + 2 JO).
  - `[low]` `[patch]` (blind) Lignes d'autres codes d'indicateur non testées — `test_indicateurs_non_projetes_ignores` (IND-2 avec trou et jour non ouvré : résultat identique).
  - `[low]` `[reject]` (blind) Tests textuels « sans horloge ni hasard » fragiles — import-linter interdit déjà `time`, `random`, `secrets`, `uuid` dans le domaine ; même choix qu'en 4.1.
  - `[false]` `[reject]` (blind) Construction de `RisqueEntreeRouge` pouvant lever une `ValidationError` — le seuil vient d'une `Fraction` de `GrilleMeteo` (dénominateur > 0) et la date vaut D + h avec h ≥ 1 : aucune violation atteignable.
  - `[low]` `[reject]` (intent) La vélocité de la Baseline n'est pas réutilisée — FR-21, l'AC de la Story 4.2 et l'addendum § E imposent une régression linéaire sur IND-1/3/4 ; la vélocité nette (sur `SerieStock`) n'existe pas pour IND-3/IND-4 ; AD-18 tenu (aucune seconde vélocité ni Baseline, primitives communes uniques) ; motivé dans les Design Notes.
  - `[medium]` `[defer]` (intent) Valeur projetée et motif d'exclusion hors du contrat publié — le contrat gelé n'a pas de champ ; différé contrats-v2 (voir `deferred`).
  - `[false]` `[reject]` (intent) Tests de la Baseline non montrés verts — `uv run pytest -q` : 1732 passés, dont `test_baseline.py`.
  - `[low]` `[patch]` (verification-gap) `fenetre` jamais testée hors défaut — `test_fenetre_non_par_defaut` (fenêtre 3 : p(1) = 21 à D + 1 ; fenêtre 10 : pente négative, aucun risque).
  - `[low]` `[patch]` (verification-gap) Opérateur strict non testé via l'appelant — groupé avec la ligne blind correspondante.
  - `[low]` `[defer]` (verification-gap) `domaine/meteo.py` garde sa comparaison de seuil — module de la lane L3, hors périmètre ; différé.
  - `[low]` `[reject]` (verification-gap) Tests de pureté et d'unicité textuels — comme la ligne blind « tests textuels ».
  - `[false]` `[reject]` (edge) Grille d'une autre version que `meteo.version_grille` — la garde proposée compare un entier à une empreinte SHA-256 : elle refuserait tout appel valide ; même fond que la ligne blind.
  - `[low]` `[reject]` (edge) Valeur courante déjà rouge — comme la ligne blind « déjà rouge ».
  - `[low]` `[reject]` (edge) Trou ancien hors fenêtre fait échouer le calcul — comme la ligne blind « tout l'historique ».
  - `[low]` `[reject]` (edge) D non ouvrée : message « Date d'arrêté absente » trompeur — l'erreur est levée et nomme D ; préciser la cause ajoute une branche pour un cas que la Chaîne n'émet pas.

## Design Notes

**Régression.** Sur la fenêtre (les `fenetre` derniers JO de la table finissant à D pour l'Entité et l'indicateur, n ≥ 2 points, x = 0..n−1) : b = Σ(x − x̄)(y − ȳ) / Σ(x − x̄)², a = ȳ − b·x̄ ; projection p(h) = a + b·(n − 1 + h). Premier h ∈ [1, horizon] où `declenche(p(h), op, seuil)` → risque : `date_franchissement_estimee = avancer(D, h)`, `valeur_projetee = p(h)`. Une valeur évaluée vaut `numerateur/denominateur` (dénominateur > 0).

**Pourquoi pas la vélocité de la Baseline.** FR-21 et l'addendum § E fixent une régression linéaire sur les séries d'indicateurs (dont IND-3 et IND-4, sans `SerieStock`) ; la vélocité nette (Σ(Sorties − Entrées)/n sur `SerieStock`) n'a pas de sens pour un taux de KO. AD-18 reste tenu : la vélocité n'est pas réécrite, la Baseline n'a pas de variante, et les primitives communes (avance en Jours ouvrés, test de seuil) n'existent qu'une fois, dans `commun`.

**Valeur projetée hors contrat.** Le contrat gelé `RisqueEntreeRouge` porte la valeur courante, pas la valeur projetée : celle-ci est rendue à côté (`RisqueProjete`). Sa publication dans `previsions.json` exigera un champ de contrat (contrats-v2) : différé à consigner.

**Paramètres hors configuration.** Comme H-7 en Story 4.1 : `contrats/config.py` est gelé, H-8 vit dans `ParametresRisque` jusqu'au branchement de l'étape `prevision` (L5).

**Précondition.** La table couvre chaque JO de la fenêtre (la Chaîne publie les indicateurs de chaque JO ≤ D) ; lignes postérieures à D ignorées.

## Verification

**Commands:**
- `uv run pytest -q tests/unit/domaine/prevision` -- expected: tous verts
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: succès
- `uv run python .github/scripts/controle_lanes.py --branche lane/4-prevision --base main` -- expected: succès

## Auto Run Result

- **Résumé :** le Risque d'entrée en rouge (FR-21, H-8) est livré comme fonction pure `domaine.prevision.risque.risques_entree_rouge(indicateurs, meteo, grille, parametres)` : régression linéaire exacte sur les 10 derniers Jours ouvrés d'IND-1, IND-3 et IND-4, projetée de 1 à 5 Jours ouvrés ; un `RisqueEntreeRouge` (indicateur, date de franchissement, valeur courante, seuil) par indicateur qui franchit son seuil rouge, avec la valeur projetée à côté ; indicateurs écartés (non évaluables sur la fenêtre, historique d'un seul JO, inactifs, absents ou sans seuil rouge) restitués avec leur motif. Les primitives communes avec la Baseline (avance en Jours ouvrés, déclenchement d'un seuil) sont mises en commun (AD-18).
- **Fichiers :**
  - `src/usine/domaine/prevision/commun.py` -- `avancer` et `declenche`, uniques.
  - `src/usine/domaine/prevision/baseline.py` -- utilise `commun`, comportement inchangé.
  - `src/usine/domaine/prevision/risque.py` -- `ParametresRisque` (10/5), `RisqueProjete`, `IndicateurExclu`, `ResultatRisque`, `risques_entree_rouge`.
  - `tests/unit/domaine/prevision/test_risque.py` -- tests de la matrice (valeurs exactes calculées à la main), erreurs, paramètres, déterminisme, unicité des primitives.
- **Revue :** 22 constats (0 high, 1 medium, 16 low, 5 false). Patches (low, tests seulement) : Grille sans l'indicateur, opérateur strict de bout en bout, fenêtre non par défaut, codes d'indicateur non projetés ignorés. Différés : valeur projetée et motifs hors contrat gelé (medium, contrats-v2) ; H-8 hors configuration (low) ; comparaison de seuil dupliquée dans `domaine/meteo.py` (low, lane L3). Rejets motivés dans le Review Triage Log.
- **Revue de suivi recommandée :** non (patches : 0 high, 0 medium, 4 entrées low).
- **Vérification :** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports`, `uv run pytest -q` (1732 passés, 1 sauté), `controle_lanes.py --branche lane/4-prevision --base main` : tous verts. Audit de matrice : chaque ligne couverte par un test passé.
- **Risques résiduels :** la vélocité de la Baseline n'est pas réutilisée pour la pente (régression exigée par FR-21, voir Design Notes) ; la publication de la valeur projetée attend un champ de contrat ; le contrôle de densité porte sur tout l'historique de l'indicateur, comme la Baseline.
