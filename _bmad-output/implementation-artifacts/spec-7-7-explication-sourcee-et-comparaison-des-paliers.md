---
title: 'Story 7.7 : Explication sourcée à l''écran et comparaison des Paliers'
type: 'feature'
created: '2026-10-13'
status: 'done'
baseline_revision: 'b00c5d7da2466e614fbf422b7f676c21fa4842d8'
review_loop_iteration: 1
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-7-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-7-6-mode-repli-sur-un-passage-enregistre.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** Le détail d'Entité affiche en Palier 2 un simple emplacement (« Explication sourcée : Story 7.7 ») : ni l'Explication sourcée, ni ses Citations, ni la narration de la Prévision (Story 6.7, report), ni le nombre de phrases retirées (Story 6.6, report). Aucun moyen de comparer Palier 1 et Palier 2, ni de montrer la Pseudonymisation (FR-43, FR-46, FR-31, FR-32 ; AD-11, AD-15).

**Approach:** Le détail lit `explications` et `narrations` de `Consultation` avec le filtre `palier` choisi par un sélecteur (offert seulement pour un Passage Palier 2). Un nouvel écran « Pseudonymisation » montre côte à côte une description et son `Pseudonymiseur.apercu`, construit par la composition sans écrire la table.

## Boundaries & Constraints

**Always:** chaque clé citée passe par `liens.lien_ticket` + `consultation.url_ticket` (texte simple en Mode repli) ; aucun chiffre calculé par l'UI (le nombre de phrases retirées vient de `SortieExplication.phrases_retirees`) ; la narration ne remplace la Prévision brute que si `statut_controle` vaut `conforme` ou `corrige` ; en Palier 1 choisi, aucune sortie LLM n'est lue (`palier=1`) et la zone porte `EXPLICATION_PALIER_1` ; `LectureDetail` reste aligné sur `Consultation` (test de signatures) ; l'aperçu est local, sans fournisseur LLM ni écriture de `donnees/pseudonymes.sqlite`.

