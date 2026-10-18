---
title: "Story 7.15 : Lancement de la Chaîne et bouton de mode"
type: 'feature'
created: '2026-10-18'
status: 'done'
baseline_revision: '48fd5348bff1c4ec48ed2c6abbde0fee8a7bed64'
review_loop_iteration: 0
followup_review_recommended: false
context: ['_bmad-output/implementation-artifacts/epic-7-context.md']
warnings: []
deferred: ['encart « Dernier Passage » : le manifeste ne porte ni le nombre d Entités ni le chemin de `manifeste.json` ; l encart affiche la Date d arrêté, la durée, les tickets extraits et le `passage_id` (le chemin demanderait de construire un chemin de Passage, interdit par AD-11)', 'Chaîne lancée par un ancien processus serveur : après un redémarrage de `usine ui`, l état de la Chaîne (processus, fichier d erreurs) est perdu ; l écran repart de « En attente » (AD-25 : l état vit dans le processus serveur)', 'les autres écrans déjà ouverts ne rechargent pas leur contenu à la bascule du mode (seule la pastille et le bandeau du cadre se mettent à jour) : ils le font à leur prochain chargement, comme après une Chaîne terminée (EXPERIENCE.md, Interaction)', 'heure de la pastille « Passage publié » en UTC : décision d une heure locale toujours ouverte (voir 7.13)', 'suppression de `app.py` (Streamlit) et des constantes dupliquées `app.X` : 7.17 ; `INTERVALLE_SONDAGE`, `LIGNES_ERREUR_MAX` et `LANCEMENT_REPLI` vivent maintenant dans `ui/textes.py`, `app.X` les réimporte', 'intégration (AD-21) : `docs/tests-manuels.md` appartient à `main` ; fusionner la lane sans la pousser seule, comme 7.13 et 7.14']
---

<intent-contract>

## Intent

**Problem:** l'écran `/chaine` de l'UI web n'a que le cadre commun (7.13) : le Pilote ne peut ni lancer la Chaîne, ni suivre ses 10 étapes, ni basculer en Mode repli depuis le navigateur (SCP du 2026-10-17, AD-8, AD-19, AD-25).

**Approach:** `ui/chaine.py` (`GestionChaine`, vit dans le processus serveur) démarre `usine rapport` en sous-processus, une Chaîne à la fois, et construit la vue `VueChaine` à chaque sondage ; `serveur.py` expose `GET/POST /api/chaine` et `POST /api/mode`, et tient le mode courant en mémoire ; `chaine.js` sonde chaque seconde et affiche étapes, barre, journal, bandeaux et boutons.

## Boundaries & Constraints

