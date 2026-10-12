---
title: 'Story 1.9 : Corpus de textes définitif par LLM'
type: 'feature'
created: '2026-10-13'
status: 'done'
baseline_revision: 'e9750889269a009726815960074faf1f4ae47947'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** `outils/generer_corpus.py` n'écrit que le Corpus provisoire (« adaptateurs LLM à la Story 6.1 ») : impossible de produire le Corpus définitif par un vrai LLM, et le garde-fou d'AD-19 (modèle de classification ≠ `modele_corpus`) n'existe nulle part.

**Approach:** l'outil accepte un fournisseur et un modèle choisis, estime le coût d'après le registre des prix avant tout appel, refuse au-delà d'un plafond ou si le modèle est celui de la classification, puis produit le Corpus par le `FournisseurLLM` réel construit par la composition. `usine.config` porte le garde-fou, appliqué au chargement de `config/llm.yaml` par la composition.

## Boundaries & Constraints

**Always:** `outils/` n'importe que `usine.composition`, `usine.contrats`, `usine.ports` (contrat import-linter « hors produit ») ; aucun SDK importé hors `adaptateurs/llm` ; aucun appel réel dans les tests (doublures `tests/doublures/fournisseur_factice.py` ou `monkeypatch` de `composition.construire_fournisseur`) ; messages d'erreur en français nommant fichier, clé et valeurs ; la clé API se lit par `charger_secrets(racine)` (jamais d'affichage de secret) ; `--provisoire` garde son comportement actuel.

**Never:** modifier `contrats/` ou `ports/` ; changer le format du Corpus, les prompts ou `produire_corpus` ; lire `.env` dans les tests ; appeler le LLM depuis la génération du Journal ; réinjecter Jira.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Estimation | `--fournisseur mistral --modele mistral-medium-latest --estimer` | affiche nombre d'appels (`(nb_domaines+1)*8+1`) et coût estimé majoré en €, code 0, aucun appel ni fournisseur construit | — |
| Génération | `--fournisseur F --modele M` (doublure) | Corpus écrit avec `modele_corpus == "F:M"`, version `llm-1` par défaut ; affiche jetons réels entrée/sortie et coût estimé réel (registre) | — |
| Plafond | estimation > `--plafond-eur` (défaut 2.00) | code 1, message nommant estimation et plafond, aucun fournisseur construit | `UsineErreur` |
| Garde-fou outil | `F:M` égal au modèle de classification de `config/llm.yaml` | code 1 avant tout appel, message nommant les deux valeurs | `UsineErreur` |
| Modèle hors registre | `--modele inconnu` | code 1, message du registre listant les modèles connus | `UsineErreur` |
| Arguments | ni `--provisoire` ni couple fournisseur/modèle, ou un seul des deux | code 1 (ou erreur argparse), message explicite | — |
| Garde-fou config | `config/llm.yaml` dont la classification (`modeles_par_tache.classification`, sinon `modele`) donne `F:M` = `modele_corpus` du Corpus de `donnees/corpus/textes.json` | chargement refusé, message nommant les deux valeurs et les fichiers | `UsineErreur` |
| Corpus absent / provisoire | pas de `textes.json`, ou `gabarits-provisoires` | chargement accepté | — |

</intent-contract>

## Code Map

- `outils/generer_corpus.py` -- CLI à étendre : `generer(...)`, `main(...)` ; message « arrivent à la Story 6.1 » à retirer ; docstring = documentation de la commande et du coût.
- `src/usine/composition.py:295` `construire_fournisseur(racine, secrets_usine)` -- ajouter des surcharges mot-clé `fournisseur`/`modele` (via `config.model_copy(update=...)`, comme `construire_fournisseurs_par_tache:316`) ; si `config/llm.yaml` est absent avec surcharge, partir d'un `ConfigLLM` minimal valide.
- `src/usine/composition.py:232` `_tarif_registre` / `usine.adaptateurs.llm.cout_estime_eur`, `tarif` -- registre des prix (import différé, comme `_tarif_registre`) ; `tarif()` lève l'erreur « hors registre ».
- `src/usine/composition.py:471` `_config_llm(racine)` -- point d'application du garde-fou (lit `racine/donnees/corpus/textes.json` s'il existe, via `generateur.corpus.charger_corpus` ou lecture de la seule clé `modele_corpus`).
- `src/usine/composition.py:825` `generer_corpus(...)` -- délégation à `generateur.corpus.produire_corpus` ; y ajouter (ou à côté) une fonction d'estimation `estimer_corpus(version_modele, domaines) -> (appels, cout_eur)` et le comptage des jetons réels (enveloppe de comptage du `FournisseurLLM` autour de `generer_structure`, ou retour enrichi).
- `src/usine/generateur/corpus.py` -- `TEXTES_PAR_CASE`, `MAX_JETONS_CASE=2000`, `_prompt_anomalie`, `_prompt_cas_de_test`, `_prompt_certifications`, `produire_corpus` (lecture seule ; on peut ajouter une fonction publique listant les prompts dans l'ordre des appels pour l'estimation, sans changer leur contenu).
- `src/usine/config/chargeur.py` + `src/usine/config/__init__.py` -- nouvelle fonction `verifier_modele_corpus(config: ConfigLLM, modele_corpus: str)` (garde-fou AD-19), exportée.
- `src/usine/contrats/versions.py` `version_modele(fournisseur, modele)` ; `src/usine/contrats/llm.py` `Tache.classification`, `ReponseStructuree.jetons_entree/jetons_sortie`.
- `src/usine/adaptateurs/llm/registre.py` -- prix (lecture seule).
- `tests/unit/outils/test_generer_corpus.py`, `tests/unit/config/`, `tests/unit/test_composition_llm.py`, `tests/doublures/fournisseur_factice.py` -- tests et doublures existants à étendre.

