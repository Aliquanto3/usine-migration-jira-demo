---
title: 'Story 4.1 : Prévision de sortie du rouge par Baseline'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'affbd8fecd6e9fc1848fbddbf0aa5ef5cc4ccd06'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
warnings: [oversized]
deferred:
  - summary: >-
      Les paramètres H-7 de la Baseline (vélocité, horizon, fenêtres) ne sont pas lus dans la configuration de la Chaîne.
    evidence: |-
      H-7 (docs/QUESTIONS.md) place vélocité et horizon en configuration ; `contrats/config.py` est gelé (contrats-v1, AD-19), donc `prevoir_sortie` reçoit un `ParametresBaseline` à valeurs par défaut 10/10/5/20. Une PR courte sur main doit ajouter les clés à `config/chaine.yaml` et au modèle de `contrats.config` lors de l'intégration de l'étape `prevision` (lane L5).
    location: >-
      src/usine/domaine/prevision/baseline.py
    severity: low
---

<intent-contract>

## Intent

**Problem:** FR-20 n'a aucune implémentation : le Pilote ne sait pas quand une Entité rouge devrait sortir du rouge. AD-18 exige une Baseline unique, dans `domaine.prevision.baseline`, sur le contrat gelé `SerieStock`, réutilisée telle quelle par l'évaluation Zenodo (Story 4.4).

**Approach:** une fonction pure `prevoir_sortie(serie, meteo, parametres)` dans `src/usine/domaine/prevision/baseline.py` qui renvoie une `Prevision` (`methode=baseline`) selon l'addendum PRD § E : vélocité nette moyenne sur 10 Jours ouvrés, date de sortie projetée, fourchette par centiles des fenêtres de 5 Jours ouvrés sur 20, probabilité empirique dans l'horizon, facteurs explicatifs. Paramètres H-7 dans un `ParametresBaseline` à valeurs par défaut (10/10/5/20).

## Boundaries & Constraints

**Always:** arithmétique exacte (`Fraction`, sorties en numérateur/dénominateur entiers) ; Jours ouvrés par `contrats.calendrier` seulement ; seuil rouge d'IND-1 lu dans la `RegleDeclenchante` IND-1 rouge de la `MeteoEntite` (opérateur et seuil) ; « sous le seuil » = la règle ne se déclenche plus (`>=` : stock < seuil ; `>` : stock ≤ seuil) ; `version_grille`, `date_arrete`, `entite` repris de la `MeteoEntite` ; fonction pure, déterministe, sans horloge ni hasard.

**Never:** modifier `src/usine/contrats/`, `src/usine/ports/`, `config/` ou la Chaîne (`chaine/`, `composition.py`) ; seconde implémentation de la Baseline ; Risque d'entrée en rouge (Story 4.2) ; Modèle ML ; numpy ou statistiques flottantes.

## I/O & Edge-Case Matrix

Série ENT-A dense sur 20 Jours ouvrés finissant à la Date d'arrêté D ; IND-1 rouge `>= 3` ; paramètres par défaut.

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Sortie projetée | S = 6 à D, Sorties − Entrées = 6 sur les 10 derniers JO (v = 3/5) | `sortie_projetee` ; t = 5 JO (6 − 3/5·5 = 3, encore rouge ; t = 6 → 2,4 < 3 → t = 6) donc date = D + 6 JO ; fourchette optimiste ≤ estimée ≤ pessimiste ; probabilité = part des fenêtres de 5 JO dont la vélocité ramène sous le seuil en ≤ 10 JO ; 5 facteurs | — |
| Vélocité nulle | Entrées = Sorties sur 10 JO | `pas_de_sortie_projetee`, aucune date, probabilité empirique conservée | — |
| Vélocité défavorable | Entrées > Sorties | `pas_de_sortie_projetee`, aucune date | — |
| Règle non projetable | Météo rouge par IND-1 et IND-5 | `regle_non_projetable`, `regles_non_projetables = (IND-5,)`, aucune date, probabilité 0/1, facteurs calculés | — |
| Rouge par IND-5 seul | aucune règle IND-1 | `regle_non_projetable` (IND-5) | — |
| Historique court | 7 JO de série seulement | vélocité sur les JO disponibles (dénominateur = nombre de JO présents) ; fenêtres de 5 JO complètes seulement ; sans fenêtre complète : la fenêtre de vélocité sert de fenêtre unique | — |
| Pessimiste non projetable | centile 25 de vélocité ≤ 0, v > 0 | `date_sortie_pessimiste = None`, optimiste et estimée renseignées | — |
| Entrées invalides | Météo non rouge, D absente de la série, trou de JO dans la série, date non ouvrée ou en double, paramètre < 1 | — | `UsineErreur` nommant l'Entité et la cause |

