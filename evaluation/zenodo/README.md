# Public Jira Dataset : chargement et conversion en `SerieStock`

Évaluation de la Baseline sur des données Jira réelles (FR-51). Rien ici ne tourne en CI
(AD-20). Le dump et les binaires MongoDB restent **hors de tout dépôt git**, sous
`usine-lanes/externe/` (à côté des worktrees), et `mongod` n'écoute que sur `127.0.0.1`.

- `conversion.py` : fonction pure `convertir_en_series(tickets, depot=…, priorites=…, fin=…)`,
  testée sur un extrait figé fictif (`tests/unit/evaluation/zenodo/`).
- `chargement.py` : lit une collection du dump restauré (pymongo, groupe de dépendances
  `evaluation`) et écrit les `SerieStock` en Parquet.

## Sources officielles

| Élément | Source | Contrôle |
|---|---|---|
| Dataset | Zenodo, record 15719919, DOI `10.5281/zenodo.15719919` (version du 2025-06-23), fichier `2025-06-23 ThePublicJiraDataset.zip` | 5 813 135 238 octets, MD5 `02f85309d966092ea130ca0797aea795` (publié par Zenodo dans `https://zenodo.org/api/records/15719919`) |
| MongoDB Community Server 8.0.32, Windows x64 (zip) | `https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-8.0.32.zip` | SHA-256 `5a0675fdec49b544cd5d374ad50a9a594cf5b3278b5ace658aa51cbb4df17177` (fichier `.sha256` publié à côté du zip) |
| MongoDB Database Tools 100.19.1, Windows x64 (zip) | `https://fastdl.mongodb.org/tools/db/mongodb-database-tools-windows-x86_64-100.19.1.zip` | SHA-256 `527738a0f9ab2d80ea40cb8fc7a68f8e28664a2fd4e3b63626c2d4629aeb7f37` (publié dans `https://downloads.mongodb.org/tools/db/release.json` ; le `.sha256` voisin du zip renvoie 403) |

Citation : Montgomery L, Lüders C, Maalej W. *An Alternative Issue Tracking Dataset of Public
Jira Repositories*. MSR 2022, pp. 73-77. Données sous CC BY 4.0, scripts sous MIT ; les
utilisateurs sont anonymisés (masques UUID4).

## Espace disque

| Élément | Taille |
|---|---|
| Zip du dataset | 5,8 Go |
| Archive `mongodump` qu'il contient (gzip) | 5,9 Go, **lue en flux** (`unzip -p`), jamais extraite |
| Binaires MongoDB (zip + extraction, `.pdb` compris) | ~3 Go |
| Base complète restaurée (16 dépôts) | ~60 Go selon les auteurs |
| Cinq petits dépôts restaurés (voir résultats) | 0,7 Go sur disque |

## Procédure (Git Bash, Windows)

