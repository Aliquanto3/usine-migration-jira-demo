# Script de la démo de 10 minutes (UJ-4)

Démo de l'usine de migration au Sponsor, écran par écran de l'interface web (`uv run usine ui`, puis http://127.0.0.1:8000).
Story 7.12. Les répétitions se consignent dans [`repetitions.md`](repetitions.md).

**Durée prévue : 9 min 40 s**, soit 20 s de marge sur les 10 minutes.
**Règle :** on suit le script. Tout geste hors script (commande tapée, page rechargée, fichier
ouvert) compte comme une intervention hors script (SM-5).

Les écrans s'ouvrent depuis la navigation latérale : Carte météo, Détail d'une Entité,
Lancement de la Chaîne (`/chaine`), Avant / après, Pseudonymisation, Agent, Ce qu'il faut pour
le faire en vrai. Un clic sur une Entité de la carte ouvre son Détail.

## Chiffres de référence

Seuls ces chiffres sont mesurés. Ne pas en citer d'autres : l'écran fait foi.

| Quoi | Mode normal (Jira Cloud `DEMO`) | Mode repli (`demo/repli/passage/`) |
|---|---|---|
| Passage | `20261012T222702Z-ec5fab` (Story 5.6) | `20261012T221158Z-96c621` |
| Tickets | 3 547 | 3 547 |
| Durée de la Chaîne | 20 s (premier Passage après réinjection ; 9,3 s en incrémental, Story 5.7) | 4,4 s (Journal local) |
| Date d'arrêté | 09/10/2026 | 09/10/2026 |
| Palier | 1 | 1 |
| Temps manuel déclaré | 120 min par Rapport (fictif, `config/demo.yaml`) | idem |

Météo identique dans les deux modes : **ENT-A et ENT-B rouges** (IND-1, Anomalies bloquantes
ouvertes : 4 et 9 pour un seuil de 3), **ENT-C orange** (IND-4, taux de KO des Cas de test),
ENT-D vert, ENT-E à ENT-J jaunes.
Prévision : ENT-A sortie estimée le 13/10/2026 (probabilité 8/16 sous 10 Jours ouvrés) ;
ENT-B aucune sortie projetée ; Risque ENT-C d'entrée en rouge sur IND-4 vers le 14/10/2026.

## Préparation

### La veille

1. Dans le dépôt principal, `git pull` puis `uv sync`.
2. Contrôles : `uv run pytest -q` (vert).
3. Vérification du déroulé, sans réseau : `uv run python outils/verifier_demo.py`. Attendu :
   9 lignes `[OK]`, « déroulé complet », code 0. Un `[KO]` se corrige avant la démo.
4. Mode normal seulement : publier un Passage frais sur `DEMO`
   (`uv run usine rapport --date-arrete 2026-10-09`) pour que l'Avant / après et l'Agent lisent
   un Passage récent. Vérifier que le site Jira Free répond (il se désactive après inactivité).
5. Vérifier que `.env` du dépôt principal porte `USINE_CLE_PSEUDO` (sinon l'écran
   Pseudonymisation affiche une erreur) et, en mode normal, les clés Jira et LLM.

### 15 minutes avant

1. Ouvrir un terminal PowerShell à la racine du dépôt principal.
2. Lancer l'UI :
   - mode normal : `uv run usine ui` ;
   - Mode repli imposé (réseau douteux) : `$env:USINE_MODE_REPLI = "1"; uv run usine ui`.
     La pastille d'en-tête affiche alors « Mode repli ».
3. Le navigateur s'ouvre sur « Carte météo ». Vérifier le bandeau : absent en mode normal,
   « **Mode repli** : la démo lit le Passage enregistré… » en Mode repli.
4. Préchauffer : ouvrir une fois chaque écran dans l'ordre du script, dont Pseudonymisation
   (environ 4 s au premier affichage : chargement du moteur) et Agent. Revenir sur
   « Carte météo ».
5. Mode normal : sur l'écran Agent, ne pas poser de question pendant le préchauffage (appel
   payant) ; vérifier seulement que le champ s'affiche.
6. Fermer les autres onglets, couper les notifications, zoom du navigateur à 125 %.
7. Chronomètre prêt.

### Basculer en Mode repli pendant la démo

Si Jira ou le LLM ne répond pas : ouvrir `/chaine` et cliquer sur **« Passer en Mode repli »** (un clic).
Le bandeau apparaît sur tous les écrans, et la démo continue sur le nouveau Passage. Phrase à dire :
« Le réseau me lâche : je bascule sur le dernier Passage enregistré, signalé comme tel à
l'écran. » Ce clic fait partie du script : ce n'est pas une intervention hors script.

## Déroulé

### 1. Ouverture : 0:00 → 0:30 (30 s)

