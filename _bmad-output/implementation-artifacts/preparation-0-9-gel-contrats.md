# Préparation de la Story 0.9 : gel des contrats v1

Ce document prépare la décision de la Story 0.9 (`epics.md:504-525`) : relire `contrats/` et `ports/` contre la table *Contrats v1* et AD-1 à AD-24, puis corriger les écarts avant de poser `contrats-v1`. **Rien n'est appliqué ici.** Le document recense les écarts, pose les questions et propose une recommandation pour chacune. Les décisions et la pose de l'étiquette restent à l'humain.

Conventions de renvoi :
- `spine:N` renvoie à la ligne N de `_bmad-output/planning-artifacts/architecture/architecture-usine-migration-jira-demo-2026-10-10/ARCHITECTURE-SPINE.md` ;
- les chemins de code sont relatifs à `src/usine/` ;
- `retro:N` renvoie à la ligne N de `epic-0-retro-2026-10-12.md`.

État relevé sur `main` à `34102b2` : branche en avance de 24 commits sur `origin/main`, aucune étiquette git.

## 1. Contrats v1 du spine → code

Valeurs de la colonne « Écart » : **aucun**, **nom** (même forme, nom différent), **forme** (structure différente) ou **absent**.

| Contrat (spine) | Module attendu | Symbole(s) dans le code | Forme attendue → réelle | Écart |
| --- | --- | --- | --- | --- |
| `EnteteJournal` | `contrats.evenements` (spine:387) | `contrats/evenements.py:108` | Pydantic → `Enregistrement` gelé | aucun |
| `Evenement` | idem | `contrats/evenements.py:50`, `SCHEMA_EVENEMENT` :162 | Pydantic + schéma → idem, champs d'AD-3 complets | aucun |
| `ManifesteInjection` | idem | `contrats/evenements.py:129` | Pydantic → idem. Le champ `correspondance_cles` est un `Mapping` modifiable (:137), voir décision 4 | aucun (décision 4) |
| `Champ` | `contrats.tickets` (spine:388) | `contrats/tickets.py:28` | énumération, 10 valeurs d'AD-23 → idem | aucun |
| Domaines de valeurs | idem | `DOMAINES_CANONIQUES` `contrats/tickets.py:102` | un domaine par `Champ` (spine:308) → `entite`, `vague`, `domaine` à `None` (valeur libre, validée par `ConfigProgramme`) | forme (mineur, justifié) |
| `TicketEtat` | idem | `SCHEMA_TICKET_ETAT` `contrats/tickets.py:195` | schéma Polars → idem | nom (préfixe `SCHEMA_`) |
| `TicketTexte` | idem | `SCHEMA_TICKET_TEXTE` `contrats/tickets.py:218` | schéma Polars → idem | nom |
| `Instantane` | `contrats.calcul` (spine:389) | `SCHEMA_INSTANTANE` `contrats/calcul.py:34` | schéma Polars → idem | nom |
| `Kpi` | idem | `SCHEMA_KPI` `contrats/calcul.py:62` | schéma Polars, format long → idem ; `code_kpi` en `Utf8` libre (:56), voir décision 10 | nom |
| `Indicateur` | idem | `SCHEMA_INDICATEUR` `contrats/calcul.py:68` | `statut` et `motif` d'AD-10 → idem | nom |
| `Tendance` | idem | `SCHEMA_TENDANCE` `contrats/calcul.py:65` | schéma Polars → mêmes colonnes que le KPI | nom |
| `MeteoEntite` | `contrats.meteo` (spine:390) | `contrats/meteo.py:113` | Pydantic → idem, avec `version_grille` | aucun |
| `RegleDeclenchante` | idem | `contrats/meteo.py:74` | Pydantic → idem, avec `tickets_en_cause` (FR-17) | aucun |
| `SerieStock` | `contrats.prevision` (spine:391) | `SCHEMA_SERIE_STOCK` `contrats/prevision.py:18` | Polars → idem | nom |
| `Prevision` | idem | `contrats/prevision.py:55` | Pydantic → idem, `methode` ∈ {baseline, ml} (AD-18) | aucun |
| `RisqueEntreeRouge` | idem | `contrats/prevision.py:104` | Pydantic → idem | aucun |
| `FacteurExplicatif` | idem | `contrats/prevision.py:46` | Pydantic → idem | aucun |
| `SortieClassification` | `contrats.llm` (spine:392) | `contrats/llm.py:115` | Pydantic + `statut_controle` → idem | aucun |
| `RepartitionCauses` | idem | `SCHEMA_REPARTITION_CAUSES` `contrats/llm.py:124` | Polars → idem | nom |
| `SortieExplication` | idem | `contrats/llm.py:136`, avec `brouillon_commentaire` :143 et `phrases_retirees` :144 | Pydantic → idem | aucun |
| `SortieNarration` | idem | `contrats/llm.py:148` | Pydantic → idem | aucun |
| `ReponseAgent` | idem | `contrats/llm.py:157` | Pydantic → idem | aucun |
| `ReponseAgentEnregistree` | idem | `contrats/llm.py:167` | Pydantic, `passage_id` (AD-24) → idem | aucun |
| `get_meteo` | `contrats.agent` (spine:393) | `ArgumentsGetMeteo` / `ResultatGetMeteo` `contrats/agent.py:17,24` | Pydantic → idem | aucun |
| `list_anomalies` | idem | `ArgumentsListAnomalies` / `ResultatListAnomalies` `contrats/agent.py:32,64` | Pydantic → idem | aucun |
| `get_tendance` | idem | `ArgumentsGetTendance` / `ResultatGetTendance` `contrats/agent.py:81,99` | Pydantic → idem | aucun |
| `get_prevision` | idem | `ArgumentsGetPrevision` / `ResultatGetPrevision` `contrats/agent.py:105,112` | Pydantic → idem | aucun |
| `get_risques` | idem | `ArgumentsGetRisques` / `ResultatGetRisques` `contrats/agent.py:119,126` | Pydantic → idem | aucun |
| `EntreeTrace` | `contrats.trace` (spine:394) | `contrats/trace.py:25` | Pydantic, quatre versions et `passage_id` (AD-16) → `version_prompt` et `version_modele` facultatifs pour une trace de Prévision (:38-39, imposés en LLM par :51-62) | forme (mineur, justifié) |
| `ManifestePassage` | `contrats.passage` (spine:395) | `contrats/passage.py:87` | Pydantic, durées, `classification_initiale`, coût, alignements (AD-4, AD-8) → idem | aucun |
| `EvenementProgression` | idem | `contrats/passage.py:55` | Pydantic → idem | aucun |
| `Etape` (énumération) | idem | `contrats/passage.py:31` | 10 valeurs dans l'ordre d'AD-8 → idem | aucun |
| `ContextePassage` | idem | `contrats/passage.py:233-249` | Pydantic → `@dataclass(frozen=True)` générique `[C]` | forme (décision 5) |
| `ResultatEtape` | idem | `contrats/passage.py:252-275` | Pydantic → `@dataclass(frozen=True)`, `sorties: Mapping[str, object]` | forme (décision 5) |
| Enveloppes de fichiers | idem | `EnveloppeFichier` :198, `lire_enveloppe` :209, `CONTENUS_JSON` :142, `FICHIERS_PASSAGE` :118 | Pydantic → idem. Le manifeste est son propre modèle, sans enveloppe (:153) | aucun |
| `ConfigProgramme` | `contrats.config` (spine:396) | `contrats/config.py:104` | Pydantic → idem | aucun |
| `GrilleMeteo` | idem | `contrats/config.py:187` | Pydantic → idem ; `indicateurs` et `seuils` en `Mapping` (:195, :173) | aucun (décision 4) |
| `ConfigChaine` | idem | `contrats/config.py:37` | Pydantic, `palier` ∈ {1, 2} → idem, en `strict` | aucun |
| `ConfigJira` | idem | `contrats/config.py:209` | Pydantic → idem ; trois `Mapping` (:217, :219, :221) | aucun (décision 4) |
| `ConfigLLM` | idem | `contrats/config.py:269` | Pydantic → idem ; `modeles_par_tache` en `Mapping` (:274) | aucun (décision 4) |
| `ConfigPseudonymisation` | idem | `contrats/config.py:307` | Pydantic → idem | aucun |
| `ConfigDemo` | idem | `contrats/config.py:319` | Pydantic → idem | aucun |
| `calendrier` | `contrats.calendrier` (spine:397, AD-17) | `jour_local` :50, `jour_ouvre_de` :63, `est_jour_ouvre` :45, `fenetre_glissante` :92, `jour_ouvre_precedent` (J-1, J-5) :69, `semaine_programme` :101 | `semaine_programme(d)` (spine:250) → `semaine_programme(d, ancrage)` : l'ancrage vient de l'`EnteteJournal` | forme (mineur, justifié) |
| `format` | `contrats.format` (AD-11) | `formater_entier` :46, `formater_nombre` :53, `formater_fraction` :59, `formater_pourcentage` :66, `formater_date` :73 | milliers, virgule, %, dates → idem ; aucun format d'horodatage (onglet 9, « horodatage d'extraction ») | aucun (à surveiller) |
| `versions` | `contrats.versions` (AD-16) | `CONTRATS_VERSION` :9, `version_grille` :41, `version_prompt` :46, `version_modele` :51, `version_donnees` :61 | quatre empreintes → idem ; `CONTRATS_VERSION = "0.1.0"` au lieu de `1.0.0` | forme (décision 6) |
| `valider(df, SCHEMA_X)` | `contrats` (AD-2, spine:75) | `contrats/schemas.py:39`, réexporté par `contrats/__init__.py:4` | types et colonnes → idem ; nullabilité non contrôlée | aucun (décision 3) |
| `UsineErreur` | Conventions (spine:334) | `contrats/erreurs.py:4` | exception racine → idem | aucun |

