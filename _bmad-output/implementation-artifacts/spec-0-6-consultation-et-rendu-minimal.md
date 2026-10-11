---
title: 'Story 0.6 (E0-6) : Consultation et rendu minimal'
type: 'feature'
created: '2026-10-11'
status: 'done'
baseline_revision: '2d92119e881c41e67e2222450e8d7eed84810b12'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-0-context.md'
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Un Passage est publié, mais aucun Rapport quotidien n'en sort. La `Consultation` ne lit que `tickets_etats`, `dernier_passage()` et `url_ticket` n'existent pas, et la suite de contrat `Consultation` n'a aucun adaptateur (Story 0.6 de `epics.md` ; amorces de FR-26, FR-27 et FR-29 ; FR-14).

**Approach:**
- Compléter `ConsultationPassage` : chaque lecture du port, `dernier_passage()` sans pointeur mutable, `url_ticket` depuis `config/jira.yaml`. L'enregistrer dans la suite de contrat.
- Ajouter dans `usine.rendu` une étape `rendu` qui lit via `Consultation` seulement. Elle renvoie les octets d'un Excel à un onglet Synthèse et d'un PowerPoint à une slide carte météo, construite sur un gabarit neutre fictif. Les deux sont déterministes à date égale.

## Boundaries & Constraints

**Always:**
- `usine.rendu` n'importe que `usine.contrats`, `usine.ports`, `usine.consultation`, ainsi qu'openpyxl et python-pptx (contrat import-linter). Il ne calcule aucune valeur métier (AD-9) et ne fait que formater via `contrats.format`.
- L'étape `rendu` lit tout via `ctx.consultation` et renvoie `ResultatEtape(reussie, {"rapport_xlsx": bytes, "rapport_pptx": bytes})`. Seule `chaine` écrit ces fichiers (AD-22), nommés `rapport-AAAA-MM-JJ.xlsx` et `rapport-AAAA-MM-JJ.pptx`.
- Excel, onglet unique `Synthèse` :
  - une ligne par Entité, dans l'ordre de `meteo()` ;
  - colonnes : Entité, Météo (libellé français), Règles déclenchantes (code, valeur et seuil formatés) et Tickets en cause.
  - chaque clé de ticket affichée porte l'hyperlien `consultation.url_ticket(cle)`, sauf si l'URL vaut `None`. Une cellule ne porte qu'une clé : une ligne par ticket en cause, ou une clé par colonne.
- PowerPoint : une slide « Carte météo », titre avec la Date d'arrêté et un tableau Entité × Météo, construit sur `gabarits/rapport.pptx` (gabarit neutre, fictif, versionné).
- Déterminisme (FR-14, AD-7) : `docProps` (`created`, `modified`, auteur, titre) fixés à partir de la Date d'arrêté et de constantes. Ordre stable des lignes et des formes.
- `ConsultationPassage` :
  - fichiers lus en ouvrir-lire-fermer ;
  - version de contrats vérifiée : métadonnée Parquet, enveloppe JSON, `ManifestePassage` ;
  - tables validées par leur `SCHEMA_X` ;
  - un fichier absent du Passage (étape bouchon ou `sautee`) donne un résultat vide : table vide au schéma, ou tuple vide. Seul le manifeste est obligatoire, et son absence lève une `UsineErreur` qui le nomme.
- `dernier_passage()` parcourt `sorties/passages/<date>/<id>/manifeste.json` (en ignorant `.en-cours-*` et `echecs/`) et rend le manifeste de `(date_arrete, horodatage_fin)` maximal, ou `None`. Aucun pointeur ni fichier mutable.
- `url_ticket(cle)` = `<ConfigJira.url_site>/browse/<cle>`. Il vaut `None` en Mode repli (`USINE_MODE_REPLI`) ou sans configuration Jira.
- Lectures LLM avec `palier=1` : résultat vide (FR-46).

