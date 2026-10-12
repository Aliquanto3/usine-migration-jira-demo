---
title: 'Story 4.3 : Conversion du Public Jira Dataset en SerieStock'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'f411eb6d8c1428a21ab8f0d944dd9f67e6e2f9d4'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** FR-51 exige d'évaluer la Baseline (Story 4.1) sur des données Jira réelles ; rien ne lit encore le Public Jira Dataset (dump MongoDB sur Zenodo, Montgomery et al.) ni ne le transforme en `SerieStock`, le contrat gelé qu'attend `domaine.prevision.baseline.prevoir_sortie`.

**Approach:** Spike d'une demi-journée (téléchargement, MongoDB portable, `mongorestore` de quelques dépôts) consigné dans `evaluation/zenodo/README.md` ; module pur `evaluation.zenodo.conversion` qui transforme des documents de tickets (forme brute Jira API v2 du dump) en `SerieStock` par projet, en Jours ouvrés ; lecteur pymongo séparé ; test unitaire sur un petit extrait figé versionné.

## Boundaries & Constraints

**Always:** sortie validée par `valider(df, SCHEMA_SERIE_STOCK)` ; série dense de Jours ouvrés consécutifs (contrat attendu par `prevoir_sortie`) ; rattachement des instants par `contrats.calendrier.jour_ouvre_de` ; invariant stock(j) = stock(j−1) + entrées(j) − sorties(j), stock ≥ 0 ; conversion pure et déterministe (aucune I/O, aucun réseau) ; pymongo importé seulement par le lecteur ; pymongo en groupe de dépendances `evaluation` (installé par défaut pour mypy et la CI, hors dépendances d'exécution du paquet `usine`) ; binaires MongoDB et dump hors de tout dépôt git (`usine-lanes/externe/`), `mongod` sur 127.0.0.1 seulement.

**Never:** modifier `contrats/` ou `ports/` ; copier ou variante de la Baseline (AD-18) ; lancer `evaluation/` en CI (AD-20) ; versionner des données du dump ou des binaires ; réseau ou MongoDB dans les tests unitaires ; évaluation de la Baseline (Story 4.4).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Ticket ouvert puis résolu | Blocker créé lundi, résolu mercredi (changelog `resolution` vide → valeur) | entrée lundi, sortie mercredi ; stock 1 lundi et mardi, 0 mercredi | — |
| Réouverture | résolution puis `resolution` valeur → vide | nouvelle entrée le jour de la réouverture | — |
| Changement de priorité | Major → Blocker puis Blocker → Major | entrée au passage en Blocker, sortie à la sortie de Blocker ; priorité initiale = `fromString` du premier changement de priorité | — |
| Hors priorité maximale | ticket Major sans changement | aucun effet ; projet sans ticket éligible : aucune série | — |
| Week-end | événement un samedi (Europe/Paris) | rattaché au lundi suivant | — |
| Résolu sans changelog | `resolutiondate` présente, aucun item `resolution` | sortie à `resolutiondate` | — |
| Entrée et sortie le même jour | créé et résolu mardi | entrées 1, sorties 1, stock inchangé | — |
| Borne de fin | `fin` fourni | série jusqu'à `fin` (Jour ouvré), événements postérieurs ignorés | `fin` non ouvré : `UsineErreur` |
| Document incomplet | `fields.created` absent ou naïf | — | `UsineErreur` nommant la clé du ticket |

</intent-contract>

## Code Map

- `src/usine/contrats/prevision.py` -- `SCHEMA_SERIE_STOCK` (serie Utf8, date Date, stock/entrees/sorties Int64, non nuls) ; lecture seule (gelé).
- `src/usine/contrats/schemas.py` -- `valider(df, schema)` ; lecture seule.
- `src/usine/contrats/calendrier.py` -- `jour_ouvre_de`, `jours_ouvres`, `est_jour_ouvre` ; lecture seule.
- `src/usine/domaine/prevision/baseline.py:171` -- `_jours` : exige une série sans trou ni doublon de Jours ouvrés, Date d'arrêté présente ; c'est le consommateur aval (4.4), aucune modification (lane 4.2 en parallèle).
- `evaluation/__init__.py` -- paquet existant hors produit ; import-linter lui permet contrats, ports, domaine, composition.
- `pyproject.toml` -- pymongo 4.18.3 aujourd'hui dans `dependencies` ; `tests/depot/test_import_linter.py` (classement des dépendances, groupes compris) et `tests/depot/test_environnement.py` (version installée) restent verts si pymongo reste installé par défaut.
- `tests/conftest.py` -- interdit tout réseau hors boucle locale dans les tests.

## Tasks & Acceptance

**Execution:**
- `evaluation/zenodo/__init__.py` -- docstring du sous-paquet (FR-51, AD-20 hors CI).
- `evaluation/zenodo/conversion.py` -- `PRIORITES_MAXIMALES = frozenset({"Blocker", "Highest"})` ; `convertir_en_series(tickets: Iterable[Mapping[str, Any]], *, depot: str, priorites: frozenset[str] = PRIORITES_MAXIMALES, fin: date | None = None) -> pl.DataFrame` selon la matrice ; `serie` = `"{depot}/{clé projet}"` (clé projet = `fields.project.key`, sinon préfixe de `key`) ; série du premier jour d'événement à `fin` (défaut : dernier jour d'événement du projet) ; tri par `serie`, `date`.
- `evaluation/zenodo/chargement.py` -- `lire_tickets(client, base, collection)` : projection minimale (`key`, `fields.project`, `fields.priority`, `fields.created`, `fields.resolutiondate`, `changelog.histories`) ; `main` : `python -m evaluation.zenodo.chargement --uri mongodb://127.0.0.1:27017 --base … --collection … --sortie fichier.parquet`.
- `evaluation/zenodo/README.md` -- procédure du spike : sources officielles, sommes de contrôle, espace disque, extraction, `mongod` portable (`--bind_ip 127.0.0.1 --dbpath …`), `mongorestore` sélectif, organisation observée du dump (bases, collections, champs), résultats du spike (volumes, noms de priorité), arrêt de `mongod`.
- `tests/unit/evaluation/__init__.py`, `tests/unit/evaluation/zenodo/__init__.py`, `tests/unit/evaluation/zenodo/extrait_tickets.json`, `tests/unit/evaluation/zenodo/test_conversion.py` -- extrait figé fictif au format du dump (deux projets, une dizaine de tickets couvrant la matrice) ; un test par ligne de la matrice, valeurs exactes ; série validée par `SCHEMA_SERIE_STOCK` et acceptée par `prevoir_sortie` (appel réel de la Baseline sur une série convertie) ; déterminisme.
- `pyproject.toml`, `uv.lock` -- `uv remove pymongo` puis `uv add --group evaluation pymongo==4.18.3` ; `default-groups = ["dev", "evaluation"]`.

