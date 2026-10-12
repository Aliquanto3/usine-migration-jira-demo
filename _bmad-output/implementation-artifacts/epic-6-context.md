# Epic 6 Context: Couche LLM sourcée et contrôlée (L6 Couche LLM)

<!-- Version concise, rédigée en run autonome (Story 6.1). Source : epics.md (Epic 6), ARCHITECTURE-SPINE.md (AD-12, AD-13, AD-15, AD-19, AD-20). -->

## Goal

Enrichir le Rapport quotidien (Palier 2) de Causes racines proposées, d'Explications sourcées, de Brouillons de commentaire et d'une narration de la Prévision, pseudonymisés, contrôlés, mis en cache et tracés, sans jamais lier la couche LLM à un fournisseur.

## Périmètre d'écriture (AD-21)

`ia/` sauf `ia/agent`, `domaine/causes`, `adaptateurs/{llm,presidio,pseudonymisation,stockage_sqlite}`, `config/{llm,pseudonymisation}.yaml`, `evals/` sauf `evals/agent`, tests miroirs. `contrats/` et `ports/` sont gelés ; `rendu/` n'est pas touché.

## Décisions qui s'imposent

- **AD-12** : tout appel passe par `ia.passerelle` : Pseudonymisation → cache → `FournisseurLLM` → contrôle → ré-identification → `EntreeTrace`. `pydantic_ai` n'est importé que dans `adaptateurs/llm/`.
- **AD-13** : `generer_structure` (mode Tool Output, schéma `Reponse<Tache>`) et `executer_agent` (`output_type=str`, seuls les outils reçus) ; jamais combinés. Fournisseur et modèle lus dans `config/llm.yaml` : Anthropic d'abord, Mistral ensuite (H-23). Reprise sur 429 (backoff croissant, `Retry-After`, tentatives max en configuration), espacement par modèle et registre des quotas et des prix dans l'adaptateur.
- **AD-15** : jetons `<TYPE>_<6 hex HMAC-SHA256(USINE_CLE_PSEUDO, valeur)>`, clés de ticket jamais remplacées (Story 6.2, lane `lane/6-pseudo`).
- **AD-19** : secrets uniquement en variables d'environnement (`ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `USINE_CLE_PSEUDO`).
- **AD-20** : la suite de contrat `FournisseurLLM` passe pour Anthropic, Mistral (enregistrements) et `FournisseurFactice`.
- Les tests n'appellent jamais les vraies API (faux transports, réponses enregistrées ; `@pytest.mark.reseau` exclu par défaut).

## Ordre des stories

6.1 adaptateurs → 6.2 Presidio → 6.3 passerelle complète (cache, coût, dégradation) → 6.4–6.7 tâches → 6.8–6.9 évaluations → 6.10 recette Palier 2. Démarrage normal après la porte M3 (5.7) ; 6.1 et 6.2 avancées pendant la réinjection Jira car indépendantes des sorties du Palier 1.
