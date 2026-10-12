# Epic 3 Context: Météo calculée et justifiée (L3 Calcul)

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Donner au Pilote, pour chaque Entité et pour le Programme, à n'importe quelle Date d'arrêté de l'historique, des Instantanés, des KPI quotidiens, des Tendances hebdomadaires et une Météo calculée par règles (vert, jaune, orange, rouge), avec les Règles déclenchantes et leurs tickets en cause. La Météo n'est plus déclarée mais calculée de façon déterministe, auditable (rattachée à sa version de Grille) et prouvée exacte par une réconciliation à 100 % avec un Rapport de référence fait à la main. C'est le socle chiffré dont dépendent la Prévision (Epic 4), le Rapport quotidien (Epic 5) et le calage des Scénarios de démo (Epic 1).

## Stories

- Story 3.1 : Instantanés quotidiens complets
- Story 3.2 : KPI quotidiens
- Story 3.3 : Tendances hebdomadaires
- Story 3.4 : Grille de météo complète et validation
- Story 3.5 : Indicateurs de météo IND-1 à IND-8
- Story 3.6 : Météo et Règles déclenchantes
- Story 3.7 : Évolution de la Météo à J-1 et J-5
- Story 3.8 : Rapport de référence et réconciliation à 100 %

## Requirements & Constraints

- **Instantané** : un par Entité pour toute Date d'arrêté de l'historique ; ne dépend que des événements dont le Jour ouvré est ≤ la date (ajouter des événements postérieurs ne le change pas).
- **KPI quotidiens** (par Entité et Programme) : stock d'Anomalies ouvertes par Gravité et par Phase ; Entrées et Sorties du jour et sur la Fenêtre glissante ; âge médian et maximum des Anomalies ouvertes en Jours ouvrés depuis la **dernière Entrée** (une réouverture remet l'âge à zéro) ; taux de KO et de non-exécution des Cas de test par Phase ; Certifications par statut.
- **Définitions** : Anomalie ouverte = statut ni Fermée ni Rejetée (statuts : Nouvelle, En analyse, En correction, À retester, Fermée, Rejetée). Entrée = création ou réouverture (Fermée/Rejetée → autre). Sortie = passage à Fermée ou Rejetée. Fenêtre glissante = 5 derniers Jours ouvrés, Date d'arrêté comprise. Jour ouvré = lundi à vendredi, sans férié. Phase en cours = Phase du calendrier de la Vague de l'Entité contenant la Date d'arrêté ; Vague en cours = Vague de l'Entité.
- **Tendances** : 8 semaines, chaque semaine porte la valeur du dernier Jour ouvré et les Entrées/Sorties cumulées ; la semaine en cours est partielle et prend la valeur de la Date d'arrêté.
- **Grille par défaut** (fictive) :

| Indicateur | Rouge | Orange | Jaune |
|---|---|---|---|
| IND-1 Bloquantes ouvertes | ≥ 3 | ≥ 1 | — |
| IND-2 Âge de la plus ancienne bloquante ouverte (J. ouvrés) | > 10 | > 5 | — |
| IND-3 Majeures ouvertes | ≥ 20 | ≥ 10 | ≥ 5 |
| IND-4 Taux de KO des Cas de test exécutés, Phase en cours | ≥ 20 % | ≥ 10 % | ≥ 5 % |
| IND-5 Certifications refusées (Vague en cours) | ≥ 1 | — | — |
| IND-6 Certifications réservées (Vague en cours) | — | ≥ 2 | ≥ 1 |
| IND-7 Ratio Entrées / Sorties bloquantes + majeures, Fenêtre glissante | — | > 1,5 | > 1,0 |
| IND-8 Hausse d'IND-4 vs J-5 (points) | — | ≥ +5 | ≥ +3 |

