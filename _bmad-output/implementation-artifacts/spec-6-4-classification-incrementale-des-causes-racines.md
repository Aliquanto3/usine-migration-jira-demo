---
title: 'Story 6.4 : Classification incrémentale des Causes racines'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '4e59d1b04b5180312bef3d00fd8d64388de4b368'
review_loop_iteration: 1
followup_review_recommended: false
context: []
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** L'étape `classification` est sautée même en Palier 2 : aucune Cause racine n'est proposée, `llm/classification.json` n'est jamais écrit et le manifeste ne porte jamais `classification_initiale`. Le schéma demandé au fournisseur (`ReponseClassification`) manque aux contrats.

**Approach:** Contrats 1.4 (additif) : `ReponseClassification`. Nouvelle tâche `ia/classification.py` + prompt `ia/prompts/classification.md` : un appel par Anomalie des `TicketTexte` via la passerelle (clé de cache sans Date d'arrêté, déjà en 6.3) ; l'incrémentalité vient du cache, qui ne manque que pour une Anomalie nouvelle ou dont le texte a changé. Étape `EtapeClassification` câblée par la composition ; la Chaîne pose `classification_initiale` quand la classification a appelé le fournisseur sans aucun succès en cache.

## Boundaries & Constraints

**Always:** passage par `Passerelle.executer_structure` (ordre AD-12, Pseudonymisation de l'entrée) ; une `SortieClassification` par Anomalie classée, triée par `rang_cle`, `cause_racine` parmi les 7 `CauseRacine` (H-18) ; `statut_controle` fixé par un contrôle déterministe (`conforme`, ou `corrige` si la justification citait une autre clé de ticket, retirée) ; titres et descriptions entre délimiteurs dans le prompt (données, pas instructions) ; `version_prompt` = octets du gabarit ; commit contrats dédié `Feat: contrats 1.4, …` en tête (`CONTRATS_VERSION` 1.4.0).

**Never:** pas d'écriture dans Jira ni d'usage de la Cause racine hors suggestion ; ne pas toucher `rendu/`, `ia/explication.py`, `ia/etape.py` (lane 6.6 en parallèle) au-delà du nécessaire ; pas de répartition (6.5) ; pas d'import d'`adaptateurs` depuis `ia`/`chaine` ; aucun appel réseau dans les tests.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Premier Passage | 3 Anomalies, cache vide | 3 appels, 3 sorties, manifeste `classification_initiale = true` | — |
| Rejeu | mêmes textes, autre Date d'arrêté | 0 appel fournisseur, mêmes sorties, `classification_initiale = false` | — |
| Incrémental | 1 Anomalie nouvelle, 1 description modifiée, 1 inchangée | 2 appels, 1 succès en cache | — |
| Hors Anomalie | `cas_de_test`, `certification` dans les textes | ignorés, aucun appel | — |
| Aucune Anomalie | table vide | sortie vide, aucune trace, `classification_initiale = false` | — |
| Plafond atteint | `PlafondCoutAtteint` sur une Anomalie | Anomalie non classée (absente de la sortie), étape réussie | journal warning |
| Justification hors cible | justification citant `DEMO-9` pour `DEMO-1` | clé retirée, `corrige` | — |
| Fournisseur en erreur | `UsineErreur` | Passage en échec, « étape « classification » » | propagé |

</intent-contract>

## Code Map

- `src/usine/contrats/llm.py:~170` -- ajouter `ReponseClassification(Enregistrement)` : `cause_racine: CauseRacine`, `justification: str = ""` (à côté de `ReponseExplication`).
- `src/usine/contrats/versions.py:9` -- `CONTRATS_VERSION` → 1.4.0 ; tests `test_evenements.py:140`, `test_llm.py:70`, `test_passage.py:103,212,220,224,228-236`, `test_versions.py:24`.
- `_bmad-output/planning-artifacts/architecture/architecture-usine-migration-jira-demo-2026-10-10/ARCHITECTURE-SPINE.md:21` -- ligne d'amendement contrats 1.4.
- `src/usine/ia/passerelle.py` -- seul ajout : paramètre nommé optionnel `plafond_eur: Decimal | None = None` de `executer_structure` ; un appel frais lève `PlafondCoutAtteint` si le cumul du Passage atteint `min(plafond du Passage, plafond_eur)` ; le cache reste servi (changement additif minimal, la lane 6.6 touche aussi ce fichier). Sinon lecture seule : `executer_structure`, `ContexteAppel` (`cible` = clé du ticket), `Controle`, `PlafondCoutAtteint` ; `cle_cache` ignore déjà la Date d'arrêté pour `Tache.classification`.
- `src/usine/ia/controles.py` -- `retirer_citations_hors(texte, autorises)` réutilisable pour la justification.
- `src/usine/ia/explication.py` -- modèle à suivre (lecture seule) : `lire_prompt`, `rendre_prompt`, `DELIMITEUR`, boucle et repli plafond.
- `src/usine/ia/classification.py` (nouveau) -- `lire_prompt`, `ContexteClassification`, `classer(passerelle, textes, date_arrete, contexte) -> (sorties, traces)`, `EtapeClassification` (sortie `"classification"`).
- `src/usine/ia/prompts/classification.md` (nouveau) -- 7 catégories avec libellés de `LIBELLES_CAUSES_RACINES`/valeurs d'énumération, ticket entre délimiteurs.
- `src/usine/chaine/execution.py:~85-115` -- `classification_initiale` = au moins une trace LLM `tache=classification` et aucune `depuis_cache`.
- `src/usine/composition.py:~516` -- `registre[Etape.classification] = EtapeClassification(passerelle, empreinte_donnees, empreinte_grille)` (`version_grille` tracée seulement, AD-16). Passer aussi `plafond_eur` = plafond du Passage × `PART_PLAFOND_CLASSIFICATION` (`None` sans plafond).
- `tests/unit/ia/espions.py` -- `textes`, `pseudonymiseur`, `CacheMemoire`, `horloge_espion` ; `tests/doublures/fournisseur_factice.py` (`FournisseurFactice`, `appels`).
- `tests/unit/chaine/test_execution.py:544-840` -- `_passer_en_palier_2` pour l'essai de bout en bout (manifeste, rejeu).

## Tasks & Acceptance

**Execution:**
- `src/usine/contrats/{llm,versions}.py`, tests de version, spine -- contrats 1.4 (commit dédié) -- AD-2, AD-13.
- `src/usine/ia/prompts/classification.md`, `src/usine/ia/classification.py` -- tâche et étape -- FR-35, AD-12.
- `src/usine/chaine/execution.py` -- `classification_initiale` -- AD-8, NFR-9.
- `src/usine/composition.py` -- câblage Palier 2.
- `src/usine/ia/passerelle.py`, `src/usine/ia/classification.py` -- part du plafond réservée à la classification (`plafond_eur`, `PART_PLAFOND_CLASSIFICATION = Decimal("0.5")`, `EtapeClassification(..., plafond_eur: Decimal | None = None)`) ; tests : appel frais refusé au-delà de la part mais cache servi, et explications encore appelées après une classification arrêtée à sa part -- NFR-9.
- `tests/unit/ia/test_classification.py` -- matrice I/O (premier passage, rejeu, incrémental, hors Anomalie, vide, plafond, justification, Pseudonymisation de l'entrée) et absence de Cause racine dans les adaptateurs Jira (`adaptateurs/jira_*`, `composite`).
- `tests/unit/chaine/test_execution.py` -- manifeste : `classification_initiale` vrai au premier Passage Palier 2, faux au rejeu ; `llm/classification.json` publié.

**Acceptance Criteria:**
- Given un Passage Palier 2 sur un entrepôt sans cache, when il se publie, then `llm/classification.json` porte une Cause racine par Anomalie et le manifeste `classification_initiale = true` ; au Passage suivant à textes identiques, aucun appel de classification et `classification_initiale = false`.
- Given le code des adaptateurs Jira, when on y cherche la Cause racine proposée, then aucune référence (`SortieClassification`, `cause_racine`, `classification`).

## Spec Change Log

### 2026-10-12 — Passe de revue 1 (bad_spec)
- **Constat déclencheur :** la classification s'exécute avant les explications et puise dans le même plafond du Passage. Stock de 3 000 à 4 000 Anomalies (`config/programme.yaml`) à ~700 jetons d'entrée sur `claude-sonnet-5-5` : ~10 € pour le stock complet, contre un plafond de 2 €. Le premier Passage, puis chaque Passage de rattrapage, épuise le plafond et toutes les explications tombent en « plafond de coût atteint ».
- **Amendement :** la classification ne dépense au plus que `PART_PLAFOND_CLASSIFICATION` (0,5) du plafond du Passage, via `plafond_eur` de la passerelle ; le reste du stock est classé aux Passages suivants (incrémental par le cache). Code Map, Tasks et Design Notes mis à jour.
- **État évité :** explications et narration indisponibles tant que le stock n'est pas entièrement classé.
- **KEEP :** tout le reste du code et des tests (contrats 1.4, prompt, `_Controleur`, `classer`, `EtapeClassification`, `classification_initiale`, câblage, échappement des points des regex de version dans `test_source_journal.py:94` et `consultation/test_passage.py:405`) ; reprise par-dessus, sans revert complet (mode économique).

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 8 findings — high 1, medium 0, low 5, false 2, maybe-false 0
- findings:
  - `[high]` `[bad_spec]` Classification et explications partagent le plafond du Passage : le stock initial (3 000 à 4 000 Anomalies, ~10 € sur Sonnet) épuise les 2 € et toutes les explications se dégradent — amendement : part de 0,5 du plafond réservée à la classification (`plafond_eur`), voir Spec Change Log.
  - `[low]` `[reject]` Plafond qui coupe le stock en cours : `classification_initiale` vrai sur un stock incomplet, les Passages de rattrapage comptent dans les mesures — détecter la coupure demanderait un signal de l'étape vers la Chaîne (champ de `ResultatEtape`) ; rattrapage borné à la part du plafond, consigné en risque résiduel.
  - `[low]` `[reject]` Passage où toutes les Anomalies sont nouvelles ou modifiées marqué initial — remplacement intégral du stock improbable hors premier Passage ou changement de prompt/modèle, cas que l'exclusion couvre à juste titre.
  - `[low]` `[reject]` Clé d'un autre projet (`OTHER-9`) gardée dans la justification — même règle que le contrôle des explications (`citations` par projet) ; le Programme n'a qu'un projet ; corriger demanderait une variante du contrôle partagé (fichier commun avec la lane 6.6).
  - `[low]` `[patch]` Points non échappés dans la regex de version, `tests/unit/adaptateurs/journal/test_source_journal.py:94` — corrigé (`1\.4\.0`).
  - `[low]` `[patch]` Idem `tests/unit/consultation/test_passage.py:405` — corrigé.
  - `[false]` `[reject]` Spec : toute clé étrangère retirée — même constat que la clé d'un autre projet ; la spec parle d'« autre clé de ticket » au sens du contrôle partagé, comportement assumé (ligne précédente).
  - `[false]` `[reject]` Commit contrats dédié risqué — les commits ne sont pas encore faits ; le commit `Feat: contrats 1.4, …` est créé en tête à la finalisation.

### 2026-10-12 — Review pass (après boucle bad_spec)
- verdicts: 2 findings — high 0, medium 0, low 0, false 2, maybe-false 0
- findings:
  - `[false]` `[reject]` Deux lignes d'Anomalie de même `cle_ticket` dans les textes — `domaine/instantanes.tickets_textes` produit une ligne par ticket créé au plus tard en D (réduction par clé) : doublon impossible en entrée de l'étape.
  - `[false]` `[reject]` Entrées de cache illisibles rappelées : un seul succès en cache rend `classification_initiale` faux — c'est la définition retenue (Design Notes) : un stock partiellement servi par le cache n'est pas un stock complet classé ; une entrée illisible rappelée compte bien comme appel frais.

## Design Notes

Incrémentalité par le cache plutôt que par un diff explicite avec le Passage précédent : l'entrée pseudonymisée (clé, titre, description) est dans la clé de cache, la Date d'arrêté n'y est pas ; une Anomalie inchangée est donc servie sans appel, une nouvelle ou modifiée part au fournisseur. `classification_initiale` en découle : appels frais sans aucun succès en cache = stock complet classé (premier Passage, ou changement de prompt ou de modèle, exclu à juste titre des mesures). Le plafond laisse l'Anomalie sans suggestion (pas de libellé : la Cause racine n'est qu'une suggestion). La classification ne prend qu'une part du plafond du Passage (0,5) : explications et narration gardent leur budget ; le stock initial se complète sur quelques Passages.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert.

## Auto Run Result

Status: done

- **Changement :** étape `classification` du Palier 2 : une Cause racine proposée (7 catégories H-18) par Anomalie des `TicketTexte`, via la passerelle (Pseudonymisation, cache sans Date d'arrêté → incrémental : seules les Anomalies nouvelles ou modifiées partent au fournisseur) ; justification contrôlée (`conforme`/`corrige`) ; `llm/classification.json` publié ; manifeste `classification_initiale` vrai quand la classification a appelé le fournisseur sans aucun succès en cache ; la classification ne dépense au plus que la moitié du plafond du Passage (`plafond_eur` de la passerelle), le reste du stock se complète aux Passages suivants ; contrats 1.4 (`ReponseClassification`).
- **Fichiers :** `src/usine/contrats/{llm,versions}.py` (contrats 1.4) ; `src/usine/ia/classification.py`, `src/usine/ia/prompts/classification.md` (nouveaux) ; `src/usine/ia/passerelle.py` (`plafond_eur`, additif) ; `src/usine/chaine/execution.py` (`classification_initiale`) ; `src/usine/composition.py` (câblage, part du plafond) ; spine (amendement 1.4) ; tests `tests/unit/ia/test_classification.py` (nouveau), `tests/unit/chaine/test_execution.py`, tests de version.
- **Revue (Edge Case Hunter seul, mode économique) :** passe 1 : 8 constats, 1 high (plafond partagé avec les explications) traité par boucle bad_spec (part de 0,5 du plafond), 2 low corrigés (regex de version), 3 low et 2 faux rejetés ; passe 2 (après le correctif high) : 2 faux rejetés. Aucun report.
- **Revue de suivi :** non recommandée (le high a été revu en passe 2).
- **Vérification :** ruff check, ruff format --check, mypy, lint-imports (14 contrats) et pytest -q (2461 passés, 1 sauté) verts.
- **Risques résiduels :** stock initial de 3 000 à 4 000 Anomalies ≈ 10 € sur `claude-sonnet-5-5` : à 1 € par Passage pour la classification, il faut une dizaine de Passages pour tout classer, et seul le premier porte `classification_initiale` ; une justification qui cite une autre clé perd la phrase entière ; une clé d'un autre projet n'est pas détectée (contrôle partagé, un seul projet) ; un avertissement journalisé par Anomalie refusée au plafond.
