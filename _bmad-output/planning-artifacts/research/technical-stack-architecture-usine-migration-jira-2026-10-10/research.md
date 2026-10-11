---
title: 'Recherche technique : stack du démonstrateur « usine de migration Jira »'
type: 'technical'
topic: "Stack technique de l'usine de migration Jira (démonstrateur)"
decision: "Choix d'architecture pour bmad-architecture : alimentation de Jira Free, adaptateurs Jira, jeu de validation, couche LLM, modèle local, pseudonymisation, versions"
source: 'run (recherche web parallèle, 6 chercheurs + 2 vérificateurs, plus lecture du code wavestack)'
status: complete
preset: 'standard (6 chercheurs)'
validation: 'normal'
created: '2026-10-10'
updated: '2026-10-10'
claims_verified: 28
claims_unverified: 7
claims_disputed: 2
claims_overturned: 0
---

# Recherche technique : stack du démonstrateur « usine de migration Jira »

**Décision servie :** fixer les choix techniques que `bmad-architecture` consigne pour le démonstrateur décrit dans `SPEC-usine-migration-jira-demo.md` (v0.2, section 11).

## Synthèse

1. **Jira Cloud ne permet pas de créer nativement 8 semaines d'historique de statuts.** L'API REST n'accepte pas de date de création antérieure [1]. L'import CSV « External System Import », dans son ancienne interface, peut antidater la création et la résolution, la résolution exigeant que le champ Resolution soit aussi importé [2][3][4]. En revanche, l'import CSV n'importe aucun historique [5]. L'import JSON accepte un historique daté [6], mais Jira Cloud enregistre ses changements de statut comme des modifications génériques, que la JQL ne voit pas (JRACLOUD-81943, non résolu en avril 2026) [7]. **Recommandation : une approche hybride.** Un instantané antidaté importé dans Jira, plus un changelog synthétique, généré et versionné hors de Jira, que l'extracteur fusionne. Il faut l'annoncer honnêtement dans la démo.
2. **Le débit de Jira Free ne pose pas de problème à cette volumétrie.** Les scripts authentifiés par jeton d'API échappent au quota en points, qui ne vise que les apps depuis le 2026-03-02. Les limites de rafale (100 GET ou POST par seconde) et d'écriture par ticket (20 écritures en 2 s, 100 en 30 s) s'appliquent par site et par endpoint [9]. Qu'elles visent aussi les scripts à jeton d'API est une inférence. Il faut gérer les 429 avec `Retry-After` et prévoir la rotation des jetons d'API, qui expirent au plus tard au bout d'un an [10].
3. **Couche LLM : Pydantic AI 2.x, version figée, sans LiteLLM.** Pydantic AI offre les sorties validées avec relance, un agent à outils, tous les fournisseurs visés et une instrumentation Langfuse [26][29][30][31]. LiteLLM n'apporte rien d'indispensable ici et a subi une compromission de sa chaîne d'approvisionnement PyPI en mars 2026 [34]. Du dépôt wavestack, on reprend l'**idée** de l'espacement des appels, le classement des 429 et le registre déclaratif des quotas et prix. Les adaptateurs HTTP ne sont pas à reprendre [W].
4. **Modèle local : Ministral 3 8B Instruct (Q4_K_M, 5,2 Go) servi par `llama-server`.** Le second choix est Qwen3.5-9B, raisonnement désactivé. À ce jour, la qualité en français et l'appel d'outils ne reposent que sur les déclarations des éditeurs [46][48]. Un A/B sur 20 tickets français tranchera.
5. **Principales réserves :**
   - Les quotas des offres gratuites Groq et Gemini **ne sont pas publiés publiquement** [37][39]. Il faut les relever dans les consoles.
   - Le plafond de changelog renvoyé en ligne par `search/jql` n'est pas documenté (10 ou 20 selon les sources) [13][14]. Il ne faut pas s'y fier.

## 1. Jira Cloud Free : historique dans le passé, quotas

| Moyen | Date de création passée | Résolution passée | Historique de statuts | Sources |
|---|---|---|---|---|
| API REST v3 | Non (JRACLOUD-38572, ouvert depuis 2014) | Non selon la communauté, et les KB orientent vers l'import (*confiance moyenne*) | Seulement en temps réel, par transitions | [1] |
| Import CSV, **ancienne interface** (admin du site) | Oui (colonne → « Date created » + format de date) | Oui, si Resolution est importée dans le même fichier | **Non** (JRACLOUD-64575) | [2][3][4][5] |
| Import CSV, nouvelle interface | Non confirmé. Pas de mappage des valeurs [8]. D'après les tickets JRACLOUD-84385 et 84516, pas d'import dans un projet existant ni de mise à jour | — | Non | [8] |
| Import JSON (ancienne interface) | Oui (`created`) | Non documenté | Accepte un tableau `history` daté, mais en Cloud les statuts deviennent des entrées génériques que la JQL ne voit pas | [6][7] |

