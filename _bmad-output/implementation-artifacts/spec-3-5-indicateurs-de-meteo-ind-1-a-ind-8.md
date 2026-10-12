---
title: 'Story 3.5 : Indicateurs de météo IND-1 à IND-8'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '82bdf5d81f3918687b1359fb3ca3afc068e610f4'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** le domaine ne calcule qu'IND-1 et refuse tout autre indicateur actif ; la Grille livrée (version 2) porte donc IND-2 à IND-8 inactifs, et la Météo ignore âge des bloquantes, majeures, taux de KO, Certifications, ratio Entrées/Sorties et hausse du KO (FR-11, FR-16, NFR-1).

**Approach:** calculer dans `domaine/meteo.py` les huit indicateurs, exacts (`numerateur`/`denominateur` entiers), avec `statut = non_evaluable` et un `motif` quand un garde-fou ou une donnée manquante l'impose ; Phase en cours et Vague en cours tirées de `ConfigProgramme` et de l'ancrage des semaines ; activer IND-2 à IND-8 dans la Grille (version 3) et passer Programme et historique J-5..D à `EtapeMeteo`.

## Boundaries & Constraints

**Always:** fonctions pures (pas d'I/O, d'horloge, de hasard) ; comparaisons en `Fraction` via `_franchit` ; un indicateur non évaluable vaut `0/0`, couleur `vert`, `motif` non vide, et ne change jamais la Météo ; ordre de sortie déterministe (Entités dans l'ordre de `entites`, indicateurs actifs dans l'ordre de `CodeIndicateur`) ; tickets en cause triés par `rang_cle` selon FR-17 ; seules les lignes de date ≤ Date d'arrêté comptent ; messages d'erreur en français (`UsineErreur`).

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` ; recalculer depuis `kpi.parquet` ou dupliquer un calcul hors du domaine ; un NaN, un `None` ou un zéro par défaut à la place d'un `non_evaluable` ; écrire hors lane au-delà de `src/usine/chaine/etapes.py`, `src/usine/composition.py` et des tests de Chaîne qui construisent `EtapeMeteo` ou figent une couleur ; implémenter l'Évolution J-1/J-5 (Story 3.7).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| IND-2 | bloquantes ouvertes entrées il y a 3 et 7 Jours ouvrés | `7/1`, orange (`> 5`), tickets : la (les) plus ancienne(s) | — |
| IND-2 sans bloquante | aucune bloquante ouverte | `non_evaluable`, motif « aucune Anomalie bloquante ouverte » | — |
| IND-3 | 5 majeures ouvertes | `5/1`, jaune | — |
| IND-4 | Phase en cours recette ; 20 exécutés dont 4 KO, + KO en tnr | `4/20`, rouge ; tickets = KO de recette | — |
| IND-4 garde-fou | 19 exécutés (OK+KO) en Phase en cours | `non_evaluable`, motif nommant 19 et 20 | — |
| IND-4 hors calendrier | Date d'arrêté dans aucune Phase de la Vague | `non_evaluable`, motif « aucune Phase en cours » | — |
| Phases chevauchantes | semaine dans deux Phases | la Phase au début le plus tardif (puis rang le plus élevé) | — |
| IND-5 / IND-6 | Certifications de l'Entité : 1 refusée V1, 2 réservées V1, 1 réservée V2 (Vague ≠ celle de l'Entité) | IND-5 `1/1` rouge ; IND-6 `2/1` orange | — |
| IND-7 infini | 6 Entrées bloquantes/majeures, 0 Sortie sur la Fenêtre | `6/0`, orange | — |
| IND-7 garde-fou | 4 Entrées | `non_evaluable`, motif nommant 4 et 5 | — |
| IND-7 mineures | Entrées de mineures | non comptées | — |
| IND-8 | IND-4 = 6/20 à D, 1/20 à J-5 | `1/4` (hausse +25 points), orange | — |
| IND-8 non évaluable | IND-4 non évaluable à D ou à J-5, ou J-5 antérieur à l'ancrage | `non_evaluable`, motif nommant la date en cause | — |
| Météo | IND-4 rouge et IND-1 orange | rouge, seule la règle IND-4 restituée | — |
| Entité inconnue | Entité absente de `programme.entites` | — | `UsineErreur` nommant l'Entité |
| Date non calculée | jour ouvré de J-5..D (≥ ancrage) absent alors que la table a des dates antérieures | — | `UsineErreur` nommant la date |

</intent-contract>

## Code Map

- `src/usine/domaine/meteo.py` -- cœur. `_ind1` (l. 122) modèle d'un comptage ; `_indicateurs_actifs` (l. 104) refuse IND-2..8 : à retirer ; `_mesures` (l. 141) contrôle les dates et ne voit que D ; `_Mesure` sans statut ni motif : à étendre ; `indicateurs` (l. 186) et `meteo` (l. 213) ; `_franchit` (l. 170) gère l'infini.
- `src/usine/domaine/kpi.py:160` -- `_anomalies` : formules Entrée (`date_derniere_entree == date`), Sortie et âge (`len(jours_ouvres(entree, d)) - 1`) à reproduire à l'identique (ne pas l'appeler sur une table tronquée : il lève sur une veille absente).
- `src/usine/contrats/config.py:59-138` -- `ConfigProgramme.entites[].vague`, `vagues[].phases[]` (`semaine_debut`/`semaine_fin`, chevauchements possibles) ; `GardeFous` (l. 160). Lecture seule.
- `src/usine/contrats/calendrier.py` -- `semaine_programme(d, ancrage)` (lève si `d < ancrage`), `jour_ouvre_precedent(d, n)`, `fenetre_glissante(d)`, `jours_ouvres`. Lecture seule.
- `src/usine/contrats/calcul.py:69` -- `SCHEMA_INDICATEUR`, `StatutIndicateur` ; `src/usine/contrats/meteo.py:84` -- `RegleDeclenchante` (numérateur négatif permis, `0/0` refusé). Lecture seule.
- `src/usine/contrats/tickets.py:205` -- `SCHEMA_TICKET_ETAT` (`vague`, `phase`, `statut_test`, `statut_certification`, `date_derniere_entree`).
- `src/usine/generateur/journal.py:170` -- `_phase_du_calendrier` : règle de chevauchement à suivre (début le plus tardif puis rang).
- `src/usine/chaine/etapes.py:56` -- `EtapeMeteo` : lit `tickets_etats(jour)` jour par jour (une date) ; doit recevoir le Programme et passer J-5..D (hors lane, L5).
- `src/usine/composition.py:225-232` -- `premier_jour = entete.ancrage_semaines` ; construit `EtapeMeteo` (hors lane).
- `config/grille_meteo.yaml` -- IND-2..8 `active: false`, `version: 2`.
- `tests/unit/domaine/test_meteo.py` -- fixture `grille` (Grille livrée) et `_grille()` ; tests IND-1 à adapter (Grille IND-1 seule), `test_indicateur_non_implemente*` à supprimer ; `tests/unit/domaine/constructeur.py` `Flux` ; `tests/unit/domaine/test_kpi.py:71,86` helpers `_cas`, `_certification`.
- `tests/unit/generateur/programme_reduit.yaml` -- Programme réduit (ENT-A, ENT-B, V1 ; recette semaines 3-6).
- `tests/unit/chaine/test_execution.py:220` -- construit `EtapeMeteo` (hors lane).

## Tasks & Acceptance

**Execution:**
- `src/usine/domaine/meteo.py` -- `indicateurs(..., *, programme, ancrage)` et `meteo(..., *, programme, ancrage)` ; mesure par indicateur avec statut/motif ; IND-2..IND-8 selon la matrice ; Phase en cours (`phase_en_cours(programme, entite, d, ancrage) -> Phase | None`, publique) ; contrôle des dates J-5..D ; refus d'une Entité hors Programme ; suppression du refus des indicateurs non implémentés -- FR-11, FR-16, AD-10.
- `config/grille_meteo.yaml` -- IND-2 à IND-8 `active: true`, commentaires mis à jour, `version: 3` -- FR-15.
- `src/usine/chaine/etapes.py` -- `EtapeMeteo(grille, version_grille, entites, premier_jour, programme)` ; passe à chaque jour la concaténation des tables de J-5 à D (hors lane).
- `src/usine/composition.py` -- passe `programme` à `EtapeMeteo` (hors lane).
- `tests/unit/domaine/test_meteo.py` -- un test par ligne de la matrice ; tests IND-1 existants sur une Grille IND-1 seule ; Grille livrée : 8 actifs, `version: 3` ; Journal généré avec la Grille livrée : Météo valide, couleur = pire couleur des indicateurs évalués, déterminisme.
- `tests/unit/chaine/test_execution.py` et tout test de Chaîne cassé par l'activation -- adapter au plus juste (hors lane).

**Acceptance Criteria:**
- Given les états des tickets d'une Entité à une Date d'arrêté, when le domaine calcule IND-1 à IND-8, then IND-4 porte sur la Phase en cours, IND-5 et IND-6 sur la Vague en cours, IND-8 compare IND-4 à J-5.
- Given moins de 20 Cas de test exécutés dans la Phase en cours, when on calcule IND-4, then `statut = non_evaluable` avec un `motif`, valeur `0/0`, et IND-8 est non évaluable si IND-4 l'est à l'une des deux dates.
- Given 6 Entrées et 0 Sortie sur la Fenêtre glissante, when on calcule IND-7, then le ratio est infini (`6/0`) et déclenche orange ; avec 4 Entrées, IND-7 est non évaluable.
- Given la Grille livrée (8 indicateurs actifs) et le Journal du mini-jeu, when on lance `usine rapport`, then un Passage est publié avec `indicateurs.parquet` portant 8 lignes par Entité et par jour.
- Given les cinq contrôles du dépôt, then ruff, ruff format, mypy, lint-imports et pytest passent.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 21 findings — high 0, medium 3, low 14, false 4, maybe-false 0
- findings:
  - `[false]` `[reject]` (blind) Ancrage de la Chaîne (`premier_jour`) différent de `ancrage_semaines` du Journal — faux : `composition.py:225` pose `premier_jour = source.entete.ancrage_semaines`, c'est la même date.
  - `[false]` `[reject]` (blind) Chaîne en échec sur un premier jour non lundi — faux : `EnteteJournal.ancrage_semaines` est validé lundi (`contrats/evenements.py:115`).
  - `[low]` `[patch]` (blind) Profondeur du `deque` d'`EtapeMeteo` juste par coïncidence (J-5 = Fenêtre + veille) — `maxlen=max(DECALAGE_IND8, TAILLE_FENETRE_GLISSANTE) + 1`.
  - `[low]` `[reject]` (blind) Sorties d'IND-7 sous-comptées le jour de l'ancrage (veille absente) — même convention que les KPI de la 3.2 (« à sa première date, la veille est vide ») ; ne touche que la première semaine de l'historique ; diverger des KPI casserait la réconciliation.
  - `[low]` `[reject]` (blind) IND-8 compare des taux de deux Phases différentes à un changement de Phase — définition littérale du PRD (« IND-4 à la Date d'arrêté moins IND-4 cinq Jours ouvrés plus tôt »), chaque IND-4 sur sa Phase en cours ; changer la règle est une décision produit (risque résiduel noté).
  - `[low]` `[reject]` (blind) IND-4 ne filtre pas la Vague — une Entité appartient à une seule Vague ; un Cas de test d'une autre Vague pour la même Entité n'est pas produit par les sources ; garde sans cas réel.
  - `[low]` `[reject]` (blind) Calcul répété (`indicateurs` puis `meteo`, IND-4 à J-5 recalculé) — six dates par jour, filtres Polars rapides ; suite complète et mini-jeu sans ralentissement notable ; une mise en cache ajoute de la structure.
  - `[low]` `[patch]` (blind) Motif d'IND-4 « garde-fou de 1 » quand le garde-fou configuré vaut 0 — motif « aucun Cas de test exécuté » quand aucun, sinon le minimum configuré.
  - `[low]` `[patch]` (blind) Chemins d'erreur non testés (IND-2 sans date de dernière Entrée, week-end, `StopIteration`) — test ajouté pour IND-2 ; le week-end est couvert (`test_date_d_arrete_non_calculee_refusee[week-end]`) ; `StopIteration` inatteignable (`ConfigProgramme` refuse une Vague inconnue).
  - `[medium]` `[patch]` (blind) Aucun test de Chaîne sur les valeurs d'IND-7/IND-8 — groupé avec la ligne verification-gap ; `test_autoportance_meteo` compare désormais tout `indicateurs.parquet` à un appel direct du domaine (historique complet, Programme, ancrage du Journal).
  - `[low]` `[reject]` (blind) Tickets en cause d'IND-8 = tous les KO de D — conforme à FR-17 (« les Cas de test KO de la Phase en cours ») et aux Design Notes.
  - `[false]` `[reject]` (intent) Contenu « 8 lignes » vérifié sous la surface `usine rapport` — faux comme défaut : `test_cli.py::test_passage_publie_et_rejeu` lance `usine rapport` sur le mini-jeu avec la Grille livrée, et le lancement manuel a publié un Passage à 640 lignes (80 × 8).
  - `[false]` `[reject]` (intent) Aucun lancement autonome de `usine rapport` consigné — faux : lancé dans le scratchpad (voir Auto Run Result).
  - `[low]` `[reject]` (intent) Tests IND-1 sur une Grille IND-1 seule — voulu : isole IND-1 ; la Grille livrée est couverte par `test_meteo_pire_couleur`, le Journal généré et la Chaîne.
  - `[medium]` `[patch]` (intent) Chaîne vérifiée en forme, pas en valeurs — groupé : même correctif que la ligne blind ci-dessus.
  - `[medium]` `[patch]` (verification-gap) Historique J-5..D et ancrage d'`EtapeMeteo` sans vérification de valeurs — même correctif (comparaison colonne à colonne de `indicateurs.parquet` au domaine).
  - `[low]` `[patch]` (verification-gap) Refus d'IND-2 sur bloquante ouverte sans `date_derniere_entree` non testé — `test_ind2_bloquante_ouverte_sans_date_de_derniere_entree`.
  - `[low]` `[reject]` (edge) IND-8 à travers un changement de Phase — même motif que la ligne blind correspondante (définition PRD).
  - `[low]` `[reject]` (edge) Sorties sous-comptées le jour de l'ancrage — même motif que la ligne blind (convention KPI).
  - `[low]` `[reject]` (edge) Bloquante déclassée en mineure et fermée le même jour : Sortie perdue — cas rare ; la gravité du jour est la convention écrite (Design Notes) ; la corriger ajoute une branche.
  - `[low]` `[patch]` (edge) Date d'arrêté antérieure à l'ancrage et absente non refusée — `_verifier_dates` contrôle toujours la Date d'arrêté ; test `test_date_d_arrete_avant_l_ancrage_toujours_controlee`.

## Design Notes

**Valeurs** (D = Date d'arrêté, lignes de l'Entité à D) : IND-1/IND-3 = nombre de bloquantes/majeures ouvertes `n/1`. IND-2 = âge max `n/1` des bloquantes ouvertes ; tickets = celles d'âge max. IND-4 = `KO/(OK+KO)` des Cas de test de l'Entité dont `phase` = Phase en cours ; tickets = KO. IND-5/IND-6 = Certifications de l'Entité, `vague` = Vague de l'Entité (Programme), refusées/réservées. IND-7 = Entrées/Sorties d'Anomalies bloquantes ou majeures (gravité du jour) sur `fenetre_glissante(D)` ; Entrée en d si `date_derniere_entree == d` ; Sortie en d si fermée en d et (ouverte en d-1 ou entrée en d) ; jours hors table ou avant l'ancrage = 0 (comme les KPI) ; tickets = entrés ou sortis. IND-8 = `IND-4(D) − IND-4(J-5)` en `Fraction` réduite ; tickets = KO de D.

**Phase en cours** : `semaine_programme(d, ancrage)` ; Phases de la Vague contenant la semaine ; plusieurs → début le plus tardif puis rang le plus élevé (comme le générateur) ; aucune → `None` (IND-4 non évaluable, pas de repli sur la dernière Phase : le Glossaire dit « contient »).

**Historique** : la table reçue doit couvrir J-5..D ; `EtapeMeteo` concatène les six dernières tables lues. Une date de J-5..D postérieure ou égale à l'ancrage, absente alors que la table a des dates antérieures, est refusée (trou).

**Fichiers hors lane** : `src/usine/chaine/etapes.py` et `src/usine/composition.py` (seul appelant du domaine Météo ; Phase et Vague en cours exigent le Programme, et IND-7/IND-8 l'historique J-5..D) ; `tests/unit/chaine/test_execution.py` (construit `EtapeMeteo`) et les tests de Chaîne qui figeaient la Météo IND-1 seule.

## Verification

**Commands:**
- `uv run pytest -q tests/unit/domaine tests/unit/chaine tests/unit/test_composition.py` -- expected: tous verts
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: succès

**Manual checks (if no CLI):**
- Dans un répertoire du scratchpad : `config/` copié avec `tests/unit/generateur/programme_reduit.yaml` en `programme.yaml`, `usine donnees` puis `usine rapport --date-arrete <Date d'injection>` publient un Passage dont `indicateurs.parquet` porte IND-1 à IND-8.

