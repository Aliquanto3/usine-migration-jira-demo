---
title: 'Story 6.5 : Répartition des Causes racines'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'f8e247427284e173caaa43e9836060003d477d28'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Les `SortieClassification` de la 6.4 sont publiées, mais aucune étape ne produit `repartition_causes.parquet` : l'Explication sourcée (6.6) affiche « non disponible » et l'onglet Commentaires n'a pas de répartition. Par ailleurs, classer tout le stock coûte environ 10 € sur `claude-sonnet-5-5`.

**Approach:** Fonction pure `domaine.causes.repartition` (compte entier et part par Entité et Cause racine des Anomalies ouvertes classées à la Date d'arrêté), appelée par une étape `repartition_causes` du Palier 2 entre `classification` et `explications` ; l'explication la lit déjà et affiche désormais compte et part. Décision orchestrateur : la clé existante `modeles_par_tache` de `config/llm.yaml` est branchée (fournisseur dédié par tâche dans la passerelle), classification réglée sur `claude-haiku-5-5`, prix de Haiku 5.5 ajouté au registre.

## Boundaries & Constraints

**Always:** seule `domaine.causes.repartition` calcule la répartition (AD-9) ; fonction pure, déterministe, sans E/S ; l'étape lit via le port `Consultation` (`classification()`, `anomalies(date)`), n'écrit rien elle-même ; contrats 1.5 dans un commit dédié `Feat: contrats 1.5, …` (colonne `part` de `SCHEMA_REPARTITION_CAUSES`, ajout additif), ligne d'amendement au spine, `CONTRATS_VERSION` 1.5.0 ; un fournisseur injecté (tests) sert toutes les tâches ; aucun appel réseau dans les tests.

**Never:** toucher `rendu/` ; recalculer la répartition ailleurs (explication, Consultation, rendu) ; écrire une Cause racine dans Jira ; remanier `passerelle.py` au-delà du choix du fournisseur par tâche (fichier commun avec la lane 6.7).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Nominal | ENT-A : 3 Anomalies ouvertes (2 `parametrage`, 1 `donnees`) classées | lignes `(D, ENT-A, parametrage, 2, 2/3)`, `(D, ENT-A, donnees, 1, 1/3)` | — |
| Anomalie ouverte non classée (plafond) | ouverte sans `SortieClassification` | ignorée ; parts calculées sur les classées | — |
| Classification d'une Anomalie fermée ou absente à D | `SortieClassification` sans Anomalie ouverte | ignorée | — |
| Anomalie sans Entité | `entite` vide | ignorée | — |
| Aucune classification | `()` | table vide au schéma | — |
| Ordre | entrées dans un ordre quelconque | tri `entite`, `nombre` décroissant, `cause_racine` ; même sortie à entrées permutées | — |
| Explication | répartition présente | `- cause : nombre (pp %)`, nombre décroissant puis cause | sans colonne `part` : `- cause : nombre` |
| Modèle par tâche | `modeles_par_tache: {classification: claude-haiku-5-5}` | appels de classification au fournisseur Haiku (clé de cache et trace `anthropic:claude-haiku-5-5`) ; explication sur `modele` | modèle hors registre : `UsineErreur` à la construction |

</intent-contract>

## Code Map

- `src/usine/contrats/llm.py:196` -- `SCHEMA_REPARTITION_CAUSES` : ajouter `part: pl.Float64()` non nulle (fraction de 0 à 1) ; docstring.
- `src/usine/contrats/versions.py:9` -- 1.5.0 ; tests `test_evenements.py:140`, `test_llm.py:70`, `test_passage.py:103,212,220,224,228-236`, `test_versions.py:24`, regex `adaptateurs/journal/test_source_journal.py:94`, `consultation/test_passage.py:405`.
- `tests/contrat/consultation/fabriques.py:228`, `tests/unit/consultation/test_passage.py:332,352` -- fabriques Parquet : ajouter `part`.
- `ARCHITECTURE-SPINE.md:22` -- ligne d'amendement contrats 1.5.
- `src/usine/domaine/causes/__init__.py`, `repartition.py` (nouveaux) -- `repartition(date_arrete, classification, anomalies) -> pl.DataFrame` ; `anomalies` : table `cle_ticket`, `entite` des Anomalies ouvertes à D. Domaine : contrats seulement (import-linter).
- `src/usine/ia/repartition.py` (nouveau) -- `EtapeRepartitionCauses.executer(ctx)` : `ctx.consultation.anomalies(ctx.date_arrete)` (palier 2, `cause_racine_proposee` ignorée), `ctx.consultation.classification()`, sortie `{"repartition_causes": table}` (nom logique de `FICHIERS_PASSAGE`, schéma validé par `chaine/ecrivain.py:47`).
- `src/usine/ia/explication.py:139` -- `_causes` : ajoute `(pp %)` quand la colonne `part` existe.
- `src/usine/ia/passerelle.py:170-263` -- paramètre `fournisseurs_par_tache: Mapping[Tache, FournisseurLLM] | None = None` ; `executer_structure` choisit `fournisseurs_par_tache.get(parametres.tache, self._fournisseur)` pour `version_modele` et `generer_structure`.
- `src/usine/composition.py:278,388-420,505-524` -- `construire_fournisseurs_par_tache(racine, secrets)` (un adaptateur par entrée de `modeles_par_tache` différente de `modele`, via `config.model_copy(update={"modele": ...})`) ; construits seulement quand le fournisseur n'est pas injecté ; fermeture de tous ; registre `Etape.repartition_causes = EtapeRepartitionCauses()` en Palier 2.
- `src/usine/adaptateurs/llm/registre.py:51-56` -- `anthropic:claude-haiku-5-5` : 0,10 $ / 0,50 $ par Mtok, 50 req/min, `temperature=False` (valeurs non par défaut refusées).
- `config/llm.yaml` -- `modeles_par_tache: {classification: claude-haiku-5-5}` commenté.
- `tests/unit/contrats/test_config.py:279` -- défaut `{}` sans la clé (inchangé).
- `tests/unit/chaine/test_execution.py:631,673-677` -- `repartition_causes` désormais `reussie` ; prompt de l'explication avec la section remplie (`CAUSE_SCRIPTEE`).

## Tasks & Acceptance

**Execution:**
- contrats 1.5 (schéma, version, tests de version, fabriques, spine) -- commit dédié.
- `src/usine/domaine/causes/repartition.py` + `tests/unit/domaine/causes/test_repartition.py` -- matrice I/O (lignes 1 à 6), pureté (entrées non modifiées, deux appels égaux).
- `src/usine/ia/repartition.py` + `tests/unit/ia/test_repartition.py` -- étape sur une Consultation minimale.
- `src/usine/ia/explication.py` + test -- part dans le prompt.
- `src/usine/ia/passerelle.py` + test -- routage par tâche, clé de cache et trace au modèle de la tâche.
- `src/usine/adaptateurs/llm/registre.py`, `config/llm.yaml`, `src/usine/composition.py` + tests -- Haiku au registre, fournisseurs par tâche construits sans réseau, étape câblée.
- `tests/unit/chaine/test_execution.py` -- Palier 2 de bout en bout.

**Acceptance Criteria:**
- Given un Passage Palier 2 publié avec classification, when on lit `repartition_causes.parquet` via `Consultation.repartition_causes()`, then chaque ligne porte `nombre` entier et `part` dont la somme vaut 1 par Entité, et l'étape `repartition_causes` est `reussie`.
- Given une Entité rouge ou orange avec Anomalies ouvertes classées, when l'étape `explications` s'exécute, then la section « Causes racines proposées » du prompt liste les causes avec compte et part (plus « non disponible »).
- Given le dépôt, when on cherche un calcul de répartition hors `domaine/causes`, then aucun (AD-9) ; `lint-imports` vert.
- Given `config/llm.yaml` du dépôt, when la composition construit les fournisseurs, then la classification utilise `anthropic:claude-haiku-5-5`, l'explication `anthropic:claude-sonnet-5-5`.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 7 findings — high 0, medium 0, low 4, false 3, maybe-false 0 (mode économique : Edge Case Hunter seul ; Blind Hunter, Verification Gap et Intent Alignment sautés sur décision de l'orchestrateur)
- findings:
  - `[false]` `[reject]` Même `cle_ticket` deux fois dans les Anomalies avec deux Entités, sortie dépendante de l'ordre — `Consultation.anomalies` filtre `tickets_etats` sur une seule date : une ligne par ticket, doublon impossible en entrée de l'étape.
  - `[low]` `[reject]` Part arrondie à « 0 % » ou parts dont la somme affichée n'est pas 100 — donnée de contexte du prompt, nombre exact affiché à côté ; corriger ajoute une branche pour un cas rare (Entité de plus de 200 Anomalies classées).
  - `[low]` `[reject]` Repli « sans colonne `part` » de `_causes` inatteignable par `ConsultationPassage` (un Parquet antérieur à 1.5 échouerait à la validation) — aucun `repartition_causes.parquet` n'a été produit avant la 6.5, premier producteur ; repli utile seulement aux appels directs.
  - `[low]` `[reject]` `_fermer_tous` s'arrête si un `fermer()` lève — même comportement que la fermeture préexistante d'un fournisseur unique ; ajouter une collecte d'erreurs complique pour un cas non observé.
  - `[low]` `[reject]` Erreur de fermeture qui masque l'erreur d'origine dans `construire_fournisseurs_par_tache` — idem, cas non observé, garde supplémentaire non justifiée.
  - `[low]` `[reject]` `config/llm.yaml` relu par `construire_fournisseurs_par_tache` — fichier modifié entre deux lectures d'une même composition improbable ; signature parallèle à `construire_fournisseur` conservée.
  - `[false]` `[reject]` `Passerelle.version_modele` rend le modèle par défaut pour une tâche dédiée — aucun appelant de cette propriété dans `src/` ; clé de cache et trace passent par le fournisseur de la tâche (`test_fournisseur_par_tache`).

