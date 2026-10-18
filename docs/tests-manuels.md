# Tests manuels : reprise sur un autre poste

Ce document sert à reprendre le projet sur un autre ordinateur, puis à vérifier à la main le dernier lot livré (Story 6.10-b, correctifs reportés de la 6.10). Il ne remplace pas la CI : les contrôles automatiques ci-dessous doivent passer d'abord.

## 1. Mise en place du poste

Ce qui n'est pas dans Git (ignoré par `.gitignore`) et doit être transféré à la main, sans passer par le dépôt :

- **`.env`** : copier `.env.example`, puis renseigner les valeurs. Y figurent les jetons Jira, les clés Anthropic et Mistral, et `USINE_CLE_PSEUDO`. Ne jamais le committer ni le coller dans un chat.
- **`donnees/` et `sorties/`** : générés localement. Ils se recréent à l'identique (graine 42) avec `uv run usine donnees generer --date-generation 2026-10-12`.

Étapes :

```powershell
git clone https://github.com/Aliquanto3/usine-migration-jira-demo.git
cd usine-migration-jira-demo
git checkout main
uv sync --locked
```

Vérifier que `uv` est installé (`uv --version`). Le projet cible Python 3.12.

## 2. Contrôles automatiques (même ordre que la CI)

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run pytest
```

Tous doivent passer avant les tests manuels. Résultat attendu sur `main` : aucun échec.

## 3. Tests manuels

### 3.1 Rapport de bout en bout (Palier 1, sans LLM, gratuit)

```powershell
uv run usine rapport --date-arrete 2026-10-09
```

Vérifier : la commande se termine sans erreur ; le Classeur Excel (9 onglets) et la présentation PowerPoint (7 sections) sont produits dans `sorties/` ; les chiffres de la météo sont cohérents avec le Passage affiché.

### 3.2 Balayage SM-7 des traces (6.10-b)

Les traces d'échec (`en_echec`) doivent être balayées comme les autres lignes de `trace/llm.jsonl`, et aucune donnée brute ne doit y fuir.

```powershell
uv run python outils/balayer_sm7.py --help
```

Lancer l'outil sur le répertoire de recette ou sur le dernier Passage (voir l'aide pour les options). Résultat attendu : code de sortie 0. Un code 1 signale une fuite : ne pas continuer et le noter.

### 3.3 Préchauffage du cache et relances bornées (6.10-b)

```powershell
uv run python outils/prechauffer_cache.py --help
```

Points à vérifier :

- l'aide indique `--max-echecs` (défaut 2) ;
- après une relance qui échoue, le fichier `donnees/prechauffage_echecs.json` est écrit ; supprimer ce fichier remet les compteurs à zéro ;
- une Anomalie ayant échoué `max-echecs` fois est comptée « abandonnée » et n'est pas redemandée.

**Attention : cet outil appelle le LLM réel et consomme du budget.** Le budget de la recette est d'environ 1 € (Anthropic et Mistral). Commencer par une petite tranche, et s'assurer que la clé utilisée est la bonne.

### 3.4 Mode repli (lecture seule, sans réseau)

```powershell
$env:USINE_MODE_REPLI = "1"
uv run usine ui
```

Vérifier : le bandeau « Mode repli » est visible en permanence ; le lancement d'un Passage est désactivé ; l'écran lit le Passage enregistré dans `demo/repli/`, sans appel Jira ni LLM. Remettre `USINE_MODE_REPLI` à vide après le test.

### 3.5 Interface de démo

```powershell
uv run usine ui
```

Vérifier que l'interface s'ouvre et que la carte, le détail des Entités et l'écran « Avant / après » s'affichent.

### 3.6 Cadre de l'interface web (Story 7.13)

`usine ui` sert l'interface FastAPI sur `http://127.0.0.1:8000/` (option `--port`) ; l'ancienne interface Streamlit reste accessible par `uv run usine ui --streamlit` jusqu'à la Story 7.17. Les contenus d'écran arrivent en 7.14 à 7.16 : ici, on contrôle le cadre commun des sept pages (`/`, `/entites/ENT-B`, `/chaine`, `/agent`, `/avant-apres`, `/pseudonymisation`, `/outillage`).

```powershell
uv run usine ui
```

