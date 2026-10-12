---
title: 'Story 2.1 : Transport Jira commun et client de lecture à liste blanche'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '0714669752662ca46ca4afecbf08fc62b4bd2463'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
warnings: ['oversized']
deferred:
  - summary: >-
      Fixtures Jira synthétiques (format documenté), pas des enregistrements d'un vrai site.
    evidence: |-
      Aucun site Jira ni jeton disponible pendant le run autonome ; tests/fixtures/jira_cloud et jira_dc sont écrites à la main. À remplacer par de vrais enregistrements à la recette 2.7.
    location: >-
      tests/fixtures/jira_cloud, tests/fixtures/jira_dc
    severity: medium
  - summary: >-
      Branches nextPageToken vide et nextPageToken non textuel de paginer_par_jeton non testées.
    evidence: |-
      Aucun test ne couvre "nextPageToken": "" ni un jeton entier ; branches défensives, à épingler avec les vrais enregistrements (recette 2.7).
    location: >-
      src/usine/adaptateurs/jira_http/pagination.py
    severity: low
---

<intent-contract>

## Intent

**Problem:** L'extraction (L2) et l'injecteur (L1, Story 1.6) ont besoin d'un transport HTTP Jira commun (pagination Cloud et DC, authentification, reprise sur 429), et le Sponsor exige que l'extraction ne puisse techniquement émettre aucune écriture vers Jira, alors que des lectures passent par POST (`search/jql`, `changelog/bulkfetch`).

**Approach:** Créer le paquet `usine.adaptateurs.jira_http` : un transport httpx (authentification, 429 + `Retry-After`, erreurs en `UsineErreur`, pagination par jeton et par position), un `ClientJiraLecture` qui vérifie chaque requête contre une liste blanche `(méthode, gabarit de chemin)` par plateforme **avant** tout envoi, et un `ClientJiraEcriture` distinct, sans liste blanche, construit avec `JIRA_TOKEN_INJECTION`. Tests sur fixtures enregistrées et `httpx.MockTransport`, sans réseau.

## Boundaries & Constraints

**Always:** pas de réseau dans les tests (`httpx.MockTransport`) ; secrets passés en `SecretStr`, jamais recopiés dans un message, un `repr` ou une exception ; toute erreur est une `UsineErreur` qui nomme la méthode, le chemin et le statut ; redirections non suivies (l'en-tête d'authentification ne part jamais vers un autre hôte) ; nombre de tentatives = `ConfigJira.tentatives_max` ; attente injectable (pas de vraie attente dans les tests) ; textes et docstrings en français ; mypy strict, ruff, import-linter verts.

