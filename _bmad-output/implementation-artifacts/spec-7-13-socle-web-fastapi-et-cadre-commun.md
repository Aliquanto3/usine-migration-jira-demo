---
title: "Story 7.13 : Socle web FastAPI et cadre commun"
type: 'feature'
created: '2026-10-17'
status: 'done'
baseline_revision: '84d943c'
review_loop_iteration: 0
followup_review_recommended: false
context: ['_bmad-output/implementation-artifacts/epic-7-context.md']
warnings: []
deferred: ['lien de navigation vers le détail d une Entité : `/entites/ENT-A` fixe, à remplacer en 7.14 par la première Entité du Tableau des Entités (lue par le script)', 'bascule du Mode repli par bouton et `POST /api/mode` (7.15) : le mode est fixé au démarrage par `USINE_MODE_REPLI`', 'contenu des sept écrans (7.14 à 7.16) et retrait de `app.py`, de `--streamlit` et de `streamlit` (7.17)', 'heure de la pastille « Passage publié » affichée en UTC, mention « UTC » comprise (convention de `rendu.commun`) : heure locale éventuelle à décider avec le contenu de 7.15', 'intégration (AD-21) : `pyproject.toml`, `uv.lock`, `tests/depot/`, `docs/` et le spine appartiennent à `main` ; fusionner la lane dans `main` sans pousser `lane/7-ui-web` seule, sinon le contrôle des lanes de la CI échoue']
---

<intent-contract>

## Intent

**Problem:** l'UI Streamlit ne ressemble pas au produit d'une vraie équipe (SCP du 2026-10-17, AD-25) ; il faut d'abord un serveur web local et un cadre commun que les écrans des Stories 7.14 à 7.16 rempliront.

**Approach:** `usine ui` lance uvicorn sur `127.0.0.1` et sert l'application FastAPI créée par `ui/serveur.py` : sept pages HTML statiques (`ui/statique/`) qui portent le cadre complet, une feuille CSS d'après DESIGN.md, un script sans framework et la vue JSON `/api/cadre` (Passage publié, mode, bandeau de repli). `usine ui --streamlit` garde l'ancienne UI jusqu'à 7.17.

## Boundaries & Constraints

