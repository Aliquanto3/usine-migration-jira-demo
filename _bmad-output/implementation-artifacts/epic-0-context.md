# Epic 0 Context: Walking skeleton (E0, sur `main`)

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Prouver l'architecture de bout en bout avant d'ouvrir les lanes parallèles : `usine rapport` publie un Passage complet sur un mini-jeu (2 Entités, ~30 tickets), avec un Excel à 1 onglet, un PowerPoint à 1 slide et une carte météo dans l'UI. Chaque couche (contrats, domaine, adaptateurs, Chaîne, consultation, rendu, passerelle LLM, UI) est traversée une fois, en tranche fine. L'epic fige aussi les contrats et ports (étiquette `contrats-v1`) sur lesquels les huit lanes coderont en worktrees. Critère de sortie : Passage publié de bout en bout, CI verte sous Windows et Linux, `CONTRATS_VERSION = 1.0.0`, étiquette posée. Stories séquentielles sur `main`.

## Stories

- Story 0.1: Socle du dépôt
- Story 0.2: Contrats v0 et ports
- Story 0.3: Mini-générateur déterministe
- Story 0.4: Calcul minimal de la Météo
- Story 0.5: Chaîne et Passage atomique
- Story 0.6: Consultation et rendu minimal
- Story 0.7: Passerelle LLM minimale
- Story 0.8: UI minimale
- Story 0.9: Gel des contrats v1

## Requirements & Constraints

- **Tests sans réseau** : aucun appel Jira ni LLM réel dans les tests unitaires ; marqueur `@pytest.mark.reseau` exclu par défaut et en CI ; `evaluation/` et `evals/` hors CI.
- **Dépôt public** : tout est fictif, aucun secret ; gitleaks en CI ; `.env.example` liste sans valeur `JIRA_EMAIL`, `JIRA_TOKEN_LECTURE`, `JIRA_TOKEN_INJECTION`, `JIRA_DC_PAT`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `USINE_CLE_PSEUDO`, `USINE_MODE_REPLI` ; `.env`, `donnees/` (sauf `donnees/corpus/`) et `sorties/` ignorés par git.
- **Lisibilité métier** : chaque clé des YAML livrés porte un commentaire en français (vérifié par test) ; toute erreur de configuration nomme fichier, clé et valeur.
- **Chiffres déterministes** : aucun KPI ni Météo calculé par un LLM ; reproductibilité par graine ; Rejeu idempotent hors liste nommée d'exclusions.
- **Performance** : mesurer `usine rapport` en Palier 1 sur un Journal synthétique à la volumétrie cible (5 000 Anomalies, 10 Entités, 8 semaines), consigner la durée par étape et le poste dans le README ; un écart à la cible de 5 minutes est signalé, pas bloquant.
- **Langue** : interface, rapports et messages en français.

## Technical Decisions

