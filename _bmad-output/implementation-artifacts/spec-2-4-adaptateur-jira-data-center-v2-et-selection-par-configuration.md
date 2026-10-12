---
title: 'Story 2.4 : Adaptateur Jira Data Center v2 et sélection par configuration'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '131eef4fadd6f830c78fce200195c63a23ab4697'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Seul Jira Cloud est lisible : rien ne lit un Jira Data Center (API v2), et un vrai Passage exécute encore `EtapeBouchon` pour l'extraction, si bien que la marge de `config/jira.yaml` n'est lue nulle part (report medium de la 2.3) (FR-7, NFR-8).

**Approach:** Créer `usine.adaptateurs.jira_dc.SourceJiraDC` (port `SourceTickets`, `GET /rest/api/2/search` paginé par position, mêmes conversions que Cloud, noms de champs personnalisés du changelog résolus par `GET /rest/api/2/field`), l'éprouver par la suite de contrat sur des fixtures équivalentes aux fixtures Cloud, puis câbler dans `composition.py` l'`EtapeExtraction` sur la source choisie par `config/jira.yaml` `mode` (`cloud` | `dc`).

## Boundaries & Constraints

**Always:** lecture par `ClientJiraLecture` seulement (liste blanche DC) ; JQL identique à Cloud (`project`, `issuetype in`, `updated >= "-<n>m"` avec `depuis`, `ORDER BY key ASC`) ; fenêtre de 10 000 résultats DC contournée par tranches successives `key > "<dernière clé>"` ; changelog en ligne tronqué complété par `GET /rest/api/2/issue/{cle}` (`expand=changelog`), encore tronqué → `UsineErreur` ; item `custom` sans `fieldId` : identifiant résolu par nom d'affichage, nom ambigu parmi les champs configurés → `UsineErreur` nommant le nom, nom sans champ configuré → item ignoré (rang conservé) ; `source = SourceEvenement.jira_dc` ; flux attendu DC = flux Cloud à `source` près ; composition : extraction Jira seulement si `config/jira.yaml` existe, hors Mode repli et si le secret de lecture de la plateforme est présent (`cloud` : `JIRA_TOKEN_LECTURE`, e-mail exigé ensuite ; `dc` : `JIRA_DC_PAT`) ; sinon source Journal seule, étape `extraction` = `EtapeBouchon` (comportement antérieur) ; marge = `timedelta(minutes=jira.marge_extraction_minutes)`, entrepôt = `racine / CHEMIN_ENTREPOT`, horloge du rapport ; client fermé après l'étape ; `instantanes` reste sur `SourceJournal` (composite = 2.6) ; tests sans réseau, données fictives `DEMO` ; textes en français ; mypy strict, ruff, import-linter verts.

**Never:** importer `httpx`, transport, pagination ou `usine.config` dans `jira_dc` ou `jira_cloud` ; modifier `src/usine/contrats/`, `src/usine/ports/`, `cli.py` racine, `tests/doublures/`, `pyproject.toml` ; extraction automatique en Mode repli ; écriture vers Jira ; alignements (2.6), source composite (2.6), Journal à l'échelle (2.5) ; vrai Data Center.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Flux DC | fixtures `jira_dc/source_*` (4 tickets, 2 pages, DEMO-3 tronqué) | `evenements_attendus()` Cloud avec `source=jira_dc` | — |
| Requêtes DC | idem | `GET /rest/api/2/field`, `GET /rest/api/2/search` (`startAt` 0 puis 2, `jql`, `fields`, `expand=changelog`), `GET /rest/api/2/issue/DEMO-3` | aucune hors liste blanche |
| Fenêtre | `fenetre=2`, 4 tickets | 2e tranche avec `AND key > "DEMO-2"` ; tranche vide → fin | — |
| Champ ambigu | deux champs « Gravité » configurés | — | `UsineErreur` nommant « Gravité » |
| Changelog encore tronqué | complément `total` > historiques | — | `UsineErreur` nommant le ticket |
| `depuis` naïf | `datetime` sans fuseau | rien envoyé | `UsineErreur` |
| Sans secret | `config/jira.yaml` (cloud), aucun jeton | Passage publié, source `journal`, extraction `EtapeBouchon` | — |
| `mode: dc` + PAT | `JIRA_DC_PAT` | `EtapeExtraction` sur `SourceJiraDC`, marge de la config, `donnees/entrepot.duckdb` | — |
| Cloud incomplet | `JIRA_TOKEN_LECTURE` sans `JIRA_EMAIL` | — | `UsineErreur` nommant `JIRA_EMAIL` |
| Mode repli | `USINE_MODE_REPLI=1` + PAT | aucune extraction Jira | — |

