---
title: 'Story 2.2 : Adaptateur Jira Cloud v3 et vocabulaire canonique'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '42e02597e46b88391818c3c92bc22d25414446fe'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
warnings: ['oversized']
deferred:
  - summary: >-
      Description initiale (ADF aplati) et valeurs `fromString`/`toString` du changelog peut-être dans deux formats de texte différents.
    evidence: |-
      Sans changelog, la description vient de l'ADF (un paragraphe par ligne) ; avec changelog, du texte que Jira Cloud met dans fromString, dont le format exact n'est pas vérifiable sans vrai site. À confronter à de vrais enregistrements à la recette 2.7, et au test de cohérence FR-49 (Story 2.6).
    location: >-
      src/usine/adaptateurs/jira_cloud/conversion.py (texte_adf, convertir_ticket)
    severity: medium (unverified)
  - summary: >-
      La fabrique Cloud n'est pas inscrite dans tests/contrat/source_tickets/fabriques.py (propriété de main).
    evidence: |-
      La suite de contrat s'exécute sur Cloud depuis tests/unit/adaptateurs/jira_cloud/test_contrat_source_tickets.py (réimport, avec un test qui détecte tout test de contrat non réimporté) ; lancer tests/contrat/ seul n'inclut pas Cloud. PR courte sur main à ouvrir (AD-20, AD-21).
    location: >-
      tests/contrat/source_tickets/fabriques.py
    severity: low
---

<intent-contract>

## Intent

**Problem:** Le calcul ne doit voir que des `Evenement` canoniques (AD-3, AD-23), alors que Jira Cloud expose des identifiants de champs (`customfield_…`), des noms de statuts et de types propres au site, un changelog en ligne tronqué et une description au format ADF.

**Approach:** Créer `usine.adaptateurs.jira_cloud` : `SourceJiraCloud`, qui implémente le port `SourceTickets` au-dessus d'un `ClientJiraLecture` (Story 2.1). Il recherche les tickets du projet par `POST /rest/api/3/search/jql` (`expand=changelog`), complète tout changelog tronqué par `GET /rest/api/3/issue/{cle}/changelog`, puis convertit tickets et changelog en `Evenement` via la table de `config/jira.yaml` (`ConfigJira`), appliquée uniquement dans l'adaptateur.

## Boundaries & Constraints

**Always:** tout appel Jira passe par `ClientJiraLecture` (liste blanche, garde d'hôte) ; identifiants `C-<id ticket>` (création), `C-<id ticket>-<champ>` (attribut initial), `<id changelog>-<rang item>` (rang 1 = premier item de l'historique, items ignorés compris) ; horodatages UTC ; flux trié par (horodatage, `rang_cle`, ordre interne au ticket), création puis attributs initiaux en tête ; seuls les `Champ` de `CHAMPS_PAR_TYPE[type]` sont émis ; toute anomalie de données est une `UsineErreur` qui nomme le ticket et, pour une correspondance manquante, `config/jira.yaml`, la clé (`types_tickets`, `valeurs.<champ>`) et la valeur ; tests sans réseau (`httpx.MockTransport`) ; données fictives (projet `DEMO`) ; textes en français ; mypy strict, ruff, import-linter verts.

