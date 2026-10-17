---
name: Usine de migration — interface web
status: final
updated: 2026-10-17
sources:
  - ../../prds/prd-usine-migration-jira-demo-2026-10-10/prd.md
  - ../../architecture/architecture-usine-migration-jira-demo-2026-10-10/ARCHITECTURE-SPINE.md
  - ../../epics.md
  - https://claude.ai/artifact/8i2xgWiBDhL79cF7g68Fyu
  - imports/maquette-canvas/
---

# Usine de migration — spine d'expérience

## Foundation

Le web est la seule surface. L'interface est pensée pour un portable branché sur un projecteur (1280 à 1440px de large) et reste utilisable en largeur de téléphone. Elle n'utilise pas de bibliothèque de composants : HTML et CSS sont écrits à la main d'après `DESIGN.md`, qui fait foi pour l'apparence. Ce document fait foi pour le comportement.

Cette interface remplace l'application Streamlit (`src/usine/ui/app.py`, lancée par `usine ui`). FastAPI la sert : chaque écran est une page HTML statique ; un petit script sans framework y charge les données par des appels JSON au même serveur. Les sélections (Entité, ticket) passent par des formulaires `GET` ordinaires.

Les contraintes d'architecture restent celles de l'UI actuelle :

- l'UI lit un Passage par `Consultation` uniquement (AD-11) et n'affiche que des valeurs qu'elle reçoit, sans calcul (AD-9) ;
- elle n'ouvre jamais `donnees/entrepot.duckdb` (AD-6) ;
- elle lance la Chaîne par `usine rapport` en sous-processus et suit `sorties/progression/<passage_id>.jsonl` (AD-8) ;
- le Mode repli se choisit par `USINE_MODE_REPLI=1` ou par le bouton de l'écran de lancement, jamais automatiquement (AD-19) ;
- tout ce qu'elle charge (polices, script, styles) est servi en local, pour que la démo tourne hors réseau (NFR-12).

L'interface est mono-utilisateur, sans authentification, en français seulement (NFR-11). Elle vise Chrome et Edge récents, ceux du poste de démo, sans version mobile dédiée. Les points de rupture sont dans `DESIGN.md`, section Layout & Spacing ; à toute largeur, l'interface garde les mêmes écrans, contrôles et URL. Le découpage des routes suit AD-25. Les URL d'écran ci-dessous sont celles que l'utilisateur voit.

Les points ouverts sont tranchés par le Sprint Change Proposal du 2026-10-17 (AD-25) : livrables lus par `Consultation.livrable`, pseudonymes non surlignés (voir Décisions).

## Information Architecture

Sept écrans, tous à un clic de la carte météo par la navigation latérale (FR-43). La navigation suit l'ordre de la maquette.

| Écran | URL | Atteint depuis | Rôle | Exigence |
|---|---|---|---|---|
| Carte météo | `/` | Ouverture, logo, navigation | Météo des 10 Entités du dernier Passage, à la Date d'arrêté | FR-43 |
| Détail d'une Entité | `/entites/{entite}` | Ligne de la carte ; navigation, qui ouvre la première Entité du Tableau des Entités | Règles déclenchantes, KPI, Explication, Prévision et Risque ; comparaison Palier 1 / Palier 2 | FR-32, FR-43, FR-46 |
| Lancement de la Chaîne | `/chaine` | Bouton d'en-tête, navigation | Lancer un Passage et suivre ses 10 étapes ; changer de mode | FR-25, FR-43, FR-45 |
| Agent | `/agent` | Encart Agent, Bouton de question, navigation | Questions en langage naturel sur le Passage affiché, en lecture seule | FR-40, FR-41 |
| Avant / après | `/avant-apres` | Navigation | Temps de reporting manuel déclaré face au temps mesuré de la Chaîne | FR-44 |
| Pseudonymisation | `/pseudonymisation` | Navigation | Description d'un ticket, originale et pseudonymisée, côte à côte | FR-31 |
| Ce qu'il faut pour le faire en vrai | `/outillage` | Navigation | Fiche `docs/fiche-outillage.md` en lecture seule | FR-43, Story 8.1 |

