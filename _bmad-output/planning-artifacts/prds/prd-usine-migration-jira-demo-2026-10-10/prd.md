---
title: Copilote de pilotage d'une usine de migration (démonstrateur)
status: final
created: 2026-10-10
updated: 2026-10-10
sources:
  - SPEC-usine-migration-jira-demo.md (v0.2, § 11 prioritaire)
---

# PRD : Copilote de pilotage d'une usine de migration
*Titre de travail, à confirmer.*

## 0. Objet du document

Ce PRD s'adresse à l'auteur du démonstrateur (seul développeur) et aux étapes BMAD suivantes : UX, architecture, epics et stories. Il dérive de la spec v0.2 sans refaire de brief. **Les décisions du § 11 de la spec priment** sur le reste de la spec : météo à quatre couleurs, reporting **quotidien** avec tendances à la semaine, format de reporting générique.

Conventions :
- Les exigences fonctionnelles (`FR-n`) et non fonctionnelles (`NFR-n`) ont des identifiants stables, à reprendre tels quels dans les stories. Les FR ajoutées après la première version prennent la suite de la numérotation (FR-49 et suivantes) et sont rangées dans leur fonctionnalité.
- Chaque FR porte un niveau : **[INDISPENSABLE]** (requis pour la démo de 10 minutes) ou **[BONUS]** (réalisé si le temps le permet, sans bloquer la démo).
- Les inférences non confirmées portent la balise `[HYPOTHÈSE H-n]`. Les hypothèses tranchées portent la mention « (décision du 10/10/2026, H-n) ». Toutes sont suivies dans `docs/QUESTIONS.md`.
- Les choix techniques (bibliothèques, formats de fichiers, pagination, méthodes de calcul détaillées) vivent dans `addendum.md`.
- Le vocabulaire du § 3 (Glossaire) est le seul autorisé.

**Dépôt public, licence MIT.** Toutes les données, tous les noms, tous les gabarits et toutes les règles de météo sont **inventés**. Aucun élément réel d'un client n'entre dans le dépôt.

## 1. Vision

Dans une usine de migration de SI bancaire, le pilotage passe par Jira, mais le reporting se fabrique à la main : extractions, retraitements Excel, copier-coller dans PowerPoint, commentaires de météo rédigés au jugement. C'est lent, sujet aux erreurs, et un « rouge » se justifie rarement par des faits vérifiables.

Le démonstrateur montre, sur un programme 100 % fictif, qu'une chaîne pro code peut produire **chaque jour** un rapport Excel et PowerPoint fiable en une commande, calculer la météo par des règles explicites, puis, avec un LLM, **expliquer un rouge en citant les anomalies**, estimer sa sortie et répondre aux questions du pilote en langage naturel. Les chiffres ne passent jamais par le LLM.

L'enjeu n'est pas l'outil lui-même : c'est d'**obtenir l'outillage** (compte de service Jira, environnement Python, LLM validé) en dix minutes de démonstration, et de constituer une référence de projet agentique de bout en bout. La valeur est découpée en deux paliers pour que la demande reste recevable même si la banque refuse tout LLM.

## 2. Utilisateurs cibles

### 2.1 Jobs To Be Done

- **Pilote** : « Chaque matin, je veux un état fiable de l'usine sans passer une heure dans Excel, et pouvoir justifier chaque rouge devant le comité avec des tickets précis. »
- **Pilote** : « Je veux savoir quelles entités vont mal tourner avant qu'elles ne passent au rouge. »
- **Sponsor** : « Avant d'accorder des accès et un budget, je veux voir que la chaîne est fiable, auditable, sans fuite de données et portable sur nos outils. »
- **Auteur** (contexte personnel) : « Je veux un projet agentique de bout en bout, montrable publiquement, qui prouve ma capacité à résoudre un vrai problème métier avec l'IA là où elle apporte quelque chose. »

### 2.2 Non-utilisateurs (v1)

- Les équipes de développement ou de recette qui traitent les anomalies : le démonstrateur ne remplace pas Jira.
- Un usage multi-utilisateurs en production : aucune authentification, aucun partage de droits.

### 2.3 Parcours utilisateurs clés

Personnages fictifs, hormis l'auteur.

- **UJ-1. Claire, pilote de l'usine, produit le rapport du jour en une commande.**
  Claire arrive à 8 h 30. Elle lance la commande de reporting sur la Date d'arrêté de la veille. La Chaîne de reporting extrait de Jira les tickets modifiés depuis le dernier Passage, recalcule les Instantanés, les KPI et la Météo, puis dépose un Excel et un PowerPoint datés. En moins de cinq minutes, elle ouvre la slide de synthèse : deux Entités rouges, une orange de plus qu'hier. **Cas limite :** Jira est injoignable ; la commande s'arrête avec un message qui nomme l'étape en échec et ne dépose aucun rapport partiel (FR-25).

- **UJ-2. Claire justifie un rouge devant le comité.**
  Dans l'interface, Claire ouvre l'Entité A. La Règle déclenchante s'affiche (« 4 Anomalies bloquantes ouvertes, seuil rouge : 3 »). En dessous, l'Explication sourcée cite chaque ticket ; un clic ouvre le ticket dans Jira. La même explication figure en Brouillon de commentaire sur la slide de l'Entité, marquée « à valider ». Claire corrige une phrase directement dans le PowerPoint produit et présente. **Cas limite :** une phrase cite un ticket qui n'appartient pas à l'Entité ; le contrôle la retire avant affichage et indique le nombre de phrases retirées.

- **UJ-3. Claire anticipe la semaine suivante avec l'Agent.**
  Claire demande à l'Agent : « Quelles entités risquent de passer au rouge la semaine prochaine, et pourquoi ? ». L'Agent consulte la Météo, les Tendances hebdomadaires et les Prévisions, puis répond que l'Entité C présente un Risque d'entrée en rouge (taux de KO en hausse de 6 points sur la Fenêtre glissante), avec les chiffres issus des outils et les Cas de test KO à l'appui. Elle demande ensuite la liste des Anomalies bloquantes de l'Entité B, sans jamais pouvoir modifier quoi que ce soit.

- **UJ-4. Anaël présente la démo de 10 minutes au Sponsor.**
  Le Sponsor dispose de dix minutes. Anaël montre l'avant / après (temps manuel déclaré contre temps mesuré), lance la Chaîne de reporting en direct sur Jira Cloud, ouvre la Météo du jour (A rouge, Règle déclenchante et Explication sourcée), la Prévision (A sort probablement sous 10 Jours ouvrés, avec ses facteurs explicatifs ; B non), l'Agent, puis l'écran « Ce qu'il faut pour le faire en vrai ». **Cas limite :** le réseau ou l'API LLM tombe pendant la démo ; Anaël bascule en Mode repli (dernier Passage et réponses de l'Agent enregistrés, signalés comme tels) et la démo continue.

## 3. Glossaire

