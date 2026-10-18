---
title: "Story 7.16 : Agent, Avant / après, Pseudonymisation et Outillage"
type: 'feature'
created: '2026-10-18'
status: 'done'
baseline_revision: 'd347bfb'
review_loop_iteration: 0
followup_review_recommended: false
context: ['_bmad-output/implementation-artifacts/epic-7-context.md']
warnings: []
deferred: ['hors périmètre : le contrat n `StatutControle` n a pas de valeur « hors périmètre » ; le badge est déduit du texte de refus `SANS_REPONSE` (injecté par `ui/cli.py`), pas d un champ du contrat', 'encart Agent de la carte (trois questions types) et bouton de question du détail : non livrés en 7.14, donc aucun lien vers `/agent?question=…` n existe encore ; l écran lit déjà le paramètre `question`', 'réponse de l Agent en texte brut (retours à la ligne conservés) : la mise en forme Markdown de l ancienne UI n est pas reprise', 'état « Chargement… » des blocs : non repris, comme en 7.14 et 7.15 (le gabarit s affiche, le bloc apparaît à l arrivée des données)', 'première ouverture de la Pseudonymisation : le moteur (Presidio, spaCy) se charge en quelques secondes, sans indicateur', 'vérification navigateur : Edge headless ne clique pas ; le rejeu, le segment de période et l envoi de question sont couverts par les vues JSON testées et à constater à la main (docs/tests-manuels.md 3.9)', 'suppression de `app.py` (Streamlit) et de `_moteur_indisponible` dupliqué : 7.17', 'intégration (AD-21) : `docs/tests-manuels.md` appartient à `main` ; fusionner la lane sans la pousser seule']
---

<intent-contract>

## Intent

**Problem:** les écrans `/agent`, `/avant-apres`, `/pseudonymisation` et `/outillage` de l'UI web n'ont que le cadre commun : la démo de 10 minutes ne peut pas se jouer de bout en bout sur la nouvelle UI (SCP du 2026-10-17, AD-11, AD-24, AD-25).

**Approach:** `ui/ecrans.py` construit les vues pydantic (locales à `ui/`) à partir des fonctions pures des modules `agent`, `avant_apres`, `pseudonymisation`, `outillage` ; `serveur.py` expose `GET /api/agent`, `POST /api/agent/question`, `GET /api/agent/enregistrees/{rang}`, `/api/avant-apres`, `/api/pseudonymisation`, `/api/outillage` selon le mode courant ; `ui/cli.py` injecte les services (`ServicesEcrans`) ; quatre scripts statiques affichent les vues.

## Boundaries & Constraints

**Always:** services reçus de `ui/cli.py` (AD-1) ; formatage côté serveur (AD-9) ; pas d'`innerHTML` de données (seul `outillage.js` insère le HTML de la fiche rendu par le serveur, HTML brut désactivé) ; `POST` question protégé par `TrustedHostMiddleware` et `_meme_origine` ; pseudonymes non surlignés, `Pseudonymiseur.apercu` inchangé (Q1) ; aucune sortie du poste.

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` ; LLM ou Presidio réels dans les tests ; calculer un écart ou un ratio ; envoyer le texte d'une réponse rejetée ; appeler le LLM en Mode repli.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Question réelle | `POST /api/agent/question`, Mode réel | session de l'Agent gardée tant que le Passage ne change pas ; vue avec badge, outils, annonce | 422 vide ; 403 origine ; 409 repli / sans Passage ; 503 session ; 502 réponse |
| Réponse rejetée | statut `rejete` | `texte` à `None`, `texte_masque` | — |
| Refus | texte `SANS_REPONSE` | badge « Hors périmètre », outils « aucun » | — |
| Mode repli | `GET /api/agent` | pas de saisie, `MESSAGE_REPLI`, questions enregistrées ; rejeu avec `mention_repli` | `passage_id` différent : `REFUS_REPLI` (vue et rejeu 409) |
| Avant / après | `GET /api/avant-apres` | valeurs des deux périodes, segment côté navigateur | config absente, classification initiale, aucun Passage : avertissement |
| Pseudonymisation | `?ticket=DEMO-17` | original et aperçu en texte brut, tickets triés | moteur ou clé absents : `erreur` nommée, sélection utilisable ; ticket inconnu : `erreur` |
| Outillage | `GET /api/outillage` | fiche en HTML, pastilles Oui / À surveiller / Non, HTML brut échappé | fiche absente : message ; illisible : `erreur` |

</intent-contract>

## Code Map

- `src/usine/ui/ecrans.py` -- `ServicesEcrans`, `GardeSession`, vues des quatre écrans.
- `src/usine/ui/vues.py` -- `VueAgent`, `VueReponseAgent`, `VueAvantApres`, `VuePseudonymisation`, `VueOutillage`, `DemandeQuestion`.
- `src/usine/ui/outillage.py` -- `rendre_fiche` (markdown-it-py, `html: False`, pastilles) ; `pseudonymisation.moteur_indisponible`.
- `src/usine/ui/serveur.py` -- `_ajouter_ecrans` ; `src/usine/ui/cli.py` -- `services_ecrans`, `manifestes_mesures`.
- `src/usine/ui/statique/` -- `agent.js`, `avant-apres.js`, `pseudonymisation.js`, `outillage.js`, `demander` de `cadre.js`, styles.
- `tests/unit/ui/test_ecrans_web.py` ; `docs/tests-manuels.md` 3.9.

## Tasks & Acceptance

**Execution:** vues et services ; routes ; pages et scripts ; tests TestClient avec doublures de session et d'aperçu ; tests manuels.

**Acceptance Criteria:** ceux de la story 7.16 (epics.md), observés par les vues JSON des routes ci-dessus.

## Design Notes

**Quatrième route `POST`.** La question appelle un LLM payant : elle passe par le même contrôle d'origine que les écritures, et le test « seules les routes d'écriture » liste maintenant trois `POST` (Chaîne, mode, question).

**Rejeu en `GET`.** Le Mode repli rejoue une réponse enregistrée : lecture seule, donc `GET /api/agent/enregistrees/{rang}`, qui relit les fichiers à chaque appel et refuse un `passage_id` étranger.

**Vérification navigateur.** `verif_nav.sh` sort 0 sur `/agent`, `/avant-apres`, `/pseudonymisation?ticket=DEMO-17`, `/outillage`, `/`, `/chaine`. Sans `USINE_CLE_PSEUDO`, `/pseudonymisation` montre le bandeau d'erreur attendu (critère « moteur absent » : variable nommée) ; avec une clé locale factice, la copie `verif_nav_pseudo.sh` (avec préchauffage du moteur et budget plus long, le moteur mettant quelques secondes à charger) remplit les deux panneaux.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q --tb=short` -- tout vert.
- `bash verif_nav.sh <worktree> 8765 /agent /avant-apres "/pseudonymisation?ticket=DEMO-17" /outillage / /chaine` -- sortie 0 ; DOM : cinq questions enregistrées, deux cartes (120 min / 4,4 s), 26 « Oui » dans la fiche.