Chaque écran a un titre de page unique et une entrée de navigation active. Le bouton « Lancer la Chaîne » de l'en-tête mène à `/chaine` et ne lance rien.

→ Composition : un écran de la maquette par entrée de ce tableau (voir `DESIGN.md`, Brand & Style, références visuelles).

## Voice and Tone

Microcopie. La posture de marque est décrite dans `DESIGN.md`. Le vocabulaire métier du PRD (§ 3) s'écrit tel quel, avec sa majuscule : Passage, Entité, Chaîne, Anomalie, Cas de test, Date d'arrêté, Palier, Mode repli, Explication.

| À écrire | À éviter |
|---|---|
| « Date d'arrêté : 17/10/2026 · 10 Entités · Grille IND-1 à IND-8 » | « Données du jour » |
| « IND-2 : 11 (seuil ≥ 10) » | « Trop d'anomalies » |
| « Chaîne terminée : Passage publié. » | « Succès ! 🎉 » |
| Le nom de l'étape en échec et son code de sortie | « Une erreur est survenue » |
| « Je ne peux pas répondre : le budget ne figure pas dans les données du Passage. » | Une réponse plausible, inventée |
| La valeur déclarée et la valeur mesurée, côte à côte | « Vous gagnez 95 % de temps » |
| Des phrases courtes, des chiffres avec leur unité et leur seuil, des dates au format JJ/MM/AAAA | Points d'exclamation, emojis, anglicismes d'interface (« run », « dashboard ») |

**Source des textes.** Un texte qui existe dans l'UI Streamlit est repris de sa constante, citée par son nom dans les tableaux ci-dessous (par exemple `detail.AUCUNE_REGLE`). Les modules `carte`, `detail`, `agent`, `avant_apres`, `pseudonymisation`, `outillage`, `progression` et `app` de `src/usine/ui/` font foi pour le texte exact. Un texte marqué « nouveau » n'existe pas encore et se rédige d'après ce document. Un texte cité par `app.py:N` n'a pas de constante : la migration l'extrait en constante nommée. Les numéros de ligne renvoient au commit `173e44f`.

## Component Patterns

Comportement. L'apparence est décrite dans `DESIGN.md.Components`, sous les mêmes noms.

**Cadre**

| Composant | Règles de comportement |
|---|---|
| En-tête | La pastille « Passage publié · date heure » est lue dans le manifeste du Passage affiché ; elle est absente s'il n'y a pas de Passage affiché. La pastille de mode affiche « Mode réel » ou « Mode repli » et reste toujours visible (FR-45). Le bouton « Lancer la Chaîne » est absent de `/chaine`. |
| Navigation latérale | Liens `<a href>` réels ; l'entrée active porte `aria-current="page"`. |
| Lien d'évitement | Premier élément focalisable de chaque page ; il mène au titre de l'écran. |
| Mention de données | Texte fixe, nouveau : « Données fictives ou publiques. Chiffres et tickets vérifiés sur le dernier Passage. » |
| Bandeau | Un seul bandeau de chaque type à la fois, sous le titre de l'écran. Le bandeau d'erreur porte `role="alert"` ; les bandeaux de succès et de repli portent `role="status"`. Une erreur répétée (sondage en échec, par exemple) ne relance pas l'annonce. |

**Carte météo**

| Composant | Règles de comportement |
|---|---|
| Tuile de comptage | Une par couleur, de rouge à vert, en lecture seule : elle ne filtre pas le tableau. |
| Filtre météo | Sélecteur « Toutes / Rouge / Orange / Jaune / Vert » qui filtre le tableau dans le navigateur sans recharger la page. Il annonce « {n} Entités affichées », au singulier pour une seule (nouveau), dans une région `role="status"`. Sans résultat : « Aucune Entité en {couleur} à cette Date d'arrêté. » (nouveau). |
| Tableau des Entités | Trié de la Météo la plus grave à la moins grave, puis par Entité. Colonnes : Entité (en-tête de ligne), Météo, Tendance (J-1, J-5), Règle principale, Anomalies ouvertes, lien « Détail {Entité} ». La légende des flèches (`carte.LEGENDE`) sert de légende du tableau. |
| Encart Agent | Trois questions types. Un clic ouvre `/agent?question=…` : la question est pré-remplie en Mode réel, sélectionnée en Mode repli. |
| Livrables du Passage | Liens de téléchargement du Rapport quotidien `.xlsx` et du Comité de pilotage `.pptx` du Passage affiché, servis en lecture seule. Un livrable absent n'a pas de lien et affiche « Non généré pour ce Passage » (nouveau). |

