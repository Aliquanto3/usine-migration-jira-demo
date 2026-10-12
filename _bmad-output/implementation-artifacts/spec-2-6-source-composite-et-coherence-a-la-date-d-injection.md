---
title: 'Story 2.6 : Source composite et cohérence à la Date d''injection'
type: 'feature'
created: '2026-10-12'
baseline_revision: '49381455086cc2d966f1a11702e0af2affced5e8'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
warnings: ['oversized']
deferred:
  - summary: >-
      Après une réinjection qui recule la coupure, un alignement déjà stocké mais désormais antérieur à la nouvelle horodatage_fin_injection est coupé, ré-détecté à chaque Passage et jamais re-persisté (même identifiant).
    evidence: |-
      id_alignement ne dépend que de (clé, champ, vers) et extraire ignore les identifiants connus ; SourceComposite coupe tout événement Jira ≤ horodatage_fin_injection, alignements compris. Non vérifié : dépend de la Story 1.7 (réinjection idempotente), qui dira si l'entrepôt est conservé ou remis à zéro après réinjection.
    location: >-
      src/usine/adaptateurs/entrepot_duckdb/extraction.py (extraire, filtre des alignements connus)
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** Après injection, le Passage ne lit que le Journal : une transition faite à la main dans Jira n'apparaît jamais, aucun `Evenement` `alignement` n'est produit quand l'état rejoué diffère de Jira (H-27), le manifeste du Passage porte `nb_alignements=0` en dur (`chaine/execution.py`, constat 17 de la rétro Epic 0), et `version_donnees` est identique avec ou sans manifeste d'injection (différé de la 2.5).