**Never:** modifier `src/usine/contrats/`, `src/usine/ports/`, `composition.py`, `cli.py` racine, `tests/contrat/`, `tests/doublures/` ; importer `usine.config` depuis les adaptateurs (interdit par import-linter : les identifiants arrivent en paramètres) ; lire `.env` ; implémenter l'adaptateur Cloud/DC (Stories 2.2, 2.4) ou l'injecteur (1.6) ; pagination parallèle.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Pagination Cloud | `search/jql`, page 1 avec `nextPageToken`, page 2 sans | éléments des deux pages, dans l'ordre ; le jeton de la page 1 est renvoyé dans la requête 2 | — |
| Pagination DC | `/rest/api/2/search`, `total`=3, serveur plafonne à 2 par page | 3 éléments ; 2e requête `startAt=2` (avance du nombre reçu, pas du `maxResults` demandé) | page vide avant `total` : arrêt |
| Jeton répété | page renvoyant le même `nextPageToken` | — | `UsineErreur` (boucle de pagination) |
| Auth Cloud | e-mail + jeton | `Authorization: Basic base64(email:jeton)` | jeton ou e-mail absent : `UsineErreur` nommant `JIRA_EMAIL` / `JIRA_TOKEN_LECTURE` |
| Auth DC | PAT | `Authorization: Bearer <pat>` | PAT absent : `UsineErreur` nommant `JIRA_DC_PAT` |
| 429 puis 200 | `Retry-After: 7` | attend 7 s puis renvoie le 200 | — |
| 429 sans en-tête | pas de `Retry-After` | attente exponentielle (1, 2, 4… s, plafonnée) | — |
| 429 persistant | `tentatives_max`=3 | 3 envois, puis échec | `UsineErreur` « 429 après 3 tentatives » |
| Hors liste blanche | `POST /rest/api/3/issue` (lecture Cloud) | aucun envoi | `RequeteJiraInterdite` (sous-classe d'`UsineErreur`) |
| Lecture POST | `POST search/jql`, `POST changelog/bulkfetch` | autorisés et envoyés | — |
| Chemin piégé | `GET /rest/api/3/issue/../issue` , `?` dans le chemin, URL absolue | aucun envoi | `RequeteJiraInterdite` |
| Erreur HTTP | 401, 404, 500 | — | `UsineErreur` nommant méthode, chemin, statut, sans corps ni secret |
| Réseau | `httpx.TransportError` | — | `UsineErreur` nommant méthode et chemin |

</intent-contract>

## Code Map

- `src/usine/contrats/config.py:211` `ConfigJira` -- lecture seule : `url_site`, `mode` (`cloud`|`dc`), `tentatives_max` ; aucune clé d'e-mail (vient de `JIRA_EMAIL`).
- `src/usine/config/secrets.py` `Secrets` -- lecture seule : `jira_email`, `jira_token_lecture`, `jira_token_injection`, `jira_dc_pat` (`SecretStr`). Les adaptateurs ne l'importent pas ; la composition passera ces valeurs.
- `src/usine/contrats/erreurs.py` `UsineErreur` -- base des erreurs.
- `src/usine/adaptateurs/journal/__init__.py` -- modèle de style (docstring de module, messages d'erreur).
- `pyproject.toml` -- `httpx==0.28.1` déjà présent ; contrat import-linter « adaptateurs » autorise httpx, interdit `usine.config` et `yaml`.
- `tests/conftest.py` -- fixture autouse `_sans_reseau` : bloque toute connexion hors boucle locale.
- `.github/scripts/controle_lanes.py` -- lane 2 : `src/usine/adaptateurs/jira_http`, `tests/unit/adaptateurs/jira_http`, `tests/fixtures/jira_cloud`, `tests/fixtures/jira_dc`.
- Recherche : Cloud `search/jql` pagine par `nextPageToken` (absent en dernière page, pages courtes possibles) ; `changelog/bulkfetch` (POST, `nextPageToken`) ; DC v2 `startAt`/`maxResults`/`total` avec plafond serveur.

## Tasks & Acceptance

**Execution:**
- `src/usine/adaptateurs/jira_http/transport.py` -- `Authentification` (fabriques `cloud(email, jeton)` et `dc(pat)`, `repr` masqué), `TransportJira(url_site, authentification, tentatives_max, *, attendre=time.sleep, transport_http=None)` avec `requete(methode, chemin, *, params=None, corps=None) -> dict[str, Any]`, gestion 429/`Retry-After` (secondes ou date HTTP, plafond 120 s), erreurs, `fermer()` et gestionnaire de contexte -- transport commun AD-5.
- `src/usine/adaptateurs/jira_http/pagination.py` -- `paginer_par_jeton(requete, methode, chemin, cle, *, params=None, corps=None)` (jeton dans le corps pour POST, dans les paramètres pour GET ; garde contre un jeton répété) et `paginer_par_position(requete, chemin, cle, *, params=None, taille_page=...)` (`startAt`/`maxResults`, `total` et `isLast` respectés, avance du nombre d'éléments reçus) ; itérateurs d'éléments -- pagination Cloud et DC.
- `src/usine/adaptateurs/jira_http/clients.py` -- `LISTE_BLANCHE_LECTURE: Mapping[Plateforme, frozenset[tuple[str, str]]]`, `RequeteJiraInterdite`, `ClientJiraLecture` (vérifie méthode et chemin avant délégation au transport ; méthodes `requete`, `paginer_par_jeton`, `paginer_par_position`), `ClientJiraEcriture` (sans liste blanche), fabriques `construire_client_lecture(config, *, email, jeton_lecture, pat, ...)` et `construire_client_ecriture(config, *, email, jeton_injection, ...)` (Cloud seulement) -- AD-5.
- `src/usine/adaptateurs/jira_http/__init__.py` -- docstring et réexports publics.
- `tests/fixtures/jira_cloud/recherche_page_1.json`, `recherche_page_2.json`, `bulkfetch_page_1.json`, `bulkfetch_page_2.json` ; `tests/fixtures/jira_dc/recherche_page_1.json`, `recherche_page_2.json` -- réponses au format des API (données fictives, projet `DEMO`).
- `tests/unit/adaptateurs/jira_http/__init__.py`, `test_transport.py`, `test_pagination.py`, `test_liste_blanche.py`, `test_ecriture.py` -- tests de la matrice ; test de contrat de liste blanche paramétré Cloud/DC ; garde « seule la composition du générateur instancie le client d'écriture ».

**Acceptance Criteria:**
- Given `adaptateurs/jira_http` et les fixtures `tests/fixtures/jira_cloud|jira_dc`, when on pagine `search/jql` (Cloud) et `/rest/api/2/search` (DC) via `httpx.MockTransport`, then tous les éléments sont rendus dans l'ordre, avec l'authentification de la plateforme, et un 429 est repris après l'attente `Retry-After`.
- Given un `ClientJiraLecture` construit avec `JIRA_TOKEN_LECTURE` (Cloud) ou `JIRA_DC_PAT` (DC), when il reçoit une requête hors liste blanche (`POST /rest/api/3/issue`, `PUT`, `DELETE`, `POST …/transitions`, `POST /rest/api/2/issue`, chemin de l'autre plateforme), then il lève `RequeteJiraInterdite` et le transport HTTP n'a reçu aucune requête ; `POST search/jql` et `POST changelog/bulkfetch` (Cloud) et `POST /rest/api/2/search` (DC) restent autorisés.
- Given le transport, when l'injecteur en a besoin, then `construire_client_ecriture` rend un `ClientJiraEcriture` distinct authentifié par `JIRA_TOKEN_INJECTION`, et un test vérifie qu'aucun module de `src/usine` hors `adaptateurs/jira_http` et `generateur/**/cli.py` ou `composition.py` ne le référence.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 32 findings — high 0, medium 6, low 19, false 7, maybe-false 0
- findings:
  - `[medium]` `[patch]` (intent) `TransportJira` public : l'extraction pourrait contourner la liste blanche — garde étendue à `TransportJira` et `Authentification` (groupé avec le constat blind équivalent).
  - `[false]` `[reject]` (intent) le client n'est pas lié à la variable `JIRA_TOKEN_LECTURE` — les adaptateurs ne peuvent pas importer `usine.config` (import-linter) ; la composition passe le secret, et l'erreur nomme la variable.
  - `[false]` `[reject]` (intent) « test de contrat » hors de `tests/contrat/` — `tests/contrat/` appartient à `main` (AD-21) ; le test paramétré Cloud/DC existe dans `test_liste_blanche.py`.
  - `[low]` `[patch]` (intent) la garde autorise `composition.py` — retiré ; seuls `adaptateurs/jira_http/**` et `generateur/**/cli.py` restent.
  - `[false]` `[reject]` (intent) aucun usage côté injecteur — l'injecteur est la Story 1.6 (lane L1) ; le client d'écriture est livré et testé.
  - `[medium]` `[defer]` (intent) fixtures synthétiques, pas enregistrées — aucun site Jira pour ce run ; remplacement à la recette 2.7.
  - `[false]` `[reject]` (intent) liste blanche plus large que les deux POST cités — élargissement délibéré, lectures seulement, épinglé par `test_liste_blanche_sans_ecriture`.
  - `[low]` `[reject]` (intent) pas de pagination par position en POST pour DC — `POST /rest/api/2/search` reste utilisable par `requete` ; la Story 2.4 l'ajoutera si besoin ; correctif = nouvelle surface.
  - `[medium]` `[patch]` (blind) chemin absolu ou `//` envoyé avec le jeton vers un autre hôte — `requete` refuse avant envoi ; `test_chemin_hors_site_jamais_envoye`.
  - `[medium]` `[patch]` (blind) contournement par les exports publics non vu par la garde — garde étendue à `TransportJira` et `Authentification`.
  - `[low]` `[patch]` (blind) motifs de la garde trop larges — `composition.py` retiré ; les motifs restants désignent la composition du générateur et le paquet lui-même.
  - `[low]` `[reject]` (blind) seul 429 est repris, pas 503 ni les erreurs réseau — hors exigence (429 + `Retry-After`) ; un Passage échoué est rejoué sans corruption (AD-6) ; correctif = nouvelles branches.
  - `[low]` `[reject]` (blind) `paginer_par_position` peut boucler si le serveur ignore `startAt` sans `total` — DC renvoie toujours `total` ; correctif = garde supplémentaire.
  - `[low]` `[reject]` (blind) POST DC autorisé mais sans paginateur — même constat que la ligne intent équivalente.
  - `[low]` `[reject]` (blind) erreurs 4xx sans détail — le spec impose de ne pas recopier le corps (données personnelles) ; correctif = modifier le spec.
  - `[false]` `[reject]` (blind) points d'accès manquants dans la liste blanche — aucun consommateur ne les demande ; les Stories 2.2 et 2.4 les ajouteront.
  - `[low]` `[patch]` (blind) type `Plateforme` défini deux fois — défini une fois dans `transport.py`, importé ailleurs.
  - `[low]` `[reject]` (blind) horloge de `Retry-After` non injectable, `1.5` non lu — délai entier selon RFC 9110 ; tests déterministes en place.
  - `[false]` `[reject]` (blind) indépendance vis-à-vis de `usine.config` non vérifiée — le contrat import-linter « adaptateurs » interdit `usine.config`.
  - `[low]` `[reject]` (blind) clients httpx non fermés dans des tests — sans effet sur la suite ; correctif diffus.
  - `[medium]` `[patch]` (blind) exception réseau chaînée qui garde l'en-tête secret — `from None` ; test `__cause__ is None`.
  - `[low]` `[patch]` (edge) jeton Cloud non nettoyé de ses espaces — `.strip()` ; `test_identifiants_copies_avec_espaces_nettoyes`.
  - `[low]` `[patch]` (edge) PAT non nettoyé — même correctif et même test.
  - `[low]` `[reject]` (edge) secret non ASCII → `UnicodeEncodeError` — jetons Atlassian ASCII par construction ; correctif = garde supplémentaire.
  - `[low]` `[patch]` (edge) `httpx.DecodingError` non capturée — capture de `httpx.RequestError`.
  - `[low]` `[patch]` (edge) `Retry-After` `²` fait planter `float` — `isascii() and isdigit()` ; cas ajouté au test.
  - `[low]` `[reject]` (edge) `requete` après `fermer()` lève `RuntimeError` — usage erroné du programmeur, échec bruyant acceptable.
  - `[low]` `[reject]` (edge) boucle si `startAt` ignoré — même cause que la ligne blind correspondante.
  - `[low]` `[reject]` (edge) pages vides infinies à jetons distincts — serveur hostile improbable ; correctif = garde supplémentaire.
  - `[false]` `[reject]` (edge) `taille_page` booléen — paramètre typé `int`, vérifié par mypy strict ; aucun appelant.
  - `[medium]` `[patch]` (verification-gap) `tentatives_max` des fabriques non testé — `test_client_lecture_respecte_tentatives_max` (Cloud, DC) et `test_client_ecriture_respecte_tentatives_max`.
  - `[low]` `[defer]` (verification-gap) branches jeton vide / non textuel non testées — à épingler avec les vrais enregistrements (2.7).

## Design Notes

- **Liste blanche** : gabarits à segments ; `{x}` accepte un segment `[A-Za-z0-9_.~-]+` sauf `.` et `..`. Le chemin doit commencer par `/rest/`, sans `?`, `#`, `//`, `%` ni `://` ; la méthode est comparée en majuscules. Cloud : `GET|POST /rest/api/3/search/jql`, `POST /rest/api/3/search/approximate-count`, `POST /rest/api/3/changelog/bulkfetch`, `GET /rest/api/3/issue/{cle}`, `GET /rest/api/3/issue/{cle}/changelog`, `GET /rest/api/3/field`, `GET /rest/api/3/serverInfo`, `GET /rest/api/3/myself`. DC : `GET|POST /rest/api/2/search`, `GET /rest/api/2/issue/{cle}`, `GET /rest/api/2/field`, `GET /rest/api/2/serverInfo`, `GET /rest/api/2/myself`.
- **Test de contrat** : `tests/contrat/` appartient à `main` ; le test de contrat de la liste blanche vit donc dans `tests/unit/adaptateurs/jira_http/test_liste_blanche.py`, paramétré par plateforme.
- **Client d'écriture Cloud seulement** : l'injection vise le site Jira Cloud Free (FR-5) ; `mode: dc` lève une `UsineErreur` explicite.
- **Fixtures** : aucun site Jira n'est disponible pour ce run ; les fixtures reproduisent le format documenté des réponses (recherche documentaire du 2026-10-10) et seront remplacées par de vrais enregistrements à la recette 2.7.
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

- **Changement** : paquet `usine.adaptateurs.jira_http` : transport httpx commun (authentification Cloud Basic / DC Bearer, reprise sur 429 avec `Retry-After`, erreurs en `UsineErreur` sans secret, redirections et chemins hors site refusés), pagination par jeton (Cloud) et par position (DC), `ClientJiraLecture` à liste blanche vérifiée avant envoi, `ClientJiraEcriture` distinct (Cloud, `JIRA_TOKEN_INJECTION`).
- **Fichiers** :
  - `src/usine/adaptateurs/jira_http/transport.py` -- authentification, transport, 429, erreurs.
  - `src/usine/adaptateurs/jira_http/pagination.py` -- `paginer_par_jeton`, `paginer_par_position`.
  - `src/usine/adaptateurs/jira_http/clients.py` -- liste blanche, clients de lecture et d'écriture, fabriques.
  - `src/usine/adaptateurs/jira_http/__init__.py` -- réexports.
  - `tests/fixtures/jira_cloud/*.json`, `tests/fixtures/jira_dc/*.json` -- réponses fictives au format des API.
  - `tests/unit/adaptateurs/jira_http/` -- `outils.py`, `test_transport.py`, `test_pagination.py`, `test_liste_blanche.py` (contrat Cloud/DC), `test_ecriture.py` (garde de construction).
- **Revue** : 32 constats ; 13 corrigés (5 medium, 8 low, en 7 correctifs), 2 reportés (fixtures synthétiques, branches de jeton), 17 rejetés (motifs dans le Review Triage Log).
- **Relecture de suivi recommandée** : oui (entrées medium corrigées : 4) ; risque non vérifié : la garde « seule la composition du générateur construit le client d'écriture » reste une recherche textuelle, et la surface de sécurité (hôte, secrets) a été modifiée après la relecture.
- **Vérification** : `ruff check`, `ruff format --check`, `mypy`, `lint-imports` verts ; `pytest -q` : 1111 réussis, 1 ignoré ; `controle_lanes.py` : tous les fichiers dans la lane.
- **Critère reporté** : fixtures réellement enregistrées → recette 2.7 (aucun site Jira pour ce run).
- **Risques résiduels** : seul 429 est repris (pas 503) ; pagination DC en GET seulement.
