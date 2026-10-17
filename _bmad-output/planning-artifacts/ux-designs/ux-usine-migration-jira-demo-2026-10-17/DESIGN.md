---
name: Usine de migration — interface web
description: Copilote de pilotage d'une migration Jira, servi par FastAPI en pages HTML statiques. Charte WaveStack violet / vert, sans bibliothèque de composants.
status: final
updated: 2026-10-17
sources:
  - https://claude.ai/artifact/8i2xgWiBDhL79cF7g68Fyu
  - imports/maquette-canvas/
colors:
  # Charte WaveStack
  nuit: '#250F6B'
  primaire: '#451DC7'
  violet-2: '#3A2393'
  lavande: '#EDE7FE'
  lavande-texte: '#C9BDFF'
  vert-wavestack: '#04F06A'
  # Surfaces et encre
  blanc: '#FFFFFF'
  fond: '#F6F5FA'
  carte: '#FFFFFF'
  bordure: '#E6E6EC'
  bordure-champ: '#8A8A9E'
  encre: '#0A0A14'
  encre-secondaire: '#4A4A5E'
  desactive: '#8A8A9E'
  console: '#0A0A14'
  # Météo : fond de pastille / point
  meteo-vert-fond: '#CAFEE0'
  meteo-vert: '#0B9A4B'
  meteo-jaune-fond: '#FFF1C7'
  meteo-jaune: '#D9A100'
  meteo-orange-fond: '#FFE2CC'
  meteo-orange: '#C85A12'
  meteo-rouge-fond: '#FFD6DC'
  meteo-rouge: '#D80F2E'
  # Statuts
  succes-fond: '#CAFEE0'
  succes-texte: '#0A5A2E'
  refus-fond: '#FFF1C7'
  refus-texte: '#6B4A00'
  erreur-fond: '#FFD6DC'
  erreur-texte: '#8A0A1E'
typography:
  titre-page:
    fontFamily: Fredoka
    fontSize: 34px
    fontWeight: '600'
    lineHeight: '1.2'
  titre-section:
    fontFamily: Fredoka
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.3'
  titre-encart:
    fontFamily: Fredoka
    fontSize: 18px
    fontWeight: '600'
    lineHeight: '1.3'
  chiffre:
    fontFamily: Fredoka
    fontSize: 40px
    fontWeight: '600'
    lineHeight: '1.1'
  chiffre-kpi:
    fontFamily: Fredoka
    fontSize: 34px
    fontWeight: '600'
    lineHeight: '1.1'
  chiffre-date:
    fontFamily: Fredoka
    fontSize: 28px
    fontWeight: '600'
    lineHeight: '1.2'
  marque:
    fontFamily: Fredoka
    fontSize: 20px
    fontWeight: '600'
  corps:
    fontFamily: Atkinson Hyperlegible
    fontSize: 15px
    fontWeight: '400'
    lineHeight: '1.5'
  corps-lecture:
    fontFamily: Atkinson Hyperlegible
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  legende:
    fontFamily: Atkinson Hyperlegible
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.5'
  entete-tableau:
    fontFamily: Atkinson Hyperlegible
    fontSize: 13px
    fontWeight: '700'
    letterSpacing: 0.04em
  code:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.5'
rounded:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 14px
  xl: 18px
  logo: 10px
  bulle-question: 18px 18px 4px 18px
  bulle-reponse: 4px 18px 18px 18px
  full: 9999px
spacing:
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 20px
  '6': 24px
  gouttiere: 24px
  entete: 64px
  nav-min: 220px
  nav-max: 260px
  contenu-max: 1440px
  lecture-max: 760px
  cible-min: 44px