**Approach:** Nouveau paquet `usine.adaptateurs.composite` : `SourceComposite` (tout le Journal lu aux clés Jira, puis les seuls événements Jira d'horodatage > `horodatage_fin_injection`), détection et conversion d'état en alignements. L'étape `extraction` persiste les alignements détectés dans la même transaction et expose leur nombre ; la composition bascule en source `composite` quand l'extraction Jira est active et qu'un manifeste existe, et la Chaîne recopie `nb_alignements` et `horodatage_extraction` au manifeste du Passage.

## Boundaries & Constraints

**Always:** flux composite trié par horodatage (Journal avant Jira à horodatage égal), `id_evenement` uniques, `depuis` sans fuseau → `UsineErreur` ; coupure strictement par instant (`>` `horodatage_fin_injection`, alignements compris) ; alignement : `id_evenement = A-<cle>-<champ>-<sha256(vers)[:8]>`, `de` = valeur rejouée (ou `None`), `vers` = valeur Jira, horodaté à l'instant de détection, `source` = source Jira du ticket ; champs comparés = champs d'état (`statut`, `entite`, `vague`, `domaine`, `gravite`, `phase`, `statut_test`, `statut_certification`), jamais `titre`/`description` ; état Jira = rejeu des seuls événements Jira non `alignement` ; persisté une seule fois (dédoublonnage par id), `nb_alignements` = alignements nouvellement persistés par ce Passage ; événements extraits et alignements validés dans une seule transaction ; Journal seul (pas de secret, Mode repli, pas de `config/jira.yaml` ou pas de manifeste) inchangé hormis `version_donnees` ; tests sans réseau, données fictives `DEMO` ; mypy strict, ruff, import-linter verts.

**Never:** modifier `src/usine/contrats/`, `src/usine/ports/`, `tests/doublures/`, `pyproject.toml` ; importer `usine.domaine` depuis `adaptateurs/` ; ouvrir l'entrepôt hors de l'étape `extraction` ; écrire le manifeste d'injection (L1) ; appel Jira réel (recette 2.7).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Coupure | Journal + manifeste + événements Jira avant `debut`, dans l'intervalle, à `fin` exact, après `fin` | tout le Journal (clés Jira) puis les seuls événements Jira `> fin`, triés | — |
| `depuis` | instant UTC | événements `≥ depuis` des deux origines | sans fuseau → `UsineErreur` |
| Journal sans manifeste | `SourceJournal(chemin)` | — | `UsineErreur` à la construction |
| Cohérence FR-49 | Journal mini-jeu, injection simulée fidèle, état Jira à `fin` converti | `instantane(tickets_etats(…, [Date d'injection]))` identiques (vrai domaine) | — |
| Injection infidèle | un ticket à gravité différente dans Jira | Instantanés différents ; détection = 1 alignement `gravite` | — |
| Détection | état rejoué ≠ état Jira sur un champ d'état | 1 `alignement` persisté, `nb_alignements = 1` | — |
| Re-détection | 2ᵉ extraction, même écart | rien d'ajouté, horodatage de la 1ʳᵉ détection gardé, `nb_alignements = 0` | — |
| Texte différent | `titre` Jira ≠ Journal | aucun alignement | — |
| Détection trop tôt | instant de détection ≤ `fin` | — | `UsineErreur` nommant les deux instants |
| Passage composite | config Jira + secret + manifeste, Jira doublé (injection + transition manuelle après `fin` + 1 écart) | `source == "composite"`, transition visible dans `tickets_etats`, `nb_alignements == 1`, `horodatage_extraction` renseigné | — |
| `version_donnees` | Journal seul avec / sans manifeste ; composite | trois empreintes distinctes | — |

</intent-contract>

## Code Map

- `src/usine/adaptateurs/composite/` (nouveau, lane L2) -- `SourceComposite(journal: SourceJournal, jira: Callable[[], Iterable[Evenement]])` (manifeste lu sur `journal.manifeste`, `heapq.merge` stable) ; `etats_tickets`, `alignements`, `id_alignement`, `convertir_etat_jira(evenements_jira, instant)` (créations Jira ≤ instant + un alignement par champ d'état, pour FR-49) ; `DetecteurAlignements(journal)` appelable `(evenements_jira, instant) -> list[Evenement]`. N'importe ni `domaine` ni `entrepot_duckdb`.
- `src/usine/adaptateurs/journal/__init__.py:SourceJournal` -- propriétés `manifeste`, `entete` ; `evenements(depuis)` dans l'ordre du fichier.
- `src/usine/adaptateurs/entrepot_duckdb/extraction.py` -- `extraire(..., aligner=None)` : avec `aligner`, matérialise stockés + nouveaux (dédoublonnés), ajoute les alignements inconnus au même `enregistrer` ; `ResultatExtraction.alignements`, `.evenements` ; `EtapeExtraction(..., aligner=None)`, `nb_alignements`, `evenements_extraits()` (`UsineErreur` si non exécutée ou sans `aligner`).
- `src/usine/adaptateurs/entrepot_duckdb/entrepot.py:evenements` -- ordre `horodatage, lot, rang`.
- `src/usine/composition.py:construire_rapport`, `_etape_extraction`, `lancer_rapport`, `Rapport` -- hors lane (AD-1).
- `src/usine/chaine/execution.py:executer_passage` -- `nb_alignements=0` en dur l. 97 ; hors lane (L5).
- `src/usine/contrats/versions.py:version_donnees(journal, horodatage_extraction)`, `contrats/passage.py:ManifestePassage` (`horodatage_extraction`, `nb_alignements`), `DonneesPassage` -- lecture seule.
- `src/usine/domaine/instantanes.py:tickets_etats`, `instantane` -- vrai domaine du test FR-49 (création requise pour qu'un ticket existe).
- `src/usine/adaptateurs/jira_cloud/conversion.py:convertir_ticket` -- `C-<id>`, `C-<id>-<champ>` : modèle des événements Jira simulés.
- `tests/unit/adaptateurs/journal/outils.py` -- `manifeste_pour` (injection 18:00–18:20 UTC à la Date d'injection), `cle_jira`, `couper_reseau`.
- `tests/unit/chaine/environnement.py` -- `preparer_racine` (Date d'injection 2026-10-09 = `DATE_ARRETE`), `horloge_figee` (`INSTANT` 2026-10-12).
- `tests/unit/test_composition.py` -- modèles `racine_journal`, `_interdire_le_client`.
- `tests/contrat/source_tickets/fabriques.py:FABRIQUES` -- ajouter `composite`.

## Tasks & Acceptance

**Execution:**
- `src/usine/adaptateurs/composite/{__init__,source,alignements}.py` -- source, rejeu d'état, alignements, conversion FR-49, détecteur -- FR-49, AD-4, H-27.
- `src/usine/adaptateurs/entrepot_duckdb/{extraction,__init__}.py` -- paramètre `aligner`, bilan et accès aux événements extraits -- persistance atomique, compte.
- `src/usine/chaine/execution.py` -- paramètres `horodatage_extraction: datetime | None = None` et `nb_alignements: Callable[[], int] | None = None` (lu après les étapes) -- constat 17.
- `src/usine/composition.py` -- source composite si extraction active et manifeste ; instant d'extraction figé à la composition (repère, détection, `version_donnees`) ; empreinte = Journal (+ `\n` + manifeste s'il existe) ; `Rapport.horodatage_extraction` ; `lancer_rapport` transmet les deux valeurs.
- `tests/unit/adaptateurs/composite/{__init__,outils,test_source,test_alignements,test_coherence}.py` -- matrice I/O ; injection simulée depuis `tickets_etats` du Journal.
- `tests/unit/adaptateurs/entrepot_duckdb/test_extraction.py` -- `aligner`, atomicité, une seule persistance.
- `tests/unit/chaine/test_execution.py` -- valeurs recopiées au manifeste.
- `tests/unit/test_composition.py` -- Passage composite de bout en bout (source Jira doublée), deux Passages, empreintes.
- `tests/contrat/source_tickets/fabriques.py` -- fabrique `composite`.

**Acceptance Criteria:**
- Given un Journal, un manifeste et des événements Jira fixtures, when `SourceComposite` produit le flux, then il contient tout le Journal puis les seuls événements Jira `> horodatage_fin_injection`.
- Given l'état Jira juste après injection converti en alignements, when le domaine calcule les deux Instantanés à la Date d'injection, then ils sont identiques.
- Given un écart état rejoué / état Jira, when l'étape `extraction` s'exécute deux fois, then un seul alignement `A-<cle>-<champ>-<sha8(vers)>` est stocké, horodaté à la première détection, et le manifeste du Passage porte `nb_alignements` 1 puis 0.
- Given les fabriques de contrat, when `uv run pytest tests/contrat` s'exécute, then la suite `SourceTickets` passe pour `composite`.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 26 findings — high 0, medium 1, low 19, false 5, maybe-false 1
- findings:
  - `[low]` `[reject]` (intent) `version_donnees` : définition effective partagée entre `contrats.versions` et la composition (manifeste ajouté aux octets) — décision consignée en Design Notes ; `contrats/` gelé ; écart de lettre au Glossaire à porter par `bmad-correct-course`.
  - `[false]` `[reject]` (intent) compte par Passage plutôt que total — H-27 : « émis et compté » par extraction ; le total reste lisible dans l'entrepôt ; aucun résultat faux.
  - `[low]` `[reject]` (intent) FR-49 sur une injection simulée, pas sur les fixtures HTTP Cloud/DC — l'injection simulée *est* la fixture d'événements Jira ; les adaptateurs produisent le même contrat `Evenement`, vérifié par la suite `SourceTickets` (dont `composite`) ; le vrai Jira relève de la recette 2.7.
  - `[false]` `[reject]` (intent) `convertir_etat_jira` sans appelant de production — l'AC FR-49 est un test ; la détection H-27 couvre le chemin d'exécution.
  - `[false]` `[reject]` (intent) fichiers hors lane non consignés — consignés dans les Design Notes (« Fichiers hors lane »).
  - `[false]` `[reject]` (intent) Mode repli sans source composite — voulu : le Mode repli coupe l'extraction (2.4), donc pas d'événements Jira frais.
  - `[low]` `[reject]` (intent) détection avant la fin d'injection refusée — garde délibérée (sinon l'alignement serait coupé) ; seul un Passage pendant une injection, interdit par AD-4, la déclenche.
  - `[low]` `[patch]` (intent) alignement jamais montré dans un rapport publié — groupe P2 : test à une Date d'arrêté ≥ jour de détection.
  - `[low]` `[reject]` (edge) alignements pour un ticket Jira sans création dans le flux composite (`cree` inutilisé) — n'arrive que pour un ticket créé à la main pendant l'injection, interdit par AD-4 ; correction = nouvelle règle sans défaut constaté.
  - `[low]` `[reject]` (edge) ticket du rejeu absent de Jira non signalé — le contrat `Evenement` n'a pas de nature « suppression » (`alignement` exige un champ) ; contrats gelés.
  - `[low]` `[reject]` (edge) type rejoué ≠ type Jira — l'injecteur crée le type du Journal ; aucun chemin montré.
  - `[maybe-false]` `[defer]` (edge) réinjection avec une nouvelle `horodatage_fin_injection` qui coupe un alignement déjà stocké, ré-détecté mais jamais re-persisté (même id) — dépend du comportement de la réinjection (Story 1.7, entrepôt conservé ou non) ; medium si vrai (frontmatter `deferred`).
  - `[low]` `[reject]` (blind) `version_donnees` hors docstring du contrat, concaténation par `\n` ambiguë — même décision que la ligne intent ; collision par concaténation sans portée pratique (SHA-256).
  - `[low]` `[patch]` (blind) `horodatage_extraction` à `None` alors qu'une extraction sans manifeste tourne — groupe P5 : docstring de `executer_passage` précisée (« `None` hors source composite ») ; les données du Passage ne dépendent alors d'aucune extraction.
  - `[low]` `[reject]` (blind) `EtatTicket.cree` inutilisé, existence des tickets — même analyse que les deux lignes edge.
  - `[false]` `[reject]` (blind) un alignement de `statut` ne compte pas comme Entrée — règle du domaine (L3), testée par `test_alignement_n_est_jamais_une_entree`.
  - `[low]` `[patch]` (blind) aucun test ne montre l'effet d'un alignement sur un rapport — groupe P2.
  - `[low]` `[reject]` (blind) id d'alignement indépendant de l'instant : un retour à une valeur déjà alignée est ignoré — exige un écart sans événement de changelog revenant exactement à une valeur déjà alignée ; « une seule fois » est l'exigence H-27.
  - `[low]` `[reject]` (blind) événement Jira tardif antérieur à un alignement plus récent — exige un retard d'indexation Jira au-delà de la marge ; la détection suivante réaligne.
  - `[low]` `[patch]` (blind) `CHAMPS_ETAT` dupliqué adaptateur / domaine sans garde — groupe P3 : test de parité.
  - `[low]` `[reject]` (blind) compte perdu si une étape ultérieure échoue — les alignements restent dans l'entrepôt (auditables) ; un compte cumulé exigerait un état hors Passage.
  - `[low]` `[reject]` (blind) Jira vide un champ : écart silencieux — décision consignée (Design Notes) ; champs d'état obligatoires.
  - `[low]` `[reject]` (blind) historique chargé plusieurs fois en mémoire — ≈ 40 000 événements à l'échelle, quelques Mo ; pas de défaut mesuré.
  - `[low]` `[reject]` (blind) chemin DC composite et Mode repli + manifeste non testés en composition — même code que Cloud ; source DC des alignements testée en unitaire ; Mode repli inchangé depuis 2.4/2.5.
  - `[low]` `[patch]` (blind) message « non exécutée » après un échec — groupe P4 : « non exécutée ou en échec ».
  - `[medium]` `[patch]` (verification-gap) instant figé jamais testé avec une horloge qui avance — groupe P1 : Passage composite avec `horloge_pas_a_pas()`.

## Design Notes

- **Instant d'extraction figé à la composition** : `version_donnees` doit être connue avant le Passage (`EtapeExplications` la reçoit) et `DonneesPassage` est gelé ; le repère pris à la composition reste antérieur à l'appel de la source (plus de recouvrement, jamais moins).
- **`version_donnees` (différé 2.5)** : la fonction de `contrats.versions` reste l'unique définition ; la composition lui passe les octets du Journal suivis de `\n` et du manifeste quand il existe (Journal *lu*), et `horodatage_extraction` en composite. Sans manifeste ni extraction, l'empreinte est inchangée. Écart de lettre au Glossaire (« SHA-256 du Journal ») à confirmer par `bmad-correct-course`.
- **Champs d'état seulement** : titre et description passent par ADF côté Cloud ; un espace de différence produirait un alignement par ticket. Les Instantanés n'utilisent que les champs d'état.
- **Valeur Jira vide** : pas d'alignement vers `None` (identifiant sans `vers`).
- **Fichiers hors lane** : `src/usine/composition.py` (câblage, AD-1) ; `src/usine/chaine/execution.py` (constat 17 : `nb_alignements` et `horodatage_extraction` au manifeste) ; `tests/unit/test_composition.py`, `tests/unit/chaine/test_execution.py` (tests de ce câblage) ; `tests/contrat/source_tickets/fabriques.py` (fabrique composite).

## Verification

**Commands:**
- `uv run ruff check .` et `uv run ruff format --check .` -- aucun écart.
- `uv run mypy` -- aucune erreur.
- `uv run lint-imports` -- tous les contrats tenus.
- `uv run pytest -q` -- tout passe.
- `uv run python .github/scripts/controle_lanes.py --branche lane/2-extraction --base main` -- seuls les fichiers hors lane listés.