**Détail d'une Entité**

| Composant | Règles de comportement |
|---|---|
| Lien de retour | Mène à la carte météo, filtre remis à « Toutes ». |
| Formulaire de sélection | Choisir une Entité ne fait rien tant qu'on n'a pas cliqué sur « Afficher », qui charge `/entites/{entite}`. Le retour arrière du navigateur ramène à l'Entité précédente. |
| Segment | Visible seulement si le Passage est de Palier 2. Les options sont des boutons, l'active porte `aria-pressed="true"`, et le choix se garde dans l'URL (`?palier=1`). Quand l'option Palier 1 est choisie, l'Explication affiche `detail.EXPLICATION_PALIER_1` et la Prévision est masquée ; la Météo, les Règles et les KPI ne changent pas. Le focus reste sur l'option choisie. L'aide `app.py:219` (« Palier 1 : la même Entité sans aucune sortie LLM ») devient la légende du segment. |
| Tuile KPI | Quatre KPI clés reçus de `Consultation`, sans calcul, en lecture seule. |
| Tableau des Règles déclenchantes | Une ligne par Règle déclenchante. Les trois premières clés de ticket sont des liens, suivies de « +N » ; « +N » est un bouton (`aria-expanded`) qui déplie la liste complète dans la cellule. |
| Explication | Texte et Citations (FR-32). Le badge suit le statut du contrôle. Phrases retirées au contrôle : listées sous le texte (`detail.PHRASES_RETIREES`). Aucune édition dans l'interface. |
| Prévision | Date, intervalle et rythme de fermeture, tels que reçus. |
| Risque | Texte reçu de `Consultation`. |
| Bouton de question | Ouvre `/agent` avec « Pourquoi {Entité} est-elle {couleur} ? » pré-remplie. |

**Lancement de la Chaîne**

| Composant | Règles de comportement |
|---|---|
| Bouton de lancement | Un clic lance `usine rapport`, puis le bouton passe à « Chaîne en cours… » et refuse les clics jusqu'à la fin. Il reste focalisable (`aria-disabled="true"`, pas l'attribut `disabled`) et son motif, visible sous le bouton, lui est lié par `aria-describedby`. Il est bloqué aussi en Mode repli (motif `app.LANCEMENT_REPLI`) et si la racine du projet manque. Le focus reste sur le bouton. |
| Bouton de mode | « Passer en Mode repli » ou « Revenir au Mode réel » (nouveaux). Un clic recharge l'interface sur `demo/repli/passage/`, ou sur le dernier Passage réel au retour. Le changement ne se fait jamais à la simple saisie. Le bouton est bloqué tant qu'une Chaîne tourne. |
| Liste des étapes | Les 10 étapes de l'énumération `Etape`, dans l'ordre, avec leur état : en attente, en cours, réussie, sautée ou échec. Le suivi est sondé chaque seconde (`app.INTERVALLE_SONDAGE`) et le sondage s'arrête à la fin ou à l'échec. |
| Barre de progression | `role="progressbar"`, `aria-valuenow` égal au nombre d'étapes terminées, `aria-valuemax="10"`. Une région `role="status"` séparée n'annonce que les changements d'étape, la fin et l'échec, jamais chaque sondage. |
| Journal de progression | Lignes horodatées du suivi, la plus récente en haut ; non annoncé. En cas d'échec, les 20 dernières lignes d'erreur (`app.LIGNES_ERREUR_MAX`) s'ajoutent au bandeau d'erreur. |
| Dernier Passage | Date, durée, nombre de tickets extraits et d'Entités, chemin du manifeste ; tout est lu dans le manifeste. |

