---
title: 'Contrats v1.1 : évolution mineure et rétrocompatible des contrats'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '0948cdb7a9c1dcb9843fa7e7ba49d018ed4c6d48'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-usine-migration-jira-demo-2026-10-10/ARCHITECTURE-SPINE.md'
warnings: ['multiple-goals', 'oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Plusieurs paramètres décidés par Anaël le 2026-10-12 sont codés en dur faute de place dans les contrats gelés v1.0.0 : Scénarios de démo A, B, C (`generateur/scenarios.py`), paramètres de la Baseline (H-7) et du Risque (H-8), décalage J-5 (H-19), valeur projetée d'un Risque (rendue à côté par `RisqueProjete`). La borne haute de volumétrie (H-2) passe par ailleurs à 4 000 Anomalies.

**Approach:** PR de contrats dédiée (AD-2) : ajouts optionnels avec défaut dans `contrats/config.py` et `contrats/prevision.py`, clés correspondantes dans les YAML livrés, lecture des Scénarios par le générateur depuis la configuration, puis `CONTRATS_VERSION` 1.0.0 → 1.1.0 dans le dernier commit.

## Boundaries & Constraints

**Always:** changements additifs (champs optionnels avec défaut, aucun renommage ni retrait) ; un YAML ou un JSON v1.0.0 existant se valide toujours ; un Passage 1.0.0 reste lisible (même majeure) ; chaque clé des YAML livrés est commentée (`test_commentaires`) ; `test_calage` reste vert sans changer ses attendus ; la Génération à graine et date fixées produit les mêmes événements qu'avant.

**Never:** brancher la lecture des paramètres Baseline/Risque/décalage dans la Chaîne, le domaine, la consultation ou le rendu (lanes L3, L4, L5, L7) ; renseigner la valeur projetée dans `domaine/prevision/risque.py` (L4 en cours) ; modifier les tests existants du générateur (`test_calage.py`, `test_scenarios.py`, `test_journal.py` : L1 en cours) ; toucher `sprint-status.yaml` ou `journal-run-autonome.md`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Programme livré | `config/programme.yaml` avec `scenarios` | `generer` sans `scenarios` applique ceux de la configuration ; égaux à `SCENARIOS_PAR_DEFAUT` | — |
| Clé absente | `programme_reduit.yaml` (sans `scenarios`) | comportement actuel : `SCENARIOS_PAR_DEFAUT` réduits par `scenarios_applicables` | — |
| `--sans-scenarios` | CLI, clé présente | `AUCUN_SCENARIO`, la configuration est ignorée | — |
| Scénario désactivé | `scenarios: {sortie: …}` sans `enlisement` ni `menace` | seul A appliqué | — |
| Scénario incohérent | Entité inconnue, Entité partagée, semaine > `nb_semaines`, semaine 0, taux > 1, poids ≤ 0, `part_bloquantes + part_majeures > 1`, `taux_ko_hausse` vide | refus au chargement | `ValidationError` (UsineErreur via `charger_yaml`) |
| `chaine.yaml` v1.0 | `palier: 1` seul | `prevision` aux défauts H-7/H-8 (10, 10, 5, 20 ; 10, 5), `decalage_comparaison` = 5 | — |
| Paramètre chaîne invalide | `0`, `true`, `2.5`, clé inconnue | refus | `ValidationError` |
| Risque v1.0 | JSON sans `valeur_projetee_*` | lu, champs à `None` | — |
| Valeur projetée incomplète | numérateur sans dénominateur (ou l'inverse), dénominateur ≤ 0 | refus | `ValidationError` |

</intent-contract>

## Code Map

- `src/usine/contrats/config.py` -- `_ModeleConfig` (non strict, YAML), `ConfigProgramme._references` (contrôles croisés à étendre), `ConfigChaine` (strict, `_entier_exact`) : y ajouter `prevision` et `decalage_comparaison`.
- `src/usine/contrats/prevision.py:105` -- `RisqueEntreeRouge` ; convention des fractions en paire `numerateur`/`denominateur` entiers (H-26).
- `src/usine/contrats/versions.py:9` -- `CONTRATS_VERSION`.
- `src/usine/generateur/scenarios.py` -- dataclasses `ScenarioSortie`, `ScenarioEnlisement`, `ScenarioMenace`, `Scenarios`, `SCENARIOS_PAR_DEFAUT` (valeurs à reporter dans le YAML) ; docstring à mettre à jour (report levé).
- `src/usine/generateur/journal.py:881` -- choix des Scénarios quand `scenarios is None`.
- `src/usine/generateur/cli.py` -- `--sans-scenarios` → `AUCUN_SCENARIO`, sinon `None` (inchangé hors aide).
- `src/usine/domaine/prevision/baseline.py:53`, `risque.py:44` -- `ParametresBaseline`, `ParametresRisque` : valeurs par défaut à reproduire (lecture seule).
- `src/usine/domaine/meteo.py:66` -- `DECALAGE_IND8 = 5` (lecture seule, consommateur futur).
- `config/programme.yaml`, `config/chaine.yaml` -- YAML livrés, chaque clé commentée.
- `docs/QUESTIONS.md:14` -- H-2.
- `tests/unit/contrats/test_versions.py`, `test_evenements.py:140`, `test_llm.py:70`, `test_passage.py:103,210,218,222` -- attendus « 1.0.0 » à ajuster au bump.
- `tests/unit/config/test_commentaires.py` -- impose un commentaire par clé YAML.

## Tasks & Acceptance

**Execution:**
- `src/usine/contrats/config.py` -- ajouter `ConfigScenarioSortie`, `ConfigScenarioEnlisement`, `ConfigScenarioMenace`, `ConfigScenarios` (mêmes champs que les dataclasses, tous requis sauf les trois Scénarios de `ConfigScenarios`, `None` = désactivé), `ConfigProgramme.scenarios: ConfigScenarios | None = None` avec contrôles croisés ; `ConfigBaseline`, `ConfigRisque`, `ConfigPrevision` (strict, défauts H-7/H-8), `ConfigChaine.prevision` et `ConfigChaine.decalage_comparaison` (défaut 5, ≥ 1) -- contrats additifs.
- `src/usine/contrats/prevision.py` -- `valeur_projetee_numerateur: int | None = None`, `valeur_projetee_denominateur: int | None = None` (> 0), tous deux ou aucun -- décision 4.
- `src/usine/generateur/scenarios.py` -- `scenarios_de_config(ConfigScenarios) -> Scenarios` ; docstring -- décision 1.
- `src/usine/generateur/journal.py` -- `scenarios is None` : configuration si `config.scenarios`, sinon `SCENARIOS_PAR_DEFAUT` ; réduits ensuite comme aujourd'hui -- décision 1.
- `src/usine/generateur/cli.py` -- aide de `generer` : Scénarios lus dans la configuration -- cohérence.
- `config/programme.yaml` -- bloc `scenarios` (valeurs de `SCENARIOS_PAR_DEFAUT`), `anomalies_max: 4000`, commentaires d'en-tête et de volumétrie -- décisions 1 et 5.
- `config/chaine.yaml` -- `prevision` (baseline, risque) et `decalage_comparaison`, commentés -- décisions 2 et 3.
- `docs/QUESTIONS.md` -- H-2 : « modifiée (12/10/2026) : 3 000 à 4 000 Anomalies » -- décision 5.
- `tests/unit/contrats/test_config_v1_1.py` -- chargement des YAML livrés, défauts, refus (matrice) -- décisions 1 à 3.
- `tests/unit/contrats/test_prevision.py` -- valeur projetée : défaut, aller-retour JSON, JSON v1.0 lu, refus -- décision 4.
- `tests/unit/generateur/test_scenarios_config.py` -- configuration livrée = `SCENARIOS_PAR_DEFAUT` ; Journal identique avec et sans clé ; Scénario désactivé ; `--sans-scenarios` ignore la clé -- décision 1.
- `src/usine/contrats/versions.py` + tests à attendu « 1.0.0 » -- 1.1.0, en dernier commit ; test qu'une enveloppe 1.0.0 reste lisible -- décision 6.

**Acceptance Criteria:**
- Given le dépôt livré, when `usine donnees generer --date-generation 2026-10-12` puis `usine rapport --date-arrete <dernier Jour ouvré>`, then un Passage est publié et la sortie liste « A (ENT-A), B (ENT-B), C (ENT-C) ».
- Given la configuration livrée, when `pytest tests/unit/generateur/test_calage.py`, then vert, fichier inchangé.
- Given le dernier commit, when on lit `CONTRATS_VERSION`, then `1.1.0` et une enveloppe `contrats_version: 1.0.0` se lit sans erreur.

## Spec Change Log

### 2026-10-12 — Écarts constatés à l'implémentation (sans retour à la base)
- **Semaine au-delà de `nb_semaines`** : la ligne « Scénario incohérent » de la matrice demandait un refus au chargement, en contradiction avec l'invariant « `test_calage` vert sans changer ses attendus » (`_programme_court` raccourcit le Programme livré à 5 semaines alors que A bascule en semaine 6 et attend A ignoré). L'invariant, issu de la décision d'Anaël, l'emporte : une telle semaine est acceptée au chargement et le générateur ignore le Scénario, comme un Scénario par défaut ; la semaine 0 reste refusée. Design Notes « Contrôle des semaines » amendées. État écarté : un `test_calage` rouge.
- **`tests/unit/generateur/test_journal.py:446`** : l'attendu `(3000, 5000)` passe à `(3000, 4000)`, seule modification d'un test existant du générateur, imposée par la décision 5.
- **Fichiers hors liste** : `outils/mesurer_nfr2.py` (`scenarios: {}`, ses Entités ENT-01 à ENT-10 étant refusées par le contrôle d'Entité connue) ; regex de version de `tests/unit/adaptateurs/journal/test_source_journal.py` et `tests/unit/consultation/test_passage.py`.
- KEEP : Scénarios livrés = `SCENARIOS_PAR_DEFAUT` (Journal identique), paramètres de Chaîne non branchés, valeur projetée non renseignée par le domaine.

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 23 findings — high 0, medium 3, low 14, false 6, maybe-false 0
- findings:
  - `[low]` `[patch]` (blind) `scenarios:` nul réactive les défauts, contrairement au commentaire — commentaire corrigé (absent ou nul : défauts ; `{}` : aucun) et test `test_cle_vide_desactive_tout`.
  - `[low]` `[reject]` (blind) Scénario configuré hors historique ignoré sans avertissement — choix imposé par `test_calage` (Spec Change Log) ; la CLI liste les Scénarios appliqués ; un avertissement ajouterait une branche.
  - `[low]` `[patch]` (blind) paramètres de `ConfigChaine` présentés comme actifs mais lus par personne — branchement exclu par l'intention (L5) ; en-tête de `chaine.yaml` précisant qu'ils ne sont pas encore lus.
  - `[false]` `[reject]` (blind) fenêtre glissante de H-19 absente — l'intention ne demande que le décalage J-5.
  - `[low]` `[reject]` (blind) contrôles croisés (`risque.fenetre ≥ 2`, profondeur ≥ fenêtre) — le domaine (`ParametresRisque`, `ParametresBaseline`) n'impose que ≥ 1 ; gardes supplémentaires pour un cas improbable.
  - `[low]` `[patch]` (blind) valeur projetée non renseignée, docstring rattachée au seul dénominateur, pas de contrôle de franchissement — non-renseignement voulu (L4) ; une docstring par champ ajoutée ; contrôle de franchissement rejeté (garde supplémentaire).
  - `[false]` `[reject]` (blind) texte d'hypothèse H-2 et epics.md toujours à 5 000 — l'intention fixe exactement le statut de H-2 (« rien d'autre »).
  - `[false]` `[reject]` (blind) lecture 1.0.0 testée seulement sur enveloppe et manifeste — `tests/fixtures/reference/journal.jsonl` (en-tête 1.0.0) est relu par la suite existante ; la métadonnée Parquet passe par le même `verifier_version`.
  - `[low]` `[reject]` (blind) règles de validation dupliquées entre `ConfigScenario*` et dataclasses, idiomes d'entier multiples — dette de développeur sans défaut observé ; le test de correspondance champ à champ couvre la conversion.
  - `[low]` `[patch]` (blind) `mesurer_nfr2` neutralise les Scénarios implicitement — `donnees["scenarios"] = {}`.
  - `[low]` `[patch]` (blind) tests faibles (`"prevision"` en sous-chaîne) — `test_chaine_livree_aux_valeurs_par_defaut` vérifie toutes les clés ; `9` en dur et Scénario partiel rejetés (cosmétique, choix de contrat).
  - `[low]` `[patch]` (edge) `scenarios:` commenté = nul = défauts — même cause que la première ligne, même correctif.
  - `[low]` `[reject]` (edge) Entité retirée de `entites` mais nommée par un Scénario : tout `programme.yaml` refusé — échec bruyant nommant fichier et Entité, cohérent avec le contrôle des Vagues.
  - `[medium]` `[patch]` (edge) chaque Risque sérialisé porte deux clés `null`, illisible par un lecteur 1.0.0 — `model_serializer` qui omet les clés non renseignées ; tests d'omission et d'aller-retour.
  - `[low]` `[reject]` (edge) flottant YAML `3e-2` lu comme texte et refusé — cas improbable, refus explicite.
  - `[low]` `[patch]` (edge) paramètres de Chaîne acceptés mais ignorés — même correctif que la troisième ligne.
  - `[medium]` `[patch]` (verification-gap) correspondance champ à champ de `scenarios_de_config` testée sur les seules valeurs par défaut — `test_correspondance_de_chaque_champ` avec des valeurs distinctes non par défaut.
  - `[low]` `[reject]` (verification-gap) semaine au-delà de `nb_semaines` acceptée contre la matrice — le correctif serait d'éditer la spec ; écart consigné au Spec Change Log.
  - `[false]` `[reject]` (intent) décisions 2 et 3 limitées au contrat, `fenetre` en plus, placement dans `ConfigChaine` — conforme à l'intention (« ne branche pas ») ; `fenetre` reproduit `ParametresRisque` pour que L5 le construise entier.
  - `[medium]` `[patch]` (intent) deux champs au lieu d'un et forme JSON modifiée — paire numérateur/dénominateur conforme à H-26 ; forme JSON rétablie par le correctif d'omission ci-dessus.
  - `[low]` `[reject]` (intent) règle « Entité inconnue » plus stricte que le générateur, `mesurer_nfr2` touché, paramètres en double — même cause que le refus d'Entité ci-dessus ; le double est le repli exigé « en l'absence de la clé ».
  - `[false]` `[reject]` (intent) borne 4 000 sans effet sur les données — voulu (Journal identique) ; le statut de H-2 est celui demandé.
  - `[false]` `[reject]` (intent) ordre des commits et bout en bout non observables — commits séparés à la finalisation, `usine donnees generer` puis `usine rapport` exécutés.

## Design Notes

**Fichiers hors lane** (évolution de contrats autorisée par Anaël, pas de lane) : `src/usine/contrats/`, `src/usine/generateur/`, `config/`, `docs/QUESTIONS.md`, tests associés.

**Placement.** Baseline, Risque et décalage J-5 vont dans `ConfigChaine` (`config/chaine.yaml`) : c'est la configuration lue par la composition seule (AD-8), qui construira `ParametresBaseline`, `ParametresRisque` et passera le décalage aux étapes (L5). La Grille est écartée : la modifier changerait `version_grille`. Les contrats ne dépendent pas du générateur (lint-imports) : les modèles de Scénarios sont des miroirs Pydantic des dataclasses, sans valeur par défaut métier (les Entités de la démo restent dans le YAML et dans `SCENARIOS_PAR_DEFAUT`, repli en l'absence de clé).

**Contrôle des semaines.** Une semaine de Scénario configuré doit être ≥ 1 ; une semaine au-delà de `nb_semaines` est acceptée au chargement et le générateur ignore ce Scénario, comme pour les défauts (`test_calage` raccourcit le Programme livré ; voir Spec Change Log).

**Volumétrie.** `anomalies_max` 5 000 → 4 000 ne change pas le tirage : le maximum effectif est déjà `min(anomalies_max, 8 × 500) = 4 000`, puis Σ plafonds = 3 600.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert.
- `uv run usine donnees generer` puis `uv run usine rapport --date-arrete <dernier Jour ouvré>` -- expected: Passage publié.

## Auto Run Result

Status: done

**Résumé.** Contrats 1.1.0, additifs : clé optionnelle `scenarios` de `ConfigProgramme` (Scénarios A, B, C déplacés dans `config/programme.yaml`, lus par le générateur, repli `SCENARIOS_PAR_DEFAUT` sans la clé) ; `ConfigChaine.prevision` (Baseline H-7, Risque H-8) et `ConfigChaine.decalage_comparaison` (H-19) avec défauts, non branchés ; `RisqueEntreeRouge.valeur_projetee_numerateur/denominateur` (défaut `None`, omis du JSON quand non renseignés) ; `anomalies_max` 4 000 et H-2 modifiée ; `CONTRATS_VERSION` 1.1.0 dans le dernier commit.

**Fichiers.**
- `src/usine/contrats/config.py` — modèles de Scénarios, de Prévision, champs optionnels de `ConfigProgramme` et `ConfigChaine`.
- `src/usine/contrats/prevision.py` — valeur projetée optionnelle d'un Risque, sérialisation sans clés vides.
- `src/usine/contrats/versions.py` — 1.1.0.
- `src/usine/generateur/scenarios.py`, `journal.py`, `cli.py` — lecture des Scénarios depuis la configuration.
- `config/programme.yaml`, `config/chaine.yaml` — nouvelles clés commentées, borne 4 000.
- `docs/QUESTIONS.md` — statut de H-2.
- `outils/mesurer_nfr2.py` — `scenarios: {}` pour son Programme ENT-01 à ENT-10.
- Tests : `tests/unit/contrats/test_config_v1_1.py`, `tests/unit/generateur/test_scenarios_config.py` (nouveaux) ; `test_prevision.py`, `test_passage.py`, `test_inventaire.py`, `test_versions.py`, `test_evenements.py`, `test_llm.py`, `test_source_journal.py`, `consultation/test_passage.py`, `generateur/test_journal.py` (ajustés).

**Revue.** 23 constats : 9 lignes corrigées (2 entrées medium, 7 low), 14 rejetées (motifs au Review Triage Log), aucun report.

**Revue de suivi recommandée : oui** (2 entrées medium corrigées : 2 medium, 0 high). Risque non vérifié : le `model_serializer` enveloppant de `RisqueEntreeRouge` n'a été éprouvé que par les tests unitaires ; sa combinaison avec l'écriture de `previsions.json` et des traces par `chaine/etapes.py` une fois la valeur projetée renseignée (L4) reste à observer.

**Vérification.** ruff, ruff format, mypy, lint-imports : verts ; pytest : 1938 réussis, 1 ignoré ; `usine donnees generer --date-generation 2026-10-12` (Scénarios A, B, C appliqués) puis `usine rapport --date-arrete 2026-10-09` : Passage publié.

**Risques résiduels.** Consommateurs à brancher : `ConfigChaine.prevision` et `decalage_comparaison` (L5, composition ; L3/L5 pour `DECALAGE_IND8`) ; valeur projetée (L4, `domaine/prevision/risque.py` ; rendu L5/L7). Un lecteur 1.0.0 refuse un Risque dont la valeur projetée est renseignée (`extra="forbid"`).