**Never:**
- Modifier `src/usine/contrats/`, `src/usine/ports/`, `pyproject.toml`, `uv.lock` ; ajouter une dépendance.
- Lire un fichier de Passage hors de `usine.consultation`, ou en écrire un hors de `chaine`.
- Produire les 9 onglets ou les 7 sections (Epic 5) ; calculer KPI, Tendances ou Prévisions.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Rapport publié | Journal (graine 42, 2026-10-12), `usine rapport --date-arrete 2026-10-09` | le Passage contient `rapport-2026-10-09.xlsx` et `rapport-2026-10-09.pptx` | N/A |
| Synthèse | xlsx publié | onglet `Synthèse` : en-têtes puis une ligne par Entité avec sa Météo, égale à `consultation.meteo()` | N/A |
| Liens | Entité rouge avec tickets en cause | chaque cellule de clé a un hyperlien `https://<site>/browse/<cle>` égal à `url_ticket(cle)` | N/A |
| Mode repli | `USINE_MODE_REPLI=1` | `url_ticket` vaut `None`, clés sans hyperlien | N/A |
| Slide | pptx publié | une seule slide, titre contenant `09/10/2026`, tableau d'une ligne par Entité avec sa Météo | N/A |
| Rejeu | deux Passages, même Date d'arrêté et même Journal | valeurs des cellules, hyperliens, textes de la slide et `docProps` identiques | N/A |
| Dernier Passage | Passages 2026-10-08 et 2026-10-09 (deux le 09), plus un `.en-cours-*` et un échec | manifeste du 09 de `horodatage_fin` maximal | N/A |
| Aucun Passage | `sorties/passages/` vide ou absent | `dernier_passage()` vaut `None` | N/A |
| Fichier absent | Passage Palier 1 (pas de `kpi.parquet`, pas de `llm/`) | `kpi()` donne une table vide au `SCHEMA_KPI`, `explications()` donne `()` | N/A |
| Version étrangère | `meteo.json` d'enveloppe `1.0.0` | `UsineErreur` qui nomme le fichier et les versions | — |
| Manifeste absent | répertoire sans `manifeste.json` | `UsineErreur` qui nomme le fichier | — |
| Évolution | Passage du 2026-10-09 | `evolution_meteo()` donne J-1 = 2026-10-08 et J-5 = 2026-10-02 avec leurs couleurs | N/A |

</intent-contract>

## Code Map

- `src/usine/consultation/passage.py` -- `ConsultationPassage(repertoire)` avec `lire_table` (version et schéma) et `tickets_etats` ; les autres lectures lèvent `MESSAGE_STORY_0_6`. Ajouter les paramètres nommés `racine_passages: Path | None = None` et `url_jira: str | None = None`, et implémenter toutes les lectures.
- `src/usine/ports/consultation.py` -- signatures et docstrings du port (filtres `date_arrete=None` = date du Passage, `palier`, `limite`, `code_kpi`).
- `src/usine/contrats/passage.py` -- `FICHIERS_PASSAGE`, `CONTENUS_JSON`, `lire_enveloppe`, `ManifestePassage`, `chemin_fichier_passage`.
- `src/usine/contrats/agent.py` -- `AnomalieResume` (Anomalie ouverte, `age_jours_ouvres` depuis `date_derniere_entree`), `ResultatListAnomalies` (`total` avant la limite).
- `src/usine/contrats/meteo.py` -- `EvolutionMeteo` (dates J-1/J-5 calées sur `jour_ouvre_precedent`, couleurs optionnelles).
- `src/usine/contrats/config.py` -- `ConfigJira` (correspondance complète exigée : `champs` couvre chaque `Champ`, `types_tickets` chaque `TypeTicket`, `valeurs` chaque `Champ` à domaine fermé) ; `ConfigUsine.jira`.
- `src/usine/contrats/format.py` -- `formater_nombre`, `formater_fraction`, `formater_date` ; `contrats.tickets.LIBELLES` pour les libellés.
- `src/usine/config/secrets.py` -- `Secrets.usine_mode_repli`.
- `src/usine/composition.py:64-97` -- `construire_rapport` : registre (`Etape.rendu` en `EtapeBouchon`) et `ConfigUsine`. `lancer_rapport` passe `ConsultationPassage` comme `fabrique_consultation(repertoire)` : passer un `functools.partial` qui fixe `racine_passages` et `url_jira`.
- `src/usine/chaine/ecrivain.py` -- écrit déjà des `bytes` tels quels pour `rapport_xlsx` et `rapport_pptx`.
- `tests/contrat/consultation/{fabriques.py,test_contrat.py}` -- suite à 11 tests ; `FABRIQUES` est vide.
- `tests/unit/contrats/test_config.py` (`test_yaml_livres_en_e0`) -- ajouter `jira.yaml`.

## Tasks & Acceptance

