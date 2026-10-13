# Mode LLM local (Story 6.12, FR-37)

Si la banque refuse tout LLM distant, le Palier 2 et l'Agent tournent sur un modèle local servi par
`llama-server` (llama.cpp, tag b11552), qui expose une API compatible OpenAI Chat Completions. Le
choix se fait dans `config/llm.yaml`, sans modification de code (H-23). Aucune clé n'est exigée.

## 1. Télécharger le modèle

`mistralai/Ministral-3-8B-Instruct-2512-GGUF`, quantification Q4_K_M (environ 5 Go, Apache 2.0,
français). Il tient dans 8 Go de VRAM avec un contexte de 16 k.

```bash
huggingface-cli download mistralai/Ministral-3-8B-Instruct-2512-GGUF \
  Ministral-3-8B-Instruct-2512-Q4_K_M.gguf --local-dir modeles
```

## 2. Lancer le serveur

`--jinja` est nécessaire à l'appel d'outils ; `--alias` fixe le nom de modèle que la configuration cite.

```bash
llama-server -m modeles/Ministral-3-8B-Instruct-2512-Q4_K_M.gguf \
  --alias ministral-3-8b --jinja -ngl 99 -c 16384 --port 8080
```

## 3. Basculer la configuration

Dans `config/llm.yaml`, remplacer `fournisseur`, `modele` et `modeles_par_tache` par le bloc « mode
local » commenté en bas du fichier (`fournisseur: local`, `modele: ministral-3-8b`).

Variables d'environnement, toutes facultatives :

- `USINE_URL_LLM_LOCAL` : URL de base du serveur (défaut `http://127.0.0.1:8080/v1`) ;
- `LLAMA_API_KEY` : clé, si le serveur est lancé avec `--api-key` ; envoyée si présente.

Le modèle local figure au registre à coût nul (`gratuit`). Serveur éteint, l'erreur nomme
`local:ministral-3-8b` et l'URL à servir.

## 4. Relancer les évaluations

```bash
uv run python -m evals.explication executer --reel
uv run python -m evals.classification executer --reel
```

Publier les résultats sous `evals/explication/resultats/` et `evals/classification/resultats/`.

État : relance non faite dans le run de livraison (aucun `llama-server` ni GPU disponible) ; elle
reste à faire avant d'afficher un score du modèle local.
