# Mode LLM local (Story 6.12, FR-37)

La couche LLM peut tourner sur le poste avec `llama-server` (llama.cpp, tag **b11552**), si la banque
refuse tout LLM distant. Rien ne quitte le poste, aucune clé d'API, coût estimé nul.

## Lancer le serveur

Un modèle quantifié qui tient dans 8 Go de VRAM (par exemple un GGUF Q4_K_M de 7 à 8 milliards de
paramètres) :

```
llama-server -m <modele>.gguf --jinja --port 8080 -ngl 99 -c 16384
```

`--jinja` est nécessaire : le mode Tool Output (sortie structurée) et les outils de l'Agent passent
par les appels d'outils du modèle de conversation. Choisir un modèle dont le gabarit les prend en
charge.

## Configurer l'usine

`config/llm.yaml` :

```
fournisseur: local
modele: <nom libre du GGUF>      # entre dans la clé de cache et les versions : local:<nom>
modeles_par_tache: {}            # ou un autre GGUF par tâche, servi par le même serveur
```

`LLM_LOCAL_URL` (variable d'environnement, facultative) remplace l'adresse par défaut
`http://127.0.0.1:8080/v1`. Tout nom `local:<nom>` est admis au registre des prix, à coût nul : le
plafond de coût par Passage ne se déclenche jamais.

## Garanties

- Le port `FournisseurLLM` ne combine jamais schéma et outils dans un même appel (AD-13, AD-20) :
  `generer_structure` n'envoie que l'outil de sortie `reponse`, `executer_agent` que les outils
  reçus. La suite de contrat (`tests/contrat/fournisseur_llm`) passe avec le cas `local`, sur
  faux transport.
- La Pseudonymisation, le cache, les contrôles déterministes et la trace restent ceux de la
  passerelle : seul l'adaptateur change.
- Serveur éteint : l'appel échoue en `UsineErreur` qui nomme `local:<modele>`.

## Relancer les évaluations

À la demande, hors CI, serveur démarré (voir les README des suites) :

```
uv run python -m evals.explication executer --reel
uv run python -m evals.classification executer --reel
```

Les résultats de chaque exécution se publient comme ceux du mode distant (répertoires
`resultats/`), avec le modèle local en tête. **Non relancées dans cette livraison** : aucun
`llama-server` ni GGUF n'était disponible à l'implémentation. Les cibles SM-3 et SM-9 restent à
mesurer sur le poste de démo ; un petit modèle quantifié peut les manquer, et le résultat se publie
tel quel.
