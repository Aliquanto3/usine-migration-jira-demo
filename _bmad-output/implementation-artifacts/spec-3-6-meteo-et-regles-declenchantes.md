---
title: 'Story 3.6 : Météo et Règles déclenchantes'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'ca00a499d42355e3128c1b5c6a47164553722dab'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** depuis la Story 3.5, `domaine/meteo.py::meteo` calcule déjà la Météo (pire couleur, Règles déclenchantes, tickets en cause), mais les critères de la Story 3.6 (FR-16, FR-17, NFR-6) ne sont prouvés par aucun test : aucune Entité rouge par deux règles, aucune vérification des tickets en cause par type de règle sur une même `MeteoEntite`, ni de l'absence d'état d'un jour à l'autre, ni de la Météo publiée dans `meteo.json`.

**Approach:** fixer le comportement par des tests d'acceptation sur la surface `MeteoEntite` (domaine) et sur `meteo.json` publié par la Chaîne ; ne corriger le code du domaine que si un test révèle un écart ; documenter FR-17 dans la docstring de `meteo`.

## Boundaries & Constraints

**Always:** fonctions pures ; couleur retenue = pire couleur des indicateurs **évalués** ; toutes les Règles de la couleur retenue, dans l'ordre de `CodeIndicateur`, chacune avec valeur (`numerateur`/`denominateur`), opérateur, seuil et tickets triés par `rang_cle` ; `version_grille` porté par chaque `MeteoEntite` ; tickets en cause selon FR-17 (IND-1/2/3 Anomalies ouvertes ; IND-4/8 Cas de test KO de la Phase en cours ; IND-5/6 Certifications de la Vague en cours ; IND-7 Anomalies entrées et sorties sur la Fenêtre glissante).

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` ; modifier `chaine/etapes.py` ou `composition.py` ; changer la sélection des tickets d'IND-2 (plus ancienne(s), décision 3.5) ; implémenter l'Évolution J-1/J-5 (Story 3.7) ; hystérésis.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Rouge par IND-1 et IND-5 | Grille livrée ; 3 bloquantes ouvertes, 1 Certification refusée V1 | rouge ; 2 règles `IND-1` (3/1, `>= 3`, 3 Anomalies) et `IND-5` (1/1, `>= 1`, la Certification) ; `version_grille` = celle passée | — |
| Toutes les règles d'une couleur | Grille où chaque indicateur n'a qu'un seuil rouge bas ; flux qui les franchit tous | 8 règles rouges ; tickets de chaque règle du type FR-17 ; KO hors Phase en cours, Certification d'une autre Vague, mineures exclus | — |
| Sans état | 3 bloquantes ouvertes vendredi, 2 fermées lundi | vendredi rouge, lundi orange (pas de maintien du rouge) | — |
| Non évaluable sans effet | Grille livrée ; IND-1 orange ; 19 Cas exécutés tous KO ; 4 Entrées bloquantes | orange, seule la règle IND-1 ; IND-4, IND-7, IND-8 non évaluables | — |
| Tout non évaluable ou vert | Grille livrée ; seuls des indicateurs non évaluables | vert, `regles == ()` | — |
| Égalité de couleurs | 2 règles orange, 1 jaune | orange, les 2 règles orange seulement | — |

</intent-contract>

## Code Map

- `src/usine/domaine/meteo.py:522` -- `meteo(...)` : couleur retenue (`max` des `_couleur_franchie`), construction des `RegleDeclenchante` (seuil `Fraction` → `seuil_numerateur`/`seuil_denominateur`). `_couleur_franchie` (l. 474) rend vert pour un non évaluable. Tickets par indicateur : `_nombre_ouvertes` (l. 206), `_ind2` (l. 212), `_taux_ko` (l. 232), `_certifications` (l. 265), `_ind7` (l. 282), `_ind8` (l. 336).
- `src/usine/contrats/meteo.py:86-144` -- `RegleDeclenchante` (refuse 0/0, vert, seuil non franchi), `MeteoEntite` (vert ⇔ aucune règle ; règles de la couleur retenue). Lecture seule.
- `tests/unit/domaine/test_meteo.py` -- helpers à réutiliser : `_grille`, `_grille_seule`, `grille_livree`, `_calculer_meteo` (version `VERSION`), `_etats` (J-5..D), `_cas`, `_certification`, `_campagne`, `_hausse`, `_entrees_fenetre`, `_a`, constantes `LUNDI`, `VENDREDI`, `J5`, `ANCRAGE`, `PROGRAMME`. Les tests 3.5 couvrent déjà chaque indicateur isolément (`_regle_unique`).
- `tests/unit/domaine/constructeur.py` -- `Flux` (`anomalie`, `transition`, `creer`, `modifier`).
- `tests/unit/chaine/test_execution.py:155` -- `test_autoportance_meteo` : compare déjà `indicateurs.parquet` au domaine, pas `meteo.json` (hors lane).
- `src/usine/contrats/passage.py` -- `lire_enveloppe` pour relire `meteo.json`. Lecture seule.

## Tasks & Acceptance

**Execution:**
- `tests/unit/domaine/test_meteo.py` -- ajouter une section « Météo et Règles déclenchantes (Story 3.6) » : un test par ligne de la matrice ; le test « Toutes les règles » vérifie, pour chaque règle, que ses tickets ont le type FR-17 attendu en les recherchant dans l'état des tickets (type, gravité, statut, Phase, Vague) ; mettre la docstring du module à jour (Story 3.6, FR-17).
- `src/usine/domaine/meteo.py` -- docstring de `meteo` : tickets en cause par type de règle (FR-17), absence d'état ; corriger le calcul seulement si un test révèle un écart.
- `tests/unit/chaine/test_execution.py` -- dans `test_autoportance_meteo`, comparer `meteo.json` publié à un appel direct de `meteo` du domaine sur le même historique (règles, valeurs, tickets compris) -- surface publiée (hors lane).

**Acceptance Criteria:**
- Given les Indicateurs d'une Entité, when le domaine calcule la Météo, then la couleur la plus grave déclenchée l'emporte, verte sans Règle déclenchante, sans état d'un jour à l'autre, et un indicateur non évaluable ne change pas la couleur.
- Given une Entité rouge par IND-1 et IND-5, when on lit sa `MeteoEntite`, then elle liste les deux Règles rouges avec valeur mesurée, seuil franchi, tickets en cause et `version_grille`.
- Given chaque type de règle, when on lit ses tickets en cause, then ils suivent FR-17.
- Given la Grille livrée et le Journal du mini-jeu, when la Chaîne publie un Passage, then chaque `MeteoEntite` de `meteo.json` est égale à celle calculée directement par le domaine.
- Given les cinq contrôles du dépôt, then ruff, ruff format, mypy, lint-imports et pytest passent.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 22 findings — high 0, medium 2, low 13, false 7, maybe-false 0
- findings:
  - `[low]` `[patch]` (blind) `test_sans_etat` : l'assertion « sans l'historique » utilise `_etats(flux)`, qui contient encore le vendredi — second flux, jamais rouge (vendredi orange), même état au lundi : `MeteoEntite` du lundi égales.
  - `[medium]` `[patch]` (blind) Ligne de matrice « seuls des indicateurs non évaluables » non exercée (IND-1/3/5/6 évalués) — cas ajouté avec `_grille_seule("IND-2", "IND-4", "IND-7", "IND-8")` : vert, sans règle, 4 lignes `non_evaluable` alors qu'IND-4 évalué serait rouge.
  - `[low]` `[patch]` (blind) Aucun leurre d'une autre Entité dans le test FR-17 — leurres ENT-B (bloquante ouverte, KO de recette), calcul `["ENT-A", "ENT-B"]`, aucune clé ENT-B chez ENT-A.
  - `[low]` `[patch]` (blind) Prédicat IND-7 laxiste (toute Anomalie fermée) et Sortie non exercée — bloquante entrée le 2026-09-21 et fermée dans la Fenêtre (IND-7 = 5/1) ; prédicat : Entrée un jour de la Fenêtre ou ouverte la veille et fermée ce jour.
  - `[low]` `[patch]` (blind) Vague « V1 » codée en dur dans l'oracle des Certifications — lue dans `PROGRAMME`.
  - `[low]` `[patch]` (blind) `meteo.json` : `any(tickets_en_cause)` n'exige qu'une règle — `any(m.regles)` + `all(regle.tickets_en_cause ...)`.
  - `[low]` `[reject]` (blind) `version_grille` vérifié seulement contre le manifeste — préexistant et hors de ce changement : `test_execution.py:135` lie le manifeste à `rapport.donnees.version_grille`, calculé par la composition ; le test domaine `test_journal_genere` compare à `version_grille(octets)`.
  - `[low]` `[reject]` (blind) `test_autoportance_meteo` à scinder — confort de lecture, aucun défaut ; scinder dupliquerait le lancement de la Chaîne.
  - `[low]` `[patch]` (blind) `test_non_evaluable_sans_effet` repose sur des faits non vérifiés — motifs des garde-fous vérifiés (IND-4 « 19 », « garde-fou de 20 » ; IND-7 « 4 », « garde-fou de 5 » ; IND-8 « IND-4 non évaluable ») et commentaire (IND-4 évalué serait rouge).
  - `[low]` `[patch]` (blind) Docstring de `meteo` : `n/0` non expliqué ; « ne dépend que de l'état des tickets » inexact — `n/0` (n > 0) = infini ; « ne dépend d'aucune Météo antérieure, seulement des entrées de l'appel ».
  - `[low]` `[patch]` (edge) Prédicat IND-7 accepte une Anomalie fermée avant la Fenêtre — groupé avec la ligne blind correspondante.
  - `[false]` `[reject]` (edge) Retirer la garde `if not mesure.evaluee` passerait inaperçu — sans effet observable : une mesure non évaluable vaut `0/0` et `_franchit(0/0)` rend faux, donc la couleur reste verte ; aucune sortie fausse possible.
  - `[low]` `[patch]` (edge) Commentaire « sans l'historique » faux — groupé avec la première ligne blind.
  - `[medium]` `[patch]` (edge) Cas « tout non évaluable » jamais exercé — groupé avec la deuxième ligne blind.
  - `[false]` `[reject]` (intent) Surfaces de restitution (Consultation, rendu, UI) non testées — l'AC lit la `MeteoEntite` ; la restitution relève d'autres lanes et stories (Consultation FR-17, L5) ; la surface publiée par L3 (`meteo.json`) est vérifiée.
  - `[false]` `[reject]` (intent) Test de Chaîne à la limite de la lane — déclaré sous « Fichiers hors lane », sans code de Chaîne modifié.
  - `[false]` `[reject]` (intent) Tests sur du code non modifié — voulu (Design Notes) : 3.5 a livré `meteo`, 3.6 en prouve les critères ; aucun écart révélé.
  - `[low]` `[reject]` (intent) IND-2 : seulement la ou les plus anciennes — décision 3.5 (Design Notes 3.5) : la valeur d'IND-2 est l'âge de la plus ancienne, ce sont les Anomalies concernées ; changer la sélection est une décision produit.
  - `[false]` `[reject]` (intent) IND-5/6 limités à la Vague en cours — c'est la définition de l'indicateur (Grille : « Certifications refusées (Vague en cours) »).
  - `[false]` `[reject]` (intent) IND-7 limité aux bloquantes et majeures — définition de l'indicateur (« Ratio Entrées / Sorties d'Anomalies bloquantes et majeures »).
  - `[low]` `[patch]` (intent) Sorties d'IND-7 non exercées dans le test combiné — groupé avec la ligne blind IND-7.
  - `[false]` `[reject]` (intent) Trajectoires FR-3 de FR-16 non traitées — rattachées à la Story 1.8 (calage des Scénarios) par epics.md.

## Design Notes

**Pourquoi surtout des tests :** la Story 3.5 a livré `meteo` complète pour activer les huit indicateurs ; la 3.6 transforme ses critères en preuves sur la surface lue par le Pilote (`MeteoEntite`, puis `meteo.json`). Un écart révélé par ces tests se corrige dans `domaine/meteo.py`.

**Grille « tout rouge »** (test des types FR-17) : chaque indicateur porte un seul seuil rouge bas (IND-1 `>= 1`, IND-2 `> 0`, IND-3 `>= 1`, IND-4 `>= 0.05`, IND-5 `>= 1`, IND-6 `>= 1`, IND-7 `> 1`, IND-8 `>= 0.03`), garde-fous livrés. Flux : 1 bloquante et 1 majeure entrées à J-5, 5 bloquantes entrées dans la Fenêtre, campagne `_hausse(1 → 6 KO sur 20)` + 1 KO en `tnr`, Certification refusée et réservée en V1 + réservée en V2, 1 mineure.

**Fichiers hors lane :** `tests/unit/chaine/test_execution.py` (seul test qui lance la Chaîne et lit `meteo.json` publié ; ajout d'une comparaison, sans changer le code de la Chaîne).

## Verification

**Commands:**
- `uv run pytest -q tests/unit/domaine/test_meteo.py tests/unit/chaine/test_execution.py` -- expected: tous verts
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: succès

## Auto Run Result

- **Résumé :** la Météo et les Règles déclenchantes (livrées en code par la 3.5) sont prouvées sur la surface `MeteoEntite` et sur `meteo.json` publié : pire couleur des indicateurs évalués, vert sans règle, sans état d'un jour à l'autre, non évaluable sans effet, toutes les règles de la couleur retenue avec valeur, seuil, tickets et `version_grille`, tickets en cause par type selon FR-17. Aucun écart révélé : le calcul du domaine est inchangé, seule la docstring de `meteo` est complétée.
- **Fichiers :**
  - `src/usine/domaine/meteo.py` -- docstring de `meteo` : FR-16/FR-17, `n/0` infini, absence d'état.
  - `tests/unit/domaine/test_meteo.py` -- section Story 3.6 : un test par ligne de la matrice (rouge par IND-1 et IND-5, 8 règles et types FR-17 avec leurres, sans état, non évaluable sans effet, tout non évaluable ou vert, égalité de couleurs).
  - `tests/unit/chaine/test_execution.py` -- `meteo.json` publié égal au domaine, chaque règle avec tickets (hors lane).
- **Revue :** 22 findings ; 8 entrées corrigées (patch : 1 medium groupant 2 constats, 7 low dont 2 groupant plusieurs constats) ; 0 différé ; rejets (3 low, 7 false) motivés dans le Review Triage Log.
- **Revue de suivi recommandée :** non (patches : 0 high, 1 medium, 7 low).
- **Vérification :** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (201 fichiers), `uv run lint-imports` (13 contrats), `uv run pytest -q` (1479 passés, 1 sauté) : tous verts après correctifs. Audit de matrice : chaque ligne couverte par un test passé.
- **Risques résiduels :** IND-2 ne cite que la ou les plus anciennes bloquantes (décision 3.5, à revoir si le comité veut toutes celles au-delà du seuil) ; la restitution des règles dans Consultation, rendu et UI relève de L5/L7 ; les trajectoires FR-3 au jour près relèvent de la Story 1.8.
- **Fichiers hors lane :** `tests/unit/chaine/test_execution.py` (voir Design Notes).
