# PRD Quality Review — Copilote de pilotage d'une usine de migration (démonstrateur)

- **PRD :** `prd.md` (+ `addendum.md`)
- **Rubrique :** `.claude/skills/bmad-prd/assets/prd-validation-checklist.md`
- **Enjeux retenus :** démonstrateur personnel, dépôt public, données fictives, développeur seul (≈ outil interne / portfolio). Décisions utilisateur non contestées : découpage indispensable / bonus, seuils de la Grille, historique via le journal d'événements, classification des Causes racines indispensable, LLM local en bonus.

## Overall verdict

Le PRD est solide sur la thèse (deux Paliers, les chiffres ne passent jamais par le LLM), sur la discipline de périmètre et sur la séparation PRD / addendum. Le risque est ailleurs : plusieurs règles de calcul et de données ne sont pas assez définies pour que l'architecture et les stories avancent sans risque. En particulier, la manière dont le pipeline live sur Jira Cloud reconstitue 8 semaines d'historique n'est pas tranchée, et la Date d'arrêté de la démo contredit la trajectoire de l'Entité A. S'y ajoutent des conflits entre reproductibilité et sorties LLM, et des notions métier non définies (Anomalie « ouverte », entrées / sorties, Phase en cours, catégories de Cause racine). Il faut corriger ces points avant `bmad-architecture`. Le reste est du resserrage de critères d'acceptation.

## Decision-readiness — adequate

Les arbitrages sont écrits comme des décisions datées (« Arbitrage du 10/10/2026 », § 7.1 ; Q-1 tranchée, FR-5). Le compromis central, une valeur découpée en deux Paliers « pour que la demande reste recevable même si la banque refuse tout LLM » (§ 1), est explicite. Les questions ouvertes Q-2 à Q-5 sont réellement ouvertes. Q-6, en revanche, porte déjà sa réponse (« Le PRD inclut les deux »). Q-3 (hystérésis) touche des FR indispensables (FR-16, FR-20, FR-3) sans qu'un comportement par défaut soit écrit.

### Findings
- **low** Q-6 n'est plus ouverte (§ 9) : « Le PRD inclut les deux » tranche la question. *Fix :* la barrer comme Q-1, avec la date de décision.
- **low** Q-3 sans valeur par défaut (§ 9, FR-16, FR-20) : sans hystérésis déclarée, l'architecte ne sait pas si la Météo doit être calculée avec un état. *Fix :* écrire « v1 : pas d'hystérésis, Météo calculée sans état d'un jour à l'autre » dans FR-16.

## Substance over theater — strong

Les trois personas (Pilote, Sponsor, Auteur) pèsent chacun sur des décisions : le Sponsor justifie FR-47 et la Pseudonymisation, l'Auteur justifie le dépôt public. Les NFR ont des seuils propres au produit : 5 min / 10 min, < 1 €, 100 % fictif, contrôle de secrets en CI. Les contre-indicateurs (SM-C1 à SM-C4) sont spécifiques et sincères. Un seul NFR reste à l'état d'adjectif.

### Findings
- **medium** NFR-10 non mesurable (§ 5) : « compréhensibles par un Pilote non développeur » est un adjectif. *Fix :* exiger que chaque message d'erreur de Grille nomme le fichier, la règle et la valeur fautive, et que chaque clé de la Grille porte un commentaire en français (vérifié par test).

## Strategic coherence — strong

La thèse est nette : un reporting quotidien fiable sans LLM, puis un LLM qui explique sans calculer. L'ordre de réalisation (§ 7.3) suit cette thèse (Palier 1 montrable avant tout travail LLM). Les SM valident la thèse, pas l'activité : réconciliation à 100 %, Citations valides, zéro chiffre inventé. Il manque un contre-indicateur sur l'Agent. Rien n'empêche de satisfaire SM-4 (« zéro chiffre inventé ») en faisant refuser l'Agent par excès de prudence.

### Findings
- **medium** Pas de contre-indicateur pour SM-4 (§ 8) : un Agent qui répond « données insuffisantes » trop souvent obtient « zéro chiffre inventé » sans être utile. *Fix :* ajouter SM-C5 « Taux de refus de l'Agent sur des questions répondables : au plus 1/15 », qui contrebalance SM-4.
- **low** SM-C1 « contrebalance SM-3, SM-4 » (§ 8) : le lien est flou, car ajouter des fonctions LLM ne dégrade pas directement SM-3 ou SM-4. *Fix :* reformuler en contrepoids de la thèse (« le Palier 1 seul reste convaincant ») ou le rattacher à SM-2 / SM-5.

## Done-ness clarity — thin

