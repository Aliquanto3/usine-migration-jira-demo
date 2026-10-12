---
date: 2026-10-12
workflow: bmad-correct-course
mode: batch
statut: approuvé le 2026-10-12 ; artefacts de planification appliqués ; code en PR contrats 1.2
declencheur: File humaine de `implementation-artifacts/journal-run-autonome.md` (Stories 4.5 et 5.5 arrêtées, catégorie contrats)
---

# Proposition de changement de sprint : contrats 1.2 et reprise jusqu'à la porte M3

## 1. Résumé du problème

Le run autonome du 12/10/2026 a livré 38 stories mais s'est arrêté sur deux stories bloquées par le gel des contrats (AD-2). Ces deux arrêts bloquent à leur tour la 5.6 et la porte M3 (5.7), donc l'Epic 6.

**Story 4.5 (recette SM-6), branche `bloque/4-5`.** Sur le Journal de la Story 1.8, SM-6 échoue :
- A est rouge par IND-1 et IND-2, donc « règle non projetable » au lieu d'une sortie dans l'horizon ;
- B est rouge par IND-1, IND-2, IND-3 et IND-5 (Certification refusée), donc « règle non projetable » au lieu de « pas de sortie projetée » ;
- C n'est signalée qu'à 0,2018 contre 0,2 le vendredi, et pas du tout si D tombe un lundi ou un mardi.

La correction respecte SM-C3 : elle passe par le générateur, sans toucher à la Grille ni à la Baseline. Les bloquantes de A et B deviennent un flux scripté (`bloquantes_par_semaine`, `duree_bloquantes`). La Certification de B passe à « réservée ». C passe à 50 Cas de test par semaine, avec un taux de KO visé de 0,18. Ce modèle ne s'exprime pas dans `ConfigScenarioSortie` et `ConfigScenarioEnlisement` (contrats 1.1, `extra="forbid"`, gelés). De plus, `test_configuration_livree_egale_aux_defauts` exige que `config/programme.yaml` égale `SCENARIOS_PAR_DEFAUT`.

**Story 5.5 (Rejeu), aucune branche.** Elle s'est arrêtée à la vérification préalable. L'AC Rejeu et AD-7 (« Rendus ») exigent de déclarer, sous `EXCLUSIONS_REJEU["rapport_xlsx"]` et `["rapport_pptx"]`, les cellules de traçabilité qui affichent `horodatage_extraction` et `version_donnees`. Ces deux valeurs varient d'un Passage à l'autre en source composite. Ajouter ces clés modifie `contrats/passage.py`, qui est gelé.

**Preuves** : la section « Auto Run Result » de `spec-4-5-…md` (branche `bloque/4-5`, commit `db5c98c`), la File humaine et le Bilan du journal, `src/usine/rendu/excel.py:121-126` et `src/usine/rendu/commun.py:342-358`.

## 2. Analyse d'impact

