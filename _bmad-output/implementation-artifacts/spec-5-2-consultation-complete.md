---
title: 'Story 5.2 : Consultation complète'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '0e50dbb0fa4f065a66a1e451656a1fb6c9f7b6a1'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-5-context.md'
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** `ConsultationPassage` couvre déjà toutes les lectures du port gelé, mais trois points ne sont pas tenus. Un Passage dont le manifeste porte une version majeure étrangère n'est refusé que par certaines lectures : `kpi(date)`, `traces()` ou `previsions()` le lisent sans contrôle. Les Prévisions et Risques ne sont jamais testés en lecture directe, ni le cas « étape `prevision` en bouchon ». Enfin, la suite de contrat ne couvre ni Prévisions, ni traces, ni Mode repli, ni le masquage Palier 1 d'une Entité. La lane L7 (UI Palier 1) attend ce lecteur complet.

**Approach:** Dans `consultation/passage.py`, toute lecture d'un fichier d'un Passage qui a un manifeste valide d'abord ce manifeste, mis en cache. Une version majeure étrangère lève alors une `UsineErreur` sur chaque lecture. Ensuite, documenter et tester l'absence explicite des Prévisions (`()` sans erreur), l'URL Jira issue de la composition, avec ou sans Mode repli, et le masquage Palier 1 par Entité. Étendre la suite de contrat aux lectures restantes.

## Boundaries & Constraints