**Always:** `GestionChaine` reçue de `ui/cli.py` (AD-1) ; progression lue en ouvrir-lire-fermer (`progression.lire_progression`), fichier retrouvé par `fichier_nouveau` ; constantes `INTERVALLE_SONDAGE`, `LIGNES_ERREUR_MAX`, `LANCEMENT_REPLI` dans `textes.py` et réimportées par `app.py` ; boutons `aria-disabled="true"` (jamais `disabled`), motif visible lié par `aria-describedby` ; le mode de départ reste `USINE_MODE_REPLI`, il ne change que par `POST /api/mode` ; seules deux routes `POST` changent un état, aucune ne touche un Passage ni Jira ; pas d'`innerHTML` de données, pas de ressource externe.

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` ; lancer une vraie Chaîne ou joindre Jira dans les tests ; bascule automatique du mode ; second lancement pendant une Chaîne.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Lancement | `POST /api/chaine`, Mode réel, racine présente | 202, `usine rapport` en sous-processus (`python -m usine rapport`, `cwd` racine), vue `en_cours`, boutons de lancement et de mode bloqués avec motif | démarrage en `OSError` : vue en `attente` avec `erreur` |
| Deuxième lancement | Chaîne en cours | 409, motif `MOTIF_LANCEMENT_EN_COURS`, aucun second processus | — |
| Mode repli ou racine absente | `POST /api/chaine` | 409, motif (`LANCEMENT_REPLI` sans marques, ou racine introuvable) | — |
| Suivi | sondage chaque seconde | étapes (état, durée), `terminees` = `aria-valuenow`, compteur « n / 10 », journal (récent en haut), annonce « Étape n sur 10 : … » | ligne finale partielle ignorée ; progression invalide : `erreur`, sondage maintenu |
| Reprise | retour sur `/chaine` en cours de Chaîne | même état, boutons bloqués | — |
| Fin réussie | code 0 | bandeau `status` « Chaîne terminée : Passage publié. » + lien « Voir la carte météo » ; bouton « Relancer la Chaîne » ; l'en-tête prend le nouveau Passage | — |
| Échec | code ≠ 0 | étape « Échec », bandeau `alert` : étape (ou « hors d'une étape »), code, au plus 20 dernières lignes d'erreur, `AUCUN_RAPPORT` ; le Passage affiché ailleurs ne change pas | sans sortie d'erreur : « aucun message » |
| Annonces | région `status` | change d'étape, fin, échec ; jamais à chaque sondage, ni entre deux étapes | — |
| Bascule | `POST /api/mode` `{"mode": "repli"\|"reel"}` | 200, `VueCadre` du nouveau mode ; tous les écrans lisent la copie ou le dernier Passage réel | 409 pendant une Chaîne ; 422 corps invalide ; 403 origine étrangère ; copie absente : `REPLI_ABSENT` dans le cadre, bouton de retour utilisable |

</intent-contract>

## Code Map

- `src/usine/ui/chaine.py` -- `GestionChaine` (`lancer`, `vue`, `en_cours`, verrou), `LancementRefuse`, `DESCRIPTIONS` des 10 étapes, libellés et motifs, `vue_dernier_passage`.
- `src/usine/ui/vues.py` -- `VueChaine`, `VueEtape`, `VueBouton`, `VueBandeauChaine`, `VueLigneJournal`, `VueDernierPassage`, `DemandeMode`.
- `src/usine/ui/serveur.py` -- mode en mémoire (`_Mode`), `/api/chaine` (GET, POST), `/api/mode` (POST), refus d'origine étrangère (`_meme_origine`).
- `src/usine/ui/cli.py` -- `application_web` fournit `GestionChaine(racine)`.
- `src/usine/ui/textes.py`, `app.py` -- constantes déplacées, `app.X` conservé.
- `src/usine/ui/statique/` -- `chaine.html`, `chaine.js`, `envoyer` et `rafraichirCadre` de `cadre.js`, styles de `cadre.css`.
- `tests/unit/ui/test_chaine.py` -- doublure de sous-processus et progression synthétique ; `docs/tests-manuels.md` -- 3.8.

## Tasks & Acceptance

**Execution:**
- Vues, `GestionChaine`, routes, composition (`cli`).
- Page, script, styles.
- Tests avec TestClient, `docs/tests-manuels.md` 3.8.

**Acceptance Criteria:**
- Given `/chaine`, when le Pilote clique sur le lancement, then `usine rapport` démarre en sous-processus, une Chaîne à la fois, et l'état se sonde chaque seconde.
- Given une Chaîne en cours, when on quitte puis rouvre `/chaine`, then le suivi reprend et les deux boutons restent `aria-disabled="true"` avec leur motif.
- Given une étape en échec, then « Échec », étape, code et au plus 20 lignes d'erreur ; le Passage affiché ailleurs est inchangé.
- Given la barre, then `aria-valuenow` = étapes terminées ; la région `status` n'annonce que changements d'étape, fin et échec.
- Given le bouton de mode, then bascule vers `demo/repli/passage/` et retour au dernier Passage réel ; `REPLI_ABSENT` si la copie manque ; jamais de bascule automatique.

## Design Notes

**Le bouton « Lancer la Chaîne » de l'en-tête** reste un lien vers `/chaine` qui ne lance rien (EXPERIENCE.md, Information Architecture) : inchangé, absent de `/chaine`.

**Écritures.** Le mode est un attribut du processus serveur, changé par `POST /api/mode` seul, refusé pendant une Chaîne. Un `POST` sans corps JSON (lancement) est une « requête simple » que n'importe quelle page ouverte dans le navigateur pourrait émettre : `TrustedHostMiddleware` limite `Host` à `127.0.0.1` et `localhost` sur toutes les routes (DNS rebinding : 400), et `_meme_origine` refuse un `Origin` présent qui ne nomme pas ce même hôte et ce même port (403). Bascule et lancement passent par un verrou d'écriture commun.

**Annonces.** Le serveur calcule le texte (`annonce`), vide quand rien de nouveau n'est à dire ; le script ne remplace le texte de la région que s'il diffère du précédent, donc le lecteur d'écran n'entend ni sondage, ni répétition.

**Un seul verrou.** Le lancement, la lecture de l'état et du fichier d'erreurs passent par un `threading.Lock` : deux clics quasi simultanés ne démarrent qu'un processus.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q --tb=short` -- tout vert.
- `bash verif_nav.sh <worktree> 8765 /chaine / /entites/ENT-A` (Edge headless, Mode repli) -- sortie 0 ; DOM de `/chaine` : 10 étapes, bouton de lancement `aria-disabled="true"` lié à son motif, bouton « Revenir au Mode réel ».
- `curl -X POST` sur `/api/mode` (repli, réel, repli), `/api/chaine` (409 en repli), `Origin` étranger (403), corps invalide (422) -- constatés.

