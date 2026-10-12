---
title: 'Story 5.3 : Classeur Excel en 9 onglets'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '06b5249eceaa20852758ace8bfa629431e73ab48'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-5-context.md'
warnings: ['multiple-goals', 'oversized']
deferred:
  - summary: >-
      Déclarer Traçabilité!B5 (horodatage d'extraction) et Traçabilité!B8 (version des données) sous EXCLUSIONS_REJEU["rapport_xlsx"] avant le Rejeu de la Story 5.5.
    evidence: |-
      Le classeur affiche deux champs exclus du Rejeu au manifeste. En source composite, deux Passages de mêmes données donneront des classeurs différents sur ces deux cellules. La déclaration modifie contrats/passage.py, gelé : contrats v1.1. Consigné aussi dans deferred-work.md.
    location: >-
      src/usine/rendu/excel.py (_tracabilite), src/usine/contrats/passage.py (EXCLUSIONS_REJEU)
    severity: medium
---

<intent-contract>

## Intent

**Problem:** Le classeur du Rapport n'a qu'un onglet (Synthèse minimale, Story 0.6) : le Pilote doit encore retraiter ses chiffres à la main. En amont, l'étape `prevision` est toujours un bouchon : un Passage réel n'a ni Prévision ni Risque. La Synthèse ne peut donc pas les afficher, et `()` ne distingue pas « Prévision non calculée » de « aucun Risque » (constat de la 5.2).

**Approach:** Tâche préalable : brancher l'étape `prevision`. Le domaine construit la `SerieStock` de chaque Entité depuis l'état des tickets du Passage. `chaine` applique la Baseline aux Entités rouges et les Risques aux autres, sur chaque Jour ouvré du Passage. La composition câble le tout avec les paramètres par défaut du domaine (H-7, H-8). Story : `rendu/excel.py` produit les 9 onglets de H-9, nombres formatés par `contrats.format`, clés liées par `url_ticket`. Les mentions Palier 1 et les sorties Palier 2 lues via `Consultation`. Un test compare chaque valeur chiffrée aux lectures de `Consultation`.

## Boundaries & Constraints

**Always:** le rendu ne calcule rien : il lit via `Consultation` (et le contexte transmis par la Chaîne : Palier, Grille, identité des données) et formate. Le rendu reste déterministe (propriétés et archive fixées, ordre stable). Une `SerieStock` est dense : une ligne par Entité et par Jour ouvré du Passage. Elle vérifie `stock(j) = stock(j−1) + entrées(j) − sorties(j)`, avec un stock égal à IND-1 (Anomalies bloquantes ouvertes de l'Entité). Les Prévisions couvrent chaque Jour ouvré ≤ D (AD-7), chacune tracée (`trace/previsions.jsonl`). Palier 1 : onglet Commentaires et colonne Cause racine portent « commentaire non généré (Palier 1) ». Toute clé de ticket affichée est un lien `url_ticket` quand il existe. Tout en français.

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` (gelés). Mettre H-7 ou H-8 en configuration : story dédiée avec les contrats v1.1. Toucher le PowerPoint au-delà de ce qu'exige la nouvelle signature d'`EtapeRendu` (Story 5.4). Écrire un fichier du Rapport ailleurs que par l'`EcrivainPassage`. Ajouter au lecteur `ConsultationPassage` une méthode publique hors port.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Série nominale | états des tickets sur 3 Jours ouvrés : une bloquante ouverte J1, une seconde J2, la première fermée J3, une majeure passée bloquante J3 | stock 1, 2, 2 ; entrées 1, 1, 1 ; sorties 0, 0, 1 | Aucune |
| Transfert d'Entité | bloquante ouverte passe de ENT-A à ENT-B | sortie ENT-A, entrée ENT-B le même jour | Aucune |
| Jour sans ticket | Jour ouvré du Passage sans aucun état | ligne à 0/0/0 pour chaque Entité | Aucune |
| Passage réel | Journal graine 42, D = 2026-10-09, ENT-A et ENT-B rouges | `previsions.json` publié : une Prévision Baseline par Entité rouge et par Jour ouvré, des Risques pour les non rouges ; une trace par élément | Aucune |
| Entité non rouge sans Risque | Passage publié, étape `prevision` réussie | Synthèse : « Aucun Risque d'entrée en rouge » | Aucune |
| Prévision non calculée | manifeste sans étape `prevision` réussie, ou Entité rouge sans Prévision | « Prévision non calculée » | Aucune |
| Palier 1 | Passage réel Palier 1 | onglet Commentaires et colonne Cause racine : « commentaire non généré (Palier 1) » | Aucune |
| Palier 2 (fixture) | `llm/*.json` et `repartition_causes.parquet` écrits | Explications, Brouillons « brouillon IA, à valider », répartition, Citations liées | Aucune |
| Mode repli | `url_jira=None` | clés affichées sans lien | Aucune |
| Passage vide | répertoire sans fichier | 9 onglets, en-têtes seuls, sans erreur | Aucune |

</intent-contract>

## Code Map

- `src/usine/domaine/prevision/baseline.py` -- `prevoir_sortie(serie, meteo, ParametresBaseline())` : exige une Météo rouge et une série dense finissant à D (`_jours`), lève si le stock ne déclenche pas la règle IND-1 rouge. Lecture seule.
- `src/usine/domaine/prevision/risque.py` -- `risques_entree_rouge(indicateurs, meteo, grille, ParametresRisque())` : exige une Météo non rouge ; rend `ResultatRisque(risques: tuple[RisqueProjete], exclus)` ; `.risque` donne le `RisqueEntreeRouge` du contrat. Valide toute la table à chaque appel : lui passer les lignes de l'Entité seulement. Lecture seule.
- `src/usine/domaine/meteo.py:197` -- `_anomalies_ouvertes` : définition d'IND-1 (anomalie, gravité bloquante, statut non nul hors `STATUTS_FERMES`) à reproduire pour le stock.
- `src/usine/contrats/prevision.py` -- `SCHEMA_SERIE_STOCK`, `Prevision`, `RisqueEntreeRouge`, `ContenuPrevisions` (gelés).
- `src/usine/chaine/etapes.py` -- `EtapePrevision(prevoir, version_donnees, horloge)`, alias `Prevoir` ; `EtapeKpi` lit déjà `tickets_etats` jour par jour (modèle de lecture).
- `src/usine/composition.py:342-351` -- registre : `Etape.prevision: EtapeBouchon()` à remplacer, `EtapeRendu(gabarit)` à enrichir ; `empreinte_donnees`, `horodatage_extraction`, `horloge`, `grille`, `entites`, `premier_jour` y sont déjà calculés. Docstring du module (l. 29-33) à mettre à jour.
- `src/usine/consultation/passage.py:435-459` -- docstrings `previsions`/`risques` (bouchon) à mettre à jour.
- `src/usine/rendu/excel.py`, `rendu/commun.py`, `rendu/etape.py` -- onglet unique actuel, `formater_regle`, `tickets_en_cause`, `archive_deterministe`, `EtapeRendu`.
- `src/usine/contrats/format.py` -- `formater_entier`, `formater_fraction`, `formater_pourcentage`, `formater_date`.
- `src/usine/contrats/tickets.py:171` `LIBELLES` (gravité, phase, statuts, Causes racines) ; `contrats/meteo.py:55` `LIBELLES_COULEURS` ; `GrilleMeteo.indicateurs[code].libelle/seuils/active`.
- `src/usine/domaine/kpi.py:36-85` -- codes KPI et dimensions (`taux_*` en %, `age_*` en Jours ouvrés, le reste en comptes) ; `rendu` ne peut pas importer `domaine` : libellés recopiés dans `rendu`.
- `tests/unit/rendu/conftest.py` -- fixtures `passage`, `passage_repli`, `passage_sans_jira`, `passage_jaune_rouge`.
- `tests/contrat/consultation/fabriques.py:163` -- `_completer_palier_2` : modèle d'écriture des fichiers Palier 2 pour la fixture du rendu.
- `tests/unit/consultation/test_passage.py:174,508-521` et `tests/unit/chaine/test_execution.py` -- assertions « bouchon » à mettre à jour.

## Tasks & Acceptance

**Execution:**
- `src/usine/domaine/prevision/serie.py` (hors lane) -- `series_stock(tickets_etats, entites, jours) -> DataFrame` au `SCHEMA_SERIE_STOCK`, dense, flux par transition d'un Jour ouvré au précédent (le premier jour, comparé à un ensemble vide). Ajouter le module à la docstring du paquet.
- `tests/unit/domaine/prevision/test_serie.py` (hors lane) -- matrice : série nominale, transfert, jour sans ticket, gravité changée, fermeture, identité stock/flux, stock = IND-1 sur un Passage réel.
- `src/usine/chaine/etapes.py` -- `prevision_du_passage(grille, entites, premier_jour) -> Prevoir` : lit `tickets_etats`, `meteo`, `indicateurs` de chaque Jour ouvré, construit les séries, appelle `prevoir_sortie` (rouges) ou `risques_entree_rouge` (autres) avec les paramètres par défaut, ordre jour puis ordre de `meteo.json`.
- `src/usine/composition.py` (hors lane) -- `Etape.prevision: EtapePrevision(prevision_du_passage(...), empreinte_donnees, horloge)` ; `EtapeRendu(gabarit, donnees, horodatage_extraction)` ; docstrings (module, `horloge`).
- `src/usine/consultation/prevision.py` -- `EtatPrevision` (`prevision`, `risque`, `aucun_risque`, `non_calculee`), `previsions_calculees(manifeste)`, `etat_prevision(consultation, entite, date_arrete, calculees)`.
- `src/usine/consultation/passage.py` -- docstrings `previsions`/`risques` : absence = Passage antérieur au câblage.
- `src/usine/rendu/commun.py` -- `ContexteRendu` (palier, grille, source, versions, horodatage d'extraction, `previsions_calculees`) et `depuis_manifeste(manifeste, grille)` ; formatage d'une mesure, d'une Prévision, d'un Risque, d'un horodatage ; libellés des KPI ; mention Palier 1.
- `src/usine/rendu/excel.py` -- 9 onglets dans l'ordre H-9 (voir Design Notes) ; signature `rendre_excel(consultation, date_arrete, contexte)`.
- `src/usine/rendu/etape.py` -- `EtapeRendu(gabarit, donnees, horodatage_extraction)` construit le `ContexteRendu` depuis `ctx` (Palier, Grille) ; `previsions_calculees=True` (l'étape `prevision` précède le rendu, AD-8).
- `tests/unit/rendu/test_excel.py`, `conftest.py` -- ordre et noms des onglets ; test SM-1 par onglet (chaque cellule = formatage de la lecture `Consultation`) ; Palier 1 ; fixture Palier 2 ; liens (normal, Mode repli, sans Jira) ; Traçabilité = manifeste ; Passage vide ; déterminisme.
- `tests/unit/consultation/test_prevision.py`, `tests/unit/consultation/test_passage.py`, `tests/unit/chaine/test_etapes.py`, `tests/unit/chaine/test_execution.py`, `tests/unit/test_composition.py` -- états de Prévision ; Passage réel avec `previsions.json` égal à un appel direct du domaine, traces, Prévisions par Jour ouvré.

**Acceptance Criteria:**
- Given un Passage publié par `lancer_rapport`, when on ouvre `rapport-<D>.xlsx`, then ses onglets sont, dans l'ordre : Synthèse, Météo détaillée, KPI, Tendances, Anomalies ouvertes, Tests, Certifications, Commentaires, Traçabilité.
- Given ce classeur et `ConsultationPassage` sur le même Passage, when le test compare chaque cellule chiffrée au formatage `contrats.format` de la valeur lue, then l'égalité est stricte dans les 9 onglets (SM-1).
- Given ce Passage Palier 1, when on lit l'onglet Commentaires et la colonne Cause racine, then ils portent « commentaire non généré (Palier 1) ».
- Given la fixture Palier 2 (`llm/*.json`, `repartition_causes.parquet`, manifeste en Palier 2), when on lit l'onglet Commentaires et la colonne Cause racine, then ils affichent Explications, Brouillons « brouillon IA, à valider », répartition des Causes racines, Causes racines proposées et Citations liées.
- Given une clé de ticket dans une cellule, when on l'inspecte, then son lien vaut `url_ticket(cle)` ; en Mode repli, aucun lien.
- Given le registre de `composition.py`, when un Passage s'exécute, then `previsions.json` égale l'appel direct de `prevoir_sortie`/`risques_entree_rouge` sur les séries du Passage, et la Synthèse affiche Prévision, Risques ou « Aucun Risque d'entrée en rouge » selon l'Entité.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 29 findings — high 0, medium 7, low 13, false 8, maybe-false 1
- findings:
  - `[medium]` `[patch]` (intent) distinction « non calculée » / « aucun Risque » livrée hors port, impossibilité consignée seulement en docstring — consignée durablement dans `deferred-work.md` (contrats v1.1 : bouchon ancien, `exclus` absent de `ContenuPrevisions`).
  - `[low]` `[reject]` (intent) `SerieStock` lue dans `tickets_etats` plutôt que dans les Instantanés — les Instantanés n'ont pas les flux de bloquantes ; choix justifié (Design Notes), stock = IND-1 vérifié sur Passage réel.
  - `[false]` `[reject]` (intent) nombres en texte et SM-1 par égalité de texte — l'AC exige le formatage par `contrats.format` (espace insécable, virgule) ; `test_commun.py` fige les phrases de `formater_prevision`, `formater_risque`, `formater_regle` par des littéraux.
  - `[low]` `[reject]` (intent) forme de l'onglet Tests (Vague en plus, taux en bloc séparé), colonnes en plus — imposé par « aucun calcul dans le rendu » (le compte OK n'existe qu'aux Instantanés) ; colonnes ajoutées sans perte.
  - `[low]` `[reject]` (blind) version des contrats tirée de la constante, nombre de tickets recompté — le rendu n'a lieu que dans la Chaîne, où la constante est celle du Passage ; le recompte est la lecture même du manifeste, comparée par `test_tracabilite_egale_le_manifeste`.
  - `[low]` `[reject]` (blind) `depuis_manifeste` accepte une Grille d'une autre version — fonction de test seulement ; aucun rendu hors Chaîne en production.
  - `[low]` `[reject]` (blind) `previsions_calculees` vrai par défaut et figé dans `EtapeRendu` — état inatteignable (le registre câble toujours `EtapePrevision`, un échec arrête le Passage) ; documenté.
  - `[false]` `[reject]` (blind) une Prévision en erreur sur un jour passé arrête le Passage — stock = IND-1 par construction (même filtre, testé), Météo et séries sur les mêmes Entités : l'erreur n'est pas atteignable, l'échec bruyant est voulu.
  - `[low]` `[reject]` (blind) filtre d'IND-1 dupliqué dans `serie.py` — la règle de `domaine/meteo` est privée (lane L3) ; `test_passage_reel_identite_et_ind1` fige l'égalité.
  - `[low]` `[reject]` (blind) Entrées du premier jour gonflées — comparaison à un ensemble vide voulue (identité stock/flux) ; n'affecte que la première fenêtre de vélocité de l'historique.
  - `[low]` `[reject]` (blind) tests qui rejouent le domaine, pas de test d'invariance par préfixe — la Baseline et le Risque ne lisent que les lignes ≤ D, et les flux ne dépendent que de j−1 et j ; garde sans défaut démontré.
  - `[low]` `[patch]` (blind) assertion faible `"rouge" in ligne[5]` — égalité stricte avec `formater_prevision` de chaque Prévision lue, ordre des Entités vérifié.
  - `[medium]` `[patch]` (blind) états incohérents lus « non calculée » ou « aucun Risque » — groupé avec le premier constat : consigné dans `deferred-work.md`.
  - `[medium]` `[defer]` (blind) Rejeu composite du classeur cassé jusqu'à la 5.5 — déclaration sous `EXCLUSIONS_REJEU["rapport_xlsx"]` impossible sans contrats v1.1 ; consigné (`deferred`, `deferred-work.md`).
  - `[low]` `[reject]` (blind) IND-8 en « % » plutôt qu'en points ; opérateur absent du Risque — cosmétique ; `RisqueEntreeRouge` ne porte pas l'opérateur (contrat gelé).
  - `[false]` `[reject]` (blind) narrations absentes, PowerPoint sans Prévision, libellés KPI mal couverts — H-9 ne met pas les narrations dans l'onglet Commentaires ; PowerPoint = Story 5.4 ; `CODES_TENDANCE` contient `CODES_KPI`, le test couvre donc tous les codes.
  - `[low]` `[reject]` (blind) `_largeurs` au-delà de Z, O(n²) sur les Entités, double lecture, coût en jours² — 8 colonnes au plus, 10 Entités, lectures en cache, 1,1 s mesurée sur le Programme complet.
  - `[medium]` `[patch]` (verification) instant d'extraction composite jamais relu dans le classeur publié — `test_passage_composite_de_bout_en_bout` lit Traçabilité : Source « composite » et horodatage = `formater_horodatage(INSTANT)`.
  - `[medium]` `[patch]` (verification) Rejeu sans `previsions.json` ni `trace/previsions.jsonl` — `test_passage_publie_et_rejeu` compare les deux, exclusions `trace_previsions` retirées.
  - `[low]` `[patch]` (verification) docstring de `test_registre_prevision_et_rendu` trop large — reformulée sur ce que le test vérifie.
  - `[false]` `[reject]` (edge) aucun Jour ouvré entre ancrage et D — `jours_du_passage` rend toujours D (vérifiée ouvrée) ou lève une `UsineErreur`.
  - `[false]` `[reject]` (edge) écrasement dans le pivot des Instantanés — Cas de test sans gravité, Certifications sans Phase ni gravité (`CHAMPS_PAR_TYPE`) : une seule ligne par combinaison d'axes et statut.
  - `[maybe-false]` `[reject]` (edge) Cas de test ou Certification sans statut omis — à vérifier : un adaptateur Jira peut-il produire un statut nul ; si oui, effet low (comptes sans statut absents de l'onglet).
  - `[low]` `[reject]` (edge) `previsions_calculees` figé à vrai — même constat que le blind, état inatteignable.
  - `[false]` `[reject]` (edge) `n/0` négatif affiché « sans objet » — aucun Indicateur évalué ni KPI n'a un dénominateur nul avec numérateur négatif (IND-8 est une fraction réduite de dénominateur > 0).
  - `[false]` `[reject]` (edge) horodatage naïf — `Horodatage` du contrat et l'horloge de la composition sont en UTC avec fuseau.
  - `[medium]` `[defer]` (edge) Rejeu des cellules B5/B8 — même cause que le constat blind, consigné.
  - `[false]` `[reject]` (edge, claim) SM-1 réutilise le code testé — les phrases sont figées par des littéraux dans `test_commun.py` et `test_prevision_ou_risque`.
  - `[medium]` `[patch]` (edge, claim) bouchon ancien et indicateurs écartés lus « aucun Risque » — groupé avec le premier constat : consigné.

## Design Notes

**Contenu des onglets.** Synthèse : Entité, Météo J, J-1, J-5 (`evolution_meteo`, « non couverte » si `None`), Règles déclenchantes, Prévision ou Risque, puis une clé en cause par colonne (liée). Météo détaillée : une ligne par Indicateur de `indicateurs(D)` : Entité, code, libellé de la Grille, statut, valeur (« ∞ » si x/0), couleur, seuils de la Grille (« Jaune ≥ 3 ; Rouge ≥ 10 »), motif si non évaluable. KPI : `kpi(D)` en format long (Périmètre, KPI, Dimension, Valeur). Tendances : `tendances()` pivotées, une colonne par semaine. Anomalies ouvertes : bloquantes puis majeures de `anomalies(D, gravite=…, palier=…)`. Tests : bloc 1, Instantanés des Cas de test pivotés (Entité, Vague, Phase × OK, KO, Non exécuté) ; bloc 2, taux de KO et de non-exécution du KPI par périmètre et Phase. Certifications : Instantanés pivotés (Entité, Vague × statut). Commentaires : Palier 2 seulement. Traçabilité : libellé / valeur à lignes fixes.

**Aucun calcul dans le rendu.** Le compte OK n'existe pas au KPI : on le lit dans les Instantanés, sans soustraction. Une combinaison absente d'un Instantané (table creuse) vaut 0 ticket. Le nombre de tickets de Traçabilité est `tickets_etats(D).height`, la même lecture que le manifeste (`execution.py`) ; le test le compare à `manifeste().nb_tickets`.

**Prévision non calculée.** Le port gelé rend `()` dans les deux cas. Après ce câblage, toute étape `prevision` réussie écrit `previsions.json` (un échec arrête le Passage). Le manifeste distingue donc une étape réussie (calculée) d'une étape sautée ou absente (non calculée), via `previsions_calculees`. Pendant la construction, le rendu suit l'étape `prevision` (AD-8) : `True`. Deux cas restent impossibles sans changer les contrats (à consigner) : les Passages publiés avec l'ancien bouchon (manifeste « réussie », sans fichier), et une Entité non rouge dont tous les indicateurs projetés sont écartés (`ResultatRisque.exclus` n'a pas de place dans `ContenuPrevisions`).

**SerieStock depuis les états des tickets.** Les Instantanés et le KPI n'ont pas les flux de bloquantes (`entrees_jour` porte toutes les gravités et ignore les changements de gravité). Les flux sont donc des transitions de l'ensemble des bloquantes ouvertes de l'Entité, et l'identité stock/flux tient par construction. C'est un calcul : il va au domaine.

**Fichiers hors lane.** `src/usine/domaine/prevision/serie.py`, `tests/unit/domaine/prevision/test_serie.py` (L4) : le calcul de la série est du domaine (AD-9, AD-18), la Chaîne n'en fait aucun. `src/usine/domaine/prevision/__init__.py` (docstring du paquet). `src/usine/composition.py` et `tests/unit/test_composition.py` : seule la composition construit le registre (AD-22), et ses tests vérifient le câblage.

**Rejeu.** L'onglet Traçabilité affiche `horodatage_extraction` et `version_donnees`, exclus du Rejeu au manifeste. Leur déclaration sous `EXCLUSIONS_REJEU["rapport_xlsx"]` (`Traçabilité!B<n>`) exige les contrats v1.1 : à consigner pour la Story 5.5.

## Verification

**Commands:**
- `uv run pytest -q tests/unit/rendu tests/unit/chaine tests/unit/consultation tests/unit/domaine/prevision tests/unit/test_composition.py tests/contrat` -- expected: tout passe
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout passe

## Auto Run Result

Status: done

**Résumé.** L'étape `prevision` est câblée. `domaine.prevision.serie.series_stock` construit la `SerieStock` dense de chaque Entité depuis l'état des tickets du Passage. Le stock suit la définition d'IND-1, et les flux sont les transitions de l'ensemble des bloquantes ouvertes. `chaine.etapes.prevision_du_passage` applique, pour chaque Jour ouvré, la Baseline aux Entités rouges et les Risques aux autres, avec les paramètres par défaut du domaine (H-7, H-8). La composition l'injecte dans `EtapePrevision` : chaque Passage publie désormais `previsions.json` et `trace/previsions.jsonl`.

`usine.consultation.prevision` distingue « Prévision non calculée » de « aucun Risque » sans toucher au port. Elle lit l'étape `prevision` au manifeste (`previsions_calculees`) ; pendant le rendu, cette étape précède toujours le rendu (AD-8). Deux cas restent indiscernables sans les contrats v1.1, et sont consignés dans `deferred-work.md` : les Passages publiés avec l'ancien bouchon, et une Entité non rouge dont tous les indicateurs projetés sont écartés.

Le classeur compte les 9 onglets de H-9, dans l'ordre. Chaque nombre est formaté par `contrats.format`, chaque clé est liée par `url_ticket`. En Palier 1, les mentions « commentaire non généré (Palier 1) » figurent dans l'onglet Commentaires et la colonne Cause racine. En Palier 2, l'onglet affiche Explications, Brouillons « brouillon IA, à valider », répartition des Causes racines et Citations liées. Traçabilité est alimenté par l'identité des données transmise par la composition.

**Fichiers modifiés.**
- `src/usine/domaine/prevision/serie.py` (nouveau, hors lane) : `series_stock`.
- `src/usine/domaine/prevision/__init__.py` (hors lane) : docstring.
- `src/usine/chaine/etapes.py` : `prevision_du_passage`.
- `src/usine/composition.py` (hors lane) : `EtapePrevision` et `EtapeRendu(gabarit, donnees, horodatage_extraction)` au registre.
- `src/usine/consultation/prevision.py` (nouveau) : `EtatPrevision`, `previsions_calculees`, `etat_prevision`.
- `src/usine/consultation/passage.py` : docstrings de `previsions`/`risques`.
- `src/usine/rendu/commun.py` : `ContexteRendu`, `depuis_manifeste`, libellés, formatage (mesures, seuils, Prévision, Risque, horodatage).
- `src/usine/rendu/excel.py` : les 9 onglets.
- `src/usine/rendu/etape.py` : `EtapeRendu` construit le `ContexteRendu`.
- Tests : `tests/unit/domaine/prevision/test_serie.py` (hors lane), `tests/unit/consultation/test_prevision.py`, `tests/unit/rendu/test_commun.py` (nouveaux) ; `tests/unit/rendu/test_excel.py`, `conftest.py`, `tests/unit/chaine/test_etapes.py`, `test_execution.py`, `test_cli.py`, `tests/unit/consultation/test_passage.py`, `tests/unit/test_composition.py` (hors lane).
- `_bmad-output/implementation-artifacts/deferred-work.md` : câblage de la 5.1 marqué résolu ; contrats v1.1 consignés.

**Revue.** 29 constats : 0 high, 7 medium, 13 low, 8 false, 1 maybe-false.
- Correctifs appliqués, 5 entrées :
  - impossibilité de la distinction consignée durablement (medium) ;
  - classeur composite relu de bout en bout (medium) ;
  - Rejeu étendu à `previsions.json` et `trace/previsions.jsonl` (medium) ;
  - assertion stricte de la Synthèse (low) ;
  - docstring d'un test de composition (low).
- Différé : déclaration de `Traçabilité!B5`/`B8` sous `EXCLUSIONS_REJEU["rapport_xlsx"]` (contrats v1.1, avant la Story 5.5).
- Rejetés, avec leur motif dans le Review Triage Log :
  - états inatteignables (`previsions_calculees` figé, erreur de Prévision, `n/0` négatif, horodatage naïf, jours vides) ;
  - choix justifiés : source de la série, forme de l'onglet Tests, Entrées du premier jour, texte formaté ;
  - cosmétique : IND-8 en %, largeurs de colonnes ;
  - hors périmètre : PowerPoint (5.4), narrations hors H-9.

**Revue de suivi recommandée : oui.** Trois entrées medium corrigées. Risque nommé et non vérifié : le jeu d'essai à 2 Entités (graine 42) n'a ni Entité non rouge à la Date d'arrêté ni Risque. La branche « Risque d'entrée en rouge » de la Synthèse n'est donc prouvée que par des fixtures écrites à la main, et la branche Baseline `sortie_projetee` que par des séries synthétiques. Après l'intégration des Scénarios calés (Story 1.8, sur `main`), une revue devrait vérifier ces branches sur un Passage réel (A et B rouges, C orange avec Risque).

**Vérification.** `ruff check`, `ruff format --check`, `mypy` (241 fichiers), `lint-imports` (13 contrats) et `pytest -q` passent après correctifs : 1895 réussis, 1 ignoré, 22 désélectionnés. Mesure sur le Programme complet (10 Entités, 3 384 tickets) : étape `prevision` 1,1 s, `rendu` 0,4 s.

**Risques résiduels.**
- Rejeu des Passages composites : les cellules B5 et B8 de Traçabilité diffèrent tant que les contrats v1.1 ne les excluent pas.
- Les deux cas « aucun Risque » indiscernables, consignés.
- Libellés choisis sans spécification : IND-4 et IND-8 en %, « non proposée », « sans extraction Jira », « aucun appel LLM ».