**Acceptance Criteria:**
- Given le spike conclu, when on lit `evaluation/zenodo/README.md`, then la procédure de téléchargement et de chargement est reproductible et l'organisation du dump est décrite.
- Given le dump chargé, when `chargement` convertit les tickets de priorité maximale d'un dépôt, then il produit des `SerieStock` validées par `SCHEMA_SERIE_STOCK`, en Jours ouvrés (ou, si le chargement réel échoue durablement, ce point est consigné reporté à la 4.4).
- Given la CI, when elle s'exécute, then rien sous `evaluation/` n'est lancé ; le test unitaire de la conversion sur l'extrait figé passe sans réseau ni MongoDB.
- Given les cinq contrôles, then ruff, ruff format, mypy, lint-imports et pytest passent ; `controle_lanes.py --branche lane/4-zenodo --base main` ne signale que `pyproject.toml` et `uv.lock`, justifiés ci-dessous.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 24 findings — high 0, medium 2, low 13, false 5, maybe-false 4
- findings:
  - `[false]` `[reject]` (blind) `uv.lock` absent du diff — exclu du diff de revue seulement ; `uv.lock` est régénéré (pymongo dans le groupe `evaluation`) et `uv sync --locked` passe.
  - `[low]` `[reject]` (blind) état final non recoupé avec `resolutiondate` (changelogs tronqués) — 4 tickets sur 9 474 d'IntelDAOS, limite documentée ; la correction ajoute une branche de réconciliation.
  - `[low]` `[reject]` (blind) troncature (`changelog.total`) non détectée — fonctionnalité additionnelle, cas marginal documenté.
  - `[low]` `[reject]` (blind) aucun compteur de diagnostic — fonctionnalité additionnelle hors intention.
  - `[maybe-false]` `[reject]` (blind) égalités d'instant entre historiques rejouées dans l'ordre du dump — sortie déterministe pour un même dump ; à trancher : fréquence d'historiques simultanés aux effets contradictoires ; au pire `low`.
  - `[low]` `[reject]` (blind) priorités comparées par nom exact — ensemble paramétrable (`--priorite`), noms observés au spike ; normalisation = complexité ajoutée.
  - `[medium]` `[patch]` (blind) `chargement.py` sans test — ajout de `tests/unit/evaluation/zenodo/test_chargement.py` (client simulé appliquant `PROJECTION`, codes de sortie, valeurs par défaut).
  - `[low]` `[patch]` (blind) erreurs MongoDB non capturées — `main` capture aussi `PyMongoError` (code 1, message), testé.
  - `[low]` `[reject]` (blind) Parquet sans métadonnées de provenance — fonctionnalité additionnelle ; la 4.4 fixe ses paramètres.
  - `[low]` `[patch]` (blind) README : pas de retour à la racine avant l'étape 5 — `RACINE=$PWD` puis `cd "$RACINE"`, note sur `mongod` lancé avec `&`.
  - `[false]` `[reject]` (blind) disposition des paquets de test fragile — `tests/unit` n'a pas d'`__init__.py` (pytest insère `tests/unit` en tête) : ajouter `tests/unit/evaluation/__init__.py` masquerait le vrai paquet `evaluation` ; l'absence est voulue.
  - `[low]` `[patch]` (edge) `PyMongoError` non capturée — même cause que la ligne ci-dessus, même correctif.
  - `[low]` `[reject]` (edge) `OSError` à l'écriture du Parquet — échec bruyant acceptable pour un outil d'évaluation manuel.
  - `[low]` `[patch]` (edge) projection `_id: 0` : ticket sans clé nommé `None` — `PROJECTION` lit `_id`, testé.
  - `[maybe-false]` `[reject]` (edge) clé dupliquée comptée deux fois — `key` unique par collection dans le dump ; à vérifier par un `distinct` ; au pire `low`.
  - `[maybe-false]` `[reject]` (edge) `resolutiondate` chaîne vide — l'API Jira v2 renvoie `null` ; aucune erreur sur les 5 dépôts du spike ; au pire `low`.
  - `[maybe-false]` `[reject]` (edge) item `priority` à `toString` nul — conversions du spike sans anomalie ; au pire `low`.
  - `[low]` `[reject]` (edge) casse des noms de priorité — même cause que la ligne « nom exact », même rejet.
  - `[false]` `[reject]` (edge) `tests/unit/evaluation/__init__.py` absent, écart à la spec — l'ajouter masquerait le paquet `evaluation` (voir plus haut) ; correction = modifier la spec.
  - `[false]` `[reject]` (edge) la spec omet `fields.status` dans la projection — la conversion en a besoin ; correction = modifier la spec.
  - `[medium]` `[patch]` (verification-gap) `PROJECTION` et `main` non testés — même entrée que la ligne « chargement.py sans test ».
  - `[low]` `[patch]` (verification-gap) `_id` exclu de la projection — même correctif que plus haut.
  - `[low]` `[patch]` (verification-gap) indice trompeur quand `--fin` précède tout événement — le message cite aussi `--fin`.
  - (intent-alignment, descriptif) extrait fictif plutôt que réel, lecteur couvert seulement par le spike, tests de `evaluation/` en CI : `[false]` `[reject]` — l'intention interdit de versionner des données du dump, exige un test unitaire sans réseau ni MongoDB, et AD-20 vise l'exécution d'`evaluation/` (le chargement), pas les tests unitaires de la conversion ; lecteur désormais testé par client simulé.

