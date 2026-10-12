---
title: 'Story 2.7 : Recette en direct sur Jira Cloud'
type: 'feature'
created: '2026-10-12'
baseline_revision: '0a4814d922de1b498e2d7180debecc070f43fbe8'
status: 'in-progress'
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

## Design Notes

- **Fixture séparée** (`direct_*`) : les fixtures `source_*` encodent des cas construits (troncature, item hors type) dont dépendent les tests ; la fixture directe prouve seulement que le vrai format de `DEMO` se convertit.
- **Transition restaurée** : laisser `DEMO-1356` modifié décalerait les Scénarios de démo calés par la Story 1.8 ; la restauration ajoute un second événement de changelog, l'état final redevient celui du Journal.

## Verification

**Commands:**
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports`, `uv run pytest -q` -- verts.
- depuis W, `USINE_RACINE_RECETTE=<M> uv run pytest -m reseau tests/unit/adaptateurs/composite/test_recette_direct.py` -- AC1 vert (AC2 avec `USINE_RECETTE_TRANSITION`).
- `gitleaks dir tests/fixtures` puis `gitleaks git` -- aucune fuite.
