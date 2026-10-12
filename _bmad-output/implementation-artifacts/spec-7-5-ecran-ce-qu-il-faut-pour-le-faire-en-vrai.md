---
title: "Story 7.5 : Écran « Ce qu'il faut pour le faire en vrai »"
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '54606dc337c096586a1501d82b44f500800b9c80'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-7-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-7-4-avant-apres.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** L'écran « Ce qu'il faut pour le faire en vrai » n'est qu'un emplacement (« Écran livré par la Story 7.5 »). La démo ne se conclut pas sur la demande d'outillage faite au Sponsor (Story 7.5, FR-43, FR-47, AD-11).

**Approach:** Un module `ui/outillage.py` lit la fiche `docs/fiche-outillage.md` de la Story 8.1 sous la racine de l'UI. L'écran l'affiche telle quelle en Markdown (lecture seule), avec une légende qui cite le fichier source. Aucun texte de la fiche n'est recopié dans `ui/`.

## Boundaries & Constraints

**Always:**
- **Source unique.** Le chemin est `racine / "docs" / "fiche-outillage.md"` (constante `FICHIER_FICHE = Path("docs/fiche-outillage.md")`), avec la même racine que les autres écrans (`racine_ui()` : `USINE_RACINE` ou répertoire courant). Le fichier est lu en UTF-8 à chaque affichage.
- **Lecture seule.** Le contenu est rendu par un seul `st.markdown` (aucun widget de saisie). La légende `st.caption` vaut « Fiche `docs/fiche-outillage.md` (Story 8.1), affichée en lecture seule. »
- **Fiche absente.** `st.warning(FICHE_ABSENTE)` nomme `docs/fiche-outillage.md` et la Story 8.1. Pas d'exception.
- **Fiche illisible** (`OSError`, `UnicodeDecodeError`). `st.error` « Lecture de la fiche outillage impossible : … ». Pas d'exception.
- **Racine introuvable.** Même message que les autres écrans (`_racine_introuvable`).
- **Navigation.** `Ecran.outillage` sort de `STORY_A_VENIR` (seul `Ecran.agent: "7.9"` reste). L'écran reste à un clic de la carte. Le bandeau Mode repli reste en tête. Le Mode repli ne change rien : la fiche est un fichier local.
- **Couches.** `ui/outillage.py` n'importe ni `ports`, ni `config`, ni `streamlit`. `app.py` n'importe pas `ports`.
- **Tests** par `streamlit.testing.v1.AppTest`. `racine_publiee` copie aussi `docs/fiche-outillage.md` du dépôt.

**Never:**
- Recopier dans `src/usine/ui/` une phrase, un titre ou une ligne de tableau de la fiche.
- Modifier `docs/`, `src/usine/contrats/`, `src/usine/ports/`, `pyproject.toml` ou `uv.lock`, ou écrire hors de `src/usine/ui/` et `tests/unit/ui/`.
- Transformer le contenu : pas de résumé, de découpage ni de chiffre dérivé.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Nominal | racine avec `docs/fiche-outillage.md` | un `st.markdown` égal au contenu du fichier, légende citant le fichier | N/A |
| Mode repli | idem + `USINE_MODE_REPLI=1` | bandeau en tête, même contenu | N/A |
| Fiche absente | pas de `docs/fiche-outillage.md` | avertissement `FICHE_ABSENTE`, aucun contenu | pas d'exception |
| Fiche illisible | octets non UTF-8 | `st.error` « Lecture de la fiche outillage impossible : … » | pas d'exception |
| Racine introuvable | `USINE_RACINE` absente | message « Racine introuvable » commun | pas d'exception |

</intent-contract>

## Code Map

