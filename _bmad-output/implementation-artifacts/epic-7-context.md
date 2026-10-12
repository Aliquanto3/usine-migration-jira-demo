# Epic 7 Context: Interface de démo et Agent (L7 Agent et UI)

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Donner au Pilote et à l'auteur les écrans de la démo de 10 minutes présentée au Sponsor : carte météo, détail d'Entité, lancement de la Chaîne avec sa progression, avant / après, écran « Ce qu'il faut pour le faire en vrai », Mode repli et comparaison Palier 1 / Palier 2. Viennent ensuite un Agent conversationnel en lecture seule, dont chaque chiffre provient d'un outil, et sa suite d'évaluation sur 15 questions. L'epic porte l'argument central de la démo (gain de temps, Météo justifiée, Prévision, Agent fiable). Il doit aussi rester jouable sans réseau. Les stories 7.1 à 7.6 relèvent du Palier 1 et passent avant la porte M3 (prérequis : Story 5.2). Les stories 7.7 à 7.12 relèvent du Palier 2 et viennent après l'Epic 6.

## Stories

- Story 7.1 : Carte météo et navigation
- Story 7.2 : Détail d'une Entité (Palier 1)
- Story 7.3 : Lancement de la Chaîne et progression
- Story 7.4 : Avant / après
- Story 7.5 : Écran « Ce qu'il faut pour le faire en vrai »
- Story 7.6 : Mode repli sur un Passage enregistré
- Story 7.7 : Explication sourcée à l'écran et comparaison des Paliers
- Story 7.8 : Outils de consultation de l'Agent
- Story 7.9 : Agent conversationnel aux chiffres contrôlés
- Story 7.10 : Suite d'évaluation de l'Agent
- Story 7.11 : Réponses enregistrées de l'Agent et Mode repli complet
- Story 7.12 : Répétitions chronométrées de la démo

## Requirements & Constraints

