# Retour d'expérience : réduire le coût du développement par agents (Claude Code)

Projet : usine-migration-jira-demo, du 10 au 13 octobre 2026. Environ 60 stories développées par un orchestrateur Claude Code (Opus 5.5) qui lance des sous-agents, avec la méthode BMAD.

Ce document sert de référence pour les autres projets. Il réunit ce qui a été observé, mesuré et mis en place. Les recommandations sont classées de la plus rentable à la moins rentable.

## 1. Ce qui a coûté cher

- **Trop d'agents en parallèle et des revues systématiques.** Le premier run autonome a lancé 7 sous-agents en parallèle, avec une revue de suivi pour chaque story. Chaque story a coûté entre 150 k et 270 k tokens, et la limite de dépense mensuelle a été atteinte. Le « mode économique » (2 agents au plus, effort medium, une seule passe de revue) a fait baisser le coût par story d'environ 40 %, sans perte de qualité visible.
- **Des sous-agents partis en arrière-plan sans que personne ne les attende.** Avec `bmad-build-auto`, un agent de story lance lui-même ses sous-agents d'implémentation et de revue. Plusieurs fois, ces appels sont partis en arrière-plan malgré la consigne d'attendre leur résultat. L'agent de story s'arrêtait alors sans avoir vu le résultat, ce qui imposait une reprise : environ 300 k tokens perdus sur les stories 7.7, 7.10 et 6.9.
- **Des contrôles complets répétés.** La suite pytest (2 800 tests) dure 4 à 5 minutes et tournait 3 à 4 fois par story. Comme le cache d'un sous-agent ne dure que 5 minutes par défaut, il expirait presque à chaque contrôle, et tout le contexte était alors relu au prix fort.
- **Opus partout par défaut**, y compris pour du code bien cadré et pour des relectures.

## 2. Banc d'essai Haiku / Sonnet / Opus (2026-10-13)

Chaque modèle a reçu la même tâche réelle du projet, avec la même consigne et le même agent. Il n'y a eu qu'un essai par case, donc ce sont des indications, pas des statistiques. Les tokens sont ceux du sous-agent ; la qualité a été vérifiée par l'orchestrateur et par les tests.

Prix par Mtok, entrée / sortie : Haiku 5.5 à 0,10 $ / 0,50 $, Sonnet 5.5 à 2 $ / 10 $, Opus 5.5 à 4 $ / 20 $.

