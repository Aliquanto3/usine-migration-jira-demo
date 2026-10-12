# Epic 2 Context: Extraction fiable de l'historique (L2 Extraction)

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Donner au Pilote l'historique complet des tickets (Anomalies, Cas de test, Certifications) depuis Jira Cloud, Jira Data Center ou le seul Journal d'événements. L'extraction est incrémentale et en lecture seule, et Jira fait foi sur l'état courant. Tout le calcul en aval (Instantanés, KPI, Météo, Prévision) part d'un flux unique d'`Evenement` canoniques. Il doit donc donner le même résultat quelle que soit la source. Il doit aussi absorber les mises à jour faites en direct dans Jira pendant la démo, sans jamais écrire dans Jira.

## Stories

- Story 2.1 : Transport Jira commun et client de lecture à liste blanche
- Story 2.2 : Adaptateur Jira Cloud v3 et vocabulaire canonique
- Story 2.3 : Entrepôt DuckDB et extraction incrémentale
- Story 2.4 : Adaptateur Jira Data Center v2 et sélection par configuration
- Story 2.5 : Source Journal à l'échelle et correspondance des clés
- Story 2.6 : Source composite et cohérence à la Date d'injection
- Story 2.7 : Recette en direct sur Jira Cloud

## Requirements & Constraints

- **Incrémental (Cloud v3)** : on n'extrait que les tickets modifiés depuis le dernier Passage réussi, changelog compris. Un deuxième Passage sans modification dans Jira n'ajoute ni ne modifie rien. Une coupure en cours d'extraction n'avance pas le repère.
- **Data Center v2** : l'adaptateur est choisi en configuration. Il passe exactement les mêmes tests que Cloud, sur des fixtures enregistrées, sans aucun vrai DC.
- **Journal seul** : le Journal peut servir de seule source, avec le même modèle de sortie. Toute Date d'arrêté de l'historique doit se calculer sans réseau.
- **Source composite** : elle prend le Journal jusqu'à la Date d'injection, puis le changelog Jira. Jira fait foi. À la Date d'injection, Instantané(Journal) = Instantané(état Jira) (test de cohérence). Une transition faite à la main dans Jira apparaît au Passage suivant.
- **Lecture seule** : l'extraction n'émet aucune requête d'écriture vers Jira, et un test le vérifie.
- **Performance** : le Rapport quotidien Palier 1 doit tenir en moins de 5 minutes, extraction incrémentale comprise.
- **Tests** : aucun appel Jira réel dans les tests unitaires, qui tournent sur fixtures. Les tests en direct portent le marqueur `@pytest.mark.reseau` et sont exclus de la CI. Les fixtures rafraîchies ne contiennent aucun secret (gitleaks vert).
- **Portabilité** : le cœur ne dépend d'aucun service propriétaire autre que Jira. Les différences d'environnement passent par la configuration.
- **Lisibilité** : chaque clé de configuration est commentée en français. Les erreurs nomment le fichier, la clé et la valeur.

## Technical Decisions

