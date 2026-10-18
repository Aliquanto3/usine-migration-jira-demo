# Note de portage détaillée : Dataiku et Power Platform

Complément de [la fiche « outillage demandé »](fiche-outillage.md) (FR-48, Story 8.3). La fiche dit quoi demander et ce qui se porte ; cette note dit comment découper la Chaîne, où poser les secrets et la configuration, et ce qui ne se porte pas. Les règles citées sont celles du spine d'architecture : AD-1 (couches hexagonales, `lint-imports`), AD-19 (configuration et secrets), AD-25 (interface web locale) ; NFR-8 (cœur sans service propriétaire autre que Jira). Aucune des deux plateformes n'a été essayée : tout ce qui suit est une analyse du code du dépôt, pas un retour d'expérience.

## Ce qui se porte tel quel

Le domaine (`usine.domaine` : Instantanés, KPI, Météo, Prévision, causes) n'a ni I/O, ni horloge, ni tirage aléatoire : la Date d'arrêté et la graine sont des paramètres. Il se rejoue donc dans n'importe quel moteur Python 3.12. Les ports (`usine.ports`) sont les seules coutures : toute plateforme se branche en écrivant un adaptateur, jamais en modifiant le domaine.

| Port | Rôle | Adaptateur livré | Point de branchement sur une plateforme |
|---|---|---|---|
| `source_tickets` | lecture des tickets et du changelog | `jira_cloud` (API v3), `jira_dc` (API v2), `journal`, `composite` | connecteur de la plateforme à la place de `jira_http` |
| `entrepot` | stockage incrémental des tickets | `entrepot_duckdb` | dataset géré (table) à la place du fichier DuckDB |
| `etape` | étape de la Chaîne (`chaine.etapes`) | étapes déterministes et étapes LLM | une recette ou un nœud par étape |
| `fournisseur_llm` | appel au modèle | `llm` (Anthropic, Mistral, mode local en bonus) | LLM Mesh ou AI Builder à la place du fournisseur |
| `pseudonymiseur` | Pseudonymisation avant tout appel LLM | `presidio`, `pseudonymisation` | inchangé, ou service de masquage du client |
| `cache_llm` | cache des réponses du modèle | `stockage_sqlite` | stockage de la plateforme |
| `consultation` | lecture d'un Passage publié | `usine.consultation` (fichiers) | lecture d'un dossier géré |

Le Passage (dossier horodaté de fichiers : manifeste, tables, classeur Excel, présentation PowerPoint) est le seul produit de la Chaîne : le publier ailleurs est une copie de dossier, pas un changement de code.

## Dataiku

### Découpage des briques

| Brique du projet | Équivalent Dataiku | Remarque |
|---|---|---|
| `usine rapport` (`chaine.execution`, `composition.py`) | scénario Dataiku, un pas par étape ou un seul pas « recette Python » | `composition.py` reste la racine de composition (AD-1) |
| Extraction Jira (`source_tickets`) | recette Python, ou plugin Jira si le client en fournit un | l'extraction est incrémentale : conserver l'état dans un dataset |
| Entrepôt DuckDB | dataset géré (SQL ou dossier) | à remplacer par un adaptateur `entrepot` ; le fichier DuckDB local n'a pas d'intérêt côté serveur |
| Instantanés, KPI, Météo, Prévision | recettes Python (une par module du domaine) | le domaine est appelé tel quel ; la Prévision ML peut aussi passer par Visual ML (à comparer, pas livré) |
| Classification, explication, narration (`usine.ia`) | recettes Python avec LLM Mesh derrière le port `fournisseur_llm` | nouvel adaptateur seulement (AD-1) ; la Pseudonymisation reste avant l'appel |
| Excel, PowerPoint (`usine.rendu`) | recette Python écrivant dans un dossier géré | le gabarit `gabarits/rapport.pptx` doit être versé dans un dossier du projet |
| Agent conversationnel (`usine.ia.agent`) | agent Dataiku ou webapp | outils en lecture seule sur le Passage ; à rebrancher sur le port de consultation |
| Interface web (`usine.ui`) | webapp Dataiku « standard » | les pages HTML statiques se reprennent ; l'API FastAPI se réécrit en backend Flask |
| Planification | scénarios à déclencheur horaire | équivalent du cron de la VM |

### Secrets et configuration