```bash
RACINE=$PWD                # racine du worktree (point de départ)
EXT=../externe            # usine-lanes/externe, hors dépôt
mkdir -p $EXT/zenodo $EXT/mongodb/{telechargements,donnees,journaux}

# 1. Dataset (reprise possible avec -C -) puis contrôle MD5
cd $EXT/zenodo
curl -sSL --retry 5 -C - -o ThePublicJiraDataset.zip \
  "https://zenodo.org/api/records/15719919/files/2025-06-23%20ThePublicJiraDataset.zip/content"
md5sum ThePublicJiraDataset.zip   # 02f85309d966092ea130ca0797aea795

# 2. MongoDB portable et outils : téléchargement, contrôle SHA-256, extraction
cd ../mongodb/telechargements
curl -sSLO https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-8.0.32.zip
curl -sSLO https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-8.0.32.zip.sha256
sha256sum -c mongodb-windows-x86_64-8.0.32.zip.sha256
curl -sSLO https://fastdl.mongodb.org/tools/db/mongodb-database-tools-windows-x86_64-100.19.1.zip
echo "527738a0f9ab2d80ea40cb8fc7a68f8e28664a2fd4e3b63626c2d4629aeb7f37  mongodb-database-tools-windows-x86_64-100.19.1.zip"   | sha256sum -c
cd .. && unzip -q telechargements/mongodb-windows-x86_64-8.0.32.zip \
  && unzip -q telechargements/mongodb-database-tools-windows-x86_64-100.19.1.zip

# 3. mongod sur la boucle locale seulement (en arrière-plan)
M=$PWD/mongodb-win32-x86_64-windows-8.0.32/bin
T=$PWD/mongodb-database-tools-windows-x86_64-100.19.1/bin
$M/mongod.exe --dbpath "$PWD/donnees" --bind_ip 127.0.0.1 --port 27017 \
  --logpath "$PWD/journaux/mongod.log" --wiredTigerCacheSizeGB 2 &

# 4. Restauration sélective, en flux depuis le zip (quelques dépôts)
unzip -p ../zenodo/ThePublicJiraDataset.zip \
    "ThePublicJiraDataset/3. DataDump/mongodump-JiraReposAnon.archive" \
  | $T/mongorestore.exe --uri mongodb://127.0.0.1:27017 --gzip --archive \
      --nsInclude "JiraReposAnon.Hyperledger" --nsInclude "JiraReposAnon.Spring"

# 5. Conversion depuis la racine du worktree (mongod, lancé avec & à l'étape 3, reste
#    attaché à ce shell : le garder ouvert)
cd "$RACINE"
uv run python -m evaluation.zenodo.chargement --uri mongodb://127.0.0.1:27017 \
  --base JiraReposAnon --collection Spring --sortie ../externe/series/Spring.parquet
#   --priorite NOM (répétable) pour un dépôt qui ne nomme pas son niveau maximal
#   Blocker ou Highest ; --fin AAAA-MM-JJ (Jour ouvré) pour borner la série.

# 6. Arrêt propre de mongod (pymongo peut lever `AutoReconnect` : attendu, le serveur
#    coupe la connexion en s'arrêtant)
uv run python -c "from pymongo import MongoClient; \
  MongoClient('mongodb://127.0.0.1:27017').admin.command('shutdown')"
```

Le flux `mongorestore` lit toute l'archive (5,9 Go) même pour un seul dépôt : compter
environ dix minutes. `mongorestore` avertit que l'archive vient de MongoDB 7.0.14 et que la
restauration vers 8.0 n'est pas supportée ; les documents restaurés au spike étaient complets
(comptes conformes aux `rough_issue_count` des auteurs, aucune erreur de conversion). En cas
de doute, utiliser un MongoDB 7.0 portable avec la même procédure.

## Organisation observée du dump

- Archive `3. DataDump/mongodump-JiraReposAnon.archive`, produite par
  `mongodump --db=JiraReposAnon --gzip --archive=…` : **une base `JiraReposAnon`, une
  collection par instance Jira** (16) : Apache, Hyperledger, IntelDAOS, JFrog, Jira,
  JiraEcosystem, MariaDB, Mindville, Mojang, MongoDB, Qt, RedHat, Sakai, SecondLife, Sonatype,
  Spring. Leur taille approximative figure dans `0. DataDefinition/jira_data_sources.json`
  (Apache ~1 015 000 tickets, Mojang ~421 000, RedHat ~353 000 … SecondLife ~2 000).
- Un document = un ticket, forme brute de l'API Jira v2 avec `expand=changelog` :
  `_id`, `id`, `key`, `self`, `expand`, `fields`, `changelog`.
- `fields.created`, `fields.resolutiondate` et `changelog.histories[].created` sont des
  **chaînes** au format Jira `2019-04-13T00:26:29.000+0000` (pas des dates BSON).
- `fields.project` : `{id, key, name, …}` ; `fields.priority` : `{id, name, …}` (priorité
  **courante**, parfois `null`).
