---
title: 'Story 3.7 : Évolution de la Météo à J-1 et J-5'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'cc65cbcdccf541e9049288d8240ee0ccdfc3aaae'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
warnings: [oversized]
deferred:
  - summary: >-
      H-19 prévoit le décalage J-5 en configuration, mais il est codé en dur (J-5) dans l'appariement et le contrat.
    evidence: |-
      docs/QUESTIONS.md H-19 : « Paramètre en configuration » ; consultation/passage.py evolution_meteo appelle jour_ouvre_precedent(jour, 5) et EvolutionMeteo valide date_j5 = J-5. Préexistant, contrats gelés (contrats-v1) : un paramètre demanderait une PR dédiée sur main si H-19 change.
    location: >-
      src/usine/consultation/passage.py:296
    severity: low
---

<intent-contract>

## Intent

**Problem:** FR-19 (Météo de J-1 et J-5 en Jours ouvrés, drapeau de changement, J-1 explicitement absent au premier Jour ouvré de l'historique) est déjà servie par la composition existante : `EtapeMeteo` publie dans `meteo.json` la Météo de chaque Jour ouvré, `Consultation.evolution_meteo` apparie J-1 et J-5 (dérivation de lecture, décision D8, AD-11), `EvolutionMeteo` porte `change_depuis_j1` et `change_depuis_j5`. Mais aucun test ne prouve les critères de la Story 3.7 sur une trajectoire de couleurs connue : aucun changement de couleur réel n'est observé, ni l'absence de J-5 seule, ni la couverture de chaque Jour ouvré.

**Approach:** comme la Story 3.6, fixer le comportement par des tests d'acceptation de bout en bout, de la Météo calculée par le domaine jusqu'à `Consultation.evolution_meteo` ; ne créer aucun second calcul d'appariement dans `domaine/` (D8) ; ne corriger du code que si un test révèle un écart.

## Boundaries & Constraints

**Always:** J-1 et J-5 en Jours ouvrés via `contrats.calendrier.jour_ouvre_precedent` ; couleur absente = `None` (jamais une couleur par défaut) et drapeau faux quand la couleur de comparaison est absente ; la Météo comparée est celle calculée par `domaine.meteo.meteo` pour chaque Jour ouvré.

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` ; ajouter une fonction d'évolution ou d'appariement dans `domaine/` (D8 : dérivation de lecture de `Consultation`) ; modifier `consultation/`, `chaine/` ou `composition.py` (lane L5) sauf écart révélé ; hystérésis.

## I/O & Edge-Case Matrix

Trajectoire ENT-A, Grille livrée réduite à IND-1, historique du lundi 2026-09-28 au lundi 2026-10-05 : 28/09 vert (0 bloquante), 29/09 orange (1), 30/09 et 01/10 rouge (3), 02/10 et 05/10 orange (2 fermées le 02/10). ENT-B vert tout du long.

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| J-1 inchangé, J-5 changé | D = 05/10 | ENT-A : orange ; J-1 = 02/10 orange, `change_depuis_j1` faux ; J-5 = 28/09 vert, `change_depuis_j5` vrai | — |
| J-1 changé, J-5 hors historique | D = 02/10 | ENT-A : J-1 = 01/10 rouge, `change_depuis_j1` vrai ; `date_j5` = 25/09, `couleur_j5` `None`, `change_depuis_j5` faux | — |
| Premier Jour ouvré | D = 28/09 | `date_j1` = 25/09 renseignée, `couleur_j1` `None` (et non vert), `change_depuis_j1` faux ; J-5 `None` | — |
| Entité stable | ENT-B, D = 05/10 | vert à D, J-1 et J-5, aucun drapeau | — |
| Passage du mini-jeu | Chaîne lancée sur le Journal généré | `meteo.json` couvre chaque Jour ouvré du premier jour à la Date d'arrêté, pour chaque Entité ; pour chaque date, `evolution_meteo` donne la Météo publiée à J-1 et J-5, `None` avant le premier jour | — |

</intent-contract>

## Code Map

- `src/usine/consultation/passage.py:289` -- `evolution_meteo` : apparie J-1/J-5 depuis `meteo.json` (`couleurs.get`, `None` si non couverte). Lane L5, lecture seule.
- `src/usine/contrats/meteo.py:147-182` -- `EvolutionMeteo` (dates J-1/J-5 toujours renseignées et validées, couleurs `Couleur | None`, `change_depuis_j1`, `change_depuis_j5`). Gelé.
- `src/usine/contrats/passage.py:273` -- `EnveloppeFichier`, `former_passage_id` (l. 264) ; `FICHIERS_PASSAGE["meteo"] = "meteo.json"`. Gelé.
- `src/usine/chaine/etapes.py:57-117` -- `EtapeMeteo` : Météo de chaque Jour ouvré `jours_du_passage(premier_jour, date_arrete)`. Lecture seule.
- `src/usine/domaine/meteo.py:522` -- `meteo(...)` ; la docstring du module peut citer FR-19 (évolution dérivée à la lecture, D8).
- `tests/unit/domaine/test_meteo.py` -- helpers : `grille` (fixture, IND-1 seul), `Flux`, `_a`, `ANCRAGE`, `PROGRAMME`, `VERSION`, `_calculer_meteo`, `tickets_etats`, `jours_ouvres`.
- `tests/unit/chaine/environnement.py` -- `preparer_racine`, `horloge_figee`, `DATE_ARRETE` ; `usine.composition.lancer_rapport` lance la Chaîne (voir `tests/unit/consultation/test_passage.py:105`).
- `_bmad-output/planning-artifacts/architecture/.../ARCHITECTURE-SPINE.md:193` -- D8 : appariement J-1/J-5 = dérivation de lecture de `Consultation`, pas un calcul AD-9.

## Tasks & Acceptance

**Execution:**
- `tests/unit/domaine/test_meteo.py` -- section « Évolution de la Météo à J-1 et J-5 (Story 3.7) » : calculer la Météo de chaque Jour ouvré de la trajectoire par `meteo` du domaine, l'écrire en `meteo.json` (enveloppe) dans un répertoire de Passage temporaire, puis vérifier chaque ligne de la matrice par `ConsultationPassage.evolution_meteo` ; un test sur le Passage publié par `lancer_rapport` (mini-jeu) pour la couverture de chaque Jour ouvré et l'appariement à chaque date ; docstring du module (Story 3.7, FR-19).
- `src/usine/domaine/meteo.py` -- docstring du module : l'évolution J-1/J-5 (FR-19) se lit par `Consultation.evolution_meteo` sur la Météo de chaque Jour ouvré, sans calcul dans le domaine (D8).

**Acceptance Criteria:**
- Given la Météo calculée pour chaque Jour ouvré, when on demande l'évolution d'une Entité à D, then on obtient la Météo de J-1 et J-5 (Jours ouvrés) et un drapeau de changement pour chacune.
- Given D égal au premier Jour ouvré de l'historique, when on demande J-1, then la couleur vaut `None`, pas une couleur par défaut.
- Given les cinq contrôles du dépôt, then ruff, ruff format, mypy, lint-imports et pytest passent, et `controle_lanes.py --branche lane/3-calcul --base main` réussit.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 21 findings — high 0, medium 0, low 15, false 6, maybe-false 0
- findings:
  - `[false]` `[reject]` (blind) Deux noms pour la même méthode (`Consultation` / `ConsultationPassage`), D8 au lieu d'AD-17 — `Consultation` est le port, `ConsultationPassage` son implémentation testée ; D8 est la décision qui place l'appariement (spine AD-11), AD-17 fixe J-1/J-5 ; les deux références sont justes.
  - `[low]` `[reject]` (blind) Le fichier de tests du domaine importe des couches externes — choix voulu (Design Notes) pour rester dans la lane : déplacer les tests sous `tests/unit/consultation/` ferait échouer `controle_lanes.py` ; aucun import de production n'est touché.
  - `[low]` `[patch]` (blind) `change_depuis_j5` jamais vérifié sur le Passage réel, J-5 peut-être jamais connu — assertion du drapeau J-5 symétrique à J-1 et compteur `j5_connus > 0` ajoutés.
  - `[low]` `[reject]` (blind) Combinaison « J-1 changé, J-5 inchangé » non testée — les drapeaux sont deux propriétés indépendantes du contrat gelé (testées dans `tests/unit/contrats/test_meteo.py`) ; le test du mini-jeu vérifie maintenant chacun à chaque date ; étendre la trajectoire ajoute de la complexité pour un défaut improbable.
  - `[low]` `[reject]` (blind) Date hors historique ou `meteo.json` vide : `()` non testé — comportement préexistant de `Consultation` (lane L5), hors des critères de la Story 3.7.
  - `[low]` `[reject]` (blind) Trou dans l'historique non testé — `EtapeMeteo` publie chaque Jour ouvré (couverture prouvée par le test du mini-jeu) et l'appariement rend `None` pour toute date non couverte (`couleurs.get`) ; un cas artificiel n'apporte rien d'atteignable.
  - `[low]` `[defer]` (blind) H-19 non traçable : J-5 codé en dur alors que H-19 le prévoit en configuration — préexistant (`contrats.calendrier`, validateur d'`EvolutionMeteo`, contrats gelés) ; différé.
  - `[low]` `[reject]` (blind) `meteo.json` écrit à la main dans la trajectoire — le format est l'`EnveloppeFichier` du contrat, relu par `lire_enveloppe` ; le test du mini-jeu passe par l'écrivain de production.
  - `[low]` `[patch]` (blind) `_evolution` échoue par un `ValueError` opaque — assertion nommant l'Entité et la date.
  - `[false]` `[reject]` (blind) Le diff ne contient aucun code de production — voulu : D8 place l'appariement dans `Consultation`, déjà livré ; la spec et le suivi sont consignés dans ce fichier.
  - `[low]` `[patch]` (edge) Drapeau J-5 non vérifié sur le mini-jeu — groupé avec la ligne blind correspondante.
  - `[low]` `[patch]` (edge) `ValueError` opaque si D non couverte — groupé avec la ligne `_evolution`.
  - `[low]` `[reject]` (edge) Chemin `()` pour une D non couverte non testé — comme la ligne blind « date hors historique ».
  - `[low]` `[reject]` (edge) Combinaison J-1 changé / J-5 inchangé — comme la ligne blind correspondante.
  - `[low]` `[patch]` (edge) Affirmation « le mini-jeu prouve les drapeaux » incomplète pour J-5 — groupé avec la ligne blind J-5.
  - `[false]` `[reject]` (intent) Spec satisfaite par vérification et non par construction — conforme à D8 (spine AD-11) et à la consigne de ne pas créer un second calcul.
  - `[low]` `[reject]` (intent) Tests placés dans le domaine mais exerçant `Consultation` — comme la ligne blind « couches externes ».
  - `[low]` `[reject]` (intent) Recouvrement avec `tests/unit/consultation/test_passage.py` — les nouveaux cas (drapeaux, J-5 hors historique, chaque date du mini-jeu) n'y figurent pas ; recouvrement partiel sans coût.
  - `[false]` `[reject]` (intent) Décision citée D8 au lieu de D9 — D8 est la décision des dérivations de lecture (spine AD-11, proposition de changement) ; D9 concerne `palier` et `dernier_passage`.
  - `[false]` `[reject]` (intent) Requête par Entité contre port global — le port rend une évolution par Entité ; aucun critère n'exige un paramètre `entite`.
  - `[false]` `[reject]` (intent) « Météo de chaque Jour ouvré » vérifiée et non construite — déjà produite par `EtapeMeteo` ; le test du mini-jeu la prouve.

## Design Notes

**Pas de second calcul (constat 11 de la rétrospective de l'Epic 0, D8).** Le spine (AD-11, « Dérivations de lecture ») tranche : l'appariement J-1/J-5 est calculé à la lecture par `Consultation`, ce n'est pas un calcul métier au sens d'AD-9, et il ne produit aucune valeur publiée. La part de L3 est la Météo de chaque Jour ouvré (déjà publiée par `EtapeMeteo`) ; la Story 3.7 la prouve de bout en bout.

**Tests dans la lane.** Les tests vivent dans `tests/unit/domaine/test_meteo.py` (miroir de `domaine/meteo`) pour que `controle_lanes.py` passe sans fichier hors lane ; ils importent `ConsultationPassage` et `lancer_rapport`, comme surface de lecture du Pilote.

## Verification

**Commands:**
- `uv run pytest -q tests/unit/domaine/test_meteo.py` -- expected: tous verts
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: succès

## Auto Run Result

- **Résumé :** FR-19 est prouvée de bout en bout sans second calcul (D8, spine AD-11) : la Météo de chaque Jour ouvré calculée par le domaine, publiée dans `meteo.json`, est appariée à J-1 et J-5 par `Consultation.evolution_meteo` avec les drapeaux `change_depuis_j1`/`change_depuis_j5` ; au premier Jour ouvré, J-1 vaut `None`, jamais une couleur par défaut. Aucun écart révélé : aucun code de production modifié hors docstring.
- **Fichiers :**
  - `src/usine/domaine/meteo.py` -- docstring du module : l'évolution J-1/J-5 se lit par `Consultation.evolution_meteo` (D8), sans calcul dans le domaine.
  - `tests/unit/domaine/test_meteo.py` -- section Story 3.7 : trajectoire ENT-A/ENT-B (une ligne de matrice par test) et test du Passage du mini-jeu (couverture de chaque Jour ouvré, appariement et drapeaux à chaque date).
- **Revue :** 21 constats ; 2 entrées corrigées (patch, low : drapeau J-5 et J-5 connu sur le mini-jeu ; assertion explicite de `_evolution`) ; 1 différé (H-19, J-5 codé en dur, préexistant) ; rejets (10 low, 6 false) motivés dans le Review Triage Log.
- **Revue de suivi recommandée :** non (patches : 0 high, 0 medium, 2 low).
- **Vérification :** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (210 fichiers), `uv run lint-imports` (13 contrats), `uv run pytest -q` (1543 passés, 22 sautés) : tous verts après correctifs. Audit de matrice : chaque ligne couverte par un test passé.
- **Risques résiduels :** J-5 codé en dur malgré H-19 (différé) ; le comportement de `evolution_meteo` pour une date non couverte (`()`) relève de L5.