components:
  entete:
    background: '{colors.nuit}'
    foreground: '{colors.blanc}'
    height: '{spacing.entete}'
  logo:
    background: '{colors.vert-wavestack}'
    foreground: '{colors.nuit}'
    radius: '{rounded.logo}'
    size: 36px
  pastille-entete:
    background: '{colors.violet-2}'
    foreground: '{colors.blanc}'
    radius: '{rounded.full}'
  pastille-mode-reel:
    background: '{colors.vert-wavestack}'
    foreground: '{colors.nuit}'
    radius: '{rounded.full}'
  pastille-mode-repli:
    background: '{colors.lavande}'
    foreground: '{colors.nuit}'
    radius: '{rounded.full}'
  bouton-primaire:
    background: '{colors.primaire}'
    background-hover: '{colors.nuit}'
    background-disabled: '{colors.desactive}'
    foreground: '{colors.blanc}'
    radius: '{rounded.lg}'
    height: 48px
  bouton-secondaire:
    background: '{colors.blanc}'
    foreground: '{colors.nuit}'
    border: '1px solid {colors.primaire}'
    radius: '{rounded.lg}'
    height: '{spacing.cible-min}'
  bouton-entete:
    background: '{colors.blanc}'
    foreground: '{colors.nuit}'
    radius: '{rounded.md}'
    height: '{spacing.cible-min}'
  nav-lien:
    foreground: '{colors.encre-secondaire}'
    background-hover: '{colors.lavande}'
    radius: '{rounded.md}'
    height: '{spacing.cible-min}'
  nav-lien-actif:
    background: '{colors.primaire}'
    foreground: '{colors.blanc}'
  carte:
    background: '{colors.carte}'
    border: '1px solid {colors.bordure}'
    radius: '{rounded.xl}'
    padding: '{spacing.5}'
  encart-agent:
    background: '{colors.nuit}'
    foreground: '{colors.blanc}'
    suggestion-background: '{colors.violet-2}'
    radius: '{rounded.xl}'
  pastille-meteo-vert:
    background: '{colors.meteo-vert-fond}'
    dot: '{colors.meteo-vert}'
    foreground: '{colors.encre}'
    radius: '{rounded.full}'
  pastille-meteo-jaune:
    background: '{colors.meteo-jaune-fond}'
    dot: '{colors.meteo-jaune}'
    foreground: '{colors.encre}'
    radius: '{rounded.full}'
  pastille-meteo-orange:
    background: '{colors.meteo-orange-fond}'
    dot: '{colors.meteo-orange}'
    foreground: '{colors.encre}'
    radius: '{rounded.full}'
  pastille-meteo-rouge:
    background: '{colors.meteo-rouge-fond}'
    dot: '{colors.meteo-rouge}'
    foreground: '{colors.encre}'
    radius: '{rounded.full}'
  badge-controle-conforme:
    background: '{colors.succes-fond}'
    foreground: '{colors.succes-texte}'
    radius: '{rounded.full}'
  badge-controle-corrige:
    background: '{colors.lavande}'
    foreground: '{colors.nuit}'
    radius: '{rounded.full}'
  badge-hors-perimetre:
    background: '{colors.refus-fond}'
    foreground: '{colors.refus-texte}'
    radius: '{rounded.full}'
  etiquette-outil:
    background: '{colors.lavande}'
    foreground: '{colors.nuit}'
    radius: '{rounded.sm}'
    typography: '{typography.code}'
  journal:
    background: '{colors.console}'
    foreground: '{colors.lavande-texte}'
    radius: '{rounded.xl}'
    typography: '{typography.code}'
  barre-progression:
    track: '{colors.lavande}'
    fill: '{colors.primaire}'
    height: 8px
    radius: '{rounded.full}'
  segment:
    track: '{colors.lavande}'
    active-background: '{colors.primaire}'
    active-foreground: '{colors.blanc}'
    foreground: '{colors.nuit}'
    radius: '{rounded.lg}'
  champ:
    background: '{colors.blanc}'
    border: '1px solid {colors.bordure-champ}'
    focus-border: '{colors.primaire}'
    radius: '{rounded.md}'
    height: '{spacing.cible-min}'
  bulle-question:
    background: '{colors.primaire}'
    foreground: '{colors.blanc}'
    radius: '{rounded.bulle-question}'
  bulle-reponse:
    background: '{colors.carte}'
    border: '1px solid {colors.bordure}'
    radius: '{rounded.bulle-reponse}'
  marque-pseudonyme:
    background: '{colors.lavande}'
    foreground: '{colors.nuit}'
    radius: '{rounded.xs}'
    typography: '{typography.code}'
  bandeau-succes:
    background: '{colors.succes-fond}'
    foreground: '{colors.succes-texte}'
    radius: '{rounded.xl}'
  bandeau-repli:
    background: '{colors.lavande}'
    foreground: '{colors.nuit}'
    radius: '{rounded.xl}'
  bandeau-erreur:
    background: '{colors.erreur-fond}'
    foreground: '{colors.erreur-texte}'
    radius: '{rounded.xl}'
