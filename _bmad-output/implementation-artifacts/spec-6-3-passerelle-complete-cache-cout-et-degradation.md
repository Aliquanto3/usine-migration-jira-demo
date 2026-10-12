---
title: 'Story 6.3 : Passerelle complète, cache, coût et dégradation'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '27ff799efd58e35d5022fc173222875bf0894e7b'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** La passerelle de l'Epic 0 met en cache et trace, mais ignore le coût (trace à 0 €, manifeste `cout_llm_eur` à 0), n'applique pas le plafond de coût de `config/llm.yaml`, garde la Date d'arrêté dans la clé de cache de la classification, et la composition ne ferme pas l'adaptateur LLM, n'applique pas `ConfigLLM.temperature` et ne permet pas de choisir le moteur de Pseudonymisation (AD-15).

**Approach:** Passerelle : coût estimé par appel (fonction de tarif injectée), cumul par Passage, plafond → exception dédiée que la tâche convertit en libellé explicite ; clé de classification sans Date d'arrêté. Chaîne : `cout_llm_eur` = somme des traces. Composition : plafond et tarif câblés, adaptateur fermé, moteur `regex|presidio` lu (contrats 1.3, clé `moteur`). Adaptateur : température décidée par modèle (registre) et lue de la config.

## Boundaries & Constraints

**Always:** ordre AD-12 inchangé ; un succès en cache coûte 0 € et ne compte pas dans le plafond ; toute erreur du fournisseur (injoignable, HTTP) remonte et fait échouer l'étape et le Passage en nommant l'étape (H-31) ; aucun appel réseau dans les tests ; commit contrats dédié `Feat: contrats 1.3, …` en tête (`CONTRATS_VERSION` 1.3.0, additif).

**Never:** pas de toucher à `rendu/` ; pas d'import d'`adaptateurs` depuis `ia` ou `chaine` (le tarif est injecté par la composition) ; ne pas dégrader sur un contrôle raté autrement que l'existant ; ne pas implémenter les tâches classification/narration (6.4, 6.7).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Coût tracé | appel frais, 1000/200 jetons, tarif connu | `EntreeTrace.cout_estime_eur` = tarif ; manifeste = somme des traces LLM | — |
| Cache | Rejeu à versions identiques | 0 appel fournisseur, `cout_estime_eur` = 0 | — |
| Plafond atteint | cumul du Passage ≥ plafond, cache manquant | aucun appel ; `PlafondCoutAtteint` ; explication = libellé « explication indisponible : plafond de coût du Passage atteint », `rejete`, Passage réussi | journal warning |
| Plafond, cache présent | cumul ≥ plafond, réponse en cache | servie depuis le cache | — |
| Classification | tâche `classification`, deux Dates d'arrêté | même clé de cache | — |
| Fournisseur injoignable | `generer_structure` lève `UsineErreur` | Passage en échec, message « étape « explications » » | propagé |
| Moteur | `moteur: regex` / `presidio` / absent | `PseudonymiseurHmac` / `PseudonymiseurPresidio` / défaut `presidio` | valeur inconnue → erreur de config |

</intent-contract>

## Code Map

