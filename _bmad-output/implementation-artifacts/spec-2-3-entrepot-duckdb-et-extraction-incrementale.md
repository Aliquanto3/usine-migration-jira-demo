---
title: 'Story 2.3 : Entrepôt DuckDB et extraction incrémentale'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'c88c772dd99f6ce3cb4ffe4ee208a2ed5b50baff'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
warnings: ['oversized']
deferred:
  - summary: >-
      EtapeExtraction n'est pas câblée dans composition.py : la marge de config/jira.yaml n'est lue par aucun chemin d'exécution et un vrai Passage exécute encore EtapeBouchon.
    evidence: |-
      extraire() et EtapeExtraction reçoivent la marge en timedelta ; aucune ligne ne convertit ConfigJira.marge_extraction_minutes. composition.py appartient à main (AD-21, epic-2-context « Contrats d'abord ») : PR courte à ouvrir, avec la sélection d'adaptateur de la Story 2.4 (marge = timedelta(minutes=jira.marge_extraction_minutes), chemin = racine / CHEMIN_ENTREPOT).
    location: >-
      src/usine/composition.py (Etape.extraction: EtapeBouchon())
    severity: medium
---

<intent-contract>

## Intent

**Problem:** Chaque Passage relit aujourd'hui tout l'historique ; rien ne garde les `Evenement` extraits de Jira ni le repère du dernier Passage réussi, et une coupure en pleine pagination pourrait avancer le repère sur un historique partiel (FR-6, NFR-2, AD-6).

**Approach:** Créer `usine.adaptateurs.entrepot_duckdb` : `EntrepotDuckDB` (port `EntrepotExtraction`, fichier `donnees/entrepot.duckdb`) qui stocke événements et repère dans une transaction unique, dédoublonnée par `id_evenement` ; `extraire()` et `EtapeExtraction` (port `Etape`, seule à ouvrir l'entrepôt) qui demandent à la source les événements depuis `repère − marge`. `SourceJiraCloud` traduit `depuis` en restriction JQL `updated >= "-<n>m"`.

## Boundaries & Constraints

**Always:** nouveau repère = instant `horloge()` pris **avant** l'appel à la source ; `depuis = repère − timedelta(minutes=config.marge_extraction_minutes)`, `None` au premier Passage ; événements et repère validés ensemble ou pas du tout (`BEGIN` … `COMMIT`, `ROLLBACK` sur toute exception, y compris levée pendant la consommation de l'itérable) ; dédoublonnage par `id_evenement` (doublons du lot compris), un événement déjà stocké n'est jamais modifié (le premier gagne) ; `enregistrer` rend le nombre d'ajouts ; horodatages stockés en UTC et relus avec fuseau UTC ; relecture par (horodatage, ordre d'insertion) ; repère sans fuseau → `UsineErreur` ; toute erreur `duckdb` → `UsineErreur` nommant le fichier ; chaque opération ouvre puis ferme sa connexion (Windows) ; insertion en bloc (DataFrame Polars), jamais `executemany` (≈ 50 000 lignes > 5 min mesuré) ; SQL sans agrégat ni calcul (AD-9) ; tests sans réseau, données fictives `DEMO` ; textes en français ; mypy strict, ruff, import-linter verts.

**Never:** importer `httpx` dans un adaptateur ; importer `duckdb` hors `adaptateurs/entrepot_duckdb` ; ouvrir l'entrepôt ailleurs que dans `EtapeExtraction` (et la future composition) ; modifier `src/usine/contrats/`, `src/usine/ports/`, `composition.py`, `cli.py` racine, `tests/doublures/`, `pyproject.toml` ; câbler `EtapeExtraction` dans `composition.py` (PR courte sur `main`) ; verrou de Passage (déjà pris par `usine rapport`) ; alignements (2.6), adaptateur DC (2.4) ; date absolue dans la JQL (fuseau du compte Jira inconnu).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Premier Passage | entrepôt neuf, `repere() is None` | `source.evenements(None)`, JQL sans clause `updated` ; tout stocké ; repère = horloge | — |
| Incrémental | repère `R`, marge 10, horloge `T` | `depuis = R − 10 min` ; JQL `… AND updated >= "-<ceil((T−depuis)/1 min)>m" ORDER BY key ASC` (≥ 1) | — |
| Rejeu identique | deuxième Passage, mêmes fixtures | 0 ajout ; événements stockés identiques ; repère avancé | — |
| Doublons | lot avec un id déjà stocké ou répété | stocké une fois, contenu initial conservé | — |
| Coupure | page 2 de la recherche en erreur | ni événement ni repère validés (état antérieur intact) | `UsineErreur` propagée |
| Itérable qui lève | exception après N événements | `ROLLBACK` | exception propagée |
| Repère naïf | `enregistrer(…, datetime sans fuseau)` | rien d'écrit | `UsineErreur` |
| Fichier illisible | chemin = répertoire ou base corrompue | — | `UsineErreur` nommant le fichier |

</intent-contract>

## Code Map

- `src/usine/ports/entrepot.py` `EntrepotExtraction` (`repere`, `enregistrer(evenements, repere) -> int`, `evenements`) -- port gelé à implémenter.
- `src/usine/ports/etape.py` `Etape.executer(ctx) -> ResultatEtape` ; `src/usine/contrats/passage.py:338` `ResultatEtape(StatutEtape.reussie)` sans sortie ; `REPERTOIRE_DONNEES` (`donnees/`).
- `src/usine/contrats/evenements.py` `Evenement` (champs `id_evenement, cle_ticket, type_ticket, horodatage, nature, champ, de, vers, source`, gelé, validé) -- une colonne par champ.
- `src/usine/contrats/config.py:211` `ConfigJira.marge_extraction_minutes` -- marge (10 dans `config/jira.yaml`).
- `src/usine/adaptateurs/jira_cloud/source.py` `requete_jql`, `SourceJiraCloud.__init__/evenements` -- ajouter `horloge` et la clause `updated` ; filtre client `horodatage >= depuis` conservé.
- `src/usine/adaptateurs/stockage_sqlite/__init__.py` -- modèle de style (connexion par opération, erreurs nommant le fichier, création du répertoire parent).
- `tests/unit/adaptateurs/jira_cloud/outils.py` `ServeurFixtures(reponses)`, `source_fixtures`, `evenements_attendus` -- serveur simulé ; retirer `recherche_2` simule la coupure (réponse 599 → `UsineErreur`).
- `tests/unit/adaptateurs/jira_cloud/test_contrat_source_tickets.py` -- fabrique Cloud à déplacer vers `tests/contrat/source_tickets/fabriques.py` (`FABRIQUES`).
- `tests/unit/adaptateurs/jira_cloud/test_garde.py` -- modèle de garde AST.
- Prototype mesuré : `INSERT INTO evenements SELECT * FROM lot ON CONFLICT DO NOTHING` sur un `pl.DataFrame` rend `[(nombre inséré,)]` (200 000 lignes ≈ 1 s) ; `pytz` absent, donc colonnes `TIMESTAMP` naïves en UTC, pas `TIMESTAMPTZ`.

## Tasks & Acceptance

**Execution:**
- `src/usine/adaptateurs/entrepot_duckdb/entrepot.py` -- `CHEMIN_ENTREPOT = REPERTOIRE_DONNEES / "entrepot.duckdb"` ; `EntrepotDuckDB(chemin)` : tables `evenements` (PK `id_evenement`, `rang` d'insertion) et `repere` (une ligne), insertion en bloc, relecture triée -- AD-6, AD-9.
- `src/usine/adaptateurs/entrepot_duckdb/extraction.py` -- `extraire(source, entrepot, marge, horloge) -> ResultatExtraction(ajouts, repere, depuis)` ; `EtapeExtraction(source, chemin, marge, horloge)` : ouvre l'entrepôt dans `executer`, rend `ResultatEtape(reussie)` -- AD-6, AD-8.
- `src/usine/adaptateurs/entrepot_duckdb/__init__.py` -- docstring et réexports.
- `src/usine/adaptateurs/jira_cloud/source.py` (+ `__init__.py`) -- `horloge` (défaut `datetime.now(UTC)`), `minutes_depuis(depuis, maintenant)`, `requete_jql(config, minutes=None)` -- FR-6.
- `tests/unit/adaptateurs/entrepot_duckdb/{__init__,test_entrepot,test_extraction,test_garde}.py` -- matrice ci-dessus ; extraction de bout en bout sur `ServeurFixtures` ; garde AST (`duckdb` et `entrepot_duckdb` importés seulement dans le paquet, ou `composition.py` ; SQL sans `SUM`/`AVG`/`COUNT`/`MIN`/`MAX`/`GROUP BY`).
- `tests/unit/adaptateurs/jira_cloud/test_source.py` -- clause JQL incrémentale et arrondi à la minute supérieure.
- `tests/contrat/source_tickets/fabriques.py` -- `fabrique_jira_cloud` ajoutée à `FABRIQUES` ; supprimer `tests/unit/adaptateurs/jira_cloud/test_contrat_source_tickets.py` (plus de doublon).

**Acceptance Criteria:**
- Given un entrepôt avec un repère, when l'extraction s'exécute sur `SourceJiraCloud`, then la recherche JQL contient `updated >= "-<n>m"` couvrant `repère − marge` et les événements sont dédoublonnés par `id_evenement`.
- Given un deuxième Passage sur des fixtures identiques, when l'extraction s'exécute, then aucun événement stocké n'est ajouté ni modifié.
- Given une coupure au milieu de la pagination, when l'extraction échoue, then ni les événements ni le repère ne sont validés.
- Given le code de `src/usine`, when on cherche les ouvertures de l'entrepôt, then seule `EtapeExtraction` (et `composition.py`) l'ouvre, et le SQL ne contient aucun agrégat.
- Given `uv run pytest tests/contrat`, when la suite `SourceTickets` s'exécute, then elle inclut le cas `jira_cloud`.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 27 findings — high 0, medium 2, low 21, false 4, maybe-false 0
- findings:
  - `[medium]` `[defer]` (intent) marge de `config/jira.yaml` lue par aucun chemin d'exécution — groupe W (câblage) : `composition.py` appartient à `main` (AD-21) ; inscrit dans `deferred`.
  - `[medium]` `[defer]` (intent) l'extraction ne s'exécute pas encore dans un vrai Passage (`EtapeBouchon`) — groupe W ; `deferred`.
  - `[low]` `[patch]` (intent) fenêtre relative et horloge du serveur distincte de celle du repère — groupe G : invariant « décalage d'horloge + durée de pagination < marge » écrit dans la docstring de `jira_cloud/source.py`.
  - `[false]` `[reject]` (intent) la garde autorise aussi `composition.py` — la composition construit les dépendances (AD-1) ; aucune étape ni module métier ne peut ouvrir l'entrepôt.
  - `[low]` `[reject]` (intent) `fabriques.py` importe les outils unitaires Cloud — fonctionne et évite un doublon ; déplacer les outils vers `tests/doublures` (propriété de `main`) ajoute un fichier hors lane sans défaut constaté.
  - `[false]` `[reject]` (intent) mention « Fichiers hors lane » absente du diff — présente dans les Design Notes de cette spec.
  - `[low]` `[patch]` (edge) un `ROLLBACK` qui lève masque l'exception d'origine — groupe R : `ROLLBACK` sous `suppress(duckdb.Error)`.
  - `[low]` `[reject]` (edge) marge négative — `ConfigJira.marge_extraction_minutes` est `ge=0` ; garde supplémentaire pour un appel programmatique improbable.
  - `[low]` `[reject]` (edge) horloge injectée naïve → `TypeError` brut — échec bruyant ; l'horloge par défaut est en UTC.
  - `[low]` `[patch]` (edge) horloge Jira en avance de plus que la marge — groupe G (docstring).
  - `[low]` `[reject]` (edge) import relatif non vu par la garde — le dépôt n'utilise que des imports absolus ; affiner la garde ajoute de la complexité sans défaut.
  - `[low]` `[reject]` (edge) `EntrepotDuckDB` importé sous alias non vu par la garde — même motif.
  - `[low]` `[reject]` (edge) `duckdb.connect` direct dans le paquet hors classe — paquet de deux modules, seul `_operation` se connecte ; garde supplémentaire sans défaut.
  - `[low]` `[patch]` (edge, claim) couverture JQL tributaire du décalage d'horloge — groupe G (docstring).
  - `[low]` `[reject]` (blind) repère dans le futur après un saut d'horloge — cas rare (NTP) ; correctif = garde supplémentaire.
  - `[low]` `[patch]` (blind) fenêtre relative réévaluée à chaque page — groupe G (docstring).
  - `[low]` `[reject]` (blind) `marge` non validée — même constat que la ligne edge (config `ge=0`).
  - `[low]` `[reject]` (blind) `EtapeExtraction` jette le bilan — `ResultatEtape` n'accepte que des clés de `FICHIERS_PASSAGE` (gelé) ; le manifeste relève de la Chaîne (L5).
  - `[low]` `[reject]` (blind) divergence de contenu à id égal non signalée — « le premier gagne » voulu (ids déterministes) ; détection = nouvelle surface.
  - `[low]` `[reject]` (blind) garde contournable (relatif, mot-clé, alias) — mêmes motifs que les lignes edge.
  - `[low]` `[patch]` (blind) erreurs hors `duckdb` sans le fichier, `ROLLBACK` qui masque — groupe R pour le `ROLLBACK` ; erreurs Polars sur des `Evenement` déjà validés improbables.
  - `[low]` `[reject]` (blind) `evenements()` matérialise tout, erreur différée — même comportement que `SourceJiraCloud` ; tri global en base.
  - `[false]` `[reject]` (blind) contrat Cloud non déterministe (horloge réelle) — le serveur simulé ignore la JQL, le flux rendu ne dépend pas de la date ; inversion des couches : voir ligne intent.
  - `[low]` `[patch]` (blind) `requetes[:2]` non filtré dans `test_sans_depuis_ni_restriction_ni_horloge` — filtré sur `CHEMIN_RECHERCHE`, deux recherches attendues.
  - `[low]` `[patch]` (blind) fichier libéré non vérifié après annulation — test `test_aucune_connexion_ne_reste_ouverte_apres_annulation` ajouté.
  - `[low]` `[reject]` (blind) ouverture concurrente non testée — le verrou de Passage d'`usine rapport` exclut deux extractions ; test multiprocessus coûteux.
  - `[false]` `[reject]` (blind) deux horloges `_maintenant` — toutes deux `now(UTC)` sur la même machine ; celle de la source est lue après le repère, ce qui élargit la fenêtre.

## Design Notes

- **JQL relative** : Jira interprète une date absolue dans le fuseau du profil du compte de lecture, inconnu ici ; `-<n>m` (minutes, arrondi supérieur, au moins 1) est indépendant du fuseau. Le décalage d'horloge client/serveur est couvert par la marge. Réutilisable par l'adaptateur DC (2.4).
- **Repère** : instant pris avant l'extraction, donc toute modification faite pendant celle-ci est revue au Passage suivant.
- **Câblage** : `EtapeExtraction` n'est pas encore branchée dans `composition.py` (propriété de `main`, AD-21) ; à faire par PR courte avec la sélection d'adaptateur (2.4).
- **Fichiers hors lane** : `tests/contrat/source_tickets/fabriques.py` -- inscription de la fabrique Jira Cloud dans la suite de contrat, prévue par son docstring (report de la 2.2). Aucun port d'entrepôt n'a de suite de contrat : pas de fabrique DuckDB à inscrire.

## Verification

**Commands:**
- `uv run ruff check .` et `uv run ruff format --check .` -- aucun écart.
- `uv run mypy` -- aucune erreur.
- `uv run lint-imports` -- tous les contrats tenus.
- `uv run pytest -q` -- tout passe, sans réseau.
- `uv run python .github/scripts/controle_lanes.py --branche lane/2-extraction --base main` -- seul `tests/contrat/source_tickets/fabriques.py` hors lane, justifié.

## Auto Run Result

Status: done

- **Changement** : paquet `usine.adaptateurs.entrepot_duckdb` : `EntrepotDuckDB` (port `EntrepotExtraction`, `donnees/entrepot.duckdb`) stocke événements et repère dans une transaction unique, dédoublonnés par `id_evenement` (le premier gagne), insertion en bloc Polars, SQL sans agrégat ; `extraire()` et `EtapeExtraction` (port `Etape`, seule à ouvrir l'entrepôt) prennent le repère avant l'appel et demandent `depuis = repère − marge`. `SourceJiraCloud` restreint la recherche par `updated >= "-<n>m"` (fenêtre relative, indépendante du fuseau du compte Jira). La fabrique Jira Cloud rejoint `FABRIQUES` de la suite de contrat.
- **Fichiers** :
  - `src/usine/adaptateurs/entrepot_duckdb/{__init__,entrepot,extraction}.py` -- entrepôt, extraction incrémentale, étape.
  - `src/usine/adaptateurs/jira_cloud/source.py`, `__init__.py` -- `horloge`, `minutes_depuis`, `requete_jql(config, minutes)`.
  - `tests/unit/adaptateurs/entrepot_duckdb/{test_entrepot,test_extraction,test_garde}.py` -- matrice, bout en bout sur fixtures Cloud (rejeu identique, coupure en pagination), gardes AST.
  - `tests/unit/adaptateurs/jira_cloud/test_source.py` -- clause incrémentale, arrondi.
  - `tests/contrat/source_tickets/fabriques.py` (hors lane, justifié) -- `fabrique_jira_cloud` ; `tests/unit/adaptateurs/jira_cloud/test_contrat_source_tickets.py` supprimé (plus de doublon). Pas de fabrique DuckDB : aucun port d'entrepôt n'a de suite de contrat.
- **Revue** : 27 constats ; 4 entrées corrigées, toutes low (`ROLLBACK` qui masquait l'erreur d'origine ; invariant d'horloge de la fenêtre relative documenté ; filtre d'un test ; test de libération du fichier après annulation) ; 1 report medium (câblage dans `composition.py`, propriété de `main`) ; le reste rejeté, motifs dans le Review Triage Log.
- **Relecture de suivi recommandée** : non (première passe : aucune entrée high ni medium corrigée ; patchées : 4 low).
- **Vérification** : `ruff check`, `ruff format --check`, `mypy`, `lint-imports` (13 contrats) verts ; `pytest -q` : 1387 réussis, 1 ignoré ; chaque ligne de la matrice I/O couverte par un test exécuté.
- **Risques résiduels** : extraction non câblée dans un vrai Passage tant que la PR courte sur `composition.py` n'est pas faite ; couverture de la fenêtre relative tributaire du décalage d'horloge client/serveur (< marge) ; vrai Jira non testé (recette 2.7).
