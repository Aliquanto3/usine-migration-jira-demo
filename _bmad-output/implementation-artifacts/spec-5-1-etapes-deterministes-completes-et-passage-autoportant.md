---
title: 'Story 5.1 : Étapes déterministes complètes et Passage autoportant'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'affbd8fecd6e9fc1848fbddbf0aa5ef5cc4ccd06'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-5-context.md'
warnings: ['oversized']
deferred:
  - summary: >-
      Câbler EtapePrevision dans le registre de composition.py dès que domaine/prevision (Stories 4.1 et 4.2, lane L4) est sur main.
    evidence: |-
      Le registre garde EtapeBouchon() pour prevision : un Passage réel n'a ni previsions.json ni trace/previsions.jsonl (AC 1 et AC 2 prouvés seulement par une EtapePrevision injectée en test). Il faudra une fonction prevoir(ctx) -> ContenuPrevisions qui lit le Passage et appelle le domaine, plus empreinte_donnees et l'horloge de construire_rapport (docstring de l'horloge à étendre aux traces de Prévision).
    location: >-
      src/usine/composition.py (registre de construire_rapport)
    severity: medium
  - summary: >-
      Configurer la journalisation et l'encodage UTF-8 de la console de la CLI (rétrospective de l'Epic 0, constat 15) en Story 5.5.
    evidence: |-
      Aucun logging.basicConfig ni reconfiguration de sys.stdout dans la CLI ; sous Git Bash la sortie s'affiche « Journal �crit ». Hors du périmètre « Passage autoportant », relève de la commande unique (Story 5.5).
    location: >-
      src/usine/cli.py, src/usine/chaine/cli.py
    severity: low
---

<intent-contract>

## Intent

**Problem:** Un Passage publié ne contient encore ni `kpi.parquet` ni `tendances.parquet` : l'étape `kpi` est un bouchon, et rien ne branche `domaine.kpi.tendances`. L'étape `prevision` n'a aucune enveloppe capable d'écrire `previsions.json` et une `EntreeTrace` par Prévision (AD-16, FR-34).

**Approach:** Ajouter dans `chaine/etapes.py` une `EtapeKpi` qui passe à `domaine.kpi.kpi` l'état des tickets depuis le début de l'historique, puis à `tendances(kpi, D, ancrage)`. Ajouter aussi une `EtapePrevision` générique : elle reçoit une fonction de prévision injectée, écrit `previsions.json` et rend une trace par Prévision et par Risque. Câbler `EtapeKpi` dans `composition.py`. L'étape `prevision` reste un bouchon tant que `domaine/prevision` (lane L4) n'est pas sur `main`.

## Boundaries & Constraints

**Always:** les étapes enveloppent les fonctions du domaine sans aucun recalcul ; elles lisent le Passage en cours par `ctx.consultation` et n'écrivent rien (l'`EcrivainPassage` écrit et valide chaque fichier par son contrat). L'ancrage des semaines est `EnteteJournal.ancrage_semaines`, déjà passé à `EtapeInstantanes` et `EtapeMeteo` sous le nom `premier_jour`. Les sorties de `kpi` couvrent chaque Jour ouvré de l'historique jusqu'à la Date d'arrêté. Une trace de Prévision porte `type_trace=prevision`, le `passage_id`, la Date d'arrêté de la Prévision, l'Entité en `cible`, `version_grille` de la Prévision, la `version_donnees` injectée et un horodatage pris à l'horloge injectée.

