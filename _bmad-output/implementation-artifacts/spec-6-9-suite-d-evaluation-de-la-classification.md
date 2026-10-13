---
title: "Story 6.9 : Suite d'évaluation de la classification"
type: 'feature'
created: '2026-10-13'
status: 'done'
baseline_revision: '855e0135b6031df08223b23283269b47ff04d28a'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Rien ne mesure la classification des Causes racines (SM-9 : F1 macro ≥ 0,8 sur la vérité terrain du générateur et, séparément, sur 30 tickets rédigés à la main). `evals/` n'a que la suite de l'explication.

**Approach:** Créer `evals/classification/` sur le modèle d'`evals/explication/` : 30 tickets manuels versionnés (cause attendue et réponse enregistrée), une source « générateur » lue dans `journal.jsonl` et `verite_terrain.json` d'un répertoire de données, un exécuteur qui passe chaque Anomalie par la vraie tâche `classer` (passerelle comprise, façade de composition), et des métriques pures (précision, rappel, F1 par Cause racine, F1 macro, exactitude, matrice de confusion) publiées par source. Rejeu hors réseau par défaut (CI) ; exécution réelle avec `--reel`.

## Boundaries & Constraints

**Always:** `evals` n'importe que contrats, ports, domaine et `usine.composition` (import-linter) : nouvelle façade `construire_classificateur` qui partage avec `construire_explicateur` la construction de la passerelle d'évaluation (cache en mémoire). Seule `evals/classification` lit `verite_terrain.json` (AD-23). Garde-fou AD-19 : l'en-tête du Journal doit porter le `version_corpus`/`modele_corpus` du Corpus versionné, non provisoire (`gabarits-provisoires` refusé), et le modèle de classification doit différer de `modele_corpus`, sinon `UsineErreur` ; le résultat publie les deux. Textes de la source générateur = `domaine.instantanes.tickets_textes(evenements, entete.date_generation)`, Anomalies seulement. F1 macro = moyenne des F1 des Causes racines présentes dans la vérité ou les propositions (F1 = 0 si division par zéro) ; une Anomalie non classée (plafond) compte comme fausse et est publiée dans `non_classes`. `sm9_atteint` = les deux F1 macro ≥ 0,8, `null` si une source manque.

**Never:** lancer `--reel` dans les tests ou la CI ; toucher `rendu/`, `ia/agent`, `evals/agent`, `contrats/`, `ia/classification.py` ou son prompt ; écrire dans `donnees/` (hors table de pseudonymes du mode réel, comme la 6.8).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Rejeu manuels | 30 tickets, réponses enregistrées | résultat JSON : source `manuels`, F1 par cause et macro, versions | — |
| Rejeu générateur | `--reponses <résultat antérieur>` et `--donnees` | prédictions rejouées, F1 de la source `generateur` | clé sans réponse : `UsineErreur` nommant la clé |
| Générateur sans réponses en rejeu | source `generateur` sans `--reponses` | — | `UsineErreur` explicite |
| Corpus provisoire | en-tête `gabarits-provisoires` ou ≠ Corpus versionné | — | `UsineErreur` : régénérer avec `usine generer` |
| AD-19 | modèle de classification = `modele_corpus` | — | `UsineErreur` nommant les deux |
| Vérité incohérente | clé de vérité absente du Journal ou Anomalie sans vérité, fichier absent ou mal formé | — | `UsineErreur` nommant le fichier |
| Tickets manuels invalides | ≠ 30 tickets, clé en double, cause inconnue | — | `UsineErreur` nommant le fichier |

</intent-contract>

## Code Map

- `src/usine/ia/classification.py:142` -- (lecture seule) `classer(passerelle, textes, date_arrete, contexte, plafond_eur)` ; `ContexteClassification(passage_id, version_donnees, version_grille, gabarit)`, `lire_prompt()`.
- `src/usine/composition.py:391-504` -- `_CacheMemoire`, `Explicateur`, `construire_explicateur` : extraire la construction passerelle/fermeture en `_passerelle_evaluation` et l'ajouter `Classificateur`/`construire_classificateur` juste après.
- `src/usine/composition.py:507,530` -- `_config_llm` (garde-fou AD-19 sur le Corpus versionné), `_modele_corpus`.
- `src/usine/domaine/instantanes.py:145` -- `tickets_textes(evenements, date_arrete)` (table `SCHEMA_TICKET_TEXTE`).
- `src/usine/contrats/evenements.py:50,108` -- `Evenement`, `EnteteJournal` (`version_corpus`, `modele_corpus`, `date_generation`).
- `src/usine/contrats/passage.py:234` -- `CHEMIN_VERITE_TERRAIN`, `CHEMIN_JOURNAL` ; `src/usine/generateur/journal.py:1097` format `{clé: cause}`.
- `evals/explication/suite.py` -- modèle de `FournisseurEnregistre`, `PseudonymiseurIdentite`, `ecrire_resultat`, CLI.
- `src/usine/adaptateurs/llm/registre.py:58` -- Haiku 5.5 : 0,1/0,5 $ par MTok, 50 req/min.

