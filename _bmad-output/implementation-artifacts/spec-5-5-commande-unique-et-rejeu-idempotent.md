---
title: 'Story 5.5 : Commande unique et Rejeu idempotent'
type: 'feature'
created: '2026-10-12'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-5-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/sprint-change-proposal-2026-10-12-contrats-1-2.md'
warnings: []
deferred: []
baseline_revision: 'a663bf357641113585540dfdbb59a06106836ee0'
---

<intent-contract>

## Intent

**Problem:** `usine rapport` existe (Stories 0.5, 5.1 à 5.4) mais trois points de la 5.5 manquent : le Rejeu n'est vérifié que sur une partie des fichiers et dans un cas où rien ne varie (source `journal`, `horodatage_extraction` nul), donc les exclusions des rendus (`rapport_xlsx`, `rapport_pptx`, contrats 1.2) ne sont jamais exercées ; la Chaîne ne journalise pas sa progression ; la console Windows affiche la sortie en mojibake (constat 15 de la rétro Epic 0).

**Approach:** un test de Rejeu générique, piloté par `FICHIERS_PASSAGE` et `EXCLUSIONS_REJEU`, compare deux Passages Palier 1 de même date dont l'instant d'extraction et la version des données diffèrent (source composite simulée), et prouve que seuls les champs exclus diffèrent. La CLI passe stdout/stderr en UTF-8 et configure `logging` (INFO, français) ; la Chaîne journalise début, chaque étape et publication.

## Boundaries & Constraints

**Always:** `contrats/` et `ports/` intacts (gelés) ; tests sans réseau, sans Jira ; messages et journaux en français ; aucun texte de ticket journalisé au-delà de DEBUG ; un champ exclu dans un fichier reste comparé ailleurs ; Parquet comparés sans exclusion.

**Never:** modifier `EXCLUSIONS_REJEU` ; figer `horodatage_extraction` ou `version_donnees` pour faire passer le Rejeu ; publier un rapport en cas d'échec ; appeler Jira.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Sans option | `usine rapport` un lundi | Date d'arrêté = vendredi, `rapport-2026-10-09.xlsx/.pptx` publiés | — |
| Rejeu composite | deux Passages, instants d'extraction et versions de données différents | tous fichiers égaux hors exclusions ; B5/B8 et lignes exclues de l'Annexe diffèrent effectivement | — |
| Échec d'étape | étape `rendu` en panne | code 1, message nomme `rendu`, aucun `rapport-*` sous `passages/` | `UsineErreur` traduite par `main` |
| Console non UTF-8 | stdout en cp1252 | « Étape », « « » » écrits en UTF-8 sans `UnicodeEncodeError` | `errors="replace"` en dernier recours |

</intent-contract>

## Code Map

- `src/usine/cli.py` -- `main()` : ajouter `configurer_console()` (reconfigure `sys.stdout`/`sys.stderr` en UTF-8 si `reconfigure` existe, `logging.basicConfig` INFO sur stderr, format français sobre) appelé avant `app()`.
- `src/usine/chaine/execution.py:31,41-130` -- `journal` déjà défini ; ajouter `journal.info` au début du Passage, après chaque étape (nom, statut) et à la publication. Rien d'autre.
- `src/usine/composition.py:134-146,340-390` -- `Rapport` (frozen, `donnees`, `horodatage_extraction`, `registre`), `EtapeRendu(gabarit, donnees, horodatage_extraction)` ; point d'injection du test via `monkeypatch` de `construire_rapport` (motif de `tests/unit/chaine/test_cli.py:203`).
- `src/usine/contrats/passage.py:175-225` -- `FICHIERS_PASSAGE`, `EXCLUSIONS_REJEU` (lecture seule).
- `tests/unit/chaine/environnement.py:85` -- `sans_exclusions(nom, valeur)` à réutiliser pour JSON/JSONL.
- `tests/unit/chaine/test_cli.py:30-150` -- `_usine`, fixture `racine`, `_passages`, ancien test de Rejeu partiel (garder, il couvre la source `journal`).
- `src/usine/rendu/commun.py:355-358`, `excel.py:121-126`, `powerpoint.py:20-21` -- commentaires « à déclarer » périmés : désormais déclarés en contrats 1.2.

## Tasks & Acceptance

**Execution:**
- `src/usine/cli.py` -- `configurer_console()` + appel dans `main()` -- AC UTF-8 et journalisation.
- `src/usine/chaine/execution.py` -- journalisation INFO de la progression -- AC journalisation.
- `src/usine/rendu/commun.py`, `excel.py`, `powerpoint.py` -- reformuler les commentaires : « déclarés sous `EXCLUSIONS_REJEU[...]` (contrats 1.2) ».
- `tests/unit/chaine/test_rejeu.py` (nouveau) -- Rejeu générique composite simulé (Parquet, JSON, JSONL, cellules xlsx avec hyperliens, textes de slides et lignes de tableaux par libellé) ; vérifie Palier 1 (`sautee` pour les 4 étapes LLM, rapports présents) ; vérifie que l'ensemble des différences observées est exactement l'ensemble attendu (champs exclus effectivement différents) ; échec à l'étape `rendu` sans rapport publié ; journal INFO de progression capturé (`caplog`).
- `tests/unit/test_cli.py` -- test de `configurer_console` sur un flux cp1252.

