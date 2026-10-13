# Mode LLM local (llama.cpp)

Si la banque refuse tout LLM distant, `fournisseur: llama` fait tourner la démo du Palier 2 sur
le poste (FR-37), sans clé d'API et à coût nul.

1. Installer `llama-server` (llama.cpp, tag b11552) depuis les binaires de la page des
   versions de llama.cpp sur GitHub (build CUDA pour un GPU NVIDIA).
2. Télécharger le modèle GGUF Qwen3-8B Q4_K_M (environ 5 Go, tient dans 8 Go de VRAM).
3. Lancer le serveur :
   `llama-server -m <fichier>.gguf --jinja --alias qwen3-8b-q4_k_m -ngl 99 -c 16384 --port 8080`
4. Dans `config/llm.yaml` : `fournisseur: llama`, `modele: qwen3-8b-q4_k_m`, et retirer le bloc
   `modeles_par_tache` (ses modèles sont ceux d'Anthropic). L'adresse du serveur se règle par
   `USINE_LLAMA_URL` (défaut `http://127.0.0.1:8080/v1`). Un autre GGUF se branche par une ligne
   de `src/usine/adaptateurs/llm/registre.py` et l'option `--alias`.
5. Relancer les suites d'évaluation (`uv run python -m evals.classification executer --reel
   --donnees <répertoire>` et `uv run python -m evals.explication executer --reel`) puis publier
   les résultats (`historique.jsonl` et `resultats/` de chaque suite). Cette relance n'a pas
   encore été faite.