## Auto Run Result

- **Résumé :** les huit Indicateurs de météo sont calculés dans `domaine/meteo.py`, exacts (`numerateur`/`denominateur` entiers), avec `non_evaluable` + `motif` (`0/0`, vert, sans effet sur la Météo) sous garde-fou ou sans donnée ; Phase en cours (`phase_en_cours`) et Vague en cours tirées du Programme et de l'ancrage ; IND-8 compare IND-4 à J-5 ; tickets en cause selon FR-17. La Grille livrée active IND-1 à IND-8 (`version: 3`) ; `EtapeMeteo` reçoit le Programme et l'historique J-5..D.
- **Fichiers :**
  - `src/usine/domaine/meteo.py` -- calcul d'IND-1 à IND-8, `phase_en_cours`, contrôles d'Entité et de dates, `DECALAGE_IND8`.
  - `config/grille_meteo.yaml` -- IND-2 à IND-8 actifs, commentaires, `version: 3`.
  - `src/usine/chaine/etapes.py` -- `EtapeMeteo` : Programme, historique glissant J-5..D (hors lane).
  - `src/usine/composition.py` -- passe le Programme à `EtapeMeteo` (hors lane).
  - `tests/unit/domaine/test_meteo.py` -- un test par ligne de la matrice et cas limites ; tests IND-1 sur Grille IND-1 seule ; Grille livrée v3 ; Journal généré.
  - `tests/unit/chaine/test_execution.py` -- `EtapeMeteo` avec Programme ; `indicateurs.parquet` publié égal au domaine, colonne à colonne (hors lane).