- `src/usine/contrats/config.py:480` -- `ConfigPseudonymisation` : ajouter `moteur: Literal["regex","presidio"] = "presidio"` (contrats 1.3).
- `src/usine/contrats/versions.py:9` -- `CONTRATS_VERSION` → 1.3.0 ; tests `test_evenements.py:140`, `test_llm.py:70`, `test_passage.py:103,212,220,224,230` à suivre.
- `src/usine/ia/passerelle.py` -- `cle_cache` (sans `date_arrete` pour `Tache.classification`), `Passerelle.__init__` (+ `tarif`, `plafond_cout_passage_eur`), `executer_structure` (cumul par `passage_id`, contrôle avant appel frais, `cout_estime_eur` dans la trace).
- `src/usine/ia/explication.py:~185` -- boucle des tentatives : attraper `PlafondCoutAtteint` → `_indisponible` avec texte de plafond.
- `src/usine/chaine/execution.py:107` -- `cout_llm_eur` = somme des `cout_estime_eur` des traces `TypeTrace.llm`.
- `src/usine/adaptateurs/llm/registre.py` -- `TarifModele.temperature: bool` (faux pour Sonnet/Opus 5.5) ; `cout_estime_eur` réutilisé par la composition.
- `src/usine/adaptateurs/llm/fournisseur.py:207-290,363-400` -- `temperature: float | None` (valeur de config, `None` si le modèle refuse) ; `ParametresAppel.temperature` prime seulement s'il est fixé explicitement (`model_fields_set`).
- `src/usine/composition.py:180-230,334-509` -- moteur lu de `pseudonymisation.yaml` ; `ConfigLLM` lu si `llm.yaml` existe (plafond, tarif) ; `Rapport.fermer()` appelé dans le `finally` de `lancer_rapport` ; fermeture si `construire_rapport` échoue après création du fournisseur.
- `src/usine/adaptateurs/presidio/__init__.py:59` -- `PseudonymiseurPresidio(cle, config, table)` (lecture seule).
- `config/pseudonymisation.yaml`, `config/llm.yaml` -- clé `moteur: presidio` ; commentaire du plafond.
- `tests/doublures/fournisseur_factice.py` (`version_modele="factice:modele"`), `tests/unit/ia/test_passerelle.py`, `tests/unit/chaine/test_execution.py:544-840` (`_passer_en_palier_2`, `preparer_racine` copie `config/`), `tests/unit/adaptateurs/llm/test_fournisseur.py`.

## Tasks & Acceptance