## Design Notes

La part se calcule sur les Anomalies ouvertes **classées** de l'Entité : une Anomalie non encore classée (part du plafond atteinte, stock initial complété sur plusieurs Passages) n'a pas de Cause racine à compter ; la somme des parts vaut 1 par Entité présente. Le modèle par tâche passe par un fournisseur par tâche dans la passerelle plutôt que par deux passerelles : le cumul de coût et le plafond du Passage restent uniques. Changer le modèle de classification change `version_modele` dans la clé de cache : le stock est reclassé (voulu, FR-14) dans la limite de la part du plafond ; à 0,10 $/Mtok, environ 0,30 € pour tout le stock.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert.

## Auto Run Result

**Changement :** étape `repartition_causes` du Palier 2 (`ia/repartition.py`) qui appelle la seule fonction de calcul `domaine.causes.repartition` (pure, injectée par la composition car `ia` n'importe pas `domaine`) et publie `repartition_causes.parquet` : compte entier et part (fraction) par Entité et Cause racine des Anomalies ouvertes classées à la Date d'arrêté. L'explication affiche `- cause : nombre (pp %)`. **Contrats 1.5** (additif) : colonne `part` de `SCHEMA_REPARTITION_CAUSES`. Décision orchestrateur : `modeles_par_tache` branché (fournisseur par tâche dans la passerelle, cumul et plafond communs), classification sur `claude-haiku-5-5` (0,10 $ / 0,50 $ par Mtok, température refusée) au registre et dans `config/llm.yaml`.

**Fichiers :** `contrats/llm.py`, `contrats/versions.py` (1.5.0), `domaine/causes/repartition.py`, `ia/repartition.py`, `ia/explication.py`, `ia/passerelle.py`, `adaptateurs/llm/registre.py`, `composition.py`, `config/llm.yaml`, spine, tests miroirs (domaine, ia, passerelle, composition LLM, Chaîne Palier 2, fabriques Parquet, versions).

**Revue :** 7 constats (Edge Case Hunter seul), 0 patch, 0 report, 4 low et 3 faux rejetés (voir Review Triage Log). Revue de suivi recommandée : non (aucun patch).

**Vérification :** ruff check, ruff format --check, mypy (302 fichiers), lint-imports (14 contrats), pytest -q : 2487 réussis, 1 sauté.

**Risques résiduels :** le changement de modèle de classification change la clé de cache : le stock est reclassé au prochain Passage réel, dans la limite de la part du plafond (≈ 0,30 € pour le stock entier sur Haiku 5.5). Parts arrondies au pour cent dans le prompt. Le registre garde Sonnet 5.5 à 3 $ / 15 $ par Mtok alors que le tarif public est 2 $ / 10 $ : coût estimé surévalué (hors périmètre, à corriger).