- Atlassian recommande de passer par l'ancienne interface (« Switch to the old experience »). Une réponse de la communauté annonce son retrait, sans date (*confiance faible*). Rien ne dit que l'importeur est restreint sur l'offre Free (*non vérifié*).
- On ne sait pas si une colonne Status d'un import CSV écrit une entrée de changelog (*non vérifié*, à tester dans un bac à sable).
- **Ce que permet l'offre Free :** 10 utilisateurs, 2 Go de stockage, aucun plafond de tickets annoncé, API REST complète [11]. Le quota d'automatisation est faible, et Atlassian donne des chiffres incohérents selon les pages (150 étapes ou 100 exécutions par mois) [11].
- **Limites de débit [9] :**
  - Rafale par endpoint et par site : GET et POST 100/s, PUT et DELETE 50/s.
  - Écritures par ticket : 20 en 2 s, 100 en 30 s.
  - Le quota en points (65 000/h sur Free) ne vise que les apps Forge, Connect et OAuth : « API token-based traffic is not affected ».
  - Les en-têtes `Retry-After` et `RateLimit-Reason` indiquent quelle limite a été atteinte.
- **Conséquence :** créer quelques milliers de tickets via l'API prend quelques minutes à un débit de quelques requêtes par seconde. La seule limite qui compte vraiment est celle d'écriture par ticket, quand on rejoue plusieurs transitions sur le même ticket.

## 2. API Jira : Cloud v3 et Data Center v2

**Cloud v3**
- `GET/POST /rest/api/3/search` est marqué « currently being removed » dans la spécification [12]. Des rapports tiers le disent retiré et renvoyant 410 (*confiance moyenne*). `/rest/api/3/search/jql` le remplace.
- Pagination de `/search/jql` :
  - par `nextPageToken`, absent de la réponse sur la dernière page ;
  - `maxResults` vaut 50 par défaut, au plus 5 000 si l'on ne demande que id et key, moins avec des champs [12] ;
  - pas de pagination parallèle, jetons valables 7 jours, pas de `total` [13] ;
  - `POST /search/approximate-count` ne donne qu'une estimation [13].
- **Changelog en ligne (`expand=changelog`) : tronqué, plafond non documenté.** La spécification OpenAPI ne donne aucun chiffre. Une RFC d'Atlassian de 2024 parle de 20 entrées [13], un message communautaire de 2026 en constate 10 [14]. Statut : *contesté*.
- **Changelog complet :** `POST /rest/api/3/changelog/bulkfetch` traite jusqu'à 1 000 tickets et 10 identifiants de champ par requête, avec pagination, tri par date puis par identifiant de ticket, et le scope `read:jira-work` [12].
  - L'étiquette « Experimental » vient d'un fil de 2025 [15] et n'apparaît plus dans la spécification. Statut : *contesté*.
  - Des doublons ont été signalés entre pages de petite taille [16]. Il faut dédupliquer par identifiant de changelog.
  - Repli : `GET /issue/{key}/changelog` [13].
- **Champs personnalisés :** créer le champ, puis son contexte (`/field/{id}/context`), puis ses options (`/context/{id}/option`) [18]. Les droits Administer Jira sont requis (source tierce, *confiance moyenne*). L'ajout à un écran n'a pas été vérifié.
- L'API évolue encore. Exemples : validation JQL modifiée le 2026-10-08, et dépréciation, annoncée le 2026-10-07 et effective le 2026-11-16, des recherches sur les propriétés d'entité utilisateur [17].

**Data Center v2**
- Jetons d'accès personnels (PAT) avec `Authorization: Bearer`, depuis Jira 8.14 [19].
- `/rest/api/2/search` pagine par `startAt`/`maxResults`/`total` : 50 par défaut, plafonné par `jira.search.views.default.max` (1 000 par défaut) [20]. Une fenêtre de 10 000 résultats impose de découper la JQL par plages de dates [21].
- Fin de vie de Data Center : arrêt des ventes aux nouveaux clients le 2026-03-30, des extensions le 2028-03-30, lecture seule le **2029-03-28** [22]. Dans une banque, l'adaptateur Data Center reste pertinent jusqu'à la migration.

## 3. Public Jira Dataset (Zenodo 5882881)

