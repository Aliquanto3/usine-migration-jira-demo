# Revue rubric walker — spine UX Usine de migration

Verdict global : paire solide. Le format est respecté (frontmatter, ordre des sections) et toutes les références `{token}` se résolvent. Les faiblesses sont la couverture des composants (DESIGN et EXPERIENCE ne se recoupent pas), des messages Streamlit présentés « mot pour mot » alors qu'ils sont paraphrasés, et des comportements de la maquette ou inventés qui ne sont pas signalés.

1. **medium** — EXPERIENCE, Voice and Tone et State Patterns. La spine affirme reprendre les messages Streamlit « mot pour mot ». Plusieurs diffèrent de `src/usine/ui/` :
   - Bandeau Mode repli : `app.py:79` ajoute « réels » et « les liens Jira sont inactifs ».
   - `REPLI_ABSENT` : `app.py:91` cite `manifeste.json` et propose « restaurer … ou désactiver le Mode repli ».
   - `LANCEMENT_REPLI` : le texte de `app.py:97` n'est pas celui de la spine (« Lancement indisponible… »).
   - Échec de Chaîne : `app.py:590` ajoute « : {fin} » et la variante « hors d'une étape ».
   - Mention de réponse rejouée : `agent.mention_repli` donne « réponse enregistrée le … sur le Passage {id}, rejouée sans LLM ». La spine écrit « …, sans LLM ».
   - « Aucun Passage publié » : trois formulations différentes selon l'écran (carte, Agent, Avant / après). La spine en met une seule.
   - `AUCUN_KPI` : « à la Date d'arrêté du Passage », contre « à cette Date d'arrêté ».
   *Fix :* citer le texte exact de chaque constante, ou écrire « paraphrase voulue » dans la table d'écarts. Retirer « mot pour mot » partout où ce n'est pas vrai.

