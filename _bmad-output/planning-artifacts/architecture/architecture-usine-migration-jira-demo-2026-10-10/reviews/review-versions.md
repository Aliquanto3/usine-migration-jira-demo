---
title: 'Revue : versions et décisions techniques du spine'
lens: 'vérification des versions et confrontation à la réalité'
target: ARCHITECTURE-SPINE.md
date: '2026-10-10'
verdict: 'à corriger avant E0-1 : deux conflits de résolution bloquants, un risque de verrou DuckDB'
---

# Revue : versions et décisions techniques du spine

## Verdict

Les versions du tableau *Stack* existent toutes sur PyPI ou GitHub, et aucune n'est retirée (yanked). Elles sont toutes compatibles avec Python 3.12 (`requires_python` lu). **En revanche, l'ensemble ne se résout pas.** `uv pip compile` (uv 0.12.23, Python 3.12, `x86_64-pc-windows-msvc`) échoue sur deux conflits de dépendances transitives que ni la recherche ni le spine n'ont vus, parce qu'ils ont contrôlé chaque paquet isolément. Il faut aussi revoir un point de conception : le verrou de fichier DuckDB entre l'UI et la CLI lancée en sous-processus.

## Méthode

- Lecture de `research.md` (§ 7), de `.memlog.md` et du tableau *Stack*.
- API JSON de PyPI pour chaque paquet épinglé : existence de la version, date, `requires_python`, `yanked`, `requires_dist`, dernière version.
- **Résolution réelle** de la pile complète avec `uv pip compile`, puis avec `--only-binary :all:` pour vérifier qu'il existe des roues Windows cp312.
- API GitHub pour llama.cpp, gitleaks et uv. `compatibility.json` et `meta/fr_core_news_md-3.8.0.json` de `explosion/spacy-models`.
- Documentation officielle : sorties et tests de Pydantic AI, contrats d'import-linter, transactions et concurrence de DuckDB, `st.fragment` de Streamlit.

## Constats à corriger

### V-1 (bloquant) : numpy 2.5.4 incompatible avec presidio-analyzer 2.2.364

`presidio-analyzer==2.2.364` déclare `numpy>=1.19.0,<2.5.0`. Message de uv : *« presidio-analyzer>=2.2.364 depends on numpy>=1.19.0,<2.5.0 and you require numpy==2.5.4 »*. Par ailleurs, numpy 2.5.4 a été publié **le jour même** (2026-10-10).
**Correction :** épingler `numpy 2.4.6`, la version choisie par le résolveur et compatible avec shap 0.53 (numpy ≥ 2), scikit-learn, lightgbm, polars et thinc. Remonter à 2.5.x quand Presidio relèvera sa borne, lors de la revérification du 2026-11-01.

### V-2 (bloquant) : pyarrow 26.0.0 incompatible avec streamlit 1.65.0

`streamlit==1.65.0` déclare `pyarrow!=25.0.0,<26,>=7.0`. pyarrow 26.0.0 a été publié le 2026-10-09.
**Correction :** épingler `pyarrow 25.0.1`, la version retenue par le résolveur. Note : streamlit 1.65 tire aussi **pandas 3.0.6** en dépendance transitive. Ce n'est pas bloquant, puisque le domaine reste en Polars, mais pandas apparaîtra dans `uv.lock`.

Avec ces deux corrections, toute la pile se résout, avec des roues binaires pour Windows et Python 3.12 (anthropic 1.13.0, mistralai 3.2.0, thinc 8.3.13, grimp 3.17, pydantic-core 2.50.0).

### V-3 (majeur, conception) : verrou DuckDB entre le processus Streamlit et la CLI en sous-processus

D'après la documentation DuckDB (*Concurrency*), un seul processus peut ouvrir un fichier en lecture-écriture. Plusieurs processus ne peuvent l'ouvrir ensemble qu'en `READ_ONLY`, et aucun d'eux n'écrit alors. L'écriture multi-processus passe par Quack, en bêta depuis 1.5.2, ou par DuckLake.
Or `ui` importe `composition`, et donc `ia`. L'Agent tourne dans le processus Streamlit et passe par `ia.passerelle`, qui lit et écrit `cache_llm.duckdb` et `pseudonymes.duckdb` (AD-12, AD-15). Au même moment, `usine rapport`, lancé par l'UI en sous-processus (AD-8, H-28), écrit dans les mêmes fichiers pendant les étapes LLM. Résultat attendu : une erreur de verrou (« Could not set lock on file ») si l'utilisateur interroge l'Agent pendant un Passage de Palier 2.
**Correction à décider dans AD-12, AD-15 ou AD-8 :**
- soit ouvrir les connexions brièvement, par appel, avec une reprise courte sur erreur de verrou ;
- soit interdire l'Agent pendant un Passage en cours, ce qui est simple pour une démo ;
- soit séparer le cache et la table de pseudonymes de l'Agent, ce qui demande d'expliquer la stabilité des pseudonymes ;
- soit passer ces deux tables en SQLite (mode WAL), qui accepte plusieurs processus.

`entrepot.duckdb` n'est pas concerné : seule l'étape `extraction` l'ouvre (AD-6), et l'UI lit les Passages par `Consultation`, sur des fichiers Parquet et JSON.

### V-4 (mineur) : `spacy validate` peut être retiré des réserves

D'après `compatibility.json` et `meta/fr_core_news_md-3.8.0.json` (`spacy_version: ">=3.8.0,<3.9.0"`), `fr_core_news_md 3.8.0` est **le seul modèle de la série 3.8** et il couvre spacy 3.8.16. La mention « compatibilité à confirmer » peut devenir « vérifiée ».
**Provenance :** un paquet `fr-core-news-md 3.8.0` existe aussi sur PyPI (auteur « Explosion », publié le 2025-09-30), mais **sans `requires_dist`**, alors que la release GitHub date du 2024-09-30. Choisir explicitement la source dans `pyproject.toml` : l'URL de la roue GitHub via `[tool.uv.sources]`, ou PyPI après vérification de l'empreinte par rapport à la release GitHub.

