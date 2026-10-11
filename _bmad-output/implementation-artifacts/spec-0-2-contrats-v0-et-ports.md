---
title: 'Story 0.2 (E0-2) : contrats v0 et ports'
type: 'feature'
created: '2026-10-11'
status: 'done'
baseline_revision: 'aeeb3021ee3855c1f3773a29d131620929bf54e0'
review_loop_iteration: 1
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-0-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-usine-migration-jira-demo-2026-10-10/ARCHITECTURE-SPINE.md'
warnings: ['oversized']
deferred:
  - summary: >-
      La liste d'exclusions du Rejeu (AD-7) ne couvre pas les champs variables des traces (horodatage, depuis_cache, cout_estime_eur) ni cout_llm_eur du manifeste.
    evidence: |-
      Un Rejeu en Palier 2 servi par le cache change depuis_cache et les coûts ; la liste EXCLUSIONS_REJEU recopie celle du spine (passage_id, horodatage_debut, horodatage_fin, horodatage_extraction, version_donnees). Corriger demande d'amender AD-7 par bmad-correct-course.
    location: >-
      src/usine/contrats/passage.py (EXCLUSIONS_REJEU)
    severity: medium
---

<intent-contract>

## Intent

**Problem:** `usine.contrats` ne contient que `ConfigChaine` et `UsineErreur`, `usine.ports` est vide : aucune lane ne peut coder contre une forme partagée, et rien ne fixe le calendrier, le formatage français ni les empreintes de version (AD-2, AD-16, AD-17).

**Approach:** Définir tous les contrats de la table *Contrats v1* du spine dans leurs modules, les fonctions pures `calendrier`, `format`, `versions` et `valider`, les six ports en `typing.Protocol`, les doublures (`FournisseurFactice`, `PseudonymiseurFactice`, `SourceEnMemoire`) et les suites `tests/contrat/<port>/` paramétrées par fabrique d'adaptateur (Story 0.2 de `epics.md`).

## Boundaries & Constraints