- **Revue :** 21 findings ; 6 entrées corrigées (patch : 1 medium groupant 3 constats, 5 low) ; 0 différé ; rejets (8 low, 4 false) motivés dans le Review Triage Log.
- **Revue de suivi recommandée :** non (patches : 0 high, 1 medium, 5 low).
- **Vérification :** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports` (13 contrats), `uv run pytest -q` (1369 passés, 1 sauté) : tous verts. Manuel : sur le mini-jeu (Programme réduit, graine 42, génération 2026-10-12), `usine donnees generer` puis `usine rapport --date-arrete 2026-10-09` publient un Passage ; `indicateurs.parquet` : 640 lignes (80 Entité-jours × 8). Audit de matrice : chaque ligne couverte par un test passé.
- **Risques résiduels :** sur le mini-jeu, IND-4, IND-7 et IND-8 restent non évaluables (volumes sous les garde-fous) et IND-2 passe rouge à côté d'IND-1 : les Stories 1.8 et 3.8 devront calibrer des données qui les déclenchent ; IND-8 au changement de Phase compare deux Phases (définition PRD) ; Sorties d'IND-7 sous-comptées le jour de l'ancrage (convention KPI) ; une Date d'arrêté week-end est désormais toujours refusée.
- **Fichiers hors lane :** `src/usine/chaine/etapes.py`, `src/usine/composition.py`, `tests/unit/chaine/test_execution.py` (voir Design Notes).
