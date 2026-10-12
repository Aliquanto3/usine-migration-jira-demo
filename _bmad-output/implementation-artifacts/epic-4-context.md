# Epic 4 Context: Prévision de sortie du rouge (L4 Prévision)

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Donner au Pilote, pour chaque Entité rouge, une date estimée de sortie du rouge (avec fourchette, probabilité et facteurs explicatifs), et signaler les Entités non rouges qui risquent d'y entrer. La Prévision est purement statistique et déterministe, jamais produite par un LLM. Pour échapper à la circularité des données synthétiques, la même Baseline est évaluée sur des données Jira réelles publiques (Public Jira Dataset, Zenodo) et comparée à une prévision naïve. Un Modèle ML explicable vient en bonus.

## Stories

- Story 4.1 : Prévision de sortie du rouge par Baseline
- Story 4.2 : Risque d'entrée en rouge
- Story 4.3 : Conversion du Public Jira Dataset en SerieStock
- Story 4.4 : Évaluation de la Baseline sur données réelles
- Story 4.5 : Recette de la Prévision sur les Scénarios de démo
- Story 4.6 : [BONUS] Modèle ML validé sur données réelles
- Story 4.7 : [BONUS] Facteurs explicatifs du Modèle ML

## Requirements & Constraints

- **Baseline de sortie du rouge** (Entité rouge par IND-1, Anomalies bloquantes ouvertes, seuil rouge ≥ 3) :
  - vélocité nette v = (Sorties − Entrées) de bloquantes, moyenne par Jour ouvré sur les 10 derniers Jours ouvrés ; horizon de 10 Jours ouvrés ; les deux en configuration ;
  - date de sortie = premier Jour ouvré où le stock projeté S − v·t passe sous le seuil rouge d'IND-1 ;
  - fourchette = vélocités au 25ᵉ et 75ᵉ centile des fenêtres glissantes de 5 Jours ouvrés sur les 20 derniers Jours ouvrés ;
  - probabilité = part des fenêtres de vélocité historiques de l'Entité qui ramènent le stock sous le seuil dans l'horizon (empirique, sans modèle) ;
  - facteurs explicatifs : stock courant, Entrées et Sorties sur 10 Jours ouvrés, vélocité nette et sa variation par rapport aux 10 Jours ouvrés précédents.
- Vélocité nulle ou défavorable : « pas de sortie projetée », sans date.
- Une date n'est produite que si toutes les Règles déclenchantes rouges sont projetables ; sinon « règle non projetable : IND-x » pour toute règle autre qu'IND-1 (ex. IND-5, Certifications refusées).
- **Risque d'entrée en rouge** (Entité non rouge) : régression linéaire sur 10 Jours ouvrés d'IND-1, IND-3 et IND-4, projetée à 5 Jours ouvrés ; signalé si une projection franchit un seuil rouge, avec l'indicateur et la valeur projetée. Un IND-4 non évaluable sur une partie de la fenêtre est exclu, avec le motif restitué.
- **Évaluation sur données réelles** : unité = couple (projet, date) où le stock de tickets de priorité maximale ouverts dépasse un seuil, dates échantillonnées chaque semaine ; cible = stock sous le seuil dans les N = 10 Jours ouvrés suivants. Prédicteurs : référence naïve (taux historique de la cible sur le projet), Baseline, Modèle ML (bonus). Découpage temporel (test sur les périodes les plus récentes) puis projets tenus à l'écart. Mesures publiées dans le dépôt : score de Brier, AUC, erreur absolue moyenne sur le stock projeté.
- **Critères de succès** : la Baseline bat la naïve en score de Brier (hypothèse ; si ce n'est pas le cas, publier tel quel et signaler l'écart à l'auteur, sans retoucher la Baseline pour l'évaluation). En fin d'historique des Scénarios de démo : A sort dans l'horizon, B ne sort pas, C est signalée en Risque d'entrée en rouge. Tout écart se corrige dans le générateur, jamais en réglant la Baseline ou la Grille sur les Scénarios.
- **Bonus ML** : probabilité de résolution d'une bloquante sous N Jours ouvrés ; doit battre la Baseline en AUC et Brier sur le jeu tenu à l'écart ; agrégation Entité P(sortie) = P(au moins k bloquantes résolues sous N jours), k = stock − (seuil − 1), indépendance supposée et documentée ; anticipe A et B ; au plus 5 facteurs en français lisibles par le Pilote. Un gain d'AUC qui rend les facteurs illisibles n'est pas retenu. Aucune story bonus avant la fin des stories indispensables.
- Aucun chiffre de Prévision n'est calculé par un LLM ; la narration LLM (Epic 6) ne reprend que les valeurs calculées ici.

