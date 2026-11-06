---
name: Usine de migration — interface web
description: Copilote de pilotage d'une migration Jira, servi par FastAPI en pages HTML statiques. Charte générique v2.1, sombre d'abord, sans bibliothèque de composants.
status: final
updated: 2026-10-17
sources:
  - https://claude.ai/artifact/8i2xgWiBDhL79cF7g68Fyu
  - imports/maquette-canvas/
colors:
  # Charte générique v2.1, valeurs du thème clair (le format n'admet qu'un thème). Les valeurs
  # du sombre, thème par défaut, sont dans le bloc :root de src/usine/ui/statique/cadre.css.
  fond: '#F6F8FB'
  surface: '#FFFFFF'
  surface-alt: '#ECF0F5'
  trait: '#CED5DF'
  trait-fort: '#808A97'
  texte: '#121821'
  texte-attenue: '#4F5A68'
  primaire: '#1D5BC2'
  primaire-vif: '#164A9E'
  primaire-doux: '#E1EAFA'
  sur-primaire: '#FFFFFF'
  bouton: '#121821'
  bouton-survol: '#2A3442'
  sur-bouton: '#FFFFFF'
  accent: '#8F6300'
  accent-texte: '#8A5F00'
  accent-doux: '#FBF1D6'
  accent-aplat: '#E0B54A'
  succes: '#1B7043'
  succes-doux: '#E2F1E8'
  alerte: '#E8892A'
  alerte-texte: '#9A4A00'
  alerte-doux: '#FDEBDA'
  erreur: '#B3261E'
  erreur-doux: '#FCE4E1'
  focus: '#1F5FD1'
  sur-statut: '#FFFFFF'
  encre-pleine: '#121821'
  sur-encre: '#FFFFFF'
  sur-encre-attenue: '#C3CEDD'