Énumérations nommées dans les Conventions (spine:331) :

| Énumération | Symbole | Valeurs attendues → réelles | Écart |
| --- | --- | --- | --- |
| `Couleur` | `contrats/meteo.py:14` | `vert < jaune < orange < rouge`, ordonnée → idem. Ordre par `rang` (:26-48), `TypeError` face à un `str`, `pl.Enum` ordonné (`calcul.py:78`) | aucun |
| `Gravite` | `contrats/tickets.py:54` | `bloquante, majeure, mineure` → idem | aucun |
| Statuts H-17 | `StatutAnomalie` `contrats/tickets.py:43`, avec `StatutTest` :70 et `StatutCertification` :78 | workflow H-17 → 6 statuts ; `STATUTS_FERMES` :156 | nom (le spine dit « statuts H-17 », sans nom de symbole) |
| `CodeIndicateur` | `contrats/meteo.py:54` | `IND-1`…`IND-8` → idem (membres `ind_1`…) | aucun |
| `CauseRacine` | `contrats/tickets.py:86` | les 7 de H-18 → idem | aucun |
| `Champ` | `contrats/tickets.py:28` | AD-23 → idem | aucun |
| `Etape` | `contrats/passage.py:31` | AD-8 → idem | aucun |

**Bilan :** aucun contrat du spine n'est absent. Les écarts de nom tiennent tous au préfixe `SCHEMA_` des tables, une convention à entériner dans le spine. Deux écarts de forme demandent une décision (`ContextePassage`/`ResultatEtape`, `CONTRATS_VERSION`). Les autres sont mineurs et justifiés.