## Tasks & Acceptance

**Execution:**
- `src/usine/config/chargeur.py`, `src/usine/config/__init__.py` -- ajouter et exporter `verifier_modele_corpus` -- garde-fou AD-19 (AC3).
- `src/usine/composition.py` -- surcharges de `construire_fournisseur` ; garde-fou appliqué dans `_config_llm` ; estimation du coût ; génération LLM renvoyant aussi jetons réels et coût estimé réel -- seul point qui touche registre et adaptateurs.
- `outils/generer_corpus.py` -- options `--fournisseur`, `--modele`, `--estimer`, `--plafond-eur` (Decimal, défaut 2.00) ; ordre : registre → garde-fou classification → estimation/plafond → construction → génération → bilan ; docstring avec la commande type et l'estimation -- AC1.
- `tests/unit/outils/test_generer_corpus.py`, `tests/unit/config/test_chargeur.py` (ou fichier existant équivalent), `tests/unit/test_composition_llm.py` -- couvrir chaque ligne de la matrice, sans réseau ni `.env`.

**Acceptance Criteria:**
- Given les adaptateurs LLM de la Story 6.1, when l'auteur lance l'outil avec un fournisseur et un modèle choisis, then le Corpus est écrit dans `donnees/corpus/` avec `modele_corpus` égal à ce `fournisseur:modele`.
- Given une configuration où le modèle de classification égale `modele_corpus`, when la composition charge `config/llm.yaml`, then elle est refusée avec un message nommant les deux valeurs.
- Given la suite complète, when `uv run pytest -q` tourne, then aucun appel réseau n'est émis et tout passe.

## Design Notes

Modèle retenu pour le Corpus définitif : `mistral:mistral-medium-latest` (offre gratuite « Experiment », coût réel nul, coût estimé faible ; fournisseur distinct de la classification `anthropic:claude-haiku-5-5`, ce que le garde-fou impose — Haiku 5.5 est exclu). Estimation majorée : jetons d'entrée ≈ `len(prompt)/3 + 500` (schéma), jetons de sortie = `MAX_JETONS_CASE` par appel. La génération réelle est lancée hors de cette implémentation, par l'orchestrateur, depuis le dépôt principal.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports` -- expected: aucun écart.
- `uv run pytest -q` -- expected: tout passe.
- `uv run python outils/generer_corpus.py --fournisseur mistral --modele mistral-medium-latest --estimer` -- expected: 57 appels, estimation ≤ 2 €, aucun appel.

## Auto Run Result

- **Résumé** : outil `outils/generer_corpus.py --fournisseur F --modele M [--estimer] [--plafond-eur]` ; garde-fou AD-19 dans `usine.config` appliqué au chargement de `config/llm.yaml` ; `composition.generer_journal` lit désormais le Corpus versionné (comme `usine generer`).
- **Génération réelle** (une fois, depuis le dépôt principal) : `mistral:mistral-medium-latest` (Haiku 5.5 exclu : c'est le modèle de classification) ; estimation majorée 0,2253 € ; bilan 57 appels, 24 200 jetons d'entrée, 20 588 de sortie, coût estimé réel 0,0468 €, coût facturé nul (offre gratuite « Experiment »). 342 paires, `version_corpus: llm-1`.
- **Vérification** : ruff, format, mypy, lint-imports (14 contrats) verts ; `pytest -q` vert ; `pytest -m lent` (calage 1.8, volumétrie, recette 5.6, recette 4.5, contrats de consultation) vert avec le nouveau Corpus. Trois tests qui figeaient le Corpus provisoire comme versionné ont été réécrits.
- **Écart** : `DEMO` (Jira) porte encore les textes du Corpus provisoire ; le Journal régénéré porte ceux du Corpus définitif. Jira non réinjecté (consigne).
- **Hors lane** : `src/usine/composition.py`, `src/usine/config/` et leurs tests.