- Les paramètres restent dans `config/*.yaml`, validés au chargement (AD-19). Les verser dans le dossier de ressources du projet et faire pointer la racine (`USINE_RACINE`, ou le répertoire de travail de la recette) sur ce dossier.
- Les secrets (`JIRA_EMAIL`, `JIRA_TOKEN_LECTURE`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `USINE_CLE_PSEUDO`, et `JIRA_DC_PAT` pour Data Center) se posent comme variables d'environnement du projet ou comme secrets d'utilisateur Dataiku, injectés dans l'environnement de la recette. Pas de fichier `.env` dans le dossier du projet (NFR-4, gitleaks).
- `JIRA_TOKEN_INJECTION` ne se pose jamais côté Dataiku : seul l'injecteur du démonstrateur écrit dans Jira, `usine rapport` ne le lit pas (AD-1).
- Avec LLM Mesh, la clé du fournisseur est portée par la connexion Dataiku, pas par le projet : l'adaptateur n'a plus à la lire.

### Limites connues

- Le modèle spaCy `fr_core_news_md` (Pseudonymisation, Palier 2) est téléchargé depuis GitHub à l'installation ; sans accès, prévoir un miroir interne ou un dépôt de paquets.
- Python 3.12 est exigé (`requires-python`) : vérifier l'environnement de code Dataiku.
- Le Verrou de Passage (`donnees/.verrou-passage`) suppose un système de fichiers local ; sur un dossier géré distant, le remplacer ou garantir un seul scénario actif.
- L'interface web et l'écran de l'Agent sont à refaire (Flask ou webapp) : ce n'est pas un simple déploiement.
- L'adaptateur LLM Mesh, l'adaptateur d'entrepôt géré et le branchement de l'Agent ne sont pas écrits : ce sont des travaux à chiffrer, pas des réglages.

## Power Platform

### Découpage des briques

| Brique du projet | Équivalent Power Platform | Remarque |
|---|---|---|
| Extraction Jira | connecteur Jira de Power Automate | limité sur le changelog et les volumes : garder l'extraction en Python, hors plateforme |
| Instantanés, KPI, Météo | non porté | possible en Power Query ou en flux, peu maintenable ; le domaine reste en Python |
| Prévision ML | non porté | pas d'équivalent |
| Classification, explication, narration | AI Builder ou Copilot Studio | seulement si l'endpoint est validé par le client ; la Pseudonymisation est à refaire |
| Excel, PowerPoint | appel de la Chaîne Python, puis dépôt SharePoint | la génération se fait en Python ; Power Automate ne fait que publier |
| Agent conversationnel | Copilot Studio | à reconstruire sur les fichiers du Passage ; les garde-fous de l'Agent (chiffres et tickets vérifiés) ne se portent pas |
| Interface web | Power Apps | à refaire ; les pages statiques ne se portent pas |
| Planification et publication | flux Power Automate planifié | déclenche la Chaîne ailleurs et copie le Passage vers SharePoint ou un partage |

Le découpage réaliste est donc hybride : la Chaîne tourne en Python (VM, conteneur ou Dataiku), et Power Platform se limite à la planification, à la publication des fichiers et à un écran de consultation.

### Secrets et configuration

- Les secrets restent côté Python (VM ou conteneur, section suivante). Power Platform ne reçoit ni jeton Jira ni clé LLM, sauf via un connecteur dont les identifiants sont gérés dans la plateforme (connexion partagée, jamais en clair dans un flux).
- Les variables d'environnement de solution Power Platform servent aux paramètres de publication (site SharePoint, dossier cible) ; les paramètres de la Chaîne restent dans `config/*.yaml` (AD-19).
- Le compte de service Jira est en lecture seule (demande 1 de la fiche) : c'est la seule identité que la Chaîne utilise.

### Limites connues