**Acceptance Criteria:**
- Given deux Passages Palier 1 du 2026-10-09 dont `horodatage_extraction` et `version_donnees` diffèrent, when le test de Rejeu compare tous les fichiers, then seuls les chemins de `EXCLUSIONS_REJEU` diffèrent, et `Traçabilité!B5`, `Traçabilité!B8`, `Annexe méthode!Horodatage d'extraction`, `Annexe méthode!Version des données` diffèrent bien.
- Given `usine rapport`, when la Chaîne s'exécute, then chaque étape est journalisée en français sur stderr et la sortie s'écrit en UTF-8.

## Spec Change Log

## Review Triage Log
### 2026-10-12 — Review pass
Mode économique : couches Blind Hunter et Intent Alignment sautées (2 reviewers : Verification Gap, Edge Case Hunter).
- verdicts: 11 findings — high 0, medium 2, low 5, false 3, maybe-false 1
- findings:
  - `[medium]` `patch` (VG) aucun test ne vérifie que `main()` appelle `configurer_console()` — ajout de `test_main_configure_la_console_avant_la_commande` (ordre console puis app).
  - `[maybe-false]` `reject` (VG) `basicConfig` réel lié au capsys d'un test si le plugin logging de pytest est désactivé — sans objet dans la configuration du dépôt ; ne serait que low.
  - `[medium]` `patch` (ECH) `basicConfig(level=INFO)` sur la racine fait sortir l'INFO de httpx (une ligne par requête Jira) — racine en WARNING, logger `usine` en INFO ; test mis à jour.
  - `[false]` `reject` (ECH) second `main()` dans le même processus avec stderr fermé — un seul `main()` par processus en production ; sous pytest `basicConfig` est sans effet.
  - `[low]` `reject` (ECH) `reconfigure` qui lèverait sur un flux exotique — improbable (TextIOWrapper standard), garde superflue.
  - `[low]` `reject` (ECH) pas de ligne de journal pour l'étape en échec — la CLI affiche déjà « Erreur : … étape « x » … » sur stderr.
  - `[false]` `reject` (ECH) graphiques, images et groupes non comparés — les rendus n'en produisent aucun (`rendu/` sans chart ni image).
  - `[low]` `reject` (ECH) dépaquetage `premier, second` peu parlant si ≠ 2 dossiers — message pytest suffisant, cas non rencontré.
  - `[low]` `reject` (ECH) la spec dit « exactement l'ensemble attendu » mais le test fait `>=` + aucune différence hors exclusions — l'AC (seuls les champs exclus diffèrent) est vérifiée ; l'égalité stricte serait instable (horodatages d'étapes réels).
  - `[low]` `reject` (ECH) l'AC « journalisé sur stderr » n'est vérifiée que par caplog — couvert par le test direct de `configurer_console` et le nouveau test d'ordre ; même cause que le 1er constat.
  - `[false]` `reject` (ECH) étape journalisée seulement en cas de succès = AC non tenue — l'AC porte sur la progression ; l'échec est nommé par le message d'erreur.


## Design Notes

Composite simulé : le test enveloppe `composition.construire_rapport` et remplace `donnees` (`source="composite"`, `version_donnees` propre à chaque appel), `horodatage_extraction` et `registre[Etape.rendu]` (même gabarit). Les manifestes diffèrent alors sur `horodatage_extraction` et `version_donnees`, exclus ; `trace_previsions.version_donnees` reste celui de la composition (même valeur), ce qui ne gêne pas.

Comparaison PowerPoint : clé `<titre de slide>!<libellé de ligne>` pour les tableaux à deux colonnes, sinon `<titre>!#<index de forme>` ; titres de slides d'Entité uniques par construction.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert.

## Auto Run Result

Status: done

- **Changement** : `usine rapport` configure la console (UTF-8, `errors="replace"`) et la journalisation (usine en INFO, tiers en WARNING) ; la Chaîne journalise début, chaque étape et publication ; nouveau test de Rejeu composite simulé qui compare tous les fichiers de `FICHIERS_PASSAGE` (Parquet, JSON, JSONL, cellules, slides) et prouve que seuls les champs de `EXCLUSIONS_REJEU` diffèrent, dont `Traçabilité!B5/B8` et les deux lignes de l'Annexe méthode ; échec à l'étape `rendu` sans rapport ; nom des fichiers vérifié sans option ; commentaires « à déclarer » corrigés.
- **Fichiers** : `src/usine/cli.py` (console et journaux) ; `src/usine/chaine/execution.py` (3 `journal.info`) ; `src/usine/rendu/{commun,excel,powerpoint}.py` (commentaires) ; `tests/unit/chaine/test_rejeu.py` (nouveau) ; `tests/unit/chaine/test_cli.py` (noms `rapport-2026-10-09.*`) ; `tests/unit/test_cli.py` (UTF-8, ordre console/app).
- **Revue** : 2 patches medium appliqués, 0 différé, 9 rejetés (motifs au Triage Log).
- **Revue de suivi** : non recommandée (aucun high, patches simples et testés).
- **Vérification** : ruff check, ruff format --check, mypy, lint-imports, pytest (2335 passés, 1 sauté) verts.
- **Risque résiduel** : la source composite est simulée (pas d'appel Jira) ; la recette réelle relève de la 5.6. Le rendu effectif sur une vraie console Windows n'est vérifié que par un flux cp1252 simulé.