**Agent**

| Composant | Règles de comportement |
|---|---|
| Fil de l'Agent | Une question, une réponse : une nouvelle question remplace la précédente à l'écran. À l'arrivée de la réponse, la région `role="status"` annonce « Réponse de l'Agent reçue » (nouveau) et le focus passe sur la réponse (`tabindex="-1"`). |
| Saisie de question | Mode réel seulement. Libellé `agent.LIBELLE_QUESTION`, valeur par défaut `agent.QUESTION_DEMO`, bouton « Envoyer » (nouveau, remplace `agent.LIBELLE_ENVOYER`). Entrée envoie, Maj+Entrée va à la ligne. Un champ vide ne s'envoie pas. |
| Questions enregistrées | En Mode réel, ce sont des suggestions qui remplissent la saisie. En Mode repli, c'est la seule manière de questionner (AD-24) : la saisie disparaît, `agent.MESSAGE_REPLI` s'affiche, et un clic sur une question rejoue sa réponse enregistrée. |
| Outils de l'Agent | Liste fixe des outils exposés à l'Agent, avec une ligne de description chacun. |
| Badge de contrôle | Suit le statut de contrôle reçu : conforme, corrigée, rejetée, hors périmètre. Une réponse rejetée n'affiche pas son texte. En Mode repli, le pied ajoute la mention de `agent.mention_repli`. |

**Avant / après, Pseudonymisation, Outillage**

| Composant | Règles de comportement |
|---|---|
| Comparatif avant / après | Valeurs reçues telles quelles : temps manuel déclaré (`config/demo.yaml`), temps mesuré du Passage affiché, cumul sur 5 Rapports. Le segment choisit la période des deux grandes cartes ; le tableau montre toujours les deux périodes. L'interface ne calcule ni écart ni ratio. La légende de source suit `avant_apres.legende`. |
| Formulaire de sélection (ticket) | Liste des tickets du Passage dont la description n'est pas vide, triée par clé. « Afficher » charge `/pseudonymisation?ticket=DEMO-17`. |
| Panneaux de Pseudonymisation | Texte brut, retours à la ligne conservés, sans interprétation HTML. Chaque panneau défile seul ; c'est une région focalisable (`tabindex="0"`, `role="region"`, libellée par son titre). Les pseudonymes ne sont pas surlignés : l'aperçu renvoie un texte seul (AD-11). Légende `pseudonymisation.LEGENDE`. |
| Fiche d'outillage | Le serveur convertit le Markdown en HTML, en lecture seule. Les marqueurs ✅, ⚠️ et ❌ deviennent les pastilles « Oui », « À surveiller » et « Non ». Légende `outillage.LEGENDE`. |

**Éléments communs**

| Composant | Règles de comportement |
|---|---|
| Clé de ticket | Lien Jira qui s'ouvre dans un nouvel onglet (FR-29), avec un nom accessible terminé par « (nouvel onglet) ». Quand l'URL du ticket est absente (Mode repli, AD-11), la clé est du texte simple ; c'est le bandeau du Mode repli qui en donne la raison. |
| Tableau | `<caption>` visible, `<th scope="col">` pour les colonnes et `<th scope="row">` pour la première cellule. Un tableau qui défile est une région focalisable libellée. |

## State Patterns

