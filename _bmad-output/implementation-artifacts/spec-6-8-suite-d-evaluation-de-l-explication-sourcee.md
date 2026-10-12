---
title: "Story 6.8 : Suite d'évaluation de l'Explication sourcée"
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '2e5015c3928d4a83fd61edf9d337e6eb18c739dc'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Rien ne mesure la fidélité des Explications sourcées avant la démo (SM-3 : 100 % de Citations valides, note humaine moyenne ≥ 4/5 sur 10 cas). `evals/` ne contient qu'un `__init__.py`.

**Approach:** Créer `evals/explication/` : 10 cas versionnés (Météo de l'Entité à la Date d'arrêté, tickets en cause, KPI et Causes racines facultatifs, réponses enregistrées), un exécuteur qui passe chaque cas par la vraie tâche `expliquer` (passerelle comprise) puis applique `controler_citations` à chaque sortie et publie le taux de Citations valides, et une commande de notation qui enregistre la moyenne humaine avec les versions de prompt et de modèle. Par défaut, rejeu hors réseau des réponses enregistrées (testé en CI) ; l'exécution réelle exige `--reel`.

## Boundaries & Constraints

**Always:** `evals` n'importe que contrats, ports, domaine et `usine.composition` (import-linter) : la composition expose une façade `construire_explicateur` et `controler_citations`. Mode par défaut sans réseau ni secret (fournisseur `FournisseurEnregistre` et pseudonymiseur identité définis dans `evals/explication`). Le mode `--reel` lit `config/llm.yaml`, la clé du fournisseur et `USINE_CLE_PSEUDO` comme un Passage Palier 2, avec un cache en mémoire (pas de cache de production). Taux = phrases retenues / phrases totales de `controler_citations(sortie.texte, tickets en cause du cas)` cumulées sur les cas : une « explication indisponible » compte comme phrase invalide. Notes entières de 1 à 5 (exactitude, utilité).

**Never:** lancer `--reel` dans les tests ou la CI ; toucher `rendu/`, `ia/agent`, `evals/agent`, `contrats/` ; lire `donnees/verite_terrain.json` (inutile ici) ; modifier `ia/explication.py` ou son prompt.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Rejeu nominal | 10 cas, réponses enregistrées conformes | résultat JSON : 10 sorties, taux 100 %, versions, notes à `null` | — |
| Phrase hors cause | réponse enregistrée citant un ticket hors cause | phrase retirée par la passerelle (`phrases_retirees` publié), taux inchangé | — |
| Explication indisponible | réponses enregistrées toutes rejetées | phrase « explication indisponible » comptée invalide, taux < 100 % | — |
| Réponses épuisées | cas sans assez de réponses enregistrées | `UsineErreur` nommant le cas | arrêt, code ≠ 0 |
| Cas invalide | JSON mal formé ou moins de 10 cas | `UsineErreur` nommant le fichier | arrêt |
| Notation complète | 10 cas notés 1..5 | moyenne écrite dans `historique.jsonl` avec versions, taux, verdict SM-3 | — |
| Notation incomplète | note manquante ou hors 1..5 | `UsineErreur` nommant le cas | rien n'est écrit |

</intent-contract>

## Code Map

