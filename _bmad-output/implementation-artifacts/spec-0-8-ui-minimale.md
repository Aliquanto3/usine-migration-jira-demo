---
title: 'Story 0.8 (E0-8) : UI minimale'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '14cb30fe8427c767b4d69c31890775b08080dff5'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-0-context.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** La démo n'a aucune surface visible : rien n'affiche la carte météo du dernier Passage, ne lance la Chaîne ni n'en suit la progression, et le Mode repli n'est signalé nulle part (Story 0.8 de `epics.md`, amorces de FR-43 et FR-45).

**Approach:** Une page Streamlit dans `usine.ui` affiche :
- la carte météo du dernier Passage publié, lue via `Consultation` seulement ;
- un bouton qui lance `usine rapport` en sous-processus et affiche chaque `Etape` en lisant `sorties/progression/<passage_id>.jsonl` en ouvrir-lire-fermer ;
- un bandeau « Mode repli » permanent quand `USINE_MODE_REPLI=1`.

`usine ui` démarre la page.

## Boundaries & Constraints

**Always:**
- `usine.ui` n'importe que `usine.contrats`, `usine.consultation`, `usine.composition` et `streamlit` (contrat import-linter). L'accès aux Passages passe par une fonction de `composition`, qui rend une `Consultation` sur le dernier Passage publié ou `None`.
- L'UI n'ouvre jamais `donnees/entrepot.duckdb` ni un répertoire `sorties/passages/.en-cours-*`. Elle ne lit que via `Consultation` et le fichier de progression.
- Lancement : `subprocess.Popen([sys.executable, "-m", "usine", "rapport", ...], cwd=racine)`, sans bloquer la page. Un module `src/usine/__main__.py` délègue à `usine.cli.main`.
- Progression :
  - le fichier du Passage lancé est le premier `sorties/progression/*.jsonl` apparu après le lancement, absent de la liste prise juste avant ;
  - chaque sondage ouvre, lit et ferme le fichier, puis valide chaque ligne complète par `EvenementProgression` ;
  - une dernière ligne incomplète (sans `\n`) est ignorée jusqu'au sondage suivant ;
  - l'affichage donne, pour chaque `Etape` dans l'ordre d'AD-8, son dernier statut (`en_cours`, `reussie`, `sautee`, `echouee`) ou « en attente ».
