---
title: 'Story 0.4 (E0-4) : calcul minimal de la Météo'
type: 'feature'
created: '2026-10-11'
status: 'done'
baseline_revision: 'aae841fd86b2dd19974fc5a2dfbe2e195eb0f321'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-0-context.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Le Journal du mini-générateur existe, mais rien ne le lit, ne reconstitue l'état des tickets ni n'attribue de Météo : la chaîne de calcul n'est pas prouvée de l'événement à la couleur (Story 0.4 de `epics.md`, amorces de FR-8, FR-10, FR-15, FR-16).

**Approach:** Un adaptateur `SourceJournal` lit le Journal JSONL et implémente `SourceTickets`. Des fonctions pures en Polars dans `usine.domaine` calculent ensuite les `TicketEtat`, l'Instantané, l'Indicateur IND-1, puis la Météo, selon une Grille YAML réduite à IND-1 (`config/grille_meteo.yaml`).

## Boundaries & Constraints

**Always:**
- `src/usine/domaine/` n'importe que `usine.contrats` et Polars (contrat import-linter « domaine pur ») : ni I/O, ni horloge, ni hasard. La Date d'arrêté, la Grille et `version_grille` arrivent en paramètre.
- Rattachement des événements aux jours uniquement par `contrats.calendrier.jour_ouvre_de` : l'état en D inclut les événements dont `jour_ouvre_de(horodatage) ≤ D` (AD-17).
- Chaque table sortant du domaine passe par `contrats.valider` avec son `SCHEMA_X` (`SCHEMA_TICKET_ETAT`, `SCHEMA_INSTANTANE`, `SCHEMA_INDICATEUR`).
- Anomalie ouverte = `statut` ∉ `STATUTS_FERMES` ; IND-1 = nombre d'Anomalies ouvertes de gravité `bloquante` de l'Entité, porté `n/1`, statut `evalue`, motif `""`.
- Météo : la couleur la plus grave dont un seuil actif est franchi l'emporte ; vert sinon. La `MeteoEntite` porte toutes les règles de cette couleur avec valeur, seuil et clés en cause (Anomalies ouvertes bloquantes, triées), et `version_grille`.
- Chaque Entité demandée a sa Météo, même sans aucun ticket (vert).
- `SourceJournal` : toute anomalie de lecture (fichier absent ou illisible, en-tête manquant ou invalide, version majeure différente, ligne invalide) devient une `UsineErreur` qui nomme le fichier et, pour une ligne, son numéro.
- `config/grille_meteo.yaml` commenté en français à chaque clé (NFR-10), validé par `GrilleMeteo`.