- **Événement canonique unique** : toutes les sources émettent le contrat `Evenement` (`contrats.evenements`) : `id_evenement`, `cle_ticket`, `type_ticket`, `horodatage` UTC, `nature` ∈ {creation, transition, modification_champ, alignement}, `champ`, `de`, `vers`, `source`. Une création est suivie, au même horodatage, d'un `modification_champ` par attribut initial (titre et description compris). On dédoublonne sur `id_evenement`.
- **Identifiants déterministes** : `J-<rang>` (Journal), `<id changelog>-<rang item>` (changelog Jira), `C-<id ticket>` (création Jira), `A-<cle>-<champ>-<sha8(vers)>` (alignement).
- **Vocabulaire canonique** : l'énumération `Champ` et ses domaines de valeurs (statuts H-17 : Nouvelle, En analyse, En correction, À retester, Fermée, Rejetée ; `Gravite` ; codes d'Entité ; Phases ; Domaines) vivent dans `contrats.tickets`. La correspondance Jira → canonique (champs personnalisés, noms de statuts) est une table de `config/jira.yaml`, appliquée **uniquement dans les adaptateurs**. `cause_racine` n'est jamais un `Champ`, et aucun `Evenement` ne porte la vérité terrain.
- **Transport et lecture seule** : `adaptateurs/jira_http` est le transport commun. Il gère la pagination Cloud (`nextPageToken`, jeton absent en dernière page, pages courtes tolérées, pas de pagination parallèle) et DC (`startAt`/`maxResults`, plafond serveur, fenêtre de 10 000 résultats à contourner par tranches de dates). Il gère aussi l'authentification Cloud (e-mail + jeton) et DC (PAT en `Bearer`), ainsi que la reprise sur 429 selon `Retry-After`. `ClientJiraLecture` (`JIRA_TOKEN_LECTURE`) refuse avant envoi toute requête hors d'une liste blanche `(méthode, gabarit de chemin)`. Les POST de lecture `search/jql` et `changelog/bulkfetch` y sont autorisés, d'où l'insuffisance d'un filtre « GET seulement ». Le client d'écriture (`JIRA_TOKEN_INJECTION`) n'est construit que par la composition du générateur. `usine rapport` ne lit jamais ce jeton.
- **Changelog Cloud** : seule `/rest/api/3/search/jql` est utilisable, l'ancienne `/search` renvoie 410. Le changelog renvoyé avec la recherche est tronqué, sans plafond documenté. Il faut détecter la troncature et compléter par l'endpoint dédié, par ticket ou `changelog/bulkfetch` avec dédoublonnage.
- **Entrepôt** : `donnees/entrepot.duckdb` stocke les `Evenement` extraits (alignements compris) et le repère d'extraction. Seule l'étape `extraction` l'ouvre, et l'UI jamais. DuckDB stocke et relit sans calcul métier, qui reste en Polars dans `domaine/`. Les événements et le repère sont validés dans une seule transaction, après succès complet. La requête incrémentale est `updated >= repère − marge`, avec la marge dans `config/jira.yaml`. Le verrou exclusif `donnees/.verrou-passage` est pris par `usine rapport`.
- **Source composite et coupure** : la coupure se fait par instants. On prend tout le Journal, puis les seuls événements Jira dont `horodatage > horodatage_fin_injection` (lu dans `donnees/injection/manifeste_injection.json`, `ManifesteInjection`). Les événements de l'intervalle d'injection sont ignorés. `created` et `resolutiondate` ne servent jamais avant cette coupure. La clé canonique en aval est la clé Jira : `correspondance_cles` s'applique à la lecture du Journal.
- **Jira fait foi (H-27)** : si l'état rejoué d'un ticket diffère de son état Jira, l'étape `extraction` persiste une seule fois un `Evenement` `alignement`, horodaté à sa première détection. Le nombre d'alignements remonte au manifeste du Passage. Pour le test FR-49, l'état Jira juste après injection est converti en `alignement`.
- **Contrats d'abord** : on ne touche pas à `contrats/`, `ports/`, `composition.py`, `cli.py` racine, `tests/contrat/` ni `tests/doublures/`. Ils appartiennent à `main` et se modifient par une PR courte dédiée, suivie d'un rebase. C'est notamment le cas du câblage de la sélection d'adaptateur dans `composition.py`. Les ports concernés sont `SourceTickets` et `EntrepotExtraction`. La suite de contrat `SourceTickets` (`tests/contrat/`) s'exécute sur Cloud, DC et Journal, contrôle des domaines de valeurs compris.
- **Périmètre d'écriture de la lane** : `adaptateurs/{jira_http,jira_cloud,jira_dc,journal,composite,entrepot_duckdb,cli}`, `config/jira.yaml`, `tests/fixtures/jira_*` et leurs tests miroirs (`tests/unit/adaptateurs/<nom>` ou test plat `test_<nom>.py`). Ce périmètre est vérifié en CI sur `lane/2-*`. La sous-application typer de la lane est `adaptateurs/cli.py`.
- **Secrets** : ils passent par des variables d'environnement (`JIRA_TOKEN_LECTURE`, `JIRA_DC_PAT`). La configuration est validée par `contrats.config`. Ne jamais lire ni versionner de `.env`.

## Cross-Story Dependencies

- 2.1 est le socle de 2.2 et 2.4. Elle débloque aussi la Story 1.6 (injecteur), qui réutilise `jira_http` pour son client d'écriture.
- 2.2 et 2.4 partagent la suite de contrat `SourceTickets`. Les fixtures DC doivent être équivalentes aux fixtures Cloud.
- 2.3 (entrepôt, repère) précède l'alignement persistant de 2.6. 2.5 et 2.6 dépendent du `ManifesteInjection` produit par L1.
- 2.7 (recette en direct sur `DEMO`) exige la Story 1.7 (réinjection idempotente, clés stables) : L1 est une dépendance de recette de L2.
- En aval, L3 calcule les Instantanés à partir du flux d'`Evenement`, et la recette L5 (Story 5.6) dépend de L2.
