# Revue croisée : réponse du projet jira

> **Statut** : réponse du 2026-10-13 au document `wavelocalai/docs/revue-croisee-couts-agents.md`, rédigée depuis `usine-migration-jira-demo`.
> **Méthode** : recalcul gratuit sur les transcriptions du projet. Aucun nouveau banc n'a été lancé.
> - **Corpus** : 463 sous-agents, 11 sessions, du 2026-10-10 au 2026-10-13, soit **593 $** en équivalent API.
> - **Calcul du coût** : somme par réponse dédoublonnée (`message.id`), avec la méthode du § 7 de wavelocalai.
>   - Mêmes prix.
>   - Écriture du cache répartie entre 5 minutes et 1 heure d'après `usage.cache_creation`.
>   - Sortie réestimée selon W12 : maximum entre `output_tokens` et le nombre de caractères émis (blocs `text`, `thinking`, `input` des `tool_use`) divisé par 3,2.
> - **Expiration** : écriture de plus de 20 k tokens après une pause de plus de 5 minutes, ou de plus d'une heure.
> - **Contrefactuel du TTL** : quand une pause dépasse le TTL simulé mais pas le TTL réel, la lecture devient une écriture. Dans le cas inverse, le contexte de l'appel précédent devient une lecture.
> - **Coût d'une story** : l'agent de profondeur 1 qui porte la story, plus ses descendants (`parentAgentId`).
> - **Hors périmètre** : la session principale de l'orchestrateur n'est pas comptée.

## Repères sur le projet

| Période | Organisation | Stories | Coût moyen d'une story | Coût médian |
|---|---|---|---|---|
| Run 1 (2026-10-12, matin et après-midi) | 7 lanes en parallèle, agent de story Opus qui invoque `bmad-build-auto` (implémenteur et 4 relecteurs), revues de suivi | 40 | **9,18 $** | 7,57 $ |
| Run 2, dit « mode économique » (2026-10-12 soir, nuit du 13) | 2 agents en parallèle, effort medium, **un seul relecteur** (Edge Case Hunter), **imbrication conservée** | 22 | **5,24 $** | 4,86 $ |
| Story 6.10-b (2026-10-13) | orchestrateur, puis agent `dev-story` Sonnet, puis agent `reviewer` Sonnet, sans agent intermédiaire, cache d'une heure | 1 | 3,41 $ (dont 0,34 $ de revue) | — |

## Grille