2. **medium** — EXPERIENCE, State Patterns. Messages et états de l'UI actuelle absents :
   - « Ce Passage ne contient aucune Météo » (`app.py:189`, `app.py:241`) ;
   - `RISQUE_SANS_OBJET` (« Sans objet : l'Entité est déjà rouge. ») ;
   - `EXPLICATION_ABSENTE` ;
   - `progression.AUCUN_RAPPORT` après un échec ;
   - les erreurs de lecture (`app.py:151`, `356`, `387`), « Agent indisponible : session » (`437`), « Réponse de l'Agent impossible » (`443`) et `REFUS_REPLI` (`473`).
   *Fix :* ajouter ces lignes, ou un état générique « Lecture impossible : {détail} » avec le message exact.

3. **medium** — EXPERIENCE, State Patterns (Chaîne en attente) et Component Patterns (Segment Palier). Messages présentés comme repris de Streamlit alors qu'ils sont inventés ou détournés :
   - « En attente d'un lancement. » et « Chargement… » n'existent pas dans `src/usine/ui/`.
   - « Palier 1 : la même Entité sans aucune sortie LLM. » est l'infobulle `help=` du segment (`app.py:219`), pas un texte de remplacement. Le texte réel est `EXPLICATION_PALIER_1`, « commentaire non généré (Palier 1) ».
   - Le message « Lecture impossible / serveur injoignable » et le bandeau « L'Agent ne joint pas le LLM… » sont nouveaux mais non signalés.
   *Fix :* marquer ces textes « nouveaux » dans la table, sans les attribuer à Streamlit.

4. **medium** — Couverture des composants, DESIGN.Components contre EXPERIENCE.Component Patterns. Les noms ne sont pas identiques d'un fichier à l'autre : « Tuile de comptage » / « Tuiles de comptage », « Tableau » / « Tableau des Entités », « Étape de la Chaîne » / « Liste des étapes », « Segment » / « Segment Palier », « Encart Agent » / « Encart « Demander à l'agent » », « Bulles » / « Fil de l'Agent », « Comparatif avant / après » / « Comparatif ».
   - Sans comportement : Tuile KPI, Pastille météo, Badge de contrôle, Bandeau, Champs.
   - Sans spécification visuelle : Clé de ticket (style lien et état inactif), Filtre météo, Livrables, Sélecteur d'Entité, Sélecteur de ticket, Saisie de question.
   *Fix :* aligner les noms une fois pour toutes, puis compléter les lignes manquantes dans les deux fichiers.

5. **medium** — Maquette non reprise ou orpheline, DESIGN et EXPERIENCE. Éléments de la maquette qui ne sont dans aucun composant :
   - tableau « Règles déclenchantes » (colonnes Règle, Valeur, Météo, Tickets en cause, « +8 ») ;
   - blocs Prévision et Risque (intervalle, rythme de fermeture) ;
   - encart « Dernier Passage » (durée, nombre de tickets extraits), cité seulement dans la table de migration ;
   - bouton « Poser une question sur ENT-B » (comportement non dit : ouvre `/agent` avec la question pré-remplie ?) ;
   - liste « Outils de l'agent » ;
   - lien « ← Carte météo » du détail.
   *Fix :* une ligne par élément dans les deux tables.

6. **medium** — Contradiction maquette, Streamlit et EXPERIENCE (Détail, Risque). Pour une Entité rouge, la maquette affiche « Déjà rouge. Entité voisine la plus exposée : ENT-E… ». Streamlit affiche « Sans objet : l'Entité est déjà rouge. » La spine ne dit rien. Le texte de la maquette suppose une donnée ou un calcul qui n'existe peut-être pas (AD-9).
   *Fix :* trancher dans la spine et lister l'écart dans « Migration depuis Streamlit ».

7. **medium** — EXPERIENCE, Information Architecture. Le choix de l'Entité de la navigation est inventé et non signalé. « Dernière Entité vue, sinon la plus mal classée » demande une mémoire côté navigateur, et « plus mal classée » est ambigu en cas d'égalité. Le défilement synchronisé des panneaux, l'historique « Questions posées » et l'infobulle « Lien Jira inactif » sont aussi des inventions : l'infobulle est inaccessible au clavier et au tactile.
   *Fix :* préciser la règle (premier de la liste triée du tableau) ou la noter [ASSUMPTION] ; remplacer l'infobulle par un texte visible ou un `aria-label`.

8. **medium** — Couverture d'états, EXPERIENCE, State Patterns. Non traités :
   - Livrables xlsx/pptx en Mode repli (les fichiers sont-ils dans `demo/repli/passage/` ?). NFR-12 exige une démo de bout en bout hors réseau.
   - Pseudonymisation et Avant / après en Mode repli, alors que l'UI actuelle leur passe `repli`.
   - Erreur de réseau ou de téléchargement d'un livrable.
   - Entité absente d'un Passage de Palier 1 dans la carte.
   *Fix :* ajouter les lignes, ou noter « sans objet » avec la raison.

9. **medium** — EXPERIENCE, Key Flows (flux 4, étape 5) et Open Questions. Le surlignage des pseudonymes est la scène du climax du flux 4, et la spine reconnaît elle-même que ce surlignage n'est pas garanti ([ASSUMPTION]).
   *Fix :* écrire le flux avec la variante de repli (panneau de droite en texte brut) ou lier la décision à une story de l'Epic 7.

10. **low** — EXPERIENCE, Key Flows (flux 1, étapes 2 et 3). Deux « Elle clique « Lancer la Chaîne » » consécutifs : le premier est le bouton d'en-tête, le second celui de l'écran. Précisez lequel. Les flux 2 et 3 n'ont pas de chemin d'échec (LLM indisponible, ticket sans lien) alors que les états existent.

11. **low** — DESIGN, Shapes et Components. Contradiction : Shapes donne `{rounded.lg}` aux « puces d'étape », Components les veut rondes de 32px (`full`). La maquette met 14px sur la ligne d'étape et 10px sur l'option de segment (le DESIGN dit `lg`).

12. **low** — DESIGN, frontmatter. Le blanc `#FFFFFF` est codé en dur 8 fois (aucun token `blanc`), tout comme les rayons `4px` et `18px 18px 4px 18px`. L'espace `{spacing.nav}` (260px) contredit la prose « 220 à 260px ». Les fonds des pastilles météo ne sont pas tokenisés dans `components`. *Fix :* ajouter `blanc` et `rounded.bulle`, et lever l'ambiguïté du gabarit.

13. **low** — Références visuelles. La spine pointe le dossier `imports/maquette-canvas/` mais pas les quatre fichiers (`Main`, `Detail`, `Chaine`, `Agent`) à la section concernée. La règle « la spine fait foi en cas d'écart » est répétée trois fois (DESIGN Brand, EXPERIENCE Foundation et Information Architecture). *Fix :* lier chaque fichier dans Components ou dans Information Architecture.

14. **low** — EXPERIENCE, Accessibility Floor. Pas de `role="alert"` pour les bandeaux d'erreur ; pas de règle de focus à l'arrivée sur une page ou après changement de segment. Les ✅ de `docs/fiche-outillage.md` (rendus tels quels) contredisent « pas d'emoji ». *Fix :* ajouter le rôle et une règle de focus ; préciser le traitement des ✅.

15. **low** — Maquette et EXPERIENCE, Pied de réponse. La maquette écrit « ✓ Contrôle : conforme · chiffres et tickets vérifiés » ; la spine « Contrôle : conforme ». Le sous-texte (« · chiffres et tickets vérifiés ») est perdu sans que l'écart soit noté.

## Synthèse des gravités
high 0 · medium 8 · low 7.