**Execution:**
- `src/usine/consultation/passage.py` -- toutes les lectures du port :
  - `manifeste`, `dates_disponibles` (dates de `meteo.json`, triées) ;
  - `meteo` et `evolution_meteo` (depuis `meteo.json`) ;
  - les tables (`instantanes`, `indicateurs`, `kpi`, `tendances`, `tickets_etats`, `textes_tickets`, `repartition_causes`), filtrées par date et Entité ;
  - `anomalies` (depuis `tickets_etats` à la date : ouvertes, filtres, tri par clé numérique, âge via `calendrier.jours_ouvres`, `limite`) ;
  - `previsions`, `risques`, `classification`, `explications`, `narrations` (vides si `palier=1` ou fichier absent) ;
  - `traces` (lignes `EntreeTrace` des deux jsonl) ;
  - `dernier_passage` et `url_ticket`.
- `src/usine/rendu/excel.py`, `src/usine/rendu/powerpoint.py`, `src/usine/rendu/etape.py` -- `rendre_excel(consultation) -> bytes`, `rendre_powerpoint(consultation, gabarit: bytes) -> bytes`, `EtapeRendu(gabarit: bytes)` qui implémente `ports.Etape`.
- `gabarits/rapport.pptx` -- gabarit neutre fictif (16:9, sans logo ni nom réel), produit par `outils/creer_gabarit.py` (python-pptx, propriétés fixes) et versionné.
- `config/jira.yaml` -- configuration fictive commentée en français (NFR-10) :
  - `url_site: https://demo-usine.atlassian.net`, `mode: cloud`, `cle_projet: DEMO` ;
  - correspondance complète en identifiants `customfield_100NN` fictifs et en valeurs Jira françaises (`Nouvelle`, `Bloquante`…).

  Elle est validée par `ConfigJira` ; la lane L2 l'ajustera.
- `src/usine/composition.py` -- charger `jira.yaml` et `Secrets` (mode repli) ; brancher `EtapeRendu(octets du gabarit)` sur `Etape.rendu` ; passer `racine_passages` et `url_jira` à la `Consultation`.
- `tests/contrat/consultation/fabriques.py` -- fabrique `passage_publie`. Elle génère un Journal (graine 42, 2026-10-12) et lance `lancer_rapport` dans un répertoire temporaire (`tempfile.mkdtemp` + `atexit` `shutil.rmtree`) avec la configuration du dépôt copiée, puis rend `ConsultationPassage` sur le Passage publié, avec Entité `ENT-A`.
- `tests/unit/consultation/test_passage.py`, `tests/unit/rendu/test_excel.py`, `test_powerpoint.py`, `tests/unit/chaine/test_cli.py` (rejeu) -- matrice I/O (openpyxl et python-pptx relisent les octets).
- `tests/unit/contrats/test_config.py` -- `jira.yaml` dans la liste des YAML livrés.

**Acceptance Criteria:**
- Given `uv run pytest tests/contrat/consultation`, when la suite tourne, then ses tests s'exécutent (non ignorés) et passent pour `passage_publie`.
- Given le dépôt, when `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest`, then tout passe.

## Spec Change Log

## Review Triage Log