- **Écran :** Carte météo (écran d'ouverture).
- **Clic :** aucun.
- **Dire :** « Un programme de migration, dix Entités, des milliers de tickets Jira. Chaque
  matin, quelqu'un passe deux heures à en tirer une météo. Je vous montre la même chose en
  une commande. »
- **Plan B (repli) :** identique ; le bandeau Mode repli est visible, le dire en une phrase.

### 2. Avant / après : 0:30 → 1:30 (60 s)

- **Écran :** Avant / après (navigation latérale).
- **Montrer :** le temps manuel déclaré (120 min par Rapport) à côté du temps mesuré du dernier
  Passage, par Rapport et cumulé sur 5 Rapports.
- **Dire :** « À gauche, le temps manuel déclaré : deux heures par rapport, c'est une valeur
  fictive que l'on ajuste avec le client. À droite, le temps mesuré de la Chaîne : quelques
  secondes. Sur une semaine, ce sont dix heures rendues à l'équipe. »
- **Plan B (repli) :** l'écran affiche les 4,4 s du Passage enregistré (Journal local). Dire :
  « En direct sur Jira Cloud, la même Chaîne prend 20 s pour 3 547 tickets. »

### 3. Lancement de la Chaîne : 1:30 → 2:45 (75 s)

- **Écran :** Lancement de la Chaîne.
- **Clic :** bouton **« Lancer la Chaîne »**. Pendant la progression, commenter les étapes
  (extraction, instantanés, KPI, météo, prévision, rendu).
- **Dire :** « Je lance la Chaîne sur Jira Cloud, en lecture seule. Elle extrait l'historique,
  calcule les indicateurs, la météo par règles, la prévision, puis écrit l'Excel et le
  PowerPoint du jour. Aucun LLM dans ce calcul : tout est déterministe et rejouable. »
- **Fin :** la carte du nouveau Passage s'affiche sous la progression.
- **Ne pas relancer `usine ui` pendant une Chaîne :** le suivi à l'écran serait perdu. La
  Chaîne continue sans lui et son Passage s'affiche au chargement suivant d'une page, une fois
  terminée.
- **Plan B (repli) :** le bouton est bloqué et l'écran dit pourquoi. Ne pas attendre : dire
  « En Mode repli, le lancement est coupé. En direct, ce Passage a tourné en 20 s sur 3 547
  tickets » et passer à la carte (gagne 45 s).
- **Si la Chaîne échoue :** l'écran nomme l'étape en échec ; ouvrir `/chaine`, cliquer sur « Passer en Mode repli », dire la
  phrase de bascule et continuer.

### 4. Carte météo, Scénarios A, B et C : 2:45 → 3:45 (60 s)

- **Écran :** Carte météo.
- **Montrer :** ENT-A et ENT-B rouges, ENT-C orange, les flèches de tendance J-1 / J-5 et la
  Règle déclenchante principale de chaque Entité.
- **Dire :** « Deux Entités sont rouges, A et B, pour la même raison : trop d'Anomalies
  bloquantes ouvertes. C est orange : trop de tests en échec. Chaque couleur vient d'une règle
  écrite, pas d'une impression. »
- **Plan B (repli) :** identique (même Météo).

### 5. Détail de ENT-A, Prévision : 3:45 → 5:00 (75 s)

- **Clic :** l'Entité **ENT-A** sur la carte.
- **Montrer :** Règles déclenchantes (IND-1 : 4 Anomalies bloquantes pour un seuil de 3, avec
  les tickets en cause), KPI clés, bloc « Prévision de sortie du rouge » et ses facteurs
  explicatifs (stock 4, 6 entrées et 15 sorties sur 10 Jours ouvrés).
- **Dire :** « A est rouge avec 4 bloquantes. L'équipe en ferme plus qu'il n'en arrive : la
  prévision la voit sortir du rouge vers le 13 octobre, une chance sur deux sous 10 jours
  ouvrés. C'est une projection statistique, pas un LLM, et ses facteurs sont affichés. »
- **Plan B (repli) :** identique ; les liens vers les tickets Jira sont inactifs, le dire si
  quelqu'un clique.

### 6. ENT-B et ENT-C : 5:00 → 6:00 (60 s)

- **Clic :** liste **« Entité »** du Détail → ENT-B, puis ENT-C.
- **Montrer :** ENT-B « aucune sortie projetée » (9 bloquantes, 11 entrées pour 9 sorties) ;
  ENT-C bloc « Risque d'entrée en rouge » sur IND-4 vers le 14/10/2026.
- **Dire :** « B, elle, ne sortira pas seule : il en arrive plus qu'il n'en part. C'est là
  qu'il faut mettre des renforts. Et C n'est pas encore rouge, mais le taux d'échec des tests
  l'y mène dans la semaine : on le sait avant qu'il arrive. »
- **Plan B (repli) :** identique.

### 7. Explication sourcée et Paliers : 6:00 → 6:30 (30 s)

- **Écran :** Détail d'une Entité, ENT-A, bloc « Explication ».
- **Si le Passage est Palier 2 :** montrer l'Explication sourcée (liens vers les tickets
  cités), puis le sélecteur **« Palier affiché »** → « Palier 1 » pour la même Entité sans
  aucune sortie LLM. Dire : « Le LLM ajoute une explication, et chaque ticket qu'il cite est
  vérifié. Sans lui, le rapport reste complet. »