**Never:**
- Modifier `src/usine/contrats/`, `src/usine/ports/`, `usine.config`, `pyproject.toml`, `uv.lock` ; ajouter une dépendance.
- Calculer IND-2 à IND-8, les KPI, les Tendances, la cohérence de la Grille (FR-18) ou la Source composite : ce sont les lanes L2 et L3.
- Ouvrir un fichier ou lire la configuration depuis `domaine/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Rouge | ENT-A avec 3 Anomalies bloquantes ouvertes en D | Météo rouge, une `RegleDeclenchante` IND-1 : valeur 3/1, seuil `>= 3`, les 3 clés en cause | N/A |
| Orange | ENT-A avec 1 bloquante ouverte | orange, règle IND-1 `>= 1`, 1 clé | N/A |
| Vert | Entité sans bloquante ouverte (majeures ouvertes, bloquante fermée) ou sans aucun ticket | vert, aucune règle, IND-1 = 0/1 | N/A |
| Coupure | bloquante créée samedi 23 h UTC avant le lundi D, ou le jour ouvré D+1 | comptée en D si créée le week-end précédent ; ignorée si créée après D | N/A |
| Fermeture | bloquante passée à `fermee` en D | non comptée en D ; comptée en D-1 | N/A |
| Réouverture | `fermee → en_analyse` | `date_derniere_entree` = jour ouvré de la réouverture | N/A |
| Version | toute Météo | porte la `version_grille` reçue | N/A |
| Indicateur inactif | IND-1 `active: false` | Météo verte | N/A |
| Indicateur non implémenté | Grille avec IND-2 actif | `UsineErreur` qui nomme IND-2 | — |
| Journal absent | chemin inexistant | `UsineErreur` qui nomme le fichier | — |
| Ligne invalide | ligne 5 non conforme à `Evenement` | `UsineErreur` qui nomme le fichier et la ligne 5 | — |
| Autre version majeure | en-tête `contrats_version: "1.0.0"` | `UsineErreur` qui nomme les versions | — |

</intent-contract>

## Code Map

- `src/usine/ports/source_tickets.py` -- `SourceTickets.evenements(depuis=None)` : horodatage croissant, `depuis` inclusif, `depuis` sans fuseau → `UsineErreur`.
- `tests/contrat/source_tickets/fabriques.py` -- liste `FABRIQUES` ; ajouter `("journal", fabrique_journal)` qui écrit `serialiser_journal(generer(config, 42, date(2026, 10, 12)))` dans un répertoire temporaire (`tempfile.mkdtemp`) et rend un `SourceJournal` dessus, avec les événements générés comme attendus.
- `tests/doublures/source_en_memoire.py` -- modèle de filtrage `depuis` et de refus d'un `depuis` naïf.
- `src/usine/generateur/journal.py` -- `generer`, `serialiser_journal` (en-tête puis événements, une ligne JSON chacun) : format à relire.
- `src/usine/contrats/evenements.py` -- `EnteteJournal`, `Evenement`, `evenements_en_table` (→ `SCHEMA_EVENEMENT`).
- `src/usine/contrats/tickets.py:195` -- `SCHEMA_TICKET_ETAT` (colonnes sans objet nulles, `date_derniere_entree`) ; `STATUTS_FERMES`, `Gravite`, `TypeTicket`.
- `src/usine/contrats/calcul.py` -- `SCHEMA_INSTANTANE` (comptes par `date`, `entite`, `type_ticket`, `vague`, `phase`, `gravite`, `statut`) et `SCHEMA_INDICATEUR` (`couleur` en `pl.Enum` ordonné).
- `src/usine/contrats/meteo.py` -- `RegleDeclenchante` (vérifie le franchissement), `MeteoEntite` (vert ⇔ aucune règle), `Couleur`, `CodeIndicateur`, `Operateur`.
- `src/usine/contrats/config.py` -- `GrilleMeteo` (`version`, `regle_agregation`, `garde_fous` obligatoire, `indicateurs` → `RegleIndicateur.seuils` analysés en `(Operateur, Fraction)`).
- `src/usine/contrats/calendrier.py` -- `jour_ouvre_de`, `est_jour_ouvre`.
- `src/usine/contrats/versions.py` -- `version_grille(octets)` (appelée par les tests ; la Story 0.5 l'appellera dans la composition).
- `tests/unit/contrats/test_config.py` (`test_yaml_livres_en_e0`) -- ajouter `grille_meteo.yaml` à la liste attendue.
- `tests/unit/config/test_commentaires.py` -- vérifie déjà les commentaires de tout YAML livré.

## Tasks & Acceptance

**Execution:**
- `src/usine/adaptateurs/journal/__init__.py` -- `SourceJournal(chemin: Path)` : lit le fichier (UTF-8) et valide l'en-tête (`EnteteJournal`, propriété `entete`) puis chaque ligne (`Evenement`) ; `evenements(depuis)` rend les événements dans l'ordre du fichier, filtrés `≥ depuis` -- FR-8.
- `src/usine/domaine/instantanes.py` -- `tickets_etats(evenements, dates) -> pl.DataFrame` (`SCHEMA_TICKET_ETAT`, une ligne par ticket créé au plus tard en D, pour chaque D de `dates`) et `instantane(tickets_etats) -> pl.DataFrame` (`SCHEMA_INSTANTANE`) -- FR-10.
- `src/usine/domaine/meteo.py` -- `indicateurs(tickets_etats, date_arrete, entites, grille) -> pl.DataFrame` (`SCHEMA_INDICATEUR`, une ligne par Entité et par indicateur actif ; `couleur` = couleur franchie) et `meteo(tickets_etats, date_arrete, entites, grille, version_grille) -> tuple[MeteoEntite, ...]` (ordre des `entites`) ; un indicateur actif autre qu'IND-1 → `UsineErreur` -- FR-15, FR-16.
- `config/grille_meteo.yaml` -- version réduite commentée : `version: 1`, `regle_agregation: pire_couleur`, `garde_fous` (20 et 5, PRD), `indicateurs.IND-1` : libellé, `rouge: ">= 3"`, `orange: ">= 1"`.
- `tests/contrat/source_tickets/fabriques.py` -- fabrique `journal`.
- `tests/unit/adaptateurs/journal/test_source_journal.py`, `tests/unit/domaine/test_instantanes.py`, `tests/unit/domaine/test_meteo.py` -- matrice I/O, avec des événements construits à la main et sur le Journal généré (graine 42).
- `tests/unit/contrats/test_config.py` -- `grille_meteo.yaml` dans la liste des YAML livrés.

**Acceptance Criteria:**
- Given `uv run pytest tests/contrat/source_tickets`, when la suite tourne, then `SourceJournal` passe chaque test de la suite.
- Given le Journal généré (graine 42, 2026-10-12) et la Grille livrée, when le domaine calcule la Météo à la Date d'injection pour ENT-A et ENT-B, then chaque `MeteoEntite` valide son contrat, et sa couleur égale celle qu'on déduit du nombre de bloquantes ouvertes compté directement sur les événements.
- Given le dépôt, when `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest`, then tout passe.

## Spec Change Log

## Review Triage Log

### 2026-10-11 — Review pass
- verdicts: 27 findings — high 0, medium 5, low 19, false 3, maybe-false 0
- findings:
  - `[medium]` `[patch]` (verification-gap) Date d'arrêté absente des `TicketEtat` → tout vert en silence — `UsineErreur` qui nomme la date, testée.
  - `[low]` `[patch]` (intention) Chaîne non prouvée de bout en bout (fichier → `SourceJournal` → Météo) — `test_journal_genere` passe par le fichier, `SourceJournal`, la Grille livrée et `version_grille`.
  - `[low]` `[reject]` (intention) L'Instantané ne nourrit pas l'Indicateur — l'Instantané ne porte que des comptes et ne peut pas fournir les clés en cause ; les deux viennent des mêmes `TicketEtat`.
  - `[low]` `[reject]` (intention) Rattachement aux jours et seuils calculés en Python — `jour_ouvre_de` est la seule source (AD-17) et les seuils se comparent en `Fraction` (AD-10) ; le domaine reste pur.
  - `[false]` `[reject]` (intention) Ajouts hors intention (doublons, horodatage décroissant, IND-2 refusé) — ce sont les promesses du port et la limite IND-1 de la story.
  - `[medium]` `[patch]` (blind) `splitlines` coupe une ligne JSON valide sur U+2028 — découpe sur `\n` seulement, testée avec U+2028, U+0085 et `\x0b`.
  - `[medium]` `[patch]` (blind) Date d'arrêté absente → tout vert — même correctif.
  - `[false]` `[reject]` (blind) Valeur inconnue → erreur Polars brute au `cast` — `Evenement` refuse toute valeur hors domaine pour les champs fermés ; les champs libres restent en `Utf8`.
  - `[low]` `[patch]` (blind) Choix de la couleur écrit deux fois — `meteo` passe par `_couleur_franchie` ; égalité des couleurs entre `indicateurs` et `meteo` testée.
  - `[low]` `[reject]` (blind) Cas `denominateur == 0` de `_franchit` — sémantique de l'infini fixée par AD-10 et `RegleDeclenchante` ; inatteignable pour IND-1.
  - `[low]` `[patch]` (blind) Fuite de répertoires temporaires — `atexit.register(shutil.rmtree, …)`.
  - `[low]` `[patch]` (blind) Test d'acceptation potentiellement vide — au moins une Entité non verte et clés en cause comparées.
  - `[low]` `[reject]` (blind) Oracle à seuils codés en dur — l'oracle compte les bloquantes ; les couleurs viennent de la Grille chargée.
  - `[false]` `[reject]` (blind) Réouverture par `modification_champ` non comptée — le contrat d'`Evenement` (Story 0.2) impose une `transition` pour tout changement de statut après la création.
  - `[low]` `[reject]` (blind) Recalcul complet par date — mesure de performance en Story 0.5 (NFR-2) ; optimisation à la demande.
  - `[low]` `[reject]` (blind) `_verifier_entites` quadratique, liste vide acceptée — deux à dix Entités ; une liste vide donne un résultat vide cohérent.
  - `[low]` `[reject]` (blind) Deux notions de version dans la Grille — `version_grille` (empreinte) fait foi (AD-16) ; `couleurs` est déjà validé par `GrilleMeteo`.
  - `[low]` `[reject]` (blind) Petites remarques de test (`reversed` sur un élément, BOM, erreur `depuis` paresseuse) — le Journal est écrit par le générateur, jamais à la main ; sans conséquence.
  - `[low]` `[patch]` (edge) U+2028 et `splitlines` — même correctif.
  - `[low]` `[reject]` (edge) `depuis` d'un autre type que `datetime` — paramètre typé, mypy strict.
  - `[medium]` `[patch]` (edge) Date d'arrêté absente → tout vert — même correctif.
  - `[low]` `[reject]` (edge) Bloquante au `statut` nul — toute Anomalie reçoit son statut initial à la création (AD-3).
  - `[low]` `[patch]` (edge) Dates en double → comptes doublés — `UsineErreur` qui nomme la date.
  - `[low]` `[reject]` (edge) Événements sans création écartés — le Journal crée toujours avant de modifier (AD-3) ; la Source composite de L2 traitera les sources réelles.
  - `[low]` `[reject]` (edge) Réouverture avec `de=None` — le générateur et les adaptateurs renseignent `de` pour une transition.
  - `[low]` `[reject]` (edge) `version_grille` vide → `ValidationError` — appel interne, échec bruyant.
  - `[low]` `[patch]` (edge) Répertoire temporaire jamais supprimé — même correctif.

## Design Notes

**`tickets_etats`.** Construire d'abord une table d'événements (`evenements_en_table`, plus une colonne `jour` = `jour_ouvre_de(horodatage)` calculée en Python sur chaque événement), puis, pour chaque D, garder `jour ≤ D`, trier par `(horodatage, rang dans le flux)` et prendre par ticket et par champ la dernière valeur `vers` (`group_by(...).last()`, ou un pivot). `date_derniere_entree` = jour de la création, ou de la dernière transition qui sort de `STATUTS_FERMES`. Les colonnes d'énumération sont converties vers les `pl.Enum` du schéma avant `valider`. Les colonnes sans objet pour le type restent nulles.

**Météo.** Pour chaque Entité, on parcourt les couleurs de la plus grave à la moins grave (`sorted(Couleur, reverse=True)`, sans `vert`). La première couleur dont le seuil d'IND-1 est franchi (`Operateur` appliqué à `Fraction(valeur)`) donne la `RegleDeclenchante` (`seuil_numerateur`/`seuil_denominateur` tirés de la `Fraction`). Si aucun seuil n'est franchi, l'Entité est verte. La validation de `RegleDeclenchante` revérifie le franchissement.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check .` -- expected: aucun écart.
- `uv run mypy` -- expected: aucune erreur.
- `uv run lint-imports` -- expected: tous les contrats KEPT (domaine pur).
- `uv run pytest` -- expected: tout vert ; la suite `source_tickets` passe pour `journal`.

