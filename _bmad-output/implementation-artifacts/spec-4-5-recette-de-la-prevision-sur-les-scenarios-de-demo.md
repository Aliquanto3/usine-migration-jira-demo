---
title: 'Story 4.5 : Recette de la Prévision sur les Scénarios de démo'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'a663bf357641113585540dfdbb59a06106836ee0'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/planning-artifacts/sprint-change-proposal-2026-10-12-contrats-1-2.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** SM-6 (A sort du rouge dans l'horizon, B ne sort pas, C est signalée en Risque d'entrée en rouge) n'est vérifié par aucun test sur le chemin réel de la Chaîne. Les Risques publiés dans `previsions.json` n'ont pas de valeur projetée (`valeur_projetee_*` vides) alors que `risque.py` la calcule.

**Approach:** Reprise après contrats 1.2 (générateur déjà corrigé sur `main`). Une recette exécute un Passage (`composition.lancer_rapport`, étape `prevision` = `prevision_du_passage`) sur le Journal généré avec la configuration livrée, puis lit `previsions.json` par `ConsultationPassage` à la Date d'arrêté D. `risques_entree_rouge` remplit `valeur_projetee_*` du `RisqueEntreeRouge` avec la valeur projetée qu'il calcule déjà.

## Boundaries & Constraints

**Always:**
- `serie.py` et `prevision_du_passage` de `main` utilisés tels quels (`serie.py`/`previsions.py` de la lane abandonnés).
- Configuration livrée (`config/`), gabarits livrés, Journal de `composition.generer_journal`.
- Rapide : graine 42, génération le vendredi 2026-10-09 → D, plus une génération hors vendredi (mardi 2026-10-13, D lundi). `lent` : générations du mercredi au samedi (D mardi à vendredi) et graines 1, 7, 123.
- À D : seules A et B rouges ; A `sortie_projetee`, date ≤ D + horizon, `regles_non_projetables == ()` ; B `pas_de_sortie_projetee`, `regles_non_projetables == ()` ; C porte un Risque IND-4 quel que soit le jour de D ; tout Risque publié a `valeur_projetee_*` renseignés.
- Recoupement : `series_stock` sur l'état des tickets du Passage = IND-1 publié, pour chaque Entité et Jour ouvré.

**Never:**
- Toucher `src/usine/contrats/`, `src/usine/ports/`, `config/`, la Grille, `baseline.py` (SM-C3) ni le générateur.
- Modifier les seuils ou la logique de projection de `risque.py` : seul le remplissage du contrat change.
- Ajouter une dépendance.

</intent-contract>

## Code Map

- `src/usine/chaine/etapes.py:177` -- `prevision_du_passage` (main) : Prévisions et Risques pour chaque Jour ouvré ; `risques.extend(projete.risque ...)` (l. 219) publie le Risque tel que construit par `risque.py`.
- `src/usine/domaine/prevision/risque.py:150-163` -- construction de `RisqueEntreeRouge` ; `projetee: Fraction` disponible ; `RisqueProjete` reste (tests existants).
- `src/usine/contrats/prevision.py:119-145` -- `valeur_projetee_numerateur/denominateur` (gelé, 1.1) : les deux ou aucun, dénominateur > 0.
- `src/usine/rendu/commun.py:316` -- affiche « valeur projetée » quand renseignée : rendu Excel/PowerPoint enrichi, pas de changement de code.
- `src/usine/composition.py:445` -- `lancer_rapport(racine, D, horloge)` ; `generer_journal` l. 488.
- `tests/unit/chaine/environnement.py` -- modèle de racine d'essai (`preparer_racine` copie `config/` et `gabarits/`), `horloge_figee`.
- `src/usine/consultation/passage.py` -- `ConsultationPassage(repertoire)` : `meteo(D)`, `previsions(D)`, `risques(D)`, `indicateurs()`, `tickets_etats(jour)`.
- `src/usine/domaine/prevision/serie.py:48` -- `series_stock(etats, entites, jours)` (main) ; changement d'Entité déjà couvert par `test_transfert_d_entite`.
- `tests/unit/domaine/prevision/test_recette_scenarios.py` -- recette de la lane bloquée, à réécrire sur la Chaîne.
- Mesure exploratoire (main a663bf3) : SM-6 tenu par la Chaîne pour la graine 42 (générations du lundi 12 au samedi 17), graines 1, 7, 123 ; environ 5 s par Passage.

## Tasks & Acceptance

