---
title: 'Story 2.7 : Recette en direct sur Jira Cloud'
type: 'feature'
created: '2026-10-12'
baseline_revision: '0a4814d922de1b498e2d7180debecc070f43fbe8'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** La Source composite (2.6) n'a été éprouvée que sur doublures : rien ne prouve que deux extractions successives sur le vrai projet `DEMO` n'ajoutent rien, qu'une transition faite à la main dans Jira apparaît au Passage suivant, ni que des fixtures rafraîchies depuis `DEMO` sont sans secret. Il n'existe ni test `reseau` de recette, ni outil de rafraîchissement des fixtures.

**Approach:** Livrer dans la lane un outil de rafraîchissement anonymisé des fixtures Cloud (`usine extraction rafraichir-fixtures`), une suite de recette `@pytest.mark.reseau` (deux extractions, transition visible au Passage publié) dont la docstring porte la procédure, puis jouer la recette en direct depuis M sur `DEMO` (une transition sur un seul ticket de l'Entité A, restaurée ensuite) et consigner les mesures.

## Boundaries & Constraints

**Always:** lecture par `ClientJiraLecture` seul dans l'outil et les tests ; tests `reseau` sautés (pas en échec) sans racine configurée, sans secret de lecture ou sans manifeste d'injection, et racine lue dans `USINE_RACINE_RECETTE` (défaut : répertoire courant) ; recette AC1 sur un entrepôt temporaire, jamais celui de la racine ; Passage de l'AC2 sur une copie temporaire de la racine (`config/`, `gabarits/`, Journal, manifeste d'injection), secrets passés par l'environnement du test ; fixtures écrites anonymisées : hôte du site → `https://jira.example.invalid`, tout objet utilisateur (porteur d'`accountId`) → `{"accountId": "compte-fictif", "displayName": "Compte fictif"}`, `emailAddress` supprimé, `nextPageToken` retiré (page finale) ; contrôle avant écriture : présence de l'hôte réel, d'une adresse e-mail ou d'un préfixe de jeton Atlassian (`ATATT`) → `UsineErreur` et aucun fichier écrit ; modification en direct limitée à une transition d'un seul ticket `DEMO` de l'Entité A, faite par le client d'écriture puis restaurée, consignée (ticket, champ, avant/après) ; tests sans réseau pour le reste ; mypy strict, ruff, import-linter verts.

**Never:** modifier `src/usine/contrats/`, `src/usine/ports/`, `composition.py`, `pyproject.toml` ; lire ou afficher `.env` ou un secret ; toucher au projet `KAN` ou supprimer quoi que ce soit sur le site ; versionner une donnée Jira non fictive (compte, e-mail, URL du site) ; écraser les fixtures existantes `source_*`, `recherche_*`, `bulkfetch_*`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Anonymisation | page de recherche avec hôte réel, `author` complet, `emailAddress`, `nextPageToken` | hôte remplacé, utilisateurs fictifs, pas d'e-mail ni de jeton de page | — |
| Résidu sensible | texte encore porteur de l'hôte réel, d'un e-mail ou de `ATATT…` | rien n'est écrit | `UsineErreur` nommant le motif, jamais la valeur |
| Rafraîchissement | client de lecture doublé, `nb_tickets = 3` | une requête POST `search/jql` (`maxResults` 3, `expand` changelog), fichier `direct_recherche_page_1.json` écrit | sortie absente → créée |
| Fixture versionnée | `tests/fixtures/jira_cloud/direct_recherche_page_1.json` + `config/jira.yaml` | chaque ticket se convertit en `Evenement` canoniques (création + champs initiaux) | — |
| Recette sans racine | ni `config/jira.yaml`, ni secret, ni manifeste | tests `reseau` sautés avec motif | — |

</intent-contract>

## Code Map