**Programme et tickets**
- **Programme** : Le programme de migration fictif « Banque Exemple — migration SI cœur ». Contient des Entités, des Vagues et des Domaines.
- **Entité** : Unité migrée et pilotée (une dizaine par Programme). Porte une Météo. Appartient à une seule Vague.
- **Vague** : Lot de migration (3 par Programme), avec un calendrier de Phases.
- **Vague en cours** : Pour une Entité, sa Vague ; les Certifications prises en compte sont celles de cette Vague.
- **Domaine** : Périmètre fonctionnel (crédits, dépôts, paiements, référentiel clients…). Attribut d'un ticket.
- **Phase** : Étape de test : migration à blanc, recette, TNR (tests de non-régression).
- **Phase en cours** : Phase du calendrier de la Vague de l'Entité qui contient la Date d'arrêté.
- **Anomalie** : Ticket Jira de défaut. Porte une Gravité, une Phase, une Entité, un Domaine et une Cause racine.
- **Statuts d'Anomalie** : Workflow fictif : Nouvelle, En analyse, En correction, À retester, Fermée, Rejetée. `[HYPOTHÈSE H-17]`
- **Anomalie ouverte** : Anomalie dont le statut n'est ni Fermée ni Rejetée.
- **Entrée** : Création d'une Anomalie, ou réouverture (passage de Fermée ou Rejetée vers un autre statut).
- **Sortie** : Passage d'une Anomalie au statut Fermée ou Rejetée.
- **Gravité** : Bloquante, majeure ou mineure.
- **Cause racine** : Catégorie d'origine d'une Anomalie, parmi sept : reprise de données, règle de transformation, paramétrage, interface ou flux, environnement, donnée de test, hors périmètre (faux positif). `[HYPOTHÈSE H-18]` Dans les données générées, c'est une vérité terrain cachée à la Chaîne de reporting.
- **Cas de test** : Ticket Jira de test, au statut OK, KO ou non exécuté.
- **Certification** : Ticket Jira de validation d'une Entité pour une Vague : accordée, réservée ou refusée.