- Pas de moteur de calcul de la Météo ni de la Prévision : tout flux qui les reproduirait diverge du domaine testé.
- Le connecteur Jira ne donne pas le changelog complet à volume réel : l'extraction incrémentale du projet ne s'y remplace pas.
- Aucune des étapes LLM n'est portée telle quelle : AI Builder et Copilot Studio ont leurs propres garde-fous, à valider avec le client.
- Les quotas de flux (appels par jour, durée d'exécution) sont à vérifier sur la licence du client ; ils n'ont pas été mesurés.

## Conteneur

Le `Dockerfile` à la racine produit une image de la Chaîne et de l'interface web. **Build non vérifié localement** : Docker et hadolint n'étaient pas installés sur le poste de développement ; la première construction est à faire et à corriger si besoin.

### Construire

```bash
docker build -t usine-jira-demo .
# avec le groupe optionnel `bonus` (lightgbm, langfuse) :
docker build --build-arg AVEC_BONUS=1 -t usine-jira-demo:bonus .
```

L'installation est `uv sync --locked --no-dev` (versions du `uv.lock`, groupes `dev` et `evaluation` écartés). `AVEC_BONUS=1` ajoute le groupe `bonus` et la bibliothèque système `libgomp1`.

### Lancer l'interface

```bash
docker run --rm -p 127.0.0.1:8000:8000 \
  --env-file .env \
  -v "$PWD/donnees:/app/donnees" -v "$PWD/sorties:/app/sorties" \
  usine-jira-demo
```

Puis ouvrir `http://127.0.0.1:8000/`. Dans le conteneur, `usine ui` écoute sur `0.0.0.0` (variable `USINE_UI_HOTE`, posée par le `Dockerfile` seulement) parce qu'un serveur lié à `127.0.0.1` n'est pas joignable par la publication de port. La protection reste celle de l'interface locale (AD-25) :

- publier **toujours** avec `-p 127.0.0.1:8000:8000`, avec le même port des deux côtés ; `-p 8000:8000` ouvrirait l'interface au réseau de l'hôte ;
- l'interface refuse tout en-tête `Host` autre que `127.0.0.1` ou `localhost` (le port n'est pas contrôlé) et tout `Origin` qui ne nomme pas ce même hôte et ce même port : un autre port d'hôte (`-p 127.0.0.1:9000:8000`, ouvert sur `http://127.0.0.1:9000/`) fonctionne donc aussi ;
- ce contrôle arrête une page web tierce (DNS rebinding), pas un client qui forge l'en-tête `Host` : l'interface n'a pas d'authentification, d'où la publication sur la boucle locale seulement. Les autres conteneurs du même réseau Docker peuvent joindre le port 8000 : ne pas lancer l'image sur un réseau partagé.

`USINE_UI_HOTE` n'accepte que `127.0.0.1` ou `0.0.0.0`, et `0.0.0.0` seulement dans un conteneur (présence de `/.dockerenv` ou de `/run/.containerenv`, posés par Docker et Podman) : hors conteneur, `usine ui` refuse de démarrer.

### Produire un Passage en Palier 1

```bash
docker run --rm --env-file .env \
  -v "$PWD/donnees:/app/donnees" -v "$PWD/sorties:/app/sorties" \
  usine-jira-demo rapport --date-arrete 2026-10-09
```

Le Journal (`donnees/journal.jsonl`, généré par `usine donnees generer`) est monté avec `donnees/` ; le Passage publié arrive dans `sorties/passages/`. Le Palier 1 n'appelle aucun LLM : les étapes LLM sont `sautees` (FR-28).

### Secrets et fichiers

- `.env` n'est jamais copié dans l'image (`.dockerignore`) : l'image ne contient aucun secret. Le fournir au lancement avec `--env-file .env`, ou en lecture seule par `-v "$PWD/.env:/app/.env:ro"`.
- `donnees/`, `sorties/`, `.git`, `.venv` et les caches sont aussi exclus de l'image.
- Le conteneur tourne avec l'utilisateur non root `usine` (UID 10001) : les dossiers montés doivent exister avant le lancement (sinon Docker les crée au nom de root) et être inscriptibles par cet UID (sous Linux, `mkdir -p donnees sorties && chown 10001 donnees sorties`, ou `--user "$(id -u):$(id -g)"`).
- `--env-file` transmet les valeurs telles quelles, guillemets compris : écrire `CLE=valeur` sans guillemets dans `.env`, ou monter `.env` en lecture seule. Ne pas y laisser de `USINE_RACINE` propre au poste (chemin Windows par exemple) : dans l'image, la racine est `/app`.
- `usine agent --enregistrer` (réponses du Mode repli, `demo/repli/agent/`) n'est pas prévu dans l'image : `demo/` y appartient à root.
- Le mode LLM local (bonus) n'est pas dans l'image : un serveur de modèle sur l'hôte demande une configuration réseau propre.