- `src/usine/adaptateurs/jira_cloud/source.py` -- `CHEMIN_RECHERCHE`, `requete_jql(config)`, `champs_demandes(config)`, `SourceJiraCloud` : réutilisés par l'outil et la recette.
- `src/usine/adaptateurs/jira_cloud/conversion.py:convertir_ticket(ticket, historiques, config, source)` -- conversion de la fixture versionnée.
- `src/usine/adaptateurs/jira_http/clients.py` -- `construire_client_lecture(config, email=, jeton_lecture=, pat=, transport_http=)`, `ClientJiraLecture.requete(...)`, `construire_client_ecriture` (transition de recette, script hors dépôt seulement).
- `src/usine/adaptateurs/entrepot_duckdb/extraction.py:extraire(source, entrepot, marge, horloge, aligner)` -- `ResultatExtraction.ajouts`, `.alignements` ; `EntrepotDuckDB(chemin)`.
- `src/usine/adaptateurs/composite/alignements.py:DetecteurAlignements(journal)` ; `adaptateurs/journal:SourceJournal(chemin, manifeste)`, `charger_manifeste`, `CHEMIN_MANIFESTE_INJECTION`.
- `src/usine/adaptateurs/cli.py` -- sous-application `usine extraction` (vide) ; un module `cli` peut importer `usine.config` (import-linter : `usine.*.cli -> usine.**` ignoré).
- `src/usine/config/secrets.py:charger_secrets(racine)` -- environnement + `racine/.env` ; `jira_email`, `jira_token_lecture`, `usine_mode_repli`. `usine.config` : `charger_yaml(chemin, ConfigJira)`.
- `src/usine/composition.py:lancer_rapport(racine, date_arrete)`, `CHEMIN_GABARIT` -- Passage de l'AC2 (lecture seule).
- `tests/unit/adaptateurs/jira_http/outils.py` -- `config_jira`, `fixture` ; `tests/unit/adaptateurs/jira_cloud/outils.py` -- modèle de serveur `httpx.MockTransport`.
- `tests/fixtures/jira_cloud/` -- fixtures existantes (hôte `jira.example.invalid`) à ne pas écraser.
- Données de M (non versionnées) : entrepôt avant recette = 1 lot de 39 159 événements `jira_cloud` (3 384 créations), repère 2026-10-12T16:53:05Z, 0 alignement ; manifeste d'injection : fin 2026-10-12T16:19:41.435Z ; Passage composite `20261012T165305Z-a078d7` (`nb_tickets` 3 384, `nb_alignements` 0).

## Tasks & Acceptance

**Execution:**
- `src/usine/adaptateurs/jira_cloud/fixtures.py` (nouveau) -- `anonymiser(objet, url_site)`, `verifier_sans_secret(texte, url_site)`, `rafraichir_fixtures(client, config, sortie, nb_tickets)` ; export dans `jira_cloud/__init__.py` -- AC3.
- `src/usine/adaptateurs/cli.py` -- commande `rafraichir-fixtures` (`--racine`, `--sortie` défaut `tests/fixtures/jira_cloud`, `--nb-tickets` défaut 3), `UsineErreur` → message et code 1 -- AC3 réutilisable.
- `tests/unit/adaptateurs/jira_cloud/test_fixtures.py` -- matrice I/O (anonymisation, résidu, rafraîchissement doublé, conversion de la fixture versionnée, commande CLI).
- `tests/unit/adaptateurs/composite/test_recette_direct.py` (nouveau, `reseau`) -- AC1 et AC2 ; docstring = procédure de recette.
- `tests/fixtures/jira_cloud/direct_recherche_page_1.json` -- produite uniquement par la commande contre `DEMO`, après l'implémentation, par l'orchestrateur du run (jamais écrite à la main) ; le test de conversion la lit telle quelle et échoue tant qu'elle manque.
- Recette en direct depuis M (transition par un script du scratchpad, rafraîchissement, gitleaks) : jouée par l'orchestrateur du run après l'implémentation, pas par l'implémenteur, qui n'appelle jamais le réseau ; mesures dans l'Auto Run Result.

