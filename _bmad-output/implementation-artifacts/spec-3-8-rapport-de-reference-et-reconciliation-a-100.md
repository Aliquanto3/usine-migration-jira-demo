---
title: 'Story 3.8 : Rapport de référence et réconciliation à 100 %'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '6f9768120dd34a517663f0f49a33097e6a2220ce'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** FR-13 et SM-1 exigent la preuve que KPI, Indicateurs et Météo calculés égalent un calcul fait à la main ; aucun Rapport de référence n'existe, et L4/L5 attendent cette preuve pour consommer les chiffres de L3.

**Approach:** livrer sous `tests/fixtures/reference/` un jeu réduit figé (H-20 : 2 Entités, environ 60 tickets, 1 Date d'arrêté) avec son Programme, sa Grille et un YAML de valeurs attendues calculées à la main (ticket par ticket, justifiées en commentaire), puis un test qui recalcule par le domaine et compare 100 % des valeurs en égalité stricte de couples entiers (H-26) ; ne corriger le domaine que si un écart révèle un défaut.

## Boundaries & Constraints

**Always:** valeurs attendues dérivées à la main de la conception du jeu, jamais produites en exécutant `usine.domaine` ; chaque valeur comparée en couple `(numerateur, denominateur)` strict (sans réduction, `4/20` ≠ `1/5`) ; ensembles de clés égaux (aucune ligne calculée absente du YAML, aucune ligne attendue absente du calcul) ; chemin de production pour les entrées : Journal lu par `SourceJournal`, Programme et Grille par `charger_yaml` + `verifier_grille`, `version_grille` par `contrats.versions` ; données fictives.

**Never:** modifier `src/usine/contrats/`, `src/usine/ports/`, `src/usine/chaine/` ou `composition.py` (branchement de l'étape `kpi` : lane L5) ; tolérance numérique ou flottant ; dépendre de `config/grille_meteo.yaml` (Grille figée copiée dans le jeu) ; ajouter une dépendance.

## I/O & Edge-Case Matrix

Jeu : ancrage lundi 2026-09-07, Date d'arrêté D = vendredi 2026-09-18 (J-5 = 11/09, Fenêtre glissante 14-18/09), Vague V1 en recette semaines 1-2, Grille par défaut figée.

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| ENT-A, tous déclenchés | 3 bloquantes, 5 majeures ouvertes ; 21 Cas exécutés (5 KO) en recette, 20 (2 KO) à J-5 ; 6 Entrées / 4 Sorties ; 1 refusée, 1 réservée | IND-1 3/1, IND-4 5/21, IND-5 1/1 rouges ; IND-2 9/1, IND-8 29/210 oranges ; IND-3 5/1, IND-6 1/1, IND-7 6/4 jaunes ; Météo rouge avec IND-1, IND-4, IND-5 | — |
| ENT-B, garde-fous | 0 bloquante ouverte ; 10 Cas exécutés (2 KO, rouge s'il était évalué) ; 4 Entrées, 2 Sorties | IND-2, IND-4, IND-7, IND-8 non évaluables (motif), autres verts ; Météo verte sans règle | — |
| Bornes et pièges | IND-1 = 3 et IND-3 = 5 (seuils `>=` atteints) ; IND-7 = 1,5 (`> 1.5` non franchi) ; Certification refusée d'une autre Vague ; Cas de test TNR ; clôture un samedi ; création à 00 h 30 heure de Paris ; événement postérieur à D | comptés ou exclus selon la règle ; rien ne change à D | — |
| Inspection du jeu | YAML attendu | chaque IND déclenché au moins une fois et non déclenché une fois ; IND-2, IND-4, IND-7, IND-8 évalués une fois et non évaluables une fois ; chaque garde-fou bloquant une fois et satisfait une fois | — |

</intent-contract>

## Code Map

- `src/usine/domaine/instantanes.py:119` -- `tickets_etats(evenements, dates)` : état par ticket et Jour ouvré ; appelé sur `jours_ouvres(ancrage, D)`.
- `src/usine/domaine/kpi.py:315` -- `kpi(etats, entites)` : 22 lignes par périmètre et date (`CODES_KPI`, `DIMENSIONS_KPI`), Programme compris ; défauts `0/1` (comptes) et `0/0` (âges, taux).
- `src/usine/domaine/meteo.py:489,526` -- `indicateurs(...)` (statut, motif, couple, couleur par IND) et `meteo(...)` (`MeteoEntite`, règles de la couleur retenue, seuil exact) ; motifs exacts l. 223, 257-264, 328-335, 346-357.
- `src/usine/adaptateurs/journal/__init__.py` -- `SourceJournal(chemin)` : `entete.ancrage_semaines`, `evenements()` ; ordre croissant d'horodatage exigé.
- `src/usine/config/chargeur.py` -- `charger_yaml(chemin, modele)` ; `src/usine/composition.py:276-282` montre le chargement de production de la Grille.
- `src/usine/contrats/config.py:106,189` -- `ConfigProgramme`, `GrilleMeteo` (gelés, `extra="forbid"`) ; `src/usine/contrats/versions.py:41` -- `version_grille(octets)`.
- `config/grille_meteo.yaml` -- Grille par défaut, copiée telle quelle dans le jeu.
- `.github/scripts/controle_lanes.py` -- lane 3 : `tests/fixtures/reference`, `tests/unit/domaine/meteo/` (miroir), `tests/unit/domaine/test_meteo.py`.

## Tasks & Acceptance

**Execution:**
- `tests/fixtures/reference/journal.jsonl` -- mini-Journal : en-tête puis événements par horodatage croissant, produit par un script jetable hors dépôt à partir de la table de conception -- jeu figé.
- `tests/fixtures/reference/programme.yaml`, `tests/fixtures/reference/grille_meteo.yaml` -- Programme réduit (ENT-A, ENT-B en V1 ; V1 recette S1-S2, TNR S3) et copie de la Grille par défaut -- entrées figées.
- `tests/fixtures/reference/attendu.yaml` -- table des tickets en commentaire, puis KPI à D (3 périmètres × 22 lignes), Indicateurs (2 × 8, motif compris), Météo (couleur, règles, seuils, tickets en cause), chaque valeur justifiée -- calcul à la main.
- `tests/unit/domaine/meteo/__init__.py`, `tests/unit/domaine/meteo/test_reconciliation.py` -- tests : taille et couverture du jeu (inspection) ; réconciliation KPI, Indicateurs, Météo en égalité stricte des ensembles de clés et des couples -- AC FR-13.

**Acceptance Criteria:**
- Given `tests/fixtures/reference/`, when on inspecte le jeu, then il compte 2 Entités, entre 50 et 70 tickets, 1 Date d'arrêté, et fait jouer chacun des 8 Indicateurs et des 3 garde-fous comme décrit dans la matrice.
- Given ce jeu, when le test calcule KPI, Indicateurs et Météo, then 100 % des valeurs sont égales au YAML, couples entiers comparés strictement, sans ligne en plus ni en moins.
- Given les cinq contrôles du dépôt, then ruff, ruff format, mypy, lint-imports et pytest passent, et `controle_lanes.py --branche lane/3-calcul --base main` réussit.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 29 findings — high 0, medium 1, low 20, false 8, maybe-false 0
- findings:
  - `[false]` `[reject]` (intent) AC1 vérifié sur le YAML et non sur le calcul — l'égalité stricte d'AC2 lie le YAML au calcul ; AC1 porte sur « le jeu » inspecté.
  - `[low]` `[reject]` (intent) IND-2/4/7/8 jamais « évalués et verts » — l'AC (déclenché + non évaluable) est tenu ; ce cas exige une Entité de plus, hors H-20.
  - `[low]` `[reject]` (intent) Ratio infini d'IND-7, IND-8 non évaluable par J-5 seul, borne exacte 5 absents — hors AC, troisième Entité nécessaire (Design Notes) ; branches couvertes par `tests/unit/domaine/test_meteo.py`.
  - `[false]` `[reject]` (intent) IND-4/7/8 rendus évaluables au-delà de la lecture « non évaluables seulement » — pas un défaut : l'AC demande déclenché et non évaluable.
  - `[false]` `[reject]` (intent) Couples comparés plus strictement que l'égalité de fractions — voulu (H-26, « comparés strictement ») ; l'égalité des couples implique celle des fractions.
  - `[low]` `[reject]` (intent) Motifs et conventions du domaine figés dans le YAML — voulu (« 100 % des valeurs ») : reformuler un motif doit être un changement conscient.
  - `[false]` `[reject]` (intent) Seule la tranche à D est comparée — l'AC fixe 1 Date d'arrêté ; J-5 est contrôlé par IND-8.
  - `[false]` `[reject]` (intent) Confiance prouvée au domaine, pas au rapport (Chaîne, Excel) — étape `kpi` et rendu relèvent de L5 (Epic 5) ; le jeu reste réutilisable sous `tests/fixtures/reference`.
  - `[false]` `[reject]` (intent) 58 tickets pour « environ 60 » — conforme ; l'ensemble exact est désormais vérifié.
  - `[low]` `[reject]` (edge) Branche « évalué et vert » d'IND-2/4/7/8 — comme la ligne intent correspondante.
  - `[low]` `[reject]` (edge) IND-8 non évaluable par J-5 seul — comme la ligne intent des branches absentes.
  - `[low]` `[patch]` (edge) Piège du samedi sur la date UTC et sur tout événement — transition vers `fermee` dont `jour_local` n'est pas ouvré.
  - `[low]` `[patch]` (edge) Piège nocturne sans contrôle de la nature — `nature is creation` exigé.
  - `[low]` `[patch]` (edge) `version_grille` comparé à lui-même — empreinte `c344967e71de` inscrite dans attendu.yaml et comparée.
  - `[false]` `[reject]` (edge) `_entier` repose sur `assert` (désactivé par `-O`) — pytest réécrit les assertions ; sous `-O` toute la suite perdrait ses assertions, mode jamais utilisé.
  - `[low]` `[reject]` (edge) `date_arrete` typé tardivement — l'erreur de fixture reste bloquante ; garde sans valeur ajoutée.
  - `[medium]` `[patch]` (blind) Tickets en cause d'IND-2, 3, 6, 7, 8 jamais réconciliés — section `meteo_variantes` (Grille dérivée, IND inactifs) : ENT-A orange (IND-2, IND-8) puis jaune (IND-3, IND-6, IND-7), calculée à la main.
  - `[low]` `[patch]` (blind) Agrégation seulement rouge contre vert — même correctif (variantes orange et jaune).
  - `[low]` `[reject]` (blind) « Non déclenché » satisfait par des non évaluables — comme la ligne intent correspondante.
  - `[low]` `[patch]` (blind) Tri naturel `rang_cle` non éprouvé — la variante jaune met REF-9 avant REF-11 (IND-3) et avant REF-10/12 (IND-7).
  - `[low]` `[patch]` (blind) `version_grille` sans valeur figée — groupé avec la ligne edge.
  - `[false]` `[reject]` (blind) Valeurs de J-5 non comparées, erreurs compensables — IND-4 à D (5/21) est comparé seul, donc IND-8 = 29/210 fixe IND-4(J-5) = 1/10 ; 19 exécutés rendraient IND-8 non évaluable.
  - `[low]` `[reject]` (blind) Réouvertures, reclassement, rejets et bornes absents de l'inspection — chacun change une valeur réconciliée (mutants vérifiés par la couche verification-gap) : redondant.
  - `[low]` `[patch]` (blind) Piège samedi en UTC et TNR sans `champ` — groupé avec la ligne edge ; `champ is Champ.phase` ajouté.
  - `[low]` `[patch]` (blind) En-tête « écrit à la main » et ensemble de tickets non figé — `modele_corpus` corrigé ; ensemble exact REF-1..REF-58 vérifié.
  - `[low]` `[patch]` (blind) Ordre des lignes de KPI et Indicateurs non vérifié — assertion sur la liste ordonnée des clés.
  - `[low]` `[reject]` (blind) Ratio infini et « hors Phase » non joués — comme la ligne intent des branches absentes.
  - `[low]` `[patch]` (blind) Docstring « non réduits » inexacte — « comparés sans réduction ».
  - `[low]` `[patch]` (verification-gap) Piège nocturne de REF-8 sans effet sur une valeur réconciliée — création déplacée à 2026-09-17T22:30Z (D à 00:30, Paris) ; entrées du jour ENT-A 2, Programme 3, âge 0 recalculés à la main.

## Design Notes

**« Déclenché et non évaluable ».** IND-1, IND-3, IND-5 et IND-6 sont des comptes, toujours évaluables : pour eux, « jouer » = déclenché sur une Entité et non déclenché (vert) sur l'autre. IND-2 (sans bloquante ouverte), IND-4, IND-7 et IND-8 sont en plus non évaluables sur ENT-B. Le cas « IND-4 évaluable à D mais pas à J-5 » exigerait une troisième Entité (hors H-20) : le garde-fou d'IND-8 est joué par « évaluable aux deux dates » (ENT-A) et « non évaluable à D » (ENT-B).

**Indépendance.** Le YAML est écrit depuis la conception du jeu (âges, Entrées, Sorties, taux dérivés ticket par ticket et justifiés en commentaire) avant toute exécution ; un écart au premier passage se tranche en relisant la règle métier (epic-3-context), jamais en recopiant la sortie du domaine.

**Conception du jeu (58 tickets `REF-n`, Vague V1, domaine `paie` sauf mention ; heures 08:00 UTC sauf mention).** Anomalies ENT-A : REF-1 bloq. recette 07/09, →en_analyse 09/09, →fermee 21/09 (après D) ; REF-2 bloq. recette 07/09, →fermee 10/09, →en_correction 15/09 ; REF-3 bloq. migration_a_blanc 16/09 ; REF-4 bloq. recette 08/09, →fermee samedi 12/09 ; REF-5 bloq. recette 15/09, →rejetee 17/09 ; REF-6 maj. recette 08/09, →en_correction 10/09, →a_retester 16/09 ; REF-7 maj. recette 14/09 ; REF-8 maj. tnr 2026-09-17T22:30Z (D à 00:30, Paris ; déplacé en revue) ; REF-9 maj. recette 18/09 ; REF-10 maj. recette 09/09, →fermee 16/09 ; REF-11 min. migration_a_blanc 09/09, gravité →majeure 15/09 ; REF-12 maj. recette 11/09, →fermee 18/09 ; REF-13 min. recette 14/09. Anomalies ENT-B : REF-14 bloq. recette 08/09, →fermee 15/09 ; REF-15 maj. recette 14/09 ; REF-16 maj. recette 17/09 ; REF-17 maj. recette 17/09, →rejetee 18/09 ; REF-18 maj. tnr 07/09, →fermee 09/09, →nouvelle 18/09 ; REF-19 min. migration_a_blanc 10/09. Certifications : REF-20 ENT-A V1 reservee 09/09, →refusee 16/09 ; REF-21 ENT-A V1 reservee 15/09 ; REF-22 ENT-A **V2** refusee 10/09 ; REF-23 ENT-B V1 accordee 11/09. Cas de test ENT-A recette, créés 07/09 : REF-24..41 ok, REF-42..43 ko, REF-44 non_execute ; REF-45 non_execute créé 16/09 ; puis REF-44 →ko et REF-24 →ko 14/09, REF-25 →ko 15/09, REF-26 →ko 16/09, REF-42 →ok 17/09. ENT-A tnr 07/09 : REF-46 ok, REF-47 ko. ENT-B recette 08/09 : REF-48..55 ok, REF-56..57 ko, REF-58 non_execute. Programme du jeu : V1 recette S1-S2 puis tnr S3 ; V2 recette S1-S3 (sans Entité) ; `nb_semaines: 3`.

**Hors périmètre.** Instantanés et Tendances ne sont pas dans l'AC (KPI, Indicateurs, Météo). L'étape `kpi` de la Chaîne reste un bouchon (lane L5, Epic 5, déjà consigné en 3.2/3.3).

## Verification

**Commands:**
- `uv run pytest -q tests/unit/domaine/meteo` -- expected: tous verts
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: succès
- `uv run python .github/scripts/controle_lanes.py --branche lane/3-calcul --base main` -- expected: tous les fichiers dans la lane

## Auto Run Result

- **Résumé :** Rapport de référence livré sous `tests/fixtures/reference/` (H-20 : 2 Entités, 58 tickets, D = 2026-09-18, Grille par défaut figée) avec valeurs attendues calculées à la main, et test de réconciliation à 100 % (H-26 : couples entiers comparés sans réduction, ensembles et ordre des lignes égaux) de KPI (66 lignes), Indicateurs (16 lignes, motifs compris), Météo et deux variantes de Grille (orange, jaune) couvrant les tickets en cause des 8 indicateurs. Concordance dès le premier passage : aucun défaut du domaine révélé, aucun code de production modifié.
- **Fichiers :**
  - `tests/fixtures/reference/journal.jsonl` -- mini-Journal (en-tête + 380 événements), pièges : samedi, nuit à Paris, événement après D, autre Vague, TNR, réouvertures, reclassement.
  - `tests/fixtures/reference/programme.yaml` -- Programme réduit commenté (ENT-A, ENT-B en V1).
  - `tests/fixtures/reference/grille_meteo.yaml` -- copie figée de la Grille par défaut (`version_grille` c344967e71de).
  - `tests/fixtures/reference/attendu.yaml` -- table des tickets et valeurs attendues justifiées (KPI, Indicateurs, Météo, variantes).
  - `tests/unit/domaine/meteo/__init__.py`, `tests/unit/domaine/meteo/test_reconciliation.py` -- 9 tests : inspection et couverture du jeu, réconciliation stricte.
- **Revue :** 29 constats (0 high, 1 medium, 20 low, 8 false). Patches : 1 medium (tickets en cause des couleurs non retenues, variantes de Météo) et 11 low (pièges samedi/nuit/TNR, REF-8 déplacé, empreinte figée, ordre des lignes, ensemble exact des tickets, docstring, en-tête). Aucun différé. Rejets motivés dans le Review Triage Log (branches nécessitant une troisième Entité hors H-20, surface rapport relevant de L5, rigueur voulue des couples et motifs).
- **Revue de suivi recommandée :** non (patches : 0 high, 1 medium, 11 low).
- **Vérification :** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (212 fichiers), `uv run lint-imports` (13 contrats), `uv run pytest -q` (1554 passés, 22 sautés) : verts après correctifs. Audit de matrice : ENT-A et ENT-B par les tests de réconciliation, bornes et pièges par l'inspection et les valeurs réconciliées, inspection par les tests de couverture ; tous passés. Valeurs attendues recoupées par un second calcul à la main indépendant (orchestrateur) et par la couche blind.
- **Risques résiduels :** ratio infini d'IND-7, IND-8 non évaluable par J-5 seul et IND-4 hors Phase non joués par ce jeu (troisième Entité, hors H-20 ; couverts par les tests unitaires du domaine) ; l'étape `kpi` de la Chaîne reste un bouchon (L5) ; toute reformulation d'un motif du domaine exige de mettre à jour attendu.yaml.
