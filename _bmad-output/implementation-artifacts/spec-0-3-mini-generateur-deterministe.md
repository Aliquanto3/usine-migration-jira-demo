---
title: 'Story 0.3 (E0-3) : mini-générateur déterministe'
type: 'feature'
created: '2026-10-11'
status: 'done'
baseline_revision: 'e359f70bde6510d682f9698961c17257e5a021fa'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-0-context.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** La Chaîne, le calcul et le rendu n'ont aucune entrée réelle : aucun Journal d'événements n'existe, et `usine donnees` n'a pas de commande (Story 0.3 de `epics.md`, FR-2 en amorce).

**Approach:** Un mini-générateur pur dans `usine.generateur` produit, pour une graine et une date de génération données, un Journal JSONL (un `EnteteJournal` puis des `Evenement`) de 2 Entités et environ 30 Anomalies, avec des Cas de test et des Certifications, au vocabulaire canonique. La vérité terrain des Causes racines est écrite à part. La commande `usine donnees generer` le relie à `config/programme.yaml` (version réduite).

## Boundaries & Constraints

**Always:**
- Le générateur (`src/usine/generateur/`, hors `cli.py`) n'importe que `usine.contrats` et la stdlib ; il ne lit ni l'horloge (`datetime.now`, `date.today`) ni le `random` global : la date de génération et la graine sont des paramètres, et le hasard vient d'une seule instance `random.Random(graine)`.
- Tout `Evenement` est construit par le modèle `contrats.evenements.Evenement` : la validation du contrat garantit les domaines canoniques. Le Journal ne porte jamais de Cause racine.
- Une création est suivie, au même horodatage, d'un `modification_champ` par `Champ` de `CHAMPS_PAR_TYPE[type_ticket]` (`titre` et `description` compris) ; l'ordre des champs est fixe (ordre de l'énumération `Champ`).
- Identifiants `J-<rang>`, rang à partir de 1, dans l'ordre d'écriture ; événements triés par `(horodatage, clé de ticket, rang de création)`, création d'abord. Clés de ticket `DEMO-<n>`, `n` à partir de 1, dans l'ordre de création.
- Temps : uniquement `contrats.calendrier`. Date d'injection = `dernier_jour_ouvre_ecoule(date_generation)` ; ancrage = lundi de la semaine de la Date d'injection, moins `nb_semaines − 1` semaines. Chaque horodatage tombe un Jour ouvré entre l'ancrage et la Date d'injection incluses, en heures ouvrées de Paris (construit avec `calendrier.FUSEAU`, stocké en UTC).
- Sortie octet pour octet stable : UTF-8, fins de ligne `\n`, JSON compact via `model_dump_json()`, une ligne par enregistrement ; vérité terrain en JSON trié par clé.
- `config/programme.yaml` commenté en français, chaque clé (NFR-10), validé par `ConfigProgramme` via `usine.config.charger_yaml` dans `generateur/cli.py` seulement.

**Never:**
- Modifier `src/usine/contrats/`, `src/usine/ports/`, `usine.config`, `pyproject.toml`, `uv.lock` ; ajouter une dépendance.
- Appeler un LLM ou Jira ; implémenter les Scénarios de démo, la volumétrie cible ou l'injection (Epic 1).
- Écrire dans `donnees/corpus/` ou versionner un Journal généré.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Génération | `usine donnees generer --graine 42 --date-generation 2026-10-12` | `donnees/journal.jsonl` (1re ligne `EnteteJournal`, graine 42, Date d'injection 2026-10-09, ancrage 2026-08-17) et `donnees/verite_terrain.json` ; code 0 | N/A |
| Reproductibilité | deux exécutions, même graine et même date | fichiers identiques octet pour octet | N/A |
| Graine différente | `--graine 43` | Journal différent | N/A |
| Création | toute création du Journal | suivie au même horodatage d'un `modification_champ` par champ du type, dont `titre` et `description` | N/A |
| Domaines | tout le Journal relu par `Evenement.model_validate_json` | aucune erreur ; `id_evenement` = `J-1`, `J-2`… sans trou | N/A |
| Vérité terrain | `verite_terrain.json` | une `CauseRacine` par Anomalie, aucune pour les autres types ; aucune ligne du Journal ne contient de Cause racine | N/A |
| Volumétrie | config réduite | 2 Entités, Anomalies entre `anomalies_min` et `anomalies_max`, au moins un Cas de test et une Certification par Entité | N/A |
| Date invalide | `--date-generation 2026-13-01` | message nommant la date, code non nul | `UsineErreur` |
| Config fautive | `programme.yaml` avec une Entité à Vague inconnue | message nommant fichier et clé, code 1 | `UsineErreur` du chargeur |

</intent-contract>

## Code Map

- `src/usine/generateur/cli.py` -- sous-application `usine donnees` (callback seul) : ajouter la commande `generer` ; seul lieu qui lit la config, l'horloge (défaut de `--date-generation` : `jour_local(datetime.now(UTC))`) et écrit les fichiers.
- `src/usine/cli.py` -- enregistre déjà `app_donnees` sous `donnees` ; `main()` traduit `UsineErreur` en code 1. Ne pas modifier.
- `src/usine/config/chargeur.py:charger_yaml(chemin, modele)` -- à réutiliser tel quel (ne pas toucher à `MODELES`).
- `src/usine/contrats/config.py` -- `ConfigProgramme` (`nom`, `graine`, `nb_semaines`, `entites`, `vagues` avec `phases`, `domaines`, `volumetrie.anomalies_min/max`, `entrees_semaine_min/max`).
- `src/usine/contrats/evenements.py` -- `Evenement`, `EnteteJournal` (`ancrage_semaines` lundi, ordre ancrage ≤ injection ≤ génération, `version_corpus`, `modele_corpus`), `NatureEvenement`, `SourceEvenement.journal`.
- `src/usine/contrats/tickets.py` -- `TypeTicket`, `Champ`, `CHAMPS_PAR_TYPE`, `StatutAnomalie`, `Gravite`, `Phase`, `StatutTest`, `StatutCertification`, `CauseRacine`, `STATUTS_FERMES`.
- `src/usine/contrats/calendrier.py` -- `FUSEAU`, `dernier_jour_ouvre_ecoule`, `jours_ouvres`, `jour_ouvre_precedent`, `verifier_lundi`.
- `tests/unit/config/test_commentaires.py:7` -- vérifie déjà chaque `config/*.yaml` livré : `programme.yaml` doit passer.
- `tests/unit/contrats/test_config.py:318` -- affirme que `config/` ne contient que `chaine.yaml` : l'élargir à `{chaine.yaml, programme.yaml}`.
- `tests/contrat/source_tickets/` -- suite à réutiliser comme oracle de forme (création suivie de ses attributs, horodatages UTC triés).

## Tasks & Acceptance

**Execution:**
- `src/usine/generateur/textes.py` -- mini-corpus fictif intégré (quelques titres et descriptions par type, sans nom réel) ; constantes `VERSION_CORPUS = "mini-e0"`, `MODELE_CORPUS = "aucun"` -- pas de LLM en E0.
- `src/usine/generateur/journal.py` -- `generer(config, graine, date_generation) -> Generation` (en-tête, tuple d'`Evenement`, vérité terrain `dict[str, CauseRacine]`) puis `serialiser_journal(generation) -> bytes` et `serialiser_verite(generation) -> bytes` -- cœur pur et déterministe.
- `src/usine/generateur/cli.py` -- commande `generer` : options `--graine` (défaut : `config.graine`), `--date-generation AAAA-MM-JJ`, `--config` (défaut `config/programme.yaml`), `--sortie` (défaut `donnees/`) ; crée le répertoire, écrit les deux fichiers en octets ; date mal formée → `UsineErreur`.
- `config/programme.yaml` -- version réduite commentée : 2 Entités (`ENT-A`, `ENT-B`), 1 Vague avec ses trois Phases, 3 Domaines, `anomalies_min: 25`, `anomalies_max: 35`, `nb_semaines: 8`, `graine: 42`.
- `tests/unit/generateur/test_journal.py`, `tests/unit/generateur/test_cli.py` -- matrice I/O (via `typer.testing.CliRunner` et `tmp_path`), plus un test qui inspecte le source de `src/usine/generateur/*.py` hors `cli.py` : ni `datetime.now`, ni `date.today`, ni `random.` au niveau module (seul `random.Random(` est permis).
- `tests/unit/contrats/test_config.py` -- élargir l'assertion de la ligne 318.

**Acceptance Criteria:**
- Given le Journal produit, when on le passe à la suite de contrat `SourceTickets` via une fabrique `SourceEnMemoire` construite sur ses événements, then les tests de forme de la suite passent (le Journal est consommable par la Story 0.4).
- Given le dépôt, when `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest`, then tout passe.

## Spec Change Log

## Review Triage Log

### 2026-10-11 — Review pass
- verdicts: 30 findings — high 0, medium 1, low 25, false 4, maybe-false 0
- findings:
  - `[low]` `[reject]` (intention) `cli.py` lit l'horloge alors que l'AC parle du « générateur » — le critère vise le cœur (AD-1 : la date est un paramètre) ; la composition peut fixer un défaut, et le cœur `generer` reçoit date et graine.
  - `[false]` `[reject]` (intention) « environ 30 tickets » contre 31 à 43 tickets au total — l'AC précise « ~30 Anomalies, Cas de test et Certifications » ; l'ordre de grandeur est tenu.
  - `[low]` `[reject]` (intention) `--graine 42` seul n'est pas reproductible d'un jour à l'autre — la date de génération est un paramètre de la sortie (AC3, en-tête) ; à date égale, la sortie est identique (testé).
  - `[false]` `[reject]` (intention) Valeurs `domaine`, `titre` hors domaines canoniques — `DOMAINES_CANONIQUES` les déclare libres (AD-23) ; la validation `Evenement` passe.
  - `[low]` `[patch]` (intention) Destination par défaut `donnees/` jamais exécutée — `test_chemins_par_defaut` ajouté.
  - `[false]` `[reject]` (intention) Fabrique `journal_genere` hors périmètre — elle porte le critère d'acceptation « consommable par la Story 0.4 ».
  - `[low]` `[patch]` (verification-gap) Défaut de date jamais testé après minuit à Paris — instant 00 h 30 Paris ajouté.
  - `[low]` `[patch]` (verification-gap) Chemins par défaut jamais exercés — même correctif.
  - `[low]` `[patch]` (verification-gap) Branche `OSError` → `UsineErreur` non testée — `test_sortie_non_inscriptible` ajouté.
  - `[low]` `[reject]` (verification-gap) Test de pureté textuel, contournable par alias — les tests de reproductibilité attrapent les régressions pratiques ; un contrôle par `ast` serait de la complexité ajoutée.
  - `[false]` `[reject]` (verification-gap) La fabrique ne vérifie pas l'ordre du générateur — le relecteur conclut lui-même à l'absence de trou (`test_tri_et_cles`).
  - `[medium]` `[patch]` (edge) Graine négative = même Journal que sa valeur absolue — `graine < 0` refusée dans `generer`, testée.
  - `[low]` `[reject]` (edge) `OverflowError` près de `date.min` — date irréaliste pour ce démonstrateur.
  - `[low]` `[reject]` (edge) Même cause via `nb_semaines` énorme — idem.
  - `[low]` `[reject]` (edge) `ValidationError` brute si le générateur produit un événement invalide — ce serait un défaut du générateur, que les tests de contrat attrapent ; un message propre le masquerait.
  - `[low]` `[reject]` (edge) Écriture non atomique des deux fichiers — données régénérables par une commande ; la garde ajouterait des fichiers temporaires.
  - `[low]` `[reject]` (edge) Transitions `nouvelle → en_correction` et `a_retester → en_correction` hors des flèches de la note — H-17 fixe les statuts, pas les transitions ; la note décrit le chemin principal, et le reteste en échec est légitime.
  - `[low]` `[reject]` (edge) Tri par numéro de clé plutôt que par chaîne — l'ordre numérique est celui de création voulu par la spec ; aucun consommateur ne retrie par chaîne.
  - `[low]` `[reject]` (blind) Ordre du Journal différent de celui de `SourceEnMemoire` à l'instant égal — les deux ordres respectent AD-3 (création suivie de ses attributs, testée par la suite et par `test_tri_et_cles`) ; la Story 0.4 lira le fichier tel quel.
  - `[low]` `[patch]` (blind) Une seule graine testée — fixture paramétrée sur cinq graines.
  - `[low]` `[reject]` (blind) Aucun test « golden » des octets — figerait des choix encore mouvants ; reproductibilité couverte à date et graine égales.
  - `[low]` `[reject]` (blind) Calendrier des Phases ignoré — Phases calées sur le calendrier : Epic 1 (Story 1.3), hors mini-générateur.
  - `[low]` `[reject]` (blind) Certifications incohérentes dans le temps — idem, Epic 1.
  - `[low]` `[reject]` (blind) Causes racines indépendantes du texte — le Corpus de textes est la Story 1.2.
  - `[low]` `[reject]` (blind) `entrees_semaine_min/max` ignorés — exigés par `ConfigProgramme`, commentés comme non utilisés en E0 ; volumétrie cible : Story 1.3.
  - `[low]` `[reject]` (blind) Écriture non atomique et écrasement silencieux — même raison que la ligne edge ; le test `OSError` est ajouté.
  - `[low]` `[reject]` (blind) Date de génération future acceptée — sans conséquence : la date est un paramètre explicite.
  - `[low]` `[patch]` (blind) Date invalide non vérifiée de bout en bout — `test_date_invalide_code_1` via `usine.cli.main()`.
  - `[low]` `[reject]` (blind) Recherche du lundi fragile si l'on ajoute des jours fériés — H-1 exclut les jours fériés ; `.weekday(` est interdit hors calendrier.
  - `[low]` `[reject]` (blind) Test de pureté contournable — même raison que la ligne verification-gap.

## Design Notes

**Cycle de vie fictif.** Pour chaque Anomalie : un Jour ouvré de création tiré dans la fenêtre, une `Gravite`, une `Phase`, un Domaine, une `CauseRacine` (vérité terrain seulement), statut initial `nouvelle`, puis 0 à 4 `transition` à des Jours ouvrés ultérieurs, ≤ Date d'injection, le long du workflow H-17 (`nouvelle → en_analyse → en_correction → a_retester → fermee`, `rejetee` possible depuis `en_analyse`, réouverture `fermee → en_analyse` rare). Cas de test : statut initial `non_execute`, puis `modification_champ` de `statut_test` vers `ok` ou `ko`. Certification : statut initial tiré parmi `StatutCertification`. Le tirage passe par la seule instance `Random`, dans un ordre fixe (Entités puis tickets dans l'ordre des clés), pour que la sortie ne dépende que de `(config, graine, date_generation)`.

**Heures.** `datetime.combine(jour, time(h, m), tzinfo=FUSEAU).astimezone(UTC)`, avec `h` entre 8 et 18 : l'horodatage UTC reste rattaché au même Jour ouvré par `jour_ouvre_de`.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check .` -- expected: aucun écart.
- `uv run mypy` -- expected: aucune erreur.
- `uv run lint-imports` -- expected: tous les contrats KEPT.
- `uv run pytest` -- expected: tout vert.
- `uv run usine donnees generer --graine 42 --date-generation 2026-10-12 --sortie <tmp>` deux fois, puis comparaison des fichiers -- expected: identiques.

## Auto Run Result

Status: done

**Résumé.** Mini-générateur pur (`usine.generateur.journal.generer`) : à partir de la config, d'une graine ≥ 0 et d'une date de génération, il produit un Journal JSONL (`EnteteJournal` puis des `Evenement` `J-1…J-n`) de 2 Entités, 25 à 35 Anomalies, des Cas de test et des Certifications, ainsi qu'une vérité terrain séparée. La commande `usine donnees generer` le relie à `config/programme.yaml` (version réduite et commentée).

**Fichiers.**
- `src/usine/generateur/journal.py` : cœur déterministe et sérialisation.
- `src/usine/generateur/textes.py` : mini-corpus fictif (`mini-e0`).
- `src/usine/generateur/cli.py` : commande `generer`.
- `config/programme.yaml` : configuration réduite.
- `tests/unit/generateur/` : matrice I/O, invariants sur cinq graines, CLI de bout en bout.
- `tests/contrat/source_tickets/fabriques.py` : fabrique `journal_genere`.
- `tests/unit/contrats/test_config.py` : liste des YAML livrés en E0.

**Revue.** 30 findings, tous dans le journal de tri : 7 lignes `patch` (1 medium, la graine négative) donnant 6 correctifs, 0 différé, 23 rejetées avec leur motif.

**Revue de suivi.** `false` : aucun correctif `high`, un seul `medium`.

**Vérification.** ruff, ruff format, mypy, lint-imports et pytest donnent 598 passés et 11 ignorés. La reproductibilité octet pour octet est vérifiée par tests, sur cinq graines.

**Risques résiduels.**
- Les Phases, la cohérence temporelle des Certifications et le lien entre Cause racine et texte sont laissés à l'Epic 1.
- Le Journal ne suit pas le même ordre que `SourceEnMemoire` quand deux créations tombent au même instant ; les deux ordres respectent AD-3.