- `src/usine/ia/explication.py:212` -- (lecture seule) `expliquer(passerelle, meteo_entite, textes, contexte, *, kpi, repartition)` ; `ContexteExplication(passage_id, version_donnees, gabarit)`, `lire_prompt()`.
- `src/usine/ia/controles.py:50` -- (lecture seule) `controler_citations(texte, tickets_autorises) -> ControleCitations(texte, citations, phrases_retirees, phrases_total)`.
- `src/usine/composition.py:285,255,605` -- `construire_fournisseur`, `_verifier_llm`, `_pseudonymiseur`, `_tarif_registre` : à réutiliser dans la nouvelle façade, insérée après `_fermer_tous` (l. 337) pour limiter les conflits avec la 6.7.
- `src/usine/ia/passerelle.py` -- `Passerelle(fournisseur, pseudonymiseur, cache, horloge, tarif=...)`.
- `src/usine/ports/{fournisseur_llm,pseudonymiseur,cache_llm}.py` -- ports implémentés par les doublures d'`evals`.
- `tests/doublures/fournisseur_factice.py` -- modèle de `FournisseurEnregistre` (jetons = mots).
- `tests/unit/ia/espions.py:132,155` -- `meteo_rouge`, `textes` : forme d'une `MeteoEntite` et de `SCHEMA_TICKET_TEXTE`.
- `pyproject.toml:310` -- contrat « hors produit » : `evals` interdit d'`usine.ia`, `usine.config`, `usine.adaptateurs`.

## Tasks & Acceptance

**Execution:**
- `src/usine/composition.py` -- `construire_explicateur(racine, fournisseur=None, pseudonymiseur=None)` : objet appelable `(meteo, textes, kpi, repartition) -> SortieExplication` portant `version_prompt` et `version_modele` ; `fournisseur=None` = mode réel (config + secrets) ; ré-export de `controler_citations`.
- `evals/explication/cas.py` -- modèle `CasExplication` et `charger_cas(repertoire)` (exactement 10 cas, identifiants uniques).
- `evals/explication/cas/cas-01.json` … `cas-10.json` -- 10 cas variés (rouge/orange, une ou plusieurs règles, KPI, causes, une phrase hors cause, une régénération).
- `evals/explication/suite.py` -- `FournisseurEnregistre`, `PseudonymiseurIdentite`, `executer_suite`, `noter`, et le CLI `python -m evals.explication {executer [--reel], noter <resultat>}` (`__main__.py`).
- `evals/explication/README.md` -- protocole, grille de notation, commande réelle et coût estimé.
- `tests/unit/evals/explication/test_suite.py` -- matrice I/O, rejeu complet des 10 cas, notation, refus de `--reel` sans secrets non testé (réseau).

**Acceptance Criteria:**
- Given les 10 cas versionnés, when `uv run python -m evals.explication executer` s'exécute sans réseau, then un fichier `evals/explication/resultats/<horodatage>.json` publie le taux de Citations valides après `controler_citations` et les versions de prompt et de modèle.
- Given un fichier de résultat noté, when `uv run python -m evals.explication noter <fichier>` s'exécute, then `evals/explication/historique.jsonl` reçoit la moyenne, les versions et `sm3_atteint` (taux 100 % et moyenne ≥ 4).
- Given la CI, when `uv run pytest -q` s'exécute, then la suite rejouée tourne sans appel réseau.

## Spec Change Log

## Review Triage Log