**Données et calcul**
- **Journal d'événements** : Fichier daté produit par le générateur, qui décrit chaque création et chaque transition de ticket sur les 8 semaines d'historique.
- **Corpus de textes** : Titres et descriptions de tickets générés une fois par un LLM, puis versionnés dans le dépôt.
- **Date d'injection** : Date à laquelle le Programme a été chargé dans Jira Cloud. Fin du Journal d'événements.
- **Passage** : Une exécution de la Chaîne de reporting pour une Date d'arrêté.
- **Chaîne de reporting** : Enchaînement extraction → Instantanés → KPI → Météo → Prévision → (Palier 2) → rendu, lancé par une seule commande.
- **Jour ouvré** : Du lundi au vendredi, sans jour férié (décision du 10/10/2026, H-1).
- **Fenêtre glissante** : Les 5 derniers Jours ouvrés, Date d'arrêté comprise (une semaine). `[HYPOTHÈSE H-19]`
- **Date d'arrêté** : Jour ouvré auquel se rapportent un Instantané et un Rapport quotidien.
- **Instantané** : État calculé de chaque Entité à une Date d'arrêté, reconstruit à partir de l'historique des tickets.
- **KPI** : Mesure déterministe calculée sur un Instantané (stocks, flux, âges, taux).
- **Indicateur de météo** : KPI utilisé par la Grille de météo (IND-1 à IND-8).
- **Grille de météo** : Ensemble de règles et de seuils, en configuration, qui attribue une Météo.
- **Météo** : Couleur d'une Entité à une Date d'arrêté : vert, jaune, orange ou rouge.
- **Règle déclenchante** : Règle de la Grille de météo dont le seuil est franchi et qui fixe la couleur de l'Entité.
- **Rapport quotidien** : Le couple Excel + PowerPoint produit pour une Date d'arrêté.
- **Tendance hebdomadaire** : Agrégation des Instantanés par semaine (8 semaines d'historique).
- **Rapport de référence** : KPI et Météo calculés à la main sur un jeu réduit figé, utilisés pour la réconciliation.
- **Scénario de démo** : Trajectoire scriptée d'une Entité dans les données générées (A, B, C).

**Prévision**
- **Prévision** : Résultat statistique (jamais produit par un LLM) : Prévision de sortie du rouge ou Risque d'entrée en rouge.
- **Prévision de sortie du rouge** : Pour une Entité rouge : date estimée à laquelle elle n'aura plus de Règle déclenchante rouge, avec une fourchette, une probabilité de sortie dans l'horizon et ses facteurs explicatifs.
- **Risque d'entrée en rouge** : Signal indiquant qu'une Entité non rouge franchirait un seuil rouge dans l'horizon de prévision.
- **Baseline** : Méthode de Prévision par projection à vélocité constante. Référence à battre pour le Modèle ML.
- **Modèle ML** : Modèle d'apprentissage supervisé (bonus), entraîné sur le Public Jira Dataset.

**Paliers, LLM et démo**
- **Palier 1** : Ce qui fonctionne sans LLM : extraction, Instantanés, KPI, Météo, Prévision, Rapport quotidien.
- **Palier 2** : Ce qui utilise un LLM : classification des Causes racines, Explication sourcée, Brouillon de commentaire, narration de la Prévision, Agent.
- **Pseudonymisation** : Remplacement des données identifiantes (numéros de compte, noms de clients) avant tout envoi à un LLM.
- **Explication sourcée** : Texte rédigé par le LLM qui justifie la Météo d'une Entité rouge ou orange ; chaque phrase porte au moins une Citation.
- **Citation** : Clé de ticket Jira citée dans une Explication sourcée, vérifiée de façon déterministe.
- **Brouillon de commentaire** : Commentaire de météo proposé par le LLM pour le PowerPoint, marqué « à valider ».
- **Agent** : Assistant conversationnel en lecture seule, qui répond à partir d'outils de consultation.
- **Journal de traçabilité** : Enregistrement local de chaque appel LLM et de chaque Prévision, avec les versions de prompt, de modèle, de Grille et de données.
- **Version de données** : Empreinte du Journal d'événements et horodatage de la dernière extraction Jira.
- **Rejeu** : Recalcul d'une Date d'arrêté déjà traitée (FR-14).
- **Mode repli** : Affichage du dernier Passage enregistré et des réponses enregistrées de l'Agent, quand Jira ou le LLM est injoignable (FR-45).
- **Pilote** : Personne qui produit le reporting de l'usine et défend la Météo en comité.
- **Sponsor** : Décideur côté banque qui accorde l'outillage.
- **Responsable de mission** : Personne qui valide la démo avant toute présentation au client.

## 4. Fonctionnalités

### 4.1 Programme fictif et générateur de données

**Description :** un générateur reproductible (graine aléatoire) crée le Programme fictif, ses tickets et 8 semaines d'historique daté, avec la volumétrie du § 11 de la spec. Il scripte trois Scénarios de démo et injecte des identifiants sensibles fictifs pour démontrer la Pseudonymisation. Le calendrier est ancré sur la date de génération, pour que la démo du jour montre l'état courant. Réalise UJ-4.

#### FR-1 : Configuration du Programme [INDISPENSABLE]
L'auteur peut décrire le Programme (Entités, Vagues, Domaines, calendrier des Phases, volumétrie) dans un fichier de configuration.
- Changer le nombre d'Entités ou la volumétrie ne demande aucune modification de code.
- Aucun nom réel d'organisation ou de personne n'apparaît dans la configuration livrée.

#### FR-2 : Génération reproductible [INDISPENSABLE]
L'auteur peut générer Anomalies, Cas de test et Certifications avec leur historique de statuts daté sur 8 semaines, sous forme de Journal d'événements.
- À Corpus de textes constant, deux exécutions avec la même graine produisent un Journal d'événements identique (structure, dates relatives, affectations, textes).
- Le Corpus de textes est généré une seule fois par un LLM **distinct du classifieur des Causes racines (FR-35)**, puis versionné ; régénérer les données ne demande aucun appel LLM.
- L'historique se termine au dernier Jour ouvré avant la date de génération ; la semaine 1 commence 8 semaines plus tôt.
- La volumétrie respecte la configuration : 3 000 à 5 000 Anomalies sur 8 semaines, 200 à 500 Entrées par semaine, 10 Entités (décision du 10/10/2026, H-2).
- Chaque Anomalie porte une Cause racine, non exposée dans Jira.

#### FR-3 : Scénarios de démo [INDISPENSABLE]
Avec la Grille de météo par défaut, les données générées produisent les trajectoires suivantes (décision du 10/10/2026 : trajectoire de A décalée pour être rouge le jour de la démo) :
- **Entité A** : verte ou jaune jusqu'à la semaine 5 ; rouge à partir de la semaine 6 (Anomalies bloquantes de reprise de données) ; Sorties supérieures aux Entrées à partir de la semaine 7, si bien qu'en fin d'historique elle est rouge avec une Prévision de sortie dans l'horizon.
- **Entité B** : rouge à partir de la semaine 2 et jusqu'à la fin, car les Entrées d'Anomalies dépassent les Sorties ; pas de sortie projetée.
- **Entité C** : verte jusqu'à la semaine 3, jaune en semaines 4 à 6, orange en semaines 7 et 8 (taux de KO en TNR en hausse), avec un Risque d'entrée en rouge en fin d'historique.
- Hors A, B et C : aucune Entité n'est rouge plus de 3 Jours ouvrés consécutifs, et au moins 80 % des couples Entité × Date d'arrêté sont verts ou jaunes.
- Au plus 2 Entités rouges en fin d'historique (décision du 10/10/2026, H-3).

#### FR-4 : Identifiants sensibles fictifs [INDISPENSABLE]
Le générateur insère, dans au moins 10 % des descriptions d'Anomalies, des numéros de compte, des noms de clients et des identifiants fictifs, au format plausible mais invalide (décision du 10/10/2026, H-4).

#### FR-5 : Chargement dans Jira Cloud [INDISPENSABLE]
L'auteur peut injecter le Programme dans un site Jira Cloud Free : l'état courant des tickets en fin d'historique et les champs personnalisés Entité, Vague, Domaine, Gravité et Phase.
- Sur un site vierge, l'injection recrée le projet, les types de tickets, le workflow et les champs personnalisés.
- Une réinjection est idempotente : relancée, elle ne crée pas de doublons.
- Les clés de ticket sont stables d'une injection à l'autre, ou une table de correspondance est produite et utilisée par les liens et les Citations.
- L'URL du site Jira est en configuration.
- L'injecteur est le seul composant qui écrit dans Jira, avec un identifiant distinct de celui de l'extraction.
- L'API Jira ne permettant pas d'antidater les transitions, l'historique de 8 semaines est porté par le Journal d'événements (décision du 10/10/2026, H-5, Q-1).

### 4.2 Extraction Jira

**Description :** l'extraction récupère les tickets et leur historique de statuts, de façon incrémentale, par un adaptateur choisi en configuration. L'historique complet combine le Journal d'événements et le changelog Jira. Réalise UJ-1 et UJ-4.

#### FR-6 : Extraction incrémentale Jira Cloud [INDISPENSABLE]
Le système extrait de Jira Cloud (API v3) les tickets modifiés depuis le dernier Passage réussi, avec leur historique de changements.
- Un deuxième Passage sans modification dans Jira n'ajoute ni ne modifie aucun ticket stocké.
- Une coupure en cours d'extraction n'avance pas le repère du dernier Passage.

#### FR-7 : Adaptateur Jira Data Center [INDISPENSABLE]
Le système dispose d'un adaptateur Jira Data Center (API v2), sélectionné en configuration.
- L'adaptateur passe les mêmes tests que l'adaptateur Cloud, sur des fixtures enregistrées.
- Aucun accès à un vrai Jira Data Center n'est requis.

#### FR-8 : Source Journal d'événements [INDISPENSABLE]
Le système peut charger le Journal d'événements comme seule source, sans Jira, avec le même modèle de données en sortie.
- Toute Date d'arrêté de l'historique peut être calculée à partir du seul Journal d'événements.

#### FR-49 : Source composite [INDISPENSABLE]
En fonctionnement normal, le système combine le Journal d'événements jusqu'à la Date d'injection et le changelog Jira après cette date.
- Jira fait foi sur l'état courant des tickets.
- À la Date d'injection, l'Instantané calculé depuis le Journal d'événements et celui calculé depuis l'état Jira sont identiques (test de cohérence).
- Une mise à jour faite en direct dans Jira apparaît dans l'Instantané du Passage suivant.

#### FR-9 : Extraction en lecture seule [INDISPENSABLE]
L'extraction n'effectue aucune écriture dans Jira.
- Les tests vérifient qu'aucune requête d'écriture n'est émise par l'extraction.

### 4.3 Instantanés et KPI

**Description :** à partir de l'historique des tickets, le système reconstitue l'état de chaque Entité à n'importe quelle Date d'arrêté, puis calcule des KPI déterministes. Le rythme est quotidien ; les tendances sont agrégées à la semaine. Réalise UJ-1.

#### FR-10 : Instantané quotidien [INDISPENSABLE]
Le système calcule un Instantané par Entité pour toute Date d'arrêté couverte par l'historique, y compris passée.
- Un Instantané d'une date passée ne dépend que des événements antérieurs ou égaux à cette date.

#### FR-11 : KPI quotidiens [INDISPENSABLE]
Le système calcule, par Entité et pour le Programme :
- stock d'Anomalies ouvertes par Gravité et par Phase ;
- Entrées et Sorties du jour et sur la Fenêtre glissante ;
- âge des Anomalies ouvertes (médian, maximum), en Jours ouvrés depuis la dernière Entrée ;
- taux de KO et taux de non-exécution des Cas de test, par Phase ;
- Certifications par statut.

#### FR-12 : Tendances hebdomadaires [INDISPENSABLE]
Le système agrège les Instantanés par semaine (valeur du dernier Jour ouvré, Entrées et Sorties cumulées de la semaine) sur 8 semaines.

#### FR-13 : Réconciliation [INDISPENSABLE]
Un test compare les KPI et la Météo calculés au Rapport de référence.
- Le Rapport de référence porte sur un jeu réduit figé (environ 2 Entités, 60 tickets, 1 Date d'arrêté) qui fait jouer chaque Indicateur de météo et chaque garde-fou de volume. `[HYPOTHÈSE H-20]`
- Égalité stricte sur 100 % des valeurs.

#### FR-14 : Rejeu idempotent [INDISPENSABLE]
Le Rejeu d'une Date d'arrêté produit des Instantanés, des KPI, une Météo, des Prévisions et un Rapport quotidien identiques, à l'exception de l'horodatage de génération.
- En Palier 2, le Rejeu réutilise les sorties LLM mises en cache pour la même Date d'arrêté, la même Entité et les mêmes versions de prompt, de modèle et de données ; il ne relance un appel que si l'une d'elles change.

### 4.4 Météo par règles

**Description :** la Météo n'est plus déclarée mais calculée. Une Grille de météo en configuration, lisible par un non-développeur, évalue huit Indicateurs de météo. **La couleur la plus grave déclenchée l'emporte** ; vert s'il n'y a aucune Règle déclenchante. La Météo est calculée sans état d'un jour à l'autre : pas d'hystérésis en v1 (Q-3). Toutes les Règles déclenchantes de la couleur retenue sont restituées avec leur valeur et leur seuil. Réalise UJ-1 et UJ-2.

**Grille de météo par défaut (entièrement fictive ; décision du 10/10/2026, H-6) :**

| Indicateur de météo | Rouge si | Orange si | Jaune si |
|---|---|---|---|
| IND-1 Anomalies bloquantes ouvertes | ≥ 3 | ≥ 1 | — |
| IND-2 Âge de la plus ancienne bloquante ouverte (Jours ouvrés) | > 10 | > 5 | — |
| IND-3 Anomalies majeures ouvertes | ≥ 20 | ≥ 10 | ≥ 5 |
| IND-4 Taux de KO des Cas de test exécutés, Phase en cours | ≥ 20 % | ≥ 10 % | ≥ 5 % |
| IND-5 Certifications refusées (Vague en cours) | ≥ 1 | — | — |
| IND-6 Certifications réservées (Vague en cours) | — | ≥ 2 | ≥ 1 |
| IND-7 Ratio Entrées / Sorties d'Anomalies bloquantes et majeures sur la Fenêtre glissante | — | > 1,5 | > 1,0 |
| IND-8 Hausse du taux de KO : IND-4 à la Date d'arrêté moins IND-4 cinq Jours ouvrés plus tôt (points) | — | ≥ + 5 | ≥ + 3 |

Garde-fous de volume (en configuration) : IND-4 n'est évalué qu'à partir de 20 Cas de test exécutés ; IND-7 qu'à partir de 5 Entrées sur la Fenêtre glissante (des Sorties nulles avec des Entrées suffisantes valent un ratio infini) ; IND-8 seulement si IND-4 est évaluable aux deux dates. Un indicateur non évaluable apparaît comme tel, sans faire changer la couleur.

#### FR-15 : Grille en configuration [INDISPENSABLE]
L'auteur ou le Pilote peut modifier les seuils, les garde-fous et l'activation de chaque règle dans un fichier de configuration commenté en français, sans toucher au code.
- Les seuils de la Grille par défaut sont ceux du tableau ci-dessus.
- Chaque Météo calculée est rattachée à la version de la Grille qui l'a produite.

#### FR-16 : Calcul de la Météo [INDISPENSABLE]
Le système attribue une Météo à chaque Entité pour chaque Date d'arrêté selon la règle « la couleur la plus grave l'emporte ».
- Avec la Grille par défaut, les Scénarios de démo suivent les trajectoires de FR-3, vérifiées au jour près par un test.

#### FR-17 : Restitution des Règles déclenchantes [INDISPENSABLE]
Pour chaque Entité, le système restitue la liste des Règles déclenchantes de la couleur retenue, avec la valeur mesurée, le seuil franchi et les tickets en cause :
- IND-1, IND-2, IND-3 : les Anomalies ouvertes concernées ;
- IND-4, IND-8 : les Cas de test KO de la Phase en cours ;
- IND-5, IND-6 : les Certifications concernées ;
- IND-7 : les Anomalies entrées et sorties sur la Fenêtre glissante.

#### FR-18 : Validation de la Grille [INDISPENSABLE]
Au chargement, le système refuse une Grille incohérente.
- Le message nomme le fichier, la règle et la valeur fautive.
- Exemples refusés : seuil orange plus sévère que le seuil rouge, indicateur inconnu, couleur inconnue.

#### FR-19 : Évolution de la Météo [INDISPENSABLE]
Le système restitue, pour chaque Entité, la Météo de J-1 et de J-5 (en Jours ouvrés, soit une semaine) et signale les changements de couleur.

### 4.5 Prévision

**Description :** la Prévision est statistique, jamais produite par un LLM. La Baseline projette les indicateurs à vélocité constante, donne une probabilité et ses facteurs explicatifs déterministes. Elle est évaluée sur des données réelles publiques, pour échapper à la circularité des données synthétiques. Un Modèle ML vient en bonus. Réalise UJ-3 et UJ-4.

#### FR-20 : Prévision de sortie du rouge, Baseline [INDISPENSABLE]
Pour chaque Entité rouge, le système projette le stock d'Anomalies bloquantes ouvertes (IND-1) à vélocité nette constante (Sorties moins Entrées) et restitue : une date de sortie estimée, une fourchette optimiste / pessimiste, une probabilité de sortie dans l'horizon, et des facteurs explicatifs (stock, Entrées, Sorties, vélocité nette et leur évolution). La vélocité est mesurée sur 10 Jours ouvrés et l'horizon est de 10 Jours ouvrés, tous deux en configuration (décision du 10/10/2026, H-7). La méthode détaillée figure dans l'addendum.
- Si la vélocité nette est nulle ou défavorable, le système indique « pas de sortie projetée ».
- Une date n'est produite que si toutes les Règles déclenchantes rouges sont projetables ; sinon le système affiche « règle non projetable : IND-x » pour toute règle autre qu'IND-1.
- En fin d'historique : A sort dans l'horizon, B ne sort pas.

#### FR-21 : Risque d'entrée en rouge [INDISPENSABLE]
Pour chaque Entité non rouge, le système signale un Risque d'entrée en rouge si la projection linéaire d'IND-1, IND-3 ou IND-4 franchit un seuil rouge dans un horizon de 5 Jours ouvrés (décision du 10/10/2026, H-8), en indiquant l'indicateur concerné.
- L'Entité C est signalée en fin d'historique.

#### FR-51 : Évaluation de la Baseline sur données réelles [INDISPENSABLE]
La méthode de la Baseline est évaluée rétrospectivement sur le Public Jira Dataset (Université de Hambourg), sur le stock de tickets de priorité maximale par projet.
- Le protocole, la cible et le seuil sont décrits dans l'addendum ; les résultats (score de Brier, AUC, erreur sur le stock projeté) sont publiés dans le dépôt.
- La Baseline fait mieux qu'une prévision naïve (taux historique de sortie sous N jours) sur le score de Brier. `[HYPOTHÈSE H-21]`

#### FR-22 : Modèle ML validé sur données réelles [BONUS]
Le système dispose d'un Modèle ML qui prédit la probabilité de résolution d'une Anomalie bloquante sous N Jours ouvrés (N = horizon de FR-20), entraîné et évalué sur le Public Jira Dataset avec le protocole de FR-51.
- Le Modèle ML bat la Baseline en AUC et en score de Brier sur un jeu de test tenu à l'écart.
- La probabilité de sortie du rouge d'une Entité s'obtient en agrégeant les probabilités de ses bloquantes ouvertes (règle d'agrégation dans l'addendum).
- Appliqué aux Scénarios de démo, il anticipe la sortie de A et le maintien de B.

#### FR-23 : Facteurs explicatifs du Modèle ML [BONUS]
Pour chaque Prévision du Modèle ML, le système restitue les principaux facteurs explicatifs, lisibles par le Pilote.

#### FR-24 : Narration de la Prévision [INDISPENSABLE]
Le LLM rédige une phrase qui raconte la Prévision (Baseline ou Modèle ML) à partir de ses valeurs, sans produire de chiffre propre.
- Un contrôle déterministe vérifie que chaque nombre de la narration figure dans les valeurs fournies ; sinon, la narration est rejetée et la Prévision brute est affichée.

### 4.6 Rapport quotidien (Excel et PowerPoint)

**Description :** aucun gabarit de reporting existant n'est à reproduire. Le démonstrateur définit un format générique et neutre, produit en une commande pour une Date d'arrêté. Sans LLM, le Rapport quotidien est complet (Palier 1) ; avec LLM, il s'enrichit des Explications sourcées, des Brouillons de commentaire et de la répartition des Causes racines (Palier 2). Réalise UJ-1, UJ-2 et UJ-4.

**Format Excel (décision du 10/10/2026, H-9) :**

| Onglet | Contenu |
|---|---|
| 1. Synthèse | Une ligne par Entité : Météo J, J-1, J-5, Règles déclenchantes, Prévision ou Risque d'entrée en rouge |
| 2. Météo détaillée | Valeur de chaque Indicateur de météo par Entité, seuils, indicateurs non évaluables |
| 3. KPI | KPI quotidiens par Entité et Programme (FR-11) |
| 4. Tendances | Tendances hebdomadaires sur 8 semaines |
| 5. Anomalies ouvertes | Bloquantes et majeures ouvertes : clé (lien Jira), Entité, Gravité, Phase, Domaine, âge, Cause racine proposée (Palier 2) |
| 6. Tests | Cas de test par Entité et Phase : OK, KO, non exécutés, taux |
| 7. Certifications | Certifications par Entité et Vague, avec leur statut |
| 8. Commentaires | Palier 2 : Explications sourcées, Brouillons de commentaire, répartition des Causes racines, avec Citations |
| 9. Traçabilité | Date d'arrêté, source, horodatage d'extraction, nombre de tickets, versions de Grille, de données, de prompt et de modèle |

**Format PowerPoint (gabarit neutre et fictif ; décision du 10/10/2026, H-10) :**

1. Titre : Programme, Date d'arrêté, périmètre.
2. Synthèse : nombre d'Entités par couleur, changements depuis J-1 et J-5, trois messages clés.
3. Carte météo : tableau Entités × Météo, flèche de tendance, Règle déclenchante principale.
4. Une slide par Entité rouge ou orange : Règles déclenchantes, KPI clés, Brouillon de commentaire (Palier 2), Prévision.
5. Tendances : stock de bloquantes et taux de KO sur 8 semaines.
6. Anomalies prioritaires : les 10 bloquantes les plus anciennes.
7. Annexe méthode : Grille de météo appliquée, sources, traçabilité.

#### FR-25 : Commande unique [INDISPENSABLE]
Le Pilote peut produire le Rapport quotidien d'une Date d'arrêté par une seule commande, qui enchaîne extraction, Instantanés, KPI, Météo, Prévision, puis, si un LLM est configuré, classification des Causes racines, Explications sourcées, Brouillons de commentaire et narration, et enfin le rendu.
- Sans option, la Date d'arrêté est le dernier Jour ouvré écoulé.
- Les fichiers produits sont nommés avec la Date d'arrêté.
- En cas d'échec d'une étape : code de sortie non nul, message qui nomme l'étape en échec, aucun fichier de Rapport quotidien déposé.

#### FR-26 : Classeur Excel [INDISPENSABLE]
Le système produit le classeur au format ci-dessus.
- Les 9 onglets sont présents ; les chiffres sont identiques à ceux des Instantanés (test automatique).

#### FR-27 : Présentation PowerPoint [INDISPENSABLE]
Le système produit la présentation au format ci-dessus, sur un gabarit neutre sans charte réelle.
- Les 7 sections sont présentes, avec une slide par Entité rouge ou orange ; les chiffres sont identiques à ceux des Instantanés (test automatique).

#### FR-28 : Fonctionnement en Palier 1 seul [INDISPENSABLE]
Sans LLM configuré, le Rapport quotidien est produit en entier ; les zones de commentaire portent la mention « commentaire non généré (Palier 1) ».

#### FR-29 : Liens vers les tickets [INDISPENSABLE]
Chaque clé de ticket affichée dans l'Excel, le PowerPoint ou l'interface est un lien vers le ticket dans Jira.

### 4.7 Couche LLM (Palier 2)

**Description :** le LLM lit, classe et rédige. Il ne calcule jamais un chiffre. Tout texte lui est transmis après Pseudonymisation. Chaque sortie est contrôlée, mise en cache et journalisée. Réalise UJ-2.

#### FR-30 : Fournisseur interchangeable [INDISPENSABLE]
L'auteur peut choisir le fournisseur et le modèle LLM en configuration, sans modifier le code.
- Au moins deux fournisseurs distants sont opérationnels : Anthropic et un second parmi OpenAI, Mistral, Google ou Groq (décision du 10/10/2026, H-11).
- Sur une réponse de dépassement de débit, l'appel est repris après une attente croissante, avec un nombre maximal de tentatives en configuration ; comportement testé avec une doublure.

#### FR-31 : Pseudonymisation [INDISPENSABLE]
Le système remplace les identifiants sensibles (FR-4) par des pseudonymes avant tout appel à un LLM. Les clés de ticket ne sont pas pseudonymisées.
- Sur le jeu généré, aucun identifiant sensible injecté ne figure dans les requêtes envoyées ni dans le Journal de traçabilité (test automatique).
- Une éventuelle ré-identification se fait localement, après les contrôles, jamais côté LLM.
- L'interface peut montrer côte à côte un texte original et sa version pseudonymisée.

#### FR-32 : Explication sourcée [INDISPENSABLE]
Pour chaque Entité rouge ou orange, le LLM rédige une Explication sourcée à partir des Règles déclenchantes, des KPI, des tickets en cause (FR-17) et de la répartition des Causes racines.
- Chaque phrase contient au moins une Citation.
- Un contrôle déterministe vérifie que chaque Citation existe, appartient à l'Entité et figure parmi les tickets en cause restitués par FR-17 à la Date d'arrêté.
- Une phrase dont une Citation échoue est retirée ; le nombre de phrases retirées est affiché et journalisé. Si plus de la moitié des phrases sont retirées, l'explication est régénérée une fois ; si l'échec persiste, elle est remplacée par « explication indisponible ».

#### FR-33 : Brouillon de commentaire [INDISPENSABLE]
Le système place un Brouillon de commentaire, issu de l'Explication sourcée, sur la slide de chaque Entité rouge ou orange et dans l'onglet Commentaires, avec la mention « brouillon IA, à valider ». La correction se fait dans le PowerPoint produit ; l'interface n'offre pas d'édition en v1.

#### FR-34 : Journal de traçabilité [INDISPENSABLE]
Chaque appel LLM et chaque Prévision sont enregistrés localement : horodatage, Date d'arrêté, Entité, versions de prompt, de modèle, de Grille et de données, fournisseur, entrées pseudonymisées, sortie, résultat des contrôles.

#### FR-35 : Classification des Causes racines [INDISPENSABLE]
Le LLM propose une Cause racine pour chaque Anomalie, après Pseudonymisation. La répartition des Causes racines par Entité alimente l'Explication sourcée et l'onglet Commentaires (décision du 10/10/2026, H-12).
- La classification est incrémentale : seules les Anomalies nouvelles ou modifiées depuis le dernier Passage sont classées ; les résultats sont mis en cache.
- La classification initiale du stock complet est une opération ponctuelle, exclue des budgets de NFR-2 et NFR-9.
- La Cause racine proposée est affichée comme une suggestion et n'est jamais écrite dans Jira.

#### FR-50 : Suites d'évaluation LLM [INDISPENSABLE]
Le dépôt contient des suites d'évaluation versionnées, lancées à la demande :
- classification : vérité terrain du générateur et 30 tickets rédigés à la main ;
- Explication sourcée : 10 cas, avec contrôle automatique des Citations et une grille de notation humaine de 1 à 5 (exactitude, utilité).

#### FR-36 : Détection de doublons [BONUS]
Le système signale des paires d'Anomalies probablement en doublon, avec un score, pour revue par le Pilote. Aucune fusion automatique.

#### FR-37 : Mode LLM local [BONUS]
Le système fonctionne avec un modèle exécuté sur le poste (8 Go de VRAM), via la même interface que FR-30 (décision du 10/10/2026, H-13).

#### FR-38 : Observabilité externe [BONUS]
Les appels LLM sont tracés dans un outil d'observabilité auto-hébergé, en complément du Journal de traçabilité, sans aucune donnée identifiante.

### 4.8 Agent conversationnel

**Description :** le Pilote interroge son Programme en langage naturel. L'Agent ne dispose que d'outils de consultation et ne peut rien écrire. Réalise UJ-3.

#### FR-39 : Outils de consultation [INDISPENSABLE]
L'Agent peut consulter la Météo et ses Règles déclenchantes, lister et filtrer les Anomalies, lire les Tendances hebdomadaires, lire les Prévisions et les Risques d'entrée en rouge, pour toute Date d'arrêté disponible.

#### FR-40 : Chiffres issus des outils [INDISPENSABLE]
Chaque nombre d'une réponse de l'Agent provient d'un résultat d'outil de la même conversation, et chaque ticket cité existe.
- Un contrôle automatique sur la suite d'évaluation compte zéro chiffre inventé.
- Quand les données ne permettent pas de répondre, l'Agent le dit.

#### FR-41 : Lecture seule [INDISPENSABLE]
L'Agent n'a aucun outil d'écriture : pas d'écriture dans Jira, pas d'envoi de mail, pas de modification de la configuration.

#### FR-42 : Suite d'évaluation de l'Agent [INDISPENSABLE]
Une suite de 15 questions types du Pilote mesure l'exactitude de l'Agent.
- Chaque question porte les éléments attendus (chiffres, Entités, tickets), vérifiés automatiquement dans la réponse.
- La suite inclut la question de la démo (« Quelles entités risquent de passer au rouge la semaine prochaine, et pourquoi ? ») et au moins 2 questions sans réponse possible dans les données.

### 4.9 Interface de démonstration

**Description :** une interface web locale sert de support à la démo de 10 minutes et d'écran de travail pour le Pilote. Réalise UJ-2, UJ-3 et UJ-4.

#### FR-43 : Écrans de démonstration [INDISPENSABLE]
L'interface présente : la carte météo du Programme, le détail d'une Entité (Règles déclenchantes, KPI, Explication sourcée avec liens, Prévision et facteurs explicatifs), l'Agent, le lancement de la Chaîne de reporting avec sa progression, et l'écran « Ce qu'il faut pour le faire en vrai » (FR-47).
- Chaque écran est atteignable en un clic depuis la carte météo.
- La progression affiche chaque étape de FR-25.

#### FR-44 : Avant / après [INDISPENSABLE]
L'interface affiche le temps de reporting manuel déclaré (en configuration, Q-5) à côté du temps mesuré du dernier Passage, sur deux bases : par Rapport quotidien, et cumulé sur une semaine (5 Rapports quotidiens).

#### FR-45 : Mode repli [INDISPENSABLE]
Si Jira ou le LLM est injoignable, l'auteur peut basculer en Mode repli :
- affichage du dernier Passage enregistré (Rapport quotidien, Météo, Explications sourcées, Prévisions) ;
- réponses de l'Agent aux questions de la démo, enregistrées lors d'une répétition et rejouées (décision du 10/10/2026) ;
- mention « Mode repli » visible en permanence ; les liens vers Jira peuvent être inactifs.

#### FR-46 : Comparaison Palier 1 / Palier 2 [INDISPENSABLE]
L'interface permet d'afficher une Entité avec et sans la couche LLM, pour montrer ce que chaque Palier apporte.

### 4.10 Portabilité

**Description :** le démonstrateur doit rendre crédible un portage sur l'outillage que la banque fournira (VM Python, Dataiku, Power Platform, poste seul). Réalise UJ-4.

#### FR-47 : Fiche « outillage demandé » et note de portage courte [INDISPENSABLE]
Le dépôt contient une fiche d'une page : liste priorisée des demandes d'outillage (spec § 8), tableau de correspondance par brique et, pour chaque cible, les points d'attention du portage.

#### FR-48 : Conteneur et note de portage détaillée [BONUS]
Le dépôt contient une image conteneur exécutable de la Chaîne de reporting et une note de portage détaillée vers Dataiku et Power Platform.

## 5. Exigences non fonctionnelles transverses

- **NFR-1 Chiffres déterministes.** Aucun KPI, aucune Météo, aucune Prévision n'est calculé par un LLM. Les sorties LLM ne contiennent que des nombres repris de valeurs calculées (contrôlés par FR-24, FR-40).
- **NFR-2 Performance.** Sur le poste de développement de l'auteur (caractéristiques consignées dans le README) et à la volumétrie de FR-2, le Rapport quotidien en Palier 1 est produit en moins de 5 minutes, extraction incrémentale comprise. En Palier 2, moins de 10 minutes pour au plus 4 Entités rouges ou oranges, classification incrémentale comprise (décision du 10/10/2026, H-14).
- **NFR-3 Reproductibilité.** Données régénérables par graine à Corpus de textes constant ; Rejeu idempotent (FR-14) ; réinjection Jira idempotente (FR-5).
- **NFR-4 Dépôt public.** Données, noms, gabarits et règles 100 % fictifs. Aucun secret dans le dépôt ; un contrôle automatique de secrets s'exécute en intégration continue.
- **NFR-5 Confidentialité des envois LLM.** Pseudonymisation systématique avant envoi (FR-31). Aucun identifiant sensible dans les journaux ni dans les traces.
- **NFR-6 Auditabilité.** Toute Météo est rattachée à une version de Grille ; toute sortie LLM et toute Prévision sont rattachées à des versions de prompt, de modèle, de Grille et de données (FR-34).
- **NFR-7 Tests.** Intégration continue verte à chaque jalon. Aucun appel LLM réel ni appel Jira réel dans les tests unitaires (fixtures et doublures). Les évaluations LLM (FR-42, FR-50) sont des suites séparées, lancées à la demande.
- **NFR-8 Portabilité.** Le cœur (extraction, Instantanés, KPI, Météo, Prévision, rendu) ne dépend d'aucun service propriétaire autre que Jira et s'exécute sur un poste seul. Toute variation d'environnement passe par la configuration.
- **NFR-9 Coût.** Infrastructure gratuite (Jira Cloud Free, outils open source). Coût LLM d'un Passage de démo complet inférieur à 1 €, classification initiale exclue (décision du 10/10/2026, H-15). Offres gratuites utilisées dans le respect de leurs limites de débit.
- **NFR-10 Lisibilité métier.** Chaque clé de la Grille de météo et de la configuration du Programme porte un commentaire en français (vérifié par test) ; chaque message d'erreur de configuration nomme le fichier, la clé et la valeur fautive.
- **NFR-11 Langue.** Interface, Rapport quotidien et sorties LLM en français.
- **NFR-12 Robustesse de la démo.** Sans réseau, la démo de 10 minutes reste jouable de bout en bout en Mode repli (FR-45), Agent compris pour les questions enregistrées.
- **NFR-13 Validation avant présentation.** La démo et la fiche FR-47 sont validées par le Responsable de mission avant toute présentation à un client. C'est une porte de passage hors logiciel, tracée dans le journal du jalon M7.

## 6. Hors objectifs

- Ce n'est pas un outil de production : pas d'authentification, pas de multi-utilisateurs, pas d'ordonnanceur, pas de publication automatique (SharePoint, mail).
- Aucune écriture dans Jira hors de l'injecteur du générateur ; aucune action automatique sur les tickets.
- Aucune reproduction du reporting, du gabarit ou des règles de météo réels d'un client.
- Le LLM ne calcule ni KPI, ni Météo, ni Prévision.
- Pas de tableau de bord en temps réel : le rythme est quotidien, sur Date d'arrêté.
- Pas de Météo forcée par le Pilote en v1 (Q-4).
- Pas d'édition des Brouillons de commentaire dans l'interface en v1.

## 7. Périmètre

### 7.1 Indispensable pour la démo de 10 minutes

- Palier 1 complet : FR-1 à FR-21, FR-25 à FR-29, FR-49, FR-51.
- Explication sourcée et ses prérequis : FR-24, FR-30 à FR-34.
- Classification des Causes racines et suites d'évaluation LLM : FR-35, FR-50.
- Agent en lecture seule : FR-39 à FR-42.
- Support de démo et portabilité : FR-43 à FR-47.

Arbitrages du 10/10/2026 (H-12, H-16) : la Baseline (avec son évaluation sur données réelles) et sa narration, l'adaptateur Data Center, la Pseudonymisation, le Journal de traçabilité local et le Mode repli restent indispensables ; la classification des Causes racines devient indispensable.

### 7.2 Bonus

- Modèle ML et facteurs explicatifs sur le Public Jira Dataset : FR-22, FR-23.
- Observabilité externe (Langfuse) : FR-38.
- Détection de doublons : FR-36.
- Mode LLM local : FR-37.
- Conteneur et note de portage détaillée : FR-48.

### 7.3 Ordre de réalisation et modalités

La démo Palier 1 doit être montrable avant tout travail LLM, puis chaque brique indispensable s'ajoute avant tout bonus. La capacité de l'auteur (environ 2 h par jour de semaine, plus le week-end) justifie cet ordre strict. Le découpage en epics revient à `bmad-create-epics-and-stories` ; correspondance indicative avec les jalons de la spec :

| Jalon | Contenu | Critère de sortie |
|---|---|---|
| M0 Socle | Dépôt, configuration, tests, intégration continue | CI verte, contrôle de secrets actif |
| M1 Données fictives | FR-1 à FR-5 | Scénarios de démo vérifiés au jour près ; injection idempotente sur site vierge |
| M2 ETL et calcul | FR-6 à FR-21, FR-49 | Réconciliation à 100 % ; Rejeu idempotent |
| M3 Rapport quotidien (Palier 1) | FR-25 à FR-29, FR-51 | Rapport quotidien en < 5 min ; **démo Palier 1 possible** |
| M4 Couche LLM | FR-24, FR-30 à FR-35, FR-50 | SM-3, SM-7, SM-9 atteints |
| M5 Prévision avancée (bonus) | FR-22, FR-23 | SM-8 |
| M6 Agent et démo | FR-39 à FR-46 | SM-4, SM-5 |
| M7 Portage | FR-47 (FR-48 en bonus) | NFR-13 : validation du Responsable de mission |

Modalités reprises de la spec : point de contrôle avant chaque jalon, mode plan pour les modifications multi-fichiers, journal de fin de jalon, hypothèses consignées dans `docs/QUESTIONS.md`.

## 8. Risques

| Risque (spec § 10) | Mitigation | Exigences |
|---|---|---|
| Démo jugée « trop synthétique » | Vraie API Jira ; Baseline évaluée sur données réelles publiques ; Scénarios de démo plausibles | FR-3, FR-5, FR-6, FR-51 |
| Promesse non tenable sur l'outillage réel (Data Center, réseau, droits) | Adaptateur Data Center dès M2 ; Paliers dissociés ; fiche d'outillage | FR-7, FR-28, FR-47 |
| LLM refusé par la banque | Palier 1 autonome. Le mode LLM local n'est qu'en bonus : risque partiellement couvert, à dire à l'oral | FR-28, FR-37 |
| Réutilisation chez le client de code écrit sur temps personnel | Dépôt public sous licence MIT, aucun élément réel ; validation avant présentation | NFR-4, NFR-13 |
| Site Jira Free désactivé après inactivité | Réinjection idempotente sur site vierge, clés stables ; Mode repli | FR-5, FR-45 |
| Panne réseau ou LLM pendant la démo | Mode repli, Agent compris | FR-45, NFR-12 |
| Dérive de coût ou de débit LLM | Classification incrémentale, cache, reprise sur dépassement de débit | FR-14, FR-30, FR-35, NFR-9 |

## 9. Indicateurs de succès

**Principaux**
- **SM-1 Fiabilité des chiffres** : réconciliation avec le Rapport de référence, 100 % d'égalité. Valide FR-11, FR-13, FR-16, FR-26.
- **SM-2 Gain de temps** : temps de production du Rapport quotidien automatique (< 5 min) contre temps manuel déclaré, par jour et par semaine. C'est l'argument central de la démo. Valide FR-25, FR-44, NFR-2.
- **SM-3 Explication fidèle** : 100 % de Citations valides après contrôle ; note humaine moyenne ≥ 4/5 (exactitude, utilité) sur 10 cas. Valide FR-32, FR-33, FR-50.
- **SM-4 Agent** : ≥ 13/15 réponses correctes, zéro chiffre inventé. Valide FR-39 à FR-42.
- **SM-5 Démo** : au moins 3 répétitions chronométrées de 10 minutes au plus, dont une en Mode repli, sans intervention hors script. Valide FR-43 à FR-46, NFR-12.

**Secondaires**
- **SM-6 Prévision sur Scénarios de démo** : en fin d'historique, A sort dans l'horizon, B ne sort pas, C est signalée en Risque d'entrée en rouge. Valide FR-20, FR-21.
- **SM-7 Pseudonymisation** : zéro identifiant sensible injecté retrouvé dans les requêtes et les journaux. Valide FR-31, NFR-5.
- **SM-8 [BONUS] Modèle ML** : meilleur que la Baseline en AUC et score de Brier sur le Public Jira Dataset. Valide FR-22.
- **SM-9 Classification** : F1 macro ≥ 0,8 sur des textes générés par un autre modèle que le classifieur et sur 30 tickets rédigés à la main. Valide FR-35, FR-50.
- **SM-10 Baseline sur données réelles** : score de Brier meilleur que la prévision naïve sur le Public Jira Dataset. Valide FR-51.

**Contre-indicateurs (à ne pas optimiser)**
- **SM-C1 Nombre de fonctions LLM** : ajouter des usages LLM ne rend pas la démo plus convaincante ; le Palier 1 seul doit rester convaincant. Contrebalance SM-2 et SM-5.
- **SM-C2 Fluidité des textes** : une explication plus élégante mais moins citée est une régression. Contrebalance SM-3.
- **SM-C3 Grille ajustée aux scénarios** : des seuils réglés au cas près pour faire passer les Scénarios de démo enlèvent toute crédibilité à la Grille. Les seuils restent ronds et défendables ; ce sont les données qui s'adaptent. Contrebalance SM-6.
- **SM-C4 Performance du Modèle ML seule** : un gain d'AUC au prix de facteurs explicatifs illisibles n'est pas un progrès pour un Sponsor bancaire. Contrebalance SM-8.
- **SM-C5 Refus de l'Agent** : un Agent qui répond trop souvent « données insuffisantes » obtient zéro chiffre inventé sans être utile. Au plus 1 refus sur les 13 questions répondables. `[HYPOTHÈSE H-22]` Contrebalance SM-4.

## 10. Questions ouvertes

Seule Q-5 reste ouverte ; elle ne bloque pas les étapes suivantes.

1. ~~**Q-1** Historique dans Jira Cloud~~ : Journal d'événements + Source composite (FR-5, FR-49).
2. ~~**Q-2** Seuils par Phase ou par Vague~~ : non en v1.
3. ~~**Q-3** Hystérésis de sortie du rouge~~ : non en v1, Météo sans état (FR-16).
4. ~~**Q-4** Météo forcée par le Pilote~~ : non en v1.
5. **Q-5** Temps de reporting manuel à afficher dans l'avant / après : valeur déclarative à fournir en configuration (FR-44).
6. ~~**Q-6** Explication sourcée pour les orange~~ : oui, rouge et orange (FR-32).

## 11. Index des hypothèses

Suivi détaillé dans `docs/QUESTIONS.md`.

**Tranchées le 10/10/2026**
- **H-1** Aucun jour férié. **H-2** Volumétrie 3 000 à 5 000 Anomalies, 10 Entités. **H-3** Au plus 2 Entités rouges en fin d'historique. **H-4** ≥ 10 % de descriptions avec identifiant fictif.
- **H-5** Historique porté par le Journal d'événements. **H-6** Grille de météo par défaut.
- **H-7** Vélocité et horizon de 10 Jours ouvrés. **H-8** Horizon de 5 Jours ouvrés pour le Risque d'entrée en rouge.
- **H-9** Excel en 9 onglets. **H-10** PowerPoint en 7 sections. **H-11** Anthropic + un second fournisseur.
- **H-12** Classification indispensable (modifiée). **H-13** LLM local en bonus.
- **H-14** Palier 2 en moins de 10 minutes. **H-15** Moins de 1 € par Passage de démo.
- **H-16** Baseline, narration, Data Center, Pseudonymisation, Journal de traçabilité et Mode repli indispensables.

**À confirmer (non bloquantes, issues de la relecture)**
- **H-17** (Glossaire) Workflow fictif des Statuts d'Anomalie et définitions d'Anomalie ouverte, d'Entrée et de Sortie.
- **H-18** (Glossaire) Sept catégories de Cause racine.
- **H-19** (Glossaire) Fenêtre glissante de 5 Jours ouvrés ; J-5 remplace J-7.
- **H-20** (FR-13) Rapport de référence sur un jeu réduit (2 Entités, environ 60 tickets).
- **H-21** (FR-51) Référence naïve : taux historique de sortie sous N jours ; critère : score de Brier.
- **H-22** (SM-C5) Au plus 1 refus de l'Agent sur 13 questions répondables.
