---
date: 2026-10-17
auteur: Anaël (via bmad-correct-course)
statut: approuvé (2026-10-17)
déclencheur: spec UX de l'interface web (ux-designs/ux-usine-migration-jira-demo-2026-10-17, commit 21f8449)
portée: modérée
---

# Sprint Change Proposal — remplacer l'UI Streamlit par FastAPI + HTML statique

## 1. Résumé du problème

La spec UX du 17/10/2026 (`DESIGN.md`, `EXPERIENCE.md`) décrit une interface web servie par FastAPI : une page HTML statique par écran, un petit script sans framework qui charge les données en JSON, HTML et CSS écrits à la main d'après la charte WaveStack. Elle remplace l'application Streamlit actuelle (`src/usine/ui/app.py`, lancée par `usine ui`).

Pourquoi : l'UI Streamlit fonctionne (Stories 0.8 et 7.1 à 7.11 terminées), mais elle a l'air d'un notebook. Elle ne permet ni une URL par écran, ni le plancher d'accessibilité WCAG 2.2 AA, ni la charte de la maquette canvas. La démo de 10 minutes devant le Sponsor (UJ-4, SM-5) doit avoir l'air du produit d'une vraie équipe.

Constat technique : la spine d'architecture fige Streamlit 1.65 (couche `ui`, liste des externes, versions, seed), et l'Epic 7 décrit des écrans Streamlit. `EXPERIENCE.md` laisse trois points ouverts : le report dans la spine, le service des livrables et les positions des pseudonymes. Ce document les tranche.

## 2. Analyse d'impact

### Checklist

| # | Point | Statut | Constat |
|---|---|---|---|
| 1.1 | Story déclenchante | [x] | Aucune story en échec : la spec UX déclenche le changement. 7.12 (répétitions) est en `review`, en attente des répétitions. Il faut la faire sur la nouvelle UI. |
| 1.2 | Nature | [x] | Changement de technologie d'interface, exigé par la spec UX. Les exigences ne changent pas. |
| 1.3 | Preuves | [x] | `EXPERIENCE.md` § Migration depuis Streamlit et § Open Questions ; spine l. 48, 68, 457, 466, 486, 532, 590. |
| 2.1 | Epic courante | [x] | Epic 7 : livrée sauf 7.12. On ajoute des stories, on ne rouvre pas les stories terminées. |
| 2.2 | Changements d'epic | [!] | Epic 7 : cinq nouvelles stories, 7.13 à 7.17, à placer avant 7.12. |
| 2.3 | Epics futures | [x] | Epic 8 : 8.2 (validation M7) suit 7.12, donc elle est décalée d'autant. La fiche 8.1 est corrigée par 7.17. |
| 2.4 | Epics obsolètes ou nouvelles | [N/A] | Aucune. |
| 2.5 | Priorités | [x] | La migration passe avant 7.12 et 8.2. Les bonus restent exclus. |
| 3.1 | PRD | [N/A] | Le PRD ne nomme pas Streamlit. FR-43 à FR-46, NFR-11 et NFR-12 sont inchangés et restent satisfaits. |
| 3.2 | Architecture | [!] | Couche `ui` et ses externes, AD-8, AD-11 (nouvelle lecture), AD-24 (précision), nouvel AD-25, versions, seed, carte E0. |
| 3.3 | UX | [!] | `EXPERIENCE.md` : clore les Open Questions et retirer le conditionnel sur le surlignage. `DESIGN.md` : composant `marque-pseudonyme` à retirer. |
| 3.4 | Autres artefacts | [!] | `pyproject.toml` (dépendances, import-linter), `tests/depot/`, `tests/unit/ui/`, `docs/fiche-outillage.md` et son test, `demo/script-demo.md`, `SPEC-…md`, `docs/QUESTIONS.md` (H-28), `README.md` (GIF Streamlit). |
| 4.1 | Ajustement direct | [x] | Viable : on garde les modules de présentation purs. On réécrit `app.py` et `cli.py` en serveur FastAPI et on ajoute les pages statiques. Effort moyen, risque faible. |
| 4.2 | Retour arrière | [N/A] | Aucun : l'UI Streamlit reste en service jusqu'à 7.17. |
| 4.3 | Revue du MVP | [N/A] | Le périmètre MVP ne change pas. |
| 4.4 | Voie retenue | [x] | Ajustement direct (option 1). |