---

## Brand & Style

L'interface sert une démonstration de 10 minutes devant un Sponsor. Elle doit ressembler au produit d'une vraie équipe de pilotage, pas au tableau de bord d'un notebook. Elle reprend la charte WaveStack :

- un violet nuit qui tient le cadre (en-tête, titres) ;
- un violet vif pour l'action ;
- un vert électrique réservé à ce qui est vivant ou réussi (logo, Mode réel, étapes terminées).

Le ton visuel est sérieux et lisible. La police de titre ronde (Fredoka) l'adoucit et lui évite l'air d'un rapport bancaire.

La lisibilité prime : chiffres et identifiants (Entités, règles IND-x, tickets DEMO-x, outils de l'Agent) doivent se lire d'un coup d'œil sur un écran projeté. D'où une police de corps conçue pour la lecture (Atkinson Hyperlegible) et une police à chasse fixe pour tout ce qui est identifiant ou trace.

Références visuelles : la maquette canvas ([lien](https://claude.ai/artifact/8i2xgWiBDhL79cF7g68Fyu)), sept écrans. Les quatre premiers sont copiés dans `imports/maquette-canvas/` : `Main.dc.html`, `Detail.dc.html`, `Chaine.dc.html`, `Agent.dc.html`. Les écrans Avant / après, Pseudonymisation et Outillage sont sur le canvas seulement. En cas d'écart, `DESIGN.md` et `EXPERIENCE.md` font foi sur la maquette. Les écarts voulus sont listés dans `EXPERIENCE.md`, section Migration depuis Streamlit.

## Colors

- **Violet nuit (`{colors.nuit}`)** : fond de l'en-tête et de l'encart Agent, titres de page et de section, survol des boutons primaires. C'est la couleur du cadre.
- **Violet primaire (`{colors.primaire}`)** : boutons d'action, entrée de navigation active, option active d'un segment, liens, bulle de question, remplissage de la barre de progression. Une seule action primaire par zone.
- **Violet 2 (`{colors.violet-2}`)** : pastilles d'information de l'en-tête et suggestions de questions sur fond nuit. Jamais sur fond clair.
- **Lavande (`{colors.lavande}`)** : survols, étape en cours, pistes des segments et de la barre de progression, étiquettes d'outils, pseudonymes, bandeau du Mode repli. **Lavande texte (`{colors.lavande-texte}`)** : seulement du texte secondaire sur fond nuit ou console.
- **Vert WaveStack (`{colors.vert-wavestack}`)** : logo, pastille Mode réel, puce d'étape réussie (coche en `{colors.nuit}`), anneau de focus sur fond nuit. Jamais en texte sur fond clair, jamais pour la météo verte, qui a sa propre teinte.
- **Gamme météo** : chaque couleur a un fond pâle de pastille et un point saturé (`{colors.meteo-rouge-fond}` et `{colors.meteo-rouge}`, etc.). Le texte de la pastille reste en `{colors.encre}` et donne le nom de la couleur : la couleur ne porte jamais seule l'information. Ces quatre teintes ne servent qu'à la Météo.
- **Statuts** : `{colors.succes-fond}` et `{colors.succes-texte}` pour « Contrôle : conforme » et la Chaîne terminée ; `{colors.refus-fond}` et `{colors.refus-texte}` pour « Hors périmètre » ; `{colors.erreur-fond}` et `{colors.erreur-texte}` pour les échecs. Les trois mêmes paires marquent les niveaux « Oui », « À surveiller » et « Non » de la fiche d'outillage.
- **Surfaces** : fond de page `{colors.fond}`, cartes `{colors.carte}` bordées de `{colors.bordure}`, texte `{colors.encre}`, texte secondaire `{colors.encre-secondaire}`. Les champs ont une bordure plus foncée, `{colors.bordure-champ}`, pour rester visibles. Le journal de progression est la seule surface sombre du contenu (`{colors.console}`).

Contrastes calculés (WCAG 2.2) le 2026-10-17 :

| Paire | Ratio | Usage |
|---|---|---|
| `blanc` sur `primaire` | 9,3:1 | texte |
| `blanc` sur `nuit` | 15,5:1 | texte |
| `encre-secondaire` sur `fond` | 8,0:1 | texte |
| `encre-secondaire` sur `carte` | 8,6:1 | texte |
| `nuit` sur `vert-wavestack` | 10,1:1 | texte |
| `lavande-texte` sur `nuit` | 9,0:1 | texte |
| `lavande-texte` sur `console` | 11,5:1 | texte |
| `nuit` sur `lavande` | 12,9:1 | texte |
| `succes-texte` sur `succes-fond` | 7,5:1 | texte |
| `refus-texte` sur `refus-fond` | 7,2:1 | texte |
| `erreur-texte` sur `erreur-fond` | 7,4:1 | texte |
| `blanc` sur `meteo-rouge` | 5,2:1 | texte |
| `bordure-champ` sur `blanc` | 3,4:1 | élément d'interface (3:1 exigé) |
| `primaire` sur `lavande` | plus de 7:1 | barre de progression, segment actif |

Les points jaune (2,1:1) et vert (3,3:1) des pastilles sont décoratifs : c'est le libellé de la pastille qui porte l'information. La bordure des cartes (`{colors.bordure}`) est décorative elle aussi : les cartes ne sont pas interactives.

## Typography

Trois familles, servies en local par l'application (la démo doit tourner hors réseau, NFR-12) :

- **Fredoka 600**, pour les titres et les grands chiffres :
  - `{typography.titre-page}` : le titre unique de chaque écran ;
  - `{typography.titre-section}` : titres de carte ;
  - `{typography.titre-encart}` : encarts latéraux ;
  - `{typography.chiffre}` : tuiles de la carte météo et comparatif avant / après ;
  - `{typography.chiffre-kpi}` : tuiles KPI ;
  - `{typography.chiffre-date}` : date de la Prévision ;
  - `{typography.marque}` : nom dans l'en-tête.
- **Atkinson Hyperlegible 400 / 700**, pour tout le reste :
  - `{typography.corps}` par défaut ;
  - `{typography.corps-lecture}` pour les textes rédigés (Explication, réponse de l'Agent, fiche d'outillage, panneaux de Pseudonymisation) ;
  - `{typography.legende}` pour les sous-titres et les légendes de source ;
  - `{typography.entete-tableau}`, en capitales espacées, pour les en-têtes de colonne.
- **JetBrains Mono** (`{typography.code}`), pour les identifiants et les traces : clés de ticket, règles IND-x avec valeur et seuil, tendances J-1 et J-5, noms d'étapes de la Chaîne, noms d'outils de l'Agent, journal de progression, pseudonymes, chemins de fichiers.

Pas de texte de corps en Fredoka.

## Layout & Spacing

Échelle en multiples de 4, de `{spacing.1}` à `{spacing.6}`. Gouttière `{spacing.gouttiere}` entre les blocs et autour du contenu, `{spacing.4}` entre les tuiles, `{spacing.2}` à `{spacing.3}` à l'intérieur des cartes.

Gabarit commun à tous les écrans :

1. **En-tête** pleine largeur, hauteur minimale `{spacing.entete}`.
2. **Corps** centré, d'au plus `{spacing.contenu-max}` de large : navigation latérale, large de `{spacing.nav-min}` à `{spacing.nav-max}`, puis le contenu.
3. **Contenu** : une ligne de titre (titre, sous-titre, contrôles alignés à droite), puis une zone principale large et une colonne d'encarts d'environ 300px, qui passe sous la zone principale quand la place manque.

Les textes longs (fiche d'outillage, Explication, panneaux de Pseudonymisation) ne dépassent pas `{spacing.lecture-max}` de large, ou la moitié de la zone principale quand deux panneaux sont côte à côte. Les tableaux larges défilent horizontalement dans leur carte, jamais la page.

Points de rupture :

| Largeur | Disposition |
|---|---|
| 1024px et plus | Navigation latérale ; tuiles de comptage et tuiles KPI sur 4 colonnes. |
| 768 à 1023px | Navigation latérale ; colonne d'encarts sous la zone principale. |
| Moins de 768px | Navigation au-dessus du contenu, en liste qui s'enroule ; tuiles sur 2 colonnes ; panneaux et cartes jumelles empilés. |
| 320px | Tout reste lisible sans défilement horizontal de la page, tuiles comprises. |

## Elevation & Depth

L'ombre ne sert pas à hiérarchiser : les cartes se détachent du fond par la couleur et une bordure de 1px, et la profondeur vient des aplats sombres décrits dans Colors.

## Shapes

Formes arrondies et amicales, en accord avec Fredoka :

- `{rounded.xl}` (18px) : cartes, encarts, bandeaux, journal ;
- `{rounded.lg}` (14px) : boutons primaires et secondaires, segments, ligne d'étape de la Chaîne ;
- `{rounded.md}` (12px) : champs, liens de navigation, suggestions, bouton d'en-tête ;
- `{rounded.sm}` (8px) : étiquettes d'outils ;
- `{rounded.xs}` (4px) : pseudonymes, code en ligne ;
- `{rounded.full}` : pastilles (météo, en-tête, contrôle), puces d'étape, barre de progression.

Les bulles de l'Agent ont un coin vif du côté du locuteur (`{rounded.bulle-question}`, `{rounded.bulle-reponse}`).

## Components

Les noms ci-dessous sont aussi ceux des tableaux de `EXPERIENCE.md`.

**Cadre**

- **En-tête** : de gauche à droite, le logo carré `{components.logo}` (lettre « U » en Fredoka), le nom « Usine de migration » et le sous-titre « Copilote de pilotage · projet DEMO » en `{colors.lavande-texte}`. À droite :
  - la pastille « Passage publié · JJ/MM/AAAA HH:MM » (`{components.pastille-entete}`) ;
  - la pastille de mode (`{components.pastille-mode-reel}` ou `{components.pastille-mode-repli}`) ;
  - le bouton « Lancer la Chaîne » (`{components.bouton-entete}`).
- **Navigation latérale** : sept liens `{components.nav-lien}`, l'actif en `{components.nav-lien-actif}`.
- **Lien d'évitement** : « Aller au contenu », masqué jusqu'au focus, puis affiché en `{components.bouton-entete}` en haut à gauche.
- **Mention de données** : carte de légende sous la navigation, sur l'écran Carte météo seulement.
- **Bandeau** : pleine largeur du contenu, texte en gras. Trois variantes : `{components.bandeau-succes}`, `{components.bandeau-repli}`, `{components.bandeau-erreur}`. Le bandeau d'erreur peut contenir un bloc de code (20 lignes au plus) en `{typography.code}`.

**Carte météo**

- **Pastille météo** : fond pâle, point saturé de 12px, nom de la couleur en gras. Quatre variantes, de `{components.pastille-meteo-vert}` à `{components.pastille-meteo-rouge}`.
- **Tuile de comptage** : carte avec une pastille météo, le chiffre en `{typography.chiffre}` et la variation depuis J-1 en légende.
- **Filtre météo** : champ de sélection `{components.champ}`, libellé « Filtrer par météo » au-dessus.
- **Tableau des Entités** : style de tableau standard (voir Tableau).
- **Encart Agent** : `{components.encart-agent}`, avec le titre « Demander à l'agent », une phrase de cadrage en `{colors.lavande-texte}` et trois suggestions en liens pleine largeur.
- **Livrables du Passage** : carte, un lien en gras par fichier, suivi du type et de la taille en légende, puis l'heure de génération.

**Détail d'une Entité**

- **Lien de retour** : « ← Carte météo » en légende, au-dessus du titre.
- **Formulaire de sélection** : champ de sélection et `{components.bouton-secondaire}` « Afficher », alignés en bas. Il sert aussi pour le ticket de la Pseudonymisation.
- **Segment** : options dans une piste `{components.segment}`, l'option active en `{colors.primaire}` sur texte blanc. Il sert au Palier (détail) et à la période (avant / après).
- **Tuile KPI** : libellé en légende, valeur en `{typography.chiffre-kpi}`, précision en légende.
- **Tableau des Règles déclenchantes** : colonnes Règle, Valeur, Météo, Tickets en cause. Règle et valeur en `{typography.code}`, Météo en pastille. Les trois premières clés de ticket sont affichées, suivies de « +N ».
- **Explication** : carte avec le titre, le badge de contrôle à droite, le texte en `{typography.corps-lecture}` et ses Citations en clés de ticket, puis une légende de provenance. Phrases retirées au contrôle : liste en légende sous le texte.
- **Prévision** : date en `{typography.chiffre-date}` `{colors.nuit}`, puis l'intervalle et le rythme de fermeture en légende.
- **Risque** : carte de texte en `{typography.corps}`.
- **Bouton de question** : `{components.bouton-primaire}` pleine largeur de la colonne d'encarts.

**Lancement de la Chaîne**

- **Bouton de lancement** : `{components.bouton-primaire}`.
- **Bouton de mode** : `{components.bouton-secondaire}`, « Passer en Mode repli » ou « Revenir au Mode réel ».
- **Liste des étapes** : une ligne `{rounded.lg}` par étape, avec une puce ronde numérotée de 32px, le nom technique en `{typography.code}`, la description en légende et un badge d'état à droite. Quatre états :

  | État | Puce | Ligne et badge |
  |---|---|---|
  | Réussie | `{colors.vert-wavestack}`, coche en `{colors.nuit}` | badge `{colors.succes-fond}` |
  | En cours | `{colors.primaire}` | ligne sur `{colors.lavande}`, badge `{colors.primaire}` |
  | En attente | bordée, sur `{colors.fond}` | badge `{colors.fond}` |
  | Échec | `{colors.meteo-rouge}` | badge `{colors.meteo-rouge}`, texte blanc, libellé « Échec » |

  Une étape sautée (`sautee`) reprend l'apparence « En attente », avec le libellé « Sautée ».
- **Barre de progression** : `{components.barre-progression}`, compteur « n / 10 » en `{typography.code}` au-dessus à droite.
- **Journal de progression** : `{components.journal}`, lignes horodatées, la plus récente en haut.
- **Dernier Passage** : carte, trois lignes en légende (date et durée, tickets extraits et Entités, manifeste).

**Agent**

- **Fil de l'Agent** : la question en `{components.bulle-question}`, alignée à droite ; la réponse en `{components.bulle-reponse}`, précédée d'un avatar « IA » vert de 36px. La réponse se termine par un pied, séparé par une bordure, qui porte le badge de contrôle, « Outils appelés : » et une `{components.etiquette-outil}` par outil.
- **Saisie de question** : zone de texte `{components.champ}` sur deux lignes, libellé au-dessus, `{components.bouton-primaire}` « Envoyer » à droite.
- **Questions enregistrées** : boutons pleine largeur, bordés de `{colors.bordure-champ}`. La question affichée passe en `{colors.lavande}`, bordée de `{colors.primaire}`.
- **Outils de l'Agent** : carte qui liste chaque outil, une `{components.etiquette-outil}` suivie de sa description.
- **Badge de contrôle** : « ✓ Contrôle : conforme · chiffres et tickets vérifiés » (`{components.badge-controle-conforme}`), « Contrôle : corrigée » (`{components.badge-controle-corrige}`), « Contrôle : rejetée » et « Hors périmètre · aucune donnée inventée » (`{components.badge-hors-perimetre}`).

**Avant / après**

- **Comparatif avant / après** : deux cartes jumelles.
  - À gauche, « Reporting manuel » avec l'étiquette « déclaré » (fond `{colors.fond}`, bordure `{colors.bordure}`) et la valeur en `{typography.chiffre}` couleur `{colors.encre-secondaire}`.
  - À droite, « Chaîne » avec l'étiquette « mesuré » (`{colors.succes-fond}`) et la valeur en `{typography.chiffre}` couleur `{colors.nuit}`.
  - Au-dessus, un segment choisit la période ; dessous, un tableau donne les deux périodes, puis vient la légende de source.

**Pseudonymisation**

- **Panneaux de Pseudonymisation** : deux cartes jumelles titrées « Original » et « Version pseudonymisée », la seconde bordée de `{colors.primaire}`, avec l'étiquette « envoyée au LLM ». Texte en `{typography.corps-lecture}`, retours à la ligne conservés. Les pseudonymes sont marqués `{components.marque-pseudonyme}` quand leurs positions sont connues.

**Ce qu'il faut pour le faire en vrai**

- **Fiche d'outillage** : Markdown rendu en cartes de largeur `{spacing.lecture-max}`, sauf le tableau, qui prend toute la largeur et défile. Titres en Fredoka `{colors.nuit}`, liste des demandes numérotée en Fredoka `{colors.primaire}` sur `{colors.lavande}`. Dans le tableau, les marqueurs ✅, ⚠️ et ❌ de la fiche deviennent des pastilles de texte « Oui » (`{colors.succes-fond}`), « À surveiller » (`{colors.refus-fond}`) et « Non » (`{colors.erreur-fond}`), suivies du reste de la cellule.

**Éléments communs**

- **Tableau** :
  - en-têtes de colonne en `{typography.entete-tableau}` et `{colors.encre-secondaire}`, en-têtes de ligne en gras ;
  - lignes séparées par `{colors.bordure}`, cellules avec 14px × 16px de marge intérieure ;
  - colonnes d'identifiants en `{typography.code}` ;
  - lien d'action de ligne (« Détail ENT-B ») aligné à droite, en gras ;
  - légende du tableau en `{typography.legende}` au-dessus des en-têtes.
- **Clé de ticket** : `{typography.code}` en gras. En lien, `{colors.primaire}` souligné au survol, suivi d'une petite flèche sortante (icône SVG au trait, `aria-hidden`). Inactive, en `{colors.encre}`, sans soulignement ni flèche.
- **Champs** : sélecteurs et zones de texte en `{components.champ}`, libellé visible au-dessus en légende.
- **Focus clavier** : anneau de 2px décalé de 2px, en `{colors.primaire}` sur fond clair et en `{colors.vert-wavestack}` sur fond nuit.

## Do's and Don'ts

| À faire | À éviter |
|---|---|
| Nommer la couleur dans chaque pastille météo | Des pastilles emoji 🟢🔴 ou une couleur sans libellé |
| Réserver la gamme météo à la Météo | Colorer un bouton en rouge ou en vert météo |
| Vert WaveStack en aplat sous du texte violet nuit | Du texte vert WaveStack sur fond clair |
| Identifiants, règles, outils et traces en JetBrains Mono | Des clés de ticket en police de corps |
| Une action primaire violette par zone | Plusieurs boutons primaires concurrents |
| Bordures de 1px et aplats pour la hiérarchie | Ombres portées, dégradés, bordure gauche colorée sur les cartes |
| Bordure `bordure-champ` sur tout champ | Des champs bordés de `bordure`, invisibles sur blanc |
| Polices et icônes servies par l'application | Google Fonts ou un CDN chargés pendant la démo |
| Tableaux larges qui défilent dans leur carte | Une page qui défile horizontalement |
