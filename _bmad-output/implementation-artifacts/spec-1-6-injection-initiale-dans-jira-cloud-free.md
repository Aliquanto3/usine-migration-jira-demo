---
title: 'Story 1.6 : Injection initiale dans Jira Cloud Free'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'ccdb87f1a8bebe718ddbf99b628094cc34d227e7'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: ['oversized']
deferred:
  - summary: >-
      La garde « projet peuplé » repose sur un compte approximatif filtré par types, après la préparation du site.
    evidence: |-
      Index de recherche en retard possible ; autres types ignorés ; préparation écrite avant refus. Robustesse de réinjection : Story 1.7.
    location: >-
      src/usine/generateur/injecteur/injection.py:122
    severity: medium
  - summary: >-
      controler ne vérifie pas qu'un workflow, schéma ou projet trouvé par nom lie Anomalie au workflow H-17.
    evidence: |-
      workflow() et schema() rendent l'objet existant sans contrôle ; un projet tiers mal câblé échouerait aux transitions après créations.
    location: >-
      src/usine/generateur/injecteur/site.py
    severity: medium
  - summary: >-
      Identifiants champs de config/jira.yaml fictifs alors que url_site est réel.
    evidence: |-
      Exclu par l'intention (fixtures L2) ; les réels sont dans donnees/injection/site_jira.json ; à aligner avant usine rapport.
    location: >-
      config/jira.yaml
    severity: medium
  - summary: >-
      État partiel sans statut atteint par ticket ni ticket ambigu (POST /issue en échec après création).
    evidence: |-
      Nécessaire à une reprise, hors périmètre (Story 1.7).
    location: >-
      src/usine/generateur/injecteur/injection.py
    severity: medium (unverified)
  - summary: >-
      Champs obligatoires supplémentaires, contextes de champ propres à d'autres projets, statuts réutilisés de catégorie différente non contrôlés.
    evidence: |-
      Dépend de la configuration réelle du site ; l'injection réelle tranchera.
    location: >-
      src/usine/generateur/injecteur/site.py
    severity: medium (unverified)
  - summary: >-
      Conformité de la doublure HTTP à l'API réelle non éprouvée par les tests.
    evidence: |-
      Faux Jira écrit avec le code ; injection réelle après intégration.
    location: >-
      tests/unit/generateur/injecteur/faux_jira.py
    severity: low
---

<intent-contract>

## Intent

**Problem:** Le Programme fictif n'existe que dans le Journal : aucun site Jira ne le porte, donc la démo ne s'appuie sur aucune vraie API Jira (FR-5). Un site Jira Cloud Free existe désormais (`https://anaelyahi.atlassian.net`), avec `JIRA_TOKEN_INJECTION` dans le `.env` de `main`.

**Approach:** Un injecteur `generateur/injecteur` prépare le site par l'API REST v3 (types de tickets, champs, workflow H-17, schémas, écran, projet `DEMO`, idempotent par nom), puis crée les tickets un à un dans l'ordre des clés générées et les amène à leur état à la Date d'injection par les transitions du workflow, et écrit `donnees/injection/manifeste_injection.json`. Seule sa composition (`generateur/injecteur/cli.py`) construit le client d'écriture.

## Boundaries & Constraints

**Always:**
- API REST seulement, sans import CSV ou JSON (AD-4) ; transport commun `adaptateurs/jira_http` (reprise sur 429 avec `Retry-After`), débit plafonné (défaut 5 requêtes/s).
- Préparation idempotente : chaque objet est d'abord cherché par nom ; un objet existant n'est jamais modifié ni recréé ; on ne supprime rien. Le projet `KAN` (et tout autre projet) n'est jamais touché.
- Ordre déterministe : tickets triés par `rang_cle` de la clé générée ; un Journal identique donne une suite de requêtes identique.
- État injecté = repli de tous les événements du ticket de jour local ≤ Date d'injection ; statut final atteint par le plus court chemin du workflow H-17.
- Le cœur de l'injecteur (`plan`, `site`, `injection`) n'importe que `contrats` et reçoit le client par un `Protocol` ; ni secret ni corps de réponse dans un message.
- Tests sans réseau (doublure HTTP `httpx.MockTransport`) ; la fixture `_sans_secret_jira` reste active.