typography:
  titre-page:
    fontFamily: Sora
    fontSize: 34px
    fontWeight: '600'
    lineHeight: '1.2'
  titre-section:
    fontFamily: Sora
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.3'
  titre-encart:
    fontFamily: Sora
    fontSize: 18px
    fontWeight: '600'
    lineHeight: '1.3'
  chiffre:
    fontFamily: Sora
    fontSize: 40px
    fontWeight: '600'
    lineHeight: '1.1'
  chiffre-kpi:
    fontFamily: Sora
    fontSize: 34px
    fontWeight: '600'
    lineHeight: '1.1'
  chiffre-date:
    fontFamily: Sora
    fontSize: 28px
    fontWeight: '600'
    lineHeight: '1.2'
  marque:
    fontFamily: Sora
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
    background: '{colors.encre-pleine}'
    foreground: '{colors.sur-encre}'
    height: '{spacing.entete}'
  logo:
    background: '{colors.primaire}'
    foreground: '{colors.sur-primaire}'
    radius: '{rounded.logo}'
    size: 28px
  pastille-entete:
    border: '1px solid {colors.sur-encre-attenue}'
    foreground: '{colors.sur-encre}'
    radius: '{rounded.full}'
  pastille-mode-reel:
    background: '{colors.succes}'
    foreground: '{colors.sur-statut}'
    radius: '{rounded.full}'
  pastille-mode-repli:
    border: '1px solid {colors.sur-encre-attenue}'
    foreground: '{colors.sur-encre}'
    radius: '{rounded.full}'
  bouton-primaire:
    background: '{colors.bouton}'
    background-hover: '{colors.bouton-survol}'
    background-disabled: '{colors.surface-alt}'
    foreground: '{colors.sur-bouton}'
    radius: '{rounded.lg}'
    height: 48px
  bouton-secondaire:
    background: '{colors.surface}'
    foreground: '{colors.texte}'
    border: '1px solid {colors.trait-fort}'
    radius: '{rounded.lg}'
    height: '{spacing.cible-min}'
  bouton-entete:
    border: '1px solid {colors.sur-encre-attenue}'
    foreground: '{colors.sur-encre}'
    radius: '{rounded.md}'
    height: '{spacing.cible-min}'
  nav-lien:
    foreground: '{colors.texte-attenue}'
    background-hover: '{colors.primaire-doux}'
    radius: '{rounded.md}'
    height: '{spacing.cible-min}'
  nav-lien-actif:
    background: '{colors.primaire}'
    foreground: '{colors.sur-primaire}'
  carte:
    background: '{colors.surface}'
    border: '1px solid {colors.trait}'
    radius: '{rounded.xl}'
    padding: '{spacing.5}'
  encart-agent:
    background: '{colors.encre-pleine}'
    foreground: '{colors.sur-encre}'
    suggestion-border: '{colors.sur-encre-attenue}'
    radius: '{rounded.xl}'
  pastille-meteo-vert:
    background: '{colors.succes-doux}'
    dot: '{colors.succes}'
    foreground: '{colors.texte}'
    radius: '{rounded.full}'
  pastille-meteo-jaune:
    background: '{colors.accent-doux}'
    dot: '{colors.accent}'
    foreground: '{colors.texte}'
    radius: '{rounded.full}'
  pastille-meteo-orange:
    background: '{colors.alerte-doux}'
    dot: '{colors.alerte-texte}'
    foreground: '{colors.texte}'
    radius: '{rounded.full}'
  pastille-meteo-rouge:
    background: '{colors.erreur-doux}'
    dot: '{colors.erreur}'
    foreground: '{colors.texte}'
    radius: '{rounded.full}'
  badge-controle-conforme:
    background: '{colors.succes-doux}'
    foreground: '{colors.succes}'
    radius: '{rounded.full}'
  badge-controle-corrige:
    background: '{colors.alerte-doux}'
    foreground: '{colors.alerte-texte}'
    radius: '{rounded.full}'
  badge-hors-perimetre:
    background: '{colors.alerte-doux}'
    foreground: '{colors.alerte-texte}'
    radius: '{rounded.full}'
  etiquette-outil:
    background: '{colors.primaire-doux}'
    foreground: '{colors.texte}'
    radius: '{rounded.sm}'
    typography: '{typography.code}'
  journal:
    background: '{colors.encre-pleine}'
    foreground: '{colors.sur-encre}'
    radius: '{rounded.xl}'
    typography: '{typography.code}'
  barre-progression:
    track: '{colors.surface-alt}'
    fill: '{colors.primaire}'
    height: 8px
    radius: '{rounded.full}'
  segment:
    track: '{colors.surface-alt}'
    active-background: '{colors.primaire-doux}'
    active-foreground: '{colors.texte}'
    active-border: '2px inset {colors.primaire}'
    foreground: '{colors.texte}'
    radius: '{rounded.lg}'
  champ:
    background: '{colors.surface}'
    border: '1px solid {colors.trait-fort}'
    focus-border: '{colors.primaire}'
    radius: '{rounded.md}'
    height: '{spacing.cible-min}'
  bulle-question:
    background: '{colors.primaire}'
    foreground: '{colors.surface}'
    radius: '{rounded.bulle-question}'
  bulle-reponse:
    background: '{colors.surface}'
    border: '1px solid {colors.trait}'
    radius: '{rounded.bulle-reponse}'
  bandeau-succes:
    background: '{colors.succes-doux}'
    foreground: '{colors.succes}'
    radius: '{rounded.xl}'
  bandeau-repli:
    background: '{colors.primaire-doux}'
    foreground: '{colors.texte}'
    radius: '{rounded.xl}'
  bandeau-erreur:
    background: '{colors.erreur-doux}'
    foreground: '{colors.erreur}'
    radius: '{rounded.xl}'
---

## Brand & Style

L'interface sert une démonstration de 10 minutes devant un Sponsor. Elle doit ressembler au produit d'une vraie équipe de pilotage, pas au tableau de bord d'un notebook. Elle suit la charte générique v2.1 (dépôt `Aliquanto3/charte-generique`, `docs/CHARTE.md`) :

- sombre d'abord, deux thèmes ; la valeur de chaque couleur vient d'un jeton de la charte, jamais d'une teinte propre à l'interface ;
- un bouton principal neutre, très contrasté (un seul geste fort par écran) ; le bleu sert à naviguer et à sélectionner, l'or à signaler (filet sous le titre) ;
- une signature : le pictogramme à point or, le filet or et Sora.

Le ton visuel est sérieux et lisible. Les titres en Sora 600 lui donnent une identité sans l'alourdir.

**Thèmes.** Le CSS met le thème sombre en `:root` (défaut de la charte quand l'utilisateur n'a pas de préférence) et le clair sous `@media (prefers-color-scheme: light)`. `data-theme="light"` ou `data-theme="dark"` sur `<html>` force un thème, pour les tests et les captures. L'interface n'a pas encore de sélecteur de thème.