**Never:** importer `httpx`, `TransportJira`, `Authentification` ou `jira_http.pagination` dans `adaptateurs/jira_cloud` (seul `ClientJiraLecture` est permis) ; modifier `src/usine/contrats/`, `src/usine/ports/`, `composition.py`, `cli.py` racine, `tests/contrat/`, `tests/doublures/`, `pyproject.toml` ; importer `usine.config` ou `yaml` depuis l'adaptateur ; repère incrémental ou entrepôt (Story 2.3), adaptateur DC (2.4), alignement (2.6) ; `cause_racine` dans un `Evenement` ; appel réel à Jira.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Création | ticket `id=10001`, `created`, champs courants, changelog complet | `C-10001` puis `C-10001-<champ>` par attribut initial non vide, au même horodatage | — |
| Valeur initiale | champ modifié plus tard dans le changelog | valeur initiale = `fromString` du premier item de ce champ ; sinon valeur courante | — |
| Transition | item `status` `Nouvelle → En correction` sur une Anomalie | `transition`, `statut`, `nouvelle → en_correction`, id `<id hist>-<rang>` | — |
| Champ hors type | item `status` sur un Cas de test, ou champ non mappé (`assignee`) | ignoré (le rang compte quand même) | — |
| Sans effet | deux valeurs Jira de même valeur canonique | item ignoré | — |
| Changelog tronqué | `changelog.total` > nombre d'`histories` (ou `changelog`/`total` absent) | `GET /rest/api/3/issue/{cle}/changelog` paginé par position ; fusion dédoublonnée par id d'historique | — |
| Valeur ADF | `description` courante au format ADF (`type: doc`) | texte : nœuds `text` concaténés, un paragraphe par ligne | forme inconnue : `UsineErreur` |
| Correspondance manquante | statut `In Progress` ou type `Bug` absent de la table | — | `UsineErreur` nommant `config/jira.yaml`, la clé, la valeur et le ticket |
| `depuis` | instant avec fuseau | événements d'horodatage ≥ `depuis` | sans fuseau : `UsineErreur` |
| Lecture seule | tout appel de l'adaptateur | seulement `POST search/jql` et `GET issue/{cle}/changelog` | requête hors liste blanche : `RequeteJiraInterdite` |

</intent-contract>

## Code Map

- `src/usine/ports/source_tickets.py` `SourceTickets.evenements(depuis)` -- port à implémenter (gelé).
- `src/usine/contrats/evenements.py` `Evenement`, `NatureEvenement`, `SourceEvenement.jira_cloud` -- contrat de sortie ; le validateur refuse `de == vers`, une transition hors `statut`, un champ hors type, une valeur hors domaine.
- `src/usine/contrats/tickets.py` `Champ`, `CHAMPS_PAR_TYPE`, `DOMAINES_CANONIQUES`, `rang_cle` -- vocabulaire canonique ; ordre des attributs initiaux = ordre de `Champ`.
- `src/usine/contrats/config.py:211` `ConfigJira` (`cle_projet`, `champs`, `types_tickets`, `valeurs`) -- table de correspondance validée.
- `config/jira.yaml` -- table fictive (statuts H-17 en français, `customfield_10001…10007`).
- `src/usine/adaptateurs/jira_http/clients.py` `ClientJiraLecture.paginer_par_jeton`, `paginer_par_position`, `LISTE_BLANCHE_LECTURE` -- `POST /rest/api/3/search/jql` (clé `issues`) et `GET /rest/api/3/issue/{cle}/changelog` (clé `values`) déjà autorisés.
- `src/usine/adaptateurs/journal/__init__.py` -- modèle de style (`SourceJournal`, refus de `depuis` sans fuseau).
- `tests/contrat/source_tickets/test_contrat.py`, `fabriques.py` (`CasSourceTickets`) -- suite de contrat, propriété de `main`.
- `tests/unit/adaptateurs/jira_http/outils.py` (`ServeurSimule`, `config_jira`, `fixture`) et `test_ecriture.py` (garde AST) -- outils et modèle de garde à réutiliser.
- Forme Cloud v3 : `issues[].{id,key,fields{issuetype{name},status{name},summary,description(ADF),created,customfield_*({value}|texte)},changelog{startAt,maxResults,total,histories[{id,created,items[{fieldId,field,fromString,toString}]}]}}` ; horodatages `2026-09-01T09:00:00.000+0000` (`datetime.fromisoformat` les lit).

## Tasks & Acceptance

