---
title: 'Story 1.3 : Génération reproductible à la volumétrie cible'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '94e9d3ced257ec743d9776ed4a88cc5a35e0fc5f'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
warnings: [oversized]
deferred:
  - summary: >-
      Le marqueur `lent` est enregistré par deux conftest de la lane (le second réimporte le premier) au lieu de `pyproject.toml` ; un test `lent` hors de ces répertoires tournerait par défaut, et un test `lent` désigné par son identifiant de nœud reste sauté sans `-m lent`.
    evidence: |-
      tests/unit/outils/conftest.py importe tests.unit.generateur.conftest (hooks chargés sous deux noms, ligne de marqueur en double) ; tests/unit/outils n'a pas de __init__.py. pyproject.toml et tests/conftest.py appartiennent à main : déplacer l'enregistrement (et l'exclusion par défaut) par une PR courte sur main, puis retirer les deux conftest.
    location: >-
      tests/unit/generateur/conftest.py, tests/unit/outils/conftest.py
    severity: low
  - summary: >-
      Aucun test n'exécute outils/mesurer_nfr2.py mesurer() (préparation de la racine temporaire, copie du gabarit) ; l'outil a déjà cassé sans bruit quand l'étape rendu est arrivée.
    evidence: |-
      tests/unit/outils/test_mesurer_nfr2.py ne couvre que programme_cible et une génération lent. Un test de fumée demanderait un Passage complet à 5 000 Anomalies (lent) ou d'extraire la préparation de la racine.
    location: >-
      outils/mesurer_nfr2.py (mesurer)
    severity: low
  - summary: >-
      Le Programme réduit (graine 42) n'a plus d'Entité rouge depuis le cycle de vie H-17 : la précondition de test_liens_jira accepte orange ou rouge.
    evidence: |-
      L'ancien rouge venait d'un backlog qui ne se fermait jamais. Le chemin des liens est vérifié sur la ligne orange (vus > 0). Un cas rouge scénarisé revient avec les Scénarios (Stories 1.5 et 1.8) ; à reprendre alors pour la démo.
    location: >-
      tests/unit/rendu/test_excel.py (test_liens_jira)
    severity: low
---

<intent-contract>

## Intent

**Problem:** Le générateur (Stories 1.1, 1.2) produit déjà un Journal reproductible aux bornes de la configuration, mais son cycle de vie des Anomalies n'est pas le workflow H-17 (raccourci Nouvelle → En correction, au plus 4 transitions sur des jours tirés au hasard dans tout l'historique : la plupart des Anomalies ne sont jamais fermées, les réouvertures sont quasi absentes et jamais depuis Rejetée). Deux reports de la Story 1.1 restent ouverts : plancher de 200 Entrées appliqué à une dernière semaine partielle d'un seul jour, créations qui saturent le maximum hebdomadaire et ne laissent aucune place aux réouvertures (d'où le plafond vers 4 000 Anomalies alors que la configuration en annonce 5 000).

**Approach:** Remplacer le cycle de vie par une marche le long du workflow H-17 strict, chaque étape séparée d'un délai tiré en Jours ouvrés, arrêtée à la Date d'injection, avec réouvertures depuis Fermée ou Rejetée. Proratiser les bornes d'Entrées d'une semaine partielle et réserver une marge de réouvertures sous le maximum hebdomadaire. Vérifier la volumétrie cible sur plusieurs graines et dates par un test marqué `lent`, exclu de la suite par défaut ; refaire la mesure NFR-2.

## Boundaries & Constraints