- `changelog` : `{startAt, maxResults, total, histories}` ; chaque historique porte
  `created` et `items[]` (`field`, `fieldtype`, `from`, `fromString`, `to`, `toString`).
  Les items `resolution` et `priority` (et, à défaut, `status` avec
  `fields.status.statusCategory.key`) suffisent à rejouer l'état d'un ticket. Quelques
  changelogs sont tronqués (`total` > nombre d'historiques), voir « Limites connues ».
- Les champs utilisateurs (`assignee`, `reporter`, auteurs des historiques) sont masqués
  (`<<|author_name|uuid|>>`).

## Résultats du spike (2026-10-12)

Dépôts restaurés : Hyperledger, IntelDAOS, JFrog, SecondLife, Spring (2,2 Go de données
logiques, 0,7 Go sur disque).

| Dépôt | Tickets | Nom de la priorité maximale (nombre de tickets, priorité courante) | Conversion |
|---|---|---|---|
| Spring | 69 156 | `Blocker` (918) ; puis Critical, Major, Minor, Trivial | 58 séries, 71 181 lignes, 9 s |
| Hyperledger | 28 146 | `Highest` (944) ; puis High, Medium, Low, Lowest | 24 séries, 13 691 lignes, 8 s |
| JFrog | 15 535 | `1 - Blocker` (498) ; puis `2 - Critical` … `6 - Trivial` | `--priorite "1 - Blocker"` : 7 séries |
| IntelDAOS | 9 474 | `P1-Urgent` (1 046) ; puis `P2-High` … `P5-Trivial` | `--priorite P1-Urgent` : 2 séries |
| SecondLife | 1 867 | `Showstopper` (34) ; puis Severe, Major, Minor, Trivial | `--priorite Showstopper` : 2 séries |

Chaque série produite est validée par `SCHEMA_SERIE_STOCK`, dense en Jours ouvrés
consécutifs, avec stock(j) = stock(j−1) + Entrées(j) − Sorties(j) ≥ 0 (contrôlé sur Spring et
Hyperledger). Exemples : `Spring/SPR` (2003-12-11 → 2019-01-07, 319 Entrées, stock maximal
4) ; `Hyperledger/FAB` (2016-08-12 → 2021-08-19, 534 Entrées, stock final 17, maximal 43).

Le défaut `PRIORITES_MAXIMALES = {Blocker, Highest}` couvre les schémas Apache (Blocker) et
Jira par défaut (Highest) ; les instances à schéma propre se convertissent avec `--priorite`.
L'évaluation de la Baseline sur ces séries (Story 4.4) est décrite dans [`RAPPORT.md`](RAPPORT.md).

## Limites connues

- **Fuseau** : chaque instant est rattaché à un Jour ouvré dans le fuseau du Programme
  (Europe/Paris, `contrats.calendrier`), pas celui de l'instance Jira ; un événement proche
  de minuit peut changer de jour (voire passer au lundi suivant).
- **Tickets déplacés entre projets** : un ticket est compté dans son projet **courant**
  (`fields.project`) pour tout son historique.
- **Changelogs tronqués** : `changelog.total` > nombre d'historiques pour 4 tickets
  d'IntelDAOS ; leurs derniers événements manquent.
- **Tickets créés résolus** (6 dans JFrog : premier item `resolution` parti d'une valeur) :
  traités, ils n'entrent en stock qu'à leur réouverture.
- **Tickets fermés sans résolution** (aucun item `resolution`, `resolutiondate` nulle, statut
  de catégorie « done » : 350 dans Hyperledger, 151 dans JFrog, 44 dans SecondLife) : traités,
  résolus au dernier changement de statut (sinon à la création).
- **Borne de fin** : sans `--fin`, chaque série s'arrête au dernier événement de son projet ;
  la Story 4.4 choisit la borne commune de l'évaluation.
