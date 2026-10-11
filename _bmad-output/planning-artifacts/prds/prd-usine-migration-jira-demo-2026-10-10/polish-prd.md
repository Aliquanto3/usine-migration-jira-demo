# Passe de polissage : prd.md

Revue `bmad-review`, lentilles `structure` puis `prose`. Lecteur : humains (défaut). Guide de style : Microsoft Writing Style Guide, adapté au français.

**Lecture du document :** ce PRD sert à l'auteur (seul développeur) et aux étapes BMAD suivantes (UX, architecture, epics) à construire le démonstrateur sans réinterpréter le besoin.

**Modèle de structure retenu :** document de référence d'exigences (objet, vision, utilisateurs, glossaire, fonctionnalités avec FR, NFR, hors objectifs, périmètre, risques, indicateurs, questions, index). La structure tient. Elle définit les notions avant de les utiliser et chaque FR a une forme stable.

Volume : 7 995 mots (word_metrics). Réduction visée : aucune. Il s'agit d'une passe de polissage, pas de coupe.

## Constats

| Passe | Texte d'origine | Texte révisé | Changements | Statut |
|---|---|---|---|---|
| structure | § 7.1, liste « Palier 1 complet : FR-1 à FR-21, FR-49, FR-51, FR-25 à FR-29 » | « FR-1 à FR-21, FR-25 à FR-29, FR-49, FR-51 » | Ordre croissant dans la liste. Même ensemble de FR, aucune renumérotation. | Appliqué |
| structure | § 8, Risques, colonne Exigences « FR-5, FR-6, FR-51, FR-3 » | « FR-3, FR-5, FR-6, FR-51 » | Ordre croissant, même ensemble. | Appliqué |
| structure | § 7.1 « Arbitrages du 10/10/2026 : … » | « Arbitrages du 10/10/2026 (H-12, H-16) : … » | H-12 et H-16 n'étaient rattachées à aucun passage du corps. Le lien index → corps est maintenant explicite. | Appliqué |
| structure | § 4.5 FR-51 et FR-50 placées hors ordre numérique dans leurs fonctionnalités | PRESERVE | Règle annoncée au § 0 (nouvelles FR rangées dans leur fonctionnalité). Ne pas déplacer. | Conservé |
| structure | § 7.2 « Observabilité externe (Langfuse) » | QUESTION | Nom d'outil dans le PRD alors que les choix techniques vivent dans l'addendum. Retrait possible, laissé à l'auteur. | Non appliqué |
| prose | § 3 Glossaire, 53 entrées « **Terme** — définition » | « **Terme** : définition » | Tirets cadratins remplacés par le deux-points, comme dans le reste du document (§ 2.1, § 9). Termes inchangés. Le nom « Banque Exemple — migration SI cœur » est conservé tel quel. | Appliqué |
| prose | Descriptions de fonctionnalités : « Réalise UJ-1, UJ-2. », « UJ-3, UJ-4. », « UJ-1, UJ-2, UJ-4. », « UJ-2, UJ-3, UJ-4. » | « … et UJ-n. » | Forme harmonisée avec « Réalise UJ-1 et UJ-4. » (§ 4.2). | Appliqué (4 endroits) |
| prose | § 4.5 Description : « …facteurs explicatifs déterministes, et elle est évaluée sur des données réelles publiques pour échapper… » | « …facteurs explicatifs déterministes. Elle est évaluée sur des données réelles publiques, pour échapper… » | Phrase trop longue coupée en deux. | Appliqué |
| prose | FR-20 : « Vélocité mesurée sur 10 Jours ouvrés, horizon de 10 Jours ouvrés, tous deux en configuration (…). Méthode détaillée dans l'addendum. » | « La vélocité est mesurée sur 10 Jours ouvrés et l'horizon est de 10 Jours ouvrés, tous deux en configuration (…). La méthode détaillée figure dans l'addendum. » | Fragments nominaux transformés en phrases. Valeurs inchangées. | Appliqué |
| prose | § 4.6 Description : « aucun modèle existant n'est à reproduire » | « aucun gabarit de reporting existant n'est à reproduire » | « modèle » pouvait se confondre avec le Modèle ML. « gabarit » est déjà utilisé au § 0 et au § 6. | Appliqué |
| prose | FR-32 : « l'explication est régénérée une fois, puis remplacée par « explication indisponible » » | « l'explication est régénérée une fois ; si l'échec persiste, elle est remplacée par « explication indisponible » » | La lecture littérale remplaçait toujours l'explication après régénération. La correction rend explicite la seule lecture cohérente avec UJ-2. | Appliqué |
| prose | FR-5 : « …Jira Cloud Free : état courant des tickets en fin d'historique, champs personnalisés Entité, Vague, Domaine, Gravité, Phase. » | « …Jira Cloud Free : l'état courant des tickets en fin d'historique et les champs personnalisés Entité, Vague, Domaine, Gravité et Phase. » | Énumération rendue grammaticale. | Appliqué |
| prose | NFR-13 : « Porte de passage hors logiciel, tracée… » | « C'est une porte de passage hors logiciel, tracée… » | Fragment transformé en phrase. | Appliqué |
| prose | § 1 « chaîne pro code » | Consider : « chaîne pro-code » ? | Jargon assumé, laissé tel quel. | Non appliqué |
| prose | Index H-12 « Classification indispensable (modifiée) » | Consider : préciser ce qui a été modifié ? | Clarifier demanderait de réécrire le contenu de la décision. | Non appliqué (sens) |

## Synthèse

- 12 modifications appliquées : 11 Edit et 1 remplacement en lot sur le glossaire (53 lignes).
- Aucun identifiant, seuil, nombre ni périmètre modifié. Aucune FR déplacée ni supprimée. Frontmatter intact.
- Réduction : négligeable (quelques mots ajoutés pour transformer des fragments en phrases).
- Non appliqué : 2 QUESTION (Langfuse au § 7.2, « (modifiée) » sur H-12) et 1 suggestion de style (« pro code »).