**Always:** générateur pur et déterministe (graine, date, Corpus, une seule instance `Random`, ordre de tirage fixe) ; formats du Journal et de la vérité terrain inchangés ; Cause racine seulement dans la vérité terrain ; transitions d'une Anomalie sur des Jours ouvrés distincts, strictement après la création et au plus tard à la Date d'injection ; une réouverture n'est gardée que si sa semaine reste sous le maximum d'Entrées ; suite par défaut rapide (une seule génération de la config livrée hors test `lent`).

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` ; modifier les bornes de `config/programme.yaml` (valeurs de l'AC 1.1) ; viser les identifiants sensibles (1.4), les Scénarios ou le calage de la Météo (1.5, 1.8) ; ajouter une dépendance.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Config livrée | graine 42, 2026-10-12 (8 semaines pleines) | 10 Entités, Anomalies dans [3 000, 4 000], chaque semaine 200 à 500 Entrées, réouvertures présentes | — |
| Dernière semaine partielle | date de génération un mardi (Date d'injection lundi) | semaine 8 : Entrées dans [⌊200 × 1/5⌋, ⌈500 × 1/5⌉] = [40, 100] ; semaines pleines inchangées | — |
| Bornes serrées | Anomalies = Σ maximum d'Entrées (ex. 160 ; 8 × 20) | toutes les semaines pleines de créations, aucune réouverture gardée | — |
| Volumétrie infaisable | Anomalies hors de [Σ min, Σ max] proratisés | refus | `UsineErreur` nommant les bornes |
| Workflow | tout Journal | transitions ⊂ {nouvelle→en_analyse, en_analyse→en_correction, en_analyse→rejetee, en_correction→a_retester, a_retester→fermee, a_retester→en_correction, fermee→en_analyse, rejetee→en_analyse} | — |
| Mesure NFR-2 | `programme_cible(42)` | 10 Entités, 5 000 Anomalies atteignables | — |

</intent-contract>

## Code Map

- `src/usine/generateur/journal.py` -- `_statut_suivant` (l.137, raccourci et réouverture depuis `fermee` seulement), `TRANSITIONS_MAX`/`PROBA_*` (l.59-82), `_jours_ulterieurs` (l.129, à retirer pour les Anomalies, garder pour les Cas de test), `_Calendrier.accepter_reouverture` (l.208), `_anomalie` (l.218), `_bornes_anomalies` (l.341), `_repartition_par_semaine` (l.360), `generer` (l.420, `jours_par_semaine` déjà calculé).
- `src/usine/contrats/tickets.py` (gelé) -- `StatutAnomalie`, `STATUTS_FERMES` = {fermee, rejetee}.
- `src/usine/domaine/kpi.py` (lecture seule) -- une Entrée par Anomalie et par jour au plus (`date_derniere_entree == date`) : transitions sur jours distincts indispensables.
- `tests/unit/generateur/test_journal.py` -- `TRANSITIONS_PERMISES` (l.44, contient le raccourci), `test_cycle_de_vie` (≤ 4 transitions), `_entrees_par_semaine` (réouverture = `de == "fermee"` seulement), `test_generation_config_livree`, `test_reouvertures_*`, `_variante`, `_volumetrie`.
- `outils/mesurer_nfr2.py` -- `programme_cible` (Entrées élargies à 1 250/semaine), sans test (report 1.1).
- `tests/unit/outils/` -- emplacement du test de `mesurer_nfr2`.
- `pyproject.toml` (hors lane, non modifié) -- `addopts = -m "not reseau"`, `--strict-markers` : le marqueur `lent` s'enregistre dans un `conftest.py` de la lane.
- `README.md` (hors lane) -- tableau NFR-2 (mesure du 2026-10-11, 54 310 événements).

## Tasks & Acceptance

**Execution:**
- `src/usine/generateur/journal.py` -- (a) `_statut_suivant` : workflow H-17 strict, réouverture depuis `fermee` et `rejetee` (`PROBA_REOUVERTURE` ≈ 0,1) ; (b) cycle de vie d'une Anomalie : marche d'étape en étape, délai par statut tiré en Jours ouvrés (≥ 1), arrêt au-delà de la Date d'injection ou sur statut terminal non rouvert, garde `TRANSITIONS_MAX` (≈ 12) ; (c) bornes d'Entrées par semaine proratisées au nombre de Jours ouvrés de la semaine (min arrondi bas, max arrondi haut, sur 5) utilisées par `_bornes_anomalies`, la répartition et `accepter_reouverture` ; (d) marge de réouvertures : plafond de créations par semaine = max − ⌊max × 10 %⌋ (au moins le min), nombre d'Anomalies tiré sous Σ plafonds quand c'est compatible avec le minimum d'Anomalies, sinon plafond = max ; docstrings à jour.
- `config/programme.yaml` -- commentaire de `anomalies_max` : intersection et marge expliquées, bornes inchangées.
- `tests/unit/generateur/conftest.py` -- créer : enregistre le marqueur `lent` et saute ces tests sauf si l'expression `-m` le sélectionne.
- `tests/unit/generateur/test_journal.py` -- transitions H-17 strictes, réouvertures depuis Rejetée dans `_entrees_par_semaine`, réouvertures présentes et dernier statut cohérent, semaine partielle, test `lent` multi-graines et multi-dates sur la config livrée (volumétrie, Entrées par semaine, workflow, vérité terrain, reproductibilité).
- `tests/unit/outils/test_mesurer_nfr2.py` -- créer : `programme_cible` (10 Entités, 5 000 Anomalies, Entrées élargies) ; génération à 5 000 dans un test `lent`.
- `README.md` (hors lane) -- tableau NFR-2 remesuré par `outils/mesurer_nfr2.py`.

**Acceptance Criteria:**
- Given la config livrée, une graine et une date de génération, when on génère, then le Journal a 10 Entités, 3 000 à 5 000 Anomalies, 200 à 500 Entrées par semaine pleine (bornes proratisées pour une semaine partielle) et l'historique va de l'ancrage (lundi, 8 semaines avant) à la Date d'injection.
- Given deux générations de même graine et même Corpus, when on compare, then Journal et vérité terrain sont identiques octet pour octet.
- Given le Journal, when on rejoue les transitions des Anomalies, then elles suivent le workflow H-17 (table de la matrice), au moins une réouverture existe sur la config livrée et chaque Anomalie a une Cause racine parmi les 7, absente de tout `Evenement`.
- Given `uv run pytest -q`, when la suite tourne, then les tests `lent` sont sautés ; `uv run pytest -m lent` les exécute et ils passent.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 23 findings — high 0, medium 1, low 15, false 7, maybe-false 0
- findings:
  - `[false]` `[reject]` (intent) Écart 5 000 / 4 000 élargi sur la config livrée — lecture A2+A3 retenue et consignée (Design Notes) ; l'AC 3 000-5 000 est tenue, les bornes du PRD ne sont pas modifiables sans contredire l'AC 1.1.
  - `[false]` `[reject]` (intent) Semaine partielle hors de 200-500 — proratisation explicitement demandée par l'intention (report 1.1).
  - `[low]` `[reject]` (intent) « Dates relatives » entre deux dates de génération non testées — l'AC compare deux exécutions de même graine et même Corpus ; identité octet pour octet à date égale testée ; décaler l'historique d'une date à l'autre n'est demandé nulle part.
  - `[low]` `[reject]` (intent) Fenêtre de l'historique de la config livrée vérifiée seulement en `lent` — `test_horodatages_ouvres_dans_la_fenetre` et `test_fenetre_generation` la vérifient dans la suite par défaut sur le Programme réduit (même code).
  - `[false]` `[reject]` (intent) Cause racine hors `Evenement` vérifiée seulement en `lent` — `test_verite_terrain` (suite par défaut) balaie le Journal sérialisé pour chacune des 7 causes.
  - `[false]` `[reject]` (intent) `test_excel.py` hors lane non annoncé — consigné et justifié dans les Design Notes.
  - `[low]` `[reject]` (intent) `lent` sauté plutôt que désélectionné — cosmétique (affichage « skipped »).
  - `[false]` `[reject]` (blind) Cas « bornes serrées » sans test — `test_reouvertures_bornees_par_le_maximum_d_entrees` ((160,160)/(1,20)) exerce la branche sans marge et vérifie `{20}`.
  - `[low]` `[reject]` (blind) Repli tout-ou-rien de la marge — n'arrive que sur une config où Σ plafonds < minimum d'Anomalies ; un étalement ajouterait une branche sans cas réel.
  - `[low]` `[reject]` (blind) Assertion de volumétrie lâche dans le test `lent` — `test_generation_config_livree` (suite par défaut) borne déjà à 3 600 ; le test `lent` vérifie l'AC.
  - `[low]` `[defer]` (blind) `mesurer()` sans test de régression, marge codée en dur dans `test_programme_cible` — consigné en `deferred` (outil manuel, test de fumée lent).
  - `[low]` `[defer]` (blind) Enregistrement fragile du marqueur `lent` — consigné en `deferred` (déplacement vers `pyproject.toml`, fichier de main).
  - `[low]` `[defer]` (blind) Plus d'Entité rouge dans le jeu réduit — consigné en `deferred` (cas rouge scénarisé en 1.5/1.8).
  - `[low]` `[reject]` (blind) Test mono-graine « fragile » — graine fixe, donc déterministe ; un changement de réglage qui le casse doit être vu.
  - `[low]` `[patch]` (blind) `jour_apres` : recherche linéaire et `ValueError` nue — table `{jour: rang}` précalculée.
  - `[low]` `[reject]` (blind) Volumes « environ 3 000 à 3 600 » sans le cas partiel — le commentaire de config mentionne la proratisation ; ordre de grandeur, pas une borne.
  - `[false]` `[reject]` (blind) Numéros de ligne périmés de la spec — corriger la spec de ce build est hors du triage.
  - `[low]` `[reject]` (edge) Garde `TRANSITIONS_MAX` qui fige une Anomalie dans un statut non terminal — garde documentée, atteinte par une poignée d'Anomalies à boucles de retest ; une Anomalie bloquée est plausible dans une usine.
  - `[low]` `[defer]` (edge) `tests/unit/outils` sans `__init__.py` — même racine que l'enregistrement du marqueur (entrée `deferred`).
  - `[low]` `[defer]` (edge) Hooks chargés sous deux noms — même racine (entrée `deferred`).
  - `[low]` `[patch]` (edge) `_rejouer_workflow` : `max()` sur séquence vide — `default=0`.
  - `[medium]` `[patch]` (verification-gap) Plafond proratisé des réouvertures d'une semaine partielle couvert seulement par un test `lent` — test rapide ajouté, semaine 8 saturée (date de génération un mardi).
  - `[low]` `[defer]` (verification-gap) `mesurer()` jamais exécuté par un test — même entrée `deferred` que la ligne blind.

## Design Notes

- **5 000 Anomalies inatteignables.** Une Anomalie compte au moins une Entrée (sa création) : 8 × 500 plafonne à 4 000. Les bornes 3 000-5 000 et 200-500 sont celles du PRD et de l'AC 1.1 ; on ne les touche pas. Le générateur tire dans l'intersection, moins une marge de 10 % par semaine pour les réouvertures (≈ [3 000, 3 600] sur la config livrée). La mesure NFR-2 garde 5 000 Anomalies (Entrées élargies) : c'est un majorant de charge.
- **Workflow strict.** L'AC énumère la chaîne Nouvelle → En analyse → En correction → À retester → Fermée ou Rejetée : le raccourci Nouvelle → En correction disparaît. Le retour À retester → En correction (retest KO) est gardé ; Rejetée ne vient que d'En analyse. Réouverture (PRD : sortie de Fermée ou Rejetée) → En analyse.
- **Délais.** Ordre de grandeur réaliste d'une usine : un cycle complet en deux semaines environ ; les Anomalies créées en fin d'historique restent ouvertes à la Date d'injection. Le Journal d'une graine change par rapport à la Story 1.2.
- **Marqueur `lent`.** Enregistré dans `tests/unit/generateur/conftest.py` (dans la lane) plutôt que dans `pyproject.toml` (hors lane) : `pytest -m lent` le sélectionne, la suite par défaut le saute.
- **Fichiers hors lane** : `README.md` (tableau de la mesure NFR-2, demandé par le run) ; `tests/unit/rendu/test_excel.py` (deux lignes : la précondition de `test_liens_jira` supposait une Entité rouge pour la graine 42 du Programme réduit, née d'un backlog qui ne se fermait jamais ; avec le cycle H-17 l'Entité est orange. La précondition accepte orange ou rouge, la vérification des liens est inchangée. Indispensable : la suite échoue sinon, et régler le générateur sur un test aval l'inverserait).
- **`outils/mesurer_nfr2.py`** copie aussi le gabarit PowerPoint (`CHEMIN_GABARIT`) : l'étape `rendu` livrée entre-temps sur `main` le lit, la mesure échouait sans lui.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check .` -- expected: aucun écart
- `uv run mypy && uv run lint-imports` -- expected: succès
- `uv run pytest -q` -- expected: tout passe, durée proche de l'actuelle, tests `lent` sautés
- `uv run pytest -q -m lent` -- expected: tests lents exécutés et verts
- `uv run python outils/mesurer_nfr2.py` -- expected: Passage dans la cible de 5 min