- **Hexagonal, composition unique** : seuls `composition.py` et les `cli.py` importent `usine.adaptateurs`. Domaine pur (pas d'I/O, ni `datetime.now`, ni `random` global : date et graine en paramètre). Le tableau des couches est recopié tel quel dans `[tool.importlinter]` (`layers` + `forbidden`) ; un test de non-régression prouve qu'importer `adaptateurs` depuis `domaine` casse la CI. `usine rapport` ne lit jamais `JIRA_TOKEN_INJECTION`.
- **Couches autorisées** : `contrats` (pydantic, polars, stdlib) ← `ports`, `domaine`, `config` ; `consultation` → contrats, ports ; `chaine` → + domaine, consultation ; `ia`, `rendu` → contrats, ports, consultation ; `adaptateurs`, `generateur` → contrats, ports ; `ui` → contrats, consultation, composition ; hors produit (`evaluation/`, `evals/`, `outils/`) → contrats, ports, domaine, composition.
- **Contrats d'abord** : toute forme inter-paquets ou inter-fichiers vit dans `usine.contrats` (modules `evenements`, `tickets`, `calcul`, `meteo`, `prevision`, `llm`, `agent`, `trace`, `passage`, `config`, plus `calendrier`, `format`, `versions`). Enregistrements = Pydantic `frozen=True` ; tables = `polars.DataFrame` validés par `contrats.valider(df, SCHEMA_X)` (erreur nommant schéma et colonne). Chaque fichier de Passage porte `contrats_version` ; relecture refusée si version majeure différente.
- **Ports** (`typing.Protocol`) : `SourceTickets`, `EntrepotExtraction`, `FournisseurLLM` (`generer_structure` et `executer_agent`, jamais combinés), `Pseudonymiseur`, `Consultation` (complet dès E0 : lectures de FR-17, FR-19, FR-26, FR-27, FR-39, FR-43 à FR-46, `url_ticket(cle)`, `dernier_passage()`, filtre `palier`), `Etape` (`executer(ctx: ContextePassage) -> ResultatEtape`).
- **Énumérations** : `Couleur` ordonnée `vert < jaune < orange < rouge` ; `Gravite` = bloquante, majeure, mineure ; `CodeIndicateur` IND-1…IND-8 ; `CauseRacine` (7 valeurs) ; `Champ` (statut, entite, vague, domaine, gravite, phase, titre, description, statut_test, statut_certification ; jamais `cause_racine`) ; `Etape` = `extraction, instantanes, kpi, meteo, prevision, classification, repartition_causes, explications, narration, rendu`.
- **Événement canonique** : `Evenement` (`id_evenement`, `cle_ticket`, `type_ticket`, `horodatage` UTC, `nature` ∈ {creation, transition, modification_champ, alignement}, `champ`, `de`, `vers`, `source`). Journal JSONL précédé d'un `EnteteJournal` ; identifiants Journal `J-<rang>` ; une création est suivie, au même horodatage, d'un `modification_champ` par attribut initial. Vérité terrain dans `donnees/verite_terrain.json`, jamais dans un `Evenement`.
- **Temps** : `contrats.calendrier` est la seule source (`jour_local` en Europe/Paris, `jour_ouvre_de` = premier Jour ouvré ≥ jour local, Fenêtre glissante, J-1, J-5, `semaine_programme`). Un Instantané en D inclut les événements dont `jour_ouvre_de` ≤ D.
- **Calcul** : en Polars, fonctions pures dans `domaine/` uniquement ; DuckDB stocke sans calculer ; rendu, UI et IA lisent via `Consultation`. Comptes entiers, taux en `numerateur`/`denominateur`, comparaisons en `Fraction` ; `statut` ∈ {evalue, non_evaluable} avec `motif`, jamais NaN/None.
- **Formatage et versions** : `contrats.format` (milliers à espace insécable, virgule décimale, %, dates). `version_grille` = SHA-256 de `grille_meteo.yaml` (12 hex) ; `version_prompt` = SHA-256 de `ia/prompts/<tache>.md` ; `version_modele` = `fournisseur:modele` ; `version_donnees` = SHA-256 du Journal + `horodatage_extraction`.
- **Passage** : construit dans `sorties/passages/.en-cours-<passage_id>/`, publié par un seul renommage vers `sorties/passages/<date_arrete>/<passage_id>/` ; en échec, déplacé sous `sorties/echecs/`, code non nul, étape nommée. `passage_id` = `AAAAMMJJTHHMMSSZ-<6 hex>`. Immuable ; dernier Passage = max `(date_arrete, horodatage_fin)` via `dernier_passage()`, sans pointeur mutable. Exclusions du Rejeu : `passage_id`, `horodatage_debut`, `horodatage_fin`, `horodatage_extraction`, `version_donnees` ; `docProps` fixés depuis la Date d'arrêté.
- **Chaîne** : registre `dict[Etape, ports.Etape]` construit par `composition.py` ; seule `chaine` (via `EcrivainPassage`) écrit dans le Passage, `rendu` renvoie des octets. Palier = `ConfigChaine.palier` ; en Palier 1 les étapes LLM sont `sautee`. Point d'entrée unique `usine rapport [--date-arrete AAAA-MM-JJ]`, date non ouvrée rejetée. Verrou `donnees/.verrou-passage`. Progression dans `sorties/progression/<passage_id>.jsonl` (hors Passage). Manifeste : durée par étape, drapeau `classification_initiale`, coût LLM.
- **Passerelle LLM** : ordre imposé Pseudonymisation → cache → `FournisseurLLM` → contrôle → ré-identification → `EntreeTrace`. `pydantic_ai` confiné à `adaptateurs/llm/`. Cache `donnees/cache_llm.sqlite` (WAL), clé `(tache, cible, date_arrete, version_prompt, version_modele, empreinte entrée pseudonymisée, tentative)`, réponse brute stockée avant contrôle, succès en cache recontrôlé et tracé `depuis_cache=true`. Jetons `<TYPE>_<6 hex HMAC-SHA256(USINE_CLE_PSEUDO, valeur)>` ; clés de ticket jamais pseudonymisées ; table `donnees/pseudonymes.sqlite` hors git. `controler_citations` retire la phrase fautive (`phrases_retirees`). Tests avec `FournisseurFactice` (`tests/doublures/`).
- **Configuration** : `config/*.yaml` validés par `contrats.config` dans `usine.config` seulement ; erreurs = `UsineErreur`. Secrets en variables d'environnement uniquement.
- **CLI et lanes** : application typer `usine` ; sous-applications enregistrées une fois dans `cli.py`, chacune depuis `<paquet>/cli.py`. Contrôle CI sur `lane/<n>-*` : fichiers modifiés limités aux répertoires de la lane. Propriété de `main` : `contrats/`, `ports/`, chargeur `config/`, `config/chaine.yaml`, `composition.py`, `cli.py`, `pyproject.toml`, `uv.lock`, `.github/`, `tests/conftest.py`, `tests/contrat/`, `tests/doublures/`.
- **Tests** : `tests/unit/` miroir de `src/usine/`, `tests/contrat/<port>/` (suites paramétrées par adaptateur), `tests/doublures/`, `tests/fixtures/`.
- **Conventions** : identifiants français en snake_case sans accents, classes en PascalCase ; exceptions dérivées de `UsineErreur`, aucune exception muette ; `logging` standard en français.
- **Stack figée** : Python 3.12, uv, pydantic 2.14.0, pydantic-settings 2.15.0, polars 1.44.2, duckdb 1.5.6, numpy 2.4.6, pyarrow 25.0.1, pyyaml 6.0.3, typer 0.27.3, httpx 0.28.1, pydantic-ai-slim 2.55.0 (anthropic, mistral), presidio 2.2.364, spacy 3.8.16 + `fr_core_news_md` 3.8.0 (roue GitHub par URL), openpyxl 3.1.5, python-pptx 1.0.2, streamlit 1.65.0, pytest 9.1.1, ruff 0.17.0, mypy 2.4.0, import-linter 2.15, time-machine 3.5.1, gitleaks v8.30.1. CI GitHub Actions Windows + Linux : ruff, mypy, import-linter, pytest, gitleaks.

## UX & Interaction Patterns

- UI Streamlit minimale : carte météo du dernier Passage (une ligne par Entité et sa couleur), lue via `Consultation` uniquement.
- Lancement de la Chaîne : l'UI démarre `usine rapport` en sous-processus et affiche chaque `Etape` en lisant le fichier de progression en ouvrir-lire-fermer ; elle n'ouvre jamais `entrepot.duckdb` ni un répertoire `.en-cours-*`.
- Bandeau « Mode repli » permanent quand `USINE_MODE_REPLI=1` (activation jamais automatique).
- Rendu : Excel avec un onglet Synthèse (une ligne par Entité et sa Météo) et PowerPoint à 1 slide carte météo sur le gabarit neutre fictif `gabarits/rapport.pptx`. Fichiers `rapport-AAAA-MM-JJ.xlsx` / `.pptx`. Chaque clé de ticket affichée est un lien construit par `consultation.url_ticket(cle)`.

## Cross-Story Dependencies

- Ordre strict 0.1 → 0.9 sur `main` : 0.2 (contrats, ports, doublures) précède toute story de code ; 0.3 fournit le Journal consommé par 0.4 ; 0.4 alimente la Chaîne de 0.5 ; 0.6 et 0.7 s'enregistrent comme étapes dans le registre de 0.5 ; 0.8 lit les Passages publiés et la progression de 0.5/0.6 ; 0.9 exige 0.1 à 0.8 terminées.
- Après `contrats-v1`, les branches `lane/1-donnees` à `lane/8-portage` partent de l'étiquette (une par worktree, `donnees/` et `.env` propres). Les tranches amorcées ici (Journal, Instantané, Météo IND-1, Chaîne, rendu, Explication sourcée, UI) sont terminées dans les lanes L1 à L7 ; toute modification ultérieure de `contrats/` ou `ports/` passe par une PR dédiée sur `main` qui incrémente `CONTRATS_VERSION`.
