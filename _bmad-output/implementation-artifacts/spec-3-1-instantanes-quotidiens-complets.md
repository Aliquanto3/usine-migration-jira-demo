---
title: 'Story 3.1 : Instantanés quotidiens complets'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '0714669752662ca46ca4afecbf08fc62b4bd2463'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** La Story 0.4 a amorcé `tickets_etats` et `instantane`, mais le calcul n'est pas encore « complet » au sens de FR-10 et FR-14 : un flux qui contient deux fois le même `id_evenement` (recouvrement d'extraction, AD-3) n'est pas dédoublonné, une date qui n'est pas un Jour ouvré est acceptée sans erreur (AD-17), et l'ordre des lignes dépend de l'ordre d'arrivée des créations dans le flux. Rien ne prouve par un test de propriété qu'un Instantané passé est insensible aux événements postérieurs, ni que deux calculs donnent des DataFrames identiques, ordre des lignes compris.

**Approach:** Durcir `domaine/instantanes.py` sans toucher aux contrats : dédoublonnage par `id_evenement` (première occurrence), refus des dates hors Jours ouvrés, ordre canonique des lignes (date dans l'ordre fourni, puis `rang_cle`), puis tests de propriété et de déterminisme sur des flux construits à la main, des flux aléatoires à graine fixe et le Journal du générateur.

## Boundaries & Constraints

**Always:** fonctions pures en Polars (AD-9) ; temps via `contrats.calendrier` seulement (un événement compte en D si `jour_ouvre_de(horodatage) ≤ D`) ; sorties validées par `valider()` contre `SCHEMA_TICKET_ETAT`, `SCHEMA_TICKET_TEXTE` et `SCHEMA_INSTANTANE` ; erreurs en `UsineErreur`, message en français nommant la date fautive ; Entrée = création ou transition qui sort de `STATUTS_FERMES` (H-17), un `alignement` n'est jamais une Entrée (AD-4).

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` (gelés) ; modifier `tests/unit/domaine/constructeur.py` ou `chaine/` (hors lane) ; ajouter une dépendance (pas d'`hypothesis` : tests de propriété par graines fixes avec `random.Random` dans les tests seulement) ; KPI, Tendances ou Météo (Stories 3.2 et suivantes).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Doublon d'id | flux où un événement apparaît deux fois (même `id_evenement`) | résultat identique au flux sans doublon | aucune erreur ; première occurrence gardée |
| Date non ouvrée | `dates` contient un samedi | — | `UsineErreur` nommant la date (`2026-10-03`) |
| Ordre des clés | créations reçues `DEMO-10` puis `DEMO-2` | lignes `DEMO-2` puis `DEMO-10` à chaque date | — |
| Arrivée permutée | même flux, horodatages distincts, ordre d'arrivée mélangé | DataFrames identiques, ordre compris (`tickets_etats`, `tickets_textes`, `instantane`) | — |
| Futur ajouté | flux complet vs flux coupé aux événements de Jour ouvré ≤ D | lignes en D identiques (états et Instantané) | — |
| Trois types | Anomalies, Cas de test, Certifications | sorties valides contre les schémas | — |

</intent-contract>

## Code Map

- `src/usine/domaine/instantanes.py` -- `_table_evenements` (l. 39-47) : point d'entrée unique du flux, y ajouter le dédoublonnage ; `_etats_en` (l. 50-102) : trie aujourd'hui par `rang_creation` ; `tickets_etats` (l. 105-121) : contrôle déjà les dates en double, y ajouter le contrôle Jour ouvré ; `tickets_textes` (l. 128-158) : même tri par `rang_creation` ; `instantane` (l. 161-185) : déjà trié par toutes ses clés, déterministe.
- `src/usine/contrats/tickets.py` -- `rang_cle(cle)` (l. 18-25) : clé de tri canonique des clés de ticket, à réutiliser (lecture seule).
- `src/usine/contrats/calendrier.py` -- `est_jour_ouvre`, `jour_ouvre_de`, `jours_ouvres` (lecture seule).
- `src/usine/contrats/evenements.py` -- `Evenement`, `evenements_en_table` (lecture seule).
- `src/usine/chaine/etapes.py:44-51` -- seul appelant de production : passe `jours_ouvres(premier_jour, date_arrete)`, donc toujours des Jours ouvrés (aucun impact du nouveau contrôle).
- `src/usine/domaine/meteo.py` -- consomme `tickets_etats` par filtres et agrégats, insensible à l'ordre des lignes.
- `tests/unit/domaine/test_instantanes.py` -- tests existants de la Story 0.4 à garder verts ; y ajouter les nouveaux tests.
- `tests/unit/domaine/constructeur.py` -- `Flux` (hors lane, lecture seule) : construit des flux d'`Evenement` numérotés `J-<rang>`.
- `src/usine/generateur/journal.py` -- `generer(config, graine, date)` : Journal synthétique pour les tests de propriété sur flux réaliste.

## Tasks & Acceptance

**Execution:**
- `src/usine/domaine/instantanes.py` -- (1) dans `_table_evenements`, ne garder que la première occurrence de chaque `id_evenement` dans l'ordre reçu, avant d'attribuer `rang` ; (2) dans `tickets_etats`, lever `UsineErreur` si une date n'est pas un Jour ouvré (« … n'est pas un Jour ouvré ») ; (3) dans `_etats_en` et `tickets_textes`, trier les lignes par `rang_cle(cle_ticket)` (ordre calculé en Python sur les clés uniques, puis jointure ou `sort_by`) au lieu de `rang_creation` ; mettre les docstrings à jour -- FR-10, FR-14, AD-3, AD-17.
- `tests/unit/domaine/test_instantanes.py` -- ajouter : doublon d'id ; date non ouvrée refusée ; ordre `rang_cle` ; déterminisme (deux calculs égaux, et arrivée permutée à horodatages distincts égale ordre compris) ; propriété « futur ajouté » sur ~20 flux aléatoires à graine fixe (trois types de tickets, réouvertures, week-ends) et sur le Journal du générateur pour plusieurs D ; validation des trois schémas -- couvre la matrice.

**Acceptance Criteria:**
- Given un flux d'`Evenement` (Anomalies, Cas de test, Certifications), when le domaine calcule les `TicketEtat` pour chaque Jour ouvré ≤ D puis l'Instantané, then les sorties passent `valider()` contre `SCHEMA_TICKET_ETAT` et `SCHEMA_INSTANTANE`.
- Given un flux et une date passée D, when on ajoute des événements postérieurs à D, then les lignes en D de `tickets_etats` et de `instantane` sont inchangées.
- Given deux calculs sur le même flux, when on compare les DataFrames, then ils sont identiques, ordre des lignes compris.
- Given les cinq contrôles du dépôt, when on les lance, then ruff, ruff format, mypy, lint-imports et pytest passent.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 15 findings — high 0, medium 0, low 9, false 6, maybe-false 0
- findings:
  - `[false]` `[reject]` (blind) La docstring du module promettrait une indépendance totale à l'ordre d'arrivée — elle ne parle que de l'ordre des lignes (« indépendant de l'ordre d'arrivée des créations ») et de deux calculs sur le même flux, ce qui est exact.
  - `[low]` `[reject]` (blind) Le dédoublonnage « première occurrence » dépend de l'ordre d'arrivée si un doublon diverge — réel seulement pour un même `id_evenement` au contenu divergent, impossible avec les identifiants déterministes d'AD-3 ; la règle est assumée dans les Design Notes et un garde-fou ajouterait une branche sans cas atteignable.
  - `[false]` `[reject]` (blind) Les flux aléatoires à horodatages distincts cachent le départage à horodatage égal — ce départage par l'ordre du flux est la règle voulue (Story 0.4, Design Notes) ; une permutation à horodatage égal n'est pas « le même flux ».
  - `[low]` `[reject]` (blind) `tickets_textes` n'exige pas un Jour ouvré — une Date d'arrêté de week-end donne l'état du vendredi, sans erreur de calcul ; ajouter le refus pourrait casser la Chaîne sur une date utilisateur, hors de l'intention.
  - `[low]` `[reject]` (blind) L'erreur de date non ouvrée ne nomme que la première — cosmétique ; le seul appelant passe `jours_ouvres`.
  - `[low]` `[reject]` (blind) Tests de dédoublonnage incomplets (copie divergente arrivée en premier, autre horodatage) — `_sans_doublons` s'applique avant tout tri dans `_table_evenements`, le cas est correct par construction.
  - `[low]` `[reject]` (blind) Test du Journal : `jours[-2]` et double appel dans le même ordre — la permutation est couverte par les 20 flux aléatoires ; à `jours[-1]` le flux coupé égale le flux complet.
  - `[low]` `[reject]` (blind) Constantes de statuts recopiées dans les tests — dérive improbable, contrats gelés.
  - `[low]` `[reject]` (blind) Contrôle des dates en double quadratique — préexistant, ~40 dates par Passage.
  - `[false]` `[reject]` (blind) Artefacts absents et appelants cassés par le refus des week-ends — le seul appelant (`chaine/etapes.py:44`) passe `jours_ouvres(...)` ; le statut de sprint est mis à jour à l'intégration.
  - `[low]` `[reject]` (edge) Doublon d'id divergent selon l'ordre d'arrivée — même cause que la ligne blind correspondante, même motif.
  - `[false]` `[reject]` (edge) `vers.last()` à horodatage égal dépend de l'ordre — règle voulue (départage par l'ordre du flux), testée par `test_meme_horodatage_ordre_du_flux`.
  - `[low]` `[reject]` (edge) `tickets_textes` accepte un week-end — même motif que la ligne blind.
  - `[false]` `[reject]` (edge) Deux créations de types différents pour une même clé — entrée invalide qu'aucune source ne produit (une clé = un ticket, AD-3) ; aucun chemin montré.
  - `[false]` `[reject]` (intent) Attente portée par Passage et Consultation, diff limité au domaine — les critères de la story sont formulés au niveau du domaine (« le domaine calcule… ») ; la Chaîne calcule déjà chaque Jour ouvré et la Consultation est couverte par ses tests (Stories 0.5, 0.6).

## Design Notes

- Dédoublonnage : garder la première occurrence (et non lever une erreur) aligne le domaine sur le port `Entrepot` (« dédoublonnés par `id_evenement` ») ; un doublon au contenu divergent relève de la source, pas du calcul.
- Ordre des lignes : `rang_cle` rend la sortie indépendante de l'ordre d'arrivée des créations (deux sources ou deux paginations du même historique). Exemple attendu : créations reçues `DEMO-10`, `DEMO-2` → lignes `DEMO-2`, `DEMO-10`. L'ordre entre événements au même horodatage reste celui du flux (règle de la Story 0.4).
- Le report différé « `entite` dans `non_nulles` » touche `contrats/` (gelé) : hors périmètre ; aucun changement ici.

## Verification

**Commands:**
- `uv run pytest -q tests/unit/domaine` -- expected: tous verts
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: succès

## Auto Run Result

- **Résumé :** `domaine/instantanes.py` dédoublonne le flux par `id_evenement` (première occurrence), refuse dans `tickets_etats` toute date qui n'est pas un Jour ouvré, et ordonne les lignes de `tickets_etats` et `tickets_textes` par date (ordre fourni) puis `rang_cle`, indépendamment de l'ordre d'arrivée des créations. Tests de propriété (futur ajouté sans effet) et de déterminisme (ordre compris, arrivée permutée) sur 20 flux aléatoires à graine fixe et sur le Journal du générateur.
- **Fichiers :**
  - `src/usine/domaine/instantanes.py` -- dédoublonnage, contrôle Jour ouvré, ordre canonique.
  - `tests/unit/domaine/test_instantanes.py` -- 11 tests (dont 40 cas paramétrés) pour la matrice et les critères.
  - `_bmad-output/implementation-artifacts/epic-3-context.md` -- contexte compilé de l'Epic 3.
- **Revue :** 15 findings, 0 patch, 0 différé, 15 rejetés (9 low, 6 false), motifs dans le Review Triage Log.
- **Revue de suivi recommandée :** non (aucun patch).
- **Vérification :** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (168 fichiers), `uv run lint-imports` (13 contrats tenus), `uv run pytest -q` (1021 passés, 1 sauté) : tous verts. Audit de matrice : chaque ligne couverte par un test passé.
- **Risques résiduels :** un doublon d'`id_evenement` au contenu divergent est écarté sans trace ; l'ordre des lignes par ticket a changé (création → `rang_cle`), sans effet sur les consommateurs actuels (`meteo.py`, Consultation).
- **Fichiers hors lane :** aucun.
