---
title: "Story 7.14 : Carte météo, détail d'une Entité et livrables"
type: 'feature'
created: '2026-10-18'
status: 'review'
baseline_revision: '9e4639c0c68867d5d3becd508ee9df9557946560'
review_loop_iteration: 0
followup_review_recommended: false
context: ['_bmad-output/implementation-artifacts/epic-7-context.md']
warnings: []
deferred: ['colonne « Anomalies ouvertes » du tableau des Entités, variation depuis J-1 des tuiles de comptage, encart Agent (trois questions types) et bouton de question du détail : non demandés par les critères de la Story 7.14 ; l encart et le bouton relèvent de 7.16 (écran Agent, `/agent?question=`), les deux premiers sont à décider avec le Pilote', 'heure de génération des livrables (Design : « puis l heure de génération ») : `Consultation.livrable` ne renvoie que les octets, l heure demanderait une autre méthode du port, hors périmètre', 'suppression des sorties Markdown des modules purs (`tableau_markdown`, `lien_ticket`, `echapper_markdown`, `texte_*`, `lignes_*`, pastilles emoji) : encore utilisées par `app.py` (Streamlit) ; elles partent avec lui en 7.17', 'intégration (AD-21) : `src/usine/contrats/versions.py` (1.9.0), `src/usine/ports/consultation.py`, `docs/tests-manuels.md` sont des fichiers de `main` : fusionner la lane dans `main` sans pousser `lane/7-ui-web` seule, comme pour 7.13']
---

<intent-contract>

## Intent

**Problem:** l'écran Carte météo et l'écran Détail d'une Entité de l'UI web n'ont encore que le cadre commun (7.13), et l'UI ne sait pas offrir le Rapport quotidien ni le Comité de pilotage à télécharger (SCP du 2026-10-17, Q2, AD-11, AD-25).

**Approach:** le port `Consultation` gagne `livrable(nom)` (contrats 1.9.0, commit dédié) ; les modules purs `carte.py` et `detail.py` construisent des vues JSON pydantic (`/api/carte`, `/api/entites/{entite}`) à partir de valeurs déjà formatées ; deux scripts sans framework (`carte.js`, `detail.js`) les affichent ; `GET /livrables/{nom}` sert les fichiers.

## Boundaries & Constraints

**Always:** vues JSON locales à `ui/` (`vues.py`), clés de ticket et couleurs en données (`VueTicket`, `VueMeteo`) ; le navigateur affiche sans calculer, le filtre de la carte agit dans le navigateur ; JS sans `innerHTML` pour les données (`textContent` / `createElement`), sans ressource externe ; le serveur ne construit aucun chemin de Passage (AD-11) ; fonctions Markdown conservées tant que `app.py` les utilise.

