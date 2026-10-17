# Revue accessibilité (WCAG 2.2 AA) de la spec UX

Contrastes recalculés le 2026-10-17 ; ceux de la spec sont confirmés (focus vert sur nuit 10,1:1 ; lien primaire 8,6:1 ; texte des pastilles OK). Écarts ci-dessous.

1. **high** · DESIGN.md `champ`, `bulle-reponse`, `segment` · La bordure de champ `#E6E6EC` sur blanc fait 1,24:1 (sur `fond` 1,15:1). WCAG 1.4.11 exige 3:1 pour délimiter select, textarea, case. Correction : bordure de champ ≥ 3:1 (ex. `#8A8A9E` = 3,4:1 sur blanc), garder `bordure` pour les cartes décoratives. Prévoir aussi le bord de la case et du segment inactif.

2. **high** · Bouton de lancement, Bascule Mode repli, Saisie · Un `<button disabled>` qui a le focus le perd (lancement, envoi, « Chaîne en cours… »), et un bouton désactivé n'est pas atteignable pour lire sa raison (« Lancement indisponible en Mode repli… »). Correction : `aria-disabled="true"` plus `aria-describedby` vers le motif, ignorer le clic ; après lancement, laisser le focus sur le bouton ou le déplacer sur le titre « Suivi de la Chaîne » (`tabindex="-1"`).

3. **high** · Bascule Mode repli · Cocher la case recharge l'interface : changement de contexte à la saisie (3.2.2) et perte du focus. Correction : bouton explicite « Appliquer », ou, si la case reste, annoncer le changement et rendre le focus à la case après rechargement.

4. **medium** · Sélecteur d'Entité · Même risque si le changement de `<select>` navigue. Correction : navigation par bouton « Afficher » ou liens ; en JS, mettre à jour le contenu, le `<title>` et déplacer le focus sur le `<h1>` (`tabindex="-1"`).

5. **medium** · Liste des étapes, barre · `aria-live="polite"` sur toute la liste, avec sondage chaque seconde, risque de répéter l'annonce. Correction : une région `role="status"` masquée visuellement n'annonçant que le changement d'étape (« Étape 4 sur 10 : kpi, en cours »), la barre en `role="progressbar"` (`aria-valuenow/max`, nom), l'échec en `role="alert"`. Le compteur reste visible.

6. **medium** · Barre de progression · Remplissage vert `#04F06A` sur piste lavande : 1,28:1 (1.4.11). Correction : remplissage `primaire` (7,8:1) ou bordure nuit de 1px ; la puce blanche/coche sur vert fait 1,5:1 : coche en `nuit`.

7. **medium** · Bandeaux d'erreur, « Serveur injoignable » · Aucun rôle précisé ; le sondage échoue chaque seconde. Correction : `role="alert"` sur erreur et succès/échec de fin de Chaîne (`role="status"` pour le succès), une seule annonce (pas de réinsertion à chaque échec de sondage). Pas de déplacement de focus, sauf bandeau de formulaire.

8. **medium** · Fil de l'Agent · « L'Agent consulte le Passage… » puis réponse qui remplace la précédente : annonces non spécifiées. Correction : région `aria-live="polite"` `aria-busy` pendant l'attente ; annoncer le texte de la réponse et son badge ; focus conservé sur la zone de saisie (ou sur la réponse si on la lit au clavier) ; vider la saisie sans perdre le focus.

9. **medium** · Filtre météo · Le tableau change sans annonce. Correction : `role="status"` « 1 Entité affichée sur 10 » après filtrage, message « Aucune Entité en… » dans la même région. Libellé visible du `<select>`.

10. **medium** · Clé de ticket, Fiche d'outillage, livrables · Liens `target="_blank"` sans avertissement (3.2.5/G201). Correction : texte ou icône « (nouvel onglet) » dans le nom accessible, `rel="noopener"` ; liens de téléchargement avec format (« .xlsx »).

11. **medium** · Clé de ticket sans lien · Infobulle « Lien Jira inactif en Mode repli » inaccessible au clavier (`title`, 1.4.13). Correction : texte visible en légende, ou `tabindex="0"` plus `aria-describedby`.

12. **medium** · Panneaux de Pseudonymisation, tableaux dans leur carte · Zones défilantes non focalisables (2.1.1) ; défilement synchronisé qui désoriente. Correction : `tabindex="0"`, `role="region"` et `aria-label`, focus visible ; synchro désactivable ou limitée à la souris ; les tableaux défilants idem.

13. **medium** · Tous les écrans · `<title>` non défini dans la spec. Correction : « {Écran} · Usine de migration », avec l'Entité sur le détail ; un seul `<h1>`, `h2` pour sections, `h3` pour encarts ; la fiche Markdown rendue démarre à `h2` (demoter son `h1`). `lang="fr"` présent dans la maquette : l'inscrire dans la spec.

14. **low** · Tableau des Entités · Ajouter `<caption>` (ou `aria-labelledby`), `scope="row"` sur la colonne Entité ; les flèches de tendance exposent leur texte alternatif.


15. **low** · Cibles et reflow · Bouton d'en-tête 40px contredit « ≥ 44px » (reste ≥ 24px, 2.5.8) ; la case de 20px doit avoir son libellé cliquable de 44px. À 320px : en-tête (marque, deux pastilles, bouton) et navigation de sept liens doivent s'enrouler sans défilement horizontal, ce que le tableau de rupture ne décrit pas sous 768px ; maquette en largeur fixe 1440px.

