# Réconciliation spec v0.2 ↔ PRD (+ addendum)

Date : 10/10/2026. Sources : `SPEC-usine-migration-jira-demo.md` (v0.2, § 11 prioritaire), `prd.md`, `addendum.md`, `docs/QUESTIONS.md`.

Hors constats (décisions délibérées) : Langfuse, doublons, modèle ML + SHAP, mode LLM local, Dockerfile en bonus ; classification des Causes racines indispensable ; historique de 8 semaines issu du journal d'événements (H-5) ; stack dans l'addendum.

Bilan : **1 critique, 6 élevés, 10 moyens, 9 faibles.**

---

## Critique

### C-1. Le calendrier des Scénarios de démo ne permet pas de jouer le script de démo
- **Spec** : § 3 (A rouge en semaine 3, revient à l'orange en semaine 5) ; § 6 étapes 3–4 (A est rouge, A sort probablement sous 10 jours, B non) ; § 9 M5 (A et B correctement anticipés).
- **PRD** : FR-3, FR-20 (« A sort dans l'horizon »), FR-25 (Date d'arrêté par défaut = dernier Jour ouvré écoulé), UJ-2, UJ-4 (« lance le pipeline en direct sur Jira Cloud, ouvre la météo (A rouge… ») ; addendum § C (Jira porte l'état courant).
- **Constat** : en fin d'historique (semaine 8), A est orange depuis 3 semaines. Le pipeline lancé en direct sur Jira (état courant) ou à la date par défaut ne montre donc ni A rouge, ni une prévision de sortie de A. Rien ne fixe la Date d'arrêté de démo, ni l'ancrage du calendrier fictif sur la date réelle (les données vieillissent entre génération et démo).
- **Correctif proposé** : ajouter une exigence « Date d'arrêté de démo » : soit A redevient rouge en fin d'historique (re-scénariser A), soit la démo se joue à une Date d'arrêté en semaine 3–4 fixée en configuration, et ancrer le calendrier généré sur la date du jour à chaque régénération.

## Élevé

### E-1. Validation préalable du responsable de mission absente
- **Spec** : § 7 (« Validation préalable du responsable de mission avant de présenter la démo au client ») ; § 9 M7 (« Note validée par le responsable de mission »).
- **PRD** : aucune occurrence (ni FR, ni NFR, ni hors objectifs, ni SM).
- **Correctif proposé** : ajouter une NFR ou un critère de sortie « démo et fiche d'outillage validées par le responsable de mission avant toute présentation client » (porte de passage, non logicielle).

### E-2. FR-2 se trompe de modèle pour l'anti-circularité
- **Spec** : § 5 classification (« textes générés par un autre modèle que le classifieur »).
- **PRD** : FR-2 (« LLM distinct de celui qui sert à l'Explication sourcée ») ; FR-35 et SM-9 disent bien « classifieur ».
- **Correctif proposé** : dans FR-2, remplacer « celui qui sert à l'Explication sourcée » par « celui qui sert à la classification des Causes racines (FR-35) ».

### E-3. Reproductibilité par graine incompatible avec des textes générés par LLM
- **Spec** : § 9 M1 (« scénarios reproductibles par graine aléatoire ») ; § 10 (« données régénérables ») ; § 3 (« Script Python + LLM pour les textes »).
- **PRD** : FR-2 (« deux exécutions avec la même graine produisent des données identiques » + textes générés par LLM) ; NFR-3.
- **Constat** : un appel LLM n'est pas déterministe ; l'exigence est intenable telle quelle, et la régénération après désactivation du site Jira coûterait de nouveaux appels.
- **Correctif proposé** : préciser que les textes LLM sont générés une fois puis figés dans un corpus versionné (cache), et que la graine garantit l'identité des données à corpus constant.

### E-4. La validation de la prévision sur données réelles disparaît du périmètre indispensable
- **Spec** : § 3 (Public Jira Dataset : « une prévision évaluée sur des données synthétiques ne prouve rien ») ; § 5 Prévision ; § 10 risque « démo jugée trop synthétique » → « prévision validée sur des données réelles publiques ».
- **PRD** : FR-22, SM-8 en bonus ; la Baseline indispensable (FR-20, SM-6) n'est évaluée que sur les Scénarios synthétiques.
- **Constat** : l'argument anti-circularité et la mitigation du risque n° 1 ne tiennent plus si le bonus n'est pas livré, et rien ne le signale.
- **Correctif proposé** : soit évaluer la Baseline elle-même sur le Public Jira Dataset (indispensable, peu coûteux), soit consigner explicitement le risque accepté dans une section Risques et dans `docs/QUESTIONS.md`.

### E-5. Étape 4 de la démo affaiblie : ni probabilité, ni facteurs explicatifs dans le périmètre indispensable
- **Spec** : § 2 message 4 (« avec un niveau de confiance ») ; § 6 étape 4 (« A sort probablement sous 10 jours, B non, avec les facteurs explicatifs »).
- **PRD** : FR-20 (date + fourchette), FR-23 (facteurs SHAP) en bonus ; UJ-4 omet les facteurs.
- **Correctif proposé** : faire restituer par la Baseline ses facteurs déterministes (stock, entrées, sorties, vélocité nette et leur évolution) comme « facteurs explicatifs » et réécrire l'étape 4 du script en conséquence.

### E-6. NFR-12 promet une démo complète hors réseau que FR-45 ne couvre pas
- **Spec** : § 6 (étape 5 agent en direct) ; § 9 M6 (« démo de 10 min répétée sans accroc »).
- **PRD** : NFR-12 (« de bout en bout sans réseau grâce au mode repli ») ; FR-45 (rejeu du dernier passage) ; FR-37 (LLM local en bonus) ; SM-5.
- **Constat** : sans réseau, l'Agent (étape 5) et la narration n'ont pas de LLM ; le rejeu du pipeline ne couvre pas une conversation.
- **Correctif proposé** : étendre FR-45 aux réponses de l'Agent (conversations de démo enregistrées et rejouées, marquées « rejeu ») ou limiter NFR-12 au Palier 1 et aux sorties LLM déjà produites.

## Moyen

### M-1. La section Risques de la spec est entièrement absente
- **Spec** : § 10 (5 risques et leurs mitigations).
- **PRD** : aucune section Risques ; les mitigations sont dispersées (FR-5, FR-7, FR-28, FR-37 bonus, NFR-4) sans lien explicite.
- **Correctif proposé** : ajouter une section « Risques » qui reprend le tableau du § 10 et renvoie chaque mitigation à ses FR, en signalant celles passées en bonus (mode local, validation sur données réelles).

### M-2. Désactivation du site Jira Free : la réinjection ne couvre pas un site vierge
- **Spec** : § 10 (« Site Jira Free désactivé après inactivité prolongée » → « script de réinjection idempotent ; données régénérables »).
- **PRD** : FR-5 (idempotence = pas de doublons sur le même site) ; FR-29 (liens Jira) ; FR-32 (Citations).
- **Constat** : sur un nouveau site, projet, types de tickets et champs personnalisés sont à recréer, et les clés de ticket peuvent changer, cassant liens, Citations figées et Rapport de référence.
- **Correctif proposé** : ajouter à FR-5 « recrée projet, types et champs sur un site vierge, et garantit des clés de ticket stables (ou une table de correspondance) » ; rendre l'URL du site configurable.

### M-3. Modalités de travail Claude Code de la spec partiellement reprises
- **Spec** : § 9 (jalons courts, point de contrôle avant chaque jalon, mode plan, `docs/QUESTIONS.md`, journal de fin de jalon, aucun appel LLM réel dans les tests unitaires).
- **PRD** : NFR-7 (tests sans LLM réel, CI verte par jalon) ; le reste est absent ; les critères d'acceptation des jalons M0–M7 ne sont pas repris en § 7.3.
- **Correctif proposé** : ajouter en § 7.3 le journal de fin de jalon et le point de contrôle obligatoire, et reporter les critères d'acceptation de chaque jalon (avec le passage au quotidien).

### M-4. Avant / après : unité de temps ambiguë après le passage au quotidien
- **Spec** : § 1 (« temps consommé chaque semaine ») ; § 6 étape 1 (« temps actuel du reporting hebdomadaire ») ; § 11 Q2 (reporting quotidien).
- **PRD** : FR-44, SM-2, UJ-4, Q-5 (« temps de reporting manuel déclaré », sans période).
- **Correctif proposé** : fixer dans FR-44 l'unité de comparaison (par Rapport quotidien et cumul hebdomadaire = 5 × quotidien) pour éviter de comparer un temps hebdomadaire manuel à un temps quotidien automatique.

### M-5. Restes de la classification « bonus » après l'arbitrage H-12
- **Spec** : § 2 Palier 2 (« explication, classification… ») ; § 4 [6]a.
- **PRD** : § 4.7 description (« le LLM lit, rédige et, **en bonus**, classe ») ; Glossaire, Palier 2 (classification absente).
- **Correctif proposé** : supprimer « en bonus » en § 4.7 et ajouter la classification des Causes racines à la définition de Palier 2.

### M-6. Classification de chaque Anomalie : coût et durée non tenus à la volumétrie cible
- **Spec** : § 11 Q2 (plusieurs milliers d'anomalies), Q7 (Groq gratuit, limites de débit).
- **PRD** : FR-35 (« à chaque Anomalie »), NFR-2 (Palier 2 < 10 min), NFR-9 (< 1 € par passage), H-2 (3 000 à 5 000).
- **Correctif proposé** : préciser dans FR-35 une classification incrémentale (seulement les Anomalies nouvelles ou modifiées), mise en cache, hors du chemin critique du Rapport quotidien.

### M-7. Fusion journal d'événements + mises à jour Jira en direct non spécifiée
- **Spec** : § 4 [1] (extraction incrémentale avec changelog) ; § 6 étape 2 (extraction Jira en direct).
- **PRD** : FR-6, FR-8 (« mêmes Instantanés sur les dates communes ») ; addendum § C (Jira porte l'état courant et les mises à jour en direct).
- **Constat** : les deux sources coexistent (historique dans le journal, changements récents dans Jira) mais aucune exigence ne dit comment elles se combinent ni laquelle fait foi en cas d'écart ; « dates communes » est vide de sens si Jira n'a pas d'historique.
- **Correctif proposé** : ajouter une exigence de fusion (journal jusqu'à la date d'injection, changelog Jira ensuite, Jira fait foi sur l'état courant) avec un test de cohérence.

### M-8. Questions ouvertes du PRD désynchronisées de `docs/QUESTIONS.md`
- **Spec** : § 11 (décisions du 10/10/2026).
- **PRD** : § 9 présente Q-2 à Q-6 comme ouvertes ; `QUESTIONS.md` les marque tranchées (proposition par défaut acceptée).
- **Correctif proposé** : barrer Q-2, Q-3, Q-4, Q-6 en § 9 avec la décision, et ne laisser ouverte que Q-5 (valeur à fournir).

### M-9. Cas limite de UJ-1 sans exigence
- **Spec** : § 4 (idempotence), § 6 (démo robuste).
- **PRD** : UJ-1 (« Jira injoignable : arrêt explicite, pas de rapport partiel ») ; aucune FR ne le porte (FR-6 ne traite que le repère).
- **Correctif proposé** : ajouter à FR-25 « en cas d'échec d'une étape, aucun fichier de Rapport quotidien n'est déposé et le message nomme l'étape en échec ».

### M-10. Note de portage Dataiku / Power Platform passée en bonus sans arbitrage tracé
- **Spec** : § 9 M7 (Dockerfile + note de portage + fiche d'une page, note validée par le responsable de mission) ; § 2 message 6.
- **PRD** : FR-48 (conteneur **et** note de portage en bonus) ; FR-47 (fiche seule).
- **Constat** : seul le Dockerfile a été arbitré bonus ; la note de portage est entraînée avec lui.
- **Correctif proposé** : scinder FR-48 (conteneur bonus) et garder une note de portage courte en indispensable, ou tracer l'arbitrage dans `QUESTIONS.md`.

## Faible

### F-1. Journal de traçabilité oublié dans le rappel de l'arbitrage H-16
- **Spec** : § 7 Traçabilité.
- **PRD** : § 7.1 (phrase d'arbitrage) et § 10 (index H-16) omettent le Journal de traçabilité, que `QUESTIONS.md` H-16 inclut (FR-34).
- **Correctif proposé** : ajouter « Journal de traçabilité local (FR-34) » dans les deux passages.

### F-2. Balises `[HYPOTHÈSE]` sur des hypothèses confirmées
- **PRD** : § 4.4 (`[HYPOTHÈSE H-6]`, confirmée), FR-37 (`[HYPOTHÈSE H-13]`, confirmée) ; la convention du § 0 réserve la balise aux inférences non confirmées.
- **Correctif proposé** : remplacer par « (décision du 10/10/2026, H-n) » pour H-5, H-6, H-12, H-13, H-16.

### F-3. Numérotation des semaines des Scénarios non définie en calendrier quotidien
- **Spec** : § 3 (semaine 3, semaine 5).
- **PRD** : FR-3, FR-12.
- **Correctif proposé** : définir la semaine 1 (premier Jour ouvré du journal) et le jour de bascule attendu dans FR-3, pour rendre FR-16 testable au jour près.

### F-4. La fiche d'outillage n'est pas accessible depuis l'interface de démo
- **Spec** : § 6 étape 6 (liste d'outillage du § 8).
- **PRD** : FR-43 (écrans) ne cite pas la fiche ; FR-47 la place dans le dépôt.
- **Correctif proposé** : ajouter à FR-43 un écran ou un lien « Ce qu'il faut pour le faire en vrai » affichant la fiche FR-47.

### F-5. Suites d'évaluation LLM (explication, classification) non portées par une FR
- **Spec** : § 5 (grille humaine 1–5 sur 10 cas ; 30 tickets rédigés à la main) ; § 9 M4 (« suite d'évaluation »).
- **PRD** : SM-3, SM-9, FR-35 ; seule l'évaluation de l'Agent a une FR (FR-42).
- **Correctif proposé** : ajouter une FR « Suites d'évaluation LLM » (10 cas d'explication notés, 30 tickets manuscrits, jeu de vérité terrain versionné).

### F-6. Contraintes de moyens du § 11 Q6–Q7 non reprises
- **Spec** : § 11 Q6 (priorité sur le projet « agent appels d'offres »), Q7 (≈ 2 h par jour de semaine + week-end ; compression Headroom dans la référence d'implémentation).
- **PRD** : absent ; addendum § A omet Headroom.
- **Correctif proposé** : mentionner la capacité de l'auteur en § 7.3 (justifie l'ordre indispensable → bonus) et ajouter Headroom à l'addendum § A.

### F-7. Ré-identification après Pseudonymisation non spécifiée
- **Spec** : § 7 (pseudonymisation avant tout appel LLM).
- **PRD** : FR-31, FR-32, FR-33 ; rien ne dit si l'Explication affichée au Pilote garde les pseudonymes ou les remplace par les valeurs d'origine.
- **Correctif proposé** : préciser dans FR-31 que la ré-identification, si elle existe, se fait localement après contrôle, jamais côté LLM.

### F-8. UJ-2 suppose une correction du brouillon sans exigence associée
- **PRD** : UJ-2 (« elle corrige une phrase et présente ») ; FR-33 ne prévoit pas d'édition.
- **Correctif proposé** : préciser dans UJ-2 que la correction se fait dans le PowerPoint produit (pas d'édition dans l'interface en v1).

### F-9. Passage du niveau ticket au niveau Entité non défini pour le modèle ML (bonus)
- **Spec** : § 4 (probabilité de sortie du rouge sous N jours, par Entité) ; § 5 (résolution des tickets bloquants).
- **PRD** : FR-22 (prédiction par Anomalie, puis « appliqué aux Scénarios »).
- **Correctif proposé** : ajouter à FR-22 la règle d'agrégation (ex. probabilité que toutes les bloquantes ouvertes de l'Entité, moins le seuil, soient résolues sous N jours).

---

## Vérifications sans écart

- Météo à quatre couleurs : cohérente partout (Glossaire, § 4.4, addendum § D). Aucun reste « rouge/orange/vert » à trois couleurs.
- Rythme : quotidien avec Tendances hebdomadaires, cohérent ; seul l'avant / après hérite du « hebdomadaire » (M-4).
- Numérotation FR-1 à FR-48 continue ; § 7.1 et § 7.2 couvrent les 48 FR sans recouvrement ; étiquettes [INDISPENSABLE]/[BONUS] cohérentes avec § 7.
- Références FR de `docs/QUESTIONS.md` valides.
- Cibles du § 5 reprises : 100 % de réconciliation (FR-13, SM-1), F1 ≥ 0,8 (FR-35, SM-9), 100 % de Citations et ≥ 4/5 (SM-3), ≥ 13/15 et 0 chiffre inventé (SM-4).
- Traçabilité (§ 7) : FR-34, NFR-6, onglet Traçabilité.
- Aucun appel LLM réel dans les tests unitaires : NFR-7.