| État | Écran | Traitement | Texte |
|---|---|---|---|
| Chargement des données | Tous | Le gabarit (en-tête, navigation, titre) s'affiche aussitôt ; chaque bloc montre « Chargement… » en légende jusqu'à l'arrivée de ses données. Pas d'animation de squelette. | nouveau |
| Lecture impossible | Tous | Bandeau d'erreur avec le détail. Les blocs déjà chargés restent. | erreurs de `app.py` (lignes 151, 356, 387) |
| Serveur injoignable | Tous | Bandeau d'erreur : « L'interface ne joint plus le serveur. Relancer usine ui. » | nouveau |
| Aucun Passage publié | Carte, Détail, Agent, Avant / après | Carte unique avec le message de l'écran et le bouton « Lancer la Chaîne ». Pastille « Passage publié » absente de l'en-tête. | carte et détail : message de `app.py` ; `agent.AUCUN_PASSAGE` ; `avant_apres.AUCUN_PASSAGE` |
| Passage sans Météo | Carte, Détail | Carte unique avec le message. | `app.py:189`, `app.py:241` |
| Mode repli actif | Tous | Pastille « Mode repli » dans l'en-tête et bandeau de repli sous le titre. | `app.BANDEAU_REPLI` |
| Passage enregistré introuvable | Tous, en Mode repli | Bandeau d'erreur ; le bouton de mode reste accessible sur `/chaine`. | `app.REPLI_ABSENT` |
| Entité verte | Détail | Règles et Prévision sans objet. | `detail.AUCUNE_REGLE`, `detail.PREVISION_SANS_OBJET` |
| Entité rouge | Détail | Le Risque est sans objet. | `detail.RISQUE_SANS_OBJET` |
| Pas de KPI | Détail | Message à la place des tuiles. | `detail.AUCUN_KPI` |
| Prévision ou Risque non calculés | Détail | Message dans le bloc. | `detail.PREVISION_NON_CALCULEE_*`, `detail.NON_PROJETABLE`, `detail.RISQUE_NON_CALCULE_PASSAGE` |
| Pas de Risque | Détail | Message dans le bloc. | `detail.AUCUN_RISQUE` |
| Pas d'Explication | Détail | Message dans le bloc. | `detail.EXPLICATION_ABSENTE` |
| Passage de Palier 1 | Détail | Segment masqué ; Explication et Prévision traitées comme en Palier 1. | `detail.EXPLICATION_PALIER_1` |
| Entité inconnue dans l'URL | Détail | Message et lien vers la carte : « Entité {entite} absente du Passage affiché. » | nouveau |
| Chaîne en attente | Chaîne | Étapes « En attente » ; le journal affiche « En attente d'un lancement. » | nouveau |
| Chaîne en cours | Chaîne | Bouton de lancement bloqué, étape courante surlignée. Quitter l'écran n'arrête pas la Chaîne ; y revenir reprend le suivi. | « Chaîne en cours… », `app.py` |
| Chaîne terminée | Chaîne | Bandeau de succès et lien « Voir la carte météo » ; le bouton devient « Relancer la Chaîne » et l'en-tête prend la nouvelle date. | « Chaîne terminée : Passage publié. », `app.py` |
| Chaîne en échec | Chaîne | Étape en échec marquée ; bandeau d'erreur avec l'étape, le code et les dernières lignes d'erreur. Le Passage affiché ailleurs ne change pas. | message d'échec, `app.py:590`, y compris la variante hors d'une étape |
| Rapport non publié après la Chaîne | Chaîne | Bandeau d'erreur. | `progression.AUCUN_RAPPORT` |
| Réponse en attente | Agent | Bouton « Envoyer » bloqué ; « L'Agent consulte le Passage… » à la place de la réponse. | nouveau |
| Hors périmètre | Agent | Réponse de refus, badge hors périmètre, outils « aucun ». | réponse de l'Agent |
| Agent indisponible | Agent, en Mode réel | Bandeau d'erreur avec le détail et un lien vers `/chaine` pour passer en Mode repli. | `app.py:437`, `app.py:443` |
| Réponses enregistrées refusées | Agent, en Mode repli | Bandeau d'erreur. | `agent.REFUS_REPLI` |
| Moteur indisponible | Pseudonymisation | Bandeau d'erreur nommant Presidio ou le modèle spaCy. | `app.py:269-273` |
| Aperçu impossible | Pseudonymisation | Bandeau d'erreur avec le détail (par exemple `USINE_CLE_PSEUDO` absente). | `app.py:299-300` |
| Aucun ticket décrit | Pseudonymisation | Message à la place des panneaux. | `pseudonymisation.AUCUNE_DESCRIPTION` |
| Configuration absente | Avant / après | Carte « Chaîne » seule, avec l'avertissement à la place de la carte « Reporting manuel ». | `avant_apres.CONFIG_ABSENTE` |
| Seul un Passage avec classification initiale | Avant / après | Avertissement à la place du temps mesuré. | `avant_apres.SEULE_CLASSIFICATION_INITIALE` |
| Fiche absente | Outillage | Message à la place de la fiche. | `outillage.FICHE_ABSENTE` |
| Téléchargement impossible | Carte | Le lien mène à une page d'erreur du serveur, qui nomme le fichier manquant et propose un lien de retour à la carte. | nouveau |