**Never:**
- Réinjection idempotente, reprise d'une injection interrompue, clés stables entre sites (Story 1.7) : un projet déjà peuplé ou un manifeste existant font refuser l'injection.
- Modifier `contrats/`, `ports/`, `adaptateurs/jira_http` ; aligner `config/jira.yaml` `champs` sur les identifiants réels (casserait les fixtures L2 : consigné pour L2).
- `datetime.now` ou `time` dans le cœur : horloge et attente sont injectées par la composition.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Site vierge | Journal réduit, faux Jira vide | Types, 7 champs + options, statuts, workflow, schémas, écran, projet créés ; tickets créés dans l'ordre ; statuts finaux = Journal ; manifeste valide | — |
| Site déjà préparé | objets existants par nom, projet vide | Aucune création de configuration, seules les options manquantes ; tickets injectés | — |
| Projet non vide | ≥ 1 ticket des 3 types dans `DEMO` | Aucun ticket créé | `UsineErreur` qui renvoie à la Story 1.7 |
| Manifeste existant | `donnees/injection/manifeste_injection.json` présent | Rien n'est envoyé | `UsineErreur` qui nomme le fichier |
| 429 | réponse 429 + `Retry-After` | Requête reprise après l'attente | transport commun |
| Échec à mi-parcours | erreur HTTP au ticket n | Pas de manifeste ; `etat_injection_partielle.json` (tickets créés, correspondance partielle, dernière erreur) | `InjectionInterrompue` (`UsineErreur`) |
| Secret absent | pas de `JIRA_TOKEN_INJECTION` | Rien n'est envoyé | erreur qui nomme `JIRA_TOKEN_INJECTION` |
| Projet existant mal configuré | type ou champ absent de l'écran de création | Aucun ticket créé | `UsineErreur` qui nomme le type ou le champ |

</intent-contract>

## Code Map