### 2026-10-11 — Review pass
- verdicts: 43 findings — high 0, medium 6, low 34, false 3, maybe-false 0
- findings:
  - `[low]` `[reject]` (intention) Écritures hors de « Écrit dans » (`config/jira.yaml`, composition, outil du gabarit) — exigées par FR-29 et par le câblage de l'étape `rendu` (spec, *Design Notes*).
  - `[medium]` `[patch]` (intention) Date du rendu déduite de `meteo.json` — `ctx.date_arrete` transmise explicitement au rendu.
  - `[low]` `[reject]` (intention) Test des liens comparé à une Consultation à URL codée en dur — l'URL est celle de `config/jira.yaml` ; les deux chemins appellent le même `url_ticket`.
  - `[low]` `[reject]` (intention) `docProps` comparés sur un sous-ensemble — ce sont les propriétés qu'AD-7 fixe à partir de la Date d'arrêté ; les autres sont des constantes de bibliothèque.
  - `[false]` `[reject]` (intention) `dernier_passage` multi-Passages testé en unitaire seulement — le cas est bien testé (`test_dernier_passage`) ; la suite de contrat en vérifie la forme.
  - `[false]` `[reject]` (intention) Lectures au-delà des AC — l'AC exige le passage de la suite de contrat, qui couvre tout le port.
  - `[medium]` `[patch]` (blind) `EtapeRendu` ignore `ctx.date_arrete` — date passée explicitement.
  - `[low]` `[patch]` (blind) Rendu en échec sans Météo — en-têtes et tableau vides, testés.
  - `[medium]` `[patch]` (blind) Date du Passage en construction devinée — paramètre `date_arrete` de `ConsultationPassage`, transmis par la fabrique.
  - `[medium]` `[patch]` (blind) Un manifeste illisible bloque `dernier_passage` — Passage ignoré avec un avertissement qui nomme le fichier, testé.
  - `[low]` `[patch]` (blind) `create_system` et `external_attr` dépendent de l'OS — constantes fixées.
  - `[low]` `[patch]` (blind) Test d'octets fait dans la même seconde — deux instants figés à trois semaines d'écart (la note de spec « valeurs, pas octets » reste juste pour le Rejeu, qui compare des valeurs).
  - `[low]` `[patch]` (blind) Retours à la ligne non affichés — `wrap_text`.
  - `[low]` `[reject]` (blind) Colonnes de tickets sans en-tête propre — mise en page de l'Epic 5 ; deux Entités en E0.
  - `[low]` `[patch]` (blind) Texte blanc sur jaune peu lisible — texte foncé sur jaune.
  - `[low]` `[reject]` (blind) Débordement de la slide au-delà de 13 Entités — 2 Entités en E0 ; PowerPoint complet en Epic 5.
  - `[low]` `[reject]` (blind) `ValueError` sur une gravité nulle dans `anomalies` — toute Anomalie porte gravité et phase (AD-3, validation `pl.Enum`).
  - `[low]` `[patch]` (blind) Palier 1 avec fichiers présents et lectures non vides non testés — tests de `traces()` et d'`explications` (Palier 1 et Palier 2) ajoutés ; Prévisions et classification seront couvertes par les stories qui les produisent.
  - `[low]` `[patch]` (blind) Docstring de `textes_tickets` inexacte — corrigée.
  - `[low]` `[reject]` (blind) `url_ticket` sans encodage — les clés sont validées par `MOTIF_CLE_TICKET` en amont.
  - `[low]` `[reject]` (blind) Gabarit binaire sans test contre son script — gabarit figé et versionné ; le script sert à le régénérer.
  - `[low]` `[reject]` (blind) Cas d'erreur du gabarit peu testés — le gabarit est livré par le dépôt ; le cas « illisible » est couvert.
  - `[low]` `[reject]` (blind) Fabrique de contrat sensible à l'environnement — `url_jira` est passée explicitement, les assertions n'en dépendent pas.
  - `[low]` `[patch]` (blind) `_REPERTOIRES_IGNORES` mort — supprimé.
  - `[low]` `[patch]` (verification-gap) Déterminisme des octets non éprouvé — même correctif.
  - `[low]` `[patch]` (verification-gap) Filtres d'`anomalies` vacuement vrais — comparés au sous-ensemble non vide attendu (Entité et gravité, phase, domaine).
  - `[low]` `[patch]` (verification-gap) Couleur J-5 jamais comparée — comparée à la Météo du 2026-10-02.
  - `[low]` `[patch]` (verification-gap) Lectures non vides jamais exercées — `traces()` et `explications` testées ; le reste avec les étapes productrices.
  - `[low]` `[patch]` (verification-gap) Branche « sans `config/jira.yaml` » jamais exécutée — fixture `passage_sans_jira`.
  - `[medium]` `[patch]` (verification-gap) Date du rendu tirée de `meteo.json` — même correctif.
  - `[low]` `[reject]` (verification-gap) Fabrique de contrat non isolée de `USINE_MODE_REPLI` — même raison que la ligne blind.
  - `[low]` `[reject]` (verification-gap) Prémisse sur les horodatages zip non vérifiée dans la bibliothèque — tranchée par le nouveau test à deux instants.
  - `[low]` `[reject]` (edge) Gravité, phase ou statut nuls — même raison que la ligne blind.
  - `[false]` `[reject]` (edge) Âge faux si la dernière Entrée tombe un week-end — `date_derniere_entree` vient de `jour_ouvre_de`, c'est toujours un Jour ouvré.
  - `[medium]` `[patch]` (edge) Manifeste corrompu bloquant `dernier_passage` — même correctif.
  - `[low]` `[reject]` (edge) Racine déduite d'un répertoire hors arborescence — la composition passe `racine_passages` explicitement.
  - `[low]` `[reject]` (edge) Valeur de filtre hors `pl.Enum` — paramètres typés `Gravite`/`Phase` (mypy).
  - `[low]` `[patch]` (edge) `Secrets()` lit le `.env` du répertoire courant — `Secrets(_env_file=racine / ".env")`.
  - `[low]` `[patch]` (edge) Rendu en échec sans Météo — même correctif.
  - `[low]` `[reject]` (edge) Débordement de la slide — même raison.
  - `[low]` `[reject]` (edge) Gabarit sans `sldSz` — gabarit livré et testé.
  - `[low]` `[reject]` (edge) Valeur commençant par `=` interprétée comme formule — codes `ENT-x` et clés `DEMO-n` seulement.
  - `[low]` `[reject]` (edge) Date d'arrêté antérieure à 1980 — hors du domaine du démonstrateur.