</intent-contract>

## Code Map

- `src/usine/contrats/prevision.py` -- `SCHEMA_SERIE_STOCK` (serie, date, stock, entrees, sorties), `Prevision` (validateur : date ssi projetée, ordre optimiste ≤ estimée ≤ pessimiste, dates > D, `regle_non_projetable` ssi liste non vide), `FacteurExplicatif`, `MethodePrevision`, `StatutPrevision`. Gelé, lecture seule.
- `src/usine/contrats/meteo.py` -- `MeteoEntite` (couleur, regles, version_grille), `RegleDeclenchante` (operateur, seuil_numerateur/denominateur), `CodeIndicateur`, `Operateur`, `Couleur`. Gelé.
- `src/usine/contrats/calendrier.py:58-100` -- `jour_ouvre_suivant`, `jour_ouvre_precedent(d, n)`, `jours_ouvres`, `est_jour_ouvre`.
- `src/usine/contrats/schemas.py:47` -- `valider(df, schema)` ; `src/usine/contrats/erreurs.py` -- `UsineErreur`.
- `src/usine/domaine/kpi.py` -- modèle de style d'un module pur du domaine (docstring, Fractions).
- `pyproject.toml:143` -- contrat import-linter « domaine : contrats seulement » (numpy, io, time, random interdits).
- `.github/scripts/controle_lanes.py` -- lane 4 : `src/usine/domaine/prevision`, `evaluation`, `tests/unit/domaine/prevision`.

## Tasks & Acceptance

**Execution:**
- `src/usine/domaine/prevision/__init__.py` -- docstring du paquet (Prévision statistique, AD-18), sans réexport.
- `src/usine/domaine/prevision/baseline.py` -- `ParametresBaseline` (dataclass gelée : `fenetre_velocite=10`, `horizon=10`, `fenetre_fourchette=5`, `profondeur_fourchette=20`, chacun ≥ 1) et `prevoir_sortie(serie: pl.DataFrame, meteo: MeteoEntite, parametres: ParametresBaseline = ParametresBaseline()) -> Prevision` selon la matrice et les Design Notes.
- `tests/unit/domaine/prevision/__init__.py`, `tests/unit/domaine/prevision/test_baseline.py` -- un test par ligne de la matrice, valeurs exactes calculées à la main ; test de déterminisme (deux appels égaux, série non mutée) ; test que le module n'utilise ni horloge ni hasard (source sans `now(`, `today(`, `random`) ; test que `prevoir_sortie` et le nom « baseline » ne sont définis comme fonction qu'une fois dans `src/` et `evaluation/` (AD-18).