**Never:** toucher `contrats/` ou `ports/` (gelés). Inventer une Baseline ou un Risque hors de `domaine/prevision` (lane L4). Modifier le calcul du nombre d'alignements ou de `horodatage_extraction` dans `execution.py` (Story 2.6, lane L2, en cours). Configurer la journalisation ou l'encodage de la console (périmètre de la CLI, Story 5.5).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Passage nominal | Journal généré (graine 42), D = 2026-10-09 | `kpi.parquet` = `domaine.kpi.kpi(tickets_etats du Passage, entités)` ; `tendances.parquet` = `tendances(kpi, D, ancrage)` ; une date KPI par Jour ouvré de l'ancrage à D | Aucune |
| Aucun ticket à D | D antérieure à toute création | `kpi.parquet` et `tendances.parquet` écrits vides, Passage publié | Aucune |
| Prévisions injectées | `prevoir` rend 1 Prévision + 1 Risque | `previsions.json` enveloppé ; 2 lignes dans `trace/previsions.jsonl`, dans l'ordre du contenu | Aucune |
| Sans Prévision | `prevoir` rend un contenu vide | `previsions.json` écrit avec des tuples vides, aucune trace | Aucune |
| Prévision d'un autre type | `prevoir` rend autre chose qu'un `ContenuPrevisions` | Passage en échec, étape `prevision` nommée | `UsineErreur` |

</intent-contract>

## Code Map

- `src/usine/chaine/etapes.py` -- `jours_du_passage`, `EtapeInstantanes`, `EtapeMeteo` (boucle sur les jours, `ctx.consultation.tickets_etats(jour)`), `EtapeBouchon` : ajouter `EtapeKpi` et `EtapePrevision` ici.
- `src/usine/domaine/kpi.py:315` `kpi(tickets_etats, entites)` -- exige tous les Jours ouvrés de la première à la dernière date de la table ; `:360` `tendances(kpi_quotidiens, date_arrete, ancrage)` -- refuse une D absente d'une table non vide.
- `src/usine/consultation/passage.py:355` `tickets_etats(date)` -- table en cache, filtrée par date (lecture jour par jour peu coûteuse).
- `src/usine/chaine/ecrivain.py` -- `SCHEMAS_TABLES` (déjà `kpi`, `tendances`), `ajouter_traces` (déjà `trace/previsions.jsonl`) : aucune modification attendue.
- `src/usine/chaine/execution.py` -- manifeste : `source`, `nb_tickets`, `version_*`, `etapes` (durées) déjà présents ; `horodatage_extraction=None` et `nb_alignements=0` relèvent de la Story 2.6 : ne pas toucher.
- `src/usine/contrats/prevision.py` -- `ContenuPrevisions`, `Prevision`, `RisqueEntreeRouge` (lecture seule) ; `src/usine/contrats/trace.py` -- `EntreeTrace` (lecture seule).
- `src/usine/composition.py:363` -- registre : `Etape.kpi: EtapeBouchon()` à remplacer (fichier hors lane).
- `tests/unit/chaine/test_execution.py` -- `test_passage_publie` (liste des fichiers), `test_autoportance_meteo` (modèle de comparaison au domaine), `test_jours_sans_ticket_verts`.
- `tests/unit/chaine/environnement.py` -- `preparer_racine`, horloges, `DATE_ARRETE`.

## Tasks & Acceptance

**Execution:**
- `src/usine/chaine/etapes.py` -- ajouter `EtapeKpi(entites, premier_jour)` : concatène `tickets_etats` de chaque jour de `jours_du_passage`, appelle `kpi`, puis `tendances` avec `premier_jour` comme ancrage, sorties `kpi` et `tendances`. Ajouter `EtapePrevision(prevoir, version_donnees, horloge)` : `prevoir(ctx)` rend un `ContenuPrevisions` (sinon `UsineErreur`), sortie `previsions`, une `EntreeTrace` par Prévision puis par Risque (`sortie` = JSON du modèle, `entree_pseudonymisee` = JSON de l'identité : Date d'arrêté, Entité, méthode ou indicateur). Mettre à jour la docstring du module.
- `src/usine/composition.py` -- `Etape.kpi: EtapeKpi(entites, premier_jour)` ; `prevision` reste `EtapeBouchon()` avec un commentaire qui renvoie à L4 ; docstring à jour.
- `tests/unit/chaine/test_etapes.py` -- tests d'`EtapePrevision` (contenu, traces, ordre, contenu vide, type refusé) et d'`EtapeKpi` sur un historique construit (`Flux`), dont le cas sans ticket.
- `tests/unit/chaine/test_execution.py` -- liste des fichiers publiés (`kpi.parquet`, `tendances.parquet`) ; autoportance des KPI (dates = Jours ouvrés de l'ancrage à D) et égalité stricte avec un appel direct de `kpi` et de `tendances` ; manifeste complet (champs de l'AC 3, relus dans `manifeste.json`) ; Passage de bout en bout avec une `EtapePrevision` injectée qui écrit `previsions.json` et `trace/previsions.jsonl`, relus par `Consultation`.

