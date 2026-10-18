# Ce qu'il faut pour le faire en vrai

Quel outillage demander au client, dans quel ordre, et comment chaque brique se porte sur chaque cible.

## Demandes, par ordre de priorité

1. **Compte de service Jira en lecture seule + jeton API.** Indispensable pour le palier 1.
2. **Environnement d'exécution Python** (VM ou Dataiku) avec accès réseau à Jira, plus un dépôt Git interne.
3. **Ordonnanceur et cible de publication** (SharePoint ou partage réseau).
4. **Endpoint LLM validé par le client.** Palier 2. À défaut, modèle on-prem.

## Correspondance par brique

| Brique | Serveur / VM Python | Dataiku | Power Platform | Poste local seul | Appui dans le dépôt |
|---|---|---|---|---|---|
| Extraction Jira | ✅ | ✅ recette Python | ✅ connecteur Jira (limité sur le changelog et les volumes) | ✅ | AD-19 : Cloud ou Data Center est la clé `mode` de `config/jira.yaml` (chargeur de `usine.config`), jeton par variable d'environnement (gitleaks) |
| KPI, météo | ✅ | ✅ recettes et scénarios | ⚠️ possible, peu maintenable | ✅ | AD-1 : domaine sans I/O (`lint-imports`) ; NFR-8 : CI Windows et Linux |
| Prévision ML | ✅ | ✅ (Visual ML) | ❌ | ✅ | AD-1 : domaine sans I/O ni `random`, graine passée en paramètre (`lint-imports`) ; NFR-8 : CI Windows et Linux |
| LLM | ✅ endpoint validé | ✅ LLM Mesh | ✅ AI Builder / Copilot Studio | ⚠️ modèle local uniquement | AD-1 : un seul port LLM, fournisseur branché dans `composition.py`, pseudonymisation avant tout appel dans la passerelle `usine.ia` (`lint-imports`) ; AD-19 : clés, dont `USINE_CLE_PSEUDO`, par variable d'environnement (gitleaks) |
| Excel / PPT | ✅ | ✅ | ✅ | ✅ | NFR-8 : fichiers produits sans service propriétaire (CI Windows et Linux) |
| Agent conversationnel | ✅ | ✅ (agents Dataiku) | ✅ Copilot Studio | ✅ | AD-1 : l'agent passe par le port LLM (`lint-imports`) |
| Planification | ✅ cron | ✅ scénarios | ✅ Power Automate | ⚠️ poste allumé | AD-19 : une commande, `usine rapport`, paramétrée par `config/*.yaml` (chargeur de `usine.config`) |
| UI de démo (FastAPI + HTML statique) | ✅ | ⚠️ webapp Dataiku « standard » (HTML/JS + backend Python) : l'API FastAPI se réécrit en backend Flask, à vérifier | ❌ à refaire en Power Apps ; les pages statiques ne se portent pas telles quelles | ✅ | AD-1, AD-25 : `usine.ui` n'importe aucun adaptateur (`lint-imports`) |

La colonne « Appui » donne la règle et son contrôle ; ils s'appliquent déjà à toutes les briques, y compris celles en cours de construction (extraction Jira, Prévision, adaptateurs LLM, Agent).

## Points d'attention par cible

### VM Python

- Ouvrir le flux vers Jira (proxy, certificats TLS), un miroir PyPI interne pour `uv sync` et l'accès GitHub au modèle spaCy `fr_core_news_md`, vérifier les projets visibles du compte de service, poser les secrets en variables d'environnement (AD-19, gitleaks).
- Le code livré tourne sans adaptation : la CI le joue sous Linux et Windows (NFR-8).
- Le lancement planifié se résume à `usine rapport` dans un cron, paramétré par `config/*.yaml` (AD-19, chargeur de `usine.config`).

### Dataiku

- Chaque étape de la Chaîne devient une recette Python ; seuls `composition.py` et les modules `cli` assemblent les adaptateurs, le domaine n'a aucune I/O à réécrire (AD-1, `lint-imports`). Entrepôt DuckDB, bases SQLite et fichiers Excel/PPT deviennent datasets et dossiers gérés, avec une composition par recette.
- Brancher le LLM Mesh demande un nouvel adaptateur derrière le port LLM existant, sans toucher au domaine (AD-1, `lint-imports`).
- Les paramètres restent dans `config/*.yaml`, validés au chargement par le chargeur de `usine.config` (AD-19).

### Power Platform

- Le connecteur Jira est limité sur le changelog et les volumes : garder l'extraction en Python, adaptateur séparé du domaine (AD-1, `lint-imports`), et ne porter que la publication.
- Le calcul des KPI et de la Météo y serait peu maintenable ; la Prévision ML n'a pas d'équivalent (tableau de la spec § 8) : le domaine reste en Python (AD-1).
- L'UI web ne se porte pas sur Power Platform : c'est un écran Power Apps à refaire. Sur Dataiku, seule l'API FastAPI est à réécrire en Flask : les pages HTML se reprennent.

### Poste seul

- Le palier 1 tourne sans LLM : les étapes LLM sont marquées `sautee` (FR-28, NFR-8, CI Windows et Linux).
- Aucun mode LLM local n'est livré aujourd'hui (bonus FR-37) ; l'Agent en dépend aussi.
- La planification exige un poste allumé ; un `.env` par poste porte les secrets (AD-19, gitleaks).

## Références

AD-1 (couches hexagonales, contrôlées par `lint-imports`), AD-19 (configuration et secrets, contrôlés par le chargeur de `usine.config` et gitleaks) et NFR-8 (cœur sans service propriétaire autre que Jira, contrôlé par la CI Windows et Linux). Sources : `ARCHITECTURE-SPINE.md` et `prd.md` sous `_bmad-output/planning-artifacts/`.