**Acceptance Criteria:**
- Given une `SerieStock` d'Entité et IND-1 rouge, when `prevoir_sortie` s'exécute avec les paramètres H-7, then la `Prevision` porte `methode=baseline`, `horizon_jours_ouvres=10`, la date estimée, la fourchette, la probabilité et les facteurs `stock`, `entrees`, `sorties`, `velocite_nette`, `variation_velocite`.
- Given la fonction, when on l'inspecte, then elle est pure et c'est la seule implémentation de la Baseline du dépôt.
- Given les cinq contrôles, then ruff, ruff format, mypy, lint-imports et pytest passent, et `controle_lanes.py --branche lane/4-prevision --base main` réussit.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 29 findings — high 0, medium 0, low 23, false 6, maybe-false 0
- findings:
  - `[false]` `[reject]` (blind) Règles non rouges comptées (couleur ignorée) — le validateur de `MeteoEntite` (contrats/meteo.py) impose que chaque règle porte la couleur de la Météo : une Météo rouge ne contient que des règles rouges.
  - `[false]` `[reject]` (blind) `next()` sans défaut lève `StopIteration` — une Météo rouge a au moins une règle (validateur) ; si une règle n'est pas IND-1 la fonction sort avant ; sinon toutes sont IND-1 et `next` trouve.
  - `[low]` `[patch]` (blind) Stock de la série jamais confronté au seuil : S sous le seuil donne une sortie à D+1 silencieuse — garde `UsineErreur` nommant l'Entité, le stock et le seuil, avec test.
  - `[low]` `[reject]` (blind) Valeurs négatives et cohérence stock/flux non contrôlées — la conversion en `SerieStock` (Story 4.3) produit des comptes ; garde supplémentaire pour un cas improbable.
  - `[low]` `[reject]` (blind) Date pessimiste non bornée — w ≥ 1/10 (sommes entières sur 10 JO au plus) donc t ≤ 10·S + 1, quelques milliers d'itérations au pire ; le calendrier ne gère pas de jours fériés, aucune limite de couverture.
  - `[low]` `[reject]` (blind) Pas de contrôle croisé des paramètres (`profondeur_fourchette < fenetre_fourchette`) — mauvaise configuration improbable, repli documenté (fenêtre unique) ; une règle de validation de plus dépasse la correction directe.
  - `[low]` `[patch]` (blind) Variation contre une fenêtre précédente partielle sans le dire — le libellé nomme le nombre de Jours ouvrés précédents.
  - `[low]` `[reject]` (blind) Différé mentionné dans les Design Notes mais `deferred: []` — correctif = éditer la spec ; le différé est consigné par la ligne « configuration » de l'auditeur d'intention ci-dessous.
  - `[low]` `[reject]` (blind) Exemple confus dans la matrice (t = 5 puis t = 6) — correctif = éditer la spec ; le test de référence vérifie les valeurs exactes.
  - `[low]` `[reject]` (blind) Test d'unicité AD-18 contournable par un autre nom — renforcer le test ajoute de la complexité pour un risque que la revue de la Story 4.4 couvre.
  - `[low]` `[reject]` (blind) Test « sans horloge ni hasard » textuel — import-linter interdit déjà `time`, `random`, `secrets`, `uuid` dans le domaine ; le test complète sans coût.
  - `[low]` `[patch]` (blind) Tests manquants (IND-5 seul : probabilité et facteurs ; plusieurs règles non projetables ; `>` fractionnaire ; paramètres non par défaut) — tests ajoutés (pour un quotient fractionnaire, ⌈x⌉ = ⌊x⌋ + 1 : le test fractionnaire confirme, le cas entier où ils diffèrent était déjà couvert).
  - `[low]` `[patch]` (verification-gap) `fenetre_velocite`, `fenetre_fourchette`, `profondeur_fourchette` jamais testés hors défaut — test à paramètres non par défaut, valeurs calculées à la main.
  - `[low]` `[patch]` (verification-gap) Troncature à 20 JO et fenêtre précédente jamais exercées — test sur une série allongée : résultat de référence inchangé.
  - `[low]` `[patch]` (verification-gap) Stock de la série incohérent avec le seuil — groupé avec la ligne blind « stock jamais confronté ».
  - `[low]` `[reject]` (verification-gap) Tests de pureté et d'unicité purement textuels — comme la ligne blind « test sans horloge ».
  - `[low]` `[defer]` (intent) Paramètres H-7 hors configuration de la Chaîne — `contrats/config.py` gelé (AD-19, contrats-v1) : branchement par PR courte sur `main` à l'intégration de l'étape `prevision` (L5) ; différé.
  - `[false]` `[reject]` (intent) « Pour chaque Entité rouge » non couvert — l'AC fixe la surface `domaine.prevision.baseline` par Entité ; l'itération sur les Entités et la publication relèvent de l'étape `prevision` de la Chaîne (L5).
  - `[false]` `[reject]` (intent) Fourchette en dates plutôt qu'en vélocités — le contrat gelé `Prevision` porte la fourchette en dates (`date_sortie_optimiste`, `date_sortie_pessimiste`), dérivées des vélocités P75/P25.
  - `[false]` `[reject]` (intent) Libellé « règle non projetable : IND-5 » non produit — le contrat porte `statut=regle_non_projetable` et `regles_non_projetables=(IND-5,)` ; le libellé appartient au rendu (L5).
  - `[false]` `[reject]` (intent) Fenêtres de la probabilité choisies par le diff — l'addendum § E parle des « fenêtres de vélocité historiques » ; réutiliser les fenêtres de la fourchette est la lecture documentée dans les Design Notes, aucun critère ne l'infirme.
  - `[low]` `[reject]` (intent) Pureté et unicité vérifiées par le texte — comme la ligne blind « test sans horloge » ; le déterminisme est aussi testé par appel.
  - `[low]` `[patch]` (edge) Stock à D sous le seuil IND-1 — groupé avec la ligne blind « stock jamais confronté ».
  - `[low]` `[reject]` (edge) Valeurs négatives — comme la ligne blind correspondante.
  - `[low]` `[reject]` (edge) `profondeur_fourchette < fenetre_fourchette` accepté — comme la ligne blind « contrôle croisé ».
  - `[low]` `[reject]` (edge) Boucle O(t) et dépassement de l'an 9999 — t ≤ 10·S + 1 ; l'an 9999 exige ~2 millions de JO, inatteignable avec des stocks réels.
  - `[low]` `[reject]` (edge) Plusieurs règles IND-1 rouges — `domaine.meteo` émet une seule règle par indicateur et par couleur ; inatteignable depuis la Météo calculée.
  - `[low]` `[reject]` (edge) Trou ancien dans l'historique fait échouer la série — la `SerieStock` est dense par construction (Story 4.3) ; l'erreur explicite est le comportement voulu par la matrice.
  - `[low]` `[reject]` (edge) Erreur de paramètre sans nom d'Entité — levée à la construction de `ParametresBaseline`, indépendante de toute Entité ; le message nomme le paramètre fautif.