**Acceptance Criteria:**
- Given le registre de `composition.py`, when un Passage s'exécute sur le Journal de test, then `kpi.parquet` et `tendances.parquet` sont publiés, égaux aux sorties directes de `domaine.kpi`, et les KPI couvrent chaque Jour ouvré de l'ancrage à la Date d'arrêté.
- Given une `EtapePrevision` dans le registre, when le Passage est publié, then `previsions.json` est relu par `Consultation.previsions()` / `risques()` et chaque Prévision et chaque Risque a sa ligne dans `trace/previsions.jsonl`, relue par `Consultation.traces()`.
- Given le manifeste publié, when on le relit, then il porte `date_arrete`, `source`, `horodatage_extraction` (nul sans extraction), `nb_tickets`, `nb_alignements`, `version_grille`, `version_donnees`, une exécution datée par étape et `contrats_version`.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 23 findings — high 0, medium 5, low 9, false 7, maybe-false 2
- findings:
  - `[medium]` `[defer]` (intent) `previsions.json` et `trace/previsions.jsonl` absents d'un Passage réel, AC 1 et AC 2 prouvés par injection seulement — le bouchon est demandé par l'intention tant que L4 n'est pas sur `main` ; câblage consigné dans `deferred`.
  - `[false]` `[reject]` (intent) l'étape `extraction` n'est ni touchée ni testée — elle enveloppe déjà `extraire` (Story 2.4) et n'est active qu'avec un secret ; rien à faire dans cette story.
  - `[low]` `[patch]` (intent) `test_manifeste_complet_relu` fige `nb_alignements == 0`, valeur de la Story 2.6 — assertion remplacée par un entier ≥ 0 égal au manifeste.
  - `[medium]` `[defer]` (intent) journalisation et encodage consignés seulement dans la spec — consignés dans `deferred` pour la Story 5.5, comme l'intention le permet.
  - `[low]` `[reject]` (intent) durées par étape vérifiées seulement par présence — `test_manifeste` vérifie déjà `horodatage_fin > horodatage_debut` pour chaque étape.
  - `[maybe-false]` `[reject]` (intent) historique commençant avant l'ancrage (lecture b) — le Journal commence à `ancrage_semaines` et `instantanes` partage ce même premier jour ; à reprendre seulement si la source composite (2.6) change le premier jour, et l'effet serait au plus low.
  - `[medium]` `[defer]` (blind) AC 1 non tenu par `composition.py` pour `prevision`, sans suivi — même cause que le premier constat, consigné dans `deferred`.
  - `[low]` `[reject]` (blind) docstring de `horloge` de `construire_rapport` incomplète pour le câblage futur — rien ne l'utilise encore pour les Prévisions ; mentionné dans l'entrée `deferred`.
  - `[medium]` `[patch]` (blind) docstrings annonçant des KPI sur « chaque Jour ouvré » depuis l'ancrage — corrigées : KPI denses à partir du premier jour où un ticket existe.
  - `[low]` `[patch]` (blind) branche `else` morte dans `EtapeKpi.executer` — supprimée (`jours_du_passage` rend toujours au moins la Date d'arrêté).
  - `[low]` `[reject]` (blind) historique lu deux fois (`EtapeKpi` et `EtapeMeteo`) — la table est en cache dans `ConsultationPassage`, chaque lecture n'est qu'un filtre ; la mesure NFR-2 viendra en 5.6.
  - `[false]` `[reject]` (blind) `EtapePrevision` ne vérifie pas `date_arrete == ctx.date_arrete` — par AD-7, les Prévisions couvrent chaque Jour ouvré ≤ D, une autre date est légitime.
  - `[low]` `[reject]` (blind) traces de Risque peu distinguables par `cible` — `cible` est l'Entité par contrat (`EntreeTrace`), l'indicateur est dans `entree_pseudonymisee` et `sortie`.
  - `[false]` `[reject]` (blind) aucun test de Rejeu sur les nouveaux fichiers — le Rejeu est l'objet de la Story 5.5, hors de l'intention de la 5.1.
  - `[false]` `[reject]` (blind) ordre des traces non vérifié après relecture — `test_passage_avec_previsions` vérifie l'ordre relu `[(prevision, ENT-A), (prevision, ENT-B)]`.
  - `[low]` `[reject]` (blind) liste de champs codée en dur dans `test_manifeste_complet_relu` — c'est exactement la liste de l'AC 3 ; un nouveau champ serait un changement de contrat gelé.
  - `[false]` `[reject]` (blind) Instantanés et Météo non revérifiés — `test_autoportance_meteo` et les tests existants les couvrent, ils passent.
  - `[false]` `[reject]` (edge) `tickets_etats.parquet` absent → KPI vides en succès — l'étape `instantanes` du registre écrit toujours ce fichier avant `kpi` ; état non démontré.
  - `[low]` `[patch]` (edge) jours de tête sans ticket sans ligne KPI — même cause que les docstrings ; comportement du domaine documenté (Design Notes), docstrings corrigées.
  - `[maybe-false]` `[reject]` (edge) `date_arrete` d'une Prévision différente de `ctx.date_arrete` — légitime par AD-7 (une Prévision par Jour ouvré) ; ce que produira L4 tranchera, effet au plus low.
  - `[low]` `[reject]` (edge) `version_grille` d'une Prévision différente du Passage — la trace reprend la version portée par la Prévision elle-même ; garde sur un état non démontré.
  - `[false]` `[reject]` (edge) Prévisions en double ou d'Entité inconnue — aucune fonction de prévision n'existe ; garde sur un état non démontré, à poser par le domaine L4.
  - `[medium]` `[patch]` (edge, claim) couverture dense annoncée par la docstring de `composition.py` — même cause que le constat des docstrings, groupé avec lui : docstring corrigée.

## Design Notes

**Prévision en bouchon.** `domaine/prevision` (Stories 4.1 et 4.2, lane L4) n'est pas sur `main`. `EtapePrevision` reçoit donc la prévision sous la forme d'une fonction injectée, `Callable[[ContextePassage[Consultation]], ContenuPrevisions]`, et ne connaît aucune Baseline. Quand L4 sera sur `main`, la composition lui passera une petite fonction qui lit le Passage et appelle le domaine. Jusque-là, le registre garde `EtapeBouchon()` et le Passage réel n'a pas de `previsions.json`. Le critère AC 2 est prouvé avec une fonction de test.

**Traces.** Les Risques sont aussi tracés, car NFR-6 et FR-34 rattachent toute Prévision à ses versions, et `previsions.json` contient les deux. `version_donnees` est passée au constructeur, comme pour `EtapeExplications`.

**KPI denses.** `kpi` est dense sur les dates présentes dans la table. Les premiers Jours ouvrés sans aucun ticket n'ont donc pas de ligne : leur ajouter des zéros serait un calcul hors domaine. Avec le Journal généré, des tickets existent dès l'ancrage, et le test d'autoportance le vérifie.

**Hors périmètre, à reprendre ailleurs.**
- Story 2.6 (L2) : `horodatage_extraction`, `nb_alignements` et la `version_donnees` recalculée après extraction (AD-16). L'extraction réelle n'alimente pas encore les Instantanés, puisque `instantanes` lit seulement le Journal.
- Story 5.5 : configurer la journalisation et l'encodage UTF-8 de la console (rétrospective de l'Epic 0, constat 15).

