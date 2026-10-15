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

## 4. À ne pas faire sans précaution

- `usine donnees injecter` écrit dans Jira (site `DEMO`). Ne pas le lancer pour un test de routine.
- Les commandes qui appellent un LLM réel (préchauffage, recette, évaluations hors CI) coûtent de l'argent.
- Ne jamais coller le contenu de `.env` ou une clé dans un message, un ticket ou un commit.

## 5. Ce qui reste à faire après les tests

- Consigner le résultat (OK ou écart) dans une section « Résultats » de ce fichier, avec la date et le poste.
- Un écart sur 3.2 (fuite) est bloquant : le signaler avant tout autre travail.
