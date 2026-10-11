# Passe de polissage : addendum.md

Revue `bmad-review`, lentilles `structure` puis `prose`. Lecteur : humains (défaut). Guide de style : Microsoft Writing Style Guide, adapté au français.

**Lecture du document :** cet addendum fournit à `bmad-architecture` les choix techniques et les méthodes de calcul que le PRD renvoie hors de son périmètre.

**Modèle de structure retenu :** document de référence technique (sections A à G par sujet). La structure tient.

## Constats

| Passe | Texte d'origine | Texte révisé | Changements | Statut |
|---|---|---|---|---|
| structure | En-tête « Source : spec v0.2, §§ 4, 8, 9. » | « …§§ 4, 8, 9 et 11. » | Le § B cite le § 11 de la spec. La liste des sources est maintenant complète. | Appliqué |
| structure | § F « Données publiques » recoupe le protocole du § E (cible, comparaison en AUC et Brier) | QUESTION : fusionner F dans le protocole du § E ? | Les cibles diffèrent (stock d'un projet pour FR-51, ticket pour FR-22). Une fusion demanderait d'arbitrer le fond. | Non appliqué (sens) |
| prose | § B « (spec § 11 Q4) » | « (question 4 du § 11 de la spec, distincte de Q-4 du PRD) » | « Q4 » se confondait avec Q-4 du PRD (Météo forcée). | Appliqué |
| prose | § C « (semaine 1 jour 1 …) ancrées à la génération sur le dernier Jour ouvré écoulé » | « (semaine 1, jour 1, etc.), ancrées sur le dernier Jour ouvré écoulé à la date de génération » | Ordre des mots clarifié. Sens identique à FR-2. | Appliqué |
| prose | § C « généré une fois (modèle différent du classifieur) » | « généré une fois (par un LLM différent du classifieur des Causes racines) » | « modèle » était ambigu. Le libellé s'aligne sur FR-2. | Appliqué |
| prose | § E « (Sorties − Entrées) de bloquantes » | « (Sorties − Entrées) d'Anomalies bloquantes » | Nom manquant. | Appliqué |
| prose | § E « d'IND-1, IND-3, IND-4 » | « d'IND-1, d'IND-3 et d'IND-4 » | Énumération rendue grammaticale. | Appliqué |
| prose | § F URL nue suivie d'un point | `<https://…>` précédée d'un deux-points | Lien cliquable. Le point final ne fait plus partie de l'URL. | Appliqué |
| prose | § D, YAML `ind7_min_entrees_7j` | Consider : `ind7_min_entrees_fenetre` ? | Le suffixe « 7j » contredit la Fenêtre glissante de 5 Jours ouvrés (H-19). C'est une clé de configuration dans un bloc de code : laissé à l'architecture. | Non appliqué |
| prose | § E protocole « sous N jours » et § F « sous N jours » | Consider : « sous N Jours ouvrés » ? | FR-22 parle de Jours ouvrés. Pour le jeu de données public, l'unité est peut-être volontairement calendaire. | Non appliqué (sens) |
| prose | § D, libellés YAML en minuscules (« jours ouvrés », « cas de test », « phase en cours ») | Aucun | Bloc de code illustratif, hors du champ de la passe prose. | Non appliqué |

## Synthèse

- 7 modifications appliquées dans le texte, plus une retouche de formulation sur la même ligne du § B (8 Edit au total).
- Aucun identifiant, seuil ni nombre modifié. Aucun bloc de code modifié.
- Non appliqué : la fusion F/E, l'unité « jours » ou « Jours ouvrés », et la clé YAML `_7j`.