| Tâche | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 |
|---|---|---|---|
| **Implémentation** (petit correctif d'UI avec test, agent `dev-story`) | 52,7 k tok, 8 min ; correct. **A lancé ses tests en arrière-plan malgré la consigne**, d'où un rapport intermédiaire « en attente » | 43,2 k tok, 9 min ; correct ; un message d'erreur pouvait rester sur plusieurs lignes, malgré la consigne | 46,4 k tok, 9 min ; le plus complet (cas multiligne et navigation testés) |
| **Revue** (commit réel de 660 lignes, en lecture seule) | 88,7 k tok, 2 min ; 4 medium et 6 low ; **trouvailles propres vérifiées en exécutant du code** | 55,4 k tok, 1 min ; 5 medium et 5 low ; précis | 82,7 k tok, 3 min ; **seul à classer « high » le défaut principal**, avec son mécanisme et son ampleur (dépense jusqu'à environ 5 fois le plafond) |
| **Recherche d'infos** (« comment le plafond de coût est-il appliqué ? ») | 36,4 k tok, 19 s ; exact | 18,6 k tok, 21 s ; exact | 18,4 k tok, 19 s ; exact, le plus complet |
| **Rédaction de spec** (story bonus, conteneur et note de portage) | 112 k tok, 3 min ; juste, une bonne remarque technique | 92 k tok, 3 min ; la plus concrète (Dockerfile détaillé, job CI) | 112 k tok, 4 min ; la plus fidèle aux contraintes du projet et la mieux justifiée |

**Ce qu'on en retient :**
- **À tâche égale, les trois modèles consomment à peu près autant de tokens** (Haiku parfois deux fois plus, car il tâtonne). L'écart de coût réel vient donc surtout du prix du token : un ordre de grandeur sépare Haiku de Sonnet. Sonnet coûte la moitié d'Opus au token, mais pas toujours à la tâche : voir la nuance du projet slm ci-dessous.
- **En revue, les trois trouvent le défaut principal, mais seul Opus en mesure bien la gravité.** La réunion des trois listes vaut mieux que chacune seule. Cette revue a trouvé un vrai bug de coût, qui a été corrigé.
- **Haiku** est très bon en lecture (revue, recherche) pour presque rien, mais il respecte moins bien les consignes de processus.
- Une mesure faite le même jour sur un autre projet (« slm ») va dans le même sens : en développement, Sonnet produit la même conception qu'Opus pour 55 % de moins, et en revue, les mêmes constats pour 25 % de moins. Environ 85 % du coût d'un sous-agent vient de la relecture du contexte : réduire le nombre de tours et la taille du contexte compte autant que le choix du modèle.

### Compléments du projet slm (2026-10-13)

Même protocole, avec deux différences : le coût est calculé à partir des transcriptions par catégorie de tokens (`outils/cout_sous_agents.py`), et la spec, l'architecture et la recherche web sont notées par un juge Opus en aveugle (sur 10).

| Tâche | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 | Écart de coût de Sonnet par rapport à Opus |
|---|---|---|---|---|
| Revue d'un commit (lecture seule) | 0,03 $ ; 14 constats, les plus précis (preuves tirées des runs) | 0,50 $ ; 15 constats | 0,67 $ ; 15 constats | −25 % |
| Implémentation multi-fichiers | 0,06 $ ; version minimale, oublie des cas | 1,01 $ ; même conception qu'Opus | 2,25 $ | −55 % |
| Spec d'une story transverse | 6,2 ; 0,07 $ ; couches violées, signature cassée | 8,0 ; 1,86 $ ; la plus exacte sur le code | **8,4** ; 2,77 $ | −33 % |
| Note d'architecture | 7,0 ; 0,05 $ | 7,5 ; 0,62 $ | **8,5** ; 1,12 $ ; seul à voir un conflit entre documents | −45 % |
| Recherche web pour une décision | 6,4 ; 0,02 $ ; cause manquée, erreurs factuelles | 7,8 ; 0,57 $ | **8,4** ; 0,69 $ ; aucune erreur | −17 % |

**Nuances apportées au banc ci-dessus :**
1. **Sonnet ne coûte pas la moitié d'Opus à la tâche**, mais de 17 % à 55 % de moins. Le premier poste, la lecture du cache, coûte le même prix chez les deux (0,20 $/Mtok). L'économie de Sonnet vient surtout du nombre de tours (33 appels contre 57 en implémentation), pas du prix du token.
2. **La recherche n'est pas une seule catégorie.** Haiku est exact pour un lookup dans le dépôt (banc ci-dessus). Pour une synthèse de sources web qui fonde une décision, il se trompe, et Opus vaut son surcoût.
3. **Architecture et spec transverse** : Opus garde une avance nette en architecture. En spec, l'avance est plus faible, mais il est le plus fidèle aux contraintes ; Sonnet est le plus exact sur le code existant.
4. **Gravité en revue** : Opus classe mieux que Sonnet (2 « high » contre 0), mais Haiku a aussi classé « high » 3 défauts réels. La réunion Sonnet plus Haiku reste le meilleur rapport qualité-prix.
5. **Le parallélisme accélère la dépense sans la grossir** : jusqu'à 11 agents simultanés n'ont pas augmenté le coût par tâche. La baisse de 40 % du mode économique vient surtout de la passe de revue unique.

### Premier lot en conditions réelles : agents `dev-story` puis `reviewer` (story 6.10-b, 2026-10-13)

Le lot corrigeait les trois constats reportés de la 6.10 : 19 fichiers, +459 lignes, avec un changement additif des contrats. L'orchestrateur, Opus 5.5 en effort medium, a appelé directement les deux agents, sans skill BMAD. Coût mesuré avec `outils/cout_sous_agents.py --ttl 1h` :

| Agent | Modèle | Appels | Écriture cache | Lecture cache | Durée | Coût |
|---|---|---|---|---|---|---|
| `dev-story` | Sonnet 5.5 | 97 | 157 k | 11,2 M | 18 min | 2,90 $ |
| `reviewer` | Sonnet 5.5 | 11 | 46 k | 0,56 M | 6 min | 0,30 $ |
| **Total** | | | | | | **3,20 $** |

- **La lecture du cache fait 77 % du coût de `dev-story`** (2,24 $ sur 2,90 $). Le coût suit le nombre de tours : 97 appels pour une story de taille moyenne.
- **La revue unique en Sonnet a payé** pour 0,30 $ : 3 constats medium réels corrigés (une trace d'échec qui fuyait d'une classification à la suivante, un filtrage par tâche manquant, la borne des relances annulée quand le préchauffage échouait). Elle a aussi relancé la suite complète, que `dev-story` n'avait pas refaite après son dernier correctif.
- **Le hook de contrôle rapide s'est bien déclenché** à la fin de `dev-story`.
- **`dev-story` a encore attendu en arrière-plan** (une commande en arrière-plan, suivie par `Monitor`) malgré la consigne. Il a renvoyé trois fois le même rapport à la fin de chaque attente, et l'orchestrateur a dû l'arrêter (`TaskStop`). Le coût est faible, mais le risque est réel : l'agent pouvait reprendre dans le worktree pendant la revue. Il faut l'interdire explicitement dans l'agent (`disallowedTools: Monitor`) ou dans sa consigne.
- Les tokens de sortie relevés dans les transcriptions paraissent sous-estimés (moins de 3 k pour 97 appels). Leur poids dans le coût reste faible.

## 3. Routage recommandé

| Rôle | Modèle | Effort | Pourquoi |
|---|---|---|---|
| Orchestration, architecture, PRD, découpage en stories, debug difficile | Opus 5.5 | medium, ou high pour ce qui touche plusieurs couches | les décisions s'y propagent partout |
| Spec d'une story transverse ou à risque (coût, sécurité, données) | Opus 5.5 | medium | il est le plus fidèle aux contraintes |
| Spec d'une story courante | Sonnet 5.5 | medium | spec concrète, pour moins cher |
| Implémentation d'une story bien cadrée | Sonnet 5.5 (agent `dev-story`) | medium | qualité équivalente, moitié prix ; si Sonnet échoue deux fois, reprendre avec Opus |
| Revue courante | Sonnet 5.5 (agent `reviewer`), plus Haiku 5.5 en second avis en lecture seule | medium | la réunion des constats coûte peu |
| Revue d'un commit à risque (argent, sécurité, données personnelles) | Opus 5.5 | medium | il juge mieux la gravité |
| Lookup dans le dépôt, lecture de logs | Haiku 5.5 (agent `lookup`) ou Sonnet | low | réponse exacte pour presque rien |
| Recherche web qui fonde une décision | Opus 5.5 | medium | Haiku y fait des erreurs factuelles ; Opus coûte à peine plus que Sonnet |

## 4. Ce qui a été mis en place dans ce dépôt (à copier dans les autres projets)

- **Agents** dans `.claude/agents/` :
  - `dev-story` : Sonnet, effort medium. Il n'a pas le droit de lancer des sous-agents (`disallowedTools: Agent, Workflow`), ce qui rend le problème d'arrière-plan impossible. Il a un hook `Stop` de contrôle rapide.
  - `reviewer` : Sonnet, effort medium, sans sous-agent non plus.
  - `lookup` : Haiku, effort low, en lecture seule.
  - Ces agents ne sont chargés qu'au démarrage d'une session. Pour un essai, on change de modèle avec le paramètre `model` de l'outil Agent.
- **Contrôle rapide** `outils/controle_rapide.py` : ruff, format, mypy et import-linter en environ 10 s. Il n'affiche que les erreurs, et sort avec le code 2 en cas d'échec, pour que le hook renvoie la main à l'agent.
  - En mode hook, il contrôle les worktrees en cours de travail, de préférence celui que l'agent nomme dans son dernier message, pour que des agents en parallèle ne se bloquent pas entre eux.
  - Il bloque au plus deux fois par agent, pour éviter une boucle.
  - La suite pytest complète tourne une seule fois, avant l'intégration.
- **Coût réel** : `outils/cout_sous_agents.py` (repris du projet slm). Il calcule le coût d'un sous-agent en équivalent API, par catégorie de tokens (entrée, écriture du cache, lecture du cache, sortie), à partir de sa transcription.
- **Réglages du projet** (`.claude/settings.json`) :
  - `"subagentPromptCacheTtl": "1h"`, pour que le cache tienne pendant la durée des tests ;
  - `env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH = "2"`, pour limiter l'imbrication des sous-agents.
- **Réglage local** (`.claude/settings.local.json`, non versionné) : `"syncClaudeAiSkills": false`. Il masque, pour ce projet seulement, les skills synchronisés depuis claude.ai : leurs descriptions étaient renvoyées à chaque tour, et dans chaque sous-agent.
- **Consignes de story inspirées de Spotify**, dans le prompt de `dev-story` :
  - une seule modification par story ;
  - décrire l'état final voulu, les préconditions et les fichiers attendus ;
  - au plus 3 cycles de correction sur un même échec, puis un rapport `bloque`.
- **Méthode de l'orchestrateur** :
  - au plus 2 agents en parallèle ;
  - `dev-story`, puis `reviewer`, lancé par l'orchestrateur avec un appel qui attend son résultat ;
  - intégration (fusion, sprint status, journal) faite par l'orchestrateur ;
  - push seulement quand tout est vert.

## 5. Pratiques externes retenues

- **Spotify** (agent de migration « Honk », [partie 2](https://engineering.atspotify.com/2025/11/context-engineering-background-coding-agents-part-2), [partie 3](https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3)) :
  - peu d'outils par agent ;
  - un seul changement par prompt, en décrivant l'état final voulu ;
  - une vérification déterministe (build, tests, format) dans un hook de fin, qui ne remonte que les erreurs utiles ;
  - un juge LLM seulement ensuite, contre le dépassement de périmètre.
- **Anthropic** ([système multi-agents](https://www.anthropic.com/engineering/multi-agent-research-system), [documentation des coûts](https://code.claude.com/docs/en/costs)) :
  - un gros modèle qui orchestre et des sous-agents plus petits ;
  - des règles explicites sur le nombre de sous-agents, pour éviter d'en lancer trop sur des tâches simples ;
  - mesurer avec `/usage`.
- **Sources secondaires** (blogs, à prendre avec prudence) :
  - le coût d'une session croît plus vite que le nombre de tours ;
  - plafonner la taille de la sortie des outils ;
  - suivre le coût par story fusionnée avec `ccusage`.

## 6. Pièges à connaître

- **Cache** : un changement de modèle invalide le cache, mais pas un changement d'effort avec les modèles 5.5. Modifier CLAUDE.md en cours de session ne l'invalide pas non plus, mais la modification ne s'applique qu'après `/clear`.
- **Hooks** : les ajouter au milieu d'une session peut être refusé par le mode auto, comme modification de la configuration de l'agent. Il faut les écrire, puis redémarrer et les approuver avec `/hooks`.
- **Sous-agents sur Windows** : le répertoire de travail est réinitialisé entre deux commandes. Il faut toujours passer des chemins absolus de worktree, et avoir fait `uv sync` dans chaque worktree.
- **Budget d'API LLM de l'application** (distinct des crédits Claude Code) :
  - annoncer un plafond par API, 1 € par exemple ;
  - estimer le coût avant tout appel réel ;
  - compter aussi le coût des appels qui échouent (bug trouvé dans ce projet).

## 7. Mesurer dans un nouveau projet

1. Noter `/usage` avant et après chaque run.
2. Compter les tokens de chaque sous-agent, affichés à la fin de chaque agent, story par story. Pour le coût réel, lancer `uv run python outils/cout_sous_agents.py --session <dossier de session> --ids <id>`. Ce total mélange en effet des tokens dont le prix varie de 1 à 100.
3. Comparer le coût par story fusionnée et le taux de réussite au premier passage, avant et après chaque changement de méthode.