- `src/usine/adaptateurs/jira_http/clients.py` (L2, lecture seule) -- `construire_client_ecriture(config, email=, jeton_injection=, attendre=, transport_http=)` ; `requete`/`requete_liste` ; 404 et autres statuts ≠ 2xx → `UsineErreur` sans le corps (chercher par recherche, jamais par 404).
- `tests/unit/adaptateurs/jira_http/test_ecriture.py` -- gardes AST et grimp : seuls `adaptateurs/jira_http/*` et `generateur/**/cli.py` citent `ClientJiraEcriture`, `construire_client_ecriture`, `TransportJira`, `Authentification` ou `._transport` (même en docstring pour la garde textuelle).
- `src/usine/contrats/evenements.py` (gelé) -- `ManifesteInjection` (Date d'injection, `debut_injection`, `horodatage_fin_injection`, `cle_projet`, `correspondance_cles` injective, clés du projet) ; `EnteteJournal`, `Evenement`.
- `src/usine/contrats/tickets.py` (gelé) -- `Champ`, `CHAMPS_PAR_TYPE`, `DOMAINES_CANONIQUES`, `STATUTS_FERMES`, `rang_cle`.
- `src/usine/contrats/calendrier.py` -- `jour_local`.
- `src/usine/adaptateurs/journal/__init__.py` (L2) -- `SourceJournal(chemin)` : `entete`, `evenements()` ; `CHEMIN_MANIFESTE_INJECTION`.
- `src/usine/adaptateurs/composite/source.py` (L2) -- coupe à `horodatage_fin_injection` (strict) : la fin doit couvrir l'horloge du serveur.
- `src/usine/adaptateurs/jira_cloud/conversion.py` (L2) -- lit les listes de sélection par `{value}`, l'ADF par paragraphes, ignore `statut` hors Anomalies.
- `src/usine/config/secrets.py` -- `charger_secrets(racine)` : `jira_email`, `jira_token_injection`.
- `src/usine/generateur/cli.py` -- application `usine donnees` : y enregistrer `injecter`.
- `config/jira.yaml` (L2) -- `url_site`, `cle_projet`, `types_tickets`, `valeurs` (noms Jira des statuts et options) ; `champs` reste fictif.
- `tests/unit/contrats/test_config.py:327` -- fige l'URL `https://jira.example.invalid`.
- `tests/unit/generateur/programme_reduit.yaml` -- Programme réduit pour les tests.

## Tasks & Acceptance

**Execution:**
- `src/usine/generateur/injecteur/plan.py` -- `planifier(entete, evenements) -> PlanInjection` (tickets ordonnés, valeurs canoniques finales), `TRANSITIONS_H17`, `chemin_statuts`, `document_adf`, `champs_creation` -- cœur pur.
- `src/usine/generateur/injecteur/site.py` -- `ClientJira` (Protocol), `preparer_site(client, config, valeurs_libres) -> SiteDemo` : recherche par nom puis création ; vérifie par `createmeta` que chaque type et champ est créable -- spike rendu reproductible.
- `src/usine/generateur/injecteur/injection.py` -- `injecter(client, plan, site, config, horloge, limiter) -> ManifesteInjection`, refus d'un projet peuplé, cache des transitions par statut, fin = max(horloge, `serverTime`), `InjectionInterrompue` avec l'état partiel.
- `src/usine/generateur/injecteur/cli.py` + `__init__.py` -- composition : secrets, client d'écriture (`JIRA_TOKEN_INJECTION`), Journal, garde du manifeste existant, écriture atomique du manifeste, de `site_jira.json` et de l'état partiel, avertissement si `champs` diffère du site.
- `src/usine/generateur/cli.py` -- commande `usine donnees injecter`.
- `config/jira.yaml`, `tests/unit/contrats/test_config.py` -- URL réelle du site (hors lane).
- `tests/unit/generateur/injecteur/` -- faux Jira HTTP en mémoire ; tests de la matrice, de l'ordre, de l'absence d'import CSV, de la garde « seul l'injecteur lit `jira_token_injection` ».

**Acceptance Criteria:**
- Given un faux Jira vierge et le Journal réduit, when on injecte, then projet, 3 types, workflow H-17 et champs Entité, Vague, Domaine, Gravité, Phase existent, chaque ticket est créé par `POST /rest/api/3/issue` dans l'ordre des clés et son état Jira égale l'état replié du Journal.
- Given l'injection terminée, when on lit le manifeste, then `SourceJournal(journal, manifeste)` le relit sans erreur et il porte Date d'injection, début, fin ≥ dernière écriture, correspondance complète et clé de projet.
- Given le code source, when la garde s'exécute, then seul `generateur/injecteur/cli.py` lit `jira_token_injection` et construit le client d'écriture ; `composition.py` ne lit jamais la variable.
- Given le spike, when il se conclut, then sa conclusion figure dans les Design Notes.

## Design Notes

**Spike (2026-10-12, environ 1 h, site réel, jeton d'injection, compte administrateur) : tout est faisable par l'API sur Jira Cloud Free.** Créés depuis `main` par des sondes : types `Anomalie` (10010), `Cas de test` (10011), `Certification` (10012) (`POST /issuetype`) ; 7 listes de sélection `customfield_10043` à `10049` (`POST /field`, contexte global créé d'office ; options par `POST /field/{id}/context/{ctx}/option`) ; 6 statuts et le workflow « DEMO : workflow des Anomalies » en un appel `POST /workflows/create` (références de statut en UUID obligatoires, validées d'abord par `/workflows/create/validation`) ; schéma de workflow (défaut `jira`, Anomalie → H-17), schéma de types, écran « DEMO : écran des tickets » (onglet « Général » + champs), schéma d'écrans, schéma d'écrans par type ; projet `DEMO` company-managed (`POST /project` avec ces schémas, sans gabarit). Pièges : `GET /field` ne liste pas un champ hors de tout projet (chercher par `GET /field/search`) ; un champ absent de l'écran ne peut pas être posé à la création. Pas de procédure manuelle de repli nécessaire.

**Requêtes validées par le spike** (noms exacts à reprendre ; recherche par nom avant chaque création ; scripts de sonde, à lire sans jamais les exécuter : `C:/Users/UTILIS~1/AppData/Local/Temp/claude/C--Users-Utilisateur-Documents-GitHub-usine-migration-jira-demo/1b7b8e7a-86ed-4062-b3e4-c2360f2ca955/scratchpad/story-1-6/sonde_creation.py` et `sonde_projet.py`) :
- types : `GET /issuetype` (types globaux = sans clé `scope`) ; `POST /issuetype {name, description, type: "standard"}` ; noms = clés de `config.types_tickets`.
- champs : `GET /field/search?type=custom&query=<nom>` (pagination `startAt`/`maxResults`/`isLast`, `values`) ; `POST /field {name, description, type: "com.atlassian.jira.plugin.system.customfieldtypes:select", searcherKey: "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher"}` → `id` ; noms : Entité, Vague, Domaine, Gravité, Phase, Statut du test, Statut de certification ; `GET /field/{id}/context` → `values[0].id` ; `GET …/context/{ctx}/option` (paginé) ; `POST …/option {options: [{value, disabled: false}]}`. Options : noms Jira de `config.valeurs` (domaines fermés), valeurs du Journal (Entité, Vague, Domaine).
- workflow : `GET /workflows/search?queryString=<nom>` ; `GET /statuses/search` (paginé) pour réutiliser l'`id` d'un statut de même nom ; `POST /workflows/create {scope: {type: GLOBAL}, statuses: [{statusReference: <uuid5>, name, statusCategory: TODO|IN_PROGRESS|DONE, id?}], workflows: [{name: "DEMO : workflow des Anomalies", description, statuses: [{statusReference, properties: {}}], transitions: [{id: "1", name: "Créer", type: "INITIAL", toStatusReference: <Nouvelle>, links: []}, {id, name: <statut d'arrivée>, type: "DIRECTED", toStatusReference, links: [{fromStatusReference}]}…]}]}` ; nouvelle = TODO, fermee/rejetee = DONE, autres IN_PROGRESS.
- schémas : `GET /workflowscheme` (paginé) puis `POST /workflowscheme {name: "DEMO : schéma de workflow", description, defaultWorkflow: "jira", issueTypeMappings: {<id Anomalie>: <workflow>}}` ; `GET /issuetypescheme` puis `POST /issuetypescheme {name: "DEMO : types de tickets", description, defaultIssueTypeId, issueTypeIds}` → `issueTypeSchemeId` ; `GET /screens?queryString=` puis `POST /screens {name: "DEMO : écran des tickets", description}`, `GET /screens/{id}/tabs` (créer un onglet si vide), `GET …/tabs/{tab}/fields`, `POST …/tabs/{tab}/fields {fieldId}` pour summary, description, issuetype et les 7 champs ; `POST /screenscheme {name: "DEMO : schéma d'écrans", description, screens: {default: <écran>}}` ; `POST /issuetypescreenscheme {name: "DEMO : écrans par type", description, issueTypeMappings: [{issueTypeId: "default", screenSchemeId}]}` → `id`.
- projet : `GET /project/search?keys=<clé>` ; `GET /myself` → `accountId` ; `POST /project {key, name: "DEMO - Banque Exemple, migration SI cœur", description, projectTypeKey: "software", leadAccountId, assigneeType: "UNASSIGNED", issueTypeScheme, issueTypeScreenScheme, workflowScheme}` (identifiants entiers).
- contrôle : `GET /issue/createmeta/{clé}/issuetypes` (`issueTypes`) puis `GET /issue/createmeta/{clé}/issuetypes/{id}` (`fields[].fieldId`).
- tickets : `POST /search/approximate-count {jql}` → `count` ; `POST /issue {fields: {project: {key}, issuetype: {id}, summary, description: <ADF>, <champ>: {value}}}` → `key` ; `GET /issue/{clé}/transitions` → `transitions[].{id, to.name}` ; `POST /issue/{clé}/transitions {transition: {id}}` ; `GET /serverInfo` → `serverTime`. Tous les chemins sous `/rest/api/3`.
- ADF : `{type: "doc", version: 1, content: [{type: "paragraph", content: [{type: "text", text: ligne}]}]}`, un paragraphe par ligne, paragraphe vide sans nœud texte.

**Environnement de développement** : le dépôt de travail est le worktree `C:/Users/Utilisateur/Documents/GitHub/usine-lanes/lane-1-donnees` (branche `lane/1-donnees`) : tous les chemins de cette spec s'y résolvent, toutes les commandes s'y lancent (`cd` d'abord), rien n'est écrit ailleurs (surtout pas dans `usine-migration-jira-demo`). Pas de `.env` dans le worktree, aucun appel réseau ; l'injection réelle est lancée après intégration, depuis `main`, hors de cette implémentation. Ne pas modifier `sprint-status.yaml` ni `journal-run-autonome.md` ; ne pas commiter (le parent commite).

**Statuts des Cas de test et Certifications** : workflow `jira` par défaut, sans objet pour le Vocabulaire canonique (la conversion L2 ignore `statut` hors Anomalies) ; leur statut métier est un champ.

**Champs `champs` de `config/jira.yaml`** : les identifiants réels (10043-10049) diffèrent des identifiants fictifs que les fixtures L2 figent ; l'injecteur trouve ses champs par nom et écrit les identifiants dans `donnees/injection/site_jira.json`. Aligner `config/jira.yaml` (et les fixtures L2) avant `usine rapport` avec `JIRA_TOKEN_LECTURE` : File humaine.

**Fin d'injection** : `max(horloge locale, serverTime)` lus après la dernière écriture, pour que la coupure stricte de la Source composite ne reprenne aucune écriture de l'injecteur malgré un décalage d'horloge.

**Fichiers hors lane** : `config/jira.yaml` (L2 : URL du site réel, demandée par Anaël), `tests/unit/contrats/test_config.py` (main : l'URL livrée change).

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout passe.
- `uv run python .github/scripts/controle_lanes.py --branche lane/1-donnees --base main` -- expected: seuls les fichiers hors lane consignés.

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 39 findings — high 0, medium 9, low 21, false 4, maybe-false 5
- findings:
  - `[medium]` `patch` (verification-gap) Limitation de la préparation du site (`_ClientLimite`) non vérifiée — ajouté `test_limiteur_couvre_preparation_et_injection` (une attente par requête, deux phases).
  - `[low]` `patch` (verification-gap) Chemin nominal de `usine donnees injecter` et transmission de `--debit` non testés — ajouté `test_commande_injecter_transmet_le_debit_et_resume`.
  - `[false]` `reject` (verification-gap) `ecarts_champs` peut lever `KeyError` — `ConfigJira` valide que chaque `Champ` a un identifiant (`contrats/config.py:228`).
  - `[medium]` `defer` (blind) `champs` de `config/jira.yaml` fictifs alors que l'URL est réelle — exclu par l'intention (Never), File humaine.
  - `[medium]` `defer` (blind) `controler` ne vérifie pas la liaison Anomalie → H-17 d'un schéma existant.
  - `[maybe-false]` `defer` (blind) Champs obligatoires supplémentaires non détectés — l'injection réelle tranchera.
  - `[medium]` `defer` (blind) Garde « projet peuplé » : compte approximatif, types filtrés, après préparation — Story 1.7.
  - `[low]` `defer` (blind) État partiel sans statut atteint par ticket — reprise = Story 1.7.
  - `[low]` `reject` (blind) Écriture du manifeste hors `try` — échec disque improbable, correction non triviale.
  - `[low]` `reject` (blind) La CLI ne nomme pas l'état partiel ; état partiel antérieur ignoré — fichier écrit à côté du manifeste, message chiffré.
  - `[low]` `reject` (blind) Chemins relatifs au répertoire courant — convention des autres commandes `usine`.
  - `[low]` `patch` (blind) Exemption import-linter trop large (`usine.*.*.cli`) — remplacée par `usine.generateur.injecteur.cli`.
  - `[low]` `patch` (blind) Chemins non testés (succès CLI, limiteur de préparation) — mêmes tests ajoutés ; `_pages` et `serverTime` exotiques rejetés (format Jira documenté).
  - `[maybe-false]` `defer` (blind) Contexte d'options non applicable à DEMO, type de champ, catégorie de statut réutilisé — dépend du site réel.
  - `[low]` `reject` (blind) Tests dépendants de l'URL réelle — URL demandée par Anaël.
  - `[low]` `reject` (blind) Champs d'écran non comptés dans `crees` — affichage seulement.
  - `[medium]` `patch` (edge) Exception non `UsineErreur` après créations : aucun état partiel — `injecter` attrape `Exception` ; test `test_erreur_inattendue_a_mi_parcours_garde_l_etat_partiel`.
  - `[false]` `reject` (edge) Valeur de domaine fermé absente de `noms` → KeyError — `ConfigJira` impose la correspondance de chaque valeur canonique.
  - `[false]` `reject` (edge) Statut d'Anomalie hors `StatutAnomalie` — Journal validé par les contrats.
  - `[maybe-false]` `defer` (edge) `POST /issue` en échec après création réelle — reprise Story 1.7.
  - `[medium]` `defer` (edge) Compte approximatif en retard d'index — même entrée Story 1.7.
  - `[low]` `defer` (edge) Projet contenant d'autres types accepté — même entrée.
  - `[medium]` `defer` (edge) Workflow/schéma/projet trouvés par nom sans contrôle H-17 — même entrée que `controler`.
  - `[low]` `reject` (edge) Écran créé sans champs après un run interrompu — `controler` le signale par nom.
  - `[low]` `reject` (edge) Option existante désactivée — l'injecteur n'en désactive aucune.
  - `[maybe-false]` `defer` (edge) Contexte limité à d'autres projets — même entrée que les contextes.
  - `[maybe-false]` `defer` (edge) Champ obligatoire supplémentaire dans `createmeta` — même entrée.
  - `[low]` `reject` (edge) Valeur libre vide ou trop longue — le générateur produit des libellés courts.
  - `[low]` `reject` (edge) Pagination infinie si `startAt` ignoré — comportement non documenté.
  - `[false]` `reject` (edge) Course sur le manifeste — un seul opérateur, run manuel.
  - `[low]` `reject` (edge) État partiel périmé à côté d'un nouveau manifeste — le manifeste fait foi.
  - `[low]` `reject` (edge) Objets d'une préparation échouée non consignés — préparation idempotente par nom.
  - `[medium]` `defer` (edge, claim) Refus du projet peuplé incomplet — même entrée Story 1.7.
  - `[medium]` `defer` (edge, claim) Workflow existant accepté par nom — même entrée que `controler`.
  - `[low]` `defer` (intent) API réelle non éprouvée par les tests — injection réelle après intégration.
  - `[low]` `reject` (intent) « Jamais modifié » vérifié au niveau requête — aucune requête ne vise KAN ni ne modifie un objet trouvé.
  - `[low]` `reject` (intent) Refus après préparation — la matrice exige « aucun ticket créé », respecté.
  - `[low]` `reject` (intent) Changements hors injecteur — nécessaires ; exemption resserrée.
  - `[low]` `reject` (intent) Choix d'interprétation mineurs — cohérents avec le générateur.

## Auto Run Result

**Statut : done** (reprise après coupure de quota ; implémentation de la tentative interrompue vérifiée complète ; revue unique, mode économique).

**Résumé :** injecteur `generateur/injecteur` (plan pur, préparation idempotente du site par nom, injection ordonnée avec transitions H-17, manifeste, état partiel), commande `usine donnees injecter`, URL réelle du site dans `config/jira.yaml`.

**Fichiers :** `src/usine/generateur/injecteur/` (injecteur) ; `src/usine/generateur/cli.py` (commande) ; `config/jira.yaml`, `tests/unit/contrats/test_config.py`, `tests/unit/rendu/test_excel.py` (URL réelle) ; `tests/unit/adaptateurs/jira_cloud/test_garde.py` (noms Jira autorisés à l'injecteur) ; `pyproject.toml` (exemption import-linter de `usine.generateur.injecteur.cli`) ; `tests/unit/generateur/injecteur/` (faux Jira, tests).

**Revue :** patchs : 2 medium, 1 low (plus un constat low couvert par les mêmes tests) ; 6 entrées différées ; rejets motivés ci-dessus.

**Revue de suivi recommandée : false** -- 0 high et 2 medium patchés, tous deux vérifiés par des tests ajoutés ; seuil de 2 medium atteint, mais aucun risque non vérifié ne peut être nommé, donc false.

**Vérification :** ruff, ruff format, mypy, lint-imports (13 contrats), pytest (1910 passed, 1 skipped) ; `controle_lanes.py` : tous les fichiers dans la lane.

**Risques résiduels :** comportement réel de Jira (createmeta, contextes, champs obligatoires) éprouvé seulement par l'injection réelle ; identifiants `champs` à aligner (File humaine).
