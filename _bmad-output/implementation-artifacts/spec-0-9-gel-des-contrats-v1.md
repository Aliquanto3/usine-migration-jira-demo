---
title: 'Story 0.9 : gel des contrats v1 (correctifs avant lanes, D1 à D4, D7 à D9, D6)'
type: 'refactor'
created: '2026-10-12'
status: 'done'
baseline_commit: '809c6730c398845a9f5647d7b7e1ee065ee620af'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/preparation-0-9-gel-contrats.md'
  - '{project-root}/_bmad-output/planning-artifacts/sprint-change-proposal-2026-10-12.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** le code de `contrats/` et `ports/` ne suit plus le spine amendé le 2026-10-12 (exclusions du Rejeu plates, `CacheLLM` et trois formes hors de `contrats`, nullabilité non contrôlée, `Mapping` modifiables, lectures de `Consultation` manquantes, doublons de tri, de libellés, de dates et de chemins), et deux défauts de composition (erreur brute de `Secrets`, `composition.py` surchargé) doivent être corrigés avant l'ouverture des lanes.

**Approach:** étapes 3 à 6 de l'ordre de `preparation-0-9-gel-contrats.md` § 6, sur `main` : correctifs « avant les lanes », puis D1 à D4 et D7 à D9 selon le spine amendé et les critères § 5 de `sprint-change-proposal-2026-10-12.md`, carte de `controle_lanes.py`, puis `CONTRATS_VERSION = 1.0.0` (D6) en dernier commit, régénération du Journal, `usine rapport` sur le mini-jeu et les quatre contrôles.

## Boundaries & Constraints

**Always:** le spine amendé fait foi (AD-2, AD-7, AD-11, AD-12, AD-15, AD-17, AD-21) ; formes JSON et YAML inchangées (D4) ; toute erreur reste une `UsineErreur` nommant fichier, clé ou variable ; tableau des couches et liste blanche d'import-linter respectés ; tests mis à jour avec chaque changement ; `1.0.0` posé dans le dernier commit seulement.

**Never:** pas de push, pas d'étiquette `contrats-v1`, pas de branche de lane ; pas de modification du spine ni des epics ; D5 et D10 sans changement de code (dataclass gardées, `code_kpi` libre) ; pas d'invention de `ReponseClassification` ni `ReponseNarration` (T6) ; pas de clé « moteur » de Pseudonymisation (Story 6.2).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Secrets illisibles | `USINE_MODE_REPLI=peut-être` lors de `usine rapport` | `UsineErreur` nommant la variable, code non nul | plus de `ValidationError` brute |
| Racine de l'UI | `USINE_RACINE` dans l'environnement ou `.env` | racine lue via `Secrets` | vide → répertoire courant |
| Rejeu par fichier | deux Passages identiques | `horodatage` exclu dans `trace_llm` reste comparé dans `manifeste.etapes[]` sauf chemins listés | — |
| Nullabilité | ligne nulle dans une colonne `non_nulles` | `valider` lève une `UsineErreur` nommant schéma et colonne | — |
| Mapping figé | `AppelOutil.arguments["x"] = 1` | `TypeError` ; `model_dump_json` puis relecture donne le même modèle | — |
| FR-44 | Passages avec et sans `classification_initiale` | `dernier_passage(sans_classification_initiale=True)` ignore les premiers | — |
| FR-46 | `anomalies(palier=1)` | `cause_racine_proposee` à `None` partout | — |

</frozen-after-approval>

## Code Map