**Always:** lire sans dériver de valeur métier (seules dérivations admises : âge en Jours ouvrés, appariement J-1 / J-5). Un fichier absent donne un résultat vide au schéma ou `()`, jamais une erreur. Un Passage en construction (sans manifeste) reste lisible ; seuls ses fichiers sont contrôlés un par un. Tout message d'erreur nomme le fichier fautif.

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` (gelés). Câbler `EtapePrevision` ou inventer une Prévision (lane L4). Toucher `ui/` (lane L7) ou `composition.py`. Ajouter au lecteur une méthode publique hors port, que l'UI ne pourrait lire qu'en contournant AD-11.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Prévisions présentes | `previsions.json` : 1 Prévision ENT-A et 1 Risque ENT-B à D, plus une Prévision à D-1 | `previsions()` = celle de D ; `previsions(D-1)` = celle de D-1 ; `previsions(entite="ENT-B")` = `()` ; `risques(entite="ENT-B")` = le Risque | Aucune |
| Prévision en bouchon | Passage publié par le registre réel (pas de `previsions.json`) | `previsions()`, `risques()`, `previsions(entite=...)` = `()` | Aucune erreur |
| Bouchon, Passage vide | Répertoire sans manifeste ni fichier | `previsions()` = `risques()` = `()` | Aucune erreur |
| Manifeste majeur étranger | `manifeste.json` en `2.0.0`, autres fichiers en `1.x` | `kpi(D)`, `traces()`, `previsions()`, `meteo()`, `tickets_etats(D)` | `UsineErreur` nommant `manifeste.json` |
| Fichier majeur étranger | `previsions.json` en `2.0.0` | `previsions()` | `UsineErreur` nommant `previsions.json` |
| Palier 1 sur Passage Palier 2 | fichiers `llm/*` et `repartition_causes.parquet` présents | pour ENT-A en `palier=1` : sorties LLM vides ou `None` ; lectures déterministes identiques au `palier=2` | Aucune |

</intent-contract>

## Code Map

- `src/usine/consultation/passage.py` -- `ConsultationPassage` : `_table` (l.156), `_contenu` (l.166), `traces` (l.505) lisent les fichiers ; `manifeste()` (l.265) met le manifeste en cache via `lire_manifeste`, qui appelle `verifier_version`. Point d'insertion du contrôle : un `_verifier_passage()` appelé par ces trois lectures, qui lit le manifeste s'il existe. `previsions` et `risques` (l.435-459) rendent déjà `()` sans fichier.
- `src/usine/ports/consultation.py` -- port gelé, lecture seule : il suffit aux écrans Palier 1 (voir Design Notes).
- `src/usine/contrats/prevision.py` -- `ContenuPrevisions`, `Prevision` (statuts `sortie_projetee`, `pas_de_sortie_projetee`, `regle_non_projetable`), `RisqueEntreeRouge` (IND-1/3/4 seulement, franchissement > D).
- `src/usine/contrats/passage.py` -- `EnveloppeFichier[T]` pour écrire un `previsions.json` de test ; `CONTENUS_JSON["previsions"]`.
- `src/usine/composition.py` -- `url_jira(racine)` (l.222), `Rapport.fabrique_consultation` (l.133) : source de l'URL Jira (lecture seule).
- `tests/unit/chaine/environnement.py` -- `contenu_previsions(date, version_grille)` (1 Prévision ENT-A, 1 Risque ENT-B), `preparer_racine`, `DATE_ARRETE`.
- `tests/unit/consultation/test_passage.py` -- fixtures `lance` (Passage réel Palier 1) et `passage` (copie modifiable) ; `test_sorties_llm_selon_palier` écrit déjà les fichiers `llm/*`, à factoriser pour le test par Entité.
- `tests/contrat/consultation/fabriques.py`, `test_contrat.py` -- suite de contrat, fabrique `passage_publie` unique.

## Tasks & Acceptance

**Execution:**
- `src/usine/consultation/passage.py` -- ajouter `_verifier_passage()` : si `manifeste.json` existe, `self.manifeste()` (donc la version) ; l'appeler en tête de `_table`, `_contenu` et `traces`, avant la lecture du fichier. Préciser les docstrings de `previsions`/`risques` (`()` quand `previsions.json` est absent, étape `prevision` en bouchon) et celle du module (refus d'un Passage de version majeure étrangère, AD-2).
- `tests/unit/consultation/test_passage.py` -- tests de la matrice : Prévisions présentes (filtres date et Entité), bouchon sur Passage réel et sur répertoire vide, manifeste majeur étranger sur chacune des lectures listées, `previsions.json` majeur étranger, Palier 1 par Entité ; `url_ticket("DEMO-123")` via `construire_rapport(racine).fabrique_consultation(D)` : URL de `config/jira.yaml` + `/browse/DEMO-123`, puis `None` avec `USINE_MODE_REPLI=1`.
- `tests/contrat/consultation/fabriques.py`, `test_contrat.py` -- seconde fabrique `passage_mode_repli` (même Passage, `url_jira=None`) ; tests de contrat : `previsions`/`risques` rendent des tuples de `Prevision`/`RisqueEntreeRouge` à la Date d'arrêté et filtrés par Entité, `traces()` un tuple d'`EntreeTrace`, masquage Palier 1 par Entité (`explications`, `narrations`, `repartition_causes`, `anomalies`), `url_ticket` : `None` ou `<url>/browse/<cle>`.

**Acceptance Criteria:**
- Given un Passage publié par `lancer_rapport`, when on appelle chaque lecture du port `Consultation`, then la suite `tests/contrat/consultation` passe sur les deux fabriques.
- Given `construire_rapport(racine)` sans Mode repli, when on appelle `url_ticket("DEMO-123")` sur la Consultation qu'il fabrique, then on obtient `<url_site de config/jira.yaml>/browse/DEMO-123` ; avec `USINE_MODE_REPLI=1`, `None`.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 29 findings — high 0, medium 5, low 18, false 5, maybe-false 1
- findings:
  - `[low]` `[patch]` (verification) lectures `palier=1` (`_sorties_llm`, `repartition_causes`) sorties avant le contrôle du manifeste — `_verifier_passage()` appelé avant le retour anticipé ; cas `palier=1` ajoutés au test paramétré.
  - `[medium]` `[patch]` (verification) tests de contrat Prévisions, traces et Palier 1 vides sur les deux fabriques — fabrique `passage_palier_2` (previsions.json, trace, llm/*, répartition) et champ `avec_sorties` qui exige des lectures non vides.
  - `[medium]` `[patch]` (verification) `test_url_ticket` de contrat accepte `None` partout — champ `url_attendue` : `None` exactement en Mode repli, sinon `/browse/<cle>` sans `//browse`.
  - `[low]` `[patch]` (blind) docstring « chaque lecture lève » contredite par `palier=1` et `url_ticket` — même cause que le premier constat ; docstring restreinte aux lectures de données, `url_ticket` et `dernier_passage` exclus explicitement.
  - `[low]` `[patch]` (blind) test du manifeste étranger sans lecture `palier=1` — groupé avec le premier constat, cas ajoutés.
  - `[low]` `[reject]` (blind) mode construction (fichier étranger sans manifeste) non testé — couvert par `test_version_etrangere_meteo` (refus par fichier) et `test_date_du_passage_en_construction` (lisible sans manifeste) ; aucune nouvelle branche.
  - `[low]` `[reject]` (blind) manifeste corrompu bloque toute lecture et est relu à chaque appel — voulu (le manifeste fait foi, échec bruyant) ; relecture seulement sur un état déjà en erreur.
  - `[low]` `[reject]` (blind) `_date_connue` duplique le test d'existence du manifeste — aucun appelant ne diverge, les deux lisent le même cache.
  - `[low]` `[reject]` (blind) un `exists()` par lecture en construction — coût négligeable devant la lecture Parquet.
  - `[medium]` `[patch]` (blind) tests de contrat Prévisions et Palier 1 vides — groupé avec le deuxième constat.
  - `[medium]` `[patch]` (blind) `test_url_ticket` ne distingue pas les fabriques — groupé avec le troisième constat.
  - `[false]` `[reject]` (blind) double barre `//browse` si `url_site` finit par `/` — le constructeur fait déjà `rstrip("/")` ; le contrat vérifie maintenant l'absence de `//browse`.
  - `[low]` `[reject]` (blind) suite de contrat rejouée par fabrique — 88 tests en quelques secondes ; la seconde fabrique porte un comportement distinct (`url_attendue`).
  - `[low]` `[patch]` (blind) filtre de date des Risques jamais exercé — Risque à J-1 écrit, `risques(VEILLE)` et `risques()` vérifiés exactement.
  - `[false]` `[reject]` (blind) cas « sans configuration Jira » non testé — couvert par `tests/unit/test_composition.py::test_url_jira_sans_configuration`.
  - `[low]` `[patch]` (blind) `test_traces` de contrat superficiel — groupé avec le deuxième constat (traces non vides exigées sur `passage_palier_2`).
  - `[low]` `[reject]` (edge) manifeste corrompu bloque toutes les lectures — même motif que le constat blind équivalent.
  - `[false]` `[reject]` (edge) renommage du répertoire entre `exists()` et la lecture — la Chaîne ne lit le Passage en cours qu'avant `publier`, qui écrit le manifeste puis renomme ; aucun lecteur concurrent du répertoire en cours.
  - `[low]` `[patch]` (edge) `url_ticket` ne refuse pas un Passage étranger — groupé avec le premier constat : aucune donnée du Passage lue, exclusion documentée.
  - `[medium]` `[patch]` (edge) contrat Prévisions vide — groupé avec le deuxième constat.
  - `[low]` `[patch]` (edge) `IndexError` si ENT-A n'a pas d'Anomalie ouverte — assertion explicite ajoutée.
  - `[low]` `[patch]` (edge, claim) « chaque lecture » contredit par `url_ticket` — groupé avec le premier constat.
  - `[maybe-false]` `[reject]` (intent) R2b : `()` ne distingue pas bouchon et « rien à signaler » — le port gelé n'offre pas mieux ; seule une Entité rouge est ambiguë et l'UI la croise avec sa Météo (Design Notes) ; si avéré, effet au plus low.
  - `[false]` `[reject]` (intent) suffisance du port établie seulement en prose — l'inventaire écran par écran est dans les Design Notes, et la suite de contrat exerce désormais chaque lecture avec données.
  - `[low]` `[patch]` (intent) contrat Prévisions vide — groupé avec le deuxième constat.
  - `[low]` `[patch]` (intent) contrat Palier 1 sur Passage Palier 1 — groupé avec le deuxième constat (`passage_palier_2`, manifeste `palier: 2`).
  - `[low]` `[reject]` (intent) refus AD-2 paresseux (première lecture) plutôt qu'à la construction — construire un lecteur ne lit rien ; la première lecture est l'ouverture, et toutes refusent.
  - `[false]` `[reject]` (intent) aucun lien visible avec `deferred-work.md` — les deux entrées de la 5.1 (câblage L4, journalisation 5.5) sont hors du périmètre de la 5.2 ; continuité reprise dans la spec (bouchon `prevision`).

## Design Notes

**Le port gelé suffit aux écrans Palier 1 (FR-43 à FR-46).** Carte météo : `dernier_passage()`, `meteo()`, `evolution_meteo()`. Détail d'Entité : `meteo(entite=)` (Règles avec valeur, seuil, tickets en cause), `indicateurs`, `kpi(entite=)`, `previsions(entite=)`, `risques(entite=)`, `explications(entite=, palier=)`, `url_ticket`. Avant / après : `dernier_passage(sans_classification_initiale=True)` (horodatages du manifeste) ; le cumul sur 5 Rapports est une multiplication d'affichage. Mode repli : `url_ticket` vaut `None`. FR-46 : filtre `palier`. La progression (`sorties/progression/`) est hors Passage et l'UI la lit elle-même (AD-8). Aucune lecture ne manque.

**Prévision absente.** Tant que l'étape `prevision` est un bouchon, `previsions()` et `risques()` rendent `()`. C'est la valeur absente explicite du port. Une Entité rouge « sans sortie projetée » portera, elle, une `Prevision` de statut `pas_de_sortie_projetee`. L'UI distingue donc « Prévision non disponible » (tuple vide) de « pas de sortie projetée ».

**Contrôle au niveau du Passage.** Les lignes de `trace/*.jsonl` ne portent pas de version, et un fichier en `1.x` peut cohabiter avec un manifeste en `2.0.0`. Le manifeste, quand il existe, fait donc foi pour tout le Passage. Il est lu une fois, puis mis en cache.

**Fichiers hors lane.** `tests/contrat/consultation/fabriques.py` et `test_contrat.py` : l'AC 1 de l'epic exige que la suite de contrat passe sur l'implémentation complète. Elle doit donc couvrir les lectures que L7 et ses doublures utiliseront. Ce sont des tests seulement, sans changement de contrat ni de port.

## Verification

**Commands:**
- `uv run pytest -q tests/unit/consultation tests/contrat/consultation` -- expected: tout passe
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout passe

## Auto Run Result

Status: done

**Résumé.** `ConsultationPassage` refuse désormais un Passage dont le manifeste porte une version majeure étrangère, et ce sur chaque lecture de données, y compris en `palier=1` (AD-2). Le manifeste est lu une fois, puis mis en cache. Tant que l'étape `prevision` est un bouchon, `previsions()` et `risques()` rendent `()` sans erreur : c'est la valeur absente explicite, désormais documentée et testée. Quand `previsions.json` existe, les filtres par date et par Entité sont testés. L'URL Jira est vérifiée de bout en bout depuis la composition (`config/jira.yaml`, `None` en Mode repli). La suite de contrat couvre maintenant toutes les lectures, avec des données : une fabrique Palier 2 contient Prévisions, Risques, traces et sorties LLM, et une fabrique Mode repli n'a pas d'URL. Le port gelé suffit aux écrans Palier 1 de la lane L7 (inventaire dans les Design Notes) : aucune lecture ne manque.

**Fichiers modifiés.**
- `src/usine/consultation/passage.py` : ajout de `_verifier_passage()`, appelé par `_table`, `_contenu`, `traces`, `_sorties_llm` et `repartition_causes` ; docstrings mises à jour (refus AD-2, Prévision absente).
- `tests/unit/consultation/test_passage.py` : Prévisions présentes ou en bouchon, manifeste ou `previsions.json` de version majeure étrangère, Palier 1 par Entité, URL via `construire_rapport`.
- `tests/contrat/consultation/fabriques.py` (hors lane) : champs `url_attendue` et `avec_sorties`, fabriques `passage_mode_repli` et `passage_palier_2`.
- `tests/contrat/consultation/test_contrat.py` (hors lane) : contrats `previsions`/`risques`, `traces`, Palier 1 par Entité et `url_ticket` selon le mode.

**Revue.** 29 constats : 0 high, 5 medium, 18 low, 5 false, 1 maybe-false.
- 4 entrées corrigées :
  - suite de contrat vide (medium) ;
  - lectures `palier=1` qui contournaient le contrôle de version (low) ;
  - filtre de date des Risques non testé (low) ;
  - `IndexError` possible dans un test (low).
- Aucun élément différé.
- Constats rejetés, avec leur motif dans le Review Triage Log :
  - le manifeste corrompu qui bloque toute lecture est voulu ;
  - la duplication dans `_date_connue` et le coût d'un `exists()` sont sans effet ;
  - le refus paresseux AD-2 et l'ambiguïté de `()` pour une Entité non rouge sont des limites du port gelé ;
  - les autres sont réfutés.

**Revue de suivi recommandée : non.** Une seule entrée medium corrigée, et elle ne touche que des tests ; aucune high.

**Vérification.** `ruff check`, `ruff format --check`, `mypy` (233 fichiers), `lint-imports` (13 contrats) et `pytest -q` passent après les correctifs : 1805 réussis, 1 ignoré, 22 désélectionnés.

**Risques résiduels.**
- Un manifeste présent mais invalide fait échouer toutes les lectures du Passage. C'est voulu.
- Pour une Entité non rouge, `()` ne distingue pas « Prévision non calculée » de « aucun Risque ». L'UI ne le pourra qu'une fois l'étape `prevision` câblée (L4).
- Les deux fichiers de `tests/contrat/consultation/` sont hors lane.