**Fichiers hors lane.** `src/usine/composition.py`, pour câbler `EtapeKpi` dans le registre (AD-22 : seule la composition construit le registre).

## Verification

**Commands:**
- `uv run pytest -q tests/unit/chaine tests/unit/test_composition.py tests/unit/rendu tests/contrat` -- expected: tout passe
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout passe

## Auto Run Result

Status: done

**Résumé.** Un Passage publié contient désormais `kpi.parquet` et `tendances.parquet`. `EtapeKpi` passe à `domaine.kpi.kpi` l'état des tickets de chaque Jour ouvré, de l'ancrage (`EnteteJournal.ancrage_semaines`) à la Date d'arrêté, puis à `tendances(kpi, D, ancrage)`. `EtapePrevision` est prête : elle reçoit une fonction de prévision injectée, écrit `previsions.json` et produit une `EntreeTrace` par Prévision et par Risque dans `trace/previsions.jsonl`. Le registre garde l'étape `prevision` en bouchon tant que `domaine/prevision` (lane L4) n'est pas sur `main`. Le manifeste porte tous les champs de l'AC 3 ; `horodatage_extraction` (nul sans extraction) et `nb_alignements` restent du ressort de la Story 2.6.

**Fichiers modifiés.**
- `src/usine/chaine/etapes.py` : `EtapeKpi`, `EtapePrevision`, alias `Prevoir`, docstring du module.
- `src/usine/composition.py` (hors lane) : `Etape.kpi` → `EtapeKpi(entites, premier_jour)` ; commentaire et docstring sur le bouchon `prevision`.
- `tests/unit/chaine/environnement.py` : `contenu_previsions`, une Prévision et un Risque fictifs.
- `tests/unit/chaine/test_etapes.py` (nouveau) : tests unitaires d'`EtapeKpi` et d'`EtapePrevision`.
- `tests/unit/chaine/test_execution.py` : fichiers publiés, `test_manifeste_complet_relu`, `test_autoportance_kpi`, `test_passage_avec_previsions`.
- `tests/unit/consultation/test_passage.py` : KPI et Tendances désormais présents en Palier 1.