Beaucoup de FR ont une conséquence testable et précise : FR-6, FR-13, FR-14, FR-18, FR-24, FR-31, FR-32. Plusieurs FR indispensables restent pourtant intestables ou contradictoires avec d'autres exigences. C'est la dimension où les stories vont buter.

### Findings
- **critical** Historique et pipeline live incompatibles (FR-5, FR-6, FR-8, FR-10, FR-12, UJ-1, UJ-4) : Jira Cloud ne porte que l'état courant. Pourtant UJ-1 et UJ-4 lancent le pipeline « en direct sur Jira Cloud » et attendent la Météo J-7 et des Tendances sur 8 semaines. FR-10 promet un Instantané « pour toute Date d'arrêté… y compris passée ». FR-8 parle de « dates communes » sans dire lesquelles. Aucun FR ne dit comment le journal d'événements et le delta Jira se combinent. *Fix :* ajouter un FR « Source composite » : historique = journal d'événements jusqu'à la date d'injection, puis changelog Jira au-delà. Définir les « dates communes » de FR-8 comme les dates postérieures ou égales à l'injection.
- **high** La Date d'arrêté de la démo contredit FR-3 (UJ-4, FR-3, FR-20, SM-6) : A « revient à l'orange en semaine 5 » sur 8 semaines d'historique, donc A n'est plus rouge en fin d'historique. Or UJ-4 montre « A rouge… sort probablement sous 10 jours ouvrés », et FR-20 / SM-6 exigent « A sort dans l'horizon ». C, lui, est évalué « en fin d'historique ». *Fix :* préciser la Date d'arrêté de chaque vérification (par ex. A et B évalués en semaine 4, C en fin d'historique), ou décaler la trajectoire de A pour qu'elle soit rouge à la date de démo.
- **high** FR-2 : reproductibilité contradictoire avec les textes générés par LLM (FR-2, NFR-3) : « Deux exécutions avec la même graine produisent des données identiques » est impossible si les titres et descriptions sont générés à chaque fois par un LLM. *Fix :* générer les textes une seule fois, les versionner dans le dépôt comme corpus, et limiter la garantie de graine à la structure, aux dates et aux affectations.
- **high** FR-14 : rejeu idempotent contradictoire avec le Palier 2 : le Rapport quotidien contient des Explications sourcées et des Brouillons non déterministes, donc « identiques à l'exception de l'horodatage » ne tient pas en Palier 2. *Fix :* limiter FR-14 au Palier 1, ou exiger la réutilisation des sorties LLM mises en cache par (Date d'arrêté, Entité, versions de prompt / modèle / données).
- **high** FR-35 (Classification) incompatible avec NFR-2 et NFR-9 : classer « chaque Anomalie » (3 000 à 5 000) avec un LLM distant dépasse vraisemblablement 10 minutes et 1 € par passage, surtout avec les limites de débit des offres gratuites. *Fix :* classer seulement les Anomalies nouvelles ou modifiées depuis le dernier passage, avec cache. Préciser si la classification initiale est hors budget NFR-2 / NFR-9.
- **high** Statuts non définis : Anomalie « ouverte », « entrée », « sortie » (FR-11, IND-1, IND-7, FR-13, FR-20) : la réconciliation à 100 % suppose une correspondance statut → ouverte / fermée, et une définition des entrées (création ? réouverture ?) et des sorties (résolution ? clôture ? rejet ?). Rien de cela n'est écrit. *Fix :* ajouter au Glossaire « Anomalie ouverte », « Entrée » et « Sortie » avec la liste des statuts Jira du Programme fictif et le traitement des réouvertures.
- **medium** FR-3 : « majoritairement vertes ou jaunes » est intestable (FR-3). *Fix :* « hors A, B, C, aucune Entité n'est rouge plus de 3 Jours ouvrés consécutifs, et au moins 80 % des couples Entité × Date d'arrêté sont verts ou jaunes ».
- **medium** FR-32 : une Citation est impossible pour certaines règles (FR-17, FR-32) : FR-17 ne restitue des tickets que pour IND-1, 2, 3, 5 et 6. Une Entité orange par IND-4, IND-7 ou IND-8 (cas de C) n'a pas de tickets fournis, alors que FR-32 exige une Citation par phrase. *Fix :* étendre FR-17 aux Cas de test KO (IND-4, IND-8) et aux Anomalies entrées sur 7 jours (IND-7). FR-32 doit alors accepter ces tickets, y compris les Anomalies fermées comptées dans les sorties.
- **medium** FR-20 : rouge multi-règle (FR-20, Glossaire « Prévision de sortie du rouge ») : le Glossaire définit la sortie comme l'absence de toute Règle déclenchante rouge, mais FR-20 ne projette qu'IND-1. Le comportement n'est pas défini si le rouge vient à la fois d'IND-1 et d'IND-2. *Fix :* produire une date seulement si toutes les Règles déclenchantes rouges sont projetables, sinon afficher « règle non projetable : IND-x ».
- **medium** FR-27 et FR-43 sans conséquence testable. *Fix :* FR-27 « les 7 sections sont présentes, une slide par Entité rouge ou orange, chiffres identiques aux Instantanés (test) » ; FR-43 « chaque écran est atteignable en 1 clic depuis la carte météo ; la progression affiche chaque étape de FR-25 ».
- **medium** Cas limite d'UJ-1 absent des FR (UJ-1, FR-25) : « la commande s'arrête… ne produit pas de rapport partiel » n'est porté par aucun FR. FR-25 n'énumère pas non plus les étapes LLM (classification, Explication, Brouillon) quand un LLM est configuré. *Fix :* ajouter à FR-25 « échec d'une étape : code de sortie non nul, message explicite, aucun fichier de rapport écrit », et la liste des étapes Palier 2.
- **medium** FR-42 : critère de « réponse correcte » non défini (FR-42, SM-4) : qui juge et comment (correspondance exacte, éléments attendus, LLM juge, humain) ? FR-40 (« l'Agent le dit ») n'est testable que si la suite contient des questions sans réponse possible. *Fix :* chaque question porte des éléments attendus (chiffres, Entités, tickets) vérifiés automatiquement, et la suite inclut au moins 2 questions sans réponse possible.
- **medium** FR-13 : Rapport de référence de taille non bornée (FR-13, Glossaire) : un calcul « à la main » sur 5 000 Anomalies n'est pas réaliste, et l'Instantané figé n'est pas défini. *Fix :* fixer un jeu figé réduit (par ex. 2 Entités, environ 60 tickets, 1 Date d'arrêté) couvrant chaque Indicateur de météo et chaque garde-fou.
- **medium** FR-30 : « les limites de débit sont respectées » n'est pas testable. *Fix :* « sur réponse de dépassement de débit, reprise avec attente croissante, au plus N tentatives ; testé avec une doublure ».
- **medium** SM-5 : « sans accroc » n'est pas mesurable (§ 8). *Fix :* « au moins 3 répétitions chronométrées de 10 min au plus, dont 1 en mode repli, sans intervention hors script ».
- **low** FR-22 : AUC de la Baseline non défini, N non fixé (bonus) : la Baseline produit une date, pas une probabilité. *Fix :* définir N et la probabilité de référence (par ex. le taux historique de résolution sous N jours).
- **low** UJ-2 : le signalement d'une phrase retirée n'est pas dans FR-32 (« le contrôle la retire… et le signale »). *Fix :* ajouter à FR-32 « le nombre de phrases retirées est affiché et journalisé ».
- **low** IND-8 : calcul ambigu (« hausse… sur 7 jours glissants ») et pas de garde-fou de volume, contrairement à IND-4. *Fix :* « taux de KO à J moins taux de KO à J-7, évalué seulement si IND-4 est évaluable aux deux dates ».

## Scope honesty — strong

Les Hors objectifs (§ 6) sont précis et utiles : pas d'ordonnanceur, pas d'écriture Jira, pas de Météo forcée. Le marquage [INDISPENSABLE] / [BONUS] est systématique et le § 7 le reprend sans écart. Les hypothèses sont balisées et indexées, ce qui donne une densité d'éléments ouverts raisonnable pour ces enjeux. Seul point : le mode repli et NFR-12 promettent plus que ce qui est spécifié.

### Findings
- **high** Démo sans réseau mais Agent et LLM non couverts (NFR-12, FR-45, UJ-4) : NFR-12 promet une démo « de bout en bout sans réseau ». Or l'Agent (FR-39 à FR-42) et la Comparaison Palier 1 / Palier 2 (FR-46) exigent un LLM distant, et le LLM local est en bonus (FR-37). Ce que « rejouer » veut dire pour l'Agent n'est pas dit. *Fix :* définir le repli de l'Agent (rejeu d'une conversation enregistrée pour la question de démo, signalée comme telle), ou réduire NFR-12 à « Palier 1 et contenus Palier 2 déjà générés ».

## Downstream usability — thin

Les identifiants FR, NFR, SM, UJ et H sont contigus et uniques, et le Glossaire est riche. Il est pourtant contourné par des noms de domaine non définis, centraux pour l'architecture. La règle « Le vocabulaire du § 3 est le seul autorisé » (§ 0) n'est donc pas respectée.

### Findings
- **high** Catégories de Cause racine non définies (Glossaire, FR-2, FR-35, SM-9) : le F1 macro ≥ 0,8 dépend du nombre et de la nature des classes, et le générateur doit les connaître. *Fix :* lister les catégories dans le Glossaire, par exemple reprise de données, paramétrage, interface, code applicatif, environnement, donnée de test.
- **medium** « Phase en cours » et « Vague en cours » non définies (IND-4, IND-5, IND-6) : comment détermine-t-on la Phase en cours d'une Entité à une Date d'arrêté ? *Fix :* ajouter au Glossaire « Phase en cours = Phase du calendrier de la Vague de l'Entité qui contient la Date d'arrêté » (idem pour Vague en cours).
- **medium** « 7 jours glissants » contre « Jours ouvrés » (FR-11, IND-7, IND-8, FR-19, UJ-3) : on ne sait pas si la fenêtre est calendaire ou en Jours ouvrés. De plus, J-7 « en Jours ouvrés » (FR-19) vaut près de 1,5 semaine. *Fix :* définir « Fenêtre glissante = 5 Jours ouvrés » (ou 7 jours calendaires) et l'employer partout. Choisir J-5 ouvrés ou J-7 calendaires pour FR-19.
- **medium** Termes métier hors Glossaire : « journal d'événements » (FR-5, FR-8), « passage » / « dernier passage » (FR-6, FR-44, FR-45, UJ-4), « Prévision » seule (FR-23, FR-34, NFR-1), « modèle ML » (FR-22, Baseline), « pipeline » / « chaîne » (FR-43, FR-44, UJ-4) en synonyme de la « commande » de FR-25. *Fix :* ajouter « Journal d'événements », « Passage », « Prévision » et « Modèle ML » au Glossaire, et remplacer « pipeline » / « chaîne » par un seul terme défini.
- **medium** « Rejeu » a deux sens : FR-14 désigne un recalcul, FR-45 l'affichage d'un passage enregistré. *Fix :* garder « rejeu » pour FR-14 et nommer FR-45 « Mode repli : affichage du dernier Passage enregistré ».
- **low** Synonymes « Explication du rouge » (§ 7.1, titre de FR-32) et « Explication sourcée » : FR-32 couvre aussi l'orange. *Fix :* titrer FR-32 « Explication sourcée » et l'employer au § 7.1.
- **low** Fuites techniques mineures dans les FR : « API v3 » / « API v2, jeton personnel » (FR-6, FR-7), « empreinte du fichier » (FR-15), « valeurs SHAP » (FR-23), « Langfuse » (FR-38), « variables d'environnement » (NFR-4). Elles restent acceptables comme contraintes d'intégration. *Fix :* garder les versions d'API comme contraintes, et déplacer l'empreinte, SHAP et le mécanisme des secrets dans l'addendum, avec une formulation fonctionnelle dans le PRD.

## Shape fit — adequate

C'est un outil mono-opérateur, et la forme spécification de capacités domine, ce qui est juste. Les quatre UJ sont justifiés parce que la démo est le livrable, et chaque UJ a un protagoniste nommé. Le PRD alimente UX, architecture et stories, donc la traçabilité compte. D'où le verdict « thin » sur l'utilisabilité en aval.

### Findings
- **low** NFR-2 et NFR-6 : références floues. Le « poste de développement » n'est pas caractérisé, et NFR-6 parle de « versions… de données » sans définition. *Fix :* préciser la machine de référence (CPU, RAM) et définir la version de données (empreinte du journal d'événements ou horodatage d'extraction).

## Mechanical notes

- Aller-retour de l'index des hypothèses : H-5, H-12 et H-16 sont indexées mais sans balise inline (FR-5, FR-35 et § 7.1 portent la décision en prose). Ajouter les balises ou signaler qu'elles sont closes dans l'index.
- Renvois des SM : SM-1 devrait aussi valider FR-26 (chiffres du classeur), SM-3 devrait valider FR-33. Aucun SM ne couvre FR-24 (narration) ni FR-8 (équivalence des sources). C'est acceptable, mais à noter.
- FR-20 : l'énumération « (IND-2, IND-5…) » se termine par des points de suspension. Écrire « toute règle autre qu'IND-1 ».
- UJ-2 : « un clic ouvre le ticket dans Jira » n'est pas disponible en mode repli sans réseau (NFR-12). À mentionner dans FR-45.
- Les seuils de l'addendum D (fractions) et du § 4.4 (pourcentages) sont cohérents.
- `docs/QUESTIONS.md` existe.
- Les identifiants FR-1 à FR-48, NFR-1 à NFR-12, SM-1 à SM-9, SM-C1 à SM-C4, UJ-1 à UJ-4 et H-1 à H-16 sont contigus et uniques.

## Décompte

- Critical : 1
- High : 7
- Medium : 15
- Low : 9