**Execution:**
- `src/usine/domaine/prevision/risque.py` -- passer `valeur_projetee_numerateur=projetee.numerator`, `valeur_projetee_denominateur=projetee.denominator` au `RisqueEntreeRouge` ; docstring de `RisqueProjete` ajustée.
- `tests/unit/domaine/prevision/test_risque.py` -- vérifier que chaque Risque rendu porte `valeur_projetee_*` égale à `valeur_projetee`.
- `tests/unit/domaine/prevision/test_recette_scenarios.py` -- réécriture : racine temporaire (config et gabarits livrés), `generer_journal(programme livré, graine, date)`, `lancer_rapport`, lecture `ConsultationPassage`, `_ecarts_sm6` avec les exigences d'Always ; tests rapides (vendredi, lundi) et `lent` (semaine partielle, graines).
- Tests existants impactés par `valeur_projetee_*` (attendus JSON, rendu) -- réaligner sans affaiblir.

**Acceptance Criteria:**
- Given le Journal généré (graine 42, 2026-10-12) et la Grille livrée, when la recette exécute un Passage à D = 2026-10-09 par `lancer_rapport`, then `previsions.json` à D donne A `sortie_projetee` dans l'horizon, B `pas_de_sortie_projetee` (sans règle non projetable), C un Risque IND-4, seules A et B rouges.
- Given une génération le mardi 2026-10-13 (D lundi), when la recette rapide s'exécute, then SM-6 et IND-4 pour C tiennent aussi.
- Given les graines 1, 7, 123 et les générations du mercredi au samedi, when `pytest -m lent` s'exécute, then SM-6 tient.
- Given une Entité non rouge qui porte un Risque, when l'étape `prevision` publie `previsions.json`, then `valeur_projetee_*` sont renseignés depuis `risque.py`.
- Given la story, then `git diff <baseline_revision>` ne touche ni `contrats/`, ni `ports/`, ni `config/`, ni `baseline.py`, ni `generateur/`.

## Spec Change Log

- 2026-10-12 — Reprise après contrats 1.2 (sprint-change-proposal-2026-10-12-contrats-1-2, étape 2a). Le générateur, `serie.py` et `prevision_du_passage` sont sur `main` : la spec est réduite à la recette par la Chaîne et au remplissage de `valeur_projetee_*`. Patchs du triage repris : SM-6 hors vendredi en rapide, IND-4 exigé tous jours, `regles_non_projetables == ()`. Changement d'Entité dans `series_stock` : déjà couvert sur `main`. KEEP : recoupement stock = IND-1.

## Review Triage Log