## Auto Run Result

Status: done

**Résumé.** Le cycle de vie des Anomalies suit le workflow H-17 strict (Nouvelle → En analyse → En correction ou Rejetée ; En correction → À retester → Fermée ou retour En correction ; réouverture depuis Fermée ou Rejetée vers En analyse). C'est une marche étape par étape, avec un séjour tiré en Jours ouvrés dans chaque statut (`DELAIS_PAR_STATUT`), arrêtée à la Date d'injection. Les bornes d'Entrées d'une dernière semaine partielle sont proratisées (report 1.1). Les créations laissent 10 % du maximum hebdomadaire aux réouvertures. Les bornes 3 000-5 000 / 200-500 de la config sont gardées : la config livrée produit environ 3 000 à 3 600 Anomalies, et 5 000 reste le majorant de la mesure NFR-2. La volumétrie cible sur 5 graines × 4 dates est vérifiée par un test `lent`, exclu de la suite par défaut.

**Fichiers.**
- `src/usine/generateur/journal.py` : workflow strict, marche temporisée, proratisation, marge de réouvertures, table des rangs de jours.
- `config/programme.yaml` : commentaire de `anomalies_max` (bornes inchangées).
- `outils/mesurer_nfr2.py` : copie du gabarit PowerPoint (l'étape `rendu` le lit).
- `tests/unit/generateur/conftest.py`, `tests/unit/outils/conftest.py` : marqueur `lent`.
- `tests/unit/generateur/test_journal.py` : workflow rejoué, semaine partielle, réouvertures, test `lent`.
- `tests/unit/outils/test_mesurer_nfr2.py` : `programme_cible`, génération à 5 000 (`lent`).
- Hors lane : `README.md` (tableau NFR-2 remesuré), `tests/unit/rendu/test_excel.py` (précondition orange ou rouge).

**Revue.** 23 constats : 3 correctifs (medium 1 : test rapide du plafond proratisé des réouvertures ; low 2 : `default=0`, table des rangs), 6 reportés (3 entrées `deferred` : marqueur `lent` à déplacer dans `pyproject.toml` sur main, `mesurer()` sans test, plus d'Entité rouge dans le jeu réduit avant les Scénarios), 14 rejetés avec leur raison dans le journal de triage. Revue complémentaire recommandée : non (un seul `medium`, corrigé par un test qui échoue sur le mutant).

**Vérification.** `ruff check`, `ruff format --check`, `mypy`, `lint-imports` (13 contrats) : succès. `pytest -q` : 1 404 passés, 22 sautés (`lent`), 65 s. `pytest -q -m lent` : 21 passés, 46 s. `outils/mesurer_nfr2.py` : 5 000 Anomalies, 63 781 événements, total 1,3 à 1,7 s, dans la cible.

**Risques résiduels.** Le Journal d'une graine diffère de celui de la Story 1.2, et les attendus fondés sur une graine peuvent bouger ailleurs (seul `test_excel` a cassé). Les tests `lent` ne tournent pas en CI. `controle_lanes.py` signalera `README.md` et `tests/unit/rendu/test_excel.py`.
