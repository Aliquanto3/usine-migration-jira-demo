---
title: 'Story 6.7 : Narration de la Prévision'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '3aff9e1ea1bc97252072dffab1ea40ee61599b2d'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** L'étape `narration` de la Chaîne est déclarée (`Etape.narration`, `llm/narrations.json`, `SortieNarration`, `Consultation.narrations`) mais toujours sautée : aucune tâche `narration`, aucun schéma `ReponseNarration`, aucun contrôleur `controler_nombres` (AD-14). Le Pilote n'a donc aucune phrase qui raconte la Prévision (FR-24), et rien ne garantit qu'une narration ne contienne pas de chiffre inventé (NFR-1).

**Approach:** Ajouter `ReponseNarration` aux contrats (1.4.0, additif, commit dédié) ; `controler_nombres` dans `ia/controles.py` (ajout en fin de fichier) ; une tâche `ia/narration.py` (prompt `ia/prompts/narration.md`) qui, pour chaque Entité ayant une `Prevision` ou des `RisqueEntreeRouge` à la Date d'arrêté, demande une phrase construite sur les seules valeurs fournies, la contrôle et, si elle est rejetée (ou plafond atteint), publie la Prévision brute (texte déterministe) avec `statut_controle = rejete` ; une `EtapeNarration` câblée en Palier 2 dans `composition.py`.

## Boundaries & Constraints

**Always:** passer par `Passerelle.executer_structure` (Pseudonymisation, cache, contrôle, trace), comme la 6.6 ; lectures via le port `Consultation` (`previsions`, `risques`) ; valeurs du prompt formatées par `contrats.format` et données entre délimiteurs ; `version_prompt` calculée sur les octets du gabarit envoyé ; une `SortieNarration` par Entité, triée par Entité ; pas de régénération (le rejet affiche la Prévision brute, AC 2) ; prompt en français.

**Never:** modifier `rendu/`, `ia/passerelle.py` ; modifier ou réordonner l'existant de `ia/controles.py` (6.4 en parallèle : ajout en fin de fichier seulement) ; faire calculer un chiffre au LLM ; changement non additif des contrats.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Narration conforme | nombres et dates tous fournis | `SortieNarration(texte=<phrase>, conforme)` | — |
| Nombre inventé | « 12 jours » absent des valeurs | texte = Prévision brute, `rejete` ; warning journalisé | — |
| Date inventée | `20/10/2026` absente | idem rejet | — |
| Formes acceptées | `60 %` pour 3/5, `0,6`, `3/5`, `1 234` (espace fine ou insécable), `15/10/2026`, `2026-10-15`, `15 octobre 2026`, `1er octobre` | conforme si la valeur (ou sa forme `contrats.format`) est fournie | — |
| Jetons ignorés | `DEMO-12`, `IND-1`, `ENT-A`, `J-5`, `COMPTE_1a2b3c` | non contrôlés | — |
| Texte vide | `texte` blanc | rejet, Prévision brute | — |
| Plafond de coût | `PlafondCoutAtteint` | Prévision brute, `rejete`, pas d'échec du Passage | — |
| Aucune Prévision ni Risque | Passage sans `previsions.json` ou sans Entité concernée | `narrations = ()`, aucun appel | — |
| Entité en Risque | 1..n `RisqueEntreeRouge` | une narration de l'ensemble des Risques de l'Entité | — |
| Palier 1 | — | étape `narration` sautée (inchangé) | — |

</intent-contract>

## Code Map