### 2026-10-13 — Review pass (mode économique : Edge Case Hunter seul ; Blind Hunter, Verification Gap et Intent Alignment sautés)
- verdicts: 14 findings — high 0, medium 3, low 7, false 4, maybe-false 0
- findings:
  - `[low]` `[reject]` `noter` : un élément non objet dans `cas` lève une `AttributeError` (trace au lieu du code 1) — fichier corrompu à la main, cas rare ; garde supplémentaire non justifiée.
  - `[low]` `[reject]` `taux_citations_valides` booléen accepté (`float(True) == 1.0`) — falsification délibérée du fichier, hors usage normal.
  - `[medium]` `[patch]` `noter` accepte un résultat tronqué ou à identifiants en double et peut enregistrer `sm3_atteint` — corrigé : refus si le nombre de cas diffère de `NOMBRE_CAS` (10) ou si un identifiant est en double ; test `test_notation_refuse_un_resultat_tronque_ou_en_double`.
  - `[low]` `[reject]` deux exécutions dans la même seconde écrasent le résultat — improbable pour une suite lancée à la main.
  - `[low]` `[reject]` horloge naïve décale le nom de fichier — l'horloge n'est injectée que par les tests, toujours en UTC.
  - `[low]` `[reject]` réponses enregistrées non consommées sans échec — le test du cas 07 vérifie déjà deux tentatives.
  - `[medium]` `[patch]` `phrases_retirees` ne compte que la tentative finale (cas 07 régénéré) — corrigé : `Explicateur.__call__` renvoie aussi les traces ; par cas, `phrases_retirees` cumulé sur les traces et champ `tentatives` ; total 3 au lieu de 1.
  - `[false]` `[reject]` plafond de coût atteint en mode réel compté comme Citation invalide — plafond 2 € contre ~0,25 € de coût estimé pour toute la suite : inatteignable.
  - `[low]` `[reject]` cas sans ticket en cause compté invalide en silence — les 10 cas versionnés ont tous des tickets en cause (test des cas).
  - `[false]` `[reject]` réponse enregistrée invalide pour le schéma — les réponses sont déjà des `ReponseExplication` validées au chargement du cas ; la revalidation du même JSON ne peut pas échouer.
  - `[low]` `[patch]` `--racine` par défaut sur le répertoire courant — corrigé : `Path(__file__).resolve().parents[2]`.
  - `[false]` `[reject]` le mode réel écrit la table de pseudonymes de production — voulu par la spec (« comme un Passage Palier 2 ») ; les cas ne contiennent que des données fictives.
  - `[medium]` `[patch]` verdict SM-3 sans contrôle des 10 cas (doublon du 3e constat) — même correctif.
  - `[false]` `[reject]` taux à 100 % quasi tautologique — choix documenté (Design Notes, README) ; la qualité brute est publiée par `phrases_retirees`, désormais cumulé sur toutes les tentatives.

## Design Notes

Le contrôle de la passerelle garantit déjà des Citations valides pour toute sortie non rejetée : le taux après contrôle mesure donc surtout les explications indisponibles, et `phrases_retirees` (publié par cas) mesure la qualité brute. Coût du mode réel (Sonnet 5.5, 3 $/15 $ par MTok) : 10 à 20 appels × ~1 500 jetons d'entrée et ~400 de sortie, soit environ 0,10 à 0,25 €.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert.
- `uv run python -m evals.explication executer --sortie <tmp>` -- expected: taux 100 % publié, sans réseau.

## Auto Run Result

- **Résumé** : suite `evals/explication/` (10 cas versionnés, rejeu hors réseau par défaut, `--reel` séparé), taux de Citations valides après `controler_citations`, notation humaine 1..5 enregistrée dans `historique.jsonl` avec versions de prompt et de modèle et verdict SM-3.
- **Fichiers** :
  - `src/usine/composition.py` — façade `construire_explicateur` / `Explicateur` (cache en mémoire), ré-export de `controler_citations`.
  - `evals/explication/cas.py`, `cas/cas-01..10.json` — modèle et 10 cas.
  - `evals/explication/suite.py`, `__main__.py` — fournisseur enregistré, pseudonymiseur identité, exécution, notation, CLI.
  - `evals/explication/README.md` — protocole, grille, commande réelle et coût (~0,10 à 0,25 €).
  - `tests/unit/evals/explication/test_suite.py` — 26 tests (matrice I/O, CLI, notation).
- **Revue** : 14 constats ; 3 corrigés (2 entrées medium, 1 low), 0 différé, 11 rejetés (motifs au journal).
- **Revue de suivi** : la règle donne `true` (deux medium corrigés) ; risque non revérifié : la nouvelle signature d'`Explicateur.__call__`. Non lancée (mode économique : pas de revue de suivi sans high).
- **Vérification** : `ruff check`, `ruff format --check`, `mypy` (308 fichiers), `lint-imports` (14 contrats), `pytest -q` (2513 passés, 1 sauté) verts.
- **Risques résiduels** : mode `--reel` jamais exécuté ; conflit possible avec la 6.7 dans les imports de `composition.py`.