- **Version et contenu.**
  - Version 7 du 2025-06-23 (le DOI conceptuel pointe vers l'enregistrement 15719919), licence CC BY 4.0. Les utilisateurs y sont masqués par UUID4 [23].
  - Un seul fichier zip de **5,8 Go**, qui contient un dump MongoDB, des scripts de téléchargement et des scripts d'interprétation [23].
  - L'organisation exacte du dump (répertoire BSON ou archive) et le nom des collections ne sont pas publiés (*non trouvé*).
  - Il n'existe pas de miroir en Parquet, CSV, Hugging Face ou Kaggle (*absence constatée*).
- **Modèle de données.** Un document par ticket, sans schéma fixe selon l'instance, avec `fields` (created, resolutiondate, priority, status…) et `changelog` imbriqués [24].
- **Taille des instances (2022).** 2,7 M tickets au total. Hyperledger compte 28 k tickets, Spring 69 k, MongoDB 137 k et Apache 1,01 M [24]. Les workflows diffèrent beaucoup d'une instance à l'autre, et beaucoup de tickets ne sont pas résolus [24].
- **Extraction recommandée.** Télécharger une seule fois, puis `unzip -l` pour découvrir l'organisation. Ensuite, `mongorestore --nsInclude` sur une petite instance (Hyperledger ou Spring), ou lecture directe des `.bson` avec `bson.decode_file_iter`. Export unique en Parquet, chargé ensuite dans DuckDB.
- **Censure.** Il faut conserver les tickets non résolus, sous peine de biaiser la prévision « résolu sous N jours ».
- **Travaux comparables.** Une étude d'estimation du délai de résolution sur des tickets Apache existe [25]. Qu'elle utilise ce jeu de données n'est pas confirmé (*confiance faible*).

## 4. Couche LLM : Pydantic AI ou LangGraph + LiteLLM

| Critère | Pydantic AI | LangGraph + LiteLLM |
|---|---|---|
| Versions | 2.55.0 (2026-10-09). v2 stable depuis le 2026-06-23 ; la branche v1 est encore maintenue [26][27][28] | langgraph 1.2.14, litellm 1.104.2 [32][33] |
| Sorties structurées validées | Trois modes : Tool Output par défaut, Native, Prompted. Relance automatique (1 essai par défaut, réglable), validateur avec `ModelRetry` [29] | LiteLLM transmet `response_format` et valide côté client en option, sans relance [36] |
| Agent à 4 outils en lecture seule | Natif, sans graphe | LangGraph est surdimensionné pour ce cas |
| Fournisseurs | Groq, Anthropic, OpenAI, Mistral, Google, Azure, Ollama et autres endpoints compatibles OpenAI ; `FallbackModel` ; `TestModel` pour une CI sans clé [30] | Large couverture, c'est le point fort de LiteLLM [36] |
| Observabilité | Langfuse via `instrument=True` (spans OpenTelemetry) [31] | Callbacks Langfuse (*non vérifié*) |
| Risque | Rythme de versions très rapide (8 versions mineures en 3 semaines) [27] | Compromission PyPI du 2026-03-24 (1.82.7 et 1.82.8 malveillantes, version saine 1.83.0) [34][35] |

**Choix : Pydantic AI 2.x, version figée dans `uv.lock`.**
- Le second choix, LangGraph, l'emporte si l'agent devient un workflow à états, avec reprise ou validation humaine.
- **Couverture contre l'irréversibilité :** un port interne mince, par exemple `classify_root_cause() -> RootCause` et `ask_agent()`, avec des schémas Pydantic définis dans le domaine. Pydantic AI peut d'ailleurs utiliser LiteLLM comme fournisseur [30].

**Contraintes par fournisseur**
- **Groq**
  - Les sorties strictes `json_schema` ne fonctionnent que sur gpt-oss-20b, gpt-oss-120b et qwen3.8-27b, et ni avec le streaming ni avec des outils [38]. Il faut donc garder le mode Tool Output.
  - Le tableau public (30 requêtes/min, 1 000/jour, 8 000 tokens/min) concerne l'**offre Developer**. Les quotas gratuits ne sont visibles que dans la console [37]. La lecture inverse, venue du premier tour, est *infirmée*.
- **Gemini (AI Studio) :** aucun quota gratuit sur la page officielle [39]. Des sources tierces font état d'une forte baisse en décembre 2025 [40] (*non vérifié*).
- **Mistral (offre gratuite) :** 1 requête/s, 500 000 tokens/min, 1 milliard de tokens/mois [41]. Une source secondaire indique que l'offre gratuite exige d'accepter l'usage des données pour l'entraînement (*non vérifié*).
- **Anthropic :** sorties structurées disponibles en GA (`output_config.format`). Les contraintes de schéma non prises en charge (min/max, minLength…) renvoient une erreur 400 [42].
- **Ollama :** schéma dans `format` [43].
- **llama.cpp :** `response_format` json_schema est converti en grammaire [44].

**Ce qu'il faut reprendre de wavestack [W]** (lecture du code, `agentic-harness-training-demo/src/wavestack`)
- **À adapter :**
  - `pace()` (`cloud_base.py:242`) : espacement minimal par modèle, thread-safe et annulable. À réécrire en asyncio, avec un seau à jetons RPM/TPM.
  - Le classement des 429 (minute, jour, quota nul, crédit épuisé, avec `Retry-After`, `cloud_base.py:194-228`, `632-672`). Il faut y ajouter un backoff, absent de wavestack.
  - Le registre déclaratif `CloudModel`/`CloudPricing` (`config.py:161-290`) : quotas, prix datés, capacités.
  - Le calcul de coût, le masquage des clés et le plafond de dépense par session.
- **À ne pas reprendre :**
  - Les adaptateurs SSE en httpx brut (openai_chat, anthropic_messages, responses) : Pydantic AI les couvre. Ils n'ont d'ailleurs ni sortie structurée ni `tool_choice`.
  - Le catalogue d'UI, la découverte et la sonde GGUF, llama-cpp-python.
  - Leurs cas limites de parsing deviennent des cas de test : appels d'outils parallèles, Gemini sans index, `tool_use_failed` de Groq.
- **Headroom (`headroom-ai` 0.38.0) :** optionnel. Il compresse les gros résultats d'outils en JSON ou en logs, mais le dépôt ne mesure aucun gain, et il ajoute 285 Mo sur disque et LiteLLM en dépendance transitive. À n'adopter qu'après un banc d'essai sur des exports Jira.

## 5. Modèle local sur 8 Go de VRAM

| Modèle | Licence | Taille Q4 | Français | Outils | Verdict |
|---|---|---|---|---|---|
| **Ministral 3 8B Instruct 2512** | Apache-2.0 | 5,20 Go Q4_K_M (officiel) | Éditeur français ; français dans les langues listées ; MMMLU 0,706 du modèle de base (éditeur) | Appel de fonctions natif annoncé ; les bogues d'outils Ministral d'Ollama sont fermés depuis janvier 2026 | **Choix** [46][47][54] |
| Qwen3.5-9B | Apache-2.0 | 5,68 Go Q4_K_M | MMMLU 81,2 (éditeur) | BFCL-V4 66,1 (éditeur), mais **appels d'outils cassés dans llama.cpp quand le raisonnement est actif**, et instables dans Ollama à cause d'un analyseur inadapté (tickets ouverts en septembre 2026) | Second choix, raisonnement désactivé [48][49][50][51] |
| Granite 4.2 8B | Apache-2.0 | 5,35 Go (dépôt GGUF d'IBM) | Français testé (éditeur) | BFCL 52,4 ; sorti le 2026-08-25, peu de retours | Écarté [53] |
| Gemma 4 12B | Apache-2.0 | 6,98 Go | MMMLU 83,4 | Tau2 69,0 | Écarté : trop juste pour 8 Go avec du contexte [52] |

**Service : `llama-server`**
- Commande : `-ngl 99 -c 16384 -fa on -ctk q8_0 -ctv q8_0 --jinja --temp 0.1`.
- `response_format` json_schema est contraint par grammaire, ce qui convient pour la classification et les commentaires [44].
- Les tours d'agent avec outils passent dans des requêtes séparées, **sans** `response_format`. La combinaison des deux n'est pas documentée dans llama.cpp et elle est cassée dans Ollama (#13750) [54].
- Ne pas descendre le cache KV à q4_0, qui dégrade l'appel d'outils [45]. q8_0 est un choix prudent.
- Ollama sert de solution de repli [43][55].

**Risques**
- La documentation de llama.cpp range Ministral-3b dans l'analyseur « Generic » [45] et peut faire de même pour Ministral 3 8B. Un test de fumée avec 3 outils s'impose.
- Le fait que le cache KV tienne en 16k sur 8 Go est une estimation (*non vérifié*).
- Toutes les données de qualité viennent des éditeurs.

## 6. Presidio en français

- presidio-analyzer et presidio-anonymizer 2.2.364 (2026-07-22), Python 3.10 à 3.14 [56]. La documentation a migré vers presidio.dataprivacystack.org.
- **Aucun reconnaisseur FR_* prédéfini** [57]. Les entités génériques fonctionnent par expression régulière : EMAIL, IBAN, PHONE, URL, IP, CREDIT_CARD. En revanche, les mots de contexte dépendent de la langue. Il faut donc réenregistrer chaque reconnaisseur avec `supported_language="fr"` et un contexte en français [58].
- **Moteur NLP :** `NlpEngineProvider` avec spaCy `fr_core_news_md` (ou lg), plus le mappage PER→PERSON, LOC→LOCATION, ORG→ORGANIZATION. La configuration se met en YAML [59]. La documentation ne montre que l'espagnol : le passage au français est une transposition (*confiance moyenne*).
- **Reconnaisseurs maison** (PatternRecognizer : regex, contexte, score, listes de refus, déclarés en YAML) : clés de ticket, codes d'entité fictifs, NIR, SIREN/SIRET, IBAN fictifs. La configuration YAML des reconnaisseurs est décrite dans la documentation de `AnalyzerEngineProvider` (non citée dans l'annexe).
- **Pseudonymisation réversible.** Opérateur `custom` qui attribue des jetons stables (PERSON_1, ENTITE_3) à partir d'une table tenue côté application, puis remplacement inverse sur la sortie du LLM. `encrypt`/`DeanonymizeEngine` est réversible mais produit des jetons opaques, peu lisibles pour le LLM [60]. Ce motif est une inférence, pas un exemple tiré de la documentation.
- **Qualité.** Aucune mesure primaire de la qualité de la NER française dans Presidio n'a été trouvée. Il faut l'évaluer sur un petit échantillon annoté. GLiNER multilingue est disponible en option (`[gliner]`), mais n'a été validé qu'en anglais [61].

## 7. Versions à figer (PyPI, lues le 2026-10-10, deux lectures concordantes) [62]

| Paquet | Version | Date | Python | Remarque |
|---|---|---|---|---|
| duckdb | 1.5.6 | 2026-09-28 | ≥ 3.10 | Toujours en 1.x |
| polars | **2.0.0** | 2026-10-06 | ≥ 3.10 | **Version majeure de 4 jours**. Ruptures sur les fenêtres SQL, les Decimal, les ENUM Parquet lus comme String, `cut`/`qcut` [63]. 1.44.0 est la dernière 1.x |
| python-pptx | 1.0.2 | 2024-08-07 | ≥ 3.8 | Aucune version depuis plus de 2 ans |
| openpyxl | 3.1.5 | 2024-06-28 | ≥ 3.8 | Aucune version depuis plus de 2 ans |
| lightgbm | 4.7.0 | 2026-07-18 | ≥ 3.10 | |
| shap | 0.53.0 | 2026-10-09 | **≥ 3.12** | Exige numpy ≥ 2 ; sortie la veille |
| streamlit | 1.65.0 | 2026-10-02 | ≥ 3.10 | Versions mineures environ toutes les 2 semaines |
| pydantic-ai | 2.55.0 | 2026-10-09 | ≥ 3.11 | Voir § 4 |
| presidio-analyzer | 2.2.364 | 2026-07-22 | 3.10 à 3.14 | |

Python 3.12 est compatible avec toute la pile.

## Enseignements croisés

- **Le changelog synthétique devient une source de données à part entière.** Puisque Jira Cloud ne peut pas porter l'historique (§ 1), l'extracteur doit fusionner deux flux : l'API Jira et un fichier de changelog généré au format de `/issue/{key}/changelog`. Ce fichier est seedé, donc idempotent, ce qui sert aussi la règle « rejouer une semaine produit le même rapport ». L'adaptateur Data Center, testé sur fixtures, suit la même logique : les fixtures et le changelog synthétique peuvent partager un format.
- **Une option hybride rend la démo honnête.** Les dernières journées de transitions peuvent être jouées *réellement* via l'API, par une tâche quotidienne pendant la préparation de la démo. Le changelog Jira lu en direct est alors authentique sur la période récente, et synthétique avant. Le débit le permet largement (§ 1).
- **L'incompatibilité entre sorties structurées et outils traverse les fournisseurs.** Groq [38] et Ollama [54] en souffrent, et llama.cpp ne documente pas la combinaison [44]. Cela plaide pour le mode Tool Output de Pydantic AI comme défaut, et pour séparer les appels de classification (schéma) des tours d'agent (outils).
- **Le changelog Cloud renvoyé en ligne est tronqué** (§ 2), alors que la prévision et les KPI de flux reposent sur l'historique complet. Il faut `changelog/bulkfetch`, ou l'appel par ticket, dès le premier adaptateur.

## Recommandations (pour `bmad-architecture`)

1. **Alimentation de Jira (contrainte d'architecture).**
   - Générateur → CSV, importé par l'ancienne interface d'import externe, avec date de création, statut courant, résolution et date de résolution.
   - Plus un fichier de changelog synthétique seedé, que l'extracteur fusionne.
   - Champs personnalisés créés par l'API (champ, contexte, options).
   - *Confiance élevée*, sauf deux points à tester en bac à sable dès le premier jour : l'import CSV sur l'offre Free et les entrées de changelog créées par l'import.
2. **Adaptateur Cloud v3.**
   - `search/jql` avec `nextPageToken`, séquentiel, filigrane `updated >=` avec chevauchement, dédoublonnage par clé et identifiant de changelog.
   - Changelog complet par `changelog/bulkfetch`, repli par ticket.
   - 429 traités avec `Retry-After`.
   - **Adaptateur DC v2 :** PAT Bearer, `startAt`/`total`, pages ≤ 1 000, découpage par dates. *Élevée.*
3. **Validation de la prévision.**
   - Hyperledger ou Spring, extraits du dump Zenodo v7 et exportés en Parquet, avec les tickets non résolus conservés.
   - Une tâche de découverte (spike) d'une demi-journée pour l'organisation du dump. *Moyenne* : l'organisation du dump est inconnue.
4. **Couche LLM.**
   - Pydantic AI 2.x figé, mode Tool Output, `output_validator` pour vérifier les citations de tickets, `FallbackModel`, Langfuse via `instrument=True`.
   - Pas de dépendance directe à LiteLLM.
   - Un module « registre des fournisseurs » inspiré de wavestack : quotas, espacement asynchrone, classement des 429, coûts. *Élevée pour le choix ; faible pour les quotas gratuits Groq et Gemini, à relever en console.*
5. **Mode local.**
   - Ministral 3 8B Q4_K_M sur `llama-server`. Les appels à schéma et les appels à outils sont séparés.
   - Un test de fumée outils et JSON, plus un A/B de 20 tickets contre Qwen3.5-9B sans raisonnement. *Moyenne : données des éditeurs uniquement.*
6. **Pseudonymisation.**
   - Presidio 2.2.364, spaCy `fr_core_news_md`, reconnaisseurs maison en YAML, opérateur `custom` avec table réversible.
   - Une évaluation sur échantillon annoté. *Moyenne.*
7. **Versions.**
   - Python 3.12, avec les versions du § 7.
   - Polars : 2.0.x pour un projet neuf, ou 1.44.x si une rupture gêne.
   - shap 0.53 impose numpy ≥ 2. *Élevée.*

## Questions ouvertes

- **Import CSV :** disponible sur l'offre Free, et crée-t-il des entrées de changelog ? → Test de 10 lignes dans le site Jira Free.
- **Plafond du changelog en ligne de `search/jql` :** 10 ou 20 ? → Sans importance si l'on passe toujours par `bulkfetch`.
- **Quotas gratuits Groq et Gemini :** → les relever dans console.groq.com/settings/limits et aistudio.google.com/rate-limit, puis les reporter dans le registre des fournisseurs.
- **Dump Zenodo :** organisation et noms des collections → `unzip -l` après téléchargement.
- **Qualité réelle en français** de Ministral 3 8B par rapport à Qwen3.5-9B, et tenue du cache KV en 16k → A/B et `nvidia-smi`.
- **Qualité de la NER spaCy française** sur des tickets → échantillon annoté.

## Annexe : sources

| # | Ce que la source étaye | Éditeur | Date pub. | Consultée | Confiance |
|---|---|---|---|---|---|
| 1 | L'API ne peut pas fixer `created` | [Atlassian, JRACLOUD-38572](https://jira.atlassian.com/browse/JRACLOUD-38572) | 2014-06, actif 2026-10 | 2026-10-10 | élevée |
| 2 | L'import CSV conserve la date de création | [Atlassian Support KB](https://support.atlassian.com/jira/kb/how-to-retain-created-date-while-importing-issues/) | 2025-09-26 | 2026-10-10 | élevée |
| 3 | Date de résolution par CSV, ancienne interface | [Atlassian Support KB](https://support.atlassian.com/jira/kb/how-to-bulk-update-the-resolved-date-field-using-csv-import/) | 2026-06-17 | 2026-10-10 | élevée |
| 4 | La résolution exige le champ Resolution | [Atlassian, JRACLOUD-65502](https://jira.atlassian.com/browse/JRACLOUD-65502) | non datée | 2026-10-10 | élevée |
| 5 | Le CSV n'importe pas l'historique | [Atlassian, JRACLOUD-64575](https://jira.atlassian.com/browse/JRACLOUD-64575) | 2016-09, actif 2026 | 2026-10-10 | élevée |
| 6 | Importeur JSON, tableau `history` | [Atlassian Support](https://support.atlassian.com/jira-cloud-administration/docs/import-data-from-json) | non datée (© 2026) | 2026-10-10 | élevée |
| 7 | Statuts importés par JSON invisibles en JQL | [Atlassian, JRACLOUD-81943](https://jira.atlassian.com/browse/JRACLOUD-81943) | 2020-08, maj 2026-04-19 | 2026-10-10 | élevée |
| 8 | Lacunes de la nouvelle interface d'import, repli sur l'ancienne | [Atlassian, JRACLOUD-84562](https://jira.atlassian.com/browse/JRACLOUD-84562) | ~2024 | 2026-10-10 | moyenne |
| 9 | Limites de débit, quota en points pour les seules apps | [Atlassian Developer](https://developer.atlassian.com/cloud/jira/platform/rate-limiting/) | 2026-10-09 | 2026-10-10 | élevée |
| 10 | Jetons d'API : expiration à 1 an maximum | [Atlassian Support](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/) | non datée | 2026-10-10 | moyenne-élevée |
| 11 | Limites de l'offre Free | [Atlassian](https://support.atlassian.com/jira-cloud-administration/docs/explore-jira-cloud-plans/) | non datée (© 2026) | 2026-10-10 | élevée ; faible pour l'automatisation |
| 12 | Spécification OpenAPI v3 : `search/jql`, `bulkfetch`, `/search` déprécié | [Atlassian Developer, swagger-v3](https://developer.atlassian.com/cloud/jira/platform/swagger-v3.v3.json) | instantané 2026-10-10 | 2026-10-10 | élevée |
| 13 | RFC-61 : `nextPageToken`, approximate-count, changelog plafonné à 20 | [Atlassian Developer Community](https://community.developer.atlassian.com/t/rfc-61-evolving-search-capabilities-addressing-scalability-with-a-new-enhanced-search-api/83027) | 2024-09 | 2026-10-10 | moyenne (ancienne) |
| 14 | Changelog en ligne constaté à 10 entrées | [Atlassian Developer Community](https://community.developer.atlassian.com/t/complete-change-log-is-not-returning-by-api-rest-api-3-search-jql-expand-changelog/101256) | 2026-07-28 | 2026-10-10 | faible |
| 15 | `bulkfetch` « Experimental » | [Atlassian Developer Community](https://community.developer.atlassian.com/t/bulk-fetch-changelogs-experimental-api/87240) | 2025-01 | 2026-10-10 | moyenne |
| 16 | Doublons entre pages de `bulkfetch` | [Atlassian, JRACLOUD-94906](https://jira.atlassian.com/browse/JRACLOUD-94906) | non datée | 2026-10-10 | moyenne |
| 17 | Évolutions de `search/jql` en octobre 2026 | [Atlassian Developer changelog](https://developer.atlassian.com/changelog/) | 2026-10 | 2026-10-10 | élevée |
| 18 | Champ, puis contexte, puis options | [Atlassian Developer](https://developer.atlassian.com/cloud/jira/platform/rest/v2/api-group-issue-custom-field-options/) | non datée | 2026-10-10 | moyenne |
| 19 | PAT Data Center depuis 8.14, Bearer | [Atlassian](https://confluence.atlassian.com/display/ENTERPRISE/Using+personal+access+tokens) | non datée | 2026-10-10 | élevée |
| 20 | `maxResults` plafonné à 1 000 (DC) | [Atlassian Support KB](https://support.atlassian.com/jira/kb/how-to-use-the-maxresults-api-parameter-for-jira-issue-search-rest-api/) | non datée | 2026-10-10 | élevée |
| 21 | Fenêtre de 10 000 résultats (DC) | [Atlassian Support KB](https://support.atlassian.com/jira/kb/handling-jql-rest-api-searching-exceeding-max_result_window-in-jira/) | non datée | 2026-10-10 | élevée |
| 22 | Fin de vie de Data Center : 2026-03-30, 2028-03-30, 2029-03-28 | [Atlassian](https://www.atlassian.com/migration) | 2025-09 | 2026-10-10 | élevée |
| 23 | Zenodo v7 : zip de 5,8 Go, dump MongoDB, CC BY 4.0 | [Zenodo](https://zenodo.org/records/5882881) | 2025-06-23 | 2026-10-10 | élevée |
| 24 | Modèle de données, taille des instances, limites | [Montgomery et al., MSR 2022 (arXiv)](https://arxiv.org/abs/2201.08368) | 2022-01 | 2026-10-10 | élevée (chiffres de 2022) |
| 25 | Estimation du délai de résolution (Apache) | [Nastos et al., arXiv 2505.01108](https://arxiv.org/abs/2505.01108) | 2025-05-02 | 2026-10-10 | faible-moyenne |
| 26 | pydantic-ai 2.55.0 | [PyPI](https://pypi.org/project/pydantic-ai/) | 2026-10-09 | 2026-10-10 | élevée |
| 27 | Rythme de versions, branche v1 maintenue | [GitHub, pydantic-ai releases](https://github.com/pydantic/pydantic-ai/releases) | 2026-09/10 | 2026-10-10 | élevée |
| 28 | v1 en septembre 2025, v2 stable le 2026-06-23 | [Pydantic, changelog](https://pydantic.dev/docs/ai/changelog/) | non datée | 2026-10-10 | moyenne-élevée |
| 29 | Modes de sortie, relances | [Pydantic, documentation Output](https://pydantic.dev/docs/ai/core-concepts/output/) | non datée | 2026-10-10 | élevée |
| 30 | Fournisseurs, `FallbackModel`, `TestModel` | [Pydantic, documentation Models](https://pydantic.dev/docs/ai/models/overview/) | non datée | 2026-10-10 | élevée (source unique) |
| 31 | Intégration Langfuse | [Langfuse](https://langfuse.com/integrations/frameworks/pydantic-ai) | non datée | 2026-10-10 | élevée |
| 32 | langgraph 1.2.14 | [PyPI](https://pypi.org/project/langgraph/) | 2026-10-06 | 2026-10-10 | élevée |
| 33 | litellm 1.104.2 | [PyPI](https://pypi.org/project/litellm/) | 2026-10-08 | 2026-10-10 | élevée |
| 34 | Compromission de LiteLLM, avis officiel | [LiteLLM / BerriAI](https://docs.litellm.ai/blog/security-update-march-2026) | 2026-03-27 | 2026-10-10 | élevée |
| 35 | Compromission de LiteLLM, presse | [InfoQ](https://infoq.com/news/2026/03/litellm-supply-chain-attack/) | 2026-03 | 2026-10-10 | élevée |
| 36 | Sorties structurées LiteLLM | [LiteLLM docs](https://docs.litellm.ai/docs/completion/json_mode) | non datée | 2026-10-10 | élevée |
| 37 | Limites Groq de l'offre Developer | [Groq](https://console.groq.com/docs/rate-limits) | non datée | 2026-10-10 | élevée |
| 38 | Sorties structurées Groq, sans outils ni streaming | [Groq](https://console.groq.com/docs/structured-outputs) | non datée | 2026-10-10 | élevée |
| 39 | Gemini : aucun quota gratuit publié | [Google AI for Developers](https://ai.google.dev/gemini-api/docs/rate-limits) | non datée | 2026-10-10 | élevée (absence) |
| 40 | Baisse des quotas gratuits Gemini en décembre 2025 | [agentdeals.dev](https://agentdeals.dev/gemini-api-pricing-changes) | 2026-04-08 | 2026-10-10 | faible |
| 41 | Limites de l'offre gratuite Mistral | [Mistral Help Center](https://help.mistral.ai/en/articles/225174-what-are-the-limits-of-the-free-tier) | non datée | 2026-10-10 | moyenne-élevée |
| 42 | Sorties structurées Anthropic en GA, erreur 400 | [Anthropic](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | non datée | 2026-10-10 | élevée |
| 43 | Sorties structurées Ollama | [Ollama](https://docs.ollama.com/capabilities/structured-outputs) | non datée | 2026-10-10 | élevée |
| 44 | Options de `llama-server`, json_schema | [ggml-org, llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) | non datée (master) | 2026-10-10 | élevée |
| 45 | Appel de fonctions dans llama.cpp, Ministral en « Generic », cache KV q4 | [ggml-org, llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md) | non datée (ancienne) | 2026-10-10 | moyenne |
| 46 | Ministral 3 8B : licence, capacités annoncées | [Mistral AI, Hugging Face](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512) | 2025-12, maj 2026-07-15 | 2026-10-10 | moyenne (éditeur) |
| 47 | GGUF de Ministral 3 8B : 5,20 Go | [Mistral AI, Hugging Face](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512-GGUF) | 2026-01-15 | 2026-10-10 | élevée |
| 48 | Qwen3.5-9B : scores, raisonnement | [Qwen, Hugging Face](https://huggingface.co/Qwen/Qwen3.5-9B) | 2026-03-02 | 2026-10-10 | moyenne (éditeur) |
| 49 | GGUF de Qwen3.5-9B : 5,68 Go | [Unsloth, Hugging Face](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF) | 2026-03-02 | 2026-10-10 | élevée |
| 50 | Outils Qwen3.5 cassés avec le raisonnement (llama.cpp) | [GitHub, llama.cpp #20837](https://github.com/ggml-org/llama.cpp/issues/20837) | 2026-03 à 2026-09 | 2026-10-10 | élevée |
| 51 | Outils Qwen3.5 instables (Ollama) | [GitHub, Ollama #14493](https://github.com/ollama/ollama/issues/14493) | 2026-02 à 2026-09 | 2026-10-10 | moyenne-élevée |
| 52 | Gemma 4 12B : 6,98 Go | [Google, Hugging Face](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf) | 2026-07-17 | 2026-10-10 | élevée |
| 53 | Granite 4.2 8B | [IBM, Hugging Face](https://huggingface.co/ibm-granite/granite-4.2-8b) | 2026-09-04 | 2026-10-10 | moyenne (éditeur) |
| 54 | Ollama : bogues Ministral fermés, #13750 outils + format | [GitHub, Ollama issues](https://github.com/ollama/ollama/issues?q=ministral-3+tool) | 2026-01 | 2026-10-10 | moyenne |
| 55 | Ollama `ministral-3` | [Ollama](https://ollama.com/library/ministral-3) | ~2025-12 | 2026-10-10 | élevée |
| 56 | Presidio 2.2.364 | [PyPI](https://pypi.org/project/presidio-analyzer/) | 2026-07-22 | 2026-10-10 | élevée |
| 57 | Aucune entité FR_* | [Presidio docs](https://presidio.dataprivacystack.org/supported_entities/) | non datée | 2026-10-10 | élevée |
| 58 | Reconnaisseurs par langue | [Presidio docs](https://presidio.dataprivacystack.org/analyzer/languages/) | non datée | 2026-10-10 | élevée |
| 59 | Moteur NLP non anglais, configuration YAML | [Presidio docs](https://presidio.dataprivacystack.org/analyzer/customizing_nlp_models/) | non datée | 2026-10-10 | élevée ; moyenne pour le français |
| 60 | Opérateurs de l'anonymiseur | [Presidio docs](https://presidio.dataprivacystack.org/anonymizer/) | non datée | 2026-10-10 | moyenne-élevée |
| 61 | Reconnaisseur GLiNER | [Presidio docs](https://presidio.dataprivacystack.org/samples/python/gliner/) | non datée | 2026-10-10 | moyenne |
| 62 | Versions des paquets (API JSON de PyPI, deux lectures) | [PyPI](https://pypi.org/) | 2024-06 à 2026-10 | 2026-10-10 | élevée |
| 63 | Ruptures de Polars 2.0 | [GitHub, pola-rs](https://github.com/pola-rs/polars/releases/tag/py-2.0.0) | 2026-10-06 | 2026-10-10 | moyenne (résumé de l'outil de lecture) |
| W | Couche fournisseurs wavestack (lecture du code, pas une source web) | [agentic-harness-training-demo](../../../../../agentic-harness-training-demo/src/wavestack/models/) | dépôt local | 2026-10-10 | élevée (code lu) |

## Calendrier de péremption

Calculé avec `recon_kit.py staleness`. Fenêtres : versions 1 mois ; quotas LLM, modèles locaux et paysage IA 3 mois ; API, limites et import Jira, jeu de données 12 mois ; motifs 24 mois.

| Affirmation | Classe | Publiée | À revérifier le |
|---|---|---|---|
| Versions des paquets (Polars 2.0, pydantic-ai 2.55, shap 0.53…) | version | 2026-10 | **2026-11-01** |
| Choix du modèle local (Ministral 3 8B ou Qwen3.5-9B) | modèle | 2026-09 | 2026-12-01 |
| Quotas Groq, Gemini et Mistral | quota LLM | 2026-10 | 2027-01-01 |
| Pydantic AI ou LangGraph + LiteLLM | paysage IA | 2026-10 | 2027-01-01 |
| Import CSV et JSON, historique Jira | capacité | 2026-06 | 2027-06-01 |
| Limites de débit, `search/jql`, `bulkfetch` | API | 2026-10 | 2027-10-01 |
| Presidio en français | motif | 2026-07 | 2028-07-01 |
| Zenodo v7 | jeu de données | 2025-06 | 2026-06-01, déjà dépassé selon le calcul |

L'outil classe Zenodo v7 comme périmé, parce que la version date de juin 2025. Ce run a pourtant vérifié qu'aucune version plus récente n'existe [23]. **Première revérification : 2026-11-01** (versions).
