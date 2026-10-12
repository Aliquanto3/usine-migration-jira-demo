---
date: 2026-10-12
workflow: bmad-correct-course
mode: batch
statut: appliqué (artefacts de planification) ; code en Story 0.9
declencheur: rétrospective de l'Epic 0 (actions 5) et décisions D1 à D10 de la Story 0.9
---

# Proposition de changement de sprint : amendement du spine avant le gel `contrats-v1`

## 1. Résumé du problème

La rétrospective de l'Epic 0 (`implementation-artifacts/epic-0-retro-2026-10-12.md`) et la préparation de la Story 0.9 (`implementation-artifacts/preparation-0-9-gel-contrats.md`) ont montré que le spine ne décrit plus exactement ce que le code et la CI appliquent. Les lanes liront le spine dès l'ouverture des worktrees : il doit être juste **avant** le gel.

Écarts constatés :
- **AD-7** : `EXCLUSIONS_REJEU` est une liste plate qui ignore les traces et les coûts. En Palier 2, ces champs varient d'un Rejeu à l'autre. À plat, exclure `horodatage` le masquerait dans tous les fichiers (constat 16, D7).
- **AD-15, arborescence, carte des lanes** : `adaptateurs/pseudonymisation/` (expressions régulières et HMAC, E0-7) n'a pas de propriétaire. Le contrôle CI des lanes le traiterait comme hors lane (constat 18).
- **AD-21** : le spine ignore les tests plats, `adaptateurs/cli` en L2 et la liste blanche des externes, alors que la CI les applique (`deferred-work.md`, élément 1 ; constat 20).
- **Décisions de gel D1 à D10** (validées le 2026-10-12) : port `CacheLLM` (D1), formes déplacées dans `contrats` (D2), `dataclass` gelées (D5). S'y ajoutent la convention `SCHEMA_` et la signature `semaine_programme(d, ancrage)`, absentes du spine. D3, D4, D8 et D9 y sont aussi reportées pour que le spine reste juste.

## 2. Analyse d'impact

| Domaine | Impact |
| --- | --- |
| Epics | Epic 0 : périmètre « Écrit dans » de la Story 0.9 élargi et nouveaux critères d'acceptation. Epics 2 et 6 : chemins de lane. Story 5.5 : critère du Rejeu. Story 6.2 : deux moteurs. Aucun epic ajouté, retiré ou réordonné |
| PRD | Aucun. Les FR et NFR sont inchangés ; seules leurs modalités techniques bougent |
| Architecture | Spine amendé : tableau des couches, AD-2, AD-7, AD-8, AD-9, AD-11, AD-12, AD-15, AD-17, AD-20, AD-21, Conventions, Contrats v1, arborescence, cartes |
| UX | Aucun |
| Code (Story 0.9) | `contrats/passage.py` (exclusions, `DonneesPassage`), `contrats/llm.py` (`EnveloppeCache`, `ReponseExplication`, grammaire des jetons), `ports/cache_llm.py`, `tests/contrat/cache_llm/`, `.github/scripts/controle_lanes.py`, consommateurs migrés |

Checklist : sections 1 à 4 [x] ; section 5 (PRD/MVP) [N/A], le MVP est inchangé ; section 6 [x], avec le transfert de la section 5 ci-dessous.

## 3. Approche retenue

**Ajustement direct**, sans retour arrière ni revue du MVP. Le gel n'a pas eu lieu, donc chaque correction de forme reste gratuite. Après le gel, elle coûterait une version majeure et un rebase des huit lanes.

- **Effort** : faible pour la planification (fait), moyen pour le code de la 0.9.
- **Risque** : faible. Le seul risque est d'oublier un consommateur ; `pytest`, `mypy` et `lint-imports` le détectent.
- **Calendrier** : aucun décalage. Le travail s'inscrit dans la Story 0.9, déjà prévue.

## 4. Changements détaillés

### 4.1 Décisions techniques tranchées dans ce workflow

En plus de D1 à D10, déjà validées :