## Tasks & Acceptance

**Execution:**
- `src/usine/composition.py` -- `_passerelle_evaluation` partagé ; `Classificateur` appelable `(textes) -> (sorties, traces)` portant `version_prompt`, `version_modele` (modèle de la tâche classification), `fermer()` ; `construire_classificateur(racine, fournisseur=None, pseudonymiseur=None)`.
- `evals/classification/tickets.py` -- `TicketManuel` (clé, domaine, titre, description, cause attendue, réponse enregistrée) et `charger_tickets_manuels` (exactement 30, clés uniques) ; `charger_source_generateur(donnees, chemin_corpus)` (en-tête, textes des Anomalies, vérité, contrôles de cohérence et de Corpus).
- `evals/classification/tickets_manuels.json` -- 30 tickets rédigés à la main, toutes les Causes racines couvertes (4 ou 5 chacune), domaines variés, réponses enregistrées dont quelques erreurs réalistes.
- `evals/classification/metriques.py` -- `evaluer(verite, propositions) -> dict` pur.
- `evals/classification/suite.py`, `__main__.py`, `__init__.py` -- `FournisseurEnregistre` (réponses par clé), exécution par source, garde-fou AD-19, `ecrire_resultat`, ajout à `historique.jsonl` en mode réel ; CLI `python -m evals.classification executer [--reel] [--source manuels|generateur|toutes] [--donnees D] [--reponses R] [--sortie S] [--historique H]` (source par défaut : `toutes` avec `--reel` ou `--reponses`, sinon `manuels`).
- `evals/classification/README.md` -- protocole, commandes (régénérer le Journal avec le Corpus définitif dans un répertoire à part), coût estimé.
- `tests/unit/evals/classification/test_suite.py` -- métriques, matrice I/O, rejeu des 30 tickets, rejeu générateur sur un mini-Journal, CLI ; `tests/unit/test_composition*` non modifiés sauf besoin.

**Acceptance Criteria:**
- Given les 30 tickets versionnés, when `uv run python -m evals.classification executer` s'exécute sans réseau, then `evals/classification/resultats/<horodatage>.json` publie le F1 par Cause racine et le F1 macro de la source `manuels`, avec versions de prompt et de modèle.
- Given un Journal généré avec le Corpus définitif et sa vérité terrain, when la suite s'exécute en `--reel` (ou en rejeu avec `--reponses`), then le F1 macro de la source `generateur` est publié séparément de celui des tickets manuels, avec `modele_corpus` et le modèle de classification, et `sm9_atteint`.
- Given la CI, when `uv run pytest -q` s'exécute, then la suite rejouée tourne sans appel réseau.

## Spec Change Log

## Review Triage Log