**Acceptance Criteria:**
- Given le projet `DEMO` injecté et `JIRA_TOKEN_LECTURE` défini, when `uv run pytest -m reseau tests/unit/adaptateurs/composite/test_recette_direct.py` s'exécute avec `USINE_RACINE_RECETTE` = M, then la première extraction stocke au moins 3 384 créations et la seconde n'ajoute aucun événement ni alignement.
- Given une transition faite à la main sur un ticket de l'Entité A après l'injection, when `usine rapport --date-arrete <jour>` s'exécute depuis M, then `tickets_etats.parquet` du Passage publié porte le nouveau statut de ce ticket à ce jour, `source` = `composite`.
- Given les fixtures rafraîchies depuis `DEMO`, when gitleaks analyse le dépôt, then aucun secret n'est signalé.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 31 findings — high 0, medium 0, low 23, false 8, maybe-false 0
- findings:
  - `[low]` `[patch]` (verification-gap) règle « champ utilisateur » de `_item_utilisateur` sans test propre — test paramétré `assignee`/`reporter`/`creator` sans `tmp*AccountId`.
  - `[low]` `[patch]` (verification-gap, autre) champ utilisateur personnalisé sans `tmp*AccountId` non anonymisé — `DEMO` n'en a pas ; filet ajouté : `verifier_sans_secret` refuse tout identifiant de compte `712020:<uuid>` (groupe P1).
  - `[false]` `[reject]` (intent) AC1/AC2 vérifiés seulement par des tests `reseau` hors CI — la recette a été jouée sur `DEMO`, mesures dans l'Auto Run Result ; la CI exclut le réseau par décision d'Epic.
  - `[false]` `[reject]` (intent) gitleaks absent du diff — exécuté (8.30.1) sur fixtures, arbre et historique ; `gitleaks git` tourne déjà en CI.
  - `[low]` `[patch]` (blind) mentions ADF non anonymisées — branche `mention` → compte fictif, test ajouté (P1).
  - `[low]` `[patch]` (blind) item de champ utilisateur personnalisé — même groupe P1 (détection d'identifiant de compte).
  - `[low]` `[patch]` (blind) filet sans motif d'identifiant de compte — P1, cas ajouté au test paramétré.
  - `[low]` `[reject]` (blind) IBAN et identifiant client dans une description — données fictives par construction (Story 1.4, identifiants sensibles fictifs) ; `DEMO` n'a que du fictif.
  - `[low]` `[reject]` (blind) changelog tronqué non complété dans la fixture — la fixture prouve le format, pas l'exhaustivité ; `convertir_ticket` reste testé sur les fixtures construites de troncature.
  - `[low]` `[reject]` (blind) `isLast` forcé — une page unique documentée comme telle (docstring) ; aucun consommateur ne pagine sur cette fixture.
  - `[low]` `[reject]` (blind) écriture non atomique — fichier versionné, restaurable par git ; garde sans défaut constaté.
  - `[low]` `[reject]` (blind) remplacement d'hôte non ancré — seules des réponses de ce site passent ; aucun hôte plus long contenant le sien.
  - `[low]` `[patch]` (blind) recette sans `JIRA_EMAIL` en échec au lieu de sautée — saut ajouté (P2).
  - `[low]` `[reject]` (blind) AC2 ne prouve pas le changement — la recette consigne l'avant (`en_correction`, Passage `20261012T165914Z-39d351`) et l'après ; le test est l'outil du jour de recette.
  - `[low]` `[reject]` (blind) jour en UTC — l'écart n'existe qu'entre minuit et 2 h, hors horaires de recette ; le test saute ou échoue bruyamment.
  - `[low]` `[reject]` (blind) `--sortie` relatif au répertoire courant — la commande affiche le chemin écrit ; la procédure la lance depuis le dépôt.
  - `[false]` `[reject]` (blind) gitleaks manuel — `gitleaks git` est une étape de la CI (`ci.yml`) et couvre toute fixture commitée.
  - `[false]` `[reject]` (blind) contrôle d'hôte faible — `config/jira.yaml` versionné porte l'URL réelle de `DEMO`, le contrôle est donc significatif.
  - `[low]` `[reject]` (blind) tests `reseau` sous `tests/unit` — imposé par le périmètre de lane (tests miroirs) ; l'échappement ne vaut que pour le marqueur `reseau`, exclu par défaut.
  - `[low]` `[reject]` (blind) branches non testées (`from` non nul, `_hote` illisible, `OSError` CLI, page sans `isLast`, clés porteuses de l'hôte) — chemins simples, sans défaut constaté ; `from` non nul couvert par le nouveau test P1.
  - `[low]` `[patch]` (edge) item utilisateur personnalisé — groupe P1.
  - `[low]` `[patch]` (edge) mention ADF — groupe P1.
  - `[low]` `[patch]` (edge) filet sans identifiant de compte — groupe P1.
  - `[low]` `[patch]` (edge) recherche vide écrase la fixture — refus `UsineErreur` « sans ticket », rien écrit, test ajouté (P3).
  - `[low]` `[reject]` (edge) écriture non atomique — même motif que la ligne blind.
  - `[low]` `[reject]` (edge) changelog tronqué — même motif que la ligne blind.
  - `[low]` `[reject]` (edge) faux positif e-mail (`icon@2x.png` correspond au motif) — le rafraîchissement échoue alors bruyamment en nommant le motif, rien d'erroné n'est écrit ; la fixture réelle de `DEMO` passe.
  - `[false]` `[reject]` (edge) `nb_tickets` au-delà du plafond — Jira rend moins de tickets, la fixture reste valide ; rien de faux n'est écrit.
  - `[false]` `[reject]` (edge) `--sortie` relatif — chemin affiché ; voir ligne blind.
  - `[false]` `[reject]` (edge) `JIRA_EMAIL` absent — doublon de la ligne blind, patché (P2).
  - `[low]` `[reject]` (edge) jour en UTC entre minuit et 2 h (Paris) — même motif que la ligne blind.
  - `[false]` `[reject]` (edge) AC2 jugé sur une copie — la recette a aussi lancé `usine rapport` depuis M (Passages `20261012T165955Z-7afa10` puis `20261012T170622Z-f87429`), Entité ENT-A lue dans `tickets_etats`.

## Design Notes

- **Fixture séparée** (`direct_*`) : les fixtures `source_*` encodent des cas construits (troncature, item hors type) dont dépendent les tests ; la fixture directe prouve seulement que le vrai format de `DEMO` se convertit.
- **Transition restaurée** : laisser `DEMO-1356` modifié décalerait les Scénarios de démo calés par la Story 1.8 ; la restauration ajoute un second événement de changelog, l'état final redevient celui du Journal.

## Verification

**Commands:**
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports`, `uv run pytest -q` -- verts.
- depuis W, `USINE_RACINE_RECETTE=<M> uv run pytest -m reseau tests/unit/adaptateurs/composite/test_recette_direct.py` -- AC1 vert (AC2 avec `USINE_RECETTE_TRANSITION`).
- `gitleaks dir tests/fixtures` puis `gitleaks git` -- aucune fuite.

## Auto Run Result

Status: done

- **Changement** : outil `usine extraction rafraichir-fixtures` (une page `search/jql` lue par `ClientJiraLecture`, anonymisée : hôte, comptes, mentions ADF, e-mails, jeton de page ; contrôle de résidus avant écriture), fixture directe `direct_recherche_page_1.json` rafraîchie depuis `DEMO`, et suite de recette `reseau` (AC1 deux extractions, AC2 transition au Passage publié) dont la docstring porte la procédure.
- **Fichiers** :
  - `src/usine/adaptateurs/jira_cloud/fixtures.py` (nouveau) et `jira_cloud/__init__.py` -- anonymisation, contrôle, rafraîchissement.
  - `src/usine/adaptateurs/cli.py` -- commande `rafraichir-fixtures`.
  - `tests/fixtures/jira_cloud/direct_recherche_page_1.json` -- 3 tickets de `DEMO` (DEMO-1 à 3), anonymisés, contenu fictif.
  - `tests/unit/adaptateurs/jira_cloud/test_fixtures.py` -- matrice I/O et fixture directe.
  - `tests/unit/adaptateurs/composite/test_recette_direct.py` (`reseau`) et `composite/conftest.py` -- coupure réseau levée pour les seuls tests `reseau`.
- **Recette en direct sur `https://anaelyahi.atlassian.net`, projet `DEMO`, 2026-10-12 (depuis M)** :
  - **L'extraction interroge réellement le site** : entrepôt de M avant recette = lot 1 de 39 159 événements `jira_cloud` (3 384 créations, 26 782 champs initiaux, 8 993 transitions), repère 16:53:05Z, 0 alignement ; Passage composite `20261012T165305Z-a078d7` (Story 1.7). Un Passage à 16:59:14Z (`20261012T165914Z-39d351`, date d'arrêté 2026-10-12) n'ajoute aucun lot : incrémental sans modification = 0 événement.
  - **AC1** : `pytest -m reseau` (entrepôt temporaire) : 1re extraction 39 160 événements (3 384 créations, 0 alignement), 2e extraction 0 événement, 0 alignement. Vert.
  - **Modification en direct** (client d'écriture de l'injecteur, script hors dépôt) : ticket `DEMO-1356` (Anomalie, ENT-A, mineure), champ `status` : « En correction » → « À retester » (transition 41, 16:59:48Z), puis restauré « À retester » → « En correction » (transition 61, 17:06:19Z). Aucun autre ticket ni projet touché, rien supprimé.
  - **AC2** : `usine rapport --date-arrete 2026-10-12` depuis M → Passage `20261012T165955Z-7afa10`, `source` composite, `nb_alignements` 0, `tickets_etats` : DEMO-1356 = `a_retester` au 2026-10-12 (avant : `en_correction`) ; entrepôt : lot 3, 1 événement `22408-1` transition `statut` `en_correction` → `a_retester`. Test `reseau` AC2 (`USINE_RECETTE_TRANSITION=DEMO-1356=a_retester`) vert, Passage `20261012T170525Z-ef7e76`. Après restauration, Passage `20261012T170622Z-f87429` : DEMO-1356 = `en_correction`, lot 4 d'un événement, 0 alignement.
  - **AC3** : gitleaks 8.30.1 (binaire officiel) : `dir tests/fixtures` et `git` sans fuite ; `dir .` ne signale que `.venv/` (non versionné).
- **Revue** : 31 constats, aucun high ni medium. Patchés (low) : P1 anonymisation (mentions ADF, motif d'identifiant de compte au contrôle, test de la règle des champs utilisateur), P2 recette sautée sans `JIRA_EMAIL`, P3 recherche vide refusée sans écriture. Rejetés : motifs au Review Triage Log. Aucun différé.
- **Relecture de suivi recommandée** : non (aucun patch medium ou high).
- **Vérification** : `ruff check`, `ruff format --check`, `mypy` (281 fichiers), `lint-imports` (13 contrats) verts ; `pytest -q` 2 310 réussis, 1 ignoré ; tests `reseau` sautés avec motif sur une racine vide.
- **Risques résiduels** : `config/jira.yaml` versionné (depuis la 1.6) porte l'URL réelle du site, ce qui n'est pas un secret. L'anonymisation ne traite pas les noms écrits en texte libre, sans objet sur `DEMO`, dont le texte est fictif. Le test AC2 ne vérifie que l'état final : l'état d'avant se consigne à la main, comme ici.