En Mode repli, la Pseudonymisation et l'Avant / après portent sur le Passage enregistré, comme dans l'UI actuelle. Les livrables sont proposés s'ils figurent dans `demo/repli/passage/` ; sinon, « Non généré pour ce Passage ».

## Interaction Primitives

- Souris et clavier ; le tactile suit les mêmes règles (cibles d'au moins 44px).
- Navigation par liens réels : chaque écran et chaque sélection utile (Entité, Palier, ticket, question) a une URL. Le retour arrière du navigateur la respecte, et on peut l'ouvrir directement pendant la démo.
- Aucun changement de contexte à la simple saisie : choisir une valeur dans un sélecteur ne navigue pas. Le Filtre météo fait exception : il filtre sur place, sans quitter la page.
- Aucun raccourci clavier propre à l'application.
- Seul le suivi de la Chaîne se rafraîchit automatiquement, par sondage chaque seconde. Après une Chaîne terminée, les autres écrans montrent le nouveau Passage à leur prochain chargement.
- **Interdits** :
  - fenêtres modales et alertes du navigateur ;
  - défilement infini et animation décorative ;
  - lancement de la Chaîne ou changement de mode sans clic explicite ;
  - toute écriture dans le Passage ou dans Jira depuis l'interface.

## Accessibility Floor

Comportement. Les contrastes sont dans `DESIGN.md.Colors`. Le PRD ne pose aucune exigence d'accessibilité : ce plancher la fixe ici, au niveau WCAG 2.2 AA.

- `<html lang="fr">`. Titre de page « {Écran} · Usine de migration » ; il nomme aussi l'Entité ou le ticket affiché (« ENT-B · Détail d'une Entité · Usine de migration »).
- Un seul `<h1>` par écran (le titre), un `<h2>` par carte et un `<h3>` par sous-section de la fiche d'outillage.
- Contrôles natifs seulement : `<a href>`, `<button>`, `<select>`, `<textarea>`, chacun avec un `<label>` visible. Aucun autre élément n'est cliquable.
- L'ordre de tabulation suit l'ordre de lecture : lien d'évitement, en-tête, navigation, titre, contrôles, contenu. Le focus reste toujours visible.
- Après un chargement de page, le focus est au début du document. Après une action sur place, il reste sur le contrôle actionné, sauf à l'arrivée d'une réponse de l'Agent : il passe alors sur la réponse.
- Un bouton bloqué reste focalisable et annonce son motif (`aria-disabled` et `aria-describedby`).
- La Météo se lit sans la couleur : chaque pastille porte son nom, et les flèches de tendance ont un texte accessible (« J-1 en hausse »).
- Les annonces suivent les composants : la région `status` de la Chaîne, l'arrivée de la réponse de l'Agent, le résultat du Filtre météo. Les bandeaux d'erreur sont en `alert`. Une annonce ne se répète pas tant que le contenu ne change pas.
- Un lien qui ouvre un nouvel onglet le dit dans son nom accessible.
- Les zones qui défilent (tableaux larges, panneaux de Pseudonymisation) sont focalisables et libellées.
- `prefers-reduced-motion` : la barre de progression change sans transition.
- Zoom à 200 % et largeur de 320px sans perte de contenu ni défilement horizontal de la page.

## Key Flows

### Flux 1 — Le rapport du matin (Claire, pilote, 7 h 40 avant le point d'équipe) · UJ-1

