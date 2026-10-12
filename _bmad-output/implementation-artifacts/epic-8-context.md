# Epic 8 Context: Dossier de portage (L8 Portage)

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Rendre crédible le portage du démonstrateur sur l'outillage que le client fournira (VM Python, Dataiku, Power Platform, poste seul). Le Sponsor reçoit une fiche d'une page qui priorise l'outillage à demander, montre comment chaque brique se porte sur chaque cible et signale les points d'attention. La démo et la fiche passent ensuite la validation du Responsable de mission (jalon M7), porte hors logiciel exigée avant toute présentation à un client. L'epic est purement documentaire : la lane L8 n'écrit que dans `docs/`.

## Stories

- Story 8.1 : Fiche « outillage demandé » et note de portage courte
- Story 8.2 : Validation par le Responsable de mission (M7)
- Story 8.3 : [BONUS] Conteneur et note de portage détaillée

## Requirements & Constraints

Énoncés exacts à citer (la Story 8.1 doit rattacher chaque affirmation de portabilité à AD-1, AD-19 et NFR-8) :

- **FR-47 [INDISPENSABLE]**, source `_bmad-output/planning-artifacts/prds/prd-usine-migration-jira-demo-2026-10-10/prd.md` (§ 4.10) : « Le dépôt contient une fiche d'une page : liste priorisée des demandes d'outillage (spec § 8), tableau de correspondance par brique et, pour chaque cible, les points d'attention du portage. »
- **FR-48 [BONUS]**, même fichier : « Le dépôt contient une image conteneur exécutable de la Chaîne de reporting et une note de portage détaillée vers Dataiku et Power Platform. »
- **NFR-8 Portabilité**, même fichier (§ 5) : « Le cœur (extraction, Instantanés, KPI, Météo, Prévision, rendu) ne dépend d'aucun service propriétaire autre que Jira et s'exécute sur un poste seul. Toute variation d'environnement passe par la configuration. »
- **NFR-13 Validation avant présentation**, même fichier : « La démo et la fiche FR-47 sont validées par le Responsable de mission avant toute présentation à un client. C'est une porte de passage hors logiciel, tracée dans le journal du jalon M7. »
- **NFR-4 Dépôt public** : tout fictif, aucun secret, aucun nom réel de client (contrôle de secrets en CI).