- **Garde-fous de volume** (en configuration) : IND-4 évalué à partir de 20 Cas de test exécutés ; IND-7 à partir de 5 Entrées sur la Fenêtre glissante (0 Sortie avec Entrées suffisantes = ratio infini) ; IND-8 seulement si IND-4 évaluable aux deux dates. Un indicateur non évaluable apparaît comme tel et ne change pas la couleur.
- **Météo** : la couleur la plus grave déclenchée l'emporte ; vert sans Règle déclenchante ; sans état d'un jour à l'autre (pas d'hystérésis). Restituer **toutes** les Règles déclenchantes de la couleur retenue avec valeur mesurée, seuil franchi et tickets en cause : IND-1/2/3 → Anomalies ouvertes concernées ; IND-4/8 → Cas de test KO de la Phase en cours ; IND-5/6 → Certifications ; IND-7 → Anomalies entrées et sorties sur la Fenêtre glissante.
- **Grille en YAML** commentée en français (chaque clé), modifiable sans code (seuils, garde-fous, activation de chaque règle). Validation au chargement : refus d'un orange plus sévère que le rouge, d'un indicateur ou d'une couleur inconnus ; message nommant fichier, règle et valeur fautive.
- **Évolution** : Météo de J-1 et J-5 (Jours ouvrés) avec drapeau de changement ; au premier Jour ouvré de l'historique, J-1 est explicitement absent (jamais une couleur par défaut).
- **Réconciliation** : jeu réduit figé (~2 Entités, ~60 tickets, 1 Date d'arrêté) qui fait jouer chacun des 8 Indicateurs et chacun des garde-fous, au moins une fois déclenché et une fois non évaluable ; égalité stricte sur 100 % des valeurs.
- **Déterminisme** : deux calculs sur le même flux donnent des DataFrames identiques, ordre des lignes compris (base du Rejeu idempotent). Aucun chiffre produit par un LLM.

## Technical Decisions

- **Domaine pur** : tout le calcul vit dans `domaine/{instantanes,kpi,meteo}`, en Polars, par fonctions pures ; pas d'I/O, d'horloge ni de hasard ; imports permis : `contrats` + pydantic, polars, stdlib (sans `io`, `os`, `pathlib`, `random`, `time`, `uuid`…). Vérifié par import-linter en CI. DuckDB, rendu, UI et Agent ne recalculent rien.
- **Périmètre d'écriture de la lane** : `domaine/{instantanes,kpi,meteo}`, `config/grille_meteo.yaml`, `tests/fixtures/reference`, et les `tests/unit/` miroirs. `contrats/` et `ports/` sont gelés (`contrats-v1`) : toute modification passe par une PR dédiée sur `main`.
- **Contrats consommés/produits** : flux d'`Evenement` (dédoublonné par `id_evenement`) → `TicketEtat` (état par ticket et par Jour ouvré) → `Instantane`, `Kpi`, `Indicateur`, `Tendance` (`contrats.calcul`, constantes `SCHEMA_<NOM>`, validées par `valider()`) → `MeteoEntite`, `RegleDeclenchante`, `EvolutionMeteo` (`contrats.meteo`, Pydantic gelé). Grille chargée en `GrilleMeteo` (`contrats.config`) dans `usine.config` seulement. Vocabulaire canonique (`Champ`, statuts, `Gravite`) dans `contrats.tickets` ; tri des clés via `rang_cle`.
- **Nombres exacts** : comptes entiers ; taux et ratios en colonnes `numerateur`/`denominateur` entières, jamais de flottant ; comparaisons en `fractions.Fraction` sur le seuil YAML converti depuis sa forme décimale (`0.20` → `Fraction` exacte) ; `denominateur = 0` avec `numerateur > 0` = infini. Indicateur : `statut` ∈ {evalue, non_evaluable} + `motif`, jamais NaN ni `None` comme valeur.
- **Temps** : `contrats.calendrier` est la seule source (Europe/Paris, `jour_local`, `jour_ouvre_de`, Fenêtre glissante, J-1, J-5, `semaine_programme(d, ancrage)` avec ancrage pris dans `EnteteJournal.ancrage_semaines`, passé par l'appelant). Un Instantané en D inclut les événements dont `jour_ouvre_de` ≤ D. Horodatages en `datetime` UTC avec fuseau.
- **Versions** : `version_grille` = SHA-256 des octets de `grille_meteo.yaml` (12 hex), défini dans `contrats.versions` ; chaque `MeteoEntite` le porte.
- **Énumérations** : `Couleur` ordonnée `vert < jaune < orange < rouge` ; `CodeIndicateur` = `IND-1`…`IND-8`.
- **Erreurs** : exceptions dérivées de `UsineErreur`, messages en français nommant fichier, clé/règle, valeur.
- **Rapport de référence** : mini-Journal JSONL + YAML de valeurs attendues au même format (entiers, fractions) dans `tests/fixtures/reference/`.
- **Fichiers du Passage concernés** (écrits par `chaine`, pas par le domaine) : `tickets_etats.parquet`, `instantanes.parquet`, `kpi.parquet`, `indicateurs.parquet`, `meteo.json`, `tendances.parquet`. Étapes `instantanes`, `kpi`, `meteo` dans l'ordre figé de la Chaîne.
- **Tests** : aucun appel réseau, Jira ou LLM en tests unitaires ; test de propriété pour l'indépendance aux événements futurs.

## Cross-Story Dependencies

- Ordre interne : 3.1 (Instantanés) → 3.2 (KPI) → 3.3 (Tendances) et 3.5 (Indicateurs, avec 3.4 Grille) → 3.6 (Météo) → 3.7 (Évolution) ; 3.8 réconcilie l'ensemble.
- En amont : Epic 0 (contrats v1 gelés, ébauche d'Instantané et de Météo minimale déjà sur `main`). Les flux réels viennent de L1 (générateur, Journal) et L2 (extraction) ; avant leur recette, travailler sur contrats, doublures et fixtures.
- En aval : L4 (Prévision, Risque d'entrée en rouge sur IND-1/3/4) et L5 (Rapport, Consultation) dépendent de L3. La Story 1.8 (calage des Scénarios A, B, C au jour près avec la Grille par défaut) et la recette de la Prévision (Story 4.5) attendent L3. L'appariement J-1/J-5 et l'âge en Jours ouvrés peuvent aussi être dérivés à la lecture par `Consultation` (L5), sans valeur publiée.