## Design Notes

**Formules (D = Date d'arrêté, S = stock à D).** Fenêtre de vélocité = les `fenetre_velocite` JO finissant à D, limités à ceux présents dans la série ; v = Σ(Sorties − Entrées) / nombre de JO. Variation = v − v_précédente (même calcul sur les JO précédant la fenêtre ; 0 si aucun). Jours à la sortie pour une vélocité w > 0 : `>=` → t = ⌊(S − seuil)/w⌋ + 1 ; `>` → t = ⌈(S − seuil)/w⌉ ; t ≥ 1 ; date = D avancée de t JO. Fenêtres de fourchette : toutes les fenêtres glissantes complètes de `fenetre_fourchette` JO incluses dans les `profondeur_fourchette` derniers JO (16 au plus) ; centiles 25 et 75 par interpolation linéaire exacte (méthode « type 7 ») sur les vélocités triées. Optimiste = date pour max(P75, v), pessimiste = date pour min(P25, v) si > 0, sinon `None` : l'ordre exigé par le contrat est garanti. Probabilité = nombre de fenêtres (w > 0 et t ≤ horizon) / nombre de fenêtres.

**Règle non projetable.** Toute Règle déclenchante rouge autre qu'IND-1 est non projetable (addendum § E, AC IND-5) ; aucune date, probabilité 0/1 (la sortie dépend d'une règle que la Baseline ne projette pas), facteurs conservés pour l'explication.

**Paramètres hors configuration.** H-7 place vélocité et horizon en configuration de la Chaîne, mais `contrats/config.py` est gelé (AD-19 : chaque fichier validé par un modèle de `contrats.config`). La fonction reçoit donc un `ParametresBaseline` ; le branchement à `config/chaine.yaml` se fera par une PR courte sur `main` lors de l'intégration de l'étape `prevision` (lane L5). Différé consigné.

**Évaluation (AD-18).** La Story 4.4 appellera `prevoir_sortie` avec une `MeteoEntite` construite pour le projet (règle IND-1 rouge au seuil du protocole) : aucune variante de la Baseline.

## Verification

**Commands:**
- `uv run pytest -q tests/unit/domaine/prevision` -- expected: tous verts
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: succès
- `uv run python .github/scripts/controle_lanes.py --branche lane/4-prevision --base main` -- expected: succès

## Auto Run Result

- **Résumé :** la Baseline de sortie du rouge (FR-20, AD-18, H-7) est livrée comme fonction pure unique `domaine.prevision.baseline.prevoir_sortie(serie, meteo, parametres)` : vélocité nette sur 10 Jours ouvrés, date estimée, fourchette par centiles 25/75 des fenêtres de 5 JO sur 20, probabilité empirique dans l'horizon, cinq facteurs explicatifs ; « pas de sortie projetée » pour une vélocité nulle ou défavorable ; « règle non projetable » pour toute règle rouge autre qu'IND-1 (IND-5).
- **Fichiers :**
  - `src/usine/domaine/prevision/__init__.py` -- paquet de la Prévision (docstring, AD-18).
  - `src/usine/domaine/prevision/baseline.py` -- `ParametresBaseline` (H-7, 10/10/5/20) et `prevoir_sortie`.
  - `tests/unit/domaine/prevision/__init__.py`, `tests/unit/domaine/prevision/test_baseline.py` -- 45 tests, valeurs calculées à la main.
  - `_bmad-output/implementation-artifacts/epic-4-context.md` -- contexte compilé de l'Epic 4.
- **Revue :** 29 constats (0 high, 0 medium, 23 low, 6 false). Patches (low) : garde sur un stock qui ne déclenche plus IND-1, libellé de variation avec le nombre de JO précédents, tests ajoutés (IND-5 seul, règles non projetables multiples, `>` fractionnaire, paramètres non par défaut, série plus longue que la profondeur). Différé : paramètres H-7 hors configuration de la Chaîne (contrats gelés). Rejets motivés dans le Review Triage Log.
- **Revue de suivi recommandée :** non (patches : 0 high, 0 medium, 5 entrées low).
- **Vérification :** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports`, `uv run pytest -q` (1660 passés, 1 sauté) : tous verts. Audit de matrice : chaque ligne couverte par un test passé.
- **Risques résiduels :** paramètres non branchés sur `config/chaine.yaml` (PR courte sur main à l'intégration L5) ; cohérence stock/flux de la `SerieStock` non contrôlée (relève de la conversion, Story 4.3) ; plusieurs règles IND-1 rouges : la première est retenue (inatteignable depuis `domaine.meteo`).
