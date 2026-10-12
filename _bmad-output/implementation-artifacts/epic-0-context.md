# Epic 0 Context: Walking skeleton (E0, sur `main`)

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

`usine rapport` publie de bout en bout un Passage sur un mini-jeu de données (Excel à 1 onglet, PowerPoint à 1 slide, carte météo dans l'UI), chaque couche étant traversée une fois. La CI est verte sous Windows et Linux et l'étiquette git `contrats-v1` est posée, ce qui permet d'ouvrir les lanes parallèles (L1 à L8, en worktrees) sur des contrats et ports figés. Stories séquentielles sur `main`.

## Stories

- Story 0.1: Socle du dépôt (E0-1)
- Story 0.2: Contrats v0 et ports (E0-2)
- Story 0.3: Mini-générateur déterministe (E0-3)
- Story 0.4: Calcul minimal de la Météo (E0-4)
- Story 0.5: Chaîne et Passage atomique (E0-5)
- Story 0.6: Consultation et rendu minimal (E0-6)
- Story 0.7: Passerelle LLM minimale (E0-7)
- Story 0.8: UI minimale (E0-8)
- Story 0.9: Gel des contrats v1 (E0-9)

## Requirements & Constraints

- Tranches fines des exigences terminées plus tard dans les lanes : chargement de la Météo et des Indicateurs, rapport Excel/PowerPoint, Explication sourcée, carte météo et lancement de la Chaîne dans l'UI.
- Aucun chiffre (KPI, Météo, Prévision) calculé par un LLM ; les sorties LLM ne reprennent que des valeurs calculées.
- Reproductibilité : données par graine, Rejeu idempotent (mêmes valeurs de cellules, textes de slides et `docProps` hors exclusions nommées).
- Dépôt public : tout fictif, aucun secret, contrôle de secrets en CI (gitleaks) ; aucun identifiant sensible en clair dans journaux et traces.
- Tests sans réseau ni appel LLM/Jira réel (marqueur `reseau` exclu par défaut) ; CI Windows + Linux : ruff, mypy, import-linter, pytest, gitleaks.
- Chaque clé de YAML commentée en français (test) ; erreurs `UsineErreur` nommant fichier, clé, valeur. Interface, Rapport et sorties LLM en français.
- Performance : durée par étape consignée dans le README sur la volumétrie cible (cible Palier 1 < 5 min, écart signalé sans bloquer).
- Date d'arrêté : jour ouvré uniquement ; un second `usine rapport` simultané échoue en nommant le verrou.

## Technical Decisions

- Architecture hexagonale autour d'une chaîne pipes-and-filters ; domaine pur (sans I/O, horloge ni hasard) en Polars ; racine de composition unique (`composition.py`) ; `import-linter` impose le tableau des couches.
- Contract-first : toute forme inter-paquets dans `usine.contrats` (Pydantic `frozen` ou schémas Polars validés par `valider()`), ports en `typing.Protocol` dans `usine.ports` ; `contrats_version` dans chaque fichier, `CONTRATS_VERSION` = 1.0.0 au gel ; `contrats/` et `ports/` modifiables seulement sur `main` par PR dédiée.
- Événement canonique unique `Evenement` (identifiants `J-<rang>`, dédoublonnage), Journal JSONL précédé d'un `EnteteJournal` ; vocabulaire canonique (`Champ`, domaines de valeurs) dans `contrats.tickets` ; vérité terrain hors `Evenement`.
- `contrats.calendrier` seule source du temps (Europe/Paris, `jour_ouvre_de`, Fenêtre glissante, J-1, J-5, `semaine_programme`) ; `contrats.format` (formatage français) et `contrats.versions` (empreintes de Grille, prompt, modèle, données).
- Comptes entiers, taux en numérateur/dénominateur, comparaisons en `Fraction`, statut `non_evaluable` explicite.
- Passage : construit dans `.en-cours-<id>/`, publié par renommage atomique (`sorties/passages/<date>/<id>/`), déplacé sous `sorties/echecs/` en échec, immuable, autoportant ; seule `chaine` écrit dans le Passage (le rendu renvoie des octets) ; id `AAAAMMJJTHHMMSSZ-<6 hex>` ; progression dans `sorties/progression/<id>.jsonl` (hors du répertoire renommé) ; étapes via `ports.Etape`, énumération `Etape` figée.
- Rejeu : `EXCLUSIONS_REJEU` est un mapping nom logique de fichier vers chemins de champ, appliqué par fichier (amendement du 2026-10-12).
- `Consultation` : lecteur unique d'un Passage (`dernier_passage()` par `(date_arrete, horodatage_fin)` maximal, `url_ticket(cle)`, filtre `palier`) ; rendu, UI et IA n'affichent que des valeurs issues de `Consultation` ; l'UI n'ouvre jamais `entrepot.duckdb` ni `.en-cours-*`.
- Passerelle LLM unique, ordre imposé : Pseudonymisation, cache, `FournisseurLLM`, `controler_citations`, ré-identification, `EntreeTrace` ; cache SQLite WAL (`CacheLLM` est un port, suite `tests/contrat/cache_llm/`) ; jetons HMAC `<TYPE>_<6 hex>` avec `USINE_CLE_PSEUDO` ; `FournisseurLLM` à deux méthodes (`generer_structure`, `executer_agent`) ; `FournisseurFactice` en test ; `EnveloppeCache`, `ReponseExplication` et la grammaire des jetons vivent dans `contrats`, `DonneesPassage` dans `contrats.passage`.
- Configuration `config/*.yaml` validée par `usine.config` seulement ; secrets en variables d'environnement (`.env.example` sans valeurs) ; Mode repli via `USINE_MODE_REPLI`.
- Suites de contrat par port dans `tests/contrat/<port>/`, exécutées par tous les adaptateurs ; doublures dans `tests/doublures/`.
- Propriété des répertoires par lane : CI contrôle les chemins sur `lane/<n>-*` ; `.github/scripts/controle_lanes.py` doit égaler la Carte des lanes du spine (`adaptateurs/pseudonymisation` en L6). Sous-applications typer enregistrées une fois dans `cli.py`.
- Stack figée : Python 3.12, uv, pydantic 2.14, polars 1.44.2, duckdb 1.5.6, openpyxl, python-pptx, streamlit 1.65, spacy `fr_core_news_md` 3.8.0 (roue par URL), pytest, ruff, mypy, import-linter, gitleaks v8.30.1.

## UX & Interaction Patterns

- Pas de document UX ; mise en page différée aux lanes L5 et L7.
- Carte météo : une ligne par Entité avec sa couleur ; écran de lancement qui suit chaque étape de la Chaîne via le fichier de progression (ouvrir-lire-fermer).
- Bandeau « Mode repli » visible en permanence quand `USINE_MODE_REPLI=1`.
- Clés de tickets affichées en liens via `url_ticket(cle)` ; formatage français (espace insécable pour les milliers, virgule décimale, `12,5 %`).
- Gabarit PowerPoint neutre et fictif `gabarits/rapport.pptx`.

## Cross-Story Dependencies

- Ordre séquentiel : 0.1 (outillage, config, CLI) puis 0.2 (contrats, ports, doublures) puis 0.3 (Journal) puis 0.4 (Météo) puis 0.5 (Chaîne) puis 0.6 (Consultation, rendu) puis 0.7 (passerelle LLM) puis 0.8 (UI) puis 0.9 (gel).
- Story 0.9 relit les contrats contre le spine amendé, applique les décisions D1 à D10 et migre les consommateurs touchés (`ia/`, `chaine/`, `consultation/`, `domaine/meteo.py`, `rendu/`, `ui/`, `generateur/cli.py`, `composition.py`, `adaptateurs/`) dans la même PR ; tout est encore propriété de `main` avant le gel.
- Après l'étiquette `contrats-v1`, les branches `lane/1-donnees` à `lane/8-portage` sont créées depuis elle, une par worktree, avec `donnees/` et `.env` propres.
- Dépendances sortantes : E0 débloque L1, L2, L3, L6, L8 ; L3 débloque L4 et L5 ; L5 et L6 débloquent L7.