### 2026-10-12 — Review pass (reprise après coupure de quota, mode économique : une seule passe)
- verdicts: 24 findings — high 3, medium 6, low 9, false 2, maybe-false 4
- findings:
  - `[medium]` `[patch]` (verification-gap) SM-6 n'est testé hors vendredi que sous `lent` — réel (`addopts` exclut `lent`) ; non appliqué, story arrêtée.
  - `[low]` `[patch]` (verification-gap) aucun test de changement d'Entité avant fermeture dans `series_stock` — réel ; non appliqué, story arrêtée.
  - `[medium]` `[bad_spec]` (edge-case) bloquantes scriptées tronquées sans signal quand `restantes` est insuffisant (Programme réduit : A perd ses créations) — réel, cf. fixtures passées de ENT-A à ENT-B.
  - `[maybe-false]` `[defer]` (edge-case) doublons (cle_ticket, date) dans `tickets_etats` : la jointure doublerait les comptes — dépend de l'unicité garantie par la Consultation, à vérifier.
  - `[low]` `[reject]` (edge-case) même Entité deux fois dans `meteos` — `meteo.json` porte une ligne par Entité ; garde peu utile.
  - `[high]` `[intent_gap]` (intent-alignment a, blind 1) `serie.py` existe sur main (Story 5.3) : `series_stock(tickets_etats, entites, jours)`, appelé par `chaine/etapes.py:190`, de sémantique ensembliste (reclassement = Entrée) contraire à la matrice de cette spec — conflit add/add ; la matrice doit être retranchée contre celle de main.
  - `[medium]` `[intent_gap]` (intent-alignment a, blind 2) `previsions_du_jour` duplique `prevision_du_passage` de main — la recette doit passer par le chemin de la Chaîne.
  - `[high]` `[intent_gap]` (intent-alignment b, blind 3 et 4) sur main, les Scénarios sont lus dans `config/programme.yaml` par `ConfigScenarioSortie`/`ConfigScenarioEnlisement`/`ConfigScenarioMenace` (contrats 1.1, `extra="forbid"`, gelés), et `test_configuration_livree_egale_aux_defauts` exige config = `SCENARIOS_PAR_DEFAUT` — le modèle 4.5 n'est pas exprimable sans modifier `src/usine/contrats/config.py`.
  - `[high]` `[intent_gap]` (blind 3) `scenarios_de_config` de main passe `part_bloquantes_vague=`/`part_bloquantes=` : `TypeError` après fusion — même racine.
  - `[low]` `[defer]` (intent-alignment c) la recette n'exerce pas `EtapePrevision` — à refaire de bout en bout après les contrats 1.2.
  - `[low]` `[patch]` (intent-alignment d) les cas lundi/mardi n'exigent qu'un Risque, pas IND-4 — réel ; non appliqué.
  - `[maybe-false]` `[defer]` (intent-alignment e) répartition entre Entités modifiée sur le Programme réduit — volume tenu ; effet sur le rendu à mesurer.
  - `[medium]` `[bad_spec]` (blind 5) même racine que la troncature sans signal ci-dessus.
  - `[low]` `[patch]` (blind 6) `test_bloquantes_scriptees` compte des jours calendaires et non ouvrés — faux seulement une semaine à jour férié ; non appliqué.
  - `[low]` `[patch]` (blind 7) `part_du_jour` code 5 en dur au lieu de `JOURS_OUVRES_SEMAINE` — non appliqué.
  - `[low]` `[patch]` (blind 8, note edge-case) docstrings `ScenarioEnlisement` et `DELAIS_LENTS` contredisent `_DELAIS_ENLISES` (seules les mineures sont lentes) — non appliqué.
  - `[medium]` `[bad_spec]` (blind 9) `duree_bloquantes` sans borne haute alors que SM-6 exige ≤ 10 — réel.
  - `[low]` `[patch]` (blind 10) `_ecarts_sm6` ne vérifie pas `regles_non_projetables == ()` — non appliqué.
  - `[false]` `[reject]` (blind 11) coût du test rapide de recette — la suite rapide complète tient en 2 min ; `== 40` est l'attendu du Programme livré.
  - `[low]` `[reject]` (blind 12) table à une seule date non testée — couvert par « première date, veille vide ».
  - `[maybe-false]` `[defer]` (blind 13) erreur côté Risque non testée dans `test_previsions` — module appelé à disparaître au profit de `prevision_du_passage`.
  - `[false]` `[reject]` (blind 13) `_meteo()` sans `jaune` lève `KeyError` — aide de test, aucun test ne la sollicite en jaune.
  - `[maybe-false]` `[defer]` (blind 14) PRD et glossaire non mis à jour pour B réservée et C à 50 Cas de test — à vérifier contre le PRD.
  - `[medium]` `[intent_gap]` (intent-alignment b) le « Programme livré » de la recette porte sur main les anciennes valeurs : la preuve SM-6 ne repose que sur le repli du générateur.

### Auto Run Result du premier passage (bloqué)

Status: blocked
Blocking condition: intent gap, catégorie contrats. Depuis la création de la spec, main a reçu les contrats 1.1 et la Story 5.3. Les Scénarios de démo sont configurés par `ConfigScenarioSortie`, `ConfigScenarioEnlisement` et `ConfigScenarioMenace` (`src/usine/contrats/config.py`, gelés, `extra="forbid"`), `config/programme.yaml` en porte les anciennes valeurs, et les tests de main exigent config = `SCENARIOS_PAR_DEFAUT`. Le modèle de la 4.5 ne s'y exprime pas.

Changement de contrat nécessaire (contrats 1.2) :
- `ConfigScenarioSortie` : ajouter `bloquantes_par_semaine: tuple[NombreScenario, ...]` (au moins 1) et `duree_bloquantes: int` (4 ≤ d ≤ 10) ; retirer `part_bloquantes_vague`.
- `ConfigScenarioEnlisement` : mêmes ajouts ; retirer `part_bloquantes` et adapter le validateur `part_bloquantes + part_majeures ≤ 1`.
- Puis `config/programme.yaml` : A bascule 4, flux (9, 2, 4), durée 7 ; B flux (3, 3, 4, 4, 5, 5, 6), durée 8, `part_majeures` 0,03, Certification `reservee` ; C 50 Cas de test par semaine, `taux_ko_hausse` jusqu'à 0,18.

À la reprise : prendre `serie.py` et `prevision_du_passage` de main (retirer `serie.py`/`previsions.py` de la lane, réaligner `test_serie.py` sur la sémantique de main) ; faire passer la recette par la Chaîne ou `usine rapport` ; appliquer les patchs du triage ; remplir `valeur_projetee_*` depuis `risque.py` (non fait). Avant l'arrêt, les cinq contrôles et `pytest -m lent` passaient sur la base de la lane (1899 tests).


