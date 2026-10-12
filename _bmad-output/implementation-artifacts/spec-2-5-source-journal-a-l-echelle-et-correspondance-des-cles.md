---
title: 'Story 2.5 : Source Journal à l''échelle et correspondance des clés'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'f80fa13e678ba61a9a701219f2a896388e65da96'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
warnings: ['oversized']
deferred:
  - summary: >-
      version_donnees ne reflète pas le manifeste d'injection : un même Journal lu aux clés générées puis aux clés Jira donne la même version de données.
    evidence: |-
      composition.py calcule version_donnees(octets du Journal, None) ; le spine (AD-16, Glossaire) définit version_donnees = SHA-256 du Journal + horodatage_extraction. Avant et après injection, deux Passages Journal seul ont des clés différentes et la même empreinte. Décision d'architecture à prendre avec la source composite (Story 2.6), qui introduit horodatage_extraction.
    location: >-
      src/usine/composition.py:291
    severity: low
---

<intent-contract>

## Intent

**Problem:** `SourceJournal` rend les clés générées (`DEMO-<n>` dans l'ordre de création), alors que la clé canonique en aval est la clé Jira (AD-4) : après injection, les Citations et les liens `<url_site>/browse/<clé>` d'un Passage Journal seul pointent vers d'autres tickets. Rien ne lit `donnees/injection/manifeste_injection.json`, et rien ne prouve que le Journal à la volumétrie cible (≈ 3 000 à 3 600 Anomalies, ≈ 40 000 événements depuis la 1.3) se charge et se calcule sans réseau (FR-8).

**Approach:** Ajouter à `usine.adaptateurs.journal` la lecture du manifeste (`charger_manifeste`, `CHEMIN_MANIFESTE_INJECTION`) et un paramètre `manifeste` à `SourceJournal` qui applique `correspondance_cles` à la lecture ; la composition passe le manifeste quand le fichier existe ; tests à l'échelle marqués `lent`, suite rapide sur le Programme réduit.

## Boundaries & Constraints

**Always:** sans manifeste, comportement et flux strictement inchangés ; avec manifeste : chaque `cle_ticket` remplacée par sa clé Jira, tous les autres champs (dont `id_evenement` `J-<rang>`, ordre, `source = journal`) inchangés ; clé du Journal absente de `correspondance_cles` → `UsineErreur` nommant le fichier, la ligne et la clé ; `manifeste.date_injection` ≠ `entete.date_injection` → `UsineErreur` nommant le fichier et les deux dates ; manifeste introuvable, JSON illisible, non objet ou invalide → `UsineErreur` nommant le fichier ; composition : manifeste chargé seulement si `racine / CHEMIN_MANIFESTE_INJECTION` existe, sinon Journal brut ; sélection « Journal seul » = celle de la 2.4 (pas de `config/jira.yaml`, pas de secret, ou Mode repli), `ConfigJira.mode` restant `cloud | dc` ; tests sans réseau (connexion socket interdite par fixture), données fictives `DEMO` ; tests à la volumétrie de `config/programme.yaml` marqués `lent` (sautés par défaut, marqueur enregistré dans un `conftest.py` de la lane) ; textes en français ; mypy strict, ruff, import-linter verts.

**Never:** modifier `src/usine/contrats/`, `src/usine/ports/`, `pyproject.toml`, `cli.py` racine, `tests/doublures/` ; changer `version_donnees` ni la forme de `DonneesPassage` ; source composite, coupure par instants, alignements (2.6) ; écrire le manifeste (injecteur, L1) ; toucher `verite_terrain.json` ; accès réseau ou Jira.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Sans manifeste | Journal seul | flux identique au fichier | — |
| Correspondance | Journal + manifeste `DEMO-n → DEMO-(n+500)` | mêmes événements, `cle_ticket` remplacée | — |
| Clé manquante | manifeste sans `DEMO-3` | — | `UsineErreur` : fichier, ligne, `DEMO-3` |
| Date incohérente | `date_injection` différente | — | `UsineErreur` : fichier, deux dates |
| Manifeste absent / illisible / invalide | fichier manquant, JSON cassé, tableau, champ manquant | — | `UsineErreur` nommant le fichier |
| `depuis` | avec manifeste | filtre identique, clés remplacées | sans fuseau → `UsineErreur` |
| Passage Journal seul + manifeste | mini-jeu, manifeste écrit, aucun secret, réseau coupé | Passage publié, `source == "journal"`, `tickets_etats` aux clés Jira | — |
| Passage sans manifeste | mini-jeu | clés générées (antérieur) | — |
| Échelle (`lent`) | `config/programme.yaml`, graine 42, manifeste | lecture complète, Instantanés à 1er jour, milieu, Date d'injection, schéma `SCHEMA_TICKET_ETAT`, clés toutes Jira | — |

</intent-contract>

## Code Map

- `src/usine/adaptateurs/journal/__init__.py` -- `SourceJournal(chemin)` : valide tout le Journal à la construction (≈ 0,35 s à l'échelle, mesuré), `_lire`, `_valider`, `entete`, `evenements(depuis)` ; ajouter `manifeste: ManifesteInjection | None = None` et la propriété `manifeste`. Remplacer la clé après validation (`model_copy(update=…)`, la clé Jira est déjà validée `CleTicket` par le manifeste).
- `src/usine/adaptateurs/journal/manifeste.py` (nouveau) -- `CHEMIN_MANIFESTE_INJECTION = REPERTOIRE_DONNEES / "injection" / "manifeste_injection.json"` (aucune constante dans `contrats.passage`, AD-4 donne ce chemin) et `charger_manifeste(chemin) -> ManifesteInjection` ; ré-exportés par le paquet.
- `src/usine/contrats/evenements.py:ManifesteInjection` -- lecture seule : `date_injection`, `cle_projet`, `correspondance_cles` (injective, clés Jira dans le projet).
- `src/usine/composition.py:construire_rapport` (≈ l. 284) -- `source = SourceJournal(chemin_journal)` : passer le manifeste s'il existe ; docstring du module à compléter. `empreinte_donnees` inchangée.
- `src/usine/generateur/journal.py:generer(config, graine, date_generation, cle_projet=…)` -- produit le Journal ; `config/programme.yaml` → ≈ 3 100 Anomalies, 39 800 événements, 8,6 Mo (graine 42, 2026-10-12).
- `src/usine/domaine/instantanes.py` -- `tickets_etats(evenements, dates)`, `instantane(etats)` ; `SCHEMA_TICKET_ETAT` (contrats) pour le modèle de sortie.
- `tests/unit/generateur/conftest.py` -- modèle du marqueur `lent` (enregistrement + saut sauf `-m lent`), à reproduire dans `tests/unit/adaptateurs/journal/conftest.py`.
- `tests/unit/chaine/environnement.py:preparer_racine` -- racine du mini-jeu (Programme réduit) ; `DATE_ARRETE`, `horloge_figee`.
- `tests/unit/test_composition.py:test_passage_sans_secret_journal_seul_sans_requete` -- modèle du Passage Journal seul.
- `tests/contrat/source_tickets/fabriques.py:FABRIQUES` -- ajouter `("journal_correspondance", …)`.

## Tasks & Acceptance

**Execution:**
- `src/usine/adaptateurs/journal/manifeste.py`, `src/usine/adaptateurs/journal/__init__.py` -- chemin, chargement du manifeste, paramètre `manifeste` de `SourceJournal` -- FR-8, AD-4.
- `src/usine/composition.py` -- passer le manifeste à `SourceJournal` quand `racine / CHEMIN_MANIFESTE_INJECTION` existe -- clés cohérentes avec les liens dans un vrai Passage.
- `tests/unit/adaptateurs/journal/conftest.py` -- marqueur `lent` et fixture `sans_reseau` (connexions socket interdites).
- `tests/unit/adaptateurs/journal/test_correspondance.py` -- matrice I/O côté adaptateur et manifeste.
- `tests/unit/adaptateurs/journal/test_echelle.py` -- test `lent` à la volumétrie cible.
- `tests/unit/test_composition.py` -- Passage Journal seul avec manifeste, réseau coupé.
- `tests/contrat/source_tickets/fabriques.py` -- fabrique `journal_correspondance`.

**Acceptance Criteria:**
- Given un Journal à la volumétrie cible et un `ManifesteInjection`, when `SourceJournal` le lit, then tous les `Evenement` portent la clé Jira de `correspondance_cles` et le flux est sinon identique au Journal (`uv run pytest -m lent tests/unit/adaptateurs/journal`).
- Given aucun secret Jira, un manifeste dans `donnees/injection/` et le réseau coupé, when `lancer_rapport` s'exécute, then le Passage est publié avec `source == "journal"` et `tickets_etats.parquet` ne contient que des clés Jira.
- Given les fabriques de contrat, when `uv run pytest tests/contrat` s'exécute, then la suite `SourceTickets` passe pour `journal_correspondance` comme pour `journal`.
- Given la suite par défaut, when `uv run pytest -q` s'exécute, then les tests `lent` sont sautés et aucun test nouveau ne génère le Journal complet.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 23 findings — high 0, medium 2, low 15, false 6, maybe-false 0
- findings:
  - `[low]` `[defer]` (blind) `version_donnees` ignore le manifeste — réel (même empreinte avant/après injection) ; la définition vient du spine (AD-16, « SHA-256 du Journal + horodatage_extraction »), antérieure à la story ; reportée à la 2.6 (frontmatter `deferred`).
  - `[low]` `[reject]` (blind) le manifeste du Passage ne dit pas quel espace de clés est utilisé — l'ajout d'un champ touche `ManifestePassage`, contrat gelé (contrats-v1).
  - `[low]` `[reject]` (blind) repli silencieux sans manifeste — voulu : avant injection aucun manifeste n'existe et le Passage Journal seul doit tourner ; un avertissement serait une nouvelle surface sans défaut constaté.
  - `[medium]` `[patch]` (blind) manifeste périmé d'une autre génération accepté si ses clés couvrent le Journal — groupe M : toute clé du manifeste absente du Journal lève désormais une `UsineErreur` (fichier, nombre, 5 clés au plus) ; test `test_cle_du_manifeste_absente_du_journal`.
  - `[low]` `[reject]` (blind) les erreurs de correspondance ne nomment pas le fichier du manifeste — `SourceJournal` reçoit un modèle, pas un chemin ; le chemin du manifeste est fixe (`CHEMIN_MANIFESTE_INJECTION`) ; passer le chemin ajoute un paramètre public.
  - `[false]` `[reject]` (blind) marqueur `lent` déjà déclaré dans `pyproject.toml` — faux : `addopts = ["-m", "not reseau", …]` et seul `reseau` y est déclaré (vérifié) ; avec `-m "not lent"` le test est désélectionné avant le crochet.
  - `[low]` `[reject]` (blind) `_motifs` dupliqué entre `__init__.py` et `manifeste.py` — style, libellé de repli différent, aucun appelant ne diverge.
  - `[low]` `[patch]` (blind) `DECALAGE = 500` : clés Jira fictives qui chevauchent les clés générées au-delà de 500 tickets — `DECALAGE = 100_000`.
  - `[low]` `[reject]` (blind) tests manquants (date incohérente via composition, `OSError`, validateurs du manifeste via `charger_manifeste`, `depuis`) — `depuis` est déjà testé (`test_depuis_avec_manifeste`) ; le surplus est couvert par le patch M ; le reste passe par des branches déjà testées au niveau adaptateur.
  - `[false]` `[reject]` (blind) suite de contrat dépendante d'un module de tests unitaires — motif existant : `fabriques.py` importe déjà `tests.unit.adaptateurs.jira_cloud.outils` et `jira_dc.outils`.
  - `[low]` `[reject]` (blind) `exists()` puis lecture (fenêtre de course) — l'injecteur n'écrit pas pendant un Passage (verrou, AD-4 « aucune modification pendant une injection ») ; l'échec serait bruyant.
  - `[false]` `[reject]` (blind) `date_injection` refusée pour une injection qui passe minuit — `date_injection` est la Date d'injection métier de l'en-tête du Journal, pas une date d'horloge ; l'injecteur la recopie.
  - `[false]` `[reject]` (intent) volumétrie cible testée seulement en `lent` — exigé par le run : tests de volumétrie marqués `lent`, suite rapide rapide ; le test tourne avec `-m lent` (vert).
  - `[low]` `[reject]` (intent) « date quelconque » testée au niveau domaine et une seule date via `lancer_rapport` — `EtapeInstantanes` appelle les mêmes `tickets_etats`/`instantane` ; un Passage complet à l'échelle alourdirait sans couvrir de code supplémentaire.
  - `[low]` `[reject]` (intent) pas de clé `adaptateur: journal` — `ConfigJira.mode` gelé (`cloud | dc`) ; la voie Journal seul est celle décidée en 2.4 (Design Notes).
  - `[false]` `[reject]` (intent) réseau coupé seulement dans les tests — c'est le critère : le code de production n'ouvre aucune connexion, les tests le prouvent.
  - `[low]` `[reject]` (intent) manifeste synthétique, pas celui de l'injecteur L1 — l'injecteur (Story 1.6) n'existe pas encore ; le contrat `ManifesteInjection` est la frontière.
  - `[low]` `[reject]` (intent) lecture « manifeste facultatif » — voulue (même motif que le repli silencieux) ; la partie `version_donnees` suit la ligne différée.
  - `[medium]` `[patch]` (edge) manifeste périmé, même Date d'injection — groupe M, traité ci-dessus.
  - `[low]` `[patch]` (edge) clés du manifeste absentes du Journal — groupe M, traité ci-dessus.
  - `[low]` `[defer]` (edge) `version_donnees` identique avec et sans manifeste — même ligne que la blind, différée.
  - `[false]` `[reject]` (edge) manifeste qui est un répertoire — `charger_manifeste` lève une `UsineErreur` « illisible » nommant le chemin : échec bruyant correct.
  - `[low]` `[reject]` (edge) suppression entre `exists()` et lecture — même motif que la ligne blind.

## Design Notes

- **Correspondance totale** : une clé du Journal sans clé Jira produirait un flux mi-généré mi-Jira, donc des liens faux en silence ; l'injecteur injecte tous les tickets (AD-4), d'où l'erreur bruyante.
- **Sélection « journal »** : `ConfigJira.mode` est gelé à `cloud | dc` (contrats-v1) ; comme en 2.4, le Journal seul est la voie sans configuration Jira, sans secret ou en Mode repli. Le critère « `adaptateur: journal` en configuration » est tenu par cette voie.
- **`version_donnees`** : le spine la fixe à « SHA-256 du Journal + `horodatage_extraction` » ; un manifeste modifié ne la change pas. Laissé en l'état (contrat, AD-16), à reprendre avec la source composite (2.6).
- **Fichiers hors lane** : `src/usine/composition.py` (passage du manifeste, AD-1) ; `tests/unit/test_composition.py` (test de ce câblage) ; `tests/contrat/source_tickets/fabriques.py` (fabrique Journal avec correspondance, prévue par son docstring).

## Verification

**Commands:**
- `uv run ruff check .` et `uv run ruff format --check .` -- aucun écart.
- `uv run mypy` -- aucune erreur.
- `uv run lint-imports` -- tous les contrats tenus.
- `uv run pytest -q` -- tout passe, tests `lent` sautés.
- `uv run pytest -q -m lent tests/unit/adaptateurs/journal` -- tests à l'échelle verts.
- `uv run python .github/scripts/controle_lanes.py --branche lane/2-extraction --base main` -- seuls les fichiers hors lane listés.

## Auto Run Result

Status: done

- **Changement** : `SourceJournal(chemin, manifeste=None)` applique `correspondance_cles` d'un `ManifesteInjection` à la lecture (clés Jira en aval, AD-4) ; clé du Journal absente, clé du manifeste inutilisée (manifeste périmé) ou Date d'injection différente → `UsineErreur`. `charger_manifeste` et `CHEMIN_MANIFESTE_INJECTION` (`donnees/injection/manifeste_injection.json`) lisent le manifeste ; la composition le passe quand le fichier existe. Le Journal à la volumétrie cible (≈ 3 100 Anomalies, ≈ 40 000 événements) se lit en ≈ 0,35 s ; testé en `lent`.
- **Fichiers** :
  - `src/usine/adaptateurs/journal/manifeste.py` -- chemin et chargement du manifeste.
  - `src/usine/adaptateurs/journal/__init__.py` -- paramètre `manifeste`, contrôles de cohérence, ré-exports.
  - `src/usine/composition.py` (hors lane) -- manifeste passé à `SourceJournal` s'il existe.
  - `tests/unit/adaptateurs/journal/{conftest,outils,test_correspondance,test_echelle}.py` -- marqueur `lent`, réseau coupé, matrice I/O, test à l'échelle.
  - `tests/unit/test_composition.py` (hors lane) -- Passages Journal seul avec et sans manifeste, manifeste invalide.
  - `tests/contrat/source_tickets/fabriques.py` (hors lane) -- fabrique `journal_correspondance`.
- **Revue** : 23 constats ; patchés : 1 entrée medium (manifeste périmé : clés du manifeste absentes du Journal refusées) et 1 low (décalage des clés fictives à 100 000) ; 1 report (`version_donnees` sans le manifeste, définition du spine, à reprendre en 2.6) ; le reste rejeté, motifs dans le Review Triage Log.
- **Relecture de suivi recommandée** : non (une seule entrée medium patchée, aucune high).
- **Vérification** : `ruff check`, `ruff format --check`, `mypy` (215 fichiers), `lint-imports` (13 contrats) verts ; `pytest -q` : 1563 réussis, 23 ignorés ; `pytest -m lent tests/unit/adaptateurs/journal` : 1 réussi (≈ 2 s) ; chaque ligne de la matrice I/O couverte par un test exécuté.
- **Risques résiduels** : manifeste réel de l'injecteur (Story 1.6) non éprouvé, seul le contrat `ManifesteInjection` fait frontière ; `version_donnees` identique avant et après injection (différé) ; un manifeste périmé couvrant exactement les mêmes clés que le Journal (même nombre de tickets) reste indétectable sans empreinte du Journal dans le manifeste.