| # | Question | Choix et raison |
| --- | --- | --- |
| T1 | Forme des exclusions du Rejeu | `Mapping[str, frozenset[str]]`, du nom logique de `FICHIERS_PASSAGE` vers des chemins de champ (`etapes[].horodatage_debut`). Le nom logique est stable, alors que le chemin contient la date. Les entrées se comparent comme des clés de dictionnaire |
| T2 | Contenu de la liste | `manifeste` : les cinq champs d'origine, plus les horodatages d'étape, `classification_initiale` et `cout_llm_eur`. Enveloppes JSON : `passage_id`. `trace_llm` : `horodatage`, `passage_id`, `version_donnees`, `depuis_cache`, `jetons_*`, `cout_estime_eur`. `trace_previsions` : `horodatage`, `passage_id`, `version_donnees`. Parquet : rien, aucune colonne variable (vérifié dans `contrats/calcul.py`, `tickets.py`, `prevision.py`) |
| T3 | Cellules de l'Excel et du PowerPoint qui affichent un champ exclu | Clés `rapport_xlsx` et `rapport_pptx` ajoutées par L5 dans une PR courte. Un ajout d'entrées est mineur ; seule la forme est gelée maintenant |
| T4 | Sort de `adaptateurs/pseudonymisation/` (question ouverte de la rétrospective) | Conservé à côté de Presidio, et les deux restent en L6. Il porte la dérivation des jetons et l'accès à la table, que `presidio` réutilise. Il reste le moteur de repli sans spaCy. Le moteur se choisit par une clé de `config/pseudonymisation.yaml` |
| T5 | Grammaire des jetons, dupliquée entre l'adaptateur et la passerelle (constat 8) | Une constante dans `contrats.llm`, ajoutée en 0.9. `ia` ne peut pas importer `adaptateurs` : sans cela, la lane L6 devrait de toute façon passer par une PR sur `main` |
| T6 | `ReponseClassification` et `ReponseNarration` | Pas inventées maintenant. Elles s'ajoutent par une PR courte au début de L6 (ajout mineur). La règle « un `Reponse<Tache>` par tâche dans `contrats.llm` » est gelée |
| T7 | Signature du port `CacheLLM` | Reprise telle quelle (`lire`, `ecrire` sur `str`). La valeur est une `EnveloppeCache` sérialisée. Une suite `tests/contrat/cache_llm/` couvre SQLite et la doublure |
| T8 | Propriété de `main` | S'y ajoutent `tests/depot/`, `.env.example` et les tests miroirs des chemins de `main` |
| T9 | Fichiers écrits hors périmètre pendant E0 (constat 19) | Consignés dans AD-21 comme écarts acceptés, rattachés à la lane de la carte |

### 4.2 Spine (`architecture/.../ARCHITECTURE-SPINE.md`)

| Section | Avant → après |
| --- | --- |
| Front matter | `updated` passe au 2026-10-12, avec une entrée `amendments` |
| Tableau des couches | Ajout de la colonne « Externes permis en plus du socle » et d'un paragraphe sur la liste blanche, recopiés de `pyproject.toml` et `tests/depot/test_import_linter.py`. `ia` et `rendu` sont séparés (rendu : openpyxl, python-pptx) |
| AD-2 | « Deux familles » devient « Trois familles » : Pydantic gelé avec `Mapping` figés (D4) ; tables `SCHEMA_<NOM>` avec `non_nulles` (D3) ; `@dataclass(frozen=True)` pour les objets en mémoire (D5). La source unique couvre aussi `EnveloppeCache`, `Reponse<Tache>` et `DonneesPassage` (D2). Formes locales consignées : `TablePseudonymes`, `LectureMeteo` (D1) |
| AD-7 | Rejeu : exclusions qualifiées par fichier (forme, liste, raison, rendus). `dernier_passage(sans_classification_initiale=True)` (D9) |
| AD-8 | La mesure de FR-44 lit `dernier_passage(sans_classification_initiale=True)` |
| AD-9 | Les dérivations de lecture de `Consultation` ne sont pas un calcul |
| AD-11 | Filtre `palier` sur `anomalies()` (D9) ; dérivations de lecture acceptées (D8) ; vue `LectureMeteo` de l'UI (D1) |
| AD-12 | Port `CacheLLM` et `EnveloppeCache` (D1, D2) ; schémas `Reponse<Tache>` (D2, T6) |
| AD-15 | Deux moteurs en L6, dérivation des jetons partagée, choix du moteur en configuration (T4) ; grammaire dans `contrats.llm` (T5) ; `TablePseudonymes` local (D1) |
| AD-17 | `semaine_programme(d, ancrage)`, ancrage pris dans `EnteteJournal.ancrage_semaines` ; analyse des dates `AAAA-MM-JJ` (D8) |
| AD-20 | Suites `Pseudonymiseur` (deux moteurs, jetons préfixés) et `CacheLLM` |
| AD-21 | Tests miroirs (plats compris), exclusions, tolérés, propriété de `main` (T8), `adaptateurs/cli.py` en L2, écarts acceptés d'E0 (T9), `controle_lanes.py` recopie le spine |
| Conventions | Nouvelles lignes « Schémas de tables » (`SCHEMA_<NOM>`) et « Objets en mémoire » ; ligne Tests (test plat, `tests/depot/`) |
| Contrats v1 | Noms `SCHEMA_*` ; ajouts `rang_cle`, `LIBELLES_COULEURS`, `EvolutionMeteo`, `EnveloppeCache`, `Reponse<Tache>`, grammaire des jetons, `EXCLUSIONS_REJEU`, chemins, `DonneesPassage` ; ligne dédiée aux `dataclass` ; port `CacheLLM` ; formes locales consignées |
| Arborescence | `ports/` mentionne `CacheLLM` ; `adaptateurs/` liste `cli.py` et `pseudonymisation` avec leur lane ; ajout de `tests/depot/` |
| Carte capacités → architecture | Couche LLM : ajout de `adaptateurs/{pseudonymisation,stockage_sqlite}` |
| Epic E0, E0-9 | Application de D1 à D10 et passage à 1.0.0 |
| Carte des lanes | L2 reçoit `cli`, L6 reçoit `pseudonymisation` ; l'en-tête renvoie aux tests miroirs d'AD-21 |