**Execution:**
- `src/usine/adaptateurs/jira_cloud/conversion.py` -- fonctions pures : lecture d'horodatage Jira, valeur courante d'un champ (texte, `{value}`, `{name}`, ADF → texte), correspondance type/valeurs via `ConfigJira`, conversion d'un ticket et de ses historiques en `Evenement` (paramètre `source`, réutilisable par la Story 2.4) -- AD-3, AD-23.
- `src/usine/adaptateurs/jira_cloud/source.py` -- `SourceJiraCloud(client: ClientJiraLecture, config: ConfigJira)` : JQL `project = "<cle>" AND issuetype in (<types Jira>) ORDER BY key ASC`, `fields` = identifiants de `config.champs` + `issuetype`, `created` ; détection de troncature et complément par ticket ; tri global ; filtre `depuis` -- port `SourceTickets`.
- `src/usine/adaptateurs/jira_cloud/__init__.py` -- docstring et réexports.
- `tests/fixtures/jira_cloud/source_recherche_page_1.json`, `source_recherche_page_2.json`, `source_changelog_DEMO-3_page_1.json`, `source_changelog_DEMO-3_page_2.json` -- Anomalie avec transitions et champs personnalisés, Cas de test (item `status` ignoré), Certification, item non mappé, un changelog tronqué complété sur deux pages.
- `tests/unit/adaptateurs/jira_cloud/__init__.py`, `outils.py` (serveur simulé des fixtures, événements attendus écrits à la main), `test_contrat_source_tickets.py` (fixture `cas` Cloud + réimport des tests de `tests.contrat.source_tickets.test_contrat`), `test_conversion.py` (matrice), `test_source.py` (requêtes émises, troncature, `depuis`, lecture seule), `test_garde.py` (AST : pas d'`httpx` ni de transport dans `jira_cloud` ; `types_tickets` et `customfield_` absents de `src/usine` hors adaptateurs Jira et `contrats/config.py`).

**Acceptance Criteria:**
- Given `config/jira.yaml` et les fixtures `tests/fixtures/jira_cloud/source_*`, when `SourceJiraCloud.evenements()` les lit via `httpx.MockTransport`, then il rend exactement les `Evenement` attendus (identifiants `<id changelog>-<rang item>`, `C-<id>`, `C-<id>-<champ>`), toutes valeurs dans les domaines canoniques.
- Given un ticket dont le changelog en ligne est tronqué, when l'adaptateur le lit, then il appelle `GET /rest/api/3/issue/DEMO-3/changelog` et les événements des historiques absents de la recherche sont rendus, sans doublon.
- Given la suite de contrat `SourceTickets`, when on l'exécute sur `SourceJiraCloud`, then tous ses tests passent.
- Given une table modifiée (statut Jira `In Progress` → `en_correction`), when l'adaptateur lit un item `In Progress`, then il émet `en_correction` : la correspondance vient de la configuration et n'est appliquée que dans l'adaptateur.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 33 findings — high 0, medium 3, low 17, false 6, maybe-false 7
- findings:
  - `[medium]` `[patch]` (blind) item de champ personnalisé sans `fieldId` : repli sur `field` (nom d'affichage), changement perdu en silence ; `fieldId: null` devient "None" — groupe F : `fieldId` non vide d'abord, repli sur `field` hors champ personnalisé, sinon `UsineErreur` nommant ticket, historique et item ; tests ajoutés.
  - `[maybe-false]` `[defer]` (blind) description initiale ADF et `fromString` du changelog dans deux formats — dépend du format réel de Jira Cloud ; à trancher sur vrais enregistrements (2.7) ; inscrit dans `deferred` (medium, non vérifié).
  - `[low]` `[reject]` (blind) historique antérieur à `created` placé avant la création — cas improbable (horloge Jira unique) ; correctif = garde supplémentaire.
  - `[low]` `[reject]` (blind) contrôle de `depuis` différé au premier `next()` — même comportement que `SourceJournal` ; la suite de contrat le vérifie ; correctif = scinder le générateur.
  - `[low]` `[reject]` (blind) `evenements()` charge tout avant le premier événement — imposé par le tri global ; choix consigné dans les Design Notes (restriction JQL en 2.3).
  - `[low]` `[reject]` (blind) complément du changelog repris depuis `startAt=0` — une page de plus par ticket tronqué ; l'ordre du changelog en ligne n'est pas documenté, la reprise complète reste sûre.
  - `[false]` `[reject]` (blind) `types_tickets` vide → JQL invalide — `ConfigJira` exige un type Jira pour chaque type canonique, la table ne peut pas être vide.
  - `[low]` `[reject]` (blind) valeurs en liste (`fixVersions`, multi-sélection) refusées — échec bruyant et explicite ; la table fictive n'utilise que des champs simples.
  - `[low]` `[patch]` (blind) tests de contrat réimportés par nom : un test ajouté sur `main` ne tournerait pas sur Cloud — test ajouté : tout `test_*` du module de contrat doit être présent dans le module Cloud.
  - `[low]` `[patch]` (blind) départage des historiques de même horodatage non testé — groupe T : test "9999" / "10000".
  - `[low]` `[patch]` (blind) contexte d'erreur `historique 20001-3` — id d'historique et rang passés séparément, « historique <id>, item <rang> ».
  - `[low]` `[reject]` (blind) garde AST trop large sur les noms `transport`/`pagination` — échec bruyant au pire ; correctif = affiner la garde sans défaut constaté.
  - `[low]` `[patch]` (blind) `ordonner_historiques` et `chemin_changelog` absents de `__all__` — ajoutés.
  - `[low]` `[reject]` (blind) chemin « sans changelog en ligne » non testé via `SourceJiraCloud` — détection couverte par `test_detection_de_la_troncature[None-True]` ; chemin trivial.
  - `[medium]` `[patch]` (edge) `fieldId` nul ou nom d'affichage seul — groupe F.
  - `[low]` `[reject]` (edge) champ mappé absent de `fields` → pas d'attribut initial — Jira renvoie les champs système demandés ; absent et nul ont le même sens ; correctif = garde supplémentaire.
  - `[low]` `[reject]` (edge) historique antérieur à `created` — même constat que la ligne blind.
  - `[maybe-false]` `[reject]` (edge) même ticket sur deux pages → identifiants en double — improbable avec `ORDER BY key` et une pagination séquentielle ; au pire low ; correctif = garde supplémentaire.
  - `[low]` `[reject]` (edge) valeur fermée avec espaces (`'Majeure '`) — échec bruyant qui nomme la valeur ; improbable avec des options de liste.
  - `[maybe-false]` `[defer]` (edge) normalisation de la description entre changelog et ADF — même racine que la ligne blind ; `deferred`.
  - `[false]` `[reject]` (edge) clé de ticket hors motif → message trompeur — les clés Jira ont toujours la forme `PROJET-n`, que la liste blanche accepte.
  - `[low]` `[patch]` (verification-gap) départage numérique des historiques non testé — groupe T : `test` ajouté.
  - `[low]` `[patch]` (verification-gap) `heading` et `codeBlock` ADF non testés — test ajouté.
  - `[maybe-false]` `[patch]` (verification-gap) repli `fieldId` → `field` jamais exercé — groupe F : tests d'item sans `fieldId` (standard accepté, personnalisé refusé).
  - `[medium]` `[patch]` (verification-gap, autre) repli `field` inutilisable pour un champ personnalisé — groupe F.
  - `[low]` `[reject]` (verification-gap, autre) garde « statut sans arrivée » redondante avec le validateur — seul le message diffère, plus clair.
  - `[false]` `[reject]` (intent) garde d'hôte non exercée par ce diff — l'adaptateur ne passe que des chemins `/rest/api/3/...` construits, contrôlés par la liste blanche ; la garde d'hôte est testée dans `jira_http` (2.1).
  - `[false]` `[reject]` (intent) `httpx` importé par les tests — la consigne vise l'adaptateur (`src`) ; les tests en ont besoin pour `MockTransport`.
  - `[maybe-false]` `[reject]` (intent) aucun câblage de production du client réel — `composition.py` appartient à `main` (AD-21), hors de cette story.
  - `[maybe-false]` `[defer]` (intent) Cloud absent de `FABRIQUES` dans `tests/contrat/` — fichier de `main` ; PR courte inscrite dans `deferred`.
  - `[maybe-false]` `[reject]` (intent) isolation de la correspondance vérifiée sur deux jetons seulement — complétée par la suite de contrat (valeurs canoniques) et par le test de table modifiée ; au pire low.
  - `[false]` `[reject]` (intent) troisième forme d'identifiant `C-<id>-<champ>` — AD-3 impose un événement par attribut initial sans en fixer l'id ; forme déterministe consignée au spec.
  - `[false]` `[reject]` (intent) fixtures et configuration — aucun écart : `config/jira.yaml` réel et fixtures `source_*`.

## Design Notes

- **Suite de contrat** : `tests/contrat/` appartient à `main` (AD-21) ; le module de la lane réimporte les fonctions de test du contrat et fournit sa propre fixture `cas`, ce qui exécute la suite inchangée sur Cloud sans écrire hors lane. L'ajout de la fabrique Cloud dans `fabriques.py` se fera par PR courte sur `main`.
- **Complément du changelog** : endpoint par ticket (stable, paginé par position) plutôt que `changelog/bulkfetch` (statut « Experimental » contesté, doublons entre pages connus) ; dédoublonnage par id d'historique dans tous les cas.
- **`depuis`** : filtrage côté client ; la restriction JQL `updated >= repère − marge` relève de la Story 2.3.
- **Fixtures** : synthétiques au format documenté ; vrais enregistrements à la recette 2.7.
- **Fichiers hors lane** : aucun.

## Verification

**Commands:**
- `uv run ruff check .` et `uv run ruff format --check .` -- aucun écart.
- `uv run mypy` -- aucune erreur.
- `uv run lint-imports` -- tous les contrats tenus.
- `uv run pytest -q` -- tout passe, sans réseau.
- `uv run python .github/scripts/controle_lanes.py --branche lane/2-extraction --base main` -- tous les fichiers dans la lane.

## Auto Run Result

Status: done

- **Changement** : paquet `usine.adaptateurs.jira_cloud` : `SourceJiraCloud` (port `SourceTickets`) lit Jira Cloud par le seul `ClientJiraLecture` (`POST search/jql` avec `expand=changelog`, complément `GET issue/{cle}/changelog` des changelogs tronqués, dédoublonné par id d'historique) et convertit tickets et changelog en `Evenement` canoniques selon `config/jira.yaml` (création `C-<id>`, attributs initiaux `C-<id>-<champ>`, items `<id historique>-<rang>`).
- **Fichiers** :
  - `src/usine/adaptateurs/jira_cloud/conversion.py` -- conversion pure (horodatages, ADF → texte, correspondance, attributs initiaux, tri global).
  - `src/usine/adaptateurs/jira_cloud/source.py` -- `SourceJiraCloud`, JQL, détection de troncature.
  - `src/usine/adaptateurs/jira_cloud/__init__.py` -- réexports.
  - `tests/fixtures/jira_cloud/source_*.json` -- recherche sur deux pages (Anomalies, Cas de test, Certification) et changelog de DEMO-3 sur deux pages.
  - `tests/unit/adaptateurs/jira_cloud/` -- `outils.py` (serveur simulé, flux attendu écrit à la main), `test_contrat_source_tickets.py` (suite de contrat sur Cloud), `test_conversion.py`, `test_source.py`, `test_garde.py` (AST : ni `httpx`, ni transport, ni pagination directe dans l'adaptateur).
- **Revue** : 33 constats ; 6 entrées corrigées (1 medium : `fieldId` des champs personnalisés ; 5 low : tests de départage et d'ADF, garde de réimport des tests de contrat, contexte d'erreur, `__all__`) ; 2 reports (format de la description, fabrique Cloud dans `tests/contrat/`) ; le reste rejeté, motifs dans le Review Triage Log.
- **Relecture de suivi recommandée** : non (première passe : 1 entrée medium corrigée, aucune high).
- **Vérification** : `ruff check`, `ruff format --check`, `mypy`, `lint-imports` (13 contrats) verts ; `pytest -q` : 1264 réussis, 1 ignoré ; matrice I/O couverte entièrement par des tests exécutés.
- **Critère reporté** : vrais enregistrements Jira Cloud → recette 2.7 (fixtures synthétiques).
- **Risques résiduels** : format texte de la description (ADF vs changelog) non vérifié sur un vrai site ; `depuis` filtré côté client (restriction JQL en 2.3) ; un champ personnalisé sans `fieldId` arrête l'extraction (choix explicite plutôt qu'une perte silencieuse).