## 2. Ports

Les six ports du spine (spine:398) :

| Port | Fichier | Méthodes | Conformité |
| --- | --- | --- | --- |
| `SourceTickets` | `ports/source_tickets.py:11` | `evenements(depuis)` :14 | AD-3, AD-20 : conforme |
| `EntrepotExtraction` | `ports/entrepot.py:11` | `repere` :14, `enregistrer` (atomique) :18, `evenements` :25 | AD-6 : conforme |
| `FournisseurLLM` | `ports/fournisseur_llm.py:18` | `version_modele` :22, `generer_structure` :26, `executer_agent` :32 | AD-13 : conforme (la propriété `version_modele` s'ajoute aux deux méthodes) |
| `Pseudonymiseur` | `ports/pseudonymiseur.py:7` | `pseudonymiser` :10, `reidentifier` :14, `apercu` :18 | AD-11 (FR-31), AD-15 : conforme |
| `Consultation` | `ports/consultation.py:25` | voir ci-dessous | voir ci-dessous |
| `Etape` | `ports/etape.py:10` | `executer(ctx: ContextePassage[Consultation]) -> ResultatEtape` :13 | AD-22 : conforme. Il porte le même nom que l'énumération `contrats.passage.Etape`, comme dans le spine ; `chaine/execution.py` l'importe sous l'alias `PortEtape` |

Lectures de `Consultation` exigées par AD-2 (spine:77), AD-11 et le critère de la Story 0.5 (`epics.md:329`) :

| Exigence | Lecture | Présente ? |
| --- | --- | --- |
| FR-17 : Règles déclenchantes et tickets en cause | `meteo()` `ports/consultation.py:40` (`RegleDeclenchante.tickets_en_cause`) | oui |
| FR-19 : J-1 et J-5 | `evolution_meteo()` :46 | oui |
| FR-26, onglet 1 (Synthèse) | `meteo` :40, `evolution_meteo` :46, `previsions` :94, `risques` :100 | oui |
| FR-26, onglet 2 (Météo détaillée) | `indicateurs()` :56 ; les seuils viennent de `ctx.configuration.grille_meteo` | oui |
| FR-26, onglets 3 et 4 (KPI, Tendances) | `kpi()` :62, `tendances()` :66 | oui |
| FR-26, onglet 5 (Anomalies ouvertes) | `anomalies()` :78 (âge, cause proposée) | oui, **sans filtre `palier`** alors que `cause_racine_proposee` est du Palier 2 (`contrats/agent.py:54`), voir décision 9 |
| FR-26, onglets 6 et 7 (Tests, Certifications) | `tickets_etats()` :70, `instantanes()` :50 | oui |
| FR-26, onglet 8 (Commentaires) | `explications` :114, `repartition_causes` :110, `classification` :106 | oui |
| FR-26, onglet 9 (Traçabilité) | `manifeste()` :32, `traces()` :126 | oui |
| FR-27 (7 sections) | mêmes lectures, plus `narrations()` :120 | oui |
| FR-39 : outils de l'Agent, pour toute Date d'arrêté disponible | `meteo`, `evolution_meteo`, `anomalies`, `tendances`, `previsions`, `risques` ; `dates_disponibles()` :36 | oui |
| FR-43 : carte, détail d'Entité | `dernier_passage` :28, `meteo`, `kpi`, `explications`, `previsions` | oui |
| FR-44 : temps du dernier Passage réussi **sans classification initiale** (`epics.md:1735-1739`) | `dernier_passage()` :28 ne filtre pas sur `classification_initiale`, et aucune lecture ne liste les Passages | **non**, voir décision 9 |
| FR-45 : Mode repli | même port, sur `demo/repli/passage/` (Story 7.6). Les `ReponseAgentEnregistree` (`demo/repli/agent/`) sont hors Passage, donc hors `Consultation` par AD-11 | oui (pour le Passage) |
| FR-46 : filtre `palier` | `classification` :106, `repartition_causes` :110, `explications` :114, `narrations` :120 | oui, sauf `anomalies` (décision 9) |
| Prompts (explication, narration) | `meteo`, `kpi`, `repartition_causes`, `textes_tickets` :74, `previsions` | oui |
| `url_ticket(cle)` (AD-11, FR-29) | :130 | oui |
| `dernier_passage()` (AD-7) | :28 | oui |

L'ouverture d'un Passage donné n'est pas une méthode du port. Elle passe par la fabrique `Callable[[Path], Consultation]` de `chaine/execution.py` (paramètre de `executer_passage`), conforme à AD-22.

## 3. Contrats présents dans le code mais absents du spine

Ces formes vivent dans `contrats/` ou `ports/` sans figurer dans la table du spine. Elles seront gelées avec le reste : à entériner dans le spine, ou à alléger, avant l'étiquette.

- **Socle :**
  - `Enregistrement` `contrats/modele.py:29` : base gelée, `extra="forbid"`.
  - `PassageId` :13, `VersionContrats` :25, `MOTIF_PASSAGE_ID_TEXTE` :10 : types annotés réutilisés partout.
  - `SchemaTable` `contrats/schemas.py:14` et `enum_polars` :27 : support d'AD-2.
- **Événements :** `NatureEvenement` `contrats/evenements.py:33`, `SourceEvenement` :42, `CleTicket` :29 et `evenements_en_table` :182, qui convertit en table.
- **Tickets :**
  - `TypeTicket` `contrats/tickets.py:20`, `Phase` :62, `StatutTest` :70 et `StatutCertification` :78 : domaines d'AD-23, non nommés dans la table.
  - `MOTIF_CLE_TICKET` :16, `CHAMPS_PAR_TYPE` :118, `STATUTS_FERMES` :156 (définition d'Entrée et de Sortie) et `LIBELLES` :161 (libellés d'affichage).
- **Calcul :** `StatutIndicateur` `contrats/calcul.py:27` (AD-10) et `PERIMETRE_PROGRAMME` :23.
- **Météo :**
  - `Operateur` `contrats/meteo.py:67` : opérateur de seuil.
  - `EvolutionMeteo` :135 : forme de FR-19, lue par `Consultation` et par `get_meteo`.
- **Prévision :** `MethodePrevision` `contrats/prevision.py:31`, `StatutPrevision` :38 et `ContenuPrevisions` :129, le contenu de `previsions.json`.
- **LLM :**
  - `Tache` `contrats/llm.py:23` et `StatutControle` :32 : nommés dans AD-12.
  - `ParametresAppel` :43, `ReponseStructuree` :52, `AppelOutil` :65, `MessageAgent` :73 et `ReponseAgentBrute` :105 : signatures d'AD-13.
  - `OutilAgent` :92 : un `@dataclass` qui porte un `Callable`.
- **Agent :** `AnomalieResume` `contrats/agent.py:43` et `PointTendance` :88 : éléments des résultats d'outils.
- **Trace :** `TypeTrace` `contrats/trace.py:18`, qui distingue LLM et Prévision.
- **Passage :**
  - `StatutEtape` `contrats/passage.py:46` et `ExecutionEtape` :65 : durée d'étape (AD-8).
  - `EXCLUSIONS_REJEU` :172 (AD-7, décision 7), `MOTIF_PASSAGE_ID` :183, `former_passage_id` :189, `chemin_fichier_passage` :165 et `est_du_type` :157.
- **Configuration :**
  - `ConfigUsine` `contrats/config.py:330` : agrégat passé à `ContextePassage`.
  - `PeriodePhase` :57, `VagueProgramme` :71, `EntiteProgramme` :79, `VolumetrieProgramme` :87, `SeuilGrille` :154, `GardeFous` :158, `RegleIndicateur` :165 et `Reconnaisseur` :290 : sous-modèles.
- **Calendrier :** `Horodatage` `contrats/calendrier.py:29`, `FUSEAU` :16, `TAILLE_FENETRE_GLISSANTE` :19, `jour_ouvre_suivant` :55, `jours_ouvres` :81, `verifier_lundi` :111 et `dernier_jour_ouvre_ecoule` :118.
- **Versions :** `CLE_VERSION` `contrats/versions.py:12` (clé portée par JSON et Parquet), `version_majeure` :18 et `verifier_version` :26.
- **Ports :** l'alias `Palier` `ports/consultation.py:21` et la propriété `FournisseurLLM.version_modele` `ports/fournisseur_llm.py:22`.

Formes qui franchissent une frontière, mais hors `contrats/` et `ports/` (constats 1 et 2 de la rétrospective, retro:33-39) :
- `Protocol` locaux :
  - `CacheLLM` `ia/passerelle.py:34`, implémenté par `CacheLLMSqlite` `adaptateurs/stockage_sqlite/__init__.py:57` ;
  - `TablePseudonymes` `adaptateurs/pseudonymisation/__init__.py:99`, implémenté par `TablePseudonymesSqlite` `adaptateurs/stockage_sqlite/__init__.py:87` ;
  - `LectureMeteo` `ui/carte.py:28`, sous-ensemble de `Consultation`.
- Formes :
  - `EnveloppeCache` `ia/passerelle.py:46`, persistée dans `cache_llm.sqlite` ;
  - `ReponseExplication` `ia/explication.py:48`, schéma envoyé à `FournisseurLLM.generer_structure` ;
  - `DonneesPassage` `chaine/execution.py:35`, construite par `composition.py:239`.

## 4. Décisions à prendre avant le gel

Après le gel, chaque décision reportée coûte une PR sur `main`, un incrément de `CONTRATS_VERSION` et un rebase des huit lanes (spine:77). Une réponse « oui » ajoute du travail sur `contrats/` et `ports/` en 0.9.

**D1. Promouvoir `CacheLLM`, `TablePseudonymes` et `LectureMeteo` en ports ?**
- Options :
  - (a) promouvoir les trois dans `ports/` ;
  - (b) promouvoir `CacheLLM` seul et garder les deux autres en local ;
  - (c) tout garder en local et le consigner dans le spine.
- Preuves :
  - `ia/passerelle.py:34` est implémenté dans `adaptateurs/stockage_sqlite/__init__.py:57` : la forme franchit `ia` ↔ `adaptateurs`, donc deux lanes ;
  - `TablePseudonymes` (`adaptateurs/pseudonymisation/__init__.py:99`) reste interne à `adaptateurs`, et AD-15 veut la table « accessible seulement via le port `Pseudonymiseur` » (spine:222) ;
  - `LectureMeteo` (`ui/carte.py:28`) existe parce que `ui` ne peut pas importer `ports` (`pyproject.toml:273`).
- **Recommandation : (b).** `CacheLLM` est un contrat entre deux lanes qui dérivera s'il n'est pas gelé. Un port `TablePseudonymes` exposerait ce qu'AD-15 cache. `LectureMeteo` n'est qu'une vue structurelle de `Consultation`, qu'un test de conformité suffit à tenir alignée.

**D2. Déplacer `EnveloppeCache`, `ReponseExplication` et `DonneesPassage` dans `contrats` ?**
- Options :
  - (a) déplacer les trois (`EnveloppeCache` et `ReponseExplication` dans `contrats.llm`, `DonneesPassage` dans `contrats.passage`) ;
  - (b) déplacer les deux formes LLM seulement ;
  - (c) ne rien déplacer et amender AD-2.
- Preuves :
  - AD-2, « toute forme qui franchit une frontière de paquet ou de fichier » (spine:74) ;
  - `ia/passerelle.py:46` est persistée en SQLite ;
  - `ia/explication.py:48` est le schéma passé au port ;
  - `chaine/execution.py:35` (lane) est construit par `composition.py:239` (propriété de `main`).
- **Recommandation : (a).** Les trois franchissent une frontière de propriété. Fixer en même temps la règle « un schéma `Reponse<Tache>` par tâche dans `contrats.llm` » évite que la classification et la narration recréent le cas en L6.

**D3. Nullabilité dans `SchemaTable` ?**
- Options :
  - (a) ajouter à `SchemaTable` un ensemble `non_nulles` contrôlé par `valider` ;
  - (b) déclarer toutes les colonnes nullables et le documenter ;
  - (c) des validateurs propres à chaque table.
- Preuves :
  - `contrats/schemas.py:13-24` et `:39-58` ne contrôlent que le nom et le type ;
  - vérifié : une ligne entièrement nulle passe `valider(df, SCHEMA_KPI)` ;
  - certaines colonnes sont nulles par conception (`contrats/tickets.py:214`, `calcul.py:50`).
- **Recommandation : (a).** Ajouter la contrainte après le gel ferait échouer des producteurs déjà écrits, donc un changement majeur, alors qu'elle coûte peu aujourd'hui.

**D4. `Mapping` modifiables dans des modèles gelés ?**
- Options :
  - (a) un type annoté commun qui fige en `MappingProxyType` après validation, avec un test d'aller-retour JSON ;
  - (b) remplacer les `Mapping` par des tuples de paires ;
  - (c) accepter et documenter.
- Preuves :
  - vérifié : `AppelOutil.arguments` est un `dict` modifiable sur un modèle `frozen` (`contrats/llm.py:70`) ;
  - même cas pour `evenements.py:137`, `config.py:173`, `:195`, `:217`, `:219`, `:221` et `:274`, et pour `ResultatEtape.sorties`, qui est déjà figé (`passage.py:274`).
- **Recommandation : (a).** Les YAML et JSON restent identiques, et l'immuabilité promise par AD-2 devient réelle.

**D5. `ContextePassage` et `ResultatEtape` : `dataclass` ou Pydantic ?**
- Options :
  - (a) garder les `dataclass` et amender le spine (spine:395) ;
  - (b) les convertir en Pydantic avec `arbitrary_types_allowed`.
- Preuves :
  - `contrats/passage.py:233` et `:252` ;
  - ils portent une `Consultation` et des `DataFrame`, et ne sont jamais sérialisés ;
  - `OutilAgent` (`llm.py:92`) et `SchemaTable` (`schemas.py:13`) suivent le même motif.
- **Recommandation : (a).** Pydantic n'apporterait aucune validation utile sur des objets non sérialisés : il suffit de nommer la règle (« `dataclass` gelée pour les objets en mémoire non sérialisés »).

**D6. `CONTRATS_VERSION` 0.1.0 → 1.0.0 : à quel moment ?**
- Options :
  - (a) dans le dernier commit de 0.9, après toutes les corrections ;
  - (b) dès maintenant, avant les corrections.
- Preuves :
  - `contrats/versions.py:9` ;
  - tests figés sur « 0.1.0 » : `tests/unit/contrats/test_versions.py:24`, `test_passage.py:102,159,167,171,216`, `test_llm.py:63` et `test_evenements.py:140`. Le cas « version majeure différente » de `test_passage.py:167` remplace par `"1.0.0"` et doit passer à une autre majeure ;
  - le Journal local `donnees/journal.jsonl` (non versionné) et les Passages sous `sorties/` portent `0.1.0` et deviendront illisibles (`versions.py:26-32`).
- **Recommandation : (a).** Une seule incrémentation marque le gel, puis on régénère le Journal et un Passage pour vérifier.

**D7. `EXCLUSIONS_REJEU` face à AD-7.**
- Options :
  - (a) `bmad-correct-course` d'abord, pour amender AD-7, puis compléter la liste en 0.9 ;
  - (b) geler la liste actuelle et la compléter plus tard par une PR mineure sur `main`.
- Preuves :
  - `contrats/passage.py:172-180` reprend exactement AD-7 (spine:138) ;
  - la liste ignore `EntreeTrace.horodatage`, `depuis_cache`, `jetons_*` et `cout_estime_eur` (`trace.py:29,46-49`), ainsi que `ManifestePassage.cout_llm_eur` (`passage.py:102`), qui varient d'un Passage à l'autre en Palier 2 (retro:78) ;
  - les noms sont plats : exclure `horodatage` masquerait ce champ dans tous les fichiers.
- **Recommandation : (a), avec des exclusions qualifiées par fichier** (par exemple `trace/llm.jsonl:horodatage`). Le changement de forme (ensemble plat → paires fichier-champ) serait majeur après le gel.

**D8. Consolidations proposées par la rétrospective (constats 5 à 7, retro:54-56).**
- Options :
  - (a) ajouter les quatre symboles à `contrats` et migrer les consommateurs sur `main` dans la même PR ;
  - (b) ajouter les symboles seulement, et laisser chaque lane migrer ;
  - (c) reporter.
- Preuves et symboles proposés :
  - tri des clés : `consultation/passage.py:533`, `ia/controles.py:50`, `domaine/meteo.py:84` (comportement différent pour un suffixe non numérique) → `rang_cle` dans `contrats.tickets` ;
  - libellés de couleur : `rendu/commun.py:18` (`dict` modifiable), `ui/carte.py:12` → `LIBELLES_COULEURS` dans `contrats.meteo` ;
  - date `AAAA-MM-JJ` : `chaine/cli.py:14`, `generateur/cli.py:17`, `consultation/passage.py:116` → une fonction d'analyse dans `contrats.calendrier` ;
  - chemins : `composition.py:57,72`, `generateur/cli.py:19`, `ui/progression.py:16` → constantes de chemins à côté de `FICHIERS_PASSAGE`.
- **Recommandation : (a).** Ces fichiers appartiennent encore tous à `main` avant le gel. La migration dépasse toutefois le « Écrit dans » de 0.9 (`contrats/`, `ports/`, `epics.md:510`), et cet écart est à consigner.
- Question liée (retro:63-67, 172) : l'âge en Jours ouvrés et l'appariement J-1/J-5 calculés dans `consultation/passage.py:372-426` et `:293` relèvent-ils d'AD-9 ? Recommandation : les déplacer dans `domaine` seulement s'ils changent la forme du port ; sinon, les accepter comme dérivations de lecture et le consigner.

**D9. Lectures manquantes de `Consultation`, relevées par cette relecture.**
- Options :
  - (a) ajouter `sans_classification_initiale: bool = False` à `dernier_passage()` et `palier: Palier = 2` à `anomalies()` ;
  - (b) ajouter une lecture `passages() -> tuple[ManifestePassage, ...]` et laisser l'UI filtrer ;
  - (c) reporter aux lanes L7 et L8.
- Preuves :
  - Story 7.4 (`epics.md:1735-1739`) contre `ports/consultation.py:28` ;
  - FR-46 contre `ports/consultation.py:78`, dont le résultat porte `cause_racine_proposee` en Palier 2 (`contrats/agent.py:54`).
- **Recommandation : (a).** AD-7 veut que le dernier Passage soit déterminé « seulement par `consultation.dernier_passage()` », et AD-2 gèle le port avec toutes les lectures de FR-43 à FR-46.

**D10. Énumération des codes de KPI (facultatif).**
- Options :
  - (a) ajouter une énumération `CodeKpi` et typer `code_kpi` en `pl.Enum` ;
  - (b) garder un texte libre.
- Preuves : `contrats/calcul.py:56`, `contrats/agent.py:85,93` ; le spine n'exige pas d'énumération.
- **Recommandation : (b), sauf si la liste des KPI de FR-11 est déjà figée.** Passer plus tard d'`Utf8` à `Enum` serait un changement majeur : il faut le savoir en décidant.

## 5. Prérequis hors contrats avant de poser l'étiquette

1. **CI jamais vérifiée.** Pousser `main` (en avance de 24 commits sur `origin/main`) et obtenir une CI verte sous Windows et sous Linux (`.github/workflows/ci.yml`). C'est le premier critère d'acceptation de 0.9 (`epics.md:514-516`) ; la rétrospective le note « jamais vérifié » (retro:24, 164).
2. **`bmad-correct-course`** (retro:139-142), avant le gel puisqu'il modifie le spine que les lanes liront :
   - AD-7 : exclusions du Rejeu (D7) ; reporter aussi l'élément dans `deferred-work.md`, où il manque (retro:78) ;
   - AD-15, l'arborescence et la carte des lanes : `adaptateurs/pseudonymisation/` n'a pas de propriétaire (`.github/scripts/controle_lanes.py:26-77`, retro:80) ;
   - AD-21 : tests plats, `adaptateurs/cli` en lane 2, liste blanche des externes (`deferred-work.md:3-5`) ;
   - entériner dans le spine les choix de D1, D2, D5, la convention `SCHEMA_` et `semaine_programme(d, ancrage)`.
3. **Les deux correctifs « avant les lanes » de la rétrospective** (retro:137-138), sur `main` :
   - traduire en `UsineErreur` la `ValidationError` de `Secrets` (`composition.py:190`), et ajouter `USINE_RACINE` à `Secrets` et à `.env.example` (lu par `os.environ` dans `ui/app.py:36`) ;
   - alléger `composition.py` (339 lignes) : sortir les services de l'UI et l'écrivain de Journal, et unifier la résolution de l'URL Jira (`composition.py:199-200` et `:316-319`).
4. **Après l'incrémentation à 1.0.0 :** régénérer `donnees/journal.jsonl`, relancer `usine rapport` sur le mini-jeu et vérifier qu'un Passage est publié (`epics.md:514-516`).
5. **Suivi du sprint :** `epic-0-retrospective` et les dix actions ne sont pas inscrits, car le script refuse l'epic 0 (retro:184). Saisie manuelle ou correctif du script à décider.

## 6. Ordre proposé

1. Trancher D1 à D10 dans ce document.
2. Lancer `bmad-correct-course` : AD-7, AD-15 et la carte des lanes, AD-21, plus les amendements issus des décisions.
3. Appliquer sur `main` les deux correctifs « avant les lanes » (prérequis 3).
4. Appliquer les corrections de contrats retenues (D1 à D4, D7 à D9), avec les tests correspondants, en une PR dédiée.
5. Passer `CONTRATS_VERSION` à `1.0.0` et mettre à jour les tests figés (D6).
6. Régénérer le Journal, lancer `usine rapport` sur le mini-jeu, puis `pytest`, `ruff`, `mypy` et `lint-imports` en local.
7. Pousser `main` et attendre la CI verte sous Windows et Linux.
8. Poser l'étiquette `contrats-v1`, puis créer `lane/1-donnees` à `lane/8-portage` depuis l'étiquette, chacune avec son `donnees/` et son `.env` (`epics.md:522-524`).
9. Mettre à jour le suivi du sprint (story 0.9 `done`, rétrospective de l'Epic 0) et requalifier le verdict de la rétrospective.

## 7. Décisions retenues (2026-10-12)

Anaël a validé l'ensemble des recommandations :

| Décision | Choix |
| --- | --- |
| D1 | (b) promouvoir `CacheLLM` seul en port ; `TablePseudonymes` et `LectureMeteo` restent locaux, consignés dans le spine |
| D2 | (a) déplacer `EnveloppeCache`, `ReponseExplication` (dans `contrats.llm`) et `DonneesPassage` (dans `contrats.passage`) ; un schéma `Reponse<Tache>` par tâche dans `contrats.llm` |
| D3 | (a) `SchemaTable` porte un ensemble `non_nulles` contrôlé par `valider` |
| D4 | (a) type annoté commun qui fige les `Mapping` en `MappingProxyType`, avec un test d'aller-retour JSON |
| D5 | (a) garder les `dataclass` gelées et amender le spine |
| D6 | (a) passer à `1.0.0` dans le dernier commit de la 0.9 |
| D7 | (a) `bmad-correct-course` d'abord, exclusions du Rejeu qualifiées par fichier |
| D8 | (a) ajouter les quatre symboles à `contrats` et migrer les consommateurs dans la même PR. Les dérivations de `Consultation` (âge, J-1/J-5) restent des dérivations de lecture, consignées, puisqu'elles ne changent pas la forme du port |
| D9 | (a) `dernier_passage(sans_classification_initiale=…)` et filtre `palier` sur `anomalies()` |
| D10 | (b) `code_kpi` reste un texte libre |