## Revue

Revue unique (Opus) du 2026-10-18 sur `d347bfb..5545523`, avec la liste du second avis (Haiku).

- low · second avis 6 · corrigé · critère tenu côté navigateur (`carte.valeurs` porte les deux périodes, le segment choisit la valeur des deux cartes, vérifié par test et code) ; mais `?periode=cumul` n'était pas transmis et `vue.periode` ignoré : `avant-apres.js` envoie la période de l'URL et part de `vue.periode` renvoyée par le serveur.
- low · second avis 4 · rejeté · mesuré : 3,2 s au premier `apercu_pseudonymisation`, 0,0 s aux suivants (moteur Presidio et spaCy gardés en mémoire par l'adaptateur) ; seule la première ouverture attend, déjà notée dans `deferred`. Pas de cache à ajouter dans `ui/cli.py`.
- low · second avis 3 · corrigé · toute exception de `apercu()` hors `UsineErreur` (Presidio, spaCy, `ValueError`…) donne le bandeau « Moteur de Pseudonymisation indisponible » avec la première ligne de la cause, au lieu d'un 500 ; test ajouté.
- low · second avis 1 · corrigé · le 502 de `POST /api/agent/question` renvoie `REPONSE_IMPOSSIBLE` (générique) ; l'exception complète part au journal du serveur (`logging.exception`) ; test : ni URL ni clé dans la réponse.
- low · second avis 7 · rejeté · le `textarea` a `maxlength="2000"` (unités UTF-16, toujours au moins le nombre de points de code compté par pydantic) et le script ignore une question vide : le 422 n'est pas atteignable depuis l'écran.
- low · second avis 9 · corrigé · test de `rendre_fiche` : `<script>`, `<img onerror>` échappés et lien `javascript:` non rendu (markdown-it `validateLink`). Le contrôle « pas d'`innerHTML` » par chaîne reste suffisant pour des scripts sans dépendance.
- low · second avis 2 · rejeté · verrou tenu pendant l'appel LLM voulu (une question à la fois, FR-39) ; le délai relève du fournisseur et du plafond de `config/llm.yaml`, et l'écran bloque déjà une seconde question pendant l'attente.
- low · second avis 5 · rejeté · déjà consigné dans `deferred` : le contrat `StatutControle` n'a pas de valeur « hors périmètre » et `src/usine/contrats/` est hors périmètre de la story.
- low · second avis 8 · rejeté · serveur sur `127.0.0.1` seulement, `TrustedHostMiddleware` et `_meme_origine` comme les autres `POST` (sans `Origin`, requête non navigateur du poste local) ; coût borné par le plafond du LLM.
- low · second avis 10 · rejeté · le verrou est un `threading.Lock` sans logique propre ; un test à deux fils avec doublure n'apporterait que la preuve du verrou de la bibliothèque standard.