1. Claire ouvre l'interface. La carte météo affiche le Passage d'hier soir ; l'en-tête indique « Passage publié · 16/10/2026 19:05 ».
2. Elle clique sur « Lancer la Chaîne » dans l'en-tête. L'écran de lancement montre les 10 étapes en attente.
3. Elle clique sur le bouton de lancement de l'écran. Les étapes passent une à une de « En cours » à « Réussie », le journal défile, le compteur monte jusqu'à « 10 / 10 ».
4. **Climax :** le bandeau « Chaîne terminée : Passage publié. » apparaît, l'en-tête passe à « 17/10/2026 07:42 ». Elle clique sur « Voir la carte météo » : ENT-E est passée à l'orange, la tuile Orange indique « +1 depuis J-1 », et le Rapport quotidien et le Comité de pilotage sont prêts à télécharger.

Échec : l'étape « extraction » échoue (jeton Jira expiré). Elle est marquée en échec, le bandeau nomme l'étape et le code, les dernières lignes d'erreur s'affichent. La carte garde le Passage d'hier, daté comme tel.

### Flux 2 — Justifier un rouge devant le comité (Claire, comité de pilotage, 14 h) · UJ-2

1. Sur la carte météo, Claire filtre sur « Rouge » : seule ENT-B reste, et le filtre annonce « 1 Entité affichée ».
2. Elle clique sur « Détail ENT-B ». Règle déclenchante : IND-2, 11 Anomalies bloquantes ouvertes pour un seuil de 10.
3. Elle lit l'Explication, badge « Contrôle : conforme », et clique sur DEMO-4 : le ticket s'ouvre dans Jira, dans un nouvel onglet.
4. Un membre du comité demande ce que dit le calcul sans l'IA. Elle choisit « Palier 1 · règles seules » : la Météo et les règles ne bougent pas, l'Explication cède la place au texte du Palier 1 et la Prévision disparaît.
5. **Climax :** de retour sur « Palier 2 », elle montre la Prévision de sortie du rouge au 24/10/2026, avec son intervalle et le rythme de fermeture qui la fonde. Le comité a le pourquoi, la preuve et la date sur un seul écran.

Échec : l'Explication d'ENT-B a été rejetée au contrôle. Le bloc n'affiche pas de texte. Claire s'appuie sur le tableau des Règles déclenchantes, qui suffit à justifier le rouge.

### Flux 3 — Interroger l'Agent (Claire, avant d'écrire à un chef de projet) · UJ-3

1. Depuis l'encart Agent, Claire clique sur « Quelle Entité risque de passer au rouge, et pourquoi ? ».
2. L'écran Agent s'ouvre, question pré-remplie ; elle clique sur « Envoyer ». « L'Agent consulte le Passage… » s'affiche.
3. La réponse cite ENT-E, dont le taux KO atteint 38 % pour un seuil rouge à 40 %, puis ENT-C. Le pied montre « Contrôle : conforme » et les outils `get_risques` et `get_meteo`.
4. Elle tente « Quel est le budget restant du programme ? ».
5. **Climax :** l'Agent refuse, badge « Hors périmètre · aucune donnée inventée », outils « aucun ». Claire sait que ce qu'il affirme vient du Passage, et qu'il dit ce qu'il ignore.

Échec : le LLM ne répond pas. Le bandeau d'erreur s'affiche avec un lien vers l'écran de lancement ; Claire passe en Mode repli et choisit une question enregistrée.

### Flux 4 — La démo de 10 minutes (Anaël, salle de réunion du Sponsor, réseau invité instable) · UJ-4