## Revue

Revue unique (Opus) du 2026-10-18 sur `48fd534..d58ce6c`, avec la liste du second avis (Haiku).

- medium · second avis 1 · corrigé · DNS rebinding confirmé (POST `/api/mode` avec `Host` et `Origin` `evil.test:8765` → 200) : `TrustedHostMiddleware` (`HOTES_AUTORISES` = `127.0.0.1`, `localhost`, tout port) sur toutes les routes, `Origin` analysé par `urlsplit` (hôte autorisé, même `netloc` que `Host` ; `null` ou autre port : 403) ; les `TestClient` des tests UI prennent `base_url=http://127.0.0.1`, la liste de production n'inclut pas `testserver`.
- low · second avis 2 · corrigé · fenêtre réelle entre la lecture de `mode.repli` par `lancer_chaine` et le verrou de `GestionChaine` : verrou d'écriture commun aux deux routes `POST` ; test à deux fils (échoue sans le verrou).
- low · second avis 3 · corrigé · `charger()` annule le minuteur en attente : un seul sondage programmé après `visibilitychange` ou `pageshow`.
- low · second avis 4 · corrigé · Mode repli sans Passage enregistré : `AUCUN_PASSAGE_REPLI` au lieu d'une invitation à lancer la Chaîne.
- low · second avis 5 · corrigé · fin et échec annoncés deux fois : quand un bandeau (`status` ou `alert`) est affiché, la région `#annonce` se tait ; l'API garde `annonce` inchangée.
- low · second avis 6 · corrigé · serveur muet au lancement ou à la bascule : les boutons reprennent l'état de la dernière vue (motif compris), le cadre affiche « serveur injoignable ».
- low · second avis 7 · corrigé · `OSError` de la lecture de la progression (y compris `fichiers_progression` au lancement) : signalée dans `erreur`, sondage maintenu, plus de 500 ; test ajouté.
- low · second avis 8 · rejeté · `usine rapport` manuel suivi à la place : il faudrait qu'il démarre avant le clic et écrive son premier événement après l'instantané `avant` ; `fichier_nouveau` prend le plus ancien horodatage, l'usage documenté est un seul lanceur (l'UI).
- low · second avis 9 · corrigé · tests ajoutés : `Host` forgé (400 partout, `localhost` accepté), `Origin` `null` / autre port / autre hôte (403), écriture sans `Origin` acceptée, verrou exercé sous deux fils.
- Vérification navigateur (Edge headless, Mode repli, `http://127.0.0.1:8765`) : `/chaine`, `/`, `/entites/ENT-A` en sortie 0.