**Always:** services injectés depuis `ui/cli.py` (AD-1), `serveur.py` seul module qui crée l'application ; vues JSON en modèles pydantic locaux à `ui/` ; polices, CSS et JS servis en local, aucune URL externe (NFR-12) ; mode fixé au démarrage par `USINE_MODE_REPLI`, jamais de bascule automatique (AD-19) ; `app.BANDEAU_REPLI` réutilisé, non dupliqué ; `fastapi`, `uvicorn` et `markdown_it` autorisés à `usine.ui` seulement.

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` ; supprimer `app.py` ; changer `starlette==1.7.0` du lock ; afficher « Chargement… » ou un bandeau d'erreur sur une page qui fonctionne ; charger une ressource d'un CDN.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Sept écrans | GET `/`, `/entites/{entite}`, `/chaine`, `/agent`, `/avant-apres`, `/pseudonymisation`, `/outillage` | page HTML, `lang="fr"`, un `<h1>`, titre « {Écran} · Usine de migration », lien d'évitement, `aria-current="page"` | route inconnue : 404 ; `/docs` et `/openapi.json` absents |
| Mode réel | sans `USINE_MODE_REPLI` | pastille « Mode réel », pas de bandeau | — |
| Mode repli | `USINE_MODE_REPLI=1` | pastille « Mode repli », bandeau `BANDEAU_REPLI` sous le titre, Passage de `demo/repli/passage/` | copie absente : bandeau d'erreur `REPLI_ABSENT` |
| Aucun Passage | pas de `sorties/passages/` | pastille « Passage publié » absente | — |
| Lecture impossible | manifeste ou répertoire illisible | `erreur` dans `/api/cadre`, bandeau d'erreur (`role="alert"`) | `UsineErreur` et `OSError` rattrapées par le serveur |
| Serveur arrêté | appel JSON qui échoue | bandeau « L'interface ne joint plus le serveur. Relancer usine ui. », une seule fois | retiré à l'appel suivant réussi |
| Variable illisible | `USINE_MODE_REPLI=peut-etre` | `usine ui` s'arrête, code 1, variable nommée | — |
| Port occupé | uvicorn journalise l'échec du bind et sort (code 3) | message qui nomme l'adresse, code 1 | — |

</intent-contract>

## Code Map

- `src/usine/ui/serveur.py` -- `creer_application(repli, lire_manifeste)`, routes des sept pages, `/api/cadre`, montage de `/statique`.
- `src/usine/ui/vues.py` -- `VueCadre`, `vue_cadre`, `libelle_passage` (« Passage publié · JJ/MM/AAAA HH:MM UTC ») ; le bandeau de repli est rendu en HTML en ligne par markdown-it-py.
- `src/usine/ui/textes.py` -- `REPERTOIRE_REPLI`, `DOSSIER_REPLI`, `BANDEAU_REPLI`, `REPLI_ABSENT` extraits de `cli.py` et `app.py` (qui les importent : `app.BANDEAU_REPLI` existe toujours) pour éviter d'importer Streamlit depuis le serveur.
- `src/usine/ui/cli.py` -- `lecture_manifeste`, `application_web`, `usine ui` (uvicorn, `--port`, `--streamlit`).
- `src/usine/ui/statique/` -- sept pages HTML, `cadre.css`, `cadre.js`, `polices/` (Fredoka, Atkinson Hyperlegible, JetBrains Mono, licences OFL).
- `pyproject.toml`, `uv.lock`, `tests/depot/` -- dépendances directes `fastapi==0.143.3`, `uvicorn==0.54.0`, `markdown-it-py==4.2.0` ; contrats import-linter ; spine : version figée.
- `tests/unit/ui/test_serveur.py`, `tests/unit/ui/test_cli.py` -- pages, cadre, mode, ressources locales, lancement.
- `docs/tests-manuels.md` -- section 3.6.

## Tasks & Acceptance

**Execution:** dépendances et contrats d'import ; `textes.py` ; `vues.py` ; `serveur.py` ; `cli.py` ; pages, CSS, JS, polices ; tests ; tests manuels ; version dans le spine.

**Acceptance Criteria:**
- Given `usine ui`, when l'auteur le lance, then uvicorn sert sur `127.0.0.1` seulement et les sept URL répondent par une page HTML statique.
- Given une page chargée hors réseau, when on l'inspecte, then polices, CSS et script viennent du serveur local (test : aucune URL `http(s)` dans les HTML, la feuille et le script).
- Given le cadre, when on l'inspecte, then en-tête (pastille « Passage publié », pastille de mode, bouton « Lancer la Chaîne » absent de `/chaine`), navigation avec `aria-current="page"`, lien d'évitement, un seul `<h1>`, `<html lang="fr">` et titre « {Écran} · Usine de migration ».
- Given `USINE_MODE_REPLI=1`, when une page s'affiche, then pastille « Mode repli » et bandeau `BANDEAU_REPLI` ; sans la variable, mode réel.
- Given le serveur arrêté, when un appel JSON échoue, then le bandeau d'erreur s'affiche une seule fois.

## Design Notes

**Version.** `fastapi==0.143.3` est la dernière version stable (PyPI, 2026-10-16) ; son `requires_dist` demande `starlette>=0.46.0`, sans plafond : le `starlette==1.7.0` du lock est conservé. `git diff uv.lock` ajoute le paquet `fastapi` et les trois dépendances directes du projet ; `annotated-doc` et `opentelemetry-api`, tirés par fastapi, étaient déjà dans le lock. Ligne consignée dans le tableau des versions du spine.

**Pages sans gabarit.** Les sept pages ont le même cadre et ne diffèrent que par titre, sous-titre, entrée active, bouton d'en-tête et mention de données. Elles ont été écrites par un script jetable puis commitées : aucun moteur de gabarits à l'exécution (AD-25). La zone de contenu porte une carte « Contenu de l'écran » en attente (pas de « Chargement… » : les blocs chargés arrivent avec leurs écrans).

**Pastilles masquées au départ.** Les pastilles de mode et de passage ont l'attribut `hidden` jusqu'à l'arrivée de `/api/cadre`, pour ne jamais afficher un mode faux avant le script. Sans réponse, le bandeau d'erreur « ne joint plus le serveur » prend le relais.

**Bandeaux.** Un bandeau par type (`repli`, `erreur`, `injoignable`), identifié par son `id` ; republier le même contenu ne le recrée pas, donc ne relance pas l'annonce. Le bandeau de repli est rendu en HTML par markdown-it-py côté serveur (texte constant) ; les erreurs passent par `textContent`. Le script relit le cadre au retour sur l'onglet (`visibilitychange`, `pageshow`), ce qui fait apparaître le bandeau « serveur injoignable » quand le serveur a été arrêté entre-temps.

**Polices.** Atkinson Hyperlegible (Regular, Bold) et JetBrains Mono (Regular, Bold) : woff2 téléchargés des dépôts officiels (googlefonts/atkinson-hyperlegible, JetBrains/JetBrainsMono). Fredoka n'a pas de woff2 dans son dépôt officiel (google/fonts, `ofl/fredoka/`) : la police variable TTF officielle est convertie en woff2 avec fonttools (`Fredoka-Variable.woff2`, axes `wght` et `wdth`). Les trois licences OFL sont jointes.

**Port.** 8000 par défaut (`--port`), l'hôte est la constante `serveur.HOTE`, non réglable.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q --tb=short` -- tout vert (2865 passés, 1 ignoré, 39 désélectionnés).
- `node --check src/usine/ui/statique/cadre.js` -- sans erreur.
- `USINE_MODE_REPLI=1 uv run usine ui --port 8765`, puis `msedge --headless --disable-gpu --virtual-time-budget=5000 --dump-dom http://127.0.0.1:8765<url>` pour les sept URL -- vérifié : aucun « Chargement… », aucun bandeau d'erreur ; pastille « Mode repli », pastille « Passage publié · 12/10/2026 22:12 UTC » (Passage du repli) et bandeau de repli présents sur chaque page. Serveur arrêté ensuite (le port ne répond plus).

