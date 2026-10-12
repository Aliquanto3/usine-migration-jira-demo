# Epic 6 Context: Couche LLM sourcée et contrôlée (L6 Couche LLM)

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Enrichir le Rapport quotidien (Palier 2) de Causes racines proposées, d'Explications sourcées, de Brouillons de commentaire et d'une narration de la Prévision. Chaque appel LLM est pseudonymisé, contrôlé de façon déterministe, mis en cache et tracé, de sorte qu'une banque puisse autoriser un LLM distant sans fuite de données ni invention de chiffres. L'epic démarre après la porte Palier 1 (M3, Story 5.7).

## Stories

- Story 6.1: Adaptateurs Anthropic et Mistral
- Story 6.2: Pseudonymisation par Presidio
- Story 6.3: Passerelle complète, cache, coût et dégradation
- Story 6.4: Classification incrémentale des Causes racines
- Story 6.5: Répartition des Causes racines
- Story 6.6: Explication sourcée et Brouillon de commentaire
- Story 6.7: Narration de la Prévision
- Story 6.8: Suite d'évaluation de l'Explication sourcée
- Story 6.9: Suite d'évaluation de la classification
- Story 6.10: Recette Palier 2
- Story 6.11: [BONUS] Détection de doublons
- Story 6.12: [BONUS] Mode LLM local
- Story 6.13: [BONUS] Observabilité externe

## Requirements & Constraints

- Fournisseur LLM interchangeable par configuration (Anthropic, Mistral) sans modification de code ; clés par variables d'environnement.
- Aucun identifiant sensible ne part vers un LLM : un test de balayage (SM-7) ne doit retrouver aucun identifiant injecté par le générateur dans traces, requêtes (Agent compris) ni Langfuse.
- Rejeu à versions identiques : zéro appel fournisseur, Rapport identique hors exclusions ; un changement de prompt, modèle ou entrée relance l'appel.
- Chaque phrase d'explication cite au moins un ticket réel de l'Entité à la Date d'arrêté ; phrases invalides retirées et comptées ; plus de la moitié retirées, une régénération puis « explication indisponible ». Narration rejetée si elle contient un nombre ou une date absents des valeurs fournies.
- Causes racines : 7 catégories (H-18), affichées comme suggestions, jamais écrites dans Jira ; classification incrémentale (seules les Anomalies nouvelles ou modifiées).
- Cibles de recette : Passage Palier 2 en moins de 10 minutes, coût LLM inférieur à 1 € ; plafond de coût par Passage, dépassement dégradé en libellé explicite ; fournisseur injoignable au démarrage, le Passage échoue en nommant l'étape.
- Évaluations (à la demande, hors CI) : SM-3 = 100 % de Citations valides et note humaine moyenne ≥ 4/5 sur 10 cas ; SM-9 = F1 macro ≥ 0,8 sur la vérité terrain du générateur et séparément sur 30 tickets manuels ; modèle de classification différent de `modele_corpus`.

## Technical Decisions

- Périmètre d'écriture : `ia/` sauf `ia/agent`, `domaine/causes`, `adaptateurs/{llm,presidio,pseudonymisation,stockage_sqlite}`, `config/{llm,pseudonymisation}.yaml`, `evals/` sauf `evals/agent`, tests miroirs. Ne pas toucher `rendu/` (déjà prêt pour les champs Palier 2).
- Les schémas `ReponseClassification` et `ReponseNarration` passent par une PR courte sur `main` en début d'epic (contrats). Les bonus ajoutant une tâche passent aussi par une PR dédiée sur `main`.
- Passerelle unique `ia.passerelle`, ordre imposé : Pseudonymisation de toute l'entrée, cache, port `FournisseurLLM`, contrôle déterministe de la tâche, ré-identification locale, `EntreeTrace`.
- Clé de cache : `(tache, cible, date_arrete, version_prompt, version_modele, empreinte de l'entrée pseudonymisée, tentative)` ; pour la classification, cible = clé du ticket, sans Date d'arrêté. Cache via port `CacheLLM` (SQLite WAL `donnees/cache_llm.sqlite`, valeur `EnveloppeCache`), appelé par la seule passerelle.
- Port `FournisseurLLM` : `generer_structure` (mode Tool Output avec schéma) et `executer_agent` (`output_type=str`, outils reçus) ne se combinent jamais dans un même appel ; `pydantic_ai` uniquement dans `adaptateurs/llm/` (import-linter). Retry sur 429 avec `Retry-After`, puis `UsineErreur`. Suite de contrat commune Anthropic, Mistral, `FournisseurFactice`.
- Pseudonymisation : deux moteurs derrière le port `Pseudonymiseur` : Presidio avec spaCy `fr_core_news_md` (Palier 2) et regex (repli du walking skeleton). Choix par clé de `config/pseudonymisation.yaml`. Jetons dérivés `<TYPE>_<6 hex HMAC-SHA256(USINE_CLE_PSEUDO, valeur)>`, identiques entre moteurs, Passages et worktrees ; grammaire définie une fois dans `contrats.llm`. Clés de ticket (`DEMO-123`) jamais remplacées. Dérivation et table portées par `adaptateurs/pseudonymisation`, réutilisées par `presidio`. Table de ré-identification `donnees/pseudonymes.sqlite` (WAL, ignorée par git) via le `Protocol` local `TablePseudonymes`. `Pseudonymiseur.apercu(texte)` sert l'UI.
- Contrôles déterministes partagés (AD-14) : `controler_citations`, `controler_nombres`. Répartition des Causes racines uniquement par `domaine.causes.repartition` (pure, déterministe, sortie `repartition_causes.parquet`).
- Traçabilité : `EntreeTrace` (horodatage, Date d'arrêté, Entité, quatre versions, fournisseur, entrées pseudonymisées, sortie, contrôles, jetons, `cout_estime_eur`) écrite par la Chaîne dans `trace/llm.jsonl` ; manifeste avec `cout_llm_eur` et `classification_initiale` (premier Passage exclu des mesures NFR-2/NFR-9).
- Seule la suite `evals/` lit la vérité terrain (`donnees/verite_terrain.json`).
- Le modèle spaCy `fr_core_news_md` se télécharge depuis GitHub (accès à ouvrir en environnement bancaire, voir `docs/fiche-outillage.md`).
- Bonus : Mode LLM local via `llama-server` (tag b11552, 8 Go VRAM) ; Langfuse 4.17.0 auto-hébergé, textes pseudonymisés uniquement.

## Cross-Story Dependencies

- Story 6.3 complète la passerelle d'Epic 0 et sert les stories 6.4, 6.6, 6.7 ; 6.4 alimente 6.5, qui alimente 6.6.
- Story 6.2 (Pseudonymisation) précède tout appel réel ; 6.1 et 6.2 sont requis par 6.10.
- Story 6.9 dépend de la Story 1.9 (Corpus définitif et vérité terrain) ; 6.10 utilise la liste d'identifiants injectés de la Story 1.x pour SM-7.
- Les stories 7.7 à 7.12 (Palier 2 de l'UI/Agent) démarrent après cet epic ; la vue côte à côte de la pseudonymisation (Epic 7) consomme `Pseudonymiseur.apercu`.
- Les bonus 6.11 à 6.13 ne démarrent qu'après toutes les stories indispensables.