## Design Notes

**Pourquoi `config/jira.yaml` dès E0.** FR-29 et l'AC « chaque clé est un lien construit par `url_ticket` » exigent une URL de site, et AD-11 la place dans `config/jira.yaml`. Le fichier est entièrement fictif et complet, pour satisfaire `ConfigJira`. La lane L2 en garde la propriété et l'ajustera.

**Rejeu.** La comparaison porte sur les valeurs relues, pas sur les octets : les zip d'openpyxl et de python-pptx contiennent des horodatages d'archive. `docProps` : `created = modified = datetime.combine(date_arrete, time(0), UTC)`, auteur « Usine de migration (démonstrateur) », titre « Rapport quotidien du JJ/MM/AAAA ».

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check .` -- expected: aucun écart.
- `uv run mypy` -- expected: aucune erreur.
- `uv run lint-imports` -- expected: tous les contrats KEPT.
- `uv run pytest` -- expected: tout vert ; la suite `consultation` n'est plus ignorée.
- `uv run usine donnees generer --graine 42 --date-generation 2026-10-12` puis `uv run usine rapport --date-arrete 2026-10-09` -- expected: Passage avec `rapport-2026-10-09.xlsx` et `.pptx`.

## Auto Run Result

Status: done

**Résumé.** `ConsultationPassage` implémente maintenant tout le port. Il gère `dernier_passage()` sans pointeur mutable, `url_ticket` depuis `config/jira.yaml` (`None` en Mode repli ou sans configuration Jira), et rend un résultat vide pour un fichier absent. Il passe la suite de contrat (11 tests, plus aucun ignoré).

L'étape `rendu` lit tout via `Consultation` et renvoie les octets de deux fichiers, que la Chaîne publie sous `rapport-AAAA-MM-JJ` :
- un Excel à un onglet `Synthèse`, avec un lien Jira par clé de ticket ;
- un PowerPoint à une slide « Carte météo », construite sur le gabarit neutre.

Le rendu est déterministe à date égale, octet pour octet, sous Windows comme sous Linux.

**Fichiers.**
- `src/usine/consultation/passage.py` : port complet.
- `src/usine/rendu/{commun,excel,powerpoint,etape}.py` : rendu.
- `gabarits/rapport.pptx` et `outils/creer_gabarit.py` : gabarit.
- `config/jira.yaml` : configuration fictive.
- `src/usine/composition.py` : branchement du rendu, de Jira et du Mode repli.
- `tests/contrat/consultation/fabriques.py` : fabrique `passage_publie`.
- `tests/unit/consultation/`, `tests/unit/rendu/` et `tests/unit/chaine/` : tests.

**Revue.** 43 findings, dont 21 lignes `patch` donnant 10 correctifs. Les 6 lignes medium tiennent à deux causes : la date du rendu ou du Passage en construction, et un manifeste illisible. Aucun élément n'est différé ; les 22 autres findings sont rejetés avec leur motif.

**Revue de suivi.** `true`. `ConsultationPassage` devine encore la date (dernière date de `meteo.json`) quand on ne lui donne ni manifeste ni `date_arrete`. Seule la composition passe aujourd'hui `date_arrete` ; un futur appelant (UI, Agent) qui lirait un Passage en construction sans elle retomberait sur cette heuristique.

**Vérification.** ruff, ruff format, mypy, lint-imports et pytest donnent 736 passés, 0 ignoré. Exécution réelle : `usine rapport --date-arrete 2026-10-09` publie l'Excel et le PowerPoint.

**Risques résiduels.**
- Les lectures de Prévisions, de risques, de classification et de narrations ne sont testées que vides (aucun producteur en E0).
- openpyxl est importé avec `type: ignore[import-untyped]`.