## Design Notes

**Reconstruction par ticket.** État initial à `created` : ouvert, priorité = `fromString` du premier item `priority` du changelog (sinon `fields.priority.name`). Les items `resolution` (vide → valeur : résolu ; valeur → vide : rouvert) et `priority` sont rejoués dans l'ordre de `histories[].created`. Si aucun item `resolution` mais `fields.resolutiondate` présente, résolution à cette date. Le ticket est « en stock » quand il est ouvert et de priorité maximale ; chaque passage hors stock → en stock est une entrée, l'inverse une sortie, au Jour ouvré `jour_ouvre_de(instant)`.

**Priorité maximale.** Les instances du dataset nomment différemment le niveau le plus haut (Apache : `Blocker` ; schéma Jira par défaut : `Highest`) ; l'ensemble est paramétrable, le défaut est confirmé par le spike.

**Fichiers hors lane.** `pyproject.toml` et `uv.lock` : consigne explicite d'Anaël (pymongo hors dépendances d'exécution de `usine`, en groupe `evaluation`, par `uv add`) ; aucun autre moyen de déplacer une dépendance. Le groupe est installé par défaut pour que mypy (qui contrôle `evaluation/`) résolve pymongo en CI.

## Verification

**Commands:**
- `uv run pytest -q tests/unit/evaluation` -- expected: tous verts.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: verts.
- `uv run python .github/scripts/controle_lanes.py --branche lane/4-zenodo --base main` -- expected: seuls `pyproject.toml` et `uv.lock` hors lane.