La lisibilité prime : chiffres et identifiants (Entités, règles IND-x, tickets DEMO-x, outils de l'Agent) doivent se lire d'un coup d'œil sur un écran projeté. D'où une police de corps conçue pour la lecture (Atkinson Hyperlegible) et une police à chasse fixe pour tout ce qui est identifiant ou trace.

Références visuelles : la maquette canvas ([lien](https://claude.ai/artifact/8i2xgWiBDhL79cF7g68Fyu)), sept écrans. Les quatre premiers sont copiés dans `imports/maquette-canvas/` : `Main.dc.html`, `Detail.dc.html`, `Chaine.dc.html`, `Agent.dc.html`. Les écrans Avant / après, Pseudonymisation et Outillage sont sur le canvas seulement. En cas d'écart, `DESIGN.md` et `EXPERIENCE.md` font foi sur la maquette. Les écarts voulus sont listés dans `EXPERIENCE.md`, section Migration depuis Streamlit.

## Colors

Les couleurs viennent de la charte générique v2.1 (`https://github.com/Aliquanto3/charte-generique`, `docs/CHARTE.md`). Le frontmatter donne les valeurs du thème clair par rôle ; le thème sombre a ses propres valeurs dans la charte. `cadre.css` porte les deux jeux de variables, nommées comme les jetons.

Correspondances appliquées (ancien nom de variable de l'interface vers rôle de la charte) :

| Ancienne variable | Rôle |
|---|---|
| `--fond` | `fond` |
| `--carte` | `surface` |
| `--bordure` | `trait` |
| `--bordure-champ` | `trait-fort` |
| `--encre`, `--nuit` (texte) | `texte` |
| `--nuit` (aplat : en-tête, journal) | `encre-pleine`, texte `sur-encre` |
| `--encre-secondaire` | `texte-attenue` |
| `--primaire` (liens, sélection) | `primaire` |
| `--primaire` (aplat du bouton principal) | `bouton`, libellé `sur-bouton`, survol `bouton-survol` |
| `--lavande` | `primaire-doux` (survol, sélection) ou `surface-alt` (code, pistes) |
| `--lavande-texte` | `sur-encre-attenue` |
| `--violet-2` | contour `sur-encre-attenue` sur l'en-tête |
| `--blanc` | `surface`, `sur-encre`, `sur-primaire`, `sur-bouton` ou `sur-statut`, selon le fond |
| vert de marque | `succes` (Mode réel, étape réussie) |
| `--succes-*`, `--erreur-*` | `succes` / `succes-doux`, `erreur` / `erreur-doux` |
| `--refus-*` | `alerte-texte` / `alerte-doux` |
| `--meteo-*` | vert `succes`, jaune `accent` / `accent-doux`, orange `alerte-texte` / `alerte-doux`, rouge `erreur` / `erreur-doux` |

Règles d'usage :

- **Bouton principal** : aplat `bouton`, libellé `sur-bouton`, survol `bouton-survol`. Le bleu n'est jamais un aplat de bouton. Boutons secondaires : contour `trait-fort` sur `surface`.
- **Bleu `primaire`** : liens (toujours soulignés), entrée de navigation active, liseré de l'option active d'un segment (fond `primaire-doux`, jamais d'aplat bleu sur un bouton), remplissage de la barre de progression, bulle de question en `primaire-doux`. Survol d'un lien : `primaire-vif`.
- **Aplat sombre `encre-pleine`** : en-tête et journal de progression, avec `sur-encre` et `sur-encre-attenue`. Le pictogramme y garde ses valeurs sombres, comme dans la charte.
- **Gamme météo** : fond pâle de pastille et point saturé, à 3:1 au moins sur ce fond (en clair, `accent` pour le jaune et `alerte-texte` pour l'orange). Le texte de la pastille reste en `texte` et donne le nom de la couleur : la couleur ne porte jamais seule l'information.
- **Statuts** : `succes` sur `succes-doux` pour « Contrôle : conforme » et la Chaîne terminée ; `alerte-texte` sur `alerte-doux` pour « Hors périmètre » ; `erreur` sur `erreur-doux` pour les échecs. Les mêmes paires marquent « Oui », « À surveiller » et « Non » de la fiche d'outillage.
- **Surfaces** : fond de page `fond`, cartes `surface` bordées de `trait`, texte `texte`, texte secondaire `texte-attenue`. Les champs ont un contour `trait-fort`.
- **Focus** : anneau de 2 px décalé de 2 px, en `focus` ; en `sur-encre` sur l'aplat sombre de l'en-tête.
- **Filet or** : 96 × 4 px en `accent`, sous le titre de chaque écran.

Contrastes : `tests/unit/ui/test_charte.py` vérifie 4,5:1 pour les couples texte/fond de l'interface et 3:1 pour `trait-fort`, `focus` et le filet, dans les deux thèmes.

## Typography

Trois familles, servies en local par l'application (la démo doit tourner hors réseau, NFR-12) :

- **Sora 600**, pour les titres et les grands chiffres :
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
- **JetBrains Mono** (`{typography.code}`), pour les identifiants et les traces : clés de ticket, règles IND-x avec valeur et seuil, tendances J-1 et J-5, noms d'étapes de la Chaîne, noms d'outils de l'Agent, journal de progression, chemins de fichiers.

Pas de texte de corps en Sora.

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

Formes arrondies :

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

- **En-tête** : de gauche à droite, le pictogramme de la charte `{components.logo}` (servi par `pictogramme.svg`), le nom « Usine de migration » et le sous-titre « Copilote de pilotage · projet DEMO » en `{colors.sur-encre-attenue}`. À droite :
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
- **Encart Agent** : `{components.encart-agent}`, avec le titre « Demander à l'agent », une phrase de cadrage en `{colors.sur-encre-attenue}` et trois suggestions en liens pleine largeur.
- **Livrables du Passage** : carte, un lien en gras par fichier, suivi du type et de la taille en légende, puis l'heure de génération.

**Détail d'une Entité**

- **Lien de retour** : « ← Carte météo » en légende, au-dessus du titre.
- **Formulaire de sélection** : champ de sélection et `{components.bouton-secondaire}` « Afficher », alignés en bas. Il sert aussi pour le ticket de la Pseudonymisation.
- **Segment** : options dans une piste `{components.segment}`, l'option active en `{colors.primaire-doux}` avec un liseré `{colors.primaire}` de 2px, texte `{colors.texte}` : le bleu n'est jamais un aplat de bouton. Il sert au Palier (détail) et à la période (avant / après).
- **Tuile KPI** : libellé en légende, valeur en `{typography.chiffre-kpi}`, précision en légende.
- **Tableau des Règles déclenchantes** : colonnes Règle, Valeur, Météo, Tickets en cause. Règle et valeur en `{typography.code}`, Météo en pastille. Les trois premières clés de ticket sont affichées, suivies de « +N ».
- **Explication** : carte avec le titre, le badge de contrôle à droite, le texte en `{typography.corps-lecture}` et ses Citations en clés de ticket, puis une légende de provenance. Phrases retirées au contrôle : liste en légende sous le texte.
- **Prévision** : date en `{typography.chiffre-date}` `{colors.texte}`, puis l'intervalle et le rythme de fermeture en légende.
- **Risque** : carte de texte en `{typography.corps}`.
- **Bouton de question** : `{components.bouton-primaire}` pleine largeur de la colonne d'encarts.

**Lancement de la Chaîne**

- **Bouton de lancement** : `{components.bouton-primaire}`.
- **Bouton de mode** : `{components.bouton-secondaire}`, « Passer en Mode repli » ou « Revenir au Mode réel ».
- **Liste des étapes** : une ligne `{rounded.lg}` par étape, avec une puce ronde numérotée de 32px, le nom technique en `{typography.code}`, la description en légende et un badge d'état à droite. Quatre états :

  | État | Puce | Ligne et badge |
  |---|---|---|
  | Réussie | `{colors.succes}`, coche en `{colors.sur-statut}` | badge `{colors.succes-doux}` |
  | En cours | `{colors.primaire}` | ligne sur `{colors.primaire-doux}`, badge `{colors.primaire}` |
  | En attente | bordée, sur `{colors.fond}` | badge `{colors.fond}` |
  | Échec | `{colors.erreur}` | badge `{colors.erreur}`, texte blanc, libellé « Échec » |

  Une étape sautée (`sautee`) reprend l'apparence « En attente », avec le libellé « Sautée ».
- **Barre de progression** : `{components.barre-progression}`, compteur « n / 10 » en `{typography.code}` au-dessus à droite.
- **Journal de progression** : `{components.journal}`, lignes horodatées, la plus récente en haut.
- **Dernier Passage** : carte, trois lignes en légende (date et durée, tickets extraits et Entités, manifeste).

**Agent**

- **Fil de l'Agent** : la question en `{components.bulle-question}`, alignée à droite ; la réponse en `{components.bulle-reponse}`, précédée d'un avatar « IA » vert de 36px. La réponse se termine par un pied, séparé par une bordure, qui porte le badge de contrôle, « Outils appelés : » et une `{components.etiquette-outil}` par outil.
- **Saisie de question** : zone de texte `{components.champ}` sur deux lignes, libellé au-dessus, `{components.bouton-primaire}` « Envoyer » à droite.
- **Questions enregistrées** : boutons pleine largeur, bordés de `{colors.trait-fort}`. La question affichée passe en `{colors.primaire-doux}`, bordée de `{colors.primaire}`.
- **Outils de l'Agent** : carte qui liste chaque outil, une `{components.etiquette-outil}` suivie de sa description.
- **Badge de contrôle** : « ✓ Contrôle : conforme · chiffres et tickets vérifiés » (`{components.badge-controle-conforme}`), « Contrôle : corrigée » (`{components.badge-controle-corrige}`), « Contrôle : rejetée » et « Hors périmètre · aucune donnée inventée » (`{components.badge-hors-perimetre}`).

**Avant / après**

- **Comparatif avant / après** : deux cartes jumelles.
  - À gauche, « Reporting manuel » avec l'étiquette « déclaré » (fond `{colors.fond}`, bordure `{colors.trait}`) et la valeur en `{typography.chiffre}` couleur `{colors.texte-attenue}`.
  - À droite, « Chaîne » avec l'étiquette « mesuré » (`{colors.succes-doux}`) et la valeur en `{typography.chiffre}` couleur `{colors.texte}`.
  - Au-dessus, un segment choisit la période ; dessous, un tableau donne les deux périodes, puis vient la légende de source.

**Pseudonymisation**

- **Panneaux de Pseudonymisation** : deux cartes jumelles titrées « Original » et « Version pseudonymisée », la seconde bordée de `{colors.primaire}`, avec l'étiquette « envoyée au LLM ». Texte en `{typography.corps-lecture}`, retours à la ligne conservés, sans surlignage des pseudonymes.

**Ce qu'il faut pour le faire en vrai**

- **Fiche d'outillage** : Markdown rendu en cartes de largeur `{spacing.lecture-max}`, sauf le tableau, qui prend toute la largeur et défile. Titres en Sora `{colors.texte}`, liste des demandes numérotée en Sora `{colors.primaire}` sur `{colors.primaire-doux}`. Dans le tableau, les marqueurs ✅, ⚠️ et ❌ de la fiche deviennent des pastilles de texte « Oui » (`{colors.succes-doux}`), « À surveiller » (`{colors.alerte-doux}`) et « Non » (`{colors.erreur-doux}`), suivies du reste de la cellule.

**Éléments communs**

- **Tableau** :
  - en-têtes de colonne en `{typography.entete-tableau}` et `{colors.texte-attenue}`, en-têtes de ligne en gras ;
  - lignes séparées par `{colors.trait}`, cellules avec 14px × 16px de marge intérieure ;
  - colonnes d'identifiants en `{typography.code}` ;
  - lien d'action de ligne (« Détail ENT-B ») aligné à droite, en gras ;
  - légende du tableau en `{typography.legende}` au-dessus des en-têtes.
- **Clé de ticket** : `{typography.code}` en gras. En lien, `{colors.primaire}` souligné, suivi d'une petite flèche sortante (icône SVG au trait, `aria-hidden`). Inactive, en `{colors.texte}`, sans soulignement ni flèche.
- **Champs** : sélecteurs et zones de texte en `{components.champ}`, libellé visible au-dessus en légende.
- **Focus clavier** : anneau de 2px décalé de 2px, en `{colors.focus}`, et en `{colors.sur-encre}` sur l'aplat sombre de l'en-tête.

## Do's and Don'ts

| À faire | À éviter |
|---|---|
| Nommer la couleur dans chaque pastille météo | Des pastilles emoji 🟢🔴 ou une couleur sans libellé |
| Réserver la gamme météo à la Météo | Colorer un bouton en rouge ou en vert météo |
| Valeurs de couleur prises dans les jetons de la charte | Une teinte propre à l'interface |
| Identifiants, règles, outils et traces en JetBrains Mono | Des clés de ticket en police de corps |
| Un bouton principal neutre par zone | Un bouton principal bleu, ou plusieurs boutons principaux concurrents |
| Bordures de 1px et aplats pour la hiérarchie | Ombres portées, dégradés, bordure gauche colorée sur les cartes |
| Contour `trait-fort` sur tout champ | Des champs bordés de `trait`, trop pâles |
| Polices et icônes servies par l'application | Google Fonts ou un CDN chargés pendant la démo |
| Tableaux larges qui défilent dans leur carte | Une page qui défile horizontalement |