Contenu de référence de la fiche. Source : `SPEC-usine-migration-jira-demo.md` (racine du dépôt), § 8 « Correspondance avec l'outillage cible et liste des demandes ». L'addendum (`_bmad-output/planning-artifacts/prds/prd-usine-migration-jira-demo-2026-10-10/addendum.md`, § G « Correspondance avec l'outillage cible ») impose : « Reprendre tel quel le tableau de la spec § 8 dans la fiche FR-47. »

Correspondance par brique (spec § 8) :

| Brique | Serveur / VM Python | Dataiku | Power Platform | Poste local seul |
|---|---|---|---|---|
| Extraction Jira | ✅ | ✅ recette Python | ✅ connecteur Jira (limité sur le changelog et les volumes) | ✅ |
| KPI, météo | ✅ | ✅ recettes et scénarios | ⚠️ possible, peu maintenable | ✅ |
| Prévision ML | ✅ | ✅ (Visual ML) | ❌ | ✅ |
| LLM | ✅ endpoint validé | ✅ LLM Mesh | ✅ AI Builder / Copilot Studio | ⚠️ modèle local uniquement |
| Excel / PPT | ✅ | ✅ | ✅ | ✅ |
| Agent conversationnel | ✅ | ✅ (agents Dataiku) | ✅ Copilot Studio | ✅ |
| Planification | ✅ cron | ✅ scénarios | ✅ Power Automate | ⚠️ poste allumé |

Demandes d'outillage, par ordre de priorité (spec § 8) :
1. **Compte de service Jira en lecture seule + jeton API.** Indispensable pour le palier 1.
2. **Environnement d'exécution Python** (VM ou Dataiku) avec accès réseau à Jira, plus un dépôt Git interne.
3. **Ordonnanceur et cible de publication** (SharePoint ou partage réseau).
4. **Endpoint LLM validé par la banque.** Palier 2. À défaut, modèle on-prem.

Contraintes de la fiche (Story 8.1) : une page ; liste priorisée ; tableau par brique couvrant au moins extraction, calcul, Météo, Prévision, rendu, LLM, UI ; points d'attention pour chaque cible (VM Python, Dataiku, Power Platform, poste seul) ; aucun nom réel de client. Le PRD et la spec rattachent la fiche au risque « promesse non tenable sur l'outillage réel (Data Center, réseau, droits) », dont les autres mitigations sont l'adaptateur Data Center (FR-7) et les Paliers dissociés (FR-28 : le Palier 1 fonctionne sans LLM).

## Technical Decisions

Énoncés exacts, source `_bmad-output/planning-artifacts/architecture/architecture-usine-migration-jira-demo-2026-10-10/ARCHITECTURE-SPINE.md`. Le spine précise que « NFR-8 est tenu par AD-1 et AD-19 ».

- **AD-1 : Hexagonal, racine de composition unique.** Rule : « seuls `composition.py` et les modules `cli` importent `usine.adaptateurs`. Le domaine n'importe ni I/O, ni `datetime.now`, ni `random` : la Date d'arrêté et la graine sont passées en paramètre. `import-linter` refuse toute importation absente du tableau des couches. La composition de `usine rapport` ne lit jamais `JIRA_TOKEN_INJECTION`. » Le tableau des couches fait foi et `import-linter` le vérifie en CI.
- **AD-19 : Configuration et secrets.** Rule :
  - Fichiers : la configuration se lit dans `config/*.yaml` (`programme`, `grille_meteo`, `chaine`, `jira`, `llm`, `pseudonymisation`, `demo`), chaque fichier validé par un modèle de `contrats.config`, au chargement, dans `usine.config` seulement.
  - Erreurs et commentaires : une erreur nomme le fichier, la clé et la valeur ; chaque clé porte un commentaire en français, vérifié par un test.
  - Secrets : uniquement par variables d'environnement (`JIRA_EMAIL`, `JIRA_TOKEN_LECTURE`, `JIRA_TOKEN_INJECTION`, `JIRA_DC_PAT`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `USINE_CLE_PSEUDO`) ; `.env` ignoré par git, `.env.example` sans valeur ; gitleaks en CI.
  - Mode repli : activé par `USINE_MODE_REPLI=1` ou la bascule de l'UI, jamais automatiquement.
  - Garde-fou FR-2 : `usine.config` refuse un modèle de classification égal au `modele_corpus` de l'en-tête du Journal.
- **AD-21 : Propriété des répertoires par lane.** Rule (extraits utiles à L8) : « Chaque lane n'écrit que dans ses chemins de la *Carte des lanes* et dans leurs tests miroirs. » L8 Portage écrit seulement dans `docs/`. `_bmad-output/implementation-artifacts/` est modifiable par toute lane. Sont propriété de `main` : `contrats/`, `ports/`, `config/` (le chargeur), `config/chaine.yaml`, `composition.py`, `cli.py`, `pyproject.toml`, `uv.lock`, `.github/`, `.env.example`, `tests/conftest.py`, `tests/contrat/`, `tests/doublures/`, `tests/depot/` ; une lane qui en a besoin ouvre une PR courte sur `main`. En CI, `.github/scripts/controle_lanes.py` vérifie sur les branches `lane/<n>-*` que tous les fichiers modifiés sont dans la lane.
- **Conséquence pour la Story 8.3 (bonus)** : le `Dockerfile` à la racine sort des chemins de L8, d'où une PR dédiée sur `main` ; la note détaillée va dans `docs/portage-detaille.md`. Le spine ne prévoit pas de conteneur en v1.
- **Faits d'architecture citables dans les points d'attention** : un seul environnement (le poste local, un `.env` par worktree) plus la CI GitHub Actions sous Windows et Linux ; Jira Cloud (API v3) et Data Center (API v2) choisis par configuration ; extraction en lecture seule, seul l'injecteur écrit dans Jira ; couche LLM derrière un port unique (Anthropic, Mistral, mode local en bonus) ; étapes LLM `sautee` en Palier 1.

## UX & Interaction Patterns

- La fiche est affichée telle quelle par l'écran « Ce qu'il faut pour le faire en vrai » de l'UI (dernière étape, 1 minute, du script de démo de 10 minutes). L'UI lit le fichier de `docs/` en lecture seule, sans en recopier le texte dans `ui/`. La fiche doit donc se lire seule, en Markdown simple.
- Langue : français (NFR-11).

## Cross-Story Dependencies

- Story 8.1 peut démarrer à tout moment (E0 → L8). Elle est prérequise de la Story 7.5 (écran « Ce qu'il faut pour le faire en vrai », lane L7), qui affiche `docs/fiche-outillage.md`.
- Story 8.2 dépend de la Story 7.12 (répétitions chronométrées de la démo, L7) et de la Story 8.1. C'est le dernier indispensable du projet. La validation (date, version du dépôt, réserves) et la levée des réserves sont consignées dans le journal du jalon M7 sous `docs/`.
- Story 8.3 [BONUS] ne démarre qu'après toutes les stories indispensables. Elle exige une PR sur `main` pour le `Dockerfile` (AD-21) et une Chaîne Palier 1 complète (Epics 1 à 5).