**Execution:**
- `src/usine/contrats/config.py`, `versions.py`, tests de version, spine AD-15/amendements -- commit contrats 1.3 -- AD-2, AD-15.
- `src/usine/ia/passerelle.py` -- clé, coût, plafond, `PlafondCoutAtteint(UsineErreur)` -- AD-12, NFR-9.
- `src/usine/ia/explication.py` -- libellé de plafond -- dégradation sans échec.
- `src/usine/chaine/execution.py` -- `cout_llm_eur` -- FR-34.
- `src/usine/adaptateurs/llm/{registre,fournisseur}.py` -- température par modèle et config -- report 6.1.
- `src/usine/composition.py` + YAML -- câblage plafond/tarif/moteur, fermeture -- reports 6.1 et 6.2.
- Tests : passerelle (clé classification, coût, plafond, cache sous plafond), explication (plafond), chaîne (manifeste, fournisseur en échec nomme l'étape), adaptateur (température), composition (moteur regex/presidio, fermeture).

**Acceptance Criteria:**
- Given un Passage Palier 2 avec un fournisseur dont les appels ont un coût, when il se publie, then chaque trace LLM porte `cout_estime_eur` et le manifeste `cout_llm_eur` égal à leur somme.
- Given `plafond_cout_passage_eur: 0`, when l'étape `explications` s'exécute sans cache, then aucun appel fournisseur, chaque explication porte le libellé de plafond et le Passage est publié.
- Given un fournisseur qui lève une `UsineErreur`, when `lancer_rapport` s'exécute, then `UsineErreur` mentionnant « explications ».
- Given un fournisseur construit par la composition, when `lancer_rapport` se termine (succès ou échec), then il est fermé.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 11 findings — high 0, medium 0, low 5, false 6, maybe-false 0
- findings:
  - `[false]` `[reject]` Coût non cumulé si le fournisseur lève après facturation — l'erreur remonte, l'étape et le Passage échouent (H-31) : aucun appel suivant dans ce Passage.
  - `[false]` `[reject]` Tarif qui lève après l'écriture du cache — `_tarif_registre` renvoie 0 € pour un modèle hors registre, seul cas où `cout_estime_eur` lève.
  - `[false]` `[reject]` Cumul et manifeste divergent si le contrôle lève — l'exception fait échouer le Passage, aucun manifeste n'est publié.
  - `[false]` `[reject]` Cache illisible au plafond dégradé sans signal — un warning « réponse en cache illisible » est déjà journalisé avant le contrôle du plafond.
  - `[low]` `[reject]` Température absente de la clé de cache — la clé est fixée par AD-12 et l'AC ; changement de température improbable en démo, l'ajouter changerait le contrat de clé.
  - `[low]` `[reject]` Température explicite ignorée en silence sur un modèle qui la refuse — aucun appelant ne la fixe ; ajouterait une branche.
  - `[low]` `[reject]` `ParametresAppel` reconstruit par `model_validate` : température vue comme explicite — les tâches construisent `ParametresAppel` directement, jamais depuis un dump.
  - `[low]` `[reject]` `fermeture()` qui lève masque l'erreur d'origine — `fermer` ne fait que `loop.close()`, qui ne lève pas en pratique ; ajouterait un garde.
  - `[low]` `[reject]` Presidio ou spaCy absent : ImportError brute — dépendances verrouillées (`uv sync --locked`), hors usage courant.
  - `[false]` `[reject]` Bascule silencieuse vers Presidio sans clé `moteur` — défaut voulu par AD-15 (moteur du Palier 2), YAML livré explicite ; jetons identiques entre moteurs par construction.
  - `[false]` `[reject]` Motifs non validés sur la voie presidio — `Reconnaisseur` valide la compilation au chargement ; la voie presidio refuse un fichier vide et l'adaptateur vérifie les types.

## Design Notes

Le tarif est injecté (`Callable[[str, int, int], Decimal]`) pour que `ia` n'importe pas `adaptateurs` ; la composition passe `cout_estime_eur` du registre, et 0 € pour un `version_modele` absent du registre (doublures). Le plafond lève `PlafondCoutAtteint` plutôt que de renvoyer une sortie générique : chaque tâche (6.4, 6.7) choisit son libellé ; non attrapé, il fait échouer l'étape avec un message clair. L'appel qui franchit le plafond passe ; les suivants sont dégradés (« atteint »).

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert.

## Auto Run Result

Status: done

- **Changement :** passerelle complète (coût estimé par appel via tarif injecté, cumul et plafond par Passage → `PlafondCoutAtteint`, clé de cache de classification sans Date d'arrêté) ; explication dégradée en « explication indisponible : plafond de coût du Passage atteint » ; manifeste `cout_llm_eur` = somme des traces ; contrats 1.3 (`ConfigPseudonymisation.moteur`, défaut `presidio`) branchés dans la composition ; fournisseur construit par la composition fermé ; température lue de `ConfigLLM` et décidée par modèle (registre).
- **Fichiers :** `src/usine/contrats/{config,versions}.py` (contrats 1.3) ; `src/usine/ia/passerelle.py` (coût, plafond, clé) ; `src/usine/ia/explication.py` (libellé de plafond) ; `src/usine/chaine/execution.py` (`cout_llm_eur`) ; `src/usine/adaptateurs/llm/{registre,fournisseur}.py` (température) ; `src/usine/composition.py` (moteur, plafond, tarif, fermeture) ; `config/{llm,pseudonymisation}.yaml` ; spine AD-15 ; tests passerelle, explication, chaîne, adaptateur, contrats.
- **Revue (Edge Case Hunter seul, mode économique) :** 11 constats ; aucun correctif, aucun report ; 6 faux, 5 low rejetés (motifs dans le triage).
- **Revue de suivi :** non recommandée (aucun patch high ni medium).
- **Vérification :** ruff check, ruff format --check, mypy, lint-imports (14 contrats) et pytest -q (2437 passés, 1 sauté) verts.
- **Risques résiduels :** les tests Palier 2 passent désormais par Presidio/spaCy (suite ~3 min 20) ; fermeture du fournisseur duck-typée (`fermer` hors port).