- **Si le Passage est Palier 1 (cas actuel, normal et repli) :** le bloc affiche « commentaire
  non généré (Palier 1) » et il n'y a pas de sélecteur. Dire : « Ici, aucun LLM : tout ce que
  vous avez vu est calculé. La couche LLM ajoute ensuite une explication sourcée par Entité,
  dont chaque ticket cité est contrôlé. Elle est en option, pas en fondation. »
- **Plan B (repli) :** cas Palier 1 ci-dessus (la copie de repli est Palier 1).

### 8. Pseudonymisation : 6:30 → 7:15 (45 s)

- **Écran :** Pseudonymisation.
- **Clic :** liste **« Ticket »** → `DEMO-4` en Mode repli (4e de la liste ; il contient un nom
  de client et un IBAN fictifs). En mode normal, les clés suivent Jira : repérer la veille un
  ticket dont la description cite un client ou un compte, et noter sa clé ici : `DEMO-____`.
- **Montrer :** « Original » à gauche, « Version pseudonymisée » à droite.
- **Dire :** « Avant qu'un texte parte vers un LLM, les noms, comptes et identifiants sont
  remplacés sur ce poste. Le LLM ne voit jamais la donnée bancaire. Ici c'est un aperçu local :
  aucun appel, rien d'écrit. »
- **Attention :** environ 4 s d'affichage à chaque changement de ticket ; choisir le ticket une
  seule fois.
- **Plan B (repli) :** identique (local, sans réseau). Si l'écran affiche « USINE_CLE_PSEUDO
  absente », passer à l'Agent sans commentaire technique.

### 9. Agent : 7:15 → 8:30 (75 s)

- **Écran :** Agent.
- **Mode normal :** la question de la démo est déjà dans le champ : « Quelle Entité risque de
  passer au rouge, et pourquoi ? ». Clic **« Poser la question »**. Montrer la réponse, la
  ligne « Contrôle : … » (attendu : « conforme : chiffres et tickets vérifiés ») et les outils
  appelés. Un appel coûte quelques centimes.
- **Dire :** « L'Agent ne lit que le dernier Passage, par des outils en lecture seule. Chaque
  chiffre et chaque ticket de sa réponse est vérifié contre ces outils avant affichage. S'il
  invente, la réponse est rejetée. »
- **Plan B (repli) :** l'écran propose les questions enregistrées (`demo/repli/agent/`), sans
  saisie libre. Choisir dans **« Question enregistrée »** :
  1. « Quelles entités risquent de passer au rouge la semaine prochaine, et pourquoi ? »
     (`01.json`), clic **« Rejouer la réponse »** ;
  2. si le temps le permet, « Quel est le budget restant du programme de migration ? »
     (`05.json`) : l'Agent répond qu'il n'a pas cette donnée. Dire : « Il sait dire non. »

  La mention « Mode repli : réponse enregistrée le … sur le Passage …, rejouée sans LLM »
  s'affiche sous la réponse : la montrer.
  Autres questions disponibles : « Quelles entités sont rouges à la Date d'arrêté ? »
  (`02.json`), « Pourquoi ENT-B est-elle rouge ? » (`03.json`), « Combien d'Anomalies sont
  ouvertes chez ENT-C ? » (`04.json`).
- **Si le LLM ne répond pas (mode normal) :** ouvrir `/chaine`, passer en Mode repli et suivre le plan B.

### 10. Ce qu'il faut pour le faire en vrai : 8:30 → 9:15 (45 s)

- **Écran :** Ce qu'il faut pour le faire en vrai.
- **Montrer :** les quatre demandes par ordre de priorité, puis le tableau des briques par cible
  (VM Python, Dataiku, Power Platform, poste seul).
- **Dire :** « Pour le faire chez vous, il faut d'abord un compte Jira en lecture seule et un
  environnement Python ; cela suffit pour le Palier 1. Le LLM vient ensuite, sur un endpoint que
  vous validez. Chaque brique se porte sur l'outillage que vous avez déjà. »
- **Plan B (repli) :** identique (fiche locale).

### 11. Conclusion : 9:15 → 9:40 (25 s)

- **Écran :** retour sur Carte météo.
- **Dire :** « En résumé : le rapport du matin en une commande, une météo justifiée par des
  règles, une prévision qui dit où mettre les renforts, et un LLM qui n'invente rien. Ce
  qu'il me faut pour démarrer, c'est l'accès Jira en lecture seule. »
- **Stop chrono.** Noter la durée dans `repetitions.md`.

## Après chaque répétition

Consigner dans [`repetitions.md`](repetitions.md) : date, durée, mode, incidents, intervention
hors script. Si une séquence déborde de plus de 15 s, raccourcir sa phrase dans ce script.
