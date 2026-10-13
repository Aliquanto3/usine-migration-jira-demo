# Mode LLM local (bonus FR-37)

Si la banque refuse tout LLM distant, le Palier 2 et la démo tournent sur un modèle servi sur le
poste par `llama-server` (llama.cpp). L'usine l'appelle par l'API compatible OpenAI
(`/v1/chat/completions`), avec le même adaptateur Pydantic AI que les fournisseurs distants
(AD-13) : sortie structurée par appel d'outil `reponse`, Agent par les seuls outils reçus.
Aucune clé d'API et un coût estimé nul. Aucun appel ne sort du poste tant que
`USINE_LLM_LOCAL_URL` pointe vers ce poste ; la Pseudonymisation s'applique de toute façon.

## Prérequis

- Un GPU de 8 Go de VRAM (ou un CPU, plus lent).
- `llama-server` de llama.cpp, tag **b11552** : archive de la release
  `https://github.com/ggml-org/llama.cpp/releases/tag/b11552` correspondant au poste (CUDA, Vulkan
  ou CPU), dézippée hors du dépôt.
- Le modèle `Qwen3-8B-Q4_K_M.gguf` (environ 5 Go, tient dans 8 Go de VRAM), du dépôt Hugging Face
  `Qwen/Qwen3-8B-GGUF`, enregistré hors du dépôt. Ni binaire ni modèle ne sont versionnés.

## Lancer le serveur

```sh
llama-server -m <chemin>/Qwen3-8B-Q4_K_M.gguf --alias qwen3-8b --jinja --reasoning-budget 0 \n  -ngl 99 -c 8192 -np 1 --host 127.0.0.1 --port 8080
```

`--jinja` active le tool calling du gabarit du modèle (indispensable : la sortie structurée et
l'Agent passent par des appels d'outils). Ne pas passer `--api-key` : l'usine n'envoie aucune clé.
- `--reasoning-budget 0` : Qwen3 raisonne par défaut, et cette réflexion consomme
  `max_jetons_sortie` (300 pour la classification) ; l'appel d'outil serait tronqué.
- `--alias qwen3-8b` : le nom de modèle servi correspond à `local:qwen3-8b`.
- `-c 8192 -np 1` : environ 5 Go de poids plus un contexte de 16 384 jetons est limite sur 8 Go de
  VRAM, et les emplacements parallèles par défaut se partagent le contexte ; un seul emplacement
  garde les 8 192 jetons entiers pour chaque requête.

Pendant le chargement, `llama-server` répond 503. Attendre que `GET /health` renvoie 200
(`curl http://127.0.0.1:8080/health`) avant de lancer l'usine.

## Configurer l'usine

1. Dans `config/llm.yaml` : `fournisseur: local`, `modele: qwen3-8b`, et retirer le bloc
   `modeles_par_tache` (ses modèles sont ceux d'Anthropic ; seul `local:qwen3-8b` est au registre).
2. Variable d'environnement optionnelle `USINE_LLM_LOCAL_URL` (environnement ou `.env`), URL de
   base du serveur ; défaut `http://127.0.0.1:8080/v1`.
3. `USINE_CLE_PSEUDO` reste requise au Palier 2 (aucun appel sans Pseudonymisation, même local).

Un serveur injoignable ou une réponse hors schéma lève une `UsineErreur` nommant
`local:qwen3-8b` ; le Passage échoue en nommant l'étape.

## Relancer et publier les deux suites d'évaluation

Mentionner dans le message du commit la quantification du GGUF (`Q4_K_M`) et le tag llama.cpp
(`b11552`).

Garde-fou AD-19 : `modele_corpus` du Journal doit différer du modèle évalué (`local:qwen3-8b`
l'est tant que le corpus a été produit par un modèle distant ou provisoire).

```sh
uv run usine donnees generer --sortie donnees-eval
uv run python -m evals.classification executer --reel --donnees donnees-eval
uv run python -m evals.explication executer --reel
# Noter à la main les 10 cas dans le fichier produit, puis :
uv run python -m evals.explication noter evals/explication/resultats/<horodatage>.json
git add evals/classification/resultats evals/classification/historique.jsonl \
        evals/explication/resultats evals/explication/historique.jsonl
git commit -m "Docs: résultats des suites d'évaluation en mode LLM local (llama-server b11552, Qwen3-8B Q4_K_M)"
```

Les fichiers `resultats/<horodatage>.json` et les lignes d'`historique.jsonl` portent
`local:qwen3-8b` comme version de modèle : ils se comparent à ceux des fournisseurs distants.
Revenir à `config/llm.yaml` d'origine avant de commiter autre chose.

## Limites

- Un modèle de 8 milliards de paramètres quantifié classe et explique moins bien qu'un modèle
  distant : les cibles SM-9 (F1 macro ≥ 0,8) et SM-3 peuvent ne pas être atteintes ; le résultat
  publié le dit tel quel.
- L'Agent (tool calling) n'a pas été essayé en mode local avec un modèle de 8 milliards de
  paramètres.
- Les tests automatiques rejouent des réponses enregistrées ; aucun test ne lance `llama-server`.
