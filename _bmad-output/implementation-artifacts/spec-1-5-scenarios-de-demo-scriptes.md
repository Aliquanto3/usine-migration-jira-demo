---
title: 'Story 1.5 : Scénarios de démo scriptés'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '26311420d83f2474ad322cf22ee85f867dfb5fe6'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
warnings: [oversized]
deferred:
  - summary: >-
      Les paramètres des Scénarios vivent dans src/usine/generateur/scenarios.py et non dans config/programme.yaml comme le dit l'AC : ConfigProgramme (contrats-v1, gelé, extra="forbid") refuse toute clé nouvelle.
    evidence: |-
      Ajouter une clé `scenarios` à programme.yaml casserait la dizaine de chargeurs (composition, tests de plusieurs lanes) qui valident ce fichier par ConfigProgramme. À reprendre à la prochaine version des contrats : champ optionnel `scenarios` de ConfigProgramme, puis lecture par le générateur et option de désactivation en CLI (PR dédiée sur main).
    location: >-
      src/usine/contrats/config.py (ConfigProgramme) ; src/usine/generateur/scenarios.py
    severity: medium
  - summary: >-
      Le Journal ne trace pas les Scénarios qui l'ont produit : EnteteJournal (gelé) ne porte que graine, dates et Corpus.
    evidence: |-
      Deux générations de même graine et de Scénarios différents ont le même en-tête. À reprendre avec la clé `scenarios` des contrats (version ou empreinte des Scénarios dans l'en-tête).
    location: >-
      src/usine/contrats/evenements.py (EnteteJournal)
    severity: low
---

<intent-contract>

## Intent

**Problem:** Le générateur (Stories 1.1 à 1.4) tire toutes les Entités de la même façon : gravité uniforme (un tiers de bloquantes), Certification de statut aléatoire, 2 à 3 Cas de test par Entité. Avec la Grille par défaut (version 3 : rouge dès 3 bloquantes ouvertes ou une Certification refusée), presque toutes les Entités sont rouges en permanence, aucune trajectoire de FR-3 n'apparaît, et la graine 42 du Programme réduit n'a plus d'Entité rouge scénarisée (report de la 1.3).

**Approach:** Donner au générateur un profil « normal » qui vise le vert ou le jaune (bloquantes rares et traitées vite, majeures peu nombreuses, Certification accordée ou réservée, jamais refusée), et trois Scénarios scriptés par paramètres : A (vague de bloquantes de reprise de données en semaine 6, puis décrue : Sorties > Entrées dès la semaine 7), B (enlisement dès la semaine 2 : plus de créations, beaucoup de majeures, corrections très lentes) et C (Cas de test nombreux dont le taux de KO monte à partir de la semaine 4 et franchit 10 % en TNR, Certification réservée en semaine 4). Un test vérifie la forme générale des trajectoires sur le Journal et sur la Météo de fin de semaine ; le calage au jour près reste à la Story 1.8.

## Boundaries & Constraints

**Always:** générateur pur et déterministe (une seule instance `Random`, ordre de tirage fixe) ; volumétrie de la 1.3 inchangée (les Scénarios répartissent les créations d'une semaine, ils n'en ajoutent pas : bornes d'Entrées et d'Anomalies tenues) ; workflow H-17 et Cause racine seulement dans la vérité terrain ; identifiants (1.4) toujours tirés en dernier ; un Scénario dont l'Entité est absente de la configuration est ignoré ; paramètres typés, validés, documentés en français.

**Never:** modifier `src/usine/contrats/`, `src/usine/ports/` ou les seuils de `config/grille_meteo.yaml` (SM-C3) ; caler au jour près (Story 1.8) ; ajouter une dépendance ; ajouter une clé à `config/programme.yaml` que `ConfigProgramme` (gelé, `extra="forbid"`) refuserait.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Config livrée | graine 42, 2026-10-12 | A : bloquantes `reprise_donnees` créées à partir de la semaine 6, Sorties > Entrées en semaines 7 et 8 ; B : Entrées > Sorties semaines 2 à 8 ; C : taux de KO hebdomadaire plus haut à partir de la semaine 4 qu'en semaines 1 à 3, et croissant en TNR | — |
| Météo, config livrée | dernier Jour ouvré de chaque semaine | A verte ou jaune semaines 1 à 5, rouge 6 à 8 ; B rouge 2 à 8 ; C verte ou jaune jusqu'à 6, orange 7 et 8 ; autres : pas de rouge en fin d'historique, ≥ 80 % verts ou jaunes | — |
| Programme réduit | ENT-A et ENT-B, graine 42 | au moins une Entité rouge en fin d'historique ; bornes d'Entrées tenues | — |
| Entité absente | Scénario C sans ENT-C dans la config | Scénario ignoré, génération normale | — |
| Paramètre invalide | taux de KO hors [0, 1], semaine < 1 | refus à la construction | `UsineErreur` nommant le paramètre |

</intent-contract>

## Code Map

- `src/usine/generateur/journal.py` -- `generer` (l.542) : boucle des créations par semaine (l.609-614, `rng.choice(config.entites)`), Cas de test et Certification par Entité (l.615-620) ; `_anomalie` (l.272 : gravité uniforme l.281, cause l.284, marche du cycle de vie l.304-328 avec `DELAIS_PAR_STATUT` l.72) ; `_cas_de_test` (l.332), `_certification` (l.374 : statut uniforme) ; `_Calendrier.semaine` (l.244).
- `src/usine/generateur/scenarios.py` -- à créer : paramètres des Scénarios A, B, C et `SCENARIOS_PAR_DEFAUT` (Entités `ENT-A`, `ENT-B`, `ENT-C`).
- `src/usine/domaine/meteo.py` (L3, lecture seule) -- IND-1 bloquantes ouvertes (≥ 1 orange, ≥ 3 rouge), IND-2 âge de la plus vieille bloquante (> 5, > 10), IND-3 majeures ouvertes (≥ 5, 10, 20), IND-4 taux de KO des Cas de test exécutés dont `phase` = Phase en cours (garde-fou 20 exécutés), IND-5/IND-6 Certifications refusées/réservées de la Vague de l'Entité, IND-7 Entrées/Sorties bloquantes+majeures sur 5 Jours ouvrés (garde-fou 5 Entrées), IND-8 hausse d'IND-4 contre J-5. Les mineures ne comptent nulle part.
- `src/usine/domaine/instantanes.py` -- `tickets_etats(evenements, dates)` : état par date, entrée de `meteo`.
- `config/grille_meteo.yaml` (L3, lecture seule) -- seuils de la Grille version 3.
- `config/programme.yaml` -- ENT-A, ENT-B, ENT-C en Vague V1 (migration à blanc 1-2, recette 3-5, TNR 6-8) ; commentaire de renvoi vers les Scénarios.
- `src/usine/contrats/config.py` (gelé) -- `ConfigProgramme` en `extra="forbid"` : pas de clé `scenarios` possible.
- `tests/unit/generateur/test_journal.py` -- tests de volumétrie, workflow, reproductibilité, identifiants à garder verts ; `programme_reduit.yaml`.
- `tests/unit/rendu/test_excel.py` (hors lane) -- précondition orange ou rouge de la 1.3 (graine 42, Programme réduit).

## Tasks & Acceptance

**Execution:**
- `src/usine/generateur/scenarios.py` -- créer : `ScenarioSortie` (A), `ScenarioEnlisement` (B), `ScenarioMenace` (C), dataclasses gelées validées (`UsineErreur`), `Scenarios` (les trois, chacun optionnel) et `SCENARIOS_PAR_DEFAUT` ; docstrings en français décrivant la trajectoire visée.
- `src/usine/generateur/journal.py` -- profil normal (poids de gravité, délais prioritaires des bloquantes et majeures, Certification accordée ou réservée) ; Entité de chaque création tirée par poids (B renforcé dès sa semaine de début, A réduit pendant sa décrue) ; vague de bloquantes `reprise_donnees` lentes de A ; corrections lentes et majeures nombreuses de B ; Cas de test de C par semaine avec nombre exact de KO ; Certifications de A, B, C fixées par Scénario ; `generer(..., scenarios=SCENARIOS_PAR_DEFAUT)` ; docstrings à jour.
- `config/programme.yaml` -- commentaire : Scénarios de démo portés par le générateur (contrats gelés).
- `tests/unit/generateur/test_scenarios.py` -- créer : validation des paramètres, Scénario ignoré sans son Entité, forme des trajectoires sur le Journal (config livrée) et sur la Météo du dernier Jour ouvré de chaque semaine avec la Grille livrée ; Programme réduit avec une Entité rouge en fin d'historique.
- `tests/unit/rendu/test_excel.py` (hors lane) -- précondition rouge rétablie si le Programme réduit en redonne une.

**Acceptance Criteria:**
- Given la configuration livrée et `SCENARIOS_PAR_DEFAUT`, when le Journal est généré, then A a des bloquantes `reprise_donnees` à partir de la semaine 6 et Sorties > Entrées à partir de la semaine 7, B a Entrées > Sorties de la semaine 2 à la fin, et le taux de KO de C monte à partir de la semaine 4.
- Given le Journal et la Grille livrée, when on calcule la Météo au dernier Jour ouvré de chaque semaine, then la forme de FR-3 est tenue pour A, B et C, et hors A, B, C au moins 80 % des couples sont verts ou jaunes, aucune autre Entité n'est rouge en fin d'historique.
- Given `uv run pytest -q`, when la suite tourne, then tout passe sans toucher aux seuils de la Grille.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 25 findings — high 0, medium 5, low 17, false 3, maybe-false 0
- findings:
  - `[low]` `[patch]` (edge) Poids de mineures négatif en flottant (0.9 + 0.1) dans `_profil` B — `max(0.0, …)`.
  - `[low]` `[reject]` (edge) `statut_certification` non typé à la construction — usage interne par code typé (mypy) ; garde supplémentaire sans cas réel.
  - `[medium]` `[patch]` (edge) Semaine de Certification au-delà de l'historique : Certification posée un jour quelconque — `_verifier_semaines_scenarios` lève une `UsineErreur` (Scénario, paramètre, dernière semaine), testé.
  - `[medium]` `[patch]` (edge) Semaine de vague/début au-delà de l'historique : Scénario sans effet silencieux — même correctif.
  - `[low]` `[patch]` (edge) Docstring de `ScenarioMenace` : « profil normal » au lieu du profil calme — corrigée.
  - `[low]` `[patch]` (edge) Docstring de `ScenarioSortie` : idem avant la vague — corrigée.
  - `[low]` `[patch]` (edge) `min()` sur Counter vide dans `test_scenario_a_journal` — assertion de non-vacuité ajoutée.
  - `[low]` `[patch]` (blind) Docstring C contraire au code — même correctif que la ligne edge.
  - `[low]` `[patch]` (blind) Docstring A contraire au code — même correctif.
  - `[medium]` `[patch]` (blind) Semaines de Scénario jamais confrontées à l'historique — même correctif que les lignes edge.
  - `[low]` `[defer]` (blind) Scénarios non tracés dans l'en-tête du Journal — `EnteteJournal` gelé ; entrée `deferred`.
  - `[low]` `[reject]` (blind) Scénarios activés implicitement par code d'Entité, sans option CLI — choix documenté (commentaire de `programme.yaml`) ; la désactivation viendra avec la clé `scenarios` des contrats (entrée `deferred`).
  - `[low]` `[reject]` (blind) `ScenarioMenace` sans `statut_certification` — FR-3 fixe le jaune de C par une Certification réservée ; un paramètre de plus n'apporte rien.
  - `[low]` `[reject]` (blind) Rupture « même graine, même Journal » entre versions — attendue et consignée (Approach de la spec, Risques résiduels) ; la 1.3 avait fait de même.
  - `[low]` `[reject]` (blind) Tests sur la seule graine 42 — robustesse mesurée hors suite (57 graines sur 61) ; le calage relève de la 1.8.
  - `[low]` `[reject]` (blind) `_profil` et `_poids_entites` sans test direct — couverts par les tests de trajectoire, renforcés (cause forcée, semaines de Certification).
  - `[low]` `[patch]` (blind) Phase des Cas de test de C « celle de l'exécution » non justifiée — hypothèse (bornes de Phase sur les semaines) écrite dans la docstring.
  - `[low]` `[reject]` (blind) Pas de Cas de test de C la dernière semaine d'un seul Jour ouvré — documenté dans la docstring ; effet au jour près = 1.8.
  - `[low]` `[reject]` (blind) `_profil` reconstruit à chaque Anomalie — coût négligeable (durée de la suite inchangée).
  - `[false]` `[reject]` (blind) Précondition rouge de `test_liens_jira` couplée aux Scénarios — c'est l'objectif demandé (report de la 1.3 : redonner une Entité rouge au jeu réduit).
  - `[medium]` `[patch]` (verification-gap) Cause `reprise_donnees` forcée non vérifiée (un mutant à 3 bloquantes passait) — le test exige que toutes les bloquantes de A en semaine 6 soient `reprise_donnees`.
  - `[low]` `[patch]` (verification-gap) Semaine de Certification de A et B non vérifiée — `test_certifications` exige (accordée, 3) et (refusée, 4).
  - `[medium]` `[defer]` (intent) Configuration hors de `config/programme.yaml` — imposé par les contrats gelés ; entrée `deferred`.
  - `[false]` `[reject]` (intent) Sortie projetée de A, absence de sortie de B, Risque d'entrée de C non testés — surface de la Prévision (Epic 4, Story 4.5) et du calage (1.8) ; l'AC 1.5 porte sur le Journal.
  - `[false]` `[reject]` (intent) Règles au jour près (≤ 3 jours rouges consécutifs, 80 % sur tous les couples) échantillonnées par semaine — l'AC renvoie explicitement le calage au jour près à la 1.8.

## Design Notes

- **Où vivent les Scénarios.** L'AC vise `config/programme.yaml`, mais `ConfigProgramme` (contrats-v1, gelé, `extra="forbid"`) refuse toute clé nouvelle et une dizaine de chargeurs, dans plusieurs lanes, lisent ce fichier. Les paramètres sont donc typés dans `generateur/scenarios.py` et passés à `generer` ; `programme.yaml` y renvoie par un commentaire. Report consigné : clé `scenarios` à ajouter à `ConfigProgramme` à la prochaine version des contrats (PR dédiée sur `main`).
- **Mécanismes.** Rouge par IND-1/IND-2 (A : bloquantes lentes ; B : bloquantes et majeures qui s'accumulent), orange de C par IND-4 en TNR (≥ 10 %, < 20 % pour rester « menace »), jaune de C par IND-6 (Certification réservée en semaine 4). Les mineures, invisibles pour la Grille, portent l'essentiel de la volumétrie des Entités normales.
- **Profil calme.** Une Entité scénarisée, hors des semaines de son Scénario (et C partout), n'a pas de bloquante et deux fois moins de majeures (`PROFIL_CALME`) : sa trajectoire ne dépend plus d'une bloquante tirée au hasard (avec le profil normal, A était orange en fin de semaine 5 pour la graine 42).
- **Fichiers hors lane** : `tests/unit/rendu/test_excel.py` (précondition de `test_liens_jira` : de nouveau une Entité rouge exigée au jeu réduit graine 42, report de la 1.3).
- **Forme, pas calage.** Le test lit la Météo au dernier Jour ouvré de chaque semaine ; la bascule au jour près (lundi de la semaine 6, premiers jours d'une Phase sous le garde-fou d'IND-4…) est l'objet de la 1.8.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check .` -- expected: aucun écart
- `uv run mypy && uv run lint-imports` -- expected: succès
- `uv run pytest -q` -- expected: tout passe
- `uv run pytest -q -m lent` -- expected: tests lents verts

## Auto Run Result

Status: done

**Résumé.** Le générateur porte un profil normal qui vise le vert ou le jaune avec la Grille par défaut. Ce profil tire les gravités bloquante, majeure et mineure à 2, 40 et 958 pour mille, traite plus vite les bloquantes et les majeures, et ne refuse jamais une Certification. Il porte aussi trois Scénarios scriptés par paramètres (`generateur/scenarios.py`, `SCENARIOS_PAR_DEFAUT`, passés à `generer`) :
- **A (ENT-A).** Vague de bloquantes `reprise_donnees` lentes en semaine 6, puis décrue : Sorties > Entrées en semaines 7 et 8.
- **B (ENT-B).** Enlisement dès la semaine 2 : poids 3, nombreuses majeures, corrections de 3 à 6 semaines, Certification refusée en semaine 4. Les Entrées dépassent les Sorties.
- **C (ENT-C).** 30 Cas de test par semaine, avec un nombre exact de KO : 3 %, puis une hausse dès la semaine 4 qui franchit 10 % en TNR. Certification réservée en semaine 4.

Les Scénarios répartissent les créations d'une semaine sans en ajouter : la volumétrie de la 1.3 est tenue. Avec la graine 42, la Météo du dernier Jour ouvré de chaque semaine donne :
- A : vert ou jaune en semaines 1 à 5, puis rouge.
- B : rouge dès la semaine 2.
- C : vert ou jaune jusqu'à la semaine 6, avec du jaune, puis orange.
- Autres Entités : au moins 80 % de vert ou de jaune, aucune rouge en fin d'historique.

Le Programme réduit retrouve une Entité rouge (report de la 1.3).

**Fichiers.**
- `src/usine/generateur/scenarios.py` (nouveau) : paramètres validés des Scénarios A, B et C.
- `src/usine/generateur/journal.py` : profils normal, calme et de Scénario, tirage pondéré des Entités, Cas de test de C, Certifications imposées, contrôle des semaines de Scénario.
- `config/programme.yaml` : commentaire de renvoi vers les Scénarios (aucune clé ajoutée).
- `tests/unit/generateur/test_scenarios.py` (nouveau) : paramètres, Entité absente, trajectoires sur le Journal, Météo de fin de semaine, Programme réduit.
- Hors lane : `tests/unit/rendu/test_excel.py` (précondition rouge rétablie).

**Revue.** 25 constats, 4 entrées corrigées :
- medium (2) : semaines de Scénario confrontées à l'historique (`UsineErreur`) ; cause `reprise_donnees` de la vague de A vérifiée.
- low (2) : poids flottant borné à 0 ; docstrings et assertions des tests de A et des Certifications.

2 entrées `deferred` :
- Scénarios à déplacer dans `config/programme.yaml` (clé `scenarios` de `ConfigProgramme`, prochaine version des contrats).
- Scénarios non tracés dans `EnteteJournal`.

Rejets, avec leur raison dans le journal de triage : graine unique, activation implicite, `_profil` sans test direct, dernière semaine partielle, performance, signaux de Prévision (Epic 4) et règles au jour près (1.8).

**Revue complémentaire recommandée : oui.** Deux entrées medium ont été corrigées. Risque non vérifié : le nouveau contrôle des semaines refuse désormais toute configuration qui contient ENT-A, ENT-B ou ENT-C avec moins de 6 semaines, et les Scénarios ne se désactivent pas en CLI. Seuls les tests de la lane ont éprouvé ce comportement.

**Vérification.** `ruff check`, `ruff format --check`, `mypy` et `lint-imports` (13 contrats) passent. `pytest -q` : 1 619 passés, 1 sauté, 21 désélectionnés. `pytest -q -m lent` : 21 passés. Robustesse mesurée hors suite avant les correctifs de revue : forme tenue sur 57 graines sur 61.

**Risques résiduels.**
- Le Journal de toute graine change, et les lanes aval voient de nouvelles données.
- Les tests de trajectoire reposent sur la graine 42.
- Les Scénarios dépendent du calendrier V1 livré (TNR en semaine 6, bornes de Phase sur les semaines).
- Le calage au jour près relève de la 1.8 : bascule le lundi de la semaine 6, premiers jours de TNR sous le garde-fou d'IND-4.
- `controle_lanes.py` signalera `tests/unit/rendu/test_excel.py`.