**Never:** modifier autre chose de `src/usine/contrats/` ou `src/usine/ports/` que `Consultation.livrable` et `CONTRATS_VERSION` ; toucher `sprint-status.yaml` ; recalculer une Météo, une Prévision ou un KPI côté interface ; lien de téléchargement pour un livrable absent.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Carte | GET `/api/carte` | tuiles, filtre, une ligne par Entité (grave d'abord, puis Entité), 3 tickets puis `+N`, livrables | aucun Passage : message + lien « Lancer la Chaîne » ; aucune Météo : message ; lecture impossible : `erreur` |
| Filtre | choix « Rouge » (navigateur) | lignes filtrées sans rechargement ; région `role="status"` : « 1 Entité affichée » / « {n} Entités affichées » | aucune ligne : « Aucune Entité en {couleur} à cette Date d'arrêté. » |
| Détail Palier 2 | `/entites/ENT-B?palier=1` | Explication `EXPLICATION_PALIER_1`, Prévision absente ; Météo, Règles, KPI, Risque identiques à `?palier=2` | `palier` illisible : Palier 2 |
| Détail Palier 1 | Passage de Palier 1 | segment absent ; aucune sortie LLM lue ; Prévision brute affichée | — |
| Entité absente | `/entites/ENT-X` | « Entité ENT-X absente du Passage affiché. » + lien vers la carte | — |
| Navigation | GET `/entites` | 307 vers la première Entité du tableau | aucun Passage ou erreur : 307 vers `/` |
| Ticket | `url_ticket` | lien nouvel onglet, nom accessible « DEMO-1 (nouvel onglet) » | URL `None` (Mode repli) : texte simple |
| Livrable présent | GET `/livrables/rapport_xlsx` | octets, type MIME OOXML, `Content-Disposition: attachment; filename="rapport-AAAA-MM-JJ.xlsx"` | — |
| Livrable absent | GET `/livrables/rapport_pptx` | carte : « Non généré pour ce Passage » sans lien ; URL directe : page HTML 404 qui nomme le fichier et renvoie à la carte | lecture impossible : page 500, message échappé |
| Nom hors liste | GET `/livrables/autre` | 404 | — |

</intent-contract>

## Code Map

- `src/usine/ports/consultation.py`, `src/usine/consultation/passage.py`, `src/usine/contrats/versions.py` -- `livrable(nom)` (chemin `chemin_fichier_passage`, `_lire_octets`), 1.9.0 ; commit « Feat: contrats 1.9.0, Consultation.livrable ».
- `tests/contrat/consultation/test_contrat.py`, `tests/unit/consultation/test_passage.py` -- `test_livrable` (trois adaptateurs du contrat ; absence, lecture sans fichier ouvert, illisible).
- `src/usine/ui/vues.py` -- modèles `Vue*` de la carte, du détail, des tickets et des livrables.
- `src/usine/ui/carte.py` -- `vue_carte`, `entites_triees`, `vues_livrables`, `taille_lisible`, `LectureVueCarte` (carte + `livrable`) ; `MIME_LIVRABLES`.
- `src/usine/ui/detail.py` -- `vue_detail`, `section_prevision`, `section_risque`, `section_explication` ; `_morceaux`, `_kpi_cles`, `_lignes_risques` partagés avec les rendus Markdown.
- `src/usine/ui/liens.py` -- `vue_ticket`.
- `src/usine/ui/serveur.py` -- `/api/carte`, `/api/entites/{entite}`, `/entites` (redirection), `/livrables/{nom}` (GET et HEAD), `LireConsultation`.
- `src/usine/ui/cli.py` -- `lecture_consultation(racine)` (dernier Passage ou copie du Mode repli).
- `src/usine/ui/statique/` -- `carte-meteo.html`, `detail-entite.html`, `carte.js`, `detail.js`, helpers de `cadre.js`, styles de `cadre.css`, lien de navigation `/entites`.
- `tests/unit/ui/test_vues_ecrans.py` -- vues, routes, livrables, lecture réelle ; `docs/tests-manuels.md` -- 3.7.

## Tasks & Acceptance

**Execution:**
- Contrats 1.9.0 : port, adaptateur, version, tests (commit dédié).
- `vues.py`, `liens.py`, `carte.py`, `detail.py` -- vues structurées ; refactors sans effet sur les sorties Markdown.
- `serveur.py`, `cli.py` -- routes et service de lecture.
- Pages, `carte.js`, `detail.js`, `cadre.js`, `cadre.css` -- affichage.
- `tests/unit/ui/test_vues_ecrans.py`, `docs/tests-manuels.md`.

**Acceptance Criteria:**
- Given le port `Consultation`, when on lit un livrable, then `livrable(nom)` renvoie les octets ou `None` ; `CONTRATS_VERSION` vaut 1.9.0 ; les suites `tests/contrat/` le couvrent.
- Given la carte, when le Pilote filtre sur « Rouge », then le tableau se filtre dans le navigateur et la région `role="status"` annonce « 1 Entité affichée » (ou « {n} Entités affichées »).
- Given les livrables, when le Pilote clique, then `GET /livrables/{nom}` télécharge ; absent : « Non généré pour ce Passage », sans lien.
- Given `/entites/ENT-B?palier=1` sur un Passage de Palier 2, then `EXPLICATION_PALIER_1`, Prévision masquée, Météo, Règles et KPI identiques.
- Given une Entité absente, then « Entité {entite} absente du Passage affiché. » et un lien vers la carte.
- Given une clé de ticket, when `url_ticket` vaut `None`, then texte simple ; sinon lien en nouvel onglet, nom accessible terminé par « (nouvel onglet) ».

## Design Notes

**Redirection plutôt que script.** Le lien de navigation « Détail d'une Entité » pointe vers `/entites`, qui redirige (307) vers la première Entité du tableau ; il remplace le `/entites/ENT-A` fixe de 7.13 sans script ni appel supplémentaire, et marche sans JavaScript.

**Prévision masquée à `?palier=1` sur Palier 2 seulement.** Sur un Passage de Palier 1, la Prévision brute (déterministe) reste affichée, comme avec l'UI Streamlit ; le masquage ne vaut que lorsque le segment est offert et que Palier 1 est choisi (critère de la story).

**Markdown conservé.** Les modules purs gardent leurs fonctions Markdown (utilisées par `app.py`) ; les vues structurées réutilisent les mêmes petits assistants (`formater_regle`, `valeur_kpi`, `_morceaux`, `_lignes_risques`) pour que les deux rendus ne divergent pas.

**Livrables.** `vues_livrables` lit chaque fichier par `Consultation.livrable` pour savoir s'il existe et en donner la taille ; quelques centaines de Ko, relus à chaque affichage de la carte. Le nom de fichier vient de `chemin_fichier_passage` (contrats).

**Sans `innerHTML`.** Toutes les données passent par `textContent` ; le seul `innerHTML` du site reste le bandeau de repli constant de 7.13.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q --tb=short` -- tout vert.
- `node --check src/usine/ui/statique/carte.js` et `detail.js` -- sans erreur.
- `bash verif_nav.sh <worktree> 8765 / /entites/ENT-A "/entites/ENT-A?palier=1" /entites/ENT-INCONNUE` (Edge headless, Mode repli) -- sortie 0 ; DOM : 10 lignes de carte (2 rouges, 1 orange, 6 jaunes, 1 verte), annonce « 10 Entités affichées », deux liens de livrables ; détail rempli ; Entité inconnue : message et lien. Avec une copie du repli en Palier 2 : segment présent, `?palier=1` masque la Prévision.
- `curl -sI http://127.0.0.1:<port>/livrables/rapport_xlsx` (Mode repli) -- 200, type OOXML, `content-disposition: attachment; filename="rapport-2026-10-09.xlsx"`.