## Auto Run Result

Status: done (reprise après coupure de quota ; spec reprise au statut `in-review`, revue unique en mode économique, sans revue de suivi).

**Livré.** Conversion pure `evaluation.zenodo.conversion.convertir_en_series` (tickets bruts Jira v2 → `SerieStock` dense en Jours ouvrés par projet), lecteur pymongo `evaluation.zenodo.chargement` (CLI → Parquet), procédure et résultats du spike dans `evaluation/zenodo/README.md`, pymongo déplacé dans le groupe `evaluation`. Chargement réel effectué : 5 dépôts restaurés dans un `mongod` portable (127.0.0.1 seulement, hors dépôt sous `usine-lanes/externe/`) ; reconversion vérifiée après revue (Hyperledger 24 séries / 13 691 lignes, SecondLife 2 séries).

**Fichiers.**
- `evaluation/zenodo/__init__.py` : docstring du sous-paquet.
- `evaluation/zenodo/conversion.py` : rejeu des tickets, Entrées/Sorties, série validée.
- `evaluation/zenodo/chargement.py` : projection minimale (plus `_id`), CLI, erreurs `UsineErreur` et `PyMongoError` en code 1.
- `evaluation/zenodo/README.md` : procédure reproductible, organisation du dump, résultats, limites.
- `tests/unit/evaluation/zenodo/extrait_tickets.json` : extrait figé fictif au format du dump.
- `tests/unit/evaluation/zenodo/test_conversion.py` : une ligne de matrice par test, Baseline, déterminisme.
- `tests/unit/evaluation/zenodo/test_chargement.py` : lecteur avec client MongoDB simulé.
- `pyproject.toml`, `uv.lock` : pymongo en groupe `evaluation` (fichiers hors lane justifiés).

**Revue.** 24 constats : 5 corrections appliquées (1 entrée medium : tests du lecteur ; 4 low : `PyMongoError`, `_id` projeté, message `--fin`, README), 0 reporté, 19 rejetés (motifs au Review Triage Log). `tests/unit/evaluation/__init__.py` volontairement absent (masquerait le paquet `evaluation`).

**Revue de suivi recommandée :** false (aucun high ; une seule entrée medium corrigée).

**Vérification.** `pytest tests/unit/evaluation` : 30 verts ; ruff, ruff format, mypy, lint-imports, pytest complet : verts ; chargement réel relancé sur Hyperledger et SecondLife.

**Risques résiduels.** Changelogs tronqués (4 tickets IntelDAOS) et noms de priorité propres à chaque instance (`--priorite`) ; borne commune de l'évaluation à fixer en 4.4.