- **Écrans** : carte météo, détail d'Entité (Règles déclenchantes avec valeur, seuil et tickets en cause, KPI, Explication sourcée avec liens, Prévision avec fourchette, probabilité et facteurs, ou « pas de sortie projetée », Risque d'entrée en rouge), Agent, lancement de la Chaîne et écran outillage. Chaque écran est à **un clic** de la carte météo. La progression affiche chaque étape de la Chaîne.
- **Liens Jira** : toute clé de ticket affichée est un lien vers Jira, inactif en Mode repli.
- **Avant / après** : le temps manuel déclaré en configuration (valeur fictive commentée) est affiché à côté du temps mesuré du dernier Passage réussi sans classification initiale, par Rapport et cumulé sur 5 Rapports. Si seul un Passage avec classification initiale existe, l'écran le signale au lieu d'afficher un temps trompeur.
- **Mode repli** : activation toujours manuelle, jamais automatique (bascule de l'UI ou `USINE_MODE_REPLI=1`). La mention « Mode repli » reste visible en permanence. Toute l'UI lit le Passage enregistré, et les réponses enregistrées de l'Agent sont rejouées. Sur un clone frais sans réseau, toute la démo fonctionne, Agent compris.
- **Comparaison des Paliers** : la même Entité s'affiche avec et sans sortie LLM. En Palier 1, la zone Explication porte « commentaire non généré (Palier 1) ».
- **Pseudonymisation** : une vue côte à côte montre l'original et la version pseudonymisée, en local seulement.
- **Agent** :
  - Outils de consultation pour toute Date d'arrêté disponible : Météo et Règles, Anomalies filtrées, Tendances, Prévisions et Risques. Une date sans Passage donne « aucune donnée pour cette date ».
  - Strictement en lecture seule : aucun outil d'écriture (Jira, mail, configuration) et aucun accès à Jira.
  - Chaque nombre vient d'un résultat d'outil de la conversation, et chaque ticket cité a été retourné. Sinon, la réponse est rejetée et remplacée par un message explicite. Quand les données ne permettent pas de répondre, l'Agent le dit.
  - Question de la démo : « Quelles entités risquent de passer au rouge la semaine prochaine, et pourquoi ? ». La réponse attendue cite C, l'indicateur en hausse et ses Cas de test KO.
- **Évaluation de l'Agent** : 15 questions versionnées, dont la question de la démo et au moins 2 questions sans réponse possible. Les éléments attendus sont vérifiés automatiquement. La suite se lance à la demande, hors CI. Cible : au moins 13/15, zéro chiffre inventé, au plus 1 refus sur les 13 questions répondables (hypothèse).
- **Démo** : au moins 3 répétitions de 10 minutes au plus, dont une en Mode repli, sans intervention hors script. Chaque répétition est consignée (date, durée, mode, incidents).
- **Transverses** :
  - Aucun chiffre calculé par un LLM ni dérivé dans l'UI ou l'Agent.
  - Rien d'identifiant n'est envoyé au LLM ni écrit dans les traces.
  - Interface et réponses en français.
  - Tests unitaires sans appel LLM ni Jira réel.

## Technical Decisions

- **Périmètre d'écriture de la lane** : `ia/agent`, `ui/`, `demo/`, `config/demo.yaml`, `evals/agent` et leurs tests miroirs. `contrats/` et `ports/` ne changent que par une PR dédiée sur `main`.
- **Lecture des Passages** : l'UI et l'Agent lisent un Passage uniquement via `Consultation` (dernier Passage : `dernier_passage()`, ou `dernier_passage(sans_classification_initiale=True)` pour l'avant / après). Ils n'ouvrent jamais `entrepot.duckdb` ni un répertoire `.en-cours-*`. Les URL de ticket viennent uniquement de `consultation.url_ticket(cle)`, qui renvoie `None` en Mode repli. Le formatage français vient de `contrats.format`. La comparaison des Paliers passe par le filtre `palier` de `Consultation`.
- **Couches** : `ui` (Streamlit 1.65) peut importer `contrats`, `consultation` et `composition`, mais pas `ports`. Elle déclare le `Protocol` local `LectureMeteo`, tenu aligné sur `Consultation` par un test de conformité. `ia/agent` peut importer `contrats`, `ports` et `consultation`. `pydantic_ai` n'est importé que dans `adaptateurs/llm/`. `import-linter` vérifie ces règles en CI.
- **Lancement de la Chaîne** : l'UI démarre `usine rapport` en sous-processus. Elle lit `sorties/progression/<passage_id>.jsonl` en ouvrir-lire-fermer. Les étapes suivent l'énumération figée `Etape`, avec les statuts en cours, réussie, `sautee` et en échec, plus leur durée. En échec, l'UI nomme l'étape fautive et n'affiche aucun rapport partiel. La durée mesurée vient des horodatages du manifeste.
- **Outils de l'Agent** : exactement `get_meteo`, `list_anomalies` (filtres Entité, Gravité, Phase, statut), `get_tendance`, `get_prevision` et `get_risques`. Leurs signatures et résultats sont des contrats de `contrats.agent`, servis par `Consultation`. `OutilAgent` est une `@dataclass(frozen=True)`.
- **Passerelle LLM** : l'Agent passe par `ia.passerelle`, tâche `agent`, et la méthode `executer_agent` du port `FournisseurLLM` (`output_type=str`, jamais combinée à un schéma de sortie). La passerelle enveloppe chaque outil pour que son résultat soit pseudonymisé et tracé avant d'atteindre le fournisseur. L'ordre est imposé : Pseudonymisation → cache → fournisseur → contrôle → ré-identification → trace. Les tests utilisent `FournisseurFactice`.
- **Contrôles partagés** : `ia.controles` fournit `controler_nombres` et `controler_citations`. Pour l'Agent, les valeurs et tickets autorisés sont ceux des résultats d'outils de la conversation. Sont ignorés les clés de ticket, `IND-n`, `ENT-x`, `J-n` et les jetons de Pseudonymisation. Les nombres sont lus au format français. La même logique sert à la suite d'évaluation.
- **Traces de l'Agent** : elles vont dans `sorties/agent/<AAAA-MM-JJ>/<session>.jsonl`, jamais dans un Passage (immuable), et ne contiennent que du texte pseudonymisé.
- **Vue côte à côte** : elle passe par `Pseudonymiseur.apercu(texte)`, exposé à l'UI par la composition.
- **Mode repli versionné** : `demo/repli/passage/` contient la copie d'un Passage publié entièrement fictif. `demo/repli/agent/*.json` contient des `ReponseAgentEnregistree` (`contrats.llm`), produites par `usine agent --enregistrer` et portant le `passage_id` de la copie. Un `passage_id` différent entraîne un refus avec un message explicite. En Mode repli, les questions enregistrées sont proposées en choix fermés, sans saisie libre.
- **Configuration** : `config/demo.yaml` est validé par un modèle de `contrats.config`. Chaque clé porte un commentaire en français, et une erreur nomme le fichier, la clé et la valeur. Les secrets viennent uniquement des variables d'environnement.

## UX & Interaction Patterns

- Aucun document UX : les contenus sont fixés par les exigences, et la mise en page revient à la lane.
- Navigation en étoile autour de la carte météo. Chaque Entité y figure avec sa Météo, une flèche de tendance J-1 / J-5 et sa Règle déclenchante principale.
- Un bandeau « Mode repli » est visible en permanence quand le mode est actif.
- Un sélecteur de Palier sur le détail d'Entité montre ce qu'apporte la couche LLM. En Palier 2, chaque Citation de l'Explication est un lien Jira, et le nombre de phrases retirées est affiché. La narration de la Prévision remplace la Prévision brute seulement si elle a passé le contrôle.
- L'écran outillage affiche la fiche de `docs/` en lecture seule, sans en dupliquer le texte dans `ui/`.
- Le script de la démo suit cet ordre : avant / après → lancement en direct → Météo (A rouge, Règle, Explication) → Prévision (A sort, B non) → Agent → écran outillage.

## Cross-Story Dependencies

- Stories 7.1 à 7.6 : elles exigent la Consultation complète (Story 5.2). Elles s'appuient sur l'UI minimale du walking skeleton (Story 0.8 : carte, lancement, bandeau).
- Stories 7.7 à 7.12 : elles viennent après l'Epic 6 (passerelle, contrôleurs, Pseudonymisation, Explication et narration).
- Story 7.5 : elle exige la fiche de la Story 8.1. La Story 7.12 conditionne la validation de la Story 8.2.
- Story 7.8 précède 7.9, qui précède 7.10 et 7.11. Story 7.6 précède 7.11.
- La Story 7.12 suppose toutes les autres stories terminées.
- Pour la recette finale, les Scénarios A, B et C doivent être calés (Epic 1) et les Prévisions disponibles (Epic 4).