- `src/usine/contrats/llm.py:173` -- après `ReponseExplication` : `class ReponseNarration(Enregistrement): texte: str`. `src/usine/contrats/versions.py:9` → `1.6.0` ; tests de version : `tests/unit/contrats/test_{evenements,llm,passage,versions}.py`, `test_inventaire.py:82`.
- `src/usine/ia/controles.py` -- ajouter `ControleNombres` (`refuses: tuple[str, ...]`, `conforme`) et `controler_nombres(texte, valeurs_autorisees: Iterable[int | Fraction | Decimal | date])`. Masquer d'abord clés (`MOTIF_CLE_TICKET`, couvre `IND-n`), `ENT-[A-Z0-9]+`, `J-\d+`, jetons (`CANDIDAT_JETON` de `contrats.llm`) ; puis dates (`JJ/MM/AAAA`, ISO, « J mois [AAAA] ») ; puis nombres français (milliers U+0020/U+00A0/U+202F, virgule décimale, `%` facultatif). Égalité en valeur absolue avec une valeur fournie, ou avec son arrondi au nombre de décimales écrit (forme `contrats.format`) ; `%` compare à la valeur × 100.
- `src/usine/ia/explication.py:62,67` -- réutiliser `rendre_prompt` (message générique à paramétrer par nom de tâche, rétrocompatible) et `DELIMITEUR`/`_donnee`.
- `src/usine/ia/narration.py` (nouveau) -- `lire_prompt`, `ContexteNarration`, `prevision_brute(prevision, risques) -> str`, `narrer(passerelle, entite, date_arrete, version_grille, prevision, risques, contexte) -> (SortieNarration, traces)`. Valeurs du prompt et valeurs autorisées produites par le même collecteur. `ContexteAppel(cible=entite)`, `ParametresAppel(tache=Tache.narration, max_jetons_sortie=256)`.
- `src/usine/ia/prompts/narration.md` (nouveau) -- consigne : une phrase en français, aucune valeur hors du bloc, dates `JJ/MM/AAAA`.
- `src/usine/ia/etape.py` -- `EtapeNarration` : `ctx.consultation.previsions(ctx.date_arrete)`, `risques(ctx.date_arrete)`, groupés par Entité ; sortie `{"narrations": ...}`.
- `src/usine/composition.py:516` -- `registre[Etape.narration] = EtapeNarration(passerelle, empreinte_donnees)`.
- `src/usine/contrats/prevision.py:56,105` -- (lecture seule) `Prevision`, `RisqueEntreeRouge`.
- `tests/unit/ia/espions.py`, `tests/unit/ia/test_etape.py:30` -- doublures ; `tests/unit/chaine/test_execution.py:556-720` -- tests Palier 2 : ajouter les réponses `ReponseNarration` après les explications (le fournisseur factice sert dans l'ordre).

## Tasks & Acceptance

**Execution:**
- `src/usine/contrats/llm.py`, `versions.py` + tests de version -- `ReponseNarration`, 1.6.0 (commit `Feat: contrats 1.6, …`).
- `src/usine/ia/controles.py` -- `controler_nombres` -- AC 2.
- `src/usine/ia/narration.py`, `src/usine/ia/prompts/narration.md` -- tâche, repli brut -- AC 1, 2.
- `src/usine/ia/etape.py`, `src/usine/composition.py` -- étape câblée en Palier 2 -- AC 1.
- `tests/unit/ia/test_controles.py`, `tests/unit/ia/test_narration.py`, `tests/unit/ia/test_etape.py` -- matrice I/O.
- `tests/unit/chaine/test_execution.py` -- Passage Palier 2 : `narration` réussie, `llm/narrations.json` lisible par `Consultation.narrations()`.

**Acceptance Criteria:**
- Given une `Prevision` ou des `RisqueEntreeRouge` à la Date d'arrêté, when l'étape `narration` s'exécute en Palier 2, then chaque Entité concernée reçoit une `SortieNarration` (phrase du LLM, `conforme`) publiée dans `llm/narrations.json`, et le prompt envoyé contient les seules valeurs de la Prévision.
- Given une narration contenant un nombre ou une date absents des valeurs fournies, when `controler_nombres` s'applique (clés, `IND-n`, `ENT-x`, `J-n` et jetons ignorés ; nombres au format français), then la narration est rejetée : `texte` = Prévision brute, `statut_controle = rejete`.
- Given le plafond de coût atteint, when la narration est demandée, then la Prévision brute est publiée sans échec du Passage.

## Spec Change Log

- 2026-10-13 : intégration après les Stories 6.4 (contrats 1.4) et 6.5 (contrats 1.5) sur main : `ReponseNarration` passe en contrats 1.6.0 (l'Approach, figée, dit 1.4.0). Tests de Chaîne réalignés sur `FournisseurPalier2` (classification servie seule, narrations scriptées après les explications) ; `repartition_causes` et `narration` réussies en Palier 2.

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 8 findings — high 2, medium 3, low 0, false 3, maybe-false 0
- findings:
  - `[high]` `[patch]` Nombre collé à des lettres (`12j`, `10h`, `3e`) non contrôlé : un chiffre inventé passait `conforme` (NFR-1) — corrigé : lookarounds de `_NOMBRE` et `_FRACTION` sur les seuls chiffres ; test `test_nombre_colle_a_des_lettres_est_controle`.
  - `[false]` `[reject]` Jetons de forme clé à numéro inventé (`IND-9`, `J-40`, `ENT-12`) ignorés — AD-14 et l'AC 2 imposent d'ignorer clés, `IND-n`, `ENT-x`, `J-n` : comportement exigé par l'intention.
  - `[medium]` `[patch]` Nombre à plus de 28 décimales : `quantize` lève `InvalidOperation`, l'étape échoue au lieu de publier la Prévision brute — corrigé : au-delà de 6 décimales, égalité exacte seulement ; test `test_nombre_a_trop_de_decimales_refuse_sans_erreur`.
  - `[false]` `[reject]` Deux Prévisions pour une Entité (baseline et ML) — `domaine/prevision/baseline.py:109` produit une seule `Prevision` par Entité rouge ; pas de Modèle ML livré.
  - `[medium]` `[patch]` Libellés de facteurs porteurs de nombres (« les 5 derniers Jours ouvrés », `baseline.py:247-262`) : narration fidèle rejetée — corrigé : les entiers des libellés envoyés au prompt sont autorisés ; test `test_nombre_d_un_libelle_de_facteur_est_autorise`.
  - `[false]` `[reject]` `version_grille` différente entre Prévision et Risques d'une Entité — un Passage n'a qu'une Grille (`verifier_grille` à la composition) ; les deux viennent de la même étape `prevision`.
  - `[high]` `[patch]` (claim) AC 2 promis mais nombres collés aux lettres non contrôlés — même cause que le premier constat, même correctif.
  - `[medium]` `[patch]` (claim) Rejet promis mais `InvalidOperation` fait échouer l'étape — même cause que le troisième constat, même correctif.

### 2026-10-12 — Review pass (suivi, Edge Case Hunter ciblé sur `controler_nombres`)
- verdicts: 8 findings — high 2, medium 3, low 1, false 0, maybe-false 0
- findings:
  - `[high]` `[patch]` Entier suivi d'une virgule de ponctuation (`dans 99, puis`) jamais contrôlé — corrigé : lookahead `(?!\d)(?!,\d)`, lookbehind `(?<!\d)(?<!\d,)`.
  - `[medium]` `[patch]` `3 %,` : le `%` perdu par retour arrière, comparé aux valeurs brutes — corrigé par le même lookahead ; test `10 %,` refusé.
  - `[medium]` `[patch]` Date partielle `JJ/MM` (`15/12`) acceptée si jour et mois sont des entiers autorisés — corrigé : `n/d` de forme jour/mois contrôlé contre les dates autorisées (sauf fraction autorisée).
  - `[medium]` `[patch]` Date `JJ/MM/AA` découpée en trois entiers — corrigé : motif `_DATE_COURTE` (XXIe siècle).
  - `[low]` `[reject]` Fraction à milliers groupés (`1 000/2 000`) mal lue — improbable dans une phrase de narration, correctif non trivial.
  - `[high]` `[patch]` Nombre à point (`2.15`) lu comme deux entiers — corrigé : `_POINT_DECIMAL` toujours refusé.
  - `[medium]` `[patch]` Mois abrégés (`15 oct.`) : seul le jour contrôlé — corrigé : abréviations ajoutées à `_MOIS`, point facultatif.
  - `[high]` `[patch]` (claim) AC 2 contournable par ces formes — mêmes causes, mêmes correctifs ; tests `test_revue_de_suivi_formes_{refusees,acceptees}`.

## Design Notes

« Prévision brute affichée » : `rendu/` est interdit à l'epic et ne lit pas encore les narrations ; la Prévision brute est donc portée par `SortieNarration.texte` (statut `rejete`), texte déterministe formé des mêmes valeurs. L'UI (Epic 7) affiche la narration seulement si elle a passé le contrôle. Nombres en toutes lettres non contrôlés (hors AD-14). Un nombre écrit sans signe est comparé en valeur absolue (« baisse de 3 » pour −3).

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports` -- expected: aucun écart
- `uv run pytest -q` -- expected: tout vert

## Auto Run Result

Status: done

**Changement :** l'étape `narration` est câblée en Palier 2. Pour chaque Entité qui a une `Prevision` ou des `RisqueEntreeRouge` à la Date d'arrêté, la tâche `narration` demande une phrase construite sur les seules valeurs fournies (formatées par `contrats.format`, entre délimiteurs). `controler_nombres` (AD-14) refuse tout nombre ou toute date absents ; un rejet, un texte vide ou le plafond de coût publient la Prévision brute (texte déterministe, `rejete`) sans régénération ni échec du Passage.

**Fichiers :**
- `src/usine/contrats/llm.py`, `versions.py` -- `ReponseNarration`, contrats 1.6.0 (commit dédié ; 1.4 et 1.5 pris par les Stories 6.4 et 6.5).
- `src/usine/ia/controles.py` -- `ControleNombres`, `controler_nombres` (ajout en fin de fichier, imports en tête).
- `src/usine/ia/narration.py`, `src/usine/ia/prompts/narration.md` -- tâche, collecteur commun prompt / valeurs autorisées, Prévision brute.
- `src/usine/ia/explication.py` -- `rendre_prompt` nomme la tâche (paramètre facultatif).
- `src/usine/ia/etape.py`, `src/usine/composition.py` -- `EtapeNarration`, câblée en Palier 2.
- `tests/unit/ia/*`, `tests/unit/chaine/test_execution.py`, tests de version -- matrice I/O, Passage Palier 2 avec `llm/narrations.json`.

**Revue (mode économique, Edge Case Hunter seul) :** 8 constats ; 5 patchés (2 high, 3 medium, regroupés en 3 causes) ; 3 rejetés (false, voir Review Triage Log) ; rien de différé. Correctifs du parent avant revue : entier sans décimale jamais accepté comme arrondi d'une valeur non entière hors pourcentage, libellés français des statuts et méthodes. Revue de suivi faite (Edge Case Hunter ciblé) : 8 constats, 7 patchés (formes de nombres et de dates qui échappaient au contrôle), 1 low rejeté. Pas d'autre passe : le mode économique n'en prévoit qu'une.

**Vérification :** `ruff check`, `ruff format --check`, `mypy` (304 fichiers), `lint-imports` (14 contrats) verts ; `pytest -q` : 2533 passés après fusion de main (6.4, 6.5), 1 ignoré, 38 désélectionnés.

**Risques résiduels :** `rendu/` ne lit pas encore les narrations (interdit à l'epic) : elles sont publiées dans `llm/narrations.json` pour l'UI Palier 2 (Epic 7). Contrôle volontairement strict : nombres en toutes lettres non contrôlés ; une suite de chiffres séparés par des espaces est lue comme un nombre à milliers ; un nombre accolé à des lettres (`S3`) est contrôlé et peut faire rejeter une phrase. Merge avec la 6.4 : `composition.py` (ligne voisine du câblage) et la fin de `ia/controles.py` peuvent entrer en conflit trivial.