1. Sur chaque page : l'en-tête montre le logo, « Usine de migration », la pastille « Passage publié · JJ/MM/AAAA HH:MM UTC » (absente s'il n'y a aucun Passage), la pastille « Mode réel » et le bouton « Lancer la Chaîne » (absent sur `/chaine`) ; la navigation latérale a sept liens dont un seul actif ; l'onglet s'intitule « {Écran} · Usine de migration » ; il n'y a ni « Chargement… » ni bandeau d'erreur.
2. Au clavier : la première touche Tab fait apparaître « Aller au contenu » ; Entrée amène le focus sur le titre ; l'anneau de focus reste visible partout.
3. Hors réseau (couper le Wi-Fi ou débrancher le câble, recharger) : les polices (Fredoka, Atkinson Hyperlegible, JetBrains Mono), la feuille et le script se chargent ; dans l'onglet Réseau des outils du navigateur, aucune requête ne sort de `127.0.0.1`.
4. Mode repli : relancer avec `$env:USINE_MODE_REPLI = "1"; uv run usine ui`. La pastille « Mode repli » et le bandeau « Mode repli : la démo lit le Passage enregistré `demo/repli/passage/` … » s'affichent sur toutes les pages. Sans la variable (la remettre à vide), le mode est « Mode réel ». Le mode ne change jamais seul.
5. Serveur arrêté : ouvrir une page, arrêter `usine ui` (Ctrl+C), puis revenir sur l'onglet depuis un autre onglet. Le bandeau « L'interface ne joint plus le serveur. Relancer usine ui. » apparaît une seule fois, même après plusieurs retours sur l'onglet.
6. Largeur de 320px et zoom à 200 % : aucun défilement horizontal de la page ; la navigation passe au-dessus du contenu sous 768px.
7. `uv run usine ui --port 8123` : la page répond sur ce port, et sur aucune autre adresse que `127.0.0.1`.

### 3.7 Carte météo, détail d'une Entité et livrables (Story 7.14)

Lancer `uv run usine ui` (Mode réel, après un Passage publié) puis, pour les points 8 et 9, `$env:USINE_MODE_REPLI = "1"; uv run usine ui`.

1. Carte (`/`) : la date d'arrêté, quatre tuiles de comptage (rouge, orange, jaune, vert), le filtre « Filtrer par météo », le tableau des Entités (de la Météo la plus grave à la moins grave, puis par Entité), la légende des flèches au-dessus du tableau et la carte « Livrables du Passage ».
2. Filtre : choisir « Rouge » ; sans rechargement de la page, seules les lignes rouges restent et un lecteur d'écran (ou l'inspecteur : région `role="status"`) annonce « 2 Entités affichées » (« 1 Entité affichée » au singulier). Une couleur sans Entité affiche « Aucune Entité en {couleur} à cette Date d'arrêté. ».
3. Navigation « Détail d'une Entité » : mène à la première Entité du tableau (`/entites` redirige vers elle) ; sans Passage publié, elle ramène à la carte.
4. Détail (`/entites/ENT-A`) : lien « ← Carte météo », sélecteur d'Entité (rien ne se passe avant le clic sur « Afficher »), Météo, Règles déclenchantes (trois premières clés puis un bouton « +N » qui déplie les autres, `aria-expanded`), KPI clés, Prévision, Risque, Explication.
5. Palier : sur un Passage de Palier 2, le segment « Palier 2 / Palier 1 » apparaît ; « Palier 1 » ajoute `?palier=1` à l'URL sans recharger, affiche « commentaire non généré (Palier 1) », masque la Prévision et laisse Météo, Règles et KPI inchangés ; le focus reste sur le bouton choisi. Sur un Passage de Palier 1, le segment est absent.
6. Entité absente : `/entites/ENT-INCONNUE` affiche « Entité ENT-INCONNUE absente du Passage affiché. » et un lien « Voir la carte météo ».
7. Clés de ticket (Mode réel) : chaque clé est un lien qui s'ouvre dans un nouvel onglet ; son nom accessible se termine par « (nouvel onglet) » (inspecteur d'accessibilité).
8. Mode repli : les clés de ticket sont du texte simple, sans lien ni flèche.
9. Livrables : cliquer sur « Rapport quotidien » et « Comité de pilotage » télécharge `rapport-AAAA-MM-JJ.xlsx` et `.pptx` (les ouvrir dans Excel et PowerPoint). Supprimer l'un des deux fichiers du Passage, recharger : le livrable affiche « Non généré pour ce Passage », sans lien ; `http://127.0.0.1:8000/livrables/rapport_xlsx` affiche alors une page qui nomme le fichier et renvoie à la carte. `/livrables/autre` répond 404.

### 3.8 Lancement de la Chaîne et bouton de mode (Story 7.15)

Lancer `uv run usine ui` en Mode réel, depuis une racine configurée (`.env`, secrets Jira) : l'essai de vraie Chaîne du point 8 écrit un Passage dans `sorties/passages/`. Pour les autres points, rien n'est écrit.