</intent-contract>

## Code Map

- `src/usine/adaptateurs/jira_cloud/source.py` -- `requete_jql`, `champs_demandes`, `changelog_tronque`, `minutes_depuis`, `_maintenant` : réutilisés ; `requete_jql(config, minutes, apres=None)` gagne la clause `key > "<clé>"`.
- `src/usine/adaptateurs/jira_cloud/conversion.py` -- `convertir_ticket(ticket, historiques, config, source)`, `trier_evenements` : réutilisés tels quels ; `_identifiant_item` lit `fieldId`, à défaut `field` hors `custom` (d'où la résolution DC).
- `src/usine/adaptateurs/jira_http/clients.py` -- `LISTE_BLANCHE_LECTURE["dc"]` contient déjà `GET /rest/api/2/search`, `/issue/{cle}`, `/field` ; `paginer_par_position(chemin, cle, params, taille_page)` ; `construire_client_lecture(config, email, jeton_lecture, pat)` choisit l'authentification selon `config.mode`.
- `src/usine/adaptateurs/jira_http/transport.py:_decoder` -- refuse une réponse JSON non objet ; `/field` rend un tableau → ajouter `requete_liste` (transport + client, contrôle de liste blanche).
- `src/usine/adaptateurs/entrepot_duckdb/extraction.py` `EtapeExtraction(source, chemin, marge, horloge)` -- ajouter `fermer` (appelé en `finally`) et propriétés en lecture `source`, `chemin`, `marge`.
- `src/usine/composition.py:construire_rapport` -- `Etape.extraction: EtapeBouchon()` à remplacer par la sélection ; `secrets_usine`, `jira`, `horloge` déjà disponibles ; `CHEMIN_ENTREPOT` dans `adaptateurs.entrepot_duckdb`.
- `tests/unit/adaptateurs/jira_cloud/outils.py` -- `ServeurFixtures`, `evenements_attendus` : modèle du serveur DC.
- `tests/fixtures/jira_cloud/source_*.json` -- à transposer en v2 (`self` en `/rest/api/2/`, description en texte, items sans `fieldId`, DEMO-3 complet dans `issue_DEMO-3.json`).
- `tests/contrat/source_tickets/fabriques.py` `FABRIQUES` -- ajouter `("jira_dc", fabrique_jira_dc)`.
- `tests/unit/chaine/environnement.py:preparer_racine` -- copie `config/` (donc `jira.yaml`, mode cloud) : la voie sans secret doit rester verte.

## Tasks & Acceptance

**Execution:**
- `src/usine/adaptateurs/jira_http/{transport,clients,__init__}.py` -- `requete_liste` (tableau JSON, sinon `UsineErreur`) -- `/rest/api/2/field`.
- `src/usine/adaptateurs/jira_cloud/source.py` -- paramètre `apres` de `requete_jql`, clause `key > "…"` échappée -- tranches DC.
- `src/usine/adaptateurs/jira_dc/{__init__,source}.py` -- `SourceJiraDC(client, config, horloge, fenetre=FENETRE_RESULTATS)` ; résolution des noms ; complément de changelog ; tranches -- FR-7, AD-5, AD-23.
- `src/usine/adaptateurs/entrepot_duckdb/extraction.py` -- `fermer`, propriétés -- câblage.
- `src/usine/composition.py` -- `_etape_extraction(racine, jira, secrets, horloge)` -- AD-1, AD-6.
- `tests/fixtures/jira_dc/source_{recherche_page_1,recherche_page_2,issue_DEMO-3,champs}.json` -- fixtures équivalentes.
- `tests/unit/adaptateurs/jira_dc/{__init__,outils,test_source,test_garde}.py` -- matrice ci-dessus, garde AST (mêmes interdits que Cloud).
- `tests/unit/adaptateurs/jira_http/test_transport.py`, `tests/unit/adaptateurs/jira_cloud/test_source.py`, `tests/unit/adaptateurs/entrepot_duckdb/test_extraction.py` -- `requete_liste`, clause `apres`, `fermer`.
- `tests/contrat/source_tickets/fabriques.py` -- `fabrique_jira_dc`.
- `tests/unit/test_composition.py` -- sélection (sans secret, cloud, dc, Mode repli, e-mail manquant) et Passage de bout en bout `mode: dc` sur serveur simulé (entrepôt alimenté, repère posé).

**Acceptance Criteria:**
- Given les fixtures `tests/fixtures/jira_dc/`, when `uv run pytest tests/contrat` s'exécute, then la suite `SourceTickets` passe pour le cas `jira_dc` avec les mêmes tests que `jira_cloud`.
- Given `config/jira.yaml` avec `mode: dc` et `JIRA_DC_PAT`, when `lancer_rapport` s'exécute sur le mini-jeu avec un serveur DC simulé, then le Passage est publié et `donnees/entrepot.duckdb` contient les événements DC et un repère.
- Given aucun secret Jira, when `lancer_rapport` s'exécute sur le mini-jeu, then un Passage est publié avec `source == "journal"` sans aucune requête.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 27 findings — high 0, medium 6, low 13, false 8, maybe-false 0
- findings:
  - `[medium]` `[patch]` (blind) homonyme personnalisé non configuré attribué au champ configuré — groupe N : carte des noms bâtie sur tous les champs personnalisés ; homonymie touchant un champ configuré → `UsineErreur` ; test inversé.
  - `[medium]` `[patch]` (blind) item `custom` résolu vers un champ système (« Statut » → `status`) — groupe N : carte limitée aux champs personnalisés ; test `test_item_personnalise_au_nom_d_un_champ_systeme_ignore`.
  - `[low]` `[reject]` (blind) client ouvert à la composition, fermé seulement par l'étape — un `Rapport` est construit puis exécuté dans `lancer_rapport` ; fuite limitée à un Passage avorté avant l'extraction, libérée à la fin du processus CLI ; fabrique paresseuse = nouvelle surface.
  - `[low]` `[reject]` (blind) étape non réexécutable (client fermé) — le registre est reconstruit à chaque `lancer_rapport` ; aucune réexécution n'existe.
  - `[low]` `[reject]` (blind) `fermer()` qui lève masque l'erreur d'origine — `httpx.Client.close` ne lève pas en pratique ; garde supplémentaire sans défaut constaté.
  - `[medium]` `[patch]` (blind) pagination par position décalée si l'ensemble change entre pages — groupe P : chaque page est une recherche `startAt=0` à curseur `key > "<dernière clé>"` ; `fenetre` remplacé par `taille_page`.
  - `[false]` `[reject]` (blind) dédoublonnage changelog en ligne / complément non testé — `source_recherche_page_2.json` porte 20005 et 20006 en ligne et `source_issue_DEMO-3.json` les répète ; `test_rend_le_flux_cloud_a_la_source_pres` exige le flux exact.
  - `[low]` `[reject]` (blind) chemins d'erreur non testés (ticket sans clé, historique illisible) — gardes simples d'une ligne, échec bruyant ; tests sans défaut à protéger.
  - `[low]` `[patch]` (blind) `_ITEM_IGNORE` mutable partagé — enveloppé dans `MappingProxyType`.
  - `[low]` `[patch]` (blind) secret blanc non testé — groupe S : `test_secret_blanc_extraction_bouchon[cloud|dc]`.
  - `[medium]` `[patch]` (blind) fenêtre de 10 000 non configurable, plafond serveur inférieur — groupe P : le curseur par clé rend chaque requête indépendante de `startAt`.
  - `[low]` `[reject]` (blind) duplication des fixtures `delenv` et remplacement textuel de `mode` dans `test_composition.py` — style de test, aucun défaut.
  - `[low]` `[patch]` (verification-gap) secret de plateforme blanc → bouchon non vérifié — groupe S.
  - `[low]` `[reject]` (verification-gap, autre) client non fermé si `executer_passage` échoue avant l'extraction — même motif que la ligne blind correspondante.
  - `[medium]` `[patch]` (edge) homonyme non configuré — groupe N.
  - `[medium]` `[patch]` (edge) item personnalisé au nom d'un champ système — groupe N.
  - `[low]` `[patch]` (edge) plafond `startAt` serveur inférieur à la fenêtre — groupe P.
  - `[low]` `[patch]` (edge) ensemble de résultats qui rétrécit entre pages — groupe P.
  - `[false]` `[reject]` (edge) `GET /issue/{cle}` rendant un autre ticket — Jira rend le ticket demandé ; aucun chemin ne mène à une autre clé.
  - `[false]` `[reject]` (edge) champs système DC dont le nom diffère de l'identifiant (Fix Version) — les champs système configurés sont `status`, `summary`, `description`, dont le nom de changelog DC est l'identifiant.
  - `[low]` `[reject]` (edge) fuite du client si le Passage avorte — même motif que la ligne blind.
  - `[low]` `[reject]` (edge) réexécution de l'étape — même motif que la ligne blind.
  - `[false]` `[reject]` (intent) activation conditionnée au secret, non écrite dans l'epic — l'intention exige qu'un Passage sans Jira ni secret soit publié avec `config/jira.yaml` versionné ; décision consignée dans les Design Notes.
  - `[false]` `[reject]` (intent) clé `mode` au lieu d'`adaptateur` — `ConfigJira.mode` est le sélecteur du contrat gelé, commenté « Adaptateur Jira ».
  - `[false]` `[reject]` (intent) câblage sur la lane plutôt qu'en PR courte sur `main` — l'intention de ce run le demande explicitement, `composition.py` consigné hors lane.
  - `[false]` `[reject]` (intent) test par `lancer_rapport` et non par la commande `usine rapport` — `chaine/cli.py` délègue directement à `lancer_rapport` ; le comportement testé est celui de la commande.
  - `[false]` `[reject]` (intent) équivalence de contrat non démontrée par une exécution — la suite tourne : 8 tests `jira_dc` passent, comme `jira_cloud`.

## Design Notes

- **Curseur par clé plutôt que tranches de dates** : la recherche est triée par clé ; chaque page est une recherche `startAt=0` restreinte par `key > "<dernière clé reçue>"`. Elle reprend exactement après le dernier ticket reçu, sans chevauchement ni fuseau, contourne la fenêtre de 10 000 résultats quel que soit le plafond du serveur, et ne saute aucun ticket si l'ensemble change entre deux pages (fenêtre `updated` relative réévaluée par Jira).
- **Activation par secret** : la Story 2.5 ne peut pas ajouter `journal` à `ConfigJira.mode` (contrat gelé) ; la présence du secret de lecture de la plateforme est le seul signal disponible. Le Mode repli reste manuel (H-30) et coupe l'extraction.
- **Fichiers hors lane** : `src/usine/composition.py` (câblage de l'extraction et sélection Cloud/DC, report medium de la 2.3, AD-1) ; `tests/unit/test_composition.py` (tests de ce câblage) ; `tests/contrat/source_tickets/fabriques.py` (fabrique DC, prévue par son docstring).

## Verification

**Commands:**
- `uv run ruff check .` et `uv run ruff format --check .` -- aucun écart.
- `uv run mypy` -- aucune erreur.
- `uv run lint-imports` -- tous les contrats tenus.
- `uv run pytest -q` -- tout passe, sans réseau.
- `uv run python .github/scripts/controle_lanes.py --branche lane/2-extraction --base main` -- seuls les trois fichiers hors lane listés.

## Auto Run Result

Status: done

- **Changement** : nouveau paquet `usine.adaptateurs.jira_dc` : `SourceJiraDC` (port `SourceTickets`, API v2) lit `GET /rest/api/2/field` pour résoudre les noms des champs personnalisés du changelog, cherche par `GET /rest/api/2/search` page par page avec un curseur `key > "<dernière clé>"` (fenêtre de 10 000 contournée), complète un changelog tronqué par `GET /rest/api/2/issue/{cle}` et réutilise la conversion Cloud (`source = jira_dc`). `composition.py` câble enfin `EtapeExtraction` (marge de `config/jira.yaml`, `donnees/entrepot.duckdb`, client fermé après l'étape) sur `SourceJiraCloud` ou `SourceJiraDC` selon `mode`, quand le secret de lecture de la plateforme est présent et hors Mode repli ; sinon bouchon et Journal seul.
- **Fichiers** :
  - `src/usine/adaptateurs/jira_dc/{__init__,source}.py` -- adaptateur DC.
  - `src/usine/adaptateurs/jira_http/{transport,clients}.py` -- `requete_liste` (tableau JSON, liste blanche vérifiée).
  - `src/usine/adaptateurs/jira_cloud/source.py` -- `requete_jql(…, apres)`.
  - `src/usine/adaptateurs/entrepot_duckdb/extraction.py` -- `fermer` et propriétés d'`EtapeExtraction`.
  - `src/usine/composition.py` (hors lane) -- `_etape_extraction`, sélection Cloud/DC.
  - `tests/fixtures/jira_dc/source_*.json` -- fixtures v2 équivalentes aux fixtures Cloud.
  - `tests/unit/adaptateurs/jira_dc/*`, `jira_http/test_{transport,liste_blanche}.py`, `jira_cloud/test_source.py`, `entrepot_duckdb/test_extraction.py` -- tests.
  - `tests/contrat/source_tickets/fabriques.py` (hors lane) -- `fabrique_jira_dc`.
  - `tests/unit/test_composition.py` (hors lane) -- sélection et Passages de bout en bout (sans secret ; `mode: dc`).
- **Revue** : 27 constats ; patchés : 2 entrées medium (résolution des noms limitée aux champs personnalisés avec homonymie détectée ; pagination par curseur de clé) et 2 low (`_ITEM_IGNORE` en lecture seule ; test du secret blanc) ; aucun report ; le reste rejeté, motifs dans le Review Triage Log.
- **Relecture de suivi recommandée** : oui (deux entrées medium patchées) : la pagination DC a été réécrite après revue (curseur par clé, arrêt sur `total`), et la résolution des noms a changé de règle ; une seconde lecture de `jira_dc/source.py` vérifierait l'arrêt sur un serveur DC qui omet `total` ou plafonne `maxResults`.
- **Vérification** : `ruff check`, `ruff format --check`, `mypy` (207 fichiers), `lint-imports` (13 contrats) verts ; `pytest -q` : 1504 réussis, 1 ignoré ; suite de contrat : 8 tests `jira_dc` comme `jira_cloud` ; chaque ligne de la matrice I/O couverte.
- **Risques résiduels** : forme réelle des réponses DC (items sans `fieldId`, `total` du curseur) non éprouvée sur un vrai Data Center ; activation de l'extraction par la seule présence du secret (un `JIRA_TOKEN_LECTURE` exporté dans le shell d'un développeur déclenche l'extraction dans les tests hors lane qui appellent `lancer_rapport`, sans réseau donc en échec) ; client Jira non fermé si un Passage avorte avant l'étape `extraction`.
