# Suite d'évaluation de l'Explication sourcée (SM-3)

Mesure la fidélité des Explications sourcées avant la démo. Cible SM-3 : **100 % de
Citations valides** et **note humaine moyenne ≥ 4/5** sur 10 cas.

## Contenu

- `cas/cas-01.json` … `cas-10.json` : les 10 cas versionnés. Chaque cas porte la Météo de
  l'Entité à la Date d'arrêté (`meteo`), les textes des tickets en cause (`textes`), les KPI
  (`kpi`) et la répartition des Causes racines (`repartition`), tous deux facultatifs, et les
  réponses enregistrées du fournisseur (`reponses`, rejouées dans l'ordre : appel initial,
  puis régénération éventuelle). Les cas couvrent le rouge et l'orange, une ou plusieurs
  règles, une phrase hors cause (cas-06), une régénération (cas-07) et une consigne glissée
  dans un ticket (cas-10).
- `suite.py` : exécution (`executer_suite`) et notation (`noter`).
- `resultats/<horodatage>.json` : un fichier par exécution.
- `historique.jsonl` : une ligne par notation.

## Protocole

1. **Exécuter.** `uv run python -m evals.explication executer` passe chaque cas par la vraie
   tâche `expliquer`, passerelle comprise (Pseudonymisation, cache en mémoire, contrôle des
   Citations, régénération), puis applique `controler_citations` à chaque sortie avec les
   tickets en cause du cas. Par défaut, les réponses enregistrées sont rejouées, sans réseau
   ni secret (c'est ce que teste la CI).
2. **Lire le taux.** `taux_citations_valides` = phrases retenues ÷ phrases totales, cumulées
   sur les 10 cas. Une « explication indisponible » ne cite aucun ticket : elle compte comme
   une phrase invalide. `phrases_retirees` (par cas) et `phrases_retirees_passerelle` donnent
   la qualité brute : le nombre de phrases que la passerelle a dû retirer.
3. **Noter.** Dans le fichier de résultat, remplacer pour chaque cas les `null` de `notes`
   par une note entière de 1 à 5, critère par critère (grille ci-dessous).
4. **Enregistrer.** `uv run python -m evals.explication noter evals/explication/resultats/<horodatage>.json`
   ajoute à `historique.jsonl` la moyenne humaine (sur les 20 notes), la moyenne par critère,
   le taux, `version_prompt`, `version_modele` et `sm3_atteint` (taux de 100 % et moyenne
   ≥ 4). Une note manquante ou hors de 1..5 arrête la commande en nommant le cas ; rien n'est
   alors écrit.

## Grille de notation

| Note | `exactitude` : l'explication est-elle juste ? | `utilite` : aide-t-elle le Pilote ? |
|------|-----------------------------------------------|-------------------------------------|
| 5 | Tout est exact et rattaché au bon ticket. | Le Pilote sait quoi faire sans ouvrir Jira. |
| 4 | Exact, une imprécision mineure (formulation, chiffre arrondi). | Utile, une précision manque. |
| 3 | Une affirmation discutable ou mal rattachée. | Utile en partie, redit surtout les données. |
| 2 | Plusieurs erreurs, ou une erreur sur la cause principale. | Peu utile, trop vague. |
| 1 | Faux ou trompeur (couleur, règle, ticket). | Inutile ou nuisible à la décision. |

Une « explication indisponible » se note 1 en utilité ; son exactitude se note 5 si rien de
faux n'est affirmé.

## Mode réel

```sh
uv run python -m evals.explication executer --reel
```

Lit `config/llm.yaml` (fournisseur, modèle de la tâche `explication`, plafond de coût), la clé
du fournisseur (`ANTHROPIC_API_KEY` ou `MISTRAL_API_KEY` ; aucune avec `fournisseur: llama`) et
`USINE_CLE_PSEUDO`, comme un
Passage Palier 2. Le cache est en mémoire : le cache de production n'est ni lu ni écrit. Les
réponses enregistrées des cas sont ignorées.

Mode LLM local : avec `fournisseur: llama` dans `config/llm.yaml` et un `llama-server` lancé
(procédure dans `docs/mode-llm-local.md`), la même commande tourne sans clé ni coût ; publier
ensuite `historique.jsonl` et `resultats/`.

Coût estimé (Sonnet 5.5, 3 $ / 15 $ par million de jetons) : 10 à 20 appels (une régénération
au plus par cas) × environ 1 500 jetons d'entrée et 400 de sortie, soit **0,10 à 0,25 €**,
bien en deçà du plafond de 2 € par Passage. Jamais lancé en CI.

Pour figer une nouvelle réponse réelle comme réponse enregistrée, la recopier (texte et
brouillon de commentaire) dans `reponses` du cas concerné.