1. Écran `/chaine` : le bouton « Lancer la Chaîne » (primaire) et le bouton « Passer en Mode repli » (secondaire) ; la barre de progression à « 0 / 10 », les 10 étapes en « En attente » avec leur description, le journal « En attente d'un lancement. » et l'encart « Dernier Passage ». Le bouton « Lancer la Chaîne » de l'en-tête est absent de cet écran.
2. Mode repli : cliquer sur « Passer en Mode repli ». La pastille devient « Mode repli », le bandeau s'affiche, l'encart « Dernier Passage » lit `demo/repli/passage/`. Le bouton de lancement est inactif (`aria-disabled="true"`, toujours focalisable au clavier) avec son motif visible dessous ; l'inspecteur d'accessibilité montre `aria-describedby` vers ce motif. Ouvrir `/` : la carte lit le Passage enregistré. Le bouton devient « Revenir au Mode réel » ; un clic ramène au dernier Passage réel (pastille « Mode réel », bandeau retiré).
3. Copie du repli absente : renommer temporairement `demo/repli/passage/`, cliquer sur « Passer en Mode repli » : le bandeau d'erreur « Mode repli : Passage enregistré introuvable… » s'affiche sur tous les écrans, et le bouton « Revenir au Mode réel » reste utilisable. Remettre le dossier.
4. Aucune bascule seule : relancer avec `$env:USINE_MODE_REPLI = "1"; uv run usine ui` : le mode de départ est « Mode repli » ; recharger la page ne change rien tant qu'on ne clique pas.
5. Terminal, sans navigateur : `curl.exe -X POST -H "Content-Type: application/json" -d '{\"mode\":\"repli\"}' http://127.0.0.1:8000/api/mode` rend l'état du cadre en mode repli (puis `reel`) ; un corps invalide rend 422. Hors du navigateur, `curl.exe -X POST -H "Origin: http://exemple.invalid" http://127.0.0.1:8000/api/chaine` rend 403.
6. Une Chaîne à la fois : pendant la Chaîne du point 8, un second `curl.exe -X POST http://127.0.0.1:8000/api/chaine` rend 409 avec le motif, sans second processus (Gestionnaire des tâches : un seul `python -m usine rapport`).
7. Pendant la Chaîne du point 8 : le bouton passe à « Chaîne en cours… » et reste inactif ainsi que le bouton de mode, chacun avec son motif ; le focus reste sur le bouton cliqué ; le journal (le plus récent en haut) et les étapes avancent chaque seconde ; la barre suit les étapes terminées (`aria-valuenow`, compteur « n / 10 »). Un lecteur d'écran annonce « Étape n sur 10 : … » à chaque changement d'étape, puis la fin, mais pas chaque seconde. Quitter `/chaine` (ouvrir `/`), attendre, revenir : le suivi reprend et les deux boutons sont toujours inactifs.
8. Vraie Chaîne (pour Anaël, quelques minutes, Jira réel, hors Mode repli) : cliquer sur « Lancer la Chaîne ». À la fin, le bandeau « Chaîne terminée : Passage publié. » et le lien « Voir la carte météo » s'affichent, le bouton devient « Relancer la Chaîne », la pastille de l'en-tête prend l'heure du nouveau Passage et la carte montre la nouvelle Date d'arrêté.
9. Échec : couper le réseau ou invalider le jeton Jira (`.env`) puis lancer la Chaîne. L'étape fautive affiche « Échec », le bandeau d'erreur nomme l'étape, le code de sortie et au plus 20 lignes d'erreur, avec « Aucun rapport publié par ce lancement… » ; la pastille de l'en-tête et la carte restent sur le Passage précédent. Remettre la configuration.
10. Serveur arrêté pendant le suivi (Ctrl+C) : le bandeau « L'interface ne joint plus le serveur. » apparaît une seule fois ; après un redémarrage, le serveur ne retrouve pas une Chaîne lancée par l'ancien processus (l'écran affiche « En attente »).

## 4. À ne pas faire sans précaution

- `usine donnees injecter` écrit dans Jira (site `DEMO`). Ne pas le lancer pour un test de routine.
- Les commandes qui appellent un LLM réel (préchauffage, recette, évaluations hors CI) coûtent de l'argent.
- Ne jamais coller le contenu de `.env` ou une clé dans un message, un ticket ou un commit.

## 5. Ce qui reste à faire après les tests

- Consigner le résultat (OK ou écart) dans une section « Résultats » de ce fichier, avec la date et le poste.
- Un écart sur 3.2 (fuite) est bloquant : le signaler avant tout autre travail.