**Always:**
- Couches : `contrats/` n'importe que pydantic, polars et la stdlib ; `ports/` n'importe que `usine.contrats` (+ stdlib, pydantic, polars). `uv run lint-imports` reste vert sans toucher `pyproject.toml`.
- Enregistrements = `BaseModel` avec `ConfigDict(frozen=True, extra="forbid")` ; collections en `tuple[...]`. Tables = `SchemaTable` nommés `SCHEMA_X`, validés par `contrats.valider(df, SCHEMA_X)`.
- Valeurs canoniques en snake_case sans accent (`en_correction`, `a_retester`, `reprise_donnees`, `migration_a_blanc`, `non_execute`, `accordee`…) ; libellés français d'affichage dans `contrats.tickets.LIBELLES`.
- Horodatages : `datetime` avec fuseau, ramenés en UTC par les modèles ; un `datetime` naïf est refusé.
- Toute erreur levée par `contrats` ou `ports` est une `UsineErreur` (ou une `ValidationError` Pydantic à la construction d'un modèle).
- Identifiants en français sans accents ; docstrings et messages en français ; mypy strict.

**Never:**
- Modifier `ConfigChaine`, `usine.config` (chargeur, `MODELES`), `pyproject.toml`, `uv.lock`, le spine, les epics ou le PRD ; ajouter une dépendance.
- Créer des fichiers `config/*.yaml` autres que `chaine.yaml` (ils appartiennent aux lanes).
- Implémenter la validation de cohérence de la Grille (FR-18, Story 3.4), un calcul métier, un adaptateur réel ou la `Consultation` réelle (Story 0.6).
- Redéfinir Jour ouvré, Fenêtre glissante, J-n, semaine ou fuseau hors de `contrats/calendrier.py`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Rattachement week-end | `jour_ouvre_de(samedi 2026-10-10 23:00 UTC)` | lundi 2026-10-12 | N/A |
| Soirée en semaine | `jour_ouvre_de(lundi 2026-10-12 22:30 UTC)` | mardi 2026-10-13 (00:30 à Paris) | N/A |
| J-5 | `jour_ouvre_precedent(lundi 2026-10-12, 5)` | lundi 2026-10-05 ; J-1 du lundi = vendredi | `UsineErreur` si `n < 0` |
| Fenêtre glissante | `fenetre_glissante(lundi 2026-10-12)` | 5 jours, du mardi 06/10 au lundi 12/10 inclus | `UsineErreur` si date non ouvrée |
| Semaine | ancrage lundi 2026-08-17, `semaine_programme(2026-10-09)` | 8 | `UsineErreur` si ancrage non lundi ou date < ancrage |
| Format | `formater_nombre(12345.5)`, `formater_nombre(1234567)`, `formater_pourcentage(Fraction(1, 8))` | `12 345,5`, `1 234 567`, `12,5 %` | N/A |
| Date | `formater_date(date(2026, 10, 5))` | `05/10/2026` | N/A |
| `valider` | colonne absente / type `Int32` au lieu de `Int64` / colonne en trop | `UsineErreur` qui nomme `SCHEMA_X` et la colonne | — |
| Versions | octets fixes `b"a: 1\n"` | `version_grille` = 12 premiers hex du SHA-256 ; `version_prompt` = 64 hex ; `version_modele("anthropic", "m")` = `anthropic:m` | N/A |
| Version de données | Journal `b"x"`, `horodatage_extraction` donné ou `None` | SHA-256 de `journal + b"\n" + isoformat UTC` (ou rien si `None`), 64 hex | N/A |
| Relecture de version | enveloppe `contrats_version="1.0.0"` relue avec `CONTRATS_VERSION="0.1.0"` | `UsineErreur` qui nomme les deux versions | — |
| Couleur | `sorted([rouge, vert, orange, jaune])`, `max(...)` | `vert, jaune, orange, rouge` ; `rouge` | comparaison avec un `str` brut : `TypeError` |
| Evenement | `vers="Fermée"` pour `champ=statut`, ou horodatage naïf | `ValidationError` | — |
| Météo | `couleur=vert` avec une règle, ou règle orange sous une Météo rouge | `ValidationError` | — |

</intent-contract>

## Code Map

- `src/usine/contrats/erreurs.py` -- `UsineErreur`, à réutiliser partout.
- `src/usine/contrats/config.py` -- `ConfigChaine` (strict, `_entier_exact`) : à conserver tel quel ; les autres modèles de configuration s'ajoutent à côté.
- `src/usine/contrats/__init__.py` -- docstring seul ; deviendra la façade (`valider`, `SchemaTable`, `CONTRATS_VERSION`, `UsineErreur`).
- `src/usine/ports/__init__.py` -- docstring seul.
- `pyproject.toml:117-246` -- contrats import-linter : `contrats` ne peut importer ni `yaml` ni `numpy` ; `ports` aucune autre couche que `contrats`. Lecture seule.
- `tests/conftest.py` -- fixture `racine_depot`, garde réseau autouse ; propriété de `main`, ne pas modifier.
- `tests/depot/test_import_linter.py` -- échoue si une dépendance n'est pas classée : ne rien importer d'externe nouveau.
- `uv.lock:1954` -- `tzdata` 2026.5, tiré sous Windows par pandas : `zoneinfo.ZoneInfo("Europe/Paris")` fonctionne sans dépendance ajoutée.
- Spine § *Contrats v1*, § *Conventions de cohérence*, AD-3, AD-7, AD-8, AD-10 à AD-17, AD-22, AD-23 -- invariants que les champs doivent porter.
- PRD § Glossaire, FR-11, FR-17, FR-19, FR-20, FR-21, FR-26, FR-34, FR-39, FR-43 à FR-46 -- lectures de `Consultation` et champs requis.

## Tasks & Acceptance

**Execution:**
- `src/usine/contrats/versions.py` -- `CONTRATS_VERSION = "0.1.0"`, `version_majeure`, `verifier_version(version)` (`UsineErreur` si majeure différente), `version_grille(octets)`, `version_prompt(octets)`, `version_modele(fournisseur, modele)`, `version_donnees(journal, horodatage_extraction)` -- AD-2, AD-16.
- `src/usine/contrats/schemas.py` -- `SchemaTable(nom, colonnes: Mapping[str, pl.DataType])` (frozen dataclass) et `valider(df, schema) -> pl.DataFrame` (colonnes dans l'ordre du schéma) -- AD-2.
- `src/usine/contrats/calendrier.py` -- `FUSEAU`, `est_jour_ouvre`, `jour_local`, `jour_ouvre_de`, `jour_ouvre_suivant`, `jour_ouvre_precedent(d, n)`, `jours_ouvres(debut, fin)`, `fenetre_glissante(d, taille=5)`, `semaine_programme(d, ancrage)`, `dernier_jour_ouvre_ecoule(aujourd_hui)` -- AD-17, H-1, H-19, H-25.
- `src/usine/contrats/format.py` -- `formater_nombre`, `formater_entier`, `formater_fraction`, `formater_pourcentage(Fraction, decimales=1)`, `formater_date` ; espace insécable U+00A0 ; arrondi au demi supérieur via `Decimal` -- AD-11.
- `src/usine/contrats/tickets.py` -- `TypeTicket`, `Champ` (sans `cause_racine`), `StatutAnomalie`, `Gravite`, `Phase`, `StatutTest`, `StatutCertification`, `CauseRacine`, `DOMAINES_CANONIQUES: Mapping[Champ, frozenset[str] | None]`, `CHAMPS_PAR_TYPE`, `STATUTS_FERMES`, `LIBELLES`, `SCHEMA_TICKET_ETAT`, `SCHEMA_TICKET_TEXTE` -- AD-23, H-17, H-18.
- `src/usine/contrats/evenements.py` -- `NatureEvenement`, `SourceEvenement`, `Evenement` (règles de cohérence nature/champ/domaine), `EnteteJournal`, `ManifesteInjection`, `SCHEMA_EVENEMENT`, `evenements_en_table(evenements)` -- AD-3, AD-4.
- `src/usine/contrats/calcul.py` -- `StatutIndicateur`, `SCHEMA_INSTANTANE`, `SCHEMA_KPI`, `SCHEMA_INDICATEUR`, `SCHEMA_TENDANCE`, `PERIMETRE_PROGRAMME` -- AD-9, AD-10, FR-11, FR-12.
- `src/usine/contrats/meteo.py` -- `Couleur` (ordonnée), `CodeIndicateur`, `Operateur`, `RegleDeclenchante`, `MeteoEntite`, `EvolutionMeteo` -- FR-16, FR-17, FR-19.
- `src/usine/contrats/prevision.py` -- `SCHEMA_SERIE_STOCK`, `MethodePrevision`, `StatutPrevision`, `FacteurExplicatif`, `Prevision`, `RisqueEntreeRouge` -- AD-18, FR-20, FR-21.
- `src/usine/contrats/llm.py` -- `Tache`, `StatutControle`, `ParametresAppel`, `ReponseStructuree[T]`, `MessageAgent`, `AppelOutil`, `OutilAgent`, `ReponseAgentBrute`, `SortieClassification`, `SCHEMA_REPARTITION_CAUSES`, `SortieExplication`, `SortieNarration`, `ReponseAgent`, `ReponseAgentEnregistree` -- AD-12, AD-13.
- `src/usine/contrats/agent.py` -- arguments et résultats de `get_meteo`, `list_anomalies` (`AnomalieResume`), `get_tendance` (`PointTendance`), `get_prevision`, `get_risques` -- FR-39.
- `src/usine/contrats/trace.py` -- `TypeTrace`, `EntreeTrace` -- AD-12, AD-16, FR-34.
- `src/usine/contrats/passage.py` -- `Etape` (ordre AD-8), `StatutEtape`, `EvenementProgression`, `ExecutionEtape`, `ManifestePassage`, `FICHIERS_PASSAGE`, `EXCLUSIONS_REJEU`, `MOTIF_PASSAGE_ID`, `former_passage_id`, `EnveloppeFichier[T]`, `lire_enveloppe`, `ContextePassage[C]`, `ResultatEtape` -- AD-7, AD-8, AD-22.
- `src/usine/contrats/config.py` -- ajouter `ConfigProgramme`, `GrilleMeteo`, `ConfigJira`, `ConfigLLM`, `ConfigPseudonymisation`, `ConfigDemo`, `ConfigUsine` -- AD-19.
- `src/usine/contrats/__init__.py` -- façade : `CONTRATS_VERSION`, `SchemaTable`, `UsineErreur`, `valider`.
- `src/usine/ports/{source_tickets,entrepot,fournisseur_llm,pseudonymiseur,consultation,etape}.py` + `__init__.py` -- les six `Protocol` (voir Design Notes), réexportés.
- `tests/doublures/{__init__,fournisseur_factice,pseudonymiseur_factice,source_en_memoire}.py` -- doublures déterministes, sans réseau.
- `tests/contrat/{source_tickets,fournisseur_llm,pseudonymiseur,consultation}/` -- `fabriques.py` (liste `FABRIQUES` de `(id, fabrique)`), `conftest.py` (fixture paramétrée), `test_contrat.py` ; `consultation` a une liste vide (tests ignorés par pytest, câblés pour la Story 0.6).
- `tests/unit/contrats/test_{versions,schemas,calendrier,format,tickets,evenements,meteo,prevision,llm,passage,config}.py`, `tests/unit/ports/test_ports.py` -- matrice I/O et invariants.

**Acceptance Criteria:**
- Given la table *Contrats v1*, when un test importe chaque nom listé depuis son module, then tous existent ; les enregistrements sont des `BaseModel` gelés (affectation refusée) et chaque `SCHEMA_X` est un `SchemaTable`.
- Given `ports`, when un test inspecte les six ports, then chacun est un `typing.Protocol`, `FournisseurLLM` a `generer_structure` et `executer_agent`, `Consultation` a toutes les lectures de la Design Note.
- Given `Etape`, when on liste ses membres, then l'ordre est celui d'AD-8 ; `Champ` n'a pas de membre `cause_racine` ; `CauseRacine` et `StatutAnomalie` ont exactement les valeurs de H-18 et H-17 (assertion valeur par valeur).
- Given un fichier `src/usine/**/*.py` autre que `contrats/calendrier.py`, when un test le lit, then il ne contient ni `Europe/Paris`, ni `zoneinfo`, ni `.weekday(`, ni `.isoweekday(`, ni `.isocalendar(`, ni `pytz`, ni `dateutil`.
- Given `uv run pytest tests/contrat`, when la suite tourne, then `FournisseurFactice`, `PseudonymiseurFactice` et `SourceEnMemoire` passent ; la suite `consultation` est collectée sans erreur.
- Given le dépôt, when `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest`, then tout passe.

## Spec Change Log

### 2026-10-11 — Boucle 1 (bad_spec)

- **Déclencheurs :** colonnes d'énumération en `Utf8` (aucun contrôle de domaine, `couleur` triée par l'alphabet dans Polars) ; contenu de `previsions.json` non défini, d'où des `RisqueEntreeRouge` sans fichier ; `Consultation.anomalies` sans `limite` et `tendances` sans `code_kpi`, alors que les outils de l'Agent les exposent ; `ConfigJira` limité aux statuts d'Anomalie ; Palier porté deux fois (`ContextePassage.palier` et `ConfigChaine.palier`).
- **Amendements (hors `<intent-contract>`) :** Design Notes *Choix de forme* (`pl.Enum`), nouvelle note *Contenu des fichiers JSON* (`CONTENUS_JSON`, `ContenuPrevisions`), `ContextePassage.palier` en propriété, lectures `Consultation` complétées (`instantanes`, `code_kpi`, `limite`), nouvelles notes *`ConfigJira`* et *Invariants des modèles* (qui reprennent les correctifs de la passe), règle de `transition` (`vers` obligatoire et différent de `de`), deux critères d'acceptation resserrés (garde du temps élargie, valeurs H-17 et H-18).
- **État à éviter :** des tables d'énumérations qui acceptent des libellés non canoniques, une « pire couleur » calculée par l'alphabet dans Polars, une étape `prevision` qui n'a nulle part où écrire ses risques, deux sources du Palier.
- **KEEP :** tout le code de la passe 1 est conservé en place. Le retour à la base a été refusé par le classifieur de permissions, comme opération destructive ; l'implémenteur amende donc l'existant au lieu de repartir de zéro. À garder tels quels : la découpe en modules, `modele.py` (base `Enregistrement`), `Couleur` qui lève `TypeError`, les dataclasses `ContextePassage`/`ResultatEtape`, la façade `contrats/__init__.py`, les doublures et les quatre suites de contrat avec leurs `FABRIQUES`, `test_inventaire.py`, et toute la couverture de la matrice I/O. Ajouter les tests manquants relevés par la revue : statut non final d'`ExecutionEtape` refusé ; fin avant début de `ManifestePassage` ; ordre des dates d'`EnteteJournal` ; phase `semaine_fin < semaine_debut`, `entrees_semaine_max < min` et code de Vague dupliqué dans `ConfigProgramme` ; les deux sens des règles « si et seulement si » de `Prevision`.

## Review Triage Log

### 2026-10-11 — Review pass
- verdicts: 61 findings — high 0, medium 16, low 40, false 5, maybe-false 0
- findings:
  - `[false]` `[reject]` (intention) L'inventaire ne vérifie pas les noms `TicketEtat`, `Kpi`… — la colonne *Forme* du spine (« schémas Polars ») et le critère « données tabulaires des schémas Polars `SCHEMA_X` » font de `SCHEMA_TICKET_ETAT` la forme attendue.
  - `[low]` `[reject]` (intention) Aucune lecture de `ReponseAgentEnregistree` (FR-45) — les réponses enregistrées vivent dans `demo/repli/agent/`, hors Passage (AD-24), et `Consultation` est le lecteur d'un Passage (AD-11) ; la lane L7 tranchera.
  - `[false]` `[reject]` (intention) FR-44 et le cumul sur 5 Rapports — AD-8 : cumul = 5 × le temps du dernier Passage, lisible par `dernier_passage()`.
  - `[false]` `[reject]` (intention) FR-27 cité par aucune docstring — le PowerPoint lit les mêmes tables et modèles que l'Excel ; aucune lecture ne manque.
  - `[low]` `[bad_spec]` (intention) Valeurs de H-17 et H-18 vérifiées par leur nombre seulement — critère d'acceptation resserré (valeur par valeur).
  - `[low]` `[reject]` (intention) Garde AD-17 limitée à `src/` — `tests/` utilise légitimement `ZoneInfo` pour construire des cas.
  - `[low]` `[bad_spec]` (verification-gap) Statut non final d'`ExecutionEtape` non testé — test ajouté au KEEP.
  - `[low]` `[bad_spec]` (verification-gap) Fin avant début de `ManifestePassage` non testée — test ajouté au KEEP.
  - `[low]` `[bad_spec]` (verification-gap) Ordre des dates d'`EnteteJournal` non testé — test ajouté au KEEP.
  - `[low]` `[bad_spec]` (verification-gap) Trois règles de `ConfigProgramme` non testées — tests ajoutés au KEEP.
  - `[low]` `[bad_spec]` (verification-gap) Règles « si et seulement si » de `Prevision` testées dans un seul sens — tests ajoutés au KEEP.
  - `[low]` `[reject]` (blind) `verifier_version` laxiste en 0.x — règle de version majeure fixée par AD-2 ; le gel E0-9 passe en 1.0.0.
  - `[medium]` `[bad_spec]` (blind) `contrats_version` non vérifié hors `lire_enveloppe` — note *Invariants des modèles*.
  - `[medium]` `[bad_spec]` (blind) `valider` ne vérifie pas les domaines des colonnes d'énumération — `pl.Enum`.
  - `[medium]` `[bad_spec]` (blind) `couleur` triée par l'alphabet dans Polars — `pl.Enum` ordonné.
  - `[medium]` `[bad_spec]` (blind) `RegleDeclenchante` ne vérifie pas le franchissement du seuil — note *Invariants* (la partie `RisqueEntreeRouge` est rejetée : peu probable, la garde demanderait le calendrier).
  - `[low]` `[reject]` (blind) `format` : `InvalidOperation` au-delà de 28 chiffres et double arrondi d'une `Fraction` — aucun chiffre du projet n'en approche ; le correctif ajouterait de l'arithmétique.
  - `[low]` `[bad_spec]` (blind) Garde du temps sans `.isocalendar(`, `pytz`, `dateutil` — critère d'acceptation élargi.
  - `[medium]` `[bad_spec]` (blind) `transition` avec `vers=None` ou `de == vers` acceptée — règle d'`Evenement` amendée.
  - `[low]` `[reject]` (blind) Ordre non total à horodatage égal dans `SourceTickets` — la suite impose déjà « création d'abord » ; un ordre total relève des adaptateurs de L2.
  - `[low]` `[reject]` (blind) `EntrepotExtraction` sans suite de contrat — AD-20 et la story ne demandent que quatre suites.
  - `[medium]` `[bad_spec]` (blind) `anomalies` sans `limite`, `tendances` sans `code_kpi` — lectures complétées.
  - `[medium]` `[bad_spec]` (blind) Risques et série de stock sans fichier — `CONTENUS_JSON`, `ContenuPrevisions`.
  - `[medium]` `[defer]` (blind) `EXCLUSIONS_REJEU` ne couvre pas les traces (`horodatage`, `depuis_cache`, coût) — la liste est nommée par AD-7 dans le spine ; à porter par `bmad-correct-course`.
  - `[low]` `[reject]` (blind) `ManifestePassage` accepte des états contradictoires selon le Palier — c'est la Chaîne (Story 0.5) qui écrit le manifeste ; rien ne montre qu'elle produise ces états.
  - `[medium]` `[bad_spec]` (blind) `ConfigJira` limité aux statuts d'Anomalie — note *`ConfigJira`*.
  - `[low]` `[bad_spec]` (blind) `GrilleMeteo.couleurs` dans n'importe quel ordre — note *Invariants*.
  - `[low]` `[bad_spec]` (blind) `ConfigLLM.fournisseur` peut contenir `:` — note *Invariants* (la borne de `temperature` est rejetée : cosmétique).
  - `[low]` `[reject]` (blind) Spec et code en désaccord sur `instantanes()` — le correctif est une édition de la spec, faite par l'amendement.
  - `[low]` `[reject]` (edge) `formater_entier(10**30)` lève `InvalidOperation` — même raison que la ligne `format` ci-dessus.
  - `[low]` `[reject]` (edge) Double arrondi d'une `Fraction` à plus de 28 chiffres — idem.
  - `[low]` `[reject]` (edge) Champs `Mapping` des modèles gelés modifiables et non hachables — aucun appelant ne hache ces modèles ni ne les modifie.
  - `[low]` `[bad_spec]` (edge) `ConfigLLM.fournisseur` avec `:` — même groupe que la ligne blind.
  - `[low]` `[reject]` (edge) Phases qui se chevauchent dans une Vague — relève de la configuration complète (Story 1.1).
  - `[low]` `[bad_spec]` (edge) `seuils` vide accepté — note *Invariants*.
  - `[low]` `[bad_spec]` (edge) `couleurs` réordonnées acceptées — note *Invariants*.
  - `[medium]` `[bad_spec]` (edge) Statuts Jira des Cas de test et des Certifications sans correspondance — note *`ConfigJira`*.
  - `[low]` `[bad_spec]` (edge) Identifiants de `champs` vides ou partagés — note *`ConfigJira`*.
  - `[low]` `[reject]` (edge) Motif de reconnaisseur qui correspond à la chaîne vide — le pseudonymiseur réel est l'affaire de L6.
  - `[medium]` `[bad_spec]` (edge) `transition` vide ou sans effet — même groupe que la ligne blind.
  - `[false]` `[reject]` (edge) Transitions de Cas de test et de Certification refusées — la spec réserve `transition` au `statut` d'Anomalie ; les autres changements passent par `modification_champ`.
  - `[medium]` `[bad_spec]` (edge) `contrats_version` non vérifié dans l'en-tête, les manifestes et les réponses enregistrées — même groupe que la ligne blind.
  - `[low]` `[bad_spec]` (edge) `correspondance_cles` non injective — note *Invariants*.
  - `[low]` `[reject]` (edge) Clés de projet Jira avec `_` — le projet utilise `DEMO` ; rien ne montre qu'on en rencontre.
  - `[medium]` `[bad_spec]` (edge) Règle déclenchante sous son seuil acceptée — même groupe que la ligne blind.
  - `[low]` `[bad_spec]` (edge) Dates J-1 et J-5 dans le désordre — note *Invariants*.
  - `[low]` `[bad_spec]` (edge) Fourchette de `Prevision` incohérente — note *Invariants*.
  - `[low]` `[reject]` (edge) `RisqueEntreeRouge` : valeur déjà au-dessus du seuil, date hors horizon — la garde demanderait le calendrier ; aucun producteur ne le montre.
  - `[low]` `[reject]` (edge) Manifeste incomplet ou incohérent avec le Palier — même raison que la ligne blind.
  - `[low]` `[reject]` (edge) `chemin_fichier_passage` avec un `datetime` — paramètre typé `date`, mypy strict l'empêche.
  - `[medium]` `[bad_spec]` (edge) `ContextePassage.palier` en conflit avec `configuration.chaine.palier` — `palier` devient une propriété.
  - `[low]` `[reject]` (edge) `lire_enveloppe` sur un type non paramétrable — appel interne, échec bruyant.
  - `[medium]` `[bad_spec]` (edge) Domaines des colonnes non vérifiés par `valider` — même groupe que la ligne blind.
  - `[low]` `[reject]` (edge) Trace de prévision qui porte des champs LLM — aucun producteur ne le fait ; garde de faible valeur.
  - `[low]` `[reject]` (edge) `statut_controle` et `phrases_retirees` non liés — une explication en échec peut avoir des phrases retirées ; le lien proposé est faux.
  - `[low]` `[bad_spec]` (edge) `total < len(anomalies)` accepté — note *Invariants*.
  - `[medium]` `[bad_spec]` (edge) `limite` et `code_kpi` absents du port — même groupe que la ligne blind.
  - `[low]` `[reject]` (edge) `FournisseurFactice` exécute des outils avant de refuser un outil inconnu — doublure de test, outils sans effet de bord.
  - `[low]` `[reject]` (edge) `FournisseurFactice` ne valide pas les arguments des outils — doublure, sans conséquence.
  - `[low]` `[reject]` (edge) `SourceEnMemoire` signale `depuis` naïf au premier `next()` — doublure ; l'erreur finit par sortir.
  - `[false]` `[reject]` (edge) `ROUND_HALF_UP` sur les négatifs — l'arrondi « au demi supérieur » s'éloigne de zéro, comme le teste le code.

### 2026-10-11 — Review pass (boucle 1)
- verdicts: 50 findings — high 0, medium 1, low 44, false 5, maybe-false 0
- findings:
  - `[false]` `[reject]` (intention) Noms tabulaires du spine absents en symboles — carried : la colonne *Forme* fait de `SCHEMA_X` la forme attendue.
  - `[low]` `[reject]` (intention) Garde AD-17 limitée à `src/` — carried : `tests/` construit ses cas avec `ZoneInfo`.
  - `[low]` `[reject]` (intention) Couverture FR de `Consultation` vérifiée par les noms de méthode ; FR-45 sans lecture — carried : les réponses enregistrées sont hors Passage (AD-24).
  - `[low]` `[reject]` (intention) Suite `consultation` jamais exécutée, pas de suite `EntrepotExtraction` — carried : suite câblée pour la Story 0.6, AD-20 et la story ne demandent que quatre suites.
  - `[false]` `[reject]` (intention) Refus de version placé dans l'enveloppe et non dans `Consultation` — le critère vise l'enveloppe ; `Consultation` arrive en Story 0.6 et réutilisera `verifier_version`.
  - `[false]` `[reject]` (intention) `Couleur` ordonnée — l'auditeur ne relève aucune divergence.
  - `[false]` `[reject]` (intention) Contrats ajoutés hors table du spine — le spine laisse les champs libres jusqu'au gel E0-9, et tous sont dans les répertoires de la story.
  - `[low]` `[patch]` (verification-gap) Trace LLM sans `fournisseur` non testée — `fournisseur` ajouté à la boucle de `test_trace_llm_porte_les_quatre_versions`.
  - `[low]` `[patch]` (verification-gap) Trace de prévision avec `tache` testée seulement via le cache — cas `tache` posé et `depuis_cache=False` ajouté.
  - `[low]` `[reject]` (verification-gap) Corps de la suite `consultation` jamais exécutés — attendu jusqu'à la Story 0.6 ; un échec y sera d'abord soupçonné côté test.
  - `[low]` `[reject]` (blind) `SchemaTable` sans notion de nullabilité — aucun producteur encore ; la garde ajouterait une forme nouvelle au contrat (à revoir au gel E0-9).
  - `[low]` `[reject]` (blind) Sorties Parquet de `ResultatEtape` non validées — l'`EcrivainPassage` (Story 0.5) valide à l'écriture ; la garde ajouterait une table de correspondance.
  - `[false]` `[reject]` (blind) Collision de noms des deux `Etape` — les deux noms sont imposés par le spine (AD-8, AD-22).
  - `[low]` `[reject]` (blind) `Literal[1, 2]` répété au lieu d'un alias `Palier` — cosmétique, sans divergence possible (mypy).
  - `[low]` `[reject]` (blind) Clés de ticket en `str` dans plusieurs modèles — le contrôle des Citations est `controler_citations` (AD-14), pas la validation des modèles.
  - `[low]` `[patch]` (blind) Changement de `statut` possible par `modification_champ` — docstring d'`Evenement` : après la création, un changement de statut est une `transition`.
  - `[low]` `[patch]` (blind) `modification_champ` et `alignement` sans effet acceptés — `de == vers` refusé quand les deux sont posés.
  - `[low]` `[patch]` (blind) `AnomalieResume` accepte un statut fermé — statut de `STATUTS_FERMES` refusé.
  - `[low]` `[patch]` (blind) `correspondance_cles` non liée à `cle_projet` — chaque clé Jira doit commencer par `<cle_projet>-` (le nommage `debut_injection` est rejeté : cosmétique).
  - `[low]` `[patch]` (blind) `EvolutionMeteo` n'impose pas les vrais J-1 et J-5 — dates comparées à `jour_ouvre_precedent`, docstring alignée sur les types.
  - `[low]` `[patch]` (blind) Dates de sortie de `Prevision` antérieures à la Date d'arrêté — dates strictement postérieures exigées (constante partagée des règles projetables rejetée : nouvelle surface).
  - `[medium]` `[patch]` (blind) `ConfigJira` incomplet accepté — `champs`, `types_tickets` et `valeurs` doivent couvrir tout le vocabulaire.
  - `[low]` `[reject]` (blind) `FournisseurLLM` sans modèle par tâche ni sémantique d'erreur — la composition construit un adaptateur par modèle (`version_modele` par instance) ; la reprise sur 429 reste dans l'adaptateur (AD-13).
  - `[low]` `[reject]` (blind) Garde du temps sans `date.today()`/`datetime.now()` — la composition lit l'horloge (AD-1) et la convertit par `jour_local` ; ces appels y sont légitimes.
  - `[low]` `[reject]` (blind) Pas de `test_calcul.py`/`test_trace.py`, suite `consultation` partielle — schémas couverts par `test_schemas.py` et `test_inventaire.py`, traces par `test_llm.py`.
  - `[low]` `[patch]` (blind) Espace insécable littéral dans `format.py` — écrit `" "` ; `textes_tickets` et la borne de `limite` rejetés comme cosmétiques.
  - `[low]` `[reject]` (edge) `formater_nombre(10**30, 1)` lève `InvalidOperation` — carried.
  - `[low]` `[reject]` (edge) Double arrondi d'une `Fraction` géante — carried.
  - `[low]` `[reject]` (edge) `chemin_fichier_passage` avec un `datetime` — carried.
  - `[low]` `[reject]` (edge) `former_passage_id` avec un non-`datetime` — paramètre typé, mypy strict l'empêche.
  - `[low]` `[reject]` (edge) `ContextePassage` avec un `passage_id` non `str` — idem.
  - `[low]` `[reject]` (edge) `ManifestePassage.palier` accepte `True` — manifeste écrit par la Chaîne, jamais lu depuis un YAML.
  - `[low]` `[reject]` (edge) Manifeste Palier 1 avec étapes LLM réussies — carried.
  - `[low]` `[reject]` (edge) Sorties Parquet non validées par `ResultatEtape` — même raison que la ligne blind.
  - `[low]` `[reject]` (edge) Enveloppe d'un autre Passage chargée — la vérification d'appartenance revient à `Consultation` (Story 0.6).
  - `[low]` `[reject]` (edge) `Mapping` modifiables dans les modèles gelés — carried.
  - `[low]` `[reject]` (edge) Seuil déjà sous forme de tuple non vérifié — construction programmatique seulement ; le YAML passe par l'analyse.
  - `[low]` `[patch]` (edge) `GrilleMeteo.indicateurs` vide accepté — `min_length=1`.
  - `[low]` `[reject]` (edge) Phases qui se chevauchent — carried.
  - `[low]` `[reject]` (edge) Identifiants Jira qui ne diffèrent que par des blancs — rien ne montre qu'un YAML en contienne.
  - `[low]` `[reject]` (edge) `temperature = inf` — carried.
  - `[low]` `[patch]` (edge) `correspondance_cles` hors projet — même correctif que la ligne blind.
  - `[low]` `[patch]` (edge) J-1/J-5 arbitraires — même correctif que la ligne blind.
  - `[low]` `[patch]` (edge) Date de sortie passée — même correctif que la ligne blind.
  - `[low]` `[reject]` (edge) `RisqueEntreeRouge` hors horizon — carried.
  - `[low]` `[reject]` (edge) `id_appel` vide ou dupliqué — aucun producteur ne le fait ; garde de faible valeur.
  - `[low]` `[reject]` (edge) `limite` ≤ 0 sur le port — un `Protocol` ne valide pas ; les arguments de l'Agent passent par `ArgumentsListAnomalies` (`gt=0`).
  - `[low]` `[reject]` (edge) `FournisseurFactice` exécute avant de refuser — carried.
  - `[low]` `[patch]` (edge) Attribut émis avant la création au même instant — la suite `source_tickets` le vérifie désormais.
  - `[low]` `[reject]` (edge) `tendances()` vide rend un test vacuement vrai — suite non exécutée avant la Story 0.6.

## Design Notes

**Choix de forme (le spine laisse les champs libres jusqu'au gel E0-9).** Taux et seuils toujours en `numerateur`/`denominateur` entiers (`denominateur = 0`, `numerateur > 0` = infini) ; `SCHEMA_KPI` et `SCHEMA_TENDANCE` en format long (`date`, `perimetre` = code d'Entité ou `PROGRAMME`, `code_kpi`, `dimension` (`""` si aucune), `numerateur`, `denominateur`), un compte valant `n/1`. `SCHEMA_INDICATEUR` : `date`, `entite`, `code`, `statut` (`evalue`/`non_evaluable`), `motif` (`""` si évalué), `numerateur`, `denominateur` (`0/0` si non évaluable), `couleur`. `SCHEMA_TICKET_ETAT` : `date`, `cle_ticket`, `type_ticket`, `entite`, `vague`, `domaine`, `gravite`, `phase`, `statut`, `statut_test`, `statut_certification` (nullables selon le type), `date_derniere_entree`. Colonnes `Date` pour les jours, `Datetime("us", "UTC")` pour les instants. Toute colonne dont les valeurs sont une énumération de `contrats` (`type_ticket`, `nature`, `champ`, `source`, `statut`, `gravite`, `phase`, `statut_test`, `statut_certification`, `cause_racine`, `code`, `couleur`, statut d'indicateur) est un `pl.Enum` construit depuis les membres de l'énumération, dans leur ordre de définition : `valider` refuse alors une valeur hors domaine, et `couleur` se trie dans Polars dans l'ordre de gravité `vert < jaune < orange < rouge`. `de` et `vers` restent en `Utf8`, car leur domaine dépend de `champ`. Les codes libres (`entite`, `vague`, `domaine`, `perimetre`, `code_kpi`, `dimension`, `motif`) restent en `Utf8`.

**Contenu des fichiers JSON.** `contrats.passage.CONTENUS_JSON: Mapping[str, type]` associe chaque nom JSON de `FICHIERS_PASSAGE` à son type de contenu (le manifeste est son propre modèle) :
- `meteo` → `tuple[MeteoEntite, ...]` ;
- `previsions` → `ContenuPrevisions(previsions: tuple[Prevision, ...], risques: tuple[RisqueEntreeRouge, ...])`, défini dans `contrats.prevision` ;
- `classification` → `tuple[SortieClassification, ...]` ;
- `explications` → `tuple[SortieExplication, ...]` ;
- `narrations` → `tuple[SortieNarration, ...]`.

`ResultatEtape` vérifie qu'une sortie JSON a le type annoncé. `SCHEMA_SERIE_STOCK` reste un contrat d'entrée de la Baseline, calculé par le domaine : il n'a pas de fichier propre.

**`Evenement`.** `creation` : `champ`, `de`, `vers` à `None`. `transition` : `champ = statut`, `vers` obligatoire et différent de `de`. `modification_champ`, `alignement` : `champ` obligatoire. `champ` doit appartenir à `CHAMPS_PAR_TYPE[type_ticket]` ; `de`/`vers` non nuls appartiennent à `DOMAINES_CANONIQUES[champ]` quand il n'est pas `None` (`entite`, `vague`, `domaine`, `titre`, `description` sont libres).

**`Couleur(StrEnum)`** redéfinit `__lt__`, `__le__`, `__gt__`, `__ge__` sur un rang (`vert=0`… `rouge=3`) et lève `TypeError` face à toute autre valeur (un `NotImplemented` laisserait `str` comparer par l'alphabet), pour que `max()` et `sorted()` suivent la gravité et non l'alphabet. `MeteoEntite` valide : `vert` ⇔ aucune règle, et toutes les règles portent la couleur de la Météo.

**`ContextePassage[C]` et `ResultatEtape`** sont des `@dataclass(frozen=True)`, pas des modèles Pydantic : ils ne sont jamais sérialisés, et `contrats` ne peut pas importer le port `Consultation`. Le port fixe le paramètre : `executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape`. `ContextePassage` : `date_arrete`, `passage_id`, `configuration: ConfigUsine`, `consultation: C` ; `palier` est une propriété qui renvoie `configuration.chaine.palier` (AD-8 : une seule source du Palier), pas un champ. `ResultatEtape` : `statut` (`reussie`/`sautee`), `sorties: Mapping[str, object]` indexées par un nom de `FICHIERS_PASSAGE`, `traces: tuple[EntreeTrace, ...]`.

**Rejeu.** `ManifestePassage.etapes` est un `tuple[ExecutionEtape]` (`etape`, `statut`, `horodatage_debut`, `horodatage_fin`, propriété `duree`) : la durée se déduit de champs déjà dans `EXCLUSIONS_REJEU`, donc le Rejeu compare le manifeste sans liste supplémentaire. `ManifestePassage` porte aussi `contrats_version`, `passage_id`, `date_arrete`, `palier`, `source`, `horodatage_debut`, `horodatage_fin`, `horodatage_extraction` (optionnel), `version_grille`, `version_donnees`, `classification_initiale`, `cout_llm_eur: Decimal`, `nb_alignements`, `nb_tickets`.

**Enveloppes.** `EnveloppeFichier[T]` (générique Pydantic) : `contrats_version`, `passage_id`, `date_arrete`, `contenu: T`. `lire_enveloppe(texte, type_contenu)` lit `contrats_version` avant toute validation et appelle `verifier_version`. Les Parquet porteront la même clé en métadonnée (`CLE_VERSION = "contrats_version"`), écrite par la Story 0.5.

**Ports.**
- `SourceTickets.evenements(depuis: datetime | None = None) -> Iterator[Evenement]`.
- `EntrepotExtraction` : `repere() -> datetime | None`, `enregistrer(evenements, repere) -> int` (atomique, dédoublonné par `id_evenement`), `evenements() -> Iterator[Evenement]`.
- `FournisseurLLM` : propriété `version_modele`, `generer_structure[T: BaseModel](prompt, schema: type[T], parametres) -> ReponseStructuree[T]`, `executer_agent(messages, outils, parametres) -> ReponseAgentBrute`.
- `Pseudonymiseur` : `pseudonymiser(texte) -> str`, `reidentifier(texte) -> str`, `apercu(texte) -> str` (sans écrire la table).
- `Consultation` (lecteur d'un Passage ; `date_arrete=None` = celle du Passage) : `dernier_passage() -> ManifestePassage | None`, `manifeste()`, `dates_disponibles()`, `meteo(date_arrete, entite) -> tuple[MeteoEntite, ...]` (FR-17, FR-43), `evolution_meteo(date_arrete) -> tuple[EvolutionMeteo, ...]` (FR-19), `indicateurs(date_arrete, entite)`, `kpi(date_arrete, entite)`, `instantanes(date_arrete, entite)`, `tendances(entite, code_kpi=None)`, `tickets_etats(date_arrete)`, `textes_tickets()` (tables validées), `anomalies(date_arrete, entite, gravite, phase, domaine, limite: int | None = None) -> ResultatListAnomalies` (`total` compte avant la limite) (FR-26 onglet 5, FR-39), `previsions(date_arrete, entite)`, `risques(date_arrete, entite)` (FR-20, FR-21), `classification(palier)`, `repartition_causes(entite, palier)`, `explications(entite, palier)`, `narrations(entite, palier)` (FR-46 : `palier=1` renvoie vide), `traces()` (FR-34, onglet 9), `url_ticket(cle) -> str | None` (FR-29, `None` en Mode repli). Lectures LLM : `palier: Literal[1, 2] = 2`.
- `Etape.executer(ctx) -> ResultatEtape`.

**Doublures.** `FournisseurFactice(reponses_structurees, reponses_agent, version_modele="factice:modele")` rejoue des réponses scriptées dans l'ordre, enregistre chaque appel dans `appels`, et dans `executer_agent` n'appelle que les outils reçus (outil inconnu scripté : `UsineErreur`). `PseudonymiseurFactice(cle, motifs: Mapping[str, str])` remplace chaque correspondance d'expression régulière par `<TYPE>_<6 hex HMAC-SHA256(cle, valeur)>`, ne touche jamais une clé de ticket (`[A-Z][A-Z0-9]+-\d+`), garde la correspondance en mémoire. Chaque fabrique de suite renvoie l'adaptateur et ses données d'essai (exemples sensibles, réponses scriptées).

**`ConfigJira` (AD-23).** La correspondance Jira → canonique couvre tout le vocabulaire :
- `champs: Mapping[Champ, str]` : identifiants Jira non vides, deux `Champ` ne partagent jamais un même identifiant ;
- `types_tickets: Mapping[str, TypeTicket]` : type de ticket Jira → `TypeTicket` ;
- `valeurs: Mapping[Champ, Mapping[str, str]]` (remplace `statuts`) : valeur Jira → valeur canonique, seulement pour les `Champ` à domaine fermé, chaque valeur canonique validée contre `DOMAINES_CANONIQUES[champ]`.

**Invariants des modèles.** Chaque contrôle est un validateur local, couvert par un test :
- chaque champ `contrats_version` d'un modèle (`ManifestePassage`, `EnteteJournal`, `ManifesteInjection`, `ReponseAgentEnregistree`, `EnveloppeFichier`) passe par `verifier_version` ;
- `RegleDeclenchante` : la valeur franchit réellement le seuil selon l'opérateur (infini compris) ;
- `EvolutionMeteo` : `date_j5 < date_j1 < date_arrete` quand ces dates sont présentes ;
- `Prevision` : dates optimiste, estimée et pessimiste présentes seulement si `sortie_projetee`, et dans l'ordre `optimiste ≤ estimée ≤ pessimiste` ;
- `ResultatListAnomalies` : `total ≥ len(anomalies)` ;
- `ManifesteInjection.correspondance_cles` est injective ;
- `GrilleMeteo.couleurs == tuple(Couleur)` ; `RegleIndicateur.seuils` n'est pas vide ;
- `ConfigLLM.fournisseur` ne contient pas `:`.

**Configuration.** Modèles gelés, `extra="forbid"` (pas `strict`, pour lire dates et décimaux YAML). `GrilleMeteo` suit l'addendum D (`version`, `regle_agregation: Literal["pire_couleur"]`, `garde_fous`, `indicateurs: Mapping[CodeIndicateur, RegleIndicateur]` avec `libelle`, `active`, `seuils: Mapping[Couleur, str]`) ; un seuil `">= 0.20"` est analysé en `(Operateur, Fraction)` à la validation, syntaxe fautive refusée ; la cohérence entre couleurs reste à la Story 3.4. `ConfigUsine` : `chaine` obligatoire, les six autres optionnels (`None` tant que la lane n'a pas livré son YAML).

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check .` -- expected: aucun écart.
- `uv run mypy` -- expected: aucune erreur (strict).
- `uv run lint-imports` -- expected: tous les contrats KEPT.
- `uv run pytest` -- expected: tout vert ; `uv run pytest tests/contrat -v` montre les doublures passer et la suite `consultation` ignorée faute d'adaptateur.

## Auto Run Result

Status: done

**Résumé.** Tous les contrats de la table *Contrats v1* sont définis dans `usine.contrats` (13 modules, plus `modele.py` et `schemas.py`), avec `calendrier`, `format`, `versions` et `valider`. Les six ports sont des `Protocol` dans `usine.ports`. Les doublures `FournisseurFactice`, `PseudonymiseurFactice` et `SourceEnMemoire` sont prêtes, et quatre suites de contrat sont paramétrées par fabrique d'adaptateur. `CONTRATS_VERSION = "0.1.0"`.

**Fichiers.**
- `src/usine/contrats/` : `versions` (empreintes AD-16, contrôle de version majeure) ; `schemas` (`SchemaTable`, `valider`, `enum_polars`) ; `calendrier` (seule source du temps, AD-17) ; `format` (formatage français) ; `tickets` (vocabulaire canonique AD-23) ; `evenements` (`Evenement`, `EnteteJournal`, `ManifesteInjection`) ; `calcul` ; `meteo` (`Couleur` ordonnée, `RegleDeclenchante`, `MeteoEntite`, `EvolutionMeteo`) ; `prevision` (`ContenuPrevisions` compris) ; `llm` ; `agent` ; `trace` ; `passage` (`Etape`, manifeste, enveloppes, `CONTENUS_JSON`, `ContextePassage`, `ResultatEtape`) ; `config` (les six modèles ajoutés et `ConfigUsine`) ; `modele` (base `Enregistrement`, `VersionContrats`) ; `__init__` (façade).
- `src/usine/ports/` : `source_tickets`, `entrepot`, `fournisseur_llm`, `pseudonymiseur`, `consultation`, `etape`, et la façade.
- `tests/doublures/` : les trois doublures. `tests/contrat/` : quatre suites (celle de `consultation` attend la Story 0.6). `tests/unit/contrats/`, `tests/unit/ports/` : matrice I/O, invariants, inventaire. `tests/__init__.py` permet les imports `tests.doublures`.

**Revue.**
- Passe 1 : 61 findings. Une reprise de spec (`bad_spec`) a ajouté les `pl.Enum`, `CONTENUS_JSON`, les lectures `limite` et `code_kpi`, la refonte de `ConfigJira`, le Palier à source unique et les invariants des modèles. 1 élément est différé (exclusions du Rejeu, AD-7) ; les autres sont rejetés avec leur motif dans le journal.
- Passe 2 : 50 findings. 15 lignes `patch` (dont 1 medium : complétude de `ConfigJira`) ont donné 10 correctifs ; les autres sont rejetées avec leur motif dans le journal.
- Écart de procédure : en boucle 1, le retour à la base a été refusé par le classifieur de permissions (opération destructive) ; le code a été amendé en place.

**Revue de suivi.** `false` : aucun correctif `high`, un seul `medium` à la passe 2.

**Vérification.** `uv run ruff check .`, `ruff format --check .`, `mypy` (strict), `lint-imports` (13 contrats KEPT) et `pytest` donnent 514 passés et 11 ignorés : la suite `consultation` n'a pas encore d'adaptateur. Chaque ligne de la matrice I/O est couverte par un test passé.

**Risques résiduels.**
- La suite `consultation` n'a jamais tourné.
- Les exclusions du Rejeu ne couvrent ni les traces ni les coûts (élément différé).
- Plusieurs formes (`SCHEMA_INSTANTANE`, `prevision`, `agent`) sont des propositions à relire au gel E0-9.
- `zoneinfo` repose sous Windows sur `tzdata`, tiré transitivement par pandas.