### 2026-10-13 — Review pass (mode économique : Edge Case Hunter seul ; Blind Hunter, Verification Gap et Intent Alignment sautés)
- verdicts: 11 findings — high 0, medium 0, low 9, false 2, maybe-false 0
- findings:
  - `[false]` `[reject]` `--reel` sur `toutes` : 30 appels payés avant l'échec AD-19 de la source générateur — inatteignable : `charger_source_generateur` exige l'en-tête égal au Corpus versionné, et `construire_classificateur` (via `_config_llm`) refuse déjà, avant tout appel, un modèle de classification égal au `modele_corpus` de ce Corpus.
  - `[low]` `[reject]` échec de la source générateur après les manuels : résultat des manuels perdu — au plus 30 appels Haiku (~0,003 €) ; écriture partielle = nouvelle branche non justifiée.
  - `[low]` `[reject]` une passerelle par source, donc deux plafonds de 2 € — coût estimé de toute la suite ~0,35 € : plafond inatteignable.
  - `[low]` `[reject]` résultat rejoué sans `modele_classification` : AD-19 non vérifié — tout résultat de la suite porte ce champ ; seul un fichier modifié à la main l'omet.
  - `[low]` `[reject]` `--reponses` d'un autre Journal à clés communes — erreur d'usage ; le résultat publie `journal`, `version_corpus` et `date_generation` pour la contrôler ; garde supplémentaire non justifiée.
  - `[low]` `[reject]` `--reel` avec `--reponses` : réponses ignorées — combinaison sans usage, garde CLI non justifiée.
  - `[low]` `[reject]` `--source manuels` avec `--reponses` : réponses ignorées — idem.
  - `[low]` `[patch]` `--reponses` non UTF-8 : `UnicodeDecodeError` hors `UsineErreur` — corrigé : clause `UnicodeDecodeError` dans `lire_reponses` ; test `test_fichiers_non_utf8_refuses_en_nommant_le_fichier`.
  - `[low]` `[patch]` `journal.jsonl` non UTF-8 : trace au lieu d'une erreur nommant le fichier — corrigé dans `_lire_journal`, même test.
  - `[low]` `[reject]` deux exécutions dans la même seconde écrasent le résultat — improbable pour une suite lancée à la main (même choix qu'en 6.8).
  - `[false]` `[reject]` horloge naïve — l'horloge n'est injectée que par les tests, toujours en UTC (même constat qu'en 6.8).

## Design Notes

Réponses rejouées pour la source générateur : un résultat antérieur (`propositions` `{clé: cause}`) sert d'enregistrement, ce qui rend un run réel rejouable hors réseau. Coût du mode réel (Haiku 5.5) : ~3 150 appels × ~700 jetons d'entrée et ~100 de sortie, soit ~0,40 $ (~0,35 €) ; durée bornée par 50 req/min, environ 65 min.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert.
- `uv run python -m evals.classification executer --sortie <tmp>` -- expected: F1 de la source `manuels` publié, sans réseau.

## Auto Run Result

- **Résumé** : suite `evals/classification/` (SM-9) : 30 tickets manuels versionnés et source « générateur » (Journal et vérité terrain d'un répertoire de données), passés par la vraie tâche `classer` via la façade `construire_classificateur` ; F1 par Cause racine, F1 macro, exactitude et matrice de confusion publiés par source ; garde-fou AD-19 (Corpus définitif exigé, modèle de classification ≠ `modele_corpus`) ; rejeu hors réseau par défaut, `--reel` séparé, historique en mode réel.
- **Fichiers** :
  - `src/usine/composition.py` — `_passerelle_evaluation` partagé, `Classificateur` / `construire_classificateur`.
  - `evals/classification/tickets.py`, `tickets_manuels.json` — 30 tickets manuels, chargement et contrôles de la source générateur.
  - `evals/classification/metriques.py` — métriques pures.
  - `evals/classification/suite.py`, `__main__.py`, `__init__.py` — fournisseur enregistré, exécution par source, CLI, historique.
  - `evals/classification/README.md` — protocole, commandes, coût (~0,35 €, ~65 min).
  - `tests/unit/evals/classification/test_suite.py` — 34 tests.
- **Revue** : 11 constats ; 2 corrigés (low), 0 différé, 9 rejetés (motifs au journal).
- **Revue de suivi** : `false` (aucun high ni medium corrigé).
- **Vérification** : `ruff check`, `ruff format --check`, `mypy`, `lint-imports` (14 contrats) verts ; `pytest -q` 2636 passés, 1 sauté (avant correctif), suite classification 34 passés après correctif ; rejeu CLI : F1 macro manuels 0,873.
- **Risques résiduels** : le rejeu retrouve la clé dans le bloc de données du prompt (cassera si le gabarit change de forme) ; constantes `CHEMIN_CORPUS`/`MODELE_GABARITS` recopiées (test d'alignement).
- **Correctif après exécution réelle (2026-10-13)** : le premier `--reel` s'est arrêté après ~110 s sur un `UnexpectedModelBehavior` de Haiku 5.5 pour une Anomalie (constat « échec d'une source après les manuels » de la revue, rejeté à tort comme low : un seul échec perdait tout le run). Le mode réel classe désormais une Anomalie à la fois, consigne les échecs isolés dans `erreurs_fournisseur` (Anomalie non classée, comptée fausse) et s'arrête après 10 échecs consécutifs ; 2 tests ajoutés.