## Auto Run Result

Status: done

**Résumé.** `SourceJournal` lit le Journal JSONL et passe la suite de contrat `SourceTickets`. Le domaine pur, en Polars, calcule les `TicketEtat` (coupure par `jour_ouvre_de`), l'Instantané, l'Indicateur IND-1 et la Météo selon la Grille réduite `config/grille_meteo.yaml`. Chaque `MeteoEntite` porte ses Règles déclenchantes et `version_grille`.

**Fichiers.**
- `src/usine/adaptateurs/journal/__init__.py` : `SourceJournal`.
- `src/usine/domaine/instantanes.py` : `tickets_etats`, `instantane`.
- `src/usine/domaine/meteo.py` : `indicateurs`, `meteo`.
- `config/grille_meteo.yaml` : Grille réduite commentée.
- `tests/contrat/source_tickets/fabriques.py` : fabrique `journal`.
- `tests/unit/adaptateurs/journal/`, `tests/unit/domaine/` : matrice I/O et chaîne fichier → couleur.
- `tests/unit/contrats/test_config.py` : liste des YAML livrés.

**Revue.** 27 findings : 11 lignes `patch` (4 medium, regroupées en 2 causes : découpe des lignes, date absente) donnant 6 correctifs, 0 différé, 16 rejetées avec leur motif.

**Revue de suivi.** `true` : deux causes `medium` corrigées. Risque non vérifié : la garde « Date d'arrêté absente » refuse aussi une date pour laquelle les `TicketEtat` ont bien été calculés, mais où aucun ticket n'existe encore. La composition de la Story 0.5 doit garantir que la Date d'arrêté figure parmi les dates calculées et porte des tickets, ou bien cette garde doit s'appuyer sur la liste des dates calculées.

**Vérification.** ruff, ruff format, mypy, lint-imports (domaine pur KEPT) et pytest donnent 648 passés et 11 ignorés.

**Risques résiduels.**
- `tickets_etats` recalcule tout pour chaque date ; la performance sera mesurée en Story 0.5 (NFR-2).
- Un `tickets_etats` vide n'est pas contrôlé par la garde de date.