- `src/usine/config/secrets.py` -- `Secrets` ; ajouter `usine_racine` et `charger_secrets(racine)` qui traduit `ValidationError`.
- `src/usine/composition.py:190,296-325,328-339` -- `Secrets` brut, services UI (`mode_repli`, `consultation_dernier_passage`), URL Jira résolue deux fois, `generer_journal`.
- `src/usine/ui/app.py:34-37`, `src/usine/ui/cli.py` -- `os.environ` ; `ui/cli.py` est une racine de composition (`*/cli.py`, ignore d'import-linter) détenue par L7.
- `src/usine/generateur/cli.py:67-74`, `generateur/journal.py` -- écriture du Journal et de la vérité terrain.
- `src/usine/ia/passerelle.py:33-52,116-133` -- `CacheLLM`, `EnveloppeCache`, grammaire des jetons dupliquée.
- `src/usine/adaptateurs/pseudonymisation/__init__.py:27-56` -- grammaire des jetons (version de référence, filtre `_TYPE_JETON`).
- `tests/doublures/pseudonymiseur_factice.py:18` -- troisième copie de la grammaire.
- `src/usine/ia/explication.py:48` -- `ReponseExplication` ; `chaine/execution.py:34` -- `DonneesPassage`.
- `src/usine/contrats/passage.py:172` -- `EXCLUSIONS_REJEU` plat ; `tests/unit/chaine/test_cli.py:48` l'applique.
- `src/usine/contrats/schemas.py` -- `SchemaTable`, `valider` ; nullables voulues : `tickets.py:214`, `calcul.py:50`.
- `Mapping` à figer : `llm.py:70`, `evenements.py:137`, `config.py:173,195,217,219,221,274`.
- Doublons D8 : `rang_cle` (`ia/controles.py:50`, `consultation/passage.py:535`, `domaine/meteo.py:84`) ; `LIBELLES_COULEURS` (`rendu/commun.py:18`, `ui/carte.py:12`) ; date `AAAA-MM-JJ` (`chaine/cli.py:14`, `generateur/cli.py:17`, `consultation/passage.py:116`) ; chemins (`composition.py:57-73`, `generateur/cli.py:19-22`, `ui/progression.py:16`, `chaine/ecrivain.py:107,112,228,239`).
- `src/usine/ports/consultation.py:28,78` + `consultation/passage.py:226,372` -- D9.
- `.github/scripts/controle_lanes.py:60-73` + `tests/depot/test_controle_lanes.py` -- L6 sans `pseudonymisation`.
- `contrats/versions.py:9` et tests figés sur `0.1.0` (préparation, D6).

## Tasks & Acceptance

**Execution:**
- [x] `config/secrets.py`, `composition.py`, `ui/app.py`, `ui/cli.py`, `generateur/*` -- correctif 1 : `charger_secrets(racine)` (`UsineErreur` nommant la variable) utilisé partout, `usine_racine` lu par la composition ; correctif 2 : services UI déplacés dans `ui/cli.py`, `ecrire_journal` dans `generateur/journal.py` (CLI et `composition.generer_journal` délèguent), une seule fonction `url_jira(racine)` -- retro constats 3, 9, 13.
- [x] `contrats/llm.py`, `ports/cache_llm.py`, `ia/*`, `adaptateurs/*`, `chaine/execution.py`, `contrats/passage.py`, doublures -- D1, D2, T5 : port `CacheLLM`, `EnveloppeCache`, `ReponseExplication`, grammaire des jetons (`LONGUEUR_EMPREINTE_JETON`, `CANDIDAT_JETON`, `variantes_jeton`, `est_type_jeton`), `DonneesPassage` ; suite `tests/contrat/cache_llm/` (SQLite, mémoire).
- [x] `contrats/schemas.py` + tous les `SCHEMA_*` -- D3 : `non_nulles` contrôlé par `valider`.
- [x] `contrats/modele.py` + modèles -- D4 : type annoté `MappingFige` (`MappingProxyType` après validation), test d'aller-retour JSON.
- [x] `contrats/passage.py`, `tests/unit/chaine/test_cli.py` -- D7 : `EXCLUSIONS_REJEU: Mapping[str, frozenset[str]]` selon AD-7, application par fichier, test d'un champ exclu ailleurs mais comparé ici.
- [x] `contrats/{tickets,meteo,calendrier,passage}.py` + consommateurs -- D8 : `rang_cle`, `LIBELLES_COULEURS`, `analyser_date_iso`, chemins `donnees/` et `sorties/`.
- [x] `ports/consultation.py`, `consultation/passage.py`, contrat `Consultation` -- D9.
- [x] `.github/scripts/controle_lanes.py`, `tests/depot/test_controle_lanes.py` -- carte = spine, `pseudonymisation` en L6.
- [x] `contrats/versions.py` + tests -- D6 en dernier commit ; régénérer `donnees/journal.jsonl`, `usine rapport` sur le mini-jeu.

**Acceptance Criteria:**
- Given le dépôt après la story, when on cherche `class CacheLLM`, `class EnveloppeCache`, `class ReponseExplication`, `class DonneesPassage` ou la grammaire des jetons, then seules les définitions de `contrats`/`ports` existent.
- Given `CONTRATS_VERSION = "1.0.0"`, when `usine rapport --date-arrete` tourne sur le mini-jeu régénéré, then un Passage est publié.
- Given le code final, when `pytest`, `ruff check`, `ruff format --check`, `mypy` et `lint-imports` tournent, then tout passe.

## Implementation Notes

- Commits : refactor (correctifs avant lanes, D1 à D4, T5, D7 à D9, carte des lanes), puis correctifs de revue, puis `CONTRATS_VERSION = 1.0.0` en dernier commit (D6).
- Journal régénéré ; `usine rapport --date-arrete 2026-10-09` publie un Passage en 1.0.0.
- `.env.example` non modifié : une règle de permission en bloque la lecture et l'écriture. Ligne à ajouter à la main : `USINE_RACINE=`, avec son commentaire.
- `test_carte_identique_au_spine` lit le spine amendé : celui-ci doit être committé avant le push.
- Vérification finale : 973 tests passés, 1 sauté (persistance de la doublure en mémoire) ; ruff, mypy et lint-imports (13 contrats) sans écart.

## Spec Change Log

## Review Triage Log

Passe 1 (blind-hunter, edge-case-hunter, verification-gap) :

| # | Constat | Verdict | Preuve | Route |
| --- | --- | --- | --- | --- |
| 1 | `construire_rapport` relit `.env` et `jira.yaml` dans `url_jira` | medium | `composition.py` : `charger_secrets` et `_config_jira` appelés, puis `url_jira(racine)` refait les deux lectures | patch |
| 2 | Variable illisible : la page UI s'arrête avant carte et lancement | medium | `ui/app.py:principal` fait `return` sur l'`UsineErreur` de `racine_ui`, régression par rapport à E0-8 | patch |
| 3 | `from exc` recopie la valeur via la `ValidationError` chaînée | low | `secrets.py` : la promesse « valeur jamais recopiée » tombe dans une trace journalisée ; correction directe | patch |
| 4 | `.env` non UTF-8 ou illisible : exception brute | low | `charger_secrets` n'attrape que `ValidationError` ; ajout d'une clause `except` | patch |
| 5 | Exclusions `trace_llm`/`explications` jamais appliquées à deux Passages réels | medium | lacune vérifiée par verification-gap ; seuls `meteo` et `manifeste` sont comparés | patch |
| 6 | Jetons collés ou préfixés de la doublure non testés en contrat | medium | lacune vérifiée par verification-gap ; seul `test_hmac.py` couvre ce cas | patch |
| 7 | Test de contrat `dernier_passage(sans_classification_initiale)` vide | medium | aucune fixture ne porte `classification_initiale=True` | patch |
| 8 | Docstring de `MappingFige` : gel annoncé comme complet | low | les `JsonValue` imbriqués restent modifiables ; la correction porte sur la docstring | patch |
| 9 | `fnmatch` insensible à la casse sous Windows | low | `test_controle_lanes.py` ; remplacement par `fnmatchcase` | patch |
| 10 | Aucun contrôle de complétude des exclusions des enveloppes | low | `CONTENUS_JSON` contre `EXCLUSIONS_REJEU` ; ajout d'un test | patch |
| 11 | `test_persistance` : `return` nu compté comme réussite | low | à remplacer par `pytest.skip` | patch |
| 12 | `non_nulles` étroit (`entite` admet `null` dans Instantané et TicketEtat) | maybe-false | Il faudrait vérifier si un producteur du domaine peut émettre `entite` à `null` ; l'élargir après le gel serait un changement majeur | defer (medium, non vérifié) |
| 13 | `ui/cli.py` devient une seconde racine de composition | false | le spine range `*/cli.py` dans la racine de composition, et c'est le choix des Design Notes | rejeté |
| 14 | `usine_racine` porté par `Secrets` | false | l'intention figée le demande | rejeté |
| 15 | Paramètre `brut` du port `CacheLLM` | false | T7 reprend la signature telle quelle | rejeté |
| 16 | Ordre de `rang_cle` pour les clés sans numéro | low | `MOTIF_CLE_TICKET` impose un numéro, le cas n'arrive pas en pratique | rejeté |
| 17 | `ecrire_journal` non atomique, docstring « pur » | low | même comportement que l'ancienne CLI ; un correctif ajouterait de la complexité | rejeté |
| 18 | `EnveloppeCache` sans `contrats_version` | low | la clé de cache porte déjà les versions (AD-12), et le spine ne demande pas ce champ | rejeté |
| 19 | Analyse de la carte du spine fragile (« sauf » multiples) | low | aucune ligne actuelle ne le déclenche | rejeté |
| 20 | Garde de `test_inventaire` trop large (`Mapping | None`, `dict`) | low | aucun champ de ce type aujourd'hui ; un correctif ajouterait de la complexité | rejeté |
| 21 | `model_construct`, `pickle` et `MappingProxyType` | low | aucun usage dans le dépôt | rejeté |
| 22 | Passages 0.1.0 masqués après le passage à 1.0.0 | low | attendu (D6) ; Journal régénéré | rejeté |
| 23 | Chemins codés en dur dans les tests, `CHEMIN_GABARIT` resté dans `composition` | low | cosmétique | rejeté |
| 24 | `JETON.findall` renvoie des tuples | false | seul `len(...)` est utilisé, le compte est le même | rejeté |
| 25 | `USINE_RACINE` d'espaces dans l'environnement masque le `.env` | low | cas improbable | rejeté |
| 26 | `TablePseudonymes` sans suite de contrat | false | forme locale consignée (D1) | rejeté |
| 27 | Fabrique SQLite de la suite cache sur `tempfile` et `atexit` | low | aucune fuite constatée ; un correctif ajouterait de la complexité | rejeté |

## Design Notes

Les services de l'UI vont dans `ui/cli.py` : le spine classe `*/cli.py` dans la racine de composition, et L7 possède `ui/`. Après le gel, une évolution de ces services ne passe donc plus par une PR sur `main`. `composition.generer_journal` reste, en délégation, parce que `outils/` ne peut pas importer `generateur`.

La grammaire de référence est celle de l'adaptateur (filtre `est_type_jeton` sur chaque variante). La passerelle l'adopte : une variante au type invalide n'est jamais un jeton.

## Verification

**Commands:**
- `uv run pytest -q` -- expected : tout vert.
- `uv run ruff check . && uv run ruff format --check .` -- expected : aucun écart.
- `uv run mypy` -- expected : aucune erreur.
- `uv run lint-imports` -- expected : tous les contrats gardés.
- `uv run usine donnees generer && uv run usine rapport --date-arrete <dernier Jour ouvré>` -- expected : « Passage publié ».