1. Avant d'entrer, Anaël lance `usine ui`, ouvre `/chaine` et clique sur « Passer en Mode repli » : le réseau invité ne laisse passer ni Jira ni le LLM. L'en-tête affiche « Mode repli », le bandeau le rappelle.
2. Il ouvre la carte météo, puis le détail d'ENT-B (flux 2). Les clés de ticket s'affichent en texte simple ; le bandeau dit pourquoi.
3. Sur l'écran Agent, il clique sur deux questions enregistrées. Chaque réponse rejouée porte la mention de réponse enregistrée sans LLM.
4. Il ouvre « Avant / après » : le reporting manuel déclaré face à la Chaîne mesurée, par Rapport, puis sur 5 Rapports d'un clic sur le segment. Il commente l'écart lui-même ; l'écran n'affiche aucun pourcentage.
5. Le Sponsor demande ce que deviennent les noms de clients dans les tickets. Anaël ouvre « Pseudonymisation », choisit DEMO-17 et clique sur « Afficher » : à gauche le texte original, à droite le texte envoyé au LLM, où noms, contacts et numéros de compte sont remplacés.
6. **Climax :** « Et pour le faire chez nous ? » Anaël ouvre « Ce qu'il faut pour le faire en vrai » : les quatre demandes par ordre de priorité, puis le tableau des briques par cible (VM Python, Dataiku, Power Platform, poste local). La démo se termine sur une liste d'actions que le Sponsor peut lancer.

Échec : à l'ouverture de la Pseudonymisation, le modèle spaCy n'est pas installé sur le poste. Le bandeau nomme le moteur manquant ; Anaël passe à l'écran suivant et la démo continue.

## Migration depuis Streamlit

La parité est attendue avec `src/usine/ui/` : mêmes écrans, mêmes sources de données, mêmes textes d'état (voir Voice and Tone). Écarts voulus, avec la maquette quand elle diffère :

| Streamlit | Maquette | Interface web |
|---|---|---|
| Radio latérale « Écran », un seul script | Liens | Une URL par écran, liens de navigation |
| Ordre : Carte, Détail, Lancement, Avant / après, Pseudonymisation, Agent, Outillage | Agent en 4e position | Ordre de la maquette |
| Pastilles emoji 🟢🟡🟠🔴, tableau Markdown | Pastilles nommées | Pastilles nommées, tableau HTML filtrable |
| Pas de tuiles de comptage, d'encart Agent ni de livrables sur la carte | Présents | Repris de la maquette |
| Bascule Mode repli dans la barre latérale de tous les écrans | Case à cocher sur l'écran de lancement | Bouton de mode sur `/chaine`, pastille de mode dans l'en-tête de tous les écrans |
| Résumé du lancement dans la barre latérale | Encart « Dernier Passage » | Encart « Dernier Passage » sur `/chaine` |
| Selectbox d'Entité et de ticket, effet immédiat | Sélecteur seul | Formulaire avec bouton « Afficher » |
| Risque d'une Entité rouge : `RISQUE_SANS_OBJET` | « Déjà rouge. Entité voisine la plus exposée… » | `RISQUE_SANS_OBJET` : le texte de la maquette supposait un calcul dans l'UI (AD-9) |
| — | Barre de progression verte, segment actif blanc | Barre et segment actif en violet primaire, pour le contraste |

Les tests de `tests/unit/ui/` qui portent sur les fonctions de présentation (`carte`, `detail`, `avant_apres`, `pseudonymisation`, `outillage`, `progression`) restent valables si ces modules sont gardés. Ceux qui pilotent Streamlit sont à réécrire contre FastAPI.

## Décisions (2026-10-17)

Tranchées par `../../sprint-change-proposal-2026-10-17.md`.

- **Positions des pseudonymes** : pas de surlignage. `Pseudonymiseur.apercu` garde sa forme (texte seul) ; les panneaux restent en texte brut. Un surlignage futur passerait par une méthode ajoutée au port, hors de ce lot.
- **Brouillon de commentaire (FR-33)** : il reste dans les livrables Excel et PowerPoint, hors de l'interface.
- **Livrables téléchargeables** : `Consultation.livrable(nom)` (contrats 1.9.0) les lit, `GET /livrables/{nom}` les sert en lecture seule, Mode repli compris.
- **Changement de stack** : reporté dans la spine (AD-25, couche `ui`, versions). Stories 7.13 à 7.17.
- **Fiche d'outillage** : ligne « UI de démo » mise à jour par la Story 7.17.