- Mode repli : lu par `composition` depuis `Secrets` (racine `.env` compris), jamais activé automatiquement (H-30). Le bandeau s'affiche en haut de la page et reste visible quel que soit l'état de la page.
- Carte météo : une ligne par Entité, avec son libellé français de couleur (`contrats.tickets.LIBELLES` ou l'équivalent de `rendu`) et la Date d'arrêté du Passage. Sans Passage publié, un message explicite remplace la carte.
- Toute la logique hors affichage vit dans des fonctions pures testables sans Streamlit : sélection du fichier de progression, lecture des lignes, état par étape, lignes de la carte.

**Never:**
- Modifier `src/usine/contrats/`, `src/usine/ports/`, `pyproject.toml`, `uv.lock` ; ajouter une dépendance.
- Lire un fichier de Passage hors de `Consultation`, appeler la Chaîne dans le processus de l'UI, ou écrire dans `sorties/`.
- Construire les écrans complets (détail d'Entité, Agent, avant/après, comparaison des Paliers : lane L7).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Carte météo | Passage publié (Journal graine 42, 2026-10-09) | page avec une ligne par Entité (ENT-A, ENT-B), couleur égale à `consultation.meteo()`, Date d'arrêté 09/10/2026 | N/A |
| Sans Passage | `sorties/passages/` vide | message « aucun Passage publié », pas d'erreur | N/A |
| Mode repli | `USINE_MODE_REPLI=1` | bandeau « Mode repli » présent en tête de page | N/A |
| Hors Mode repli | variable absente | aucun bandeau | N/A |
| Lancement | clic sur « Lancer la Chaîne » (Popen injecté en test) | commande `[python, "-m", "usine", "rapport", ...]` dans la racine ; la page reste interactive | N/A |
| Progression | fichier avec `extraction` `en_cours` puis `reussie`, `instantanes` `en_cours` | `extraction` : réussie ; `instantanes` : en cours ; autres : en attente | N/A |
| Ligne partielle | dernière ligne sans `\n` | ignorée, aucune erreur | N/A |
| Choix du fichier | deux fichiers anciens et un nouveau apparu après le lancement | le nouveau est suivi | N/A |
| Échec | ligne `echouee` sur `kpi` | `kpi` affiché en échec | N/A |
| Commande | `usine ui --help` | aide de la sous-application, code 0 | N/A |

</intent-contract>

## Code Map

- `src/usine/ui/cli.py` -- sous-application `usine ui` (callback seul) : ajouter la commande qui lance `streamlit run <chemin de usine/ui/app.py>` en sous-processus.
- `src/usine/composition.py` -- `construire_rapport`, `lancer_rapport`, `Rapport.fabrique_consultation` ; ajouter `consultation_dernier_passage(racine) -> Consultation | None`. Elle utilise `ConsultationPassage(...).dernier_passage()` pour localiser `<date>/<id>/`, avec `url_jira` venant de `config/jira.yaml` et du Mode repli. Ajouter aussi `mode_repli(racine) -> bool`.
- `src/usine/consultation/passage.py` -- `ConsultationPassage(repertoire, racine_passages=, url_jira=, date_arrete=)`, `dernier_passage()`, `meteo()`.
- `src/usine/contrats/passage.py` -- `Etape` (ordre AD-8), `StatutEtape`, `EvenementProgression`.
- `src/usine/chaine/ecrivain.py:110` -- progression écrite dans `sorties/progression/<passage_id>.jsonl`, en ouvrir-ajouter-fermer.
- `src/usine/rendu/commun.py` -- libellés de couleur déjà utilisés par le rendu. `ui` ne peut pas importer `rendu` : reprendre `contrats.tickets.LIBELLES` si les couleurs y figurent, sinon un petit dictionnaire local.
- `src/usine/cli.py` -- `main()` ; enregistre déjà `ui`.
- `tests/unit/chaine/environnement.py` -- `preparer_racine` (copie `config/` et `gabarits/`) pour publier un Passage d'essai.

## Tasks & Acceptance

**Execution:**
- `src/usine/__main__.py` -- `from usine.cli import main` puis `main()`.
- `src/usine/ui/progression.py` -- `fichiers_progression(racine) -> frozenset[Path]`, `fichier_nouveau(avant, racine) -> Path | None`, `lire_progression(chemin) -> tuple[EvenementProgression, ...]` (ouvrir-lire-fermer, ligne partielle ignorée), `etat_des_etapes(evenements) -> list[tuple[Etape, str]]`.
- `src/usine/ui/carte.py` -- `lignes_carte(consultation) -> list[dict[str, str]]` (Entité, Météo) et libellés.
- `src/usine/ui/lancement.py` -- `lancer_chaine(racine, date_arrete=None, popen=subprocess.Popen) -> subprocess.Popen[bytes]`.
- `src/usine/ui/app.py` -- page Streamlit :
  - bandeau Mode repli ;
  - carte du dernier Passage ;
  - bouton de lancement, avec la liste des fichiers mémorisée dans `st.session_state` ;
  - suivi de la progression rafraîchi par sondage (`st.rerun` ou fragment à intervalle) tant que le processus tourne.
  
  La racine est le répertoire courant, ou `USINE_RACINE` si elle est définie.
- `src/usine/ui/cli.py` -- commande `usine ui` (`streamlit run`).
- `src/usine/composition.py` -- `consultation_dernier_passage`, `mode_repli`.
- `tests/unit/ui/test_progression.py`, `test_carte.py`, `test_lancement.py`, `test_app.py` (via `streamlit.testing.v1.AppTest`, `monkeypatch.chdir` sur une racine d'essai), `tests/unit/test_cli.py` ou `tests/unit/ui/test_cli.py` -- matrice I/O.

**Acceptance Criteria:**
- Given le dépôt, when `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest`, then tout passe, et `lint-imports` confirme que `usine.ui` n'importe ni `usine.chaine` ni `usine.adaptateurs`.
- Given un test qui inspecte `src/usine/ui/*.py`, when il cherche `entrepot.duckdb`, `.en-cours` et `duckdb`, then aucune occurrence n'est trouvée.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 34 findings — high 0, medium 6, low 27, false 1, maybe-false 0
- findings:
  - `[low]` `[patch]` (verification-gap) Chemin de succès (code 0, `st.rerun`, carte rafraîchie) jamais testé — `test_lancement_succes`.
  - `[low]` `[patch]` (verification-gap) Chemins d'erreur de la page non testés — `test_mode_repli_illisible` et `test_passage_illisible`.
  - `[medium]` `[patch]` (verification-gap) `USINE_MODE_REPLI` illisible fait planter la carte — `mode_repli` lève une `UsineErreur` qui nomme la variable.
  - `[medium]` `[patch]` (verification-gap) stderr en tube lu après la fin : blocage possible — stderr écrit dans un fichier temporaire.
  - `[medium]` `[patch]` (blind) Blocage par stderr — même correctif.
  - `[medium]` `[patch]` (blind) `USINE_MODE_REPLI` illisible — même correctif.
  - `[low]` `[reject]` (blind) Fichier de progression d'un autre lancement suivi — règle de sélection fixée par la spec ; un second `usine rapport` concurrent échoue sur le verrou (AD-6).
  - `[low]` `[patch]` (blind) Processus et tube jamais nettoyés — fichier temporaire fermé dans les deux issues ; arrêt d'un lancement en cours hors périmètre E0.
  - `[low]` `[reject]` (blind) Importer `app.py` exécute la page — convention Streamlit ; la logique testable vit dans des modules purs.
  - `[low]` `[patch]` (blind) Fin de lancement non testée — même correctif.
  - `[low]` `[patch]` (blind) Règles d'URL Jira non testées — `test_url_jira`.
  - `[low]` `[patch]` (blind) Fixture de module avant le nettoyage de l'environnement — nettoyage dans `racine_publiee`.
  - `[low]` `[reject]` (blind) Libellés de couleur dupliqués avec `rendu` — `ui` ne peut pas importer `rendu` ; libellés stables.
  - `[low]` `[reject]` (blind) `usine ui` sans options de port ou de racine — `USINE_RACINE` suffit en E0 ; écrans complets en L7.
  - `[low]` `[reject]` (blind) Étapes « en attente » si le lancement meurt avant la progression — l'erreur s'affiche à côté ; affinage en L7.
  - `[low]` `[reject]` (blind) Écarts entre la spec et le code — le correctif serait une édition de la spec.
  - `[low]` `[reject]` (blind) Test d'isolement textuel — complété par import-linter ; aucune construction dynamique du chemin dans `ui`.
  - `[medium]` `[patch]` (edge) `ValidationError` dans la carte — même correctif.
  - `[medium]` `[patch]` (edge) Blocage par stderr — même correctif.
  - `[low]` `[patch]` (edge) Tube jamais fermé en succès — même correctif.
  - `[low]` `[patch]` (edge) Second lancement possible pendant le premier — retour immédiat si le processus suivi tourne encore.
  - `[low]` `[patch]` (edge) `OSError` au lancement — message « Lancement de la Chaîne impossible ».
  - `[low]` `[reject]` (edge) Mauvais fichier de progression suivi — même raison que la ligne blind.
  - `[low]` `[reject]` (edge) Ligne de progression corrompue → toutes les étapes « en attente » — l'écrivain écrit des lignes complètes et validées ; cas improbable.
  - `[low]` `[reject]` (edge) `PermissionError` sur `sorties/passages` — droits du poste de démo ; improbable.
  - `[low]` `[reject]` (edge) `.env` illisible — même raison.
  - `[false]` `[reject]` (edge) « Dernier Passage » au sens de la date d'arrêté — c'est la définition d'AD-7 (maximum de `(date_arrete, horodatage_fin)`).
  - `[low]` `[reject]` (intention) URL Jira lue par `composition` hors de `Consultation` — c'est la composition qui configure le lecteur (AD-11 : `url_ticket` est construit dans `consultation`).
  - `[low]` `[reject]` (intention) Aucun vrai `usine rapport` lancé depuis l'UI en test — sous-processus remplacé par une doublure ; la Chaîne est éprouvée de bout en bout par ses propres tests.
  - `[low]` `[reject]` (intention) Garde « jamais `entrepot.duckdb` » limitée au texte de `ui` — l'UI n'appelle que `consultation_dernier_passage` et `mode_repli`, qui n'ouvrent ni DuckDB ni `.en-cours-*`.
  - `[low]` `[reject]` (intention) Bandeau non vérifié pendant un lancement — il est dessiné en tête à chaque exécution complète de la page, et le fragment ne réexécute que le suivi.
  - `[low]` `[reject]` (intention) Pas de bascule de Mode repli dans l'UI (H-30) — l'AC 3 ne nomme que la variable ; la bascule relève de la lane L7.
  - `[low]` `[reject]` (intention) Écritures hors de `src/usine/ui/` — exigées par les couches (`__main__`, fonctions de composition).
  - `[low]` `[reject]` (intention) Aucun serveur Streamlit démarré en test — `AppTest` exécute la page ; un démarrage réel a été vérifié à la main par l'implémenteur.

### 2026-10-12 — Review pass (suivi, code actuel)
- verdicts: 30 findings — high 0, medium 0, low 28, false 2, maybe-false 0
- findings:
  - `[low]` `[patch]` (verification-gap) `st.rerun()` de fin de lancement invisible aux tests — `test_rerun_unique_en_fin_de_chaine` (espion).
  - `[low]` `[patch]` (verification-gap) Ligne de progression invalide non testée sur la page — `test_progression_invalide`.
  - `[low]` `[patch]` (verification-gap) Ctrl+C de `usine ui` non testé — `test_interruption` ; `OSError` au démarrage de Streamlit traduite en code 1 (`test_streamlit_introuvable`).
  - `[low]` `[patch]` (intention) Couleurs de la carte non vérifiées sur la page — `test_carte_meteo` compare aux libellés de `consultation.meteo()`.
  - `[low]` `[reject]` (intention) Ligne `echouee` sur `kpi` vérifiée seulement en fonction pure — l'affichage n'est qu'une table des états calculés.
  - `[low]` `[reject]` (intention) Choix entre deux anciens fichiers vérifié en fonction pure — même raison.
  - `[low]` `[reject]` (intention) Page « non bloquante » non démontrée avec un vrai processus — `Popen` ne bloque pas par construction ; le vrai processus est désormais éprouvé côté lancement.
  - `[low]` `[reject]` (intention) Bandeau non vérifié dans tous les états — carried.
  - `[low]` `[reject]` (intention) Garanties d'accès vérifiées statiquement — carried.
  - `[false]` `[reject]` (intention) Import de `pydantic` contraire à la liste d'imports — la liste vise les paquets `usine.*` et les dépendances externes du contrat import-linter, qui reste vert.
  - `[false]` `[reject]` (blind) `composition.py` absent du diff — fonctions livrées par le commit 05ee86f, hors du périmètre des fichiers relus.
  - `[low]` `[patch]` (blind) `LIBELLES_ETATS` sans test de couverture — `test_libelles_de_tous_les_etats`.
  - `[low]` `[reject]` (blind) Noms d'étapes techniques affichés — écrans complets en L7.
  - `[low]` `[reject]` (blind) stderr ignoré en cas de succès — `usine rapport` n'écrit rien d'utile en succès ; lane L7 pour un journal visible.
  - `[low]` `[patch]` (blind) Message d'erreur sans limite — 20 dernières lignes (`test_erreur_tronquee`).
  - `[low]` `[patch]` (blind) Racine inexistante non signalée — message explicite et bouton désactivé (`test_racine_introuvable`).
  - `[low]` `[patch]` (blind) Option `--date-arrete` non confrontée à la vraie CLI — `test_option_date_arrete_de_la_cli`.
  - `[low]` `[patch]` (blind) Sondage du fragment non testé — même correctif que la ligne verification-gap.
  - `[low]` `[reject]` (blind) Tests rangés dans le mauvais fichier — cosmétique.
  - `[low]` `[reject]` (blind) Clés de `session_state` codées en dur dans un test — cosmétique.
  - `[low]` `[reject]` (blind) Bouton actif malgré un Mode repli illisible — l'erreur s'affiche en tête ; le sous-processus échoue avec un message.
  - `[low]` `[patch]` (edge) `fichier_erreurs()` hors du `try` — déplacé dans le `try`.
  - `[low]` `[reject]` (edge) `glob` qui lève `OSError` — droits du poste de démo, improbable.
  - `[low]` `[reject]` (edge) Autre lancement concurrent suivi par erreur — carried (verrou AD-6).
  - `[low]` `[reject]` (edge) Second onglet pendant un lancement — le verrou fait échouer le second, avec un message.
  - `[low]` `[reject]` (edge) Égalité de seconde entre deux fichiers — carried.
  - `[low]` `[patch]` (edge) `OSError` au démarrage de Streamlit — même correctif.
  - `[low]` `[reject]` (edge) Fin de session pendant un lancement — limite de Streamlit, documentée dans les risques.
  - `[low]` `[patch]` (risque nommé lors de la passe initiale) stderr en fichier temporaire jamais éprouvé avec un vrai processus — `test_vrai_processus_erreurs_volumineuses` (200 000 caractères, code 2, fichier fermé).
  - `[low]` `[reject]` (blind) Écritures dans `sorties/` non testées — l'UI n'écrit nulle part ; le sous-processus est la Chaîne.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check .` -- expected: aucun écart.
- `uv run mypy` -- expected: aucune erreur.
- `uv run lint-imports` -- expected: tous les contrats KEPT.
- `uv run pytest` -- expected: tout vert.
- `uv run usine ui --help` -- expected: code 0.

## Auto Run Result

Status: done

**Résumé.** La page Streamlit (`usine ui`) affiche :
- un bandeau « Mode repli » permanent quand `USINE_MODE_REPLI=1` ;
- la carte météo du dernier Passage publié, lue via `Consultation` ;
- un bouton qui lance `python -m usine rapport` en sous-processus ;
- le suivi de chaque `Etape`, lu dans le fichier de progression en ouvrir-lire-fermer.

L'UI n'ouvre ni l'entrepôt ni un `.en-cours-*`.

**Fichiers.**
- `src/usine/ui/{app,carte,lancement,progression,cli}.py` : page, carte, lancement, progression et commande.
- `src/usine/__main__.py` : point d'entrée `python -m usine`.
- `src/usine/composition.py` : `mode_repli` et `consultation_dernier_passage`.
- `tests/unit/ui/` : tests.

**Revue.** 34 findings, tous consignés dans le journal de tri. 15 lignes `patch` (6 medium en 2 causes : `USINE_MODE_REPLI` illisible, blocage par stderr) donnent 6 correctifs ; aucun élément différé ; 19 rejets motivés.

**Revue de suivi.** `true`. Le passage de stderr par un fichier temporaire n'est éprouvé qu'avec une doublure de `Popen`. Aucun test ne lance un vrai `usine rapport` depuis la page, si bien que le comportement avec un enfant bavard sous Windows n'est pas vérifié de bout en bout.

**Vérification.** ruff, ruff format, mypy, lint-imports et pytest : 840 tests passés. `usine ui --help` répond avec le code 0.

**Risques résiduels.**
- Le fichier de progression suivi est choisi par heuristique : c'est le premier nouveau fichier après le lancement.
- Aucune bascule du Mode repli n'existe dans l'UI : elle relève de la lane L7.

### Revue de suivi (2026-10-12)

**Résumé.** Revue du code actuel de l'UI : 30 findings, 14 lignes `patch` (aucune medium) donnant 6 correctifs, 0 différé.

**Risque fermé.** Le risque nommé lors de la passe initiale l'est : un vrai sous-processus qui écrit 200 000 caractères sur stderr se termine sans blocage, et son erreur est relue intégralement.

**Autres apports.**
- Tests : l'appel unique à `st.rerun()` en fin de lancement, une ligne de progression invalide, Ctrl+C et l'échec du démarrage de Streamlit, les couleurs de la carte, la couverture des libellés d'état, l'option `--date-arrete` confrontée à la vraie CLI.
- Message d'erreur limité à 20 lignes.
- Une racine introuvable est signalée explicitement, avec le bouton désactivé.

**Revue de suivi.** `false` : aucun correctif `high`.

**Vérification.** ruff, ruff format, mypy, lint-imports et pytest : 873 tests passés.