**Revue.** 23 constats.
- 3 entrées corrigées :
  - docstrings de couverture des KPI (medium) ;
  - branche morte supprimée (low) ;
  - assertion `nb_alignements` assouplie (low).
- 2 éléments différés dans `deferred` :
  - câblage d'`EtapePrevision` après L4 ;
  - journalisation et encodage de la console en 5.5.
- Constats rejetés, avec leur motif dans le Review Triage Log :
  - Rejeu : Story 5.5 ;
  - gardes sur des Prévisions non démontrées ;
  - double lecture de l'historique, mise en cache par `ConsultationPassage` ;
  - `cible` des Risques, fixée par contrat ;
  - les autres sont réfutés.

**Revue de suivi recommandée : non.** Les correctifs comptent 0 high, 1 medium et 2 low. Le medium ne touche que des docstrings.

**Vérification.** `ruff check`, `ruff format --check`, `mypy` (218 fichiers), `lint-imports` (13 contrats) et `pytest -q` (1624 réussis, 1 ignoré, 22 désélectionnés) passent après les correctifs.

**Risques résiduels.**
- Un historique dont les premiers Jours ouvrés n'ont aucun ticket produit des KPI qui commencent au premier ticket. C'est un comportement du domaine, documenté.
- L'AC 2 n'est prouvé que par une fonction de test, jusqu'au câblage L4.
- À l'intégration, la Story 2.6 (L2) touche `chaine/execution.py` et `composition.py`.