**Never:** modifier `contrats/` ou `ports/` ; importer `ports` ou `adaptateurs` depuis `ui/app.py`/`ui/detail.py` ; appel LLM réel ; lecture de `.env` dans les tests (variables via `monkeypatch`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Palier 2, Entité rouge | `SortieExplication` (2 citations, `phrases_retirees=1`) | texte avec clés en liens, liste « Citations », « Phrases retirées au contrôle : 1 » | — |
| Palier 2, pas d'Explication pour l'Entité | `explications()` vide | `EXPLICATION_ABSENTE` | — |
| Explication rejetée | `statut_controle=rejete` | texte de remplacement affiché tel quel, statut indiqué | — |
| Narration conforme / corrigée | `SortieNarration` de l'Entité | remplace le bloc Prévision brute, mention « narration contrôlée » | — |
| Narration rejetée ou absente | — | Prévision brute | — |
| Sélecteur sur Palier 1 | Passage Palier 2 | `EXPLICATION_PALIER_1`, Prévision brute | — |
| Passage Palier 1 | `manifeste.palier=1` | pas de sélecteur, Palier 1 | — |
| Mode repli | `url_ticket` → `None` | clés en texte simple | — |
| Aperçu sans clé | `USINE_CLE_PSEUDO` absente | message d'erreur nommant la variable | `UsineErreur` affichée |
| Aucune description | `textes_tickets()` sans description non vide | message « aucune description » | — |

</intent-contract>

## Code Map

- `src/usine/ui/detail.py` -- `LectureDetail` (+ `explications`, `narrations`, annotation `Literal[1, 2]` égale à `ports.consultation.Palier`) ; `texte_prevision` (+ narrations) ; `texte_explication(palier)` à refondre ; supprimer `EXPLICATION_PALIER_2`.
- `src/usine/ui/liens.py:23` -- `lien_ticket`, `echapper_markdown` : réutilisés pour lier les clés dans le texte.
- `src/usine/ui/app.py:187` -- `afficher_detail` : sélecteur de Palier, lectures `palier=` ; `principal` : nouvel écran.
- `src/usine/ui/navigation.py` -- `Ecran` (+ `pseudonymisation`), clé `CLE_PALIER`.
- `src/usine/ui/cli.py` -- service `apercu_pseudonymisation(racine)` (couche de composition de la lane).
- `src/usine/composition.py:227,799` -- `_moteur_pseudonymisation`, `_pseudonymiseur` ; ajouter `apercu_pseudonymisation(racine)` public, table en mémoire en lecture seule.
- `src/usine/consultation/passage.py:519-532` -- `explications`, `narrations`, filtre `palier` (lecture seule).
- `src/usine/contrats/llm.py:36,223,235` -- `StatutControle`, `SortieExplication`, `SortieNarration` (lecture seule).
- `tests/unit/ui/test_detail.py:48` -- `METHODES` ; `tests/unit/ui/test_app.py:255,467` -- `_Doublure`, `test_detail_palier_2`.

## Tasks & Acceptance

**Execution:**
- `src/usine/ui/detail.py` -- fonctions pures `texte_explication(palier, explications, url_ticket)` et narration dans `texte_prevision` -- logique testable sans Streamlit.
- `src/usine/composition.py` -- `apercu_pseudonymisation(racine) -> Callable[[str], str]` -- AD-15 : l'UI ne voit que l'aperçu.
- `src/usine/ui/cli.py`, `navigation.py`, `app.py` -- sélecteur, écran Pseudonymisation (deux colonnes, `st.text`).
- `tests/unit/ui/test_detail.py`, `test_app.py`, `test_navigation.py`, `tests/unit/test_composition*.py` -- matrice ci-dessus.

**Acceptance Criteria:**
- Given un Passage Palier 2 et une Entité rouge, when le Pilote ouvre son détail, then l'Explication s'affiche, chaque Citation est un lien Jira et le nombre de phrases retirées est indiqué, et la narration contrôlée remplace la Prévision brute.
- Given le sélecteur de Palier, when le Pilote choisit Palier 1, then la même Entité s'affiche sans aucune sortie LLM.
- Given l'écran Pseudonymisation, when le Pilote choisit une description, then l'original et la version pseudonymisée s'affichent côte à côte via `Pseudonymiseur.apercu`.

## Spec Change Log

## Review Triage Log

## Design Notes

**Liens dans le texte.** Le texte est découpé sur les clés de `citations` (bornes `(?<![\w-])CLE(?![\w-])`, plus longues d'abord) ; les morceaux hors clé sont échappés, les clés passent par `lien_ticket`. Une liste « Citations » suit, pour qu'une clé absente du texte reste visible.

**Table en mémoire.** `apercu` n'écrit pas la table, mais le constructeur en exige une : la composition passe une table vide qui refuse `enregistrer`, ce qui évite de créer `donnees/pseudonymes.sqlite` sur un clone frais.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert.

## Auto Run Result

- **Livré** : Explication sourcée à l'écran (texte avec clés en liens, Citations, phrases retirées, statut), narration contrôlée de la Prévision, sélecteur de Palier sur un Passage Palier 2, écran Pseudonymisation côte à côte via `composition.apercu_pseudonymisation` (table en mémoire qui refuse toute écriture, clé jamais affichée). Contrôles verts : ruff, mypy, lint-imports, 2633 tests.
- **Revue** (une passe Edge Case Hunter) : aucun constat medium/high. Notés : moteur Presidio reconstruit à chaque rendu de l'écran Pseudonymisation (lenteur, pas de cache) ; une erreur hors `UsineErreur` (ex. import Presidio) n'est pas interceptée par l'écran.
- **Reports** : sélecteur Palier 2 non vu sur un vrai Passage Palier 2 ; Brouillon de commentaire (`brouillon_commentaire`) non affiché.