### 2026-10-12 — Review pass (reprise, mode économique : Edge Case Hunter et Intent Alignment seuls ; Blind Hunter et Verification Gap non lancés)
- verdicts: 10 findings — high 0, medium 0, low 3, false 7, maybe-false 0
- findings:
  - `[low]` `[reject]` (edge-case) `dates_disponibles()` vide : `IndexError` sur `jours[-1]` dans `_ecarts_stock_ind_1` — le test échoue bruyamment de toute façon ; Passage publié sans Météo non atteignable ici, garde inutile.
  - `[low]` `[patch]` (edge-case) Prévisions en double à D masquées par le dict hors du test du vendredi — `_ecarts_sm6` exige désormais la liste publiée `[ENT-A, ENT-B]` à toute D.
  - `[low]` `[reject]` (edge-case, intent-alignment) la recette vérifie la présence de `valeur_projetee_*`, pas l'égalité avec `risque.py` — l'égalité est testée au domaine (`test_valeur_projetee_portee_par_chaque_risque`) et `prevision_du_passage` publie l'objet `RisqueEntreeRouge` de `risque.py` tel quel (`etapes.py:219`) ; recalcul dans la recette = duplication sans gain.
  - `[false]` `[reject]` (intent-alignment) changement d'Entité dans `series_stock` non testé par le diff — couvert sur `main` par `test_transfert_d_entite` (`test_serie.py:53`).
  - `[false]` `[reject]` (intent-alignment) IND-4 exigé le mardi seulement en `lent` — l'intention demande SM-6 hors vendredi en rapide (lundi fait) et IND-4 lundi et mardi ; le mardi est exigé en `lent`, conforme.
  - `[false]` `[reject]` (intent-alignment) graines 1, 7, 123 non croisées avec les semaines partielles — l'intention les liste séparément.
  - `[false]` `[reject]` (intent-alignment) AC SM-C3 honoré par omission — aucun écart à corriger, `git diff --stat` sur `config`, `contrats`, `ports`, `generateur`, `baseline.py` vide.
  - `[false]` `[reject]` (intent-alignment) C épinglé sur IND-4 plus strict que l'AC — conforme au patch du triage (IND-4 exigé).
  - `[false]` `[reject]` (intent-alignment) chemin `valeur_projetee_*` non touché dans la publication — la Chaîne passe l'objet tel quel ; la recette relit `previsions.json` et le vérifie.
  - `[false]` `[reject]` (intent-alignment) spec non suivie dans le diff — commitée avec la story.

## Auto Run Result

Status: done

- **Résumé :** reprise après contrats 1.2. `risques_entree_rouge` remplit `valeur_projetee_*` ; la recette SM-6 passe par un Passage réel (`lancer_rapport`, étape `prevision` = `prevision_du_passage`) et relit `previsions.json`.
- **Fichiers :**
  - `src/usine/domaine/prevision/risque.py` -- `valeur_projetee_*` du `RisqueEntreeRouge` depuis la `Fraction` projetée.
  - `tests/unit/domaine/prevision/test_risque.py` -- égalité valeur publiée / `valeur_projetee` (horizons 4, 5, 6, 10).
  - `tests/unit/domaine/prevision/test_recette_scenarios.py` -- recette par la Chaîne : rapide (graine 42, D vendredi et lundi), `lent` (D mardi à vendredi, graines 1, 7, 123), recoupement stock = IND-1.
- **Revue :** 1 patch (low, Prévisions en double), 0 report, 9 rejets (motifs au triage). Revue de suivi recommandée : false (aucun patch high ni deux medium).
- **Vérification :** ruff, ruff format, mypy, lint-imports (13 contrats), `pytest -q` 2338 passés, 1 ignoré ; `pytest -m lent` recette 7 passés.
- **Risques résiduels :** la recette utilise le Corpus provisoire de `generer_journal` (l’ancienne recette lisait le Corpus versionné) ; suite rapide allongée d'environ 12 s.

## Design Notes

**Pourquoi `lancer_rapport`.** C'est l'exécution réelle d'un Passage (registre de `construire_rapport`, étape `prevision` câblée sur `prevision_du_passage`), sans réécrire la fenêtre de calcul dans le test. Le Rapport Palier 1 est produit au passage ; son coût (~5 s) reste acceptable en rapide pour deux Passages.

## Verification

**Commands:**
- `uv run pytest -q tests/unit/domaine/prevision` -- expected: tout passe.
- `uv run pytest -q -m lent tests/unit/domaine/prevision/test_recette_scenarios.py` -- expected: SM-6 tenu.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: succès.
- `git diff --stat a663bf357641113585540dfdbb59a06106836ee0 -- config src/usine/contrats src/usine/ports src/usine/generateur src/usine/domaine/prevision/baseline.py` -- expected: vide.