| Constat | Verdict | Mes chiffres | Niveau de preuve et nombre d'essais | Trait du projet qui explique l'écart |
|---|---|---|---|---|
| W1 relecture du contexte | **Confirmé** | Sur 593 $ : écriture du cache 46 %, lecture 39 %, sortie 15 %, entrée hors cache 0 %. Relecture du contexte : 85 %, comme slm. | Mesuré, 463 agents | Même profil que wavelocalai : des agents Opus longs, avec 50 à 150 appels. |
| W2 agent intermédiaire | **Confirmé, et plus fort** | L'agent de story pèse **45 %** du coût des stories du run 1 (166 $ sur 367 $), et **62 %** dans le run 2 (72 $ sur 115 $), soit 4,16 $ puis 3,26 $ par story. L'implémenteur pèse 30 % puis 21 %, les relecteurs 22 % puis 7 %. Sans agent intermédiaire, la 6.10-b a coûté 3,41 $. | Mesuré, 62 stories ; un seul point après la suppression (et sur Sonnet, donc avec un modèle différent) | Le mode économique a réduit les relecteurs, mais il a **gardé l'agent intermédiaire**. Sa part a donc monté. |
| W3 contexte × appels | **Confirmé** | Sur les 257 agents de plus de 0,50 $, le coût suit le produit pic × appels (corrélation **r = 0,96**) ; le nombre d'appels seul donne r = 0,91. Le pic d'une story va de 110 à 390 k, avec une médiane d'environ 200 k, proche de slm. Les stories les plus chères ont les plus gros pics : 5.3 (19,93 $, 239 appels, 363 k), 4.5 (16,55 $, 371 k), 0.9 (12,64 $, 148 appels, 386 k). | Mesuré, 257 agents | Pics plus bas que dans wavelocalai : les agents lisent des extraits des epics et le fichier de contexte de l'epic, pas tout le spine. |
| W4 cache d'une heure | **Confirmé**, avec un seuil un peu plus bas | Run 1 (cache de 5 min) : **68 expirations pour 287 agents (0,24 par agent)**, environ 1,7 par story. 365 agents sur 444 n'en ont aucune. Contrefactuel d'une heure : **+9 %** sur le run 1 (367 $ contre 402 $), +10 % sur tous les agents en cache de 5 min (587 $ contre 645 $). Par nombre d'expirations par agent : 0 → **+29 %**, 1 → **−2 %**, 2 → −8 %, 4 et plus → −45 %. Après le passage à une heure (6.10-b) : 0 expiration, et un coût de **+6 %** par rapport au cache de 5 min. | Mesuré par recalcul contrefactuel, 444 agents ; même limite que wavelocalai (préfixe supposé intact) | La suite de 4 à 5 minutes provoquait rarement une expiration : la plupart des pauses restaient sous 5 minutes. Les expirations se concentrent sur les longues attentes du réel (Jira réel, téléchargement Zenodo, reprises), soit 8 à 10 par agent dans les stories 1.6 et 4.3. |
| W5 effort en implémentation | **Non mesurable** | Aucun banc ne fait varier l'effort. Seul indice, non contrôlé : la part des appels en effort high passe d'environ 26 % (run 1) à environ 4 % (run 2). | — | Le banc du 13 octobre comparait les modèles, pas les efforts. |
| W6 Opus low contre Sonnet high | **Non mesurable** | — | — | Idem. |
| W7 revue et défauts liés au réel | **Nuancé** | Commit relu : `22d7079` (story 6.10). Vérité terrain : 4 défauts corrigés ensuite (6.10, puis 6.10-b). D1 coût d'un échec hors plafond ; D2 aucune trace d'échec ; D3 relances du préchauffage non bornées ; D4 faux vert de `balayer_sm7` (espaces insécables, trace vide). **Opus : 4 sur 4** (D4 en partie : trace vide, classé low), 0,68 $. **Sonnet : 3 sur 4** (D4 manqué), 0,22 $. **Haiku : 4 sur 4** (D4 vérifié en exécutant du code), 0,02 $. La réunion Sonnet et Haiku trouve les 4. **Seul Opus classe D1 en high** ; les deux autres le classent medium. Défaut échappé aux trois : `executer_agent`, hors du diff. | Mesuré, un essai. **Vérité terrain en partie circulaire** : le tri d'origine s'appuyait déjà sur ces trois revues. | D1 dépend d'un comportement réel non simulé : le fournisseur facture les appels qui échouent, alors que la doublure de test échouait sans rien coûter. Mais le défaut **se voit à la lecture du code**. L'écart entre modèles porte alors sur la **gravité**, pas sur la **détection**. |
| W8 Opus en conception | **Confirmé en partie** | Spec d'une story bonus : Haiku 0,04 $, Sonnet 0,53 $, Opus 1,23 $. Jugement de l'orchestrateur, sans juge en aveugle : Opus est le plus fidèle aux contraintes, Sonnet le plus concret, Haiku juste. Architecture et recherche web : non mesurées. | Observé, un essai, sans juge en aveugle | Sonnet n'y est pas derrière Haiku, contrairement à W8. |
| W9 nombre de tours | **Nuancé** | Appels Haiku / Sonnet / Opus, puis écart de coût de Sonnet par rapport à Opus. Implémentation : 21 / **10 / 10**, −45 %. Revue : 12 / 8 / 13, −68 %. Spec : 17 / 13 / 21, −57 %. Recherche dans le dépôt : 7 / 5 / 4, −44 %. | Mesuré, un essai par case | À nombre d'appels égal, l'écart vaut à peu près le rapport des prix (−45 %, et non −50 %, car la lecture du cache coûte le même prix). Il ne dépasse 50 % que quand Opus fait plus de tours. |
| W10 variance de Haiku | **Non mesurable** (un essai) | Implémentation : correcte, 0,02 $, mais **21 appels**, deux fois plus que Sonnet et Opus. Il a aussi lancé ses tests en arrière-plan malgré la consigne. | Observé, un essai | Le défaut observé concerne le respect du processus, pas la qualité du code. |
| W11 contexte fixe | **Confirmé** | Premier appel d'un agent `general-purpose` : 38,2 à 39,4 k jusqu'au 2026-10-13 à 05 h 46, puis **34,1 k à 05 h 52 (−4,8 k)**. Cette baisse précède le commit des agents et du cache (07 h 46). Elle coïncide avec `syncClaudeAiSkills: false`, un réglage local non versionné. Les agents `dev-story` et `reviewer`, avec moins d'outils, partent de 32,2 à 32,6 k (−1,2 k de plus) ; `lookup` part de 7,5 k. Gain : 4,8 k × environ 100 lectures par story × 0,20 $ par Mtok ≈ **0,10 $ par story, environ 2 %**. | Mesuré sur 463 premiers appels ; attribution au réglage : observée (horaire), non prouvée | Les contextes de travail (150 à 250 k) écrasent ce gain. |
| W12 sortie sous-comptée | **Confirmé, plus fort chez moi** | Médiane par agent du rapport entre sortie comptée et sortie estimée : **0,08 à 0,10 chaque jour**, y compris le 10 octobre (wavelocalai trouvait 1,01 ce jour-là ; la méthode d'agrégation diffère sans doute). Effet : 531 $ → **593 $ (+12 %)**. Sur le banc, la correction ajoute 4 à 18 %, surtout en spec (+18 %), mais les écarts entre Sonnet et Opus ne bougent pas. | Mesuré, 463 agents ; borne basse (réflexion masquée) | La sortie pèse 15 % du coût : la rédaction de specs et les rapports longs sont les plus touchés. |

## Réponses aux questions adressées à jira (§ 5)

1. **Coût en dollars.** Voir W1 et W12 pour l'ensemble des 593 $.
   - Banc du 13 octobre recalculé (Haiku / Sonnet / Opus) :
     - implémentation 0,02 / 0,27 / 0,49 $ ;
     - revue 0,02 / 0,22 / 0,68 $ ;
     - recherche 0,01 / 0,10 / 0,18 $ ;
     - spec 0,04 / 0,53 / 1,23 $.
   - Le compte de tokens affiché dans le retour d'expérience donnait le bon ordre de grandeur, pas les rapports.
2. **Cache d'une heure.** Avant ce réglage, on comptait 0,24 expiration par agent et environ 1,7 par story. Avec un cache d'une heure partout, le coût aurait été **10 % plus élevé**.
   - Après le réglage, la 6.10-b coûte 6 % de plus qu'avec le cache par défaut.
   - **Le réglage d'une heure n'est pas rentable dans ce projet.** Il faudrait revenir au TTL par défaut, et ne le rallonger que pour les runs à longues attentes (Jira réel, gros téléchargements).
   - Le seuil de rentabilité se situe **entre 1 et 2 expirations par agent**, au lieu d'environ 2 dans W4.
3. **Décomposer la baisse de 40 %.** Le coût moyen d'une story passe de 9,18 $ à 5,24 $ (−43 % ; −36 % en médiane). Les 3,94 $ de baisse se répartissent ainsi :
   - **relecteurs, passés de 4 à 1 : 1,68 $ (43 %)** ;
   - implémenteur : 1,30 $ (33 %) ;
   - agent intermédiaire : 0,90 $ (23 %) ;
   - divers : 0,07 $.

   Sur le run 1, les revues de suivi et les reprises d'agents partis en arrière-plan coûtaient 0,84 $ par story (9 %), contre 0,06 $ dans le run 2. Ce montant est déjà réparti entre les rôles ci-dessus.

   La part de la **fin de l'imbrication est nulle** : le run 2 imbriquait encore les agents, et la suppression n'est venue que le 13 octobre.

   Effort medium et parallélisme réduit : leur effet n'est pas séparable. Il se lit en partie dans la baisse de l'implémenteur et de l'agent intermédiaire, mais les stories diffèrent aussi d'un run à l'autre (epics 1 à 5, puis 6 et 7).

   Le nombre d'expirations par story ne change pas (1 à 2), ce qui va dans le sens de slm : le parallélisme ne fait pas grossir le coût.
4. **Contexte fixe.** Voir W11 : −4,8 k entre 05 h 46 et 05 h 52 le 13 octobre, attribués à `syncClaudeAiSkills: false` d'après l'horaire, puis −1,2 k pour les agents qui ont moins d'outils.
5. **Revue.** Voir W7. Le défaut de coût dépendait d'un comportement réel non simulé : un appel qui échoue est facturé, alors que la doublure de test ne coûtait rien. Il se lisait pourtant dans le code, et les trois modèles l'ont trouvé. Seul Opus en a mesuré la gravité.
   - **Reformulation proposée de l'hypothèse du § 3** : l'écart de détection entre Opus et les autres se creuse quand le défaut dépend d'un comportement **qu'on ne peut pas déduire du code** (comme `think: false` dans Ollama). Quand le défaut se lit dans le code, l'écart ne porte que sur la gravité.

## Critique du système adaptatif (§ 4)

**Signaux que jira aurait mal classés :**
- **S2, dépendance au réel non simulé, si elle est déclarée.** Jira l'aurait déclarée élevée (API Jira, facturation des fournisseurs LLM, Zenodo), ce qui aurait déclenché une revue Opus partout. Or tous les défauts du banc se lisaient dans le code : Sonnet et Haiku réunis les ont tous trouvés, pour un tiers du prix d'Opus. **S2 doit se mesurer (part des défauts trouvés seulement à l'exécution), pas se déclarer.**
- **S6, durée de la suite de tests.** Une suite de 4 à 5 minutes, lancée 3 à 4 fois par story, laissait présager beaucoup d'expirations. Il y en a eu 0,24 par agent. S6 ne prédit pas S4 : seul S4, mesuré sur les transcriptions, compte.
- **S4 à l'échelle de l'agent.** Le réglage du TTL est global, alors que les expirations sont très concentrées : 82 % des agents n'en ont aucune, et quelques agents qui attendent le réel en ont 8 à 10. La règle « 1 heure si S4 ≥ 2 par agent » doit porter sur la **moyenne des agents pondérée par leur coût**, pas sur les agents qui expirent.
- **S1, criticité.** Le budget LLM de l'application rend le code critique, mais la revue unique en Sonnet de la 6.10-b a trouvé 3 défauts medium réels pour 0,34 $. Une criticité élevée justifie Opus pour **classer la gravité** d'un commit à risque, pas pour chaque story.

**Seuils que ces données permettent de fixer :**
- **Cache d'une heure** : rentable au-delà d'environ **1 expiration par agent en moyenne pondérée par le coût**. En dessous, il coûte jusqu'à 29 % de plus pour les agents qui n'expirent jamais.
- **Contexte** : les stories de plus de 150 appels ou de plus de 250 k de pic coûtent de 10 à 20 $, contre une médiane de 5 à 8 $. Ces deux seuils conviennent pour une alerte de découpage.
- **Agent intermédiaire** : il pèse de 45 à 62 % du coût. Le supprimer est la première économie, devant le choix du modèle.
- **Relecteurs** : passer de 4 à 1 relecteur réduit le coût de la revue de 80 % par story (2,08 $ → 0,40 $). Un second avis Haiku coûte 0,02 $.

**Ce qui manque pour publier :**
- Des essais répétés : chaque case du banc de jira ne compte qu'un essai, et W5, W6 et W10 ne sont pas mesurés ici.
- Une vérité terrain de revue qui ne dérive pas des revues comparées.
- Le coût de l'orchestrateur : la session principale n'est pas comptée ici, alors qu'elle relit aussi les rapports.
- Une version de `cout_sous_agents.py` qui intègre W12, le contrefactuel du TTL, le pic, les appels et les expirations par agent.
  - Les scripts de ce recalcul existent, mais ils n'ont pas été versionnés.
  - Ils étendent `outils/cout_sous_agents.py` et pourraient être fusionnés dans l'outil publié.
- Plus d'un point de mesure après la suppression de l'agent intermédiaire : la 6.10-b seule, sur Sonnet, ne permet pas de séparer l'effet du modèle de celui de l'architecture.
