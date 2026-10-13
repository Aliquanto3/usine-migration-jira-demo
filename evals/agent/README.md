# Suite d'évaluation de l'Agent (SM-4)

Mesure la fiabilité de l'Agent conversationnel avant la démo. Cible SM-4 : **au moins 13
questions réussies sur 15**, **aucun chiffre inventé** et **au plus 1 refus** sur les 13
questions répondables (H-22).

## Contenu

- `questions.json` : le `passage_id` du Passage interrogé (`demo/repli/passage/`, Date
  d'arrêté 2026-10-09), puis les 15 questions versionnées. Chacune porte son identifiant, son
  texte, `repondable`, `demo` (une seule : la question de l'epic, « Quelles entités risquent
  de passer au rouge la semaine prochaine, et pourquoi ? »), ses éléments attendus
  (`attendus` : `entites`, codes d'Entité ou d'indicateur ; `tickets` ; `chiffres`, nombres
  écrits à la française ou dates ISO) et son tour enregistré (`tour` : appels d'outils, puis
  texte final). Deux questions n'ont pas de réponse possible (budget, Date d'arrêté non
  couverte).
- `questions.py` : chargement validé (15 questions, une seule `demo`, au moins 2 sans
  réponse possible, identifiants et textes uniques).
- `suite.py` : exécution, notation automatique et historique.
- `resultats/<horodatage>.json` : un fichier par exécution.
- `historique.jsonl` : une ligne de synthèse par exécution.

## Protocole

```sh
uv run python -m evals.agent executer
```

Chaque question est posée à la vraie `SessionAgent`, celle de l'UI
(`usine.composition.construire_session_agent`) : outils réels sur le Passage, passerelle
(Pseudonymisation, cache en mémoire, traces) et contrôle des chiffres et des tickets. Par
défaut, le tour enregistré de chaque question est rejoué : ses appels d'outils sont exécutés
sur le Passage, puis son texte passe le contrôle, sans réseau ni secret (c'est ce que teste
la CI). Les traces de la session vont dans `sorties/agent/<AAAA-MM-JJ>/<session>.jsonl` ; le
Passage n'est que lu. Si le `passage_id` du Passage diffère de celui des questions, ou si une
question n'a pas de tour enregistré en rejeu, la commande s'arrête (code 1) en le nommant.

Options : `--questions`, `--passage`, `--racine`, `--sortie`, `--historique`.

## Notation

- **Question répondable réussie** : réponse conforme au contrôle, qui n'est pas un refus et
  contient chaque élément attendu. Entité, indicateur et ticket : mot entier (`ENT-C` n'est
  pas dans `ENT-CD`). Chiffre : nombre isolé écrit à la française (`1 100`, `0,5`), qui
  n'est ni un fragment d'un nombre plus long, ni un morceau de clé (`4` de `IND-4`) ou de
  date.
- **Question sans réponse possible réussie** : réponse conforme contenant « ne permettent pas
  de répondre ».
- **Chiffres inventés** : nombres et dates du texte brut refusés par le contrôle (absents des
  résultats des outils). **Tickets inventés** : tickets cités mais non retournés.
- **Refus** : réponse conforme « Les données ne permettent pas de répondre. » à une question
  répondable.
- **Verdict** `sm4_atteint` : score ≥ 13, 0 chiffre inventé, refus ≤ 1.

## Mode réel

```sh
uv run python -m evals.agent executer --reel
```

Lit `config/llm.yaml` (fournisseur et modèle de la tâche `agent`, plafond de coût), la clé du
fournisseur et `USINE_CLE_PSEUDO`, comme l'écran Agent. Le cache est en mémoire. Les tours
enregistrés sont ignorés. Jamais lancé en CI.

Coût estimé (Sonnet 5.5, 3 $ / 15 $ par million de jetons) : environ 3 tours de modèle par
question, avec des résultats d'outils de 2 000 à 5 000 jetons, soit **0,40 à 0,90 €** pour
les 15 questions. Le coût réel, tarifé par le registre des prix, figure dans le résultat
(`cout_estime_eur`).

Pour figer une réponse réelle comme tour enregistré, recopier ses appels d'outils et son texte
dans `tour` de la question concernée.