## Technical Decisions

- **Une seule Baseline** : implémentée une fois dans `domaine.prevision.baseline` sur le contrat `SerieStock` (stock, Entrées, Sorties par Jour ouvré). `evaluation/zenodo` convertit le dataset en `SerieStock` et appelle cette même fonction, sans copie ni variante. Le Modèle ML produit le même contrat `Prevision` avec `methode=ml` (Baseline : `methode=baseline`).
- **Contrats** : `SerieStock`, `Prevision`, `RisqueEntreeRouge`, `FacteurExplicatif` vivent dans `contrats.prevision` (`SCHEMA_SERIE_STOCK` / Pydantic `frozen`). `contrats/` et `ports/` ne se modifient que sur `main` par PR dédiée.
- **Domaine pur** : calculs en Polars, fonctions pures sans I/O, horloge ni hasard ; DuckDB ne calcule rien ; rendu, UI et Agent ne font qu'afficher via `consultation`.
- **Nombres exacts** : comptes entiers, taux en numérateur/dénominateur, comparaisons de seuil en `Fraction`, statut `non_evaluable` explicite.
- **Temps** : `contrats.calendrier` est la seule source des Jours ouvrés (Europe/Paris, `jour_ouvre_de`, Fenêtre glissante) ; les `SerieStock` sont en Jours ouvrés.
- **Paramètres** (vélocité, horizons) dans la configuration de la Chaîne, propriété de `main` : toute clé manquante passe par une PR courte. Seuils lus depuis la Grille de météo (L3).
- **Intégration Chaîne** : étape `prevision` entre `meteo` et `classification` ; Prévisions et Risques publiés dans `previsions.json` et tracés dans `trace/previsions.jsonl` (versions prompt/modèle/Grille/données, `passage_id`) ; sorties couvrant chaque Jour ouvré ≤ Date d'arrêté ; rendu déterministe pour le Rejeu idempotent.
- **Zenodo** : lecture du dump avec pymongo 4.18.3 ; spike d'une demi-journée en début de lane, procédure documentée dans `evaluation/zenodo/`. `evaluation/` est hors CI ; un test unitaire couvre la conversion sur un petit extrait figé. Aucun réseau dans les tests unitaires.
- **ML (bonus)** : LightGBM 4.7.0 ; facteurs par contributions de variables (`pred_contrib`) ; ajouter SHAP passe par une PR sur `main`.
- **Périmètre d'écriture de la lane** : `domaine/prevision`, `evaluation/` et les `tests/unit/` correspondants uniquement.

## Cross-Story Dependencies

- 4.1 et 4.2 consomment les sorties de l'Epic 3 (Indicateurs IND-1/3/4/5, Météo, Règles déclenchantes, Grille).
- 4.3 → 4.4 (les `SerieStock` Zenodo alimentent l'évaluation) ; 4.4 réutilise la Baseline de 4.1 telle quelle.
- 4.5 exige la Story 1.8 (calage des Scénarios de démo) et l'Epic 3 terminés.
- 4.6 réutilise le protocole de 4.4 ; 4.7 dépend de 4.6.
- En aval : Epic 5 affiche Prévisions et Risques (Excel, PowerPoint) ; Epic 6 narre la Prévision (FR-24) ; Epic 7 expose `get_prevision` / `get_risques` à l'Agent et le détail d'Entité.
