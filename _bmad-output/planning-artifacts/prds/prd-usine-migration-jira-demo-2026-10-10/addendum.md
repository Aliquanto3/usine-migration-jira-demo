# Addendum au PRD : éléments techniques et matière pour l'architecture

Ce fichier conserve ce qui ne relève pas du PRD (le « comment ») mais doit nourrir `bmad-architecture`. Source : spec v0.2, §§ 4, 8, 9 et 11.

## A. Stack pressentie (spec § 4, non contractuelle)

| Brique | Choix pressenti |
|---|---|
| Langage, dépendances | Python 3.12, `uv` |
| Stockage, calcul | DuckDB + Polars |
| Grille de météo | YAML + moteur de règles maison |
| Prévision | scikit-learn / LightGBM, `lifelines` en option, SHAP |
| LLM | Interface unique, sorties structurées Pydantic. Référence : couche fournisseurs du dépôt voisin `agentic-harness-training-demo` (adaptateurs OpenAI Chat et Anthropic Messages, catalogue de modèles, espacement des appels, compression Headroom). Alternative : LiteLLM |
| Pseudonymisation | Microsoft Presidio, avec reconnaisseurs pour les identifiants bancaires fictifs |
| Agent | Pydantic AI ou LangGraph, outils `get_meteo`, `list_anomalies`, `get_tendance`, `get_prevision` (+ `get_risques` pour FR-21) |
| Facteurs explicatifs du Modèle ML (bonus) | SHAP |
| Secrets | Variables d'environnement, fichier `.env.example` sans valeur, `gitleaks` ou équivalent en CI |
| Version de Grille | Empreinte SHA-256 du fichier YAML |
| Restitution | openpyxl, python-pptx, Streamlit |
| Évaluation, observabilité | pytest, Inspect AI ou promptfoo ; Langfuse auto-hébergé (bonus) |
| LLM local (bonus) | llama.cpp, modèle quantifié tenant dans 8 Go de VRAM |

## B. Adaptateurs Jira

- **Cloud v3** : recherche JQL paginée par `nextPageToken`, authentification e-mail + jeton API, changelog via `expand=changelog` ou endpoint dédié si le changelog est tronqué.
- **Data Center v2** : pagination `startAt` / `maxResults`, authentification par jeton personnel (PAT). Testé sur fixtures JSON enregistrées.
- Requête incrémentale : `updated >= "<dernier passage>"` avec une marge de recouvrement (quelques minutes) et dédoublonnage par clé, pour absorber les décalages d'horloge.
- Sélection de l'adaptateur par configuration (question 4 du § 11 de la spec, distincte de Q-4 du PRD).

## C. Historique et Source composite (FR-5, FR-8, FR-49 ; décision Q-1)

L'API REST Jira ne permet ni d'antidater la création d'un ticket ni d'antidater une transition. Décision : le Journal d'événements porte les 8 semaines d'historique ; Jira Cloud reçoit l'état courant à la Date d'injection, puis les mises à jour faites en direct.

- Source composite : événements du Journal jusqu'à la Date d'injection incluse, changelog Jira strictement après. Jira fait foi sur l'état courant.
- Test de cohérence : à la Date d'injection, Instantané(Journal) == Instantané(état Jira).
- Clés de ticket : créer les tickets dans un ordre déterministe sur un projet vierge pour obtenir des clés stables ; à défaut, table de correspondance clé générée → clé Jira.
- Calendrier : le générateur produit des dates relatives (semaine 1, jour 1, etc.), ancrées sur le dernier Jour ouvré écoulé à la date de génération ; régénérer et réinjecter avant chaque démo.
- Corpus de textes : généré une fois (par un LLM différent du classifieur des Causes racines), stocké en JSON versionné ; la graine sélectionne et affecte les textes.

Options écartées : import CSV Jira (couvre la création, pas l'historique des statuts) ; champ personnalisé « date d'effet » (déforme le modèle Jira réel, donc l'argument de portabilité).

## D. Exemple de Grille de météo en YAML (illustratif)

```yaml
version: 1
couleurs: [vert, jaune, orange, rouge]   # ordre de gravité croissante
regle_agregation: pire_couleur
garde_fous:
  ind4_min_tests_executes: 20
  ind7_min_entrees_fenetre_glissante: 5
indicateurs:
  IND-1:
    libelle: "Anomalies bloquantes ouvertes"
    seuils: { rouge: ">= 3", orange: ">= 1" }
  IND-2:
    libelle: "Âge de la plus ancienne bloquante ouverte (jours ouvrés)"
    seuils: { rouge: "> 10", orange: "> 5" }
  IND-4:
    libelle: "Taux de KO des cas de test exécutés, phase en cours"
    seuils: { rouge: ">= 0.20", orange: ">= 0.10", jaune: ">= 0.05" }
  # ...
```

## E. Baseline de prévision (détail de FR-20, FR-21, FR-51)

- Vélocité nette v = (Sorties − Entrées) d'Anomalies bloquantes, moyenne par Jour ouvré sur les 10 derniers Jours ouvrés.
- Date de sortie = premier Jour ouvré où le stock projeté S − v·t passe sous le seuil rouge d'IND-1.
- Fourchette : vélocités au 25ᵉ et 75ᵉ centile des fenêtres glissantes de 5 Jours ouvrés sur les 20 derniers Jours ouvrés.
- Probabilité de sortie dans l'horizon : part des fenêtres de vélocité historiques de l'Entité qui ramènent le stock sous le seuil dans l'horizon (estimation empirique, sans modèle).
- Facteurs explicatifs : stock courant, Entrées et Sorties sur 10 Jours ouvrés, vélocité nette et sa variation par rapport aux 10 Jours ouvrés précédents.
- Risque d'entrée en rouge : régression linéaire sur 10 Jours ouvrés d'IND-1, d'IND-3 et d'IND-4, projetée à 5 Jours ouvrés.

### Protocole d'évaluation sur le Public Jira Dataset (FR-51, FR-22)

- Unité : couple (projet, date) où le stock de tickets de priorité maximale ouverts dépasse un seuil ; dates échantillonnées chaque semaine.
- Cible : le stock passe sous le seuil dans les N = 10 Jours ouvrés suivants.
- Prédicteurs comparés : référence naïve (taux historique de la cible sur le projet), Baseline (probabilité empirique ci-dessus), Modèle ML (bonus).
- Découpage temporel : entraînement et calibrage sur le passé, test sur les périodes les plus récentes ; projets tenus à l'écart en second test.
- Mesures : score de Brier, AUC, erreur absolue moyenne sur le stock projeté.
- Agrégation Entité pour le Modèle ML (FR-22) : P(sortie) = P(au moins k bloquantes résolues sous N jours), k = stock − (seuil − 1), en supposant l'indépendance des tickets (limite assumée et documentée).

## F. Données publiques (FR-51 indispensable, FR-22 bonus)

Public Jira Dataset, Université de Hambourg : 16 instances Jira publiques, 2,7 M tickets, historiques de changements, données anonymisées : <https://zenodo.org/doi/10.5281/zenodo.5882881>. Cible : résolution d'un ticket de priorité maximale sous N jours ; comparaison à la Baseline en AUC et score de Brier.

## G. Correspondance avec l'outillage cible

Reprendre tel quel le tableau de la spec § 8 dans la fiche FR-47.