| Domaine | Impact |
| --- | --- |
| Epics | Epic 4 : la 4.5 perd sa partie générateur (reprise par la PR de contrats) et garde la recette. Epic 5 : AC de la 5.5 précisé, prérequis de la 5.6 complétés (5.5, réinjection de `DEMO`, Mode repli). Epic 6 inchangé, toujours derrière la porte M3. Aucun epic ajouté, retiré ou réordonné |
| PRD | Aucun. FR-3 n'exige ni le refus de la Certification de B ni le volume de Cas de test de C. B rouge par ses seules bloquantes colle même mieux au texte (« les Entrées d'Anomalies dépassent les Sorties ») |
| Architecture | Spine : front matter (`amendments`), AD-7 (liste des exclusions complétée par les rendus) |
| UX | Aucun |
| Code | `contrats/config.py`, `contrats/passage.py`, `contrats/versions.py` ; `generateur/scenarios.py` et `generateur/journal.py` repris de `bloque/4-5` ; `config/programme.yaml` ; tests associés |
| Données réelles | **Le Journal change** (graine 42 identique, autres tirages). Le projet `DEMO` (3 384 tickets injectés depuis l'ancien Journal) et `donnees/injection/manifeste_injection.json` ne lui correspondent plus. `SourceJournal` refusera la correspondance (clé manquante ou inutilisée) et la source composite échouera tant que `DEMO` n'aura pas été réinjecté. La copie du Mode repli (`demo/repli/passage/`, AD-24) montre aussi les anciennes trajectoires |

Checklist : sections 1 à 4 [x]. Section 5 (PRD/MVP) [N/A], le MVP est inchangé. Section 6 [x], avec le transfert de la § 5. Point [!] : réinjection de `DEMO`, une action d'Anaël sur un service externe (§ 5).

## 3. Approche retenue

**Ajustement direct** par une PR de contrats sur `main`, sans retour arrière ni revue du MVP.

- **Effort** : moyen. La PR reprend un code déjà écrit et revu sur `bloque/4-5`. Ensuite viennent deux stories courtes en parallèle (4.5, 5.5), puis la 5.6 et la porte.
- **Risque** : moyen, et concentré sur deux points.
  1. Le calage au jour près de la 1.8 doit rester vert avec le flux scripté. La lane l'avait vérifié, rapide et `lent`, avant l'arrêt.
  2. Il faut réinjecter `DEMO` (environ 2 h d'API à 5 req/s).
- **Calendrier** : la porte M3 recule du temps de la PR, puis de la réinjection, qui se fait en parallèle de 4.5 et 5.5.

## 4. Changements détaillés

### 4.1 Décisions techniques tranchées dans ce workflow

| # | Question | Choix et raison |
| --- | --- | --- |
| C1 | Contenu de la PR de contrats | Elle embarque **la partie générateur de la 4.5** : `scenarios.py`, `journal.py`, leurs tests et les fixtures passées d'ENT-A à ENT-B. Retirer `part_bloquantes_vague` et `part_bloquantes` des contrats casse `scenarios_de_config` sur `main` (`TypeError`) et le test « config = défauts ». Les deux doivent donc arriver dans le même commit pour que `main` reste vert. La 4.5 ne garde que la recette |
| C2 | Version | `CONTRATS_VERSION` passe à **1.2.0**, mineure, posée au dernier commit. Aucun fichier de Passage ne change de forme ; les clés retirées ne concernent que `config/programme.yaml`, versionné avec le code. Une version 2.0.0 ferait refuser par `Consultation` la copie du Mode repli et tous les Passages existants, sans aucun gain |
| C3 | `ConfigScenarioSortie` | Ajout de `bloquantes_par_semaine: tuple[NombreScenario, ...]` (au moins 1) et de `duree_bloquantes: int` (strict, 4 ≤ d ≤ 10 ; la borne haute garantit IND-2 ≤ 10 JO, constat du triage). `part_bloquantes_vague` est retiré. `bloquantes_bascule`, `poids_vague` et `poids_decrue` sont conservés |
| C4 | `ConfigScenarioEnlisement` | Mêmes ajouts. `part_bloquantes` est retiré, ainsi que le validateur `part_bloquantes + part_majeures ≤ 1`, devenu sans objet : `part_majeures` reste borné à [0, 1] par `TauxScenario` |
| C5 | `ConfigScenarioMenace` | Forme inchangée ; seules les valeurs de `config/programme.yaml` bougent |
| C6 | Valeurs livrées (`config/programme.yaml` = `SCENARIOS_PAR_DEFAUT`) | A : `bloquantes_bascule` 4, `bloquantes_par_semaine` [9, 2, 4], `duree_bloquantes` 7. B : `bloquantes_par_semaine` [3, 3, 4, 4, 5, 5, 6], `duree_bloquantes` 8, `part_majeures` 0,03, `statut_certification` `reservee`. C : `cas_de_test_par_semaine` 50, `taux_ko_hausse` [0.045, 0.065, 0.07, 0.14, 0.18] |
| C7 | Forme des repères de rendu | `rapport_xlsx` : adresse de cellule (`Traçabilité!B5`, `Traçabilité!B8`), qui est le repère natif d'Excel. `rapport_pptx` : libellé de ligne (`Annexe méthode!Horodatage d'extraction`, `Annexe méthode!Version des données`), stable quel que soit le nombre d'Indicateurs. C'est le format `<onglet ou slide>!<repère>` d'AD-7 ; seule la nature du repère diffère selon le rendu |
| C8 | Garde des repères | `contrats` ne peut pas importer `rendu`. `test_exclusions_rejeu_designent_des_champs` saute donc les clés `rapport_*`, et un test sous `tests/unit/rendu/` vérifie que `B5`, `B8` et les deux libellés désignent bien « Horodatage d'extraction » et « Version des données » dans `LIBELLES_TRACABILITE` et dans le classeur produit |
| C9 | Données réelles après le recalage | `DEMO` est vidé puis réinjecté depuis le nouveau Journal (graine 42, génération le 2026-10-12, Date d'injection 2026-10-09). La clé `DEMO`, les liens et les AC restent ainsi tels quels. La 1.7 traite déjà le projet vide comme un site neuf. Le projet passe par la corbeille Jira, restaurable 60 jours : l'opération est réversible |
| C10 | Mode repli | La copie `demo/repli/passage/` est régénérée en 5.6, sur le nouveau Journal, pour que le repli montre les mêmes trajectoires que la démo en direct (AD-24) |

### 4.2 Contrats et code (PR `contrats/v1-2` sur `main`)

| Fichier | Avant → après |
| --- | --- |
| `src/usine/contrats/config.py` | Décisions C3 et C4 ; docstrings des miroirs mises à jour |
| `src/usine/contrats/passage.py` | `EXCLUSIONS_REJEU` reçoit `"rapport_xlsx": frozenset({"Traçabilité!B5", "Traçabilité!B8"})` et `"rapport_pptx": frozenset({"Annexe méthode!Horodatage d'extraction", "Annexe méthode!Version des données"})`. La docstring ajoute : « Les rendus sont repérés `<onglet ou slide>!<repère>` » |
| `src/usine/contrats/versions.py` | `1.1.0` → `1.2.0` (dernier commit) |
| `src/usine/generateur/scenarios.py`, `journal.py` | Repris de `bloque/4-5` (`part_du_jour`, `bloquantes()`, `_bloquantes_scriptees`, `_nouvelle_anomalie`). `scenarios_de_config` est aligné sur C3 et C4. Les patchs low du triage qui touchent ces fichiers sont appliqués : `JOURS_OUVRES_SEMAINE` au lieu de 5, docstrings de `ScenarioEnlisement` et `DELAIS_LENTS`. La troncature sans signal des bloquantes scriptées (constat medium `bad_spec`) devient une erreur ou un avertissement explicite quand les créations de la semaine ne suffisent pas |
| `config/programme.yaml` | Décision C6, commentaires mis à jour |
| Tests | `test_scenarios.py`, `test_scenarios_config.py`, `test_calage.py` (bloquante scriptée comptée en Jours ouvrés), `tests/unit/contrats/test_config.py`, `test_passage.py` (C8), test de rendu (C8), fixtures ENT-A → ENT-B (`tests/contrat/consultation/fabriques.py`, `tests/unit/consultation/test_passage.py`), regex et attendus de version |

### 4.3 Spine (`architecture/.../ARCHITECTURE-SPINE.md`)

| Section | Avant → après |
| --- | --- |
| Front matter | Nouvelle entrée `amendments` : « 2026-10-12 : sprint-change-proposal-2026-10-12-contrats-1-2.md (contrats 1.2 : Scénarios à flux scripté, exclusions des rendus) » |
| AD-7, Liste | Ajout de `rapport_xlsx` : `Traçabilité!B5`, `Traçabilité!B8` (adresse de cellule) ; et de `rapport_pptx` : `Annexe méthode!Horodatage d'extraction`, `Annexe méthode!Version des données` (libellé de ligne) |
| AD-7, Rendus | « … par une PR courte sur `main` pendant L5 » → « … déclarés en contrats 1.2. Le repère est une adresse de cellule pour l'Excel, un libellé de ligne pour le PowerPoint. Ajouter une entrée est une modification mineure ; changer la forme serait majeure. » |

### 4.4 Epics (`epics.md`)

**Story 4.5, sous les Exigences** : ajout de la ligne suivante.

> **Prérequis :** contrats 1.2 (flux scripté des Scénarios A et B, Certification de B réservée, C à 50 Cas de test : partie générateur livrée par la PR de contrats). La story ne garde que la recette.

**Story 4.5, AC 1**, de :
> **When** le test calcule les Prévisions au dernier Jour ouvré de l'historique

à :
> **When** le test calcule les Prévisions au dernier Jour ouvré de l'historique par le chemin de la Chaîne (`prevision_du_passage`, étape `prevision`)

**Story 4.5, nouvel AC** :
> **Given** une Entité non rouge qui porte un Risque d'entrée en rouge
> **When** l'étape `prevision` publie `previsions.json`
> **Then** la valeur projetée du Risque (`valeur_projetee_*`) est remplie depuis `risque.py`

**Story 5.5, AC Rejeu, second « And »**, de :
> **And** les cellules de l'onglet Traçabilité qui affichent un champ exclu sont déclarées sous `rapport_xlsx` et `rapport_pptx` par une PR courte sur `main`

à :
> **And** les cellules de Traçabilité qui affichent un champ exclu, déclarées en contrats 1.2 sous `rapport_xlsx` (`Traçabilité!B5`, `!B8`) et `rapport_pptx` (`Annexe méthode!<libellé>`), sont ignorées, et elles seules

**Story 5.5, nouvel AC** (constat 15 de la rétro Epic 0, reporté par la 5.1) :
> **Given** une console Windows
> **When** `usine rapport` journalise sa progression
> **Then** les messages s'affichent en UTF-8 sans erreur d'encodage

**Story 5.6, Prérequis externes**, de :
> Stories 1.8, 2.6, 4.5

à :
> Stories 1.8, 2.6, 4.5, 5.5 ; réinjection de `DEMO` depuis le Journal recalé (contrats 1.2)

**Story 5.6, nouvel AC** :
> **Given** le Passage recalé de la volumétrie cible
> **When** l'auteur régénère `demo/repli/passage/`
> **Then** le Mode repli montre A et B rouges et C orange, comme en direct (AD-24)

### 4.5 Suivi (`sprint-status.yaml`, `journal-run-autonome.md`)

- `4-5` : commentaire « prérequis : contrats 1.2 ; reprise depuis `bloque/4-5`, recette seule ».
- `5-5` : commentaire « prérequis : contrats 1.2 ».
- `5-6` : prérequis complétés (4.5, 5.5, réinjection de `DEMO`).
- Journal, File humaine : les deux entrées 4.5 et 5.5 sont marquées « tranché par sprint-change-proposal-2026-10-12-contrats-1-2.md ».

## 5. Transfert pour la mise en œuvre

**Portée : modérée.** La planification est amendée par ce workflow. Le code part au développeur dans une PR de contrats, puis le backlog est réordonné. Il n'y a pas de replanification de fond.

### Ordre de reprise

| # | Travail | Qui | Dépend de | Parallèle |
| --- | --- | --- | --- | --- |
| 1 | PR de contrats 1.2 (§ 4.2), branche `contrats/v1-2` depuis `main`. Cinq contrôles, `pytest -m lent tests/unit/generateur` vert, avance rapide de `main` | Développeur (`bmad-build`) | — | — |
| 2a | Reprise de la 4.5 : lane L4 rebasée sur `main`. Abandon de `serie.py` et `previsions.py` de la lane au profit de ceux de `main`, recette par `prevision_du_passage`, patchs du triage (SM-6 hors vendredi en rapide, changement d'Entité dans `series_stock`, IND-4 exigé les lundis et mardis, `regles_non_projetables == ()`), `valeur_projetee_*` | Développeur | 1 | avec 2b et 2c |
| 2b | Story 5.5 : `usine rapport` sans option, Palier 1 sauté, Rejeu (Parquet, JSON, cellules, slides) hors exclusions, échec sans rapport, UTF-8 de la console | Développeur | 1 | avec 2a et 2c |
| 2c | Réinjection de `DEMO` : projet `DEMO` à la corbeille Jira (restaurable 60 jours), `donnees/injection/` archivé localement, `usine donnees generer` (graine 42, génération le 2026-10-12), puis `usine donnees injecter` (environ 2 h). Projet `KAN` non touché | **Anaël** (action destructive sur un service externe) | 1 | avec 2a et 2b |
| 3 | Story 5.6 : Rapport sur le Journal complet (A et B rouges, C orange, Prévisions attendues), source composite sur `DEMO` (liens), régénération du Mode repli | Développeur | 2a, 2b, 2c | — |
| 4 | Story 5.7, porte M3 : mesure NFR-2 consignée, réconciliation à 100 %, Rejeu idempotent, journal de fin de jalon. La CI verte exige un push : à faire par **Anaël** | Développeur, puis Anaël | 3 | — |

En mode économique (deux agents au plus), 2a et 2b tournent en parallèle pendant qu'Anaël réinjecte.

### Critères de réussite

1. Sur `main`, `CONTRATS_VERSION` vaut `1.2.0` et `config/programme.yaml` égale `SCENARIOS_PAR_DEFAUT` (le test existant reste vert).
2. `test_calage` passe, en rapide et en `lent`, avec le flux scripté.
3. `EXCLUSIONS_REJEU` porte `rapport_xlsx` et `rapport_pptx`, et le test de rendu C8 les relie à `LIBELLES_TRACABILITE`.
4. La recette 4.5 vérifie SM-6 par le chemin de la Chaîne, pour la graine 42 en rapide, et pour les graines 1, 7 et 123 et les semaines partielles en `lent`.
5. Le Rejeu de la 5.5 compare deux Passages Palier 1 de même date, et seuls les champs exclus diffèrent.
6. `usine rapport` sur `DEMO` réinjecté publie un Passage composite ; A et B y sont rouges, C orange.
7. La porte M3 est passée et consignée ; l'Epic 6 peut démarrer.

### Hors périmètre, à arbitrer par Anaël avant le journal de fin de jalon M3

- **SM-10** : la Baseline perd contre la référence naïve sur les projets tenus à l'écart (Brier 0,0476 contre 0,0452 ; `evaluation/zenodo/RAPPORT.md`).
- **AD-16** : `version_donnees` inclut le manifeste d'injection (2.6), un écart à la lettre du Glossaire.

Ni l'un ni l'autre ne bloque les AC de la 5.7, mais le journal de jalon devra les mentionner.