### 4.3 Epics (`epics.md`)

| Endroit | Changement |
| --- | --- |
| Résumé AD-7, AD-15, répertoires par lane | Alignés sur le spine |
| Epic 2 « Écrit seulement dans » | Ajout de `cli` et renvoi aux tests miroirs |
| Epic 6 « Écrit seulement dans » | Ajout de `pseudonymisation` ; PR courte pour `ReponseClassification` et `ReponseNarration` |
| Story 0.9 | AD élargis ; « Écrit dans » élargi aux consommateurs migrés (D2, D8), à `controle_lanes.py` et aux tests, avec la justification. Nouveau critère : exclusions par fichier, port `CacheLLM` et sa suite, formes déplacées, carte CI = carte du spine |
| Story 5.5 | Critère du Rejeu : exclusions par fichier, et cellules de Traçabilité déclarées par PR courte |
| Story 6.2 | `presidio` délègue jetons et table ; la suite `Pseudonymiseur` couvre les deux moteurs et les jetons préfixés |

### 4.4 `deferred-work.md`

- L'élément AD-21 est marqué résolu.
- L'élément AD-7, qui manquait (constat 16), est ajouté, avec le statut « spine amendé, code en 0.9 ».

## 5. Transfert pour la mise en œuvre

- **Portée : mineure.** La planification est déjà amendée. La mise en œuvre revient au développeur, dans la Story 0.9 sur `main`.
- **Destinataire** : `bmad-build`, Story 0.9, en suivant l'ordre de la § 6 de `preparation-0-9-gel-contrats.md`. L'étape 2 (ce workflow) est faite.
- **Critères de réussite** :
  1. `EXCLUSIONS_REJEU` a la forme et le contenu d'AD-7. `tests/unit/chaine/test_cli.py` applique les exclusions par fichier, et un test vérifie qu'un champ exclu dans un fichier reste comparé ailleurs.
  2. `ports/cache_llm.py` existe ; `ia/passerelle.py` n'a plus de `Protocol` local ; la suite `tests/contrat/cache_llm/` passe sur SQLite et sur la doublure.
  3. `EnveloppeCache`, `ReponseExplication` et la grammaire des jetons sont dans `contrats.llm`, `DonneesPassage` dans `contrats.passage`. `grep` ne trouve plus aucune définition de ces formes hors de `contrats`.
  4. Dans `.github/scripts/controle_lanes.py`, `adaptateurs/pseudonymisation` est en L6, et `tests/depot/test_controle_lanes.py` le couvre.
  5. D3, D4, D8 et D9 sont appliquées, puis `CONTRATS_VERSION` passe à `1.0.0` dans le dernier commit (D6).
  6. `pytest`, `ruff`, `mypy` et `lint-imports` passent en local, puis la CI est verte sous Windows et Linux avant l'étiquette.
- **Restent à faire par Anaël** : le push de `main`, la pose de l'étiquette `contrats-v1` et la création des branches de lane.