- `docs/fiche-outillage.md` -- fiche de la Story 8.1 (lane L8, lecture seule) : titre « Ce qu'il faut pour le faire en vrai », demandes, tableau de correspondance.
- `src/usine/ui/navigation.py:22` -- `STORY_A_VENIR` : retirer `Ecran.outillage`.
- `src/usine/ui/app.py:67` -- `_racine_introuvable` (réutiliser). `app.py:191` -- `afficher_avant_apres` : modèle de l'écran. `app.py:375` -- `principal` : brancher `afficher_outillage(racine)`.
- `src/usine/ui/avant_apres.py` -- modèle de module pur (constantes de messages, `FICHIER_CONFIG`).
- `tests/unit/ui/conftest.py` -- `racine_publiee` : ajouter la copie de la fiche.
- `tests/unit/ui/test_app.py:131` -- `test_navigation` : branche outillage (contenu affiché, pas d'info).
- `tests/unit/ui/test_navigation.py:27` -- attendu de `STORY_A_VENIR`.

## Tasks & Acceptance

**Execution:**
- `src/usine/ui/outillage.py` -- `FICHIER_FICHE`, `FICHE_ABSENTE`, `LEGENDE`, `lire_fiche(racine) -> str | None` (`None` si absent ; laisse remonter `OSError` / `UnicodeDecodeError`).
- `src/usine/ui/navigation.py`, `src/usine/ui/app.py` -- `afficher_outillage(racine)` selon la matrice ; docstring de `app.py` mise à jour.
- `tests/unit/ui/conftest.py` -- copie de `docs/fiche-outillage.md` dans `racine_publiee`.
- `tests/unit/ui/test_outillage.py` -- `lire_fiche` (présent, absent) ; garde anti-duplication : aucune ligne non triviale de la fiche (titres, lignes de liste ou de tableau de plus de 20 caractères) n'apparaît dans un fichier de `src/usine/ui/`.
- `tests/unit/ui/test_app.py`, `test_navigation.py` -- matrice I/O par `AppTest`.

**Acceptance Criteria:**
- Given la fiche `docs/` de la Story 8.1, when le Pilote ouvre l'écran, then l'UI affiche son contenu en lecture seule, sans en dupliquer le texte dans `ui/`.
- Given le dépôt, when `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest -q`, then tout passe.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 19 findings — high 0, medium 0, low 13, false 6, maybe-false 0
- findings:
  - `[low]` `[patch]` (verification-gap) Branche `OSError` d'`afficher_outillage` non testée au niveau de la page — ajout de `test_outillage_fiche_inaccessible` (`PermissionError` simulée, erreur unique, ni fiche ni légende).
  - `[low]` `[patch]` (edge) Fiche enregistrée avec BOM : U+FEFF avant le premier titre — lecture en `utf-8-sig`, test `test_lire_fiche_avec_bom`.
  - `[low]` `[reject]` (edge) Fiche vide affichée sans avertissement — cas improbable (fiche versionnée de 8.1) ; ajouterait une branche.
  - `[false]` `[reject]` (edge) `$…$` et `:code:` interprétés par Streamlit — la fiche n'en contient aucun (grep) ; échapper transformerait le contenu, contraire à « telle quelle ».
  - `[false]` `[reject]` (edge) Fichier énorme ou FIFO bloquant la page — fichier versionné d'une page ; aucun chemin ne fait de `docs/fiche-outillage.md` un FIFO.
  - `[low]` `[patch]` (edge) `mkdir` sans `exist_ok` dans `racine_publiee` — `mkdir(exist_ok=True)`.
  - `[low]` `[reject]` (edge) Titre H1 exempté de la garde — libellé d'écran fixé par la Story 7.1, exemption documentée dans le test.
  - `[low]` `[patch]` (edge) Garde aveugle aux paragraphes — voir correctif de la garde ci-dessous.
  - `[low]` `[reject]` (intent) Fiche lue sous la racine d'exécution plutôt que dans le dépôt — en démo la racine est le clone (même hypothèse que `config/demo.yaml`, Story 7.4) ; un repli vers le dépôt ajouterait un second chemin de résolution.
  - `[low]` `[patch]` (intent) Garde plus étroite que « aucun texte dans `ui/` » — même correctif que la garde.
  - `[false]` `[reject]` (intent) « La démo se conclut » non traité — l'écran est déjà le dernier de `Ecran` (navigation inchangée) ; clause de justification.
  - `[low]` `[reject]` (blind) Titre affiché deux fois (sous-titre et H1 de la fiche) — cosmétique ; le sous-titre est commun à tous les écrans et la fiche ne doit pas être découpée.
  - `[low]` `[reject]` (blind) Fiche lue sous `USINE_RACINE` — doublon du rejet intent ci-dessus.
  - `[low]` `[reject]` (blind) Message « Racine introuvable » centré sur les Passages — message commun imposé par la spec, identique à l'avant / après.
  - `[low]` `[patch]` (blind) Garde : paragraphes, cellules, emphase, sous-répertoires et fichiers non `.py` ignorés — `_lignes_non_triviales` prend titres, éléments, paragraphes et chaque cellule sans marques ; parcours récursif de `ui/` (39 unités, 11 fichiers).
  - `[low]` `[patch]` (blind) `OSError` non testé au niveau de la page — doublon du premier correctif.
  - `[false]` `[reject]` (blind) Test Mode repli sans `not page.warning` — le bandeau Mode repli est lui-même un `st.warning` ; `_bandeau_en_tete` le vérifie.
  - `[false]` `[reject]` (blind) Égalité sur la source Markdown et non sur le rendu — l'écran transmet le fichier tel quel ; aucune construction ambiguë dans la fiche (voir rejet edge).
  - `[false]` `[reject]` (blind) Branche `elif` supprimée non détectée — `test_navigation` est paramétré sur tout `Ecran` : la chute vers `afficher_a_venir` lèverait `KeyError`, donc `page.exception`.

## Design Notes

**Racine plutôt que chemin du paquet.** La fiche se lit sous la racine de l'UI, comme `config/demo.yaml` (Story 7.4). En démo, la racine est le clone du dépôt. Un chemin calculé depuis `__file__` dépendrait de l'installation en mode éditable.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check .` -- expected: aucun écart.
- `uv run mypy` -- expected: aucune erreur.
- `uv run lint-imports` -- expected: tous les contrats KEPT.
- `uv run pytest -q tests/unit/ui` puis `uv run pytest -q` -- expected: tout vert.

## Auto Run Result

Status: done

- **Résumé.** L'écran « Ce qu'il faut pour le faire en vrai » affiche en lecture seule la fiche `docs/fiche-outillage.md` de la Story 8.1, lue sous la racine de l'UI et rendue telle quelle par un seul `st.markdown`, avec une légende citant le fichier. Fiche absente : avertissement ; fiche illisible : erreur ; racine introuvable : message commun. Aucun texte de la fiche n'est recopié dans `ui/`, ce que vérifie une garde de test.
- **Fichiers.**
  - `src/usine/ui/outillage.py` — chemin, messages, `lire_fiche` (UTF-8, BOM accepté).
  - `src/usine/ui/app.py` — `afficher_outillage`, branché dans `principal`.
  - `src/usine/ui/navigation.py` — l'outillage n'est plus un emplacement.
  - `tests/unit/ui/conftest.py` — copie de la fiche dans `racine_publiee`.
  - `tests/unit/ui/test_outillage.py` — lecture et garde anti-duplication (parcours récursif de `ui/`).
  - `tests/unit/ui/test_app.py`, `test_navigation.py` — matrice I/O par `AppTest`.
- **Revue (une passe, mode économique).** 19 constats : 7 lignes patchées (`low`, 4 correctifs : test `OSError` en page, BOM, `exist_ok`, garde élargie), 0 différé, 12 rejetés (6 `low`, 6 `false` ; motifs dans le Triage Log).
- **Revue de suivi recommandée :** non (aucun `high` ni `medium` patché).
- **Vérification.** `ruff check`, `ruff format --check`, `mypy`, `lint-imports` (aucun contrat cassé), `pytest -q` : 2185 passed, 1 skipped.
- **Risques résiduels.** Lancée avec `USINE_RACINE` hors du clone, la page affiche « Fiche absente ». Le titre apparaît deux fois (sous-titre de l'écran et H1 de la fiche).