## Constats à noter (pas de changement obligatoire)

- **N-1, versions très fraîches.** Plusieurs versions épinglées ont moins de 72 h : uv 0.13.0 (2026-10-09), pyarrow 26.0.0, ruff 0.17.0, pydantic-ai 2.55.0 (2026-10-09), pydantic 2.14.0 (2026-10-08), numpy 2.5.4 et llama.cpp b11552 (2026-10-10, build du jour). Elles sont valides, mais n'ont pas encore de retour d'usage. Suggestion : un délai de carence dans uv (`exclude-newer`, avec une date fixe ; la syntaxe relative est à vérifier dans uv 0.13), et un tag llama.cpp vieux de quelques jours pour le bonus FR-37. Pour uv, déclarer `required-version` dans `[tool.uv]`, puisque le poste est en 0.12.23.
- **N-2, polars 1.44.2.** Cette version existe (2026-09-09). Le spine a raison et la recherche (§ 7, « 1.44.0 est la dernière 1.x ») est inexacte : les versions 1.44.1 et 1.44.2 existent. Il faut corriger la recherche, pas le spine.
- **N-3, Pydantic AI.** Vérifié dans la documentation officielle :
  - `ToolOutput`, `NativeOutput` et `PromptedOutput` existent, et Tool Output est le mode par défaut ;
  - `TestModel` (`pydantic_ai.models.test`), `FunctionModel`, `Agent.override` et `models.ALLOW_MODEL_REQUESTS = False` existent ;
  - les extras `anthropic` et `mistral` existent dans `pydantic-ai-slim 2.55.0`, qui requiert anthropic ≥ 1.12.1, mistralai ≥ 2.9.2 et pydantic ≥ 2.12.

  Deux précisions pour AD-13 :
  - En mode Tool Output, le schéma *est* un outil. Pour que `executer_agent` respecte « jamais schéma et outils dans le même appel », l'agent doit avoir `output_type=str`. Sinon Pydantic AI mêle outil de sortie et outils de fonction, avec la règle `end_strategy`.
  - Si `FournisseurFactice` s'appuie sur `TestModel`, il importe `pydantic_ai` : il doit donc vivre sous `adaptateurs/llm/` ou dans `tests/`, sous peine d'enfreindre AD-12.
- **N-4, import-linter 2.15.** La configuration dans `pyproject.toml` se fait par `[tool.importlinter]` et `[[tool.importlinter.contracts]]` (documentation TOML). Les types de contrat sont `forbidden`, `protected`, `layers`, `independence` et `acyclic_siblings`.
  - Il n'existe **pas** de contrat en liste blanche : la phrase « toute importation absente du diagramme est interdite » se traduit par un contrat `layers` et une série de contrats `forbidden`. `protected` correspond exactement à AD-1 (`usine.adaptateurs` importable seulement par `composition` et `cli`).
  - Pour « `pydantic_ai` seulement dans `adaptateurs/llm` », il faut `include_external_packages = true`.
  - `evaluation/`, à la racine du dépôt, doit être déclaré dans `root_packages`.
- **N-5, DuckDB et AD-6.** `BEGIN TRANSACTION` / `COMMIT` / `ROLLBACK` sont ACID, avec isolation par instantané : la transaction unique tickets + repère est réalisable telle qu'écrite.
- **N-6, Streamlit et AD-8.** `st.fragment(run_every=...)` existe dans la documentation actuelle. Il convient pour suivre `progression.jsonl` sans recharger la page. Il faut garder le `Popen` dans `st.session_state`, car un rerun ne doit pas relancer la CLI. Sous Windows, prévoir `creationflags=CREATE_NEW_PROCESS_GROUP` pour pouvoir l'interrompre.
- **N-7, autres paquets.** Leur existence, leur `requires_python` (compatible 3.12) et leurs roues Windows ont été vérifiés : typer 0.27.3, time-machine 3.5.1, duckdb 1.5.6, pydantic-settings 2.15.0 (qui requiert pydantic ≥ 2.7), httpx 0.28.1, pyyaml 6.0.3, openpyxl 3.1.5, python-pptx 1.0.2, scikit-learn 1.9.1 (≥ 3.11), lightgbm 4.7.0, pymongo 4.18.3, langfuse 4.17.0, pytest 9.1.1, ruff 0.17.0, mypy 2.4.0 et presidio-anonymizer 2.2.364. gitleaks v8.30.1 est toujours la dernière version (2026-03-21) ; gitleaks-action est en v3.0.0.
- **N-8, chiffres de la recherche.** Le § 7 de la recherche affirme que « Python 3.12 est compatible avec toute la pile ». C'est vrai paquet par paquet, mais faux pour l'ensemble (V-1, V-2). À l'avenir, la vérification des versions doit inclure une résolution complète (`uv pip compile`), pas seulement des lectures de `requires_python`.

## Tableau corrigé proposé (lignes modifiées seulement)

| Nom | Spine | Proposé | Motif |
| --- | --- | --- | --- |
| numpy | 2.5.4 | 2.4.6 | presidio-analyzer : `numpy<2.5.0` |
| pyarrow | 26.0.0 | 25.0.1 | streamlit 1.65.0 : `pyarrow<26` |
| spacy / fr_core_news_md | « à confirmer » | 3.8.16 / 3.8.0, vérifiée | `spacy_version >=3.8.0,<3.9.0` |
| (nouveau, transitif) pandas | — | 3.0.6 (via streamlit) | à mentionner pour mémoire |