## Revue

Revue unique (Opus) du commit `475f328`, avec la liste du second avis (Haiku). Correctifs dans le commit de revue.

- medium, second avis 1, reporté (intégration) : confirmé, `controle_lanes.py --branche lane/7-ui-web` signale six fichiers hors lane (`pyproject.toml`, `uv.lock`, `tests/depot/` ×2, `docs/tests-manuels.md`, spine). Le contrôle tourne en CI sur tout push ou PR d'une branche `lane/`. Ces fichiers appartiennent à `main` (AD-21) et la migration est prévue par le SCP ; même cas que la Story 7.8 (`pyproject.toml` et `tests/depot/` sur `lane/7-agent-ui`). Pas d'affaiblissement du contrôle : intégrer par fusion dans `main` (CI de `main` : contrôle sans objet) et ne pas pousser `lane/7-ui-web` avant cette fusion. Consigné dans `deferred`.
- medium, second avis 2, corrigé : `cadre()` laissait passer une `OSError` (`iterdir` de `sorties/passages/`) en 500, prise par `cadre.js` pour « serveur injoignable ». `OSError` rattrapée, bandeau « Lecture du Passage impossible : … » ; test `test_cadre_repertoire_illisible`.
- medium, revue (requalifie second avis 3), corrigé : port occupé vérifié en réel, uvicorn journalise puis `sys.exit(3)` ; `usine ui` sortait en code 3 sans message de l'usine, contre « message, code 1 » de la matrice. Le test ne le voyait pas : sa doublure levait une `OSError` qu'uvicorn ne lève jamais. `SystemExit` non nul converti en message qui nomme l'adresse et code 1 ; test `test_ui_port_reellement_occupe` sur un vrai port pris.
- low, revue, corrigé : en mode réel, la lecture du manifeste passait par `consultation_dernier_passage`, qui relit `.env` et `config/jira.yaml` pour l'URL Jira ; un `jira.yaml` invalide aurait affiché une erreur de cadre sans rapport. Lecture directe de `dernier_passage()`.
- low, second avis 4, corrigé : heure de la pastille convertie en UTC (`astimezone`) et suivie de « UTC », comme `rendu.commun` ; test d'un horodatage +02:00.
- low, second avis 5, corrigé en partie : `innerHTML` gardé pour le seul bandeau de repli (texte constant `BANDEAU_REPLI`) ; markdown-it passe en `html: False`, aucun HTML brut ne traverse ; erreurs et messages en `textContent`. À ne pas étendre aux données des écrans 7.14 à 7.16.
- low, second avis 6, rejeté : rendre le mode côté serveur demande un gabarit (exclu par AD-25) ; un mode par défaut visible pourrait être faux avant la réponse (AD-19). La pastille apparaît au premier appel, et sans réponse le bandeau d'erreur prend le relais (Design Notes).
- low, second avis 7, rejeté : l'unicité du bandeau est un comportement du navigateur, non testable en pytest sans navigateur ; couverte par la vérification navigateur et le test manuel 3.6 § 5.
- low, second avis 8, corrigé : `annotated-doc` et `opentelemetry-api` étaient déjà dans le lock ; Design Notes rectifiées.