### Impact sur les epics et les stories

- **Story 0.8** (terminée) : ses critères restent vrais (lecture par `Consultation`, sous-processus, pas d'accès à `entrepot.duckdb`, bandeau Mode repli). Seul le mot « Streamlit » vieillit. On ajoute une note de remplacement, sans réécrire l'historique.
- **Stories 7.1 à 7.11** (terminées) : leurs critères d'acceptation sont repris tels quels comme critères de parité par 7.13 à 7.16. Elles ne sont pas rouvertes.
- **Story 7.12** : on garde son statut `review`, mais elle est bloquée par 7.17. On répète sur la nouvelle UI.
- **Story 8.2** : décalée, parce qu'elle a 7.12 pour prérequis.

### Impact technique

- **Gardés, à adapter** : `carte`, `detail`, `avant_apres`, `pseudonymisation`, `outillage`, `progression`, `agent`, `lancement`, `navigation`. Ces modules sont purs et ne dépendent pas de Streamlit. Leurs sorties en Markdown (`tableau_markdown`, `lien_ticket`, `echapper_markdown`, pastilles emoji) deviennent des données structurées : une clé et son URL, une couleur nommée. Le HTML est produit côté navigateur. Les constantes de texte restent la source unique de la microcopie (`EXPERIENCE.md`, Voice and Tone).
- **Réécrits** : `app.py` (page Streamlit) devient `serveur.py` (application FastAPI). `cli.py` lance uvicorn au lieu de `streamlit run`.
- **Nouveaux** : `src/usine/ui/statique/`, avec 7 pages HTML, une feuille CSS, un script JS sans framework et trois polices sous licence OFL en woff2 avec leurs licences. Fichiers servis en local (NFR-12).
- **Dépendances** :
  - on retire `streamlit==1.65.0`, et `pandas` disparaît s'il n'est plus tiré par rien ;
  - on ajoute `fastapi` et `uvicorn` en version exacte, et `markdown-it-py` en dépendance directe (déjà verrouillé en 4.2.0 par `rich`) ;
  - `starlette` 1.7.0 et `uvicorn` 0.54.0 sont déjà dans `uv.lock` ;
  - la contrainte `pyarrow < 26` perd sa raison (« streamlit exige < 26 ») : il faut la revérifier, sans monter de version dans ce lot.
- **Contrats** : un ajout au port `Consultation` (`livrable`, voir § 4.2), donc `CONTRATS_VERSION` 1.8.0 → 1.9.0, modification mineure.
- **Tests** : 3 543 lignes dans `tests/unit/ui/`.
  - Les tests des modules purs restent valables, sauf les assertions sur le Markdown à adapter.
  - `test_app.py`, `test_app_agent.py`, `test_bout_en_bout.py` et `test_cli.py` utilisent `streamlit.testing`. Ils sont réécrits contre `fastapi.testclient.TestClient` (httpx est déjà en dépendance).
  - `test_repli.py` est à vérifier.

## 3. Voie recommandée

**Ajustement direct** : cinq stories ajoutées à l'Epic 7, en série, sur la lane L7.

- **Justification** : les règles métier, `Consultation` et la microcopie existent et sont testées. La migration remplace seulement la couche d'affichage. La parité se vérifie contre les critères des Stories 7.1 à 7.11.
- **Effort** :
  - quatre stories moyennes (7.13 à 7.16) et une story mécanique (7.17) ;
  - environ 1,5 à 2 M tokens au total, selon les mesures du projet (une story moyenne avec revue coûte environ 300 à 400 k tokens) ;
  - c'est au-delà du plafond de fin de projet du 12/10, déjà atteint : Anaël doit l'accorder explicitement.
- **Risques** :
  - Le comportement du script JS n'est pas couvert par pytest. Parade : un script court et sans état, une liste de tests manuels par écran dans `docs/` (même pratique que 6.10-b), et l'essai réel de 7.12.
  - Les polices sont à télécharger une fois, depuis leurs dépôts officiels sous licence OFL.
- **Calendrier** : 7.12 et 8.2 sont décalées de la durée du lot.

## 4. Propositions de modification détaillées

### 4.1 Questions ouvertes tranchées

**Q1. Positions des pseudonymes : pas de surlignage, port inchangé.**
`Pseudonymiseur.apercu(texte) -> str` reste tel quel. Les panneaux montrent le texte brut, et la comparaison côte à côte suffit au flux 4, comme l'indique déjà `EXPERIENCE.md`.

Raisons :
- renvoyer les positions changerait un port, l'adaptateur Presidio de la lane L6 et la doublure de test, pour un gain seulement visuel ;
- repérer les pseudonymes par motif dans l'UI risquerait de marquer un texte d'origine qui leur ressemble.

Le composant `marque-pseudonyme` est retiré de `DESIGN.md`. Un surlignage futur passerait par une nouvelle méthode `apercu_plages`, ajoutée au port sans casser l'existant, hors de ce lot.

**Q2. Service des livrables : lecture par `Consultation`, téléchargement par le serveur.**
- On ajoute au port `Consultation` la méthode `livrable(nom: Literal["rapport_xlsx", "rapport_pptx"]) -> bytes | None` :
  - elle renvoie le contenu du fichier `FICHIERS_PASSAGE[nom]` du Passage lu, en ouvrir-lire-fermer ;
  - elle renvoie `None` si le fichier est absent ;
  - contrats 1.9.0.
- Le serveur expose `GET /livrables/{nom}`, en lecture seule. Il répond avec le bon type MIME et `Content-Disposition: attachment`, ou avec une page d'erreur qui nomme le fichier et renvoie à la carte.
- La même méthode sert en Mode repli (`demo/repli/passage/` contient déjà `rapport-2026-10-09.xlsx` et `.pptx`).
- Le serveur ne construit aucun chemin vers un Passage : AD-11 reste vrai à la lettre (un seul lecteur des fichiers d'un Passage). Lire tout le fichier en mémoire, quelques centaines de Ko, ne garde aucun fichier ouvert pendant le téléchargement : rien ne gêne un renommage sous Windows (AD-8).

**Q3. Report du changement de stack** : voir § 4.3.

**Q4. Brouillon de commentaire (FR-33)** : on confirme l'hypothèse de `EXPERIENCE.md`. Il reste dans l'Excel et le PowerPoint, hors de l'interface.

**Q5. Fiche d'outillage** : corrigée par 7.17 (§ 4.5).

### 4.2 Epics et stories (`epics.md`)

**Story 0.8 — note ajoutée sous le titre**

```
OLD:
### Story 0.8 : UI minimale (E0-8)

As a Pilote,
I want une page Streamlit qui affiche …

NEW:
### Story 0.8 : UI minimale (E0-8)

> Interface remplacée par l'UI web FastAPI (Stories 7.13 à 7.17, Sprint Change Proposal du 2026-10-17). Les critères ci-dessous restent des exigences de la nouvelle UI.

As a Pilote,
I want une page Streamlit qui affiche …
```

Justification : l'historique d'une story terminée est conservé, et ses critères restent vrais.

**En-tête de l'Epic 7 (l. 1677)**

```
OLD:
… **Stories 7.7 à 7.12 : Palier 2, après l'Epic 6.** **Écrit seulement dans :** `ia/agent`, `ui/`, `demo/`, `config/demo.yaml`, `evals/agent` et `tests/unit/` correspondant. L'UI ne lit les Passages que via `Consultation` (AD-11).

NEW:
… **Stories 7.7 à 7.11 : Palier 2, après l'Epic 6.** **Stories 7.13 à 7.17 : migration de l'UI vers FastAPI + HTML statique (AD-25), après 7.11 et avant 7.12** ; elles suivent `ux-designs/ux-usine-migration-jira-demo-2026-10-17/` (DESIGN.md pour l'apparence, EXPERIENCE.md pour le comportement) et reprennent comme critères de parité ceux des Stories 7.1 à 7.11. **Story 7.12 en dernier, sur la nouvelle UI.** **Écrit seulement dans :** `ia/agent`, `ui/`, `demo/`, `config/demo.yaml`, `evals/agent` et `tests/unit/` correspondant ; 7.14 écrit aussi dans `contrats/`, `ports/consultation.py`, `consultation/` et `tests/contrat/` ; 7.17 dans `pyproject.toml`, `uv.lock`, `tests/depot/`, `docs/`, `README.md` et `SPEC-usine-migration-jira-demo.md`. L'UI ne lit les Passages que via `Consultation` (AD-11).
```

**Résumé de l'Epic 7 (l. 242)** : ajouter « , sur une interface web FastAPI (Stories 7.13 à 7.17) » après « comparaison des Paliers) ».

**Stack (l. 142)** : `streamlit 1.65` → `fastapi <version figée> + uvicorn 0.54.0, markdown-it-py 4.2.0`.

**Nouvelles stories, insérées entre 7.11 et 7.12**

```
### Story 7.13 : Socle web FastAPI et cadre commun

As a auteur,
I want que `usine ui` démarre un serveur FastAPI local qui sert le cadre commun des sept écrans,
So that la démo a une interface web qui ressemble au produit d'une vraie équipe.

**Exigences :** FR-43, FR-45, NFR-11, NFR-12 · **AD :** AD-11, AD-19, AD-25 · **UX :** DESIGN.md (tout), EXPERIENCE.md (Foundation, Information Architecture, Cadre, Accessibility Floor)

**Acceptance Criteria:**

**Given** `usine ui`
**When** l'auteur le lance
**Then** uvicorn sert l'application sur `127.0.0.1` seulement, et les sept URL d'écran de EXPERIENCE.md répondent par une page HTML statique

**Given** n'importe quelle page
**When** elle se charge hors réseau
**Then** polices, CSS et script viennent tous du serveur local, et aucune requête ne sort (NFR-12)

**Given** le cadre commun
**When** on l'inspecte
**Then** il porte l'en-tête (pastille « Passage publié » lue dans le manifeste, pastille de mode toujours visible, bouton « Lancer la Chaîne » absent de `/chaine`), la navigation latérale (`aria-current="page"`), le lien d'évitement, un seul `<h1>`, `<html lang="fr">` et un titre de page « {Écran} · Usine de migration »

**Given** `USINE_MODE_REPLI=1` au démarrage
**When** une page s'affiche
**Then** la pastille « Mode repli » et le bandeau `app.BANDEAU_REPLI` sont visibles ; sans la variable, le mode est réel, et aucune bascule n'est jamais automatique (AD-19)

**Given** le serveur arrêté pendant qu'une page est ouverte
**When** un appel JSON échoue
**Then** le bandeau d'erreur « L'interface ne joint plus le serveur. Relancer usine ui. » s'affiche une seule fois

Notes : l'UI Streamlit reste en place jusqu'à 7.17 (`usine ui --streamlit` le temps du lot). Une liste de tests manuels du cadre est ajoutée à `docs/`.

### Story 7.14 : Carte météo, détail d'une Entité et livrables

As a Pilote,
I want la carte météo filtrable, le détail d'une Entité avec la comparaison des Paliers et les livrables du Passage à télécharger,
So that je justifie un rouge et je repars avec le Rapport quotidien.

**Exigences :** FR-17, FR-20, FR-21, FR-29, FR-32, FR-43, FR-46 · **AD :** AD-9, AD-11, AD-25 · **Parité :** Stories 7.1, 7.2, 7.7 (Explication, Paliers)

**Acceptance Criteria:**

**Given** le port `Consultation`
**When** on lit un livrable
**Then** `livrable(nom)` renvoie le contenu de `rapport_xlsx` ou `rapport_pptx` du Passage lu, ou `None` s'il est absent ; `CONTRATS_VERSION` passe à 1.9.0 et les suites `tests/contrat/` couvrent la méthode

**Given** la carte météo
**When** le Pilote filtre sur « Rouge »
**Then** le tableau se filtre dans le navigateur, sans rechargement, et une région `role="status"` annonce « 1 Entité affichée »

**Given** les livrables du Passage affiché
**When** le Pilote clique sur l'un d'eux
**Then** `GET /livrables/{nom}` le télécharge ; un livrable absent affiche « Non généré pour ce Passage », sans lien

**Given** `/entites/ENT-B?palier=1` sur un Passage de Palier 2
**When** la page s'affiche
**Then** l'Explication affiche `detail.EXPLICATION_PALIER_1`, la Prévision est masquée, et Météo, Règles et KPI sont identiques à `?palier=2`

**Given** une Entité absente du Passage
**When** on ouvre son URL
**Then** « Entité {entite} absente du Passage affiché. » et un lien vers la carte

**Given** une clé de ticket
**When** l'URL de `consultation.url_ticket` vaut `None` (Mode repli)
**Then** la clé est du texte simple ; sinon c'est un lien qui s'ouvre dans un nouvel onglet, avec un nom accessible terminé par « (nouvel onglet) »

### Story 7.15 : Lancement de la Chaîne et bouton de mode

As a Pilote,
I want lancer la Chaîne et suivre ses 10 étapes dans le navigateur, et basculer en Mode repli d'un clic,
So that je montre le rapport fait en une commande et je prépare la démo hors réseau.

**Exigences :** FR-25, FR-43, FR-45 · **AD :** AD-8, AD-19, AD-24, AD-25 · **Parité :** Stories 7.3, 7.6

**Acceptance Criteria:**

**Given** l'écran `/chaine`
**When** le Pilote clique sur le bouton de lancement
**Then** le serveur démarre `usine rapport` en sous-processus (une Chaîne à la fois), et la page sonde chaque seconde (`app.INTERVALLE_SONDAGE`) un état lu dans `sorties/progression/<passage_id>.jsonl` en ouvrir-lire-fermer

**Given** une Chaîne en cours
**When** le Pilote quitte puis rouvre `/chaine`
**Then** le suivi reprend ; le bouton de lancement et le bouton de mode restent `aria-disabled="true"`, avec leur motif lié par `aria-describedby`

**Given** une étape en échec
**When** la CLI se termine
**Then** l'étape est marquée « Échec », et le bandeau d'erreur nomme l'étape, le code de sortie et au plus 20 lignes d'erreur (`app.LIGNES_ERREUR_MAX`) ; le Passage affiché ailleurs ne change pas

**Given** la barre de progression
**When** les étapes avancent
**Then** `aria-valuenow` suit le nombre d'étapes terminées, et la région `status` n'annonce que les changements d'étape, la fin et l'échec

**Given** le bouton « Passer en Mode repli »
**When** le Pilote clique
**Then** le serveur bascule sur `demo/repli/passage/` pour tous les écrans ; « Revenir au Mode réel » ramène au dernier Passage réel ; `app.REPLI_ABSENT` s'affiche si la copie manque

### Story 7.16 : Agent, Avant / après, Pseudonymisation et Outillage

As a Pilote,
I want les quatre derniers écrans de la démo dans l'interface web,
So that la démo de 10 minutes se joue de bout en bout sur la nouvelle UI.

**Exigences :** FR-31, FR-40, FR-41, FR-43, FR-44, FR-45, FR-47 · **AD :** AD-8, AD-11, AD-24, AD-25 · **Parité :** Stories 7.4, 7.5, 7.7 (Pseudonymisation), 7.9, 7.11

**Acceptance Criteria:**

**Given** l'écran `/agent` en Mode réel
**When** le Pilote envoie une question
**Then** `POST /api/agent/question` passe par la session de l'Agent existante, « L'Agent consulte le Passage… » s'affiche pendant l'attente, puis la réponse remplace la précédente avec son badge de contrôle et ses outils, et le focus passe sur la réponse ; une réponse rejetée n'affiche pas son texte

**Given** le Mode repli
**When** le Pilote ouvre `/agent`
**Then** la saisie disparaît, `agent.MESSAGE_REPLI` s'affiche, et chaque question enregistrée rejoue sa réponse avec `agent.mention_repli` ; des réponses dont le `passage_id` diffère de la copie sont refusées (`agent.REFUS_REPLI`)

**Given** `/avant-apres`
**When** l'écran s'affiche
**Then** les valeurs sont celles des fonctions de `avant_apres`, sans écart ni ratio calculé ; le segment choisit la période des deux grandes cartes

**Given** `/pseudonymisation?ticket=DEMO-17`
**When** l'écran s'affiche
**Then** l'original et la version de `Pseudonymiseur.apercu` s'affichent en texte brut côte à côte, sans surlignage, dans deux régions focalisables ; un moteur absent est nommé dans le bandeau d'erreur

**Given** `/outillage`
**When** l'écran s'affiche
**Then** le serveur rend `docs/fiche-outillage.md` en HTML (markdown-it-py, HTML brut désactivé), et ✅, ⚠️ et ❌ deviennent les pastilles « Oui », « À surveiller » et « Non »

### Story 7.17 : Retrait de Streamlit

As a auteur,
I want que Streamlit disparaisse du code, des dépendances et des documents,
So that le dépôt n'a plus qu'une seule interface, documentée telle qu'elle est.

**Exigences :** FR-47, NFR-8 · **AD :** AD-1, AD-25 · **Prérequis :** 7.13 à 7.16

**Acceptance Criteria:**

**Given** le dépôt
**When** on cherche `streamlit`
**Then** il n'apparaît plus que dans l'historique : `app.py` et l'option `--streamlit` sont supprimés, `streamlit` est retiré de `pyproject.toml`, `uv.lock` et des listes d'externes de `[tool.importlinter]`, et `tests/depot/` est à jour (`fastapi`, `uvicorn`, `markdown_it` classés pour `usine.ui` seulement)

**Given** `tests/unit/ui/`
**When** la suite complète s'exécute
**Then** plus aucun test n'importe `streamlit` ; les tests de pilotage passent par `TestClient`, et la CI est verte sous Windows et Linux

**Given** `docs/fiche-outillage.md`, `demo/script-demo.md`, `SPEC-usine-migration-jira-demo.md`, `docs/QUESTIONS.md` (H-28) et `README.md`
**When** on les relit
**Then** ils décrivent l'interface web FastAPI (§ 4.5 du Sprint Change Proposal du 2026-10-17), et `tests/unit/docs/test_fiche_outillage.py` attend la nouvelle ligne
```

**Story 7.12** : on ajoute « **Prérequis :** Story 7.17 (répétitions sur l'interface web). » sous la ligne Exigences.

**`sprint-status.yaml`** : on ajoute `7-13` à `7-17` en `backlog`, avant `7-12`, avec un commentaire « migration UI FastAPI, SCP 2026-10-17 ». `7-12` reste en `review` avec la note « bloquée par 7.17 ».

### 4.3 Architecture (`ARCHITECTURE-SPINE.md`)

| Endroit | OLD | NEW |
|---|---|---|
| l. 48, tableau des couches | `Interface \| ui/ \| contrats, consultation, composition \| streamlit` | `Interface \| ui/ \| contrats, consultation, composition \| fastapi, uvicorn, markdown-it-py` |
| l. 68, graphe | `ui["ui (Streamlit)"]` | `ui["ui (FastAPI)"]` |
| AD-8, puce Progression | « L'UI lance la CLI en sous-processus et lit ce fichier… » | « Le serveur de l'UI lance la CLI en sous-processus, une Chaîne à la fois, et lit ce fichier en ouvrir-lire-fermer à chaque sondage du navigateur (décision du 10/10/2026, H-28). » |
| AD-11, nouvelle puce après Liens Jira | — | « **Livrables.** `Consultation.livrable(nom)` renvoie le contenu de `rapport_xlsx` ou `rapport_pptx` du Passage lu, ou `None`. L'UI ne construit aucun chemin vers un Passage (contrats 1.9.0, décision du 17/10/2026). » |
| AD-11, puce Côte à côte | « …exposé à l'UI par la composition, en local seulement. » | « …exposé à l'UI par la composition, en local seulement. Il renvoie un texte seul : l'UI ne surligne pas les pseudonymes (décision du 17/10/2026). » |
| AD-24, puce Mode repli | « En Mode repli, l'UI propose les questions enregistrées sous forme de choix, sans saisie libre. » | « En Mode repli, l'UI propose les questions enregistrées sous forme de choix, sans saisie libre. Les livrables proposés sont ceux de la copie, lus par `Consultation.livrable`. » |
| Après AD-24 | — | Nouvel **AD-25** (ci-dessous) |
| l. 457, versions | `pyarrow \| 25.0.1 (streamlit exige < 26)` | `pyarrow \| 25.0.1` (contrainte à revérifier en 7.17, sans montée de version dans ce lot) |
| l. 466, versions | `streamlit (tire pandas 3.0.6) \| 1.65.0` | trois lignes : `fastapi \| <version exacte figée en 7.13>`, `uvicorn \| 0.54.0`, `markdown-it-py \| 4.2.0` |
| l. 486, seed | `UI["Streamlit (localhost)"]` | `UI["UI web FastAPI (127.0.0.1)"]` ; on ajoute `NAV["Navigateur"] -- HTTP local --> UI` |
| l. 532, arborescence | `ui/  # Streamlit` | `ui/  # FastAPI : serveur, vues JSON, statique/ (HTML, CSS, JS, polices)` |
| l. 590, carte E0 | `E0-8 UI \| Streamlit : …` | inchangé (historique), avec « (remplacé par AD-25, Stories 7.13 à 7.17) » ajouté |
| Carte des capacités, FR-43 à FR-46 | `AD-8, AD-11, AD-19, AD-24` | `AD-8, AD-11, AD-19, AD-24, AD-25` |

**Nouvel AD-25 : Interface web locale, pages statiques et vues JSON**

```
### AD-25 : Interface web locale, pages statiques et vues JSON

- **Binds :** FR-43 à FR-46, NFR-11, NFR-12
- **Prevents :** une UI qui calcule ou formate à sa façon ; une démo qui casse hors réseau ; une interface joignable depuis le réseau invité ; un second écrivain du Passage.
- **Rule :**
  - **Serveur.** `usine ui` lance uvicorn sur `127.0.0.1`. Un seul module, `ui/serveur.py`, crée l'application FastAPI ; il ne reçoit ses services (`Consultation`, Agent, `apercu`) que de `ui/cli.py`, racine de composition (AD-1).
  - **Pages.** Une page HTML statique par écran, dans `ui/statique/`, sans moteur de gabarits. Un script sans framework charge les données par `fetch` sur `/api/…`. Polices, CSS et JS sont servis en local (NFR-12).
  - **Vues JSON.** Les réponses de `/api/…` sont des modèles pydantic locaux à `ui/`, pas des contrats. Ils sont construits par les modules de présentation purs (`carte`, `detail`, …) à partir de valeurs déjà formatées par `contrats.format`. Le navigateur affiche sans calculer ni formater (AD-9).
  - **Écritures.** Seules trois routes changent un état, toutes en `POST` : lancer la Chaîne (sous-processus `usine rapport`, AD-8), changer de mode (état du processus serveur, jamais automatique, AD-19) et poser une question à l'Agent. Aucune ne touche un Passage ni Jira.
  - **Livrables.** `GET /livrables/{nom}` sert le résultat de `Consultation.livrable` (AD-11).
  - **Mono-utilisateur.** Pas d'authentification. L'état du mode et de la Chaîne en cours vit dans le processus serveur.
```

L'import-linter ne change pas de forme : `usine.ui` garde ses trois couches permises, seuls ses externes changent.

### 4.4 UX (`EXPERIENCE.md`, `DESIGN.md`)

- `EXPERIENCE.md` l. 31 :
  - OLD : « Trois points ouverts cadrent l'implémentation : … (voir Open Questions). »
  - NEW : « Les points ouverts sont tranchés par le Sprint Change Proposal du 2026-10-17 (AD-25) : livrables lus par `Consultation.livrable`, pseudonymes non surlignés. »
- `EXPERIENCE.md` l. 132, Panneaux de Pseudonymisation :
  - OLD : « Les pseudonymes sont marqués seulement si l'aperçu fournit leurs positions. »
  - NEW : « Les pseudonymes ne sont pas surlignés : l'aperçu renvoie un texte seul (AD-11). »
- `EXPERIENCE.md` l. 247, flux 4 étape 5 : retirer la phrase « Si l'aperçu fournit les positions… la comparaison suffit. »
- `EXPERIENCE.md` l. 29 : remplacer « Le découpage des routes et des endpoints JSON revient à `bmad-architecture`. » par « Le découpage des routes suit AD-25. »
- `EXPERIENCE.md` § Open Questions : les cinq points passent sous un titre « Décisions (2026-10-17) », chacun avec sa décision du § 4.1.
- `DESIGN.md` :
  - retirer `marque-pseudonyme` du front matter (l. 252-256) ;
  - retirer la phrase « Les pseudonymes sont marqués… » (l. 447) ;
  - retirer « pseudonymes » de la liste des usages de Lavande (l. 290) et de JetBrains Mono (l. 334).

### 4.5 Documents et code hors planning

- **`docs/fiche-outillage.md` l. 23**
  - OLD : `| UI de démo (Streamlit) | ✅ | ⚠️ webapp Streamlit, à vérifier | ❌ à refaire en Power Apps | ✅ | AD-1 : … |`
  - NEW : `| UI de démo (FastAPI + HTML statique) | ✅ | ⚠️ webapp Dataiku « standard » (HTML/JS + backend Python) : l'API FastAPI se réécrit en backend Flask, à vérifier | ❌ à refaire en Power Apps ; les pages statiques ne se portent pas telles quelles | ✅ | AD-1, AD-25 : `usine.ui` n'importe aucun adaptateur (`lint-imports`) |`
- **`docs/fiche-outillage.md` l. 45**
  - OLD : « L'UI Streamlit ne se porte pas : c'est un écran Power Apps à refaire. »
  - NEW : « L'UI web ne se porte pas sur Power Platform : c'est un écran Power Apps à refaire. Sur Dataiku, seule l'API FastAPI est à réécrire en Flask : les pages HTML se reprennent. »
- **`tests/unit/docs/test_fiche_outillage.py` l. 18** : `"UI de démo (FastAPI + HTML statique)"`.
- **`demo/script-demo.md` l. 3** : « …de l'interface web (`uv run usine ui`, puis http://127.0.0.1:8000) ». On ajoute l'étape « ouvrir `/chaine` et passer en Mode repli » (flux 4).
- **`SPEC-usine-migration-jira-demo.md`** :
  - l. 109 : « Streamlit pour l'agent et la démo » devient « FastAPI + HTML statique pour l'agent et la démo » ;
  - l. 171 : « dans Streamlit » devient « dans l'interface web ».
- **`docs/QUESTIONS.md` H-28** : la colonne de l'alternative écartée « Exécution dans le processus Streamlit » devient « Exécution dans le processus de l'UI ».
- **`README.md`** : le GIF montre l'UI Streamlit. On le garde jusqu'à 7.12, puis on le réenregistre sur la nouvelle UI, pendant une répétition.

## 5. Passage à l'implémentation

- **Portée : modérée.** On réorganise le backlog (5 stories ajoutées, 7.12 et 8.2 décalées). Ni le PRD ni le MVP ne changent.
- **Destinataires** :
  - **Orchestrateur (session principale, Opus)** : applique les modifications d'artefacts des § 4.2 à 4.4 et met à jour `sprint-status.yaml` ;
  - **`dev-story` (Sonnet)** puis **`second-avis` (Haiku)** puis **`reviewer` (Opus)**, par story : 7.13 → 7.14 → 7.15 → 7.16 → 7.17, en série sur la lane L7. 7.14 touche les contrats : sa spec doit nommer les suites `tests/contrat/` ;
  - **Anaël** : accorde le budget du lot, puis réalise 7.12 sur la nouvelle UI et réenregistre le GIF.
- **Critères de succès** :
  - les sept URL de `EXPERIENCE.md` jouent les flux 1 à 4, Mode repli compris, hors réseau ;
  - les critères des Stories 0.8 et 7.1 à 7.11 restent vrais sur la nouvelle UI ;
  - `streamlit` n'apparaît plus que dans l'historique git ; CI verte sous Windows et Linux ; `lint-imports` vert ;
  - contrats 1.9.0, avec `livrable` couvert par `tests/contrat/` ;
  - après 7.17, release `v0.10.0` (projet `ai-portfolio`, versionnage obligatoire).
