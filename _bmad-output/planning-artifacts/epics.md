---
status: final
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-usine-migration-jira-demo-2026-10-10/prd.md
  - _bmad-output/planning-artifacts/prds/prd-usine-migration-jira-demo-2026-10-10/addendum.md
  - _bmad-output/planning-artifacts/architecture/architecture-usine-migration-jira-demo-2026-10-10/ARCHITECTURE-SPINE.md
  - docs/QUESTIONS.md
---

# usine-migration-jira-demo - Découpage en epics

## Vue d'ensemble

Ce document découpe en epics et stories implémentables les exigences du PRD (FR-1 à FR-51, NFR-1 à NFR-13), de son addendum technique et du spine d'architecture (AD-1 à AD-24). Aucun document UX n'existe : la mise en page relève de L5 et L7 (spine, *Différé*). Les identifiants `FR-n`, `NFR-n` et `AD-n` sont repris tels quels. Vocabulaire : Glossaire du PRD (§ 3).

## Inventaire des exigences

### Exigences fonctionnelles

**4.1 Programme fictif et générateur de données**
- FR-1 [INDISPENSABLE] Configuration du Programme (Entités, Vagues, Domaines, calendrier des Phases, volumétrie) dans un fichier de configuration ; changer la volumétrie ne demande aucun code ; aucun nom réel.
- FR-2 [INDISPENSABLE] Génération reproductible par graine d'Anomalies, Cas de test et Certifications avec 8 semaines d'historique (Journal d'événements) ; Corpus de textes généré une fois par un LLM distinct du classifieur et versionné ; historique terminé au dernier Jour ouvré avant la génération ; 3 000 à 5 000 Anomalies, 200 à 500 Entrées/semaine, 10 Entités ; Cause racine portée mais non exposée dans Jira.
- FR-3 [INDISPENSABLE] Scénarios de démo A, B, C avec la Grille par défaut (A rouge à partir de S6 avec sortie projetée ; B rouge de S2 à la fin, sans sortie ; C vert→jaune→orange avec Risque d'entrée en rouge) ; hors A/B/C, aucune Entité rouge > 3 Jours ouvrés consécutifs et ≥ 80 % vert/jaune ; au plus 2 rouges en fin d'historique.
- FR-4 [INDISPENSABLE] Identifiants sensibles fictifs (comptes, clients, identifiants) dans ≥ 10 % des descriptions, au format plausible mais invalide.
- FR-5 [INDISPENSABLE] Injection dans Jira Cloud Free de l'état courant et des champs Entité, Vague, Domaine, Gravité, Phase ; recrée projet/types/workflow/champs sur site vierge ; réinjection idempotente ; clés stables ou table de correspondance ; URL en configuration ; seul composant écrivain, identifiant distinct.

**4.2 Extraction Jira**
- FR-6 [INDISPENSABLE] Extraction incrémentale Jira Cloud (API v3) des tickets modifiés depuis le dernier Passage réussi, avec changelog ; un 2ᵉ Passage sans modification ne change rien ; une coupure n'avance pas le repère.
- FR-7 [INDISPENSABLE] Adaptateur Jira Data Center (API v2) sélectionné en configuration ; mêmes tests que Cloud sur fixtures ; aucun vrai DC requis.
- FR-8 [INDISPENSABLE] Journal d'événements comme seule source, même modèle de sortie ; toute Date d'arrêté calculable depuis le seul Journal.
- FR-49 [INDISPENSABLE] Source composite : Journal jusqu'à la Date d'injection, changelog Jira après ; Jira fait foi ; Instantané(Journal) = Instantané(Jira) à la Date d'injection ; une mise à jour Jira apparaît au Passage suivant.
- FR-9 [INDISPENSABLE] Extraction en lecture seule, vérifiée par test.

**4.3 Instantanés et KPI**
- FR-10 [INDISPENSABLE] Instantané par Entité pour toute Date d'arrêté de l'historique ; ne dépend que des événements ≤ la date.
- FR-11 [INDISPENSABLE] KPI quotidiens par Entité et Programme : stock par Gravité et Phase ; Entrées/Sorties du jour et de la Fenêtre glissante ; âge médian et maximum en Jours ouvrés ; taux de KO et de non-exécution par Phase ; Certifications par statut.
- FR-12 [INDISPENSABLE] Tendances hebdomadaires sur 8 semaines (valeur du dernier Jour ouvré, Entrées et Sorties cumulées).
- FR-13 [INDISPENSABLE] Réconciliation avec le Rapport de référence (jeu réduit figé, ~2 Entités, ~60 tickets, 1 Date d'arrêté, chaque indicateur et garde-fou) ; égalité stricte à 100 %.
- FR-14 [INDISPENSABLE] Rejeu idempotent (Instantanés, KPI, Météo, Prévisions, Rapport quotidien identiques hors horodatage) ; en Palier 2, réutilisation du cache LLM à versions identiques.

**4.4 Météo par règles**
- FR-15 [INDISPENSABLE] Grille de météo en configuration commentée en français (seuils, garde-fous, activation) ; seuils par défaut du PRD § 4.4 ; chaque Météo rattachée à sa version de Grille.
- FR-16 [INDISPENSABLE] Calcul de la Météo, « la couleur la plus grave l'emporte » ; trajectoires FR-3 vérifiées au jour près par un test.
- FR-17 [INDISPENSABLE] Restitution des Règles déclenchantes de la couleur retenue avec valeur, seuil et tickets en cause (IND-1/2/3 : Anomalies ; IND-4/8 : Cas de test KO ; IND-5/6 : Certifications ; IND-7 : Anomalies entrées et sorties).
- FR-18 [INDISPENSABLE] Validation de la Grille au chargement ; message nommant fichier, règle, valeur ; refus d'un orange plus sévère que le rouge, d'un indicateur ou d'une couleur inconnus.
- FR-19 [INDISPENSABLE] Météo de J-1 et J-5 par Entité, changements de couleur signalés.

**4.5 Prévision**
- FR-20 [INDISPENSABLE] Prévision de sortie du rouge par Baseline (vélocité nette sur 10 Jours ouvrés, horizon 10) : date, fourchette, probabilité, facteurs explicatifs ; « pas de sortie projetée » si vélocité nulle ou défavorable ; « règle non projetable : IND-x » hors IND-1 ; A sort, B ne sort pas.
- FR-21 [INDISPENSABLE] Risque d'entrée en rouge (projection linéaire d'IND-1, IND-3, IND-4 à 5 Jours ouvrés) avec l'indicateur concerné ; C signalée.
- FR-51 [INDISPENSABLE] Évaluation de la Baseline sur le Public Jira Dataset (protocole de l'addendum § E) ; Brier, AUC, erreur sur le stock publiés ; meilleur Brier que la prévision naïve.
- FR-22 [BONUS] Modèle ML (probabilité de résolution d'une bloquante sous N Jours ouvrés) entraîné sur le Public Jira Dataset, qui bat la Baseline en AUC et Brier ; agrégation par Entité ; anticipe A et B.
- FR-23 [BONUS] Facteurs explicatifs du Modèle ML lisibles par le Pilote.
- FR-24 [INDISPENSABLE] Narration LLM de la Prévision sans chiffre propre ; contrôle déterministe des nombres, sinon Prévision brute affichée.

**4.6 Rapport quotidien**
- FR-25 [INDISPENSABLE] Commande unique enchaînant toutes les étapes ; Date d'arrêté par défaut = dernier Jour ouvré écoulé ; fichiers nommés par la Date d'arrêté ; en échec : code non nul, étape nommée, aucun fichier déposé.
- FR-26 [INDISPENSABLE] Classeur Excel en 9 onglets (PRD § 4.6) ; chiffres identiques aux Instantanés (test).
- FR-27 [INDISPENSABLE] PowerPoint en 7 sections sur gabarit neutre, une slide par Entité rouge ou orange ; chiffres identiques (test).
- FR-28 [INDISPENSABLE] Palier 1 seul : Rapport complet, zones de commentaire « commentaire non généré (Palier 1) ».
- FR-29 [INDISPENSABLE] Chaque clé de ticket affichée (Excel, PowerPoint, interface) est un lien Jira.

**4.7 Couche LLM (Palier 2)**
- FR-30 [INDISPENSABLE] Fournisseur et modèle LLM en configuration ; Anthropic + Mistral opérationnels ; reprise sur dépassement de débit avec attente croissante et tentatives maximales en configuration, testée sur doublure.
- FR-31 [INDISPENSABLE] Pseudonymisation avant tout appel LLM (clés de ticket exclues) ; aucun identifiant injecté dans requêtes ni traces (test) ; ré-identification locale ; vue côte à côte original / pseudonymisé.
- FR-32 [INDISPENSABLE] Explication sourcée pour chaque Entité rouge ou orange ; chaque phrase cite ≥ 1 ticket ; contrôle déterministe des Citations (existence, Entité, tickets en cause FR-17) ; retrait de phrase, compteur affiché et journalisé ; > 50 % retirées → une régénération, puis « explication indisponible ».
- FR-33 [INDISPENSABLE] Brouillon de commentaire « brouillon IA, à valider » sur la slide de chaque Entité rouge ou orange et dans l'onglet Commentaires ; pas d'édition dans l'interface.
- FR-34 [INDISPENSABLE] Journal de traçabilité local de chaque appel LLM et chaque Prévision (horodatage, Date d'arrêté, Entité, versions prompt/modèle/Grille/données, fournisseur, entrées pseudonymisées, sortie, contrôles).
- FR-35 [INDISPENSABLE] Classification LLM des Causes racines après Pseudonymisation, incrémentale et mise en cache ; classification initiale exclue des budgets NFR-2 et NFR-9 ; suggestion jamais écrite dans Jira ; répartition par Entité alimentant l'Explication et l'onglet Commentaires.
- FR-50 [INDISPENSABLE] Suites d'évaluation LLM versionnées à la demande : classification (vérité terrain + 30 tickets écrits à la main) ; Explication sourcée (10 cas, contrôle des Citations, grille humaine 1 à 5).
- FR-36 [BONUS] Détection de doublons avec score, sans fusion.
- FR-37 [BONUS] Mode LLM local (8 Go de VRAM) via la même interface que FR-30.
- FR-38 [BONUS] Observabilité externe auto-hébergée, sans donnée identifiante.

**4.8 Agent conversationnel**
- FR-39 [INDISPENSABLE] Outils de consultation : Météo et Règles déclenchantes, Anomalies filtrées, Tendances, Prévisions et Risques, pour toute Date d'arrêté disponible.
- FR-40 [INDISPENSABLE] Chaque nombre d'une réponse provient d'un résultat d'outil de la conversation, chaque ticket cité existe ; zéro chiffre inventé (contrôle automatique) ; « données insuffisantes » si nécessaire.
- FR-41 [INDISPENSABLE] Agent en lecture seule : aucun outil d'écriture (Jira, mail, configuration).
- FR-42 [INDISPENSABLE] Suite d'évaluation de 15 questions avec éléments attendus vérifiés automatiquement, dont la question de la démo et ≥ 2 questions sans réponse possible.

**4.9 Interface de démonstration**
- FR-43 [INDISPENSABLE] Écrans : carte météo, détail d'Entité (Règles, KPI, Explication avec liens, Prévision et facteurs), Agent, lancement de la Chaîne avec progression par étape, écran « Ce qu'il faut pour le faire en vrai » ; chaque écran à un clic de la carte météo.
- FR-44 [INDISPENSABLE] Avant / après : temps manuel déclaré (configuration) contre temps mesuré du dernier Passage, par Rapport et cumulé sur 5 Rapports.
- FR-45 [INDISPENSABLE] Mode repli : dernier Passage enregistré, réponses enregistrées de l'Agent rejouées, mention « Mode repli » permanente, liens Jira inactifs possibles.
- FR-46 [INDISPENSABLE] Comparaison d'une Entité avec et sans couche LLM.

**4.10 Portabilité**
- FR-47 [INDISPENSABLE] Fiche d'une page « outillage demandé » : demandes priorisées, correspondance par brique, points d'attention par cible.
- FR-48 [BONUS] Image conteneur de la Chaîne et note de portage détaillée Dataiku / Power Platform.

### Exigences non fonctionnelles

- NFR-1 Chiffres déterministes : aucun KPI, Météo ou Prévision calculé par un LLM ; les sorties LLM ne reprennent que des valeurs calculées (FR-24, FR-40).
- NFR-2 Performance : Rapport quotidien Palier 1 < 5 min (extraction incrémentale comprise) ; Palier 2 < 10 min pour ≤ 4 Entités rouges ou oranges ; poste consigné dans le README.
- NFR-3 Reproductibilité : données par graine, Rejeu idempotent, réinjection idempotente.
- NFR-4 Dépôt public : tout fictif, aucun secret, contrôle de secrets en CI.
- NFR-5 Confidentialité des envois LLM : Pseudonymisation systématique, aucun identifiant sensible dans journaux et traces.
- NFR-6 Auditabilité : Météo → version de Grille ; sortie LLM et Prévision → versions de prompt, modèle, Grille, données.
- NFR-7 Tests : CI verte à chaque jalon ; aucun appel LLM ou Jira réel dans les tests unitaires ; évaluations LLM en suites séparées à la demande.
- NFR-8 Portabilité : cœur sans service propriétaire autre que Jira, exécutable sur un poste seul ; variations d'environnement par configuration.
- NFR-9 Coût : infrastructure gratuite ; Passage de démo complet < 1 € de LLM (classification initiale exclue) ; limites de débit respectées.
- NFR-10 Lisibilité métier : chaque clé de Grille et de configuration commentée en français (test) ; erreurs nommant fichier, clé, valeur.
- NFR-11 Langue : interface, Rapport et sorties LLM en français.
- NFR-12 Robustesse de la démo : démo jouable sans réseau en Mode repli, Agent compris.
- NFR-13 Validation avant présentation par le Responsable de mission, tracée au journal du jalon M7 (porte hors logiciel).

### Exigences complémentaires (architecture)

**Démarrage (pas de gabarit tiers)** : aucun starter externe. Le projet démarre par l'epic E0 walking skeleton du spine (E0-1 à E0-9), séquentiel sur `main` : `uv init`, `pyproject` (ruff, mypy, import-linter, pytest), CI Windows + Linux. Critère de sortie : `usine rapport` publie un Passage de bout en bout sur le mini-jeu, CI verte, étiquette `contrats-v1` posée.

**Structure et règles transverses**
- AD-1 Hexagonal, racine de composition unique ; domaine sans I/O, horloge ni hasard ; `import-linter` vérifie le tableau des couches en CI ; `usine rapport` ne lit jamais `JIRA_TOKEN_INJECTION`.
- AD-2 Contrats d'abord : toute forme inter-paquets dans `usine.contrats` ; Pydantic `frozen` ou `polars.DataFrame` validé par `valider()` ; `contrats_version` dans chaque fichier ; `contrats/` et `ports/` modifiés seulement sur `main` par PR dédiée.
- AD-3 Événement canonique unique `Evenement` (identifiants déterministes, dédoublonnage par `id_evenement`) ; Journal JSONL précédé d'un `EnteteJournal`.
- AD-4 Injection par API REST seulement ; `ManifesteInjection` ; coupure par instants (`horodatage_fin_injection`) ; clé canonique = clé Jira ; événements `alignement` (H-27) ; test de cohérence FR-49.
- AD-5 Transport `jira_http` commun ; `ClientJiraLecture` à liste blanche `(méthode, gabarit)` testée sur Cloud et DC ; seul l'injecteur écrit, avec `JIRA_TOKEN_INJECTION` ; l'Agent n'accède pas à Jira.
- AD-6 `donnees/entrepot.duckdb`, ouvert seulement par l'étape `extraction` ; événements et repère validés dans une seule transaction ; verrou `donnees/.verrou-passage` ; incrémental avec marge.
- AD-7 Passage construit dans `.en-cours-<id>/`, publié par renommage atomique, déplacé sous `sorties/echecs/` en échec ; immuable ; autoportant ; dernier Passage via `consultation.dernier_passage()` ; rendu déterministe pour le Rejeu, liste nommée d'exclusions qualifiées par fichier (`EXCLUSIONS_REJEU`, amendement du 2026-10-12).
- AD-8 Énumération `Etape` figée (`extraction … rendu`) ; Palier = `ConfigChaine.palier` ; point d'entrée `usine rapport [--date-arrete]` ; progression dans `sorties/progression/<id>.jsonl` ; durées, drapeau `classification_initiale` et coût au manifeste.
- AD-9 Calculs métier en Polars, fonctions pures dans `domaine/` seulement ; DuckDB stocke sans calculer ; rendu, UI, IA et Agent n'affichent que des valeurs de `consultation`.
- AD-10 Comptes entiers ; taux en `numerateur`/`denominateur` ; comparaisons en `Fraction` ; statut `non_evaluable` explicite ; Rapport de référence = mini-Journal + YAML attendu dans `tests/fixtures/reference/`.
- AD-11 `Consultation`, lecteur unique d'un Passage ; `url_ticket(cle)` (None en Mode repli) ; `contrats.format` ; filtre `palier` ; aperçu de Pseudonymisation via la composition.
- AD-12 Passerelle LLM unique, ordre imposé (Pseudonymisation → cache → fournisseur → contrôle → ré-identification → trace) ; `pydantic_ai` confiné à `adaptateurs/llm/` ; clé de cache définie ; cache SQLite WAL ; tâches figées ; dégradation explicite ; coût tracé.
- AD-13 Port `FournisseurLLM` à deux méthodes (`generer_structure`, `executer_agent`) jamais combinées ; outils de l'Agent enveloppés (pseudonymisés, tracés) ; Anthropic puis Mistral ; reprise 429 dans l'adaptateur ; `FournisseurFactice` dans les tests.
- AD-14 Deux contrôleurs partagés `controler_citations` et `controler_nombres` (règles d'ignorance et de format définies).
- AD-15 Presidio + `fr_core_news_md` (L6, `adaptateurs/presidio`) ; moteur par expressions régulières d'E0 conservé en repli (`adaptateurs/pseudonymisation`, L6), même dérivation des jetons ; jetons HMAC dérivés `<TYPE>_<6 hex>` ; table de ré-identification `donnees/pseudonymes.sqlite` hors git ; test de balayage SM-7.
- AD-16 Empreintes définies une fois dans `contrats.versions` ; traces de la Chaîne dans le Passage ; traces de l'Agent dans `sorties/agent/`.
- AD-17 `contrats.calendrier` seule source du temps (Europe/Paris, `jour_ouvre_de`, Fenêtre glissante, J-1, J-5, `semaine_programme`).
- AD-18 Une seule Baseline (`domaine.prevision.baseline` sur `SerieStock`), appelée telle quelle par `evaluation/zenodo` ; Modèle ML au même contrat `Prevision`.
- AD-19 Configuration `config/*.yaml` validée par `contrats.config` dans `usine.config` seulement ; secrets en variables d'environnement ; `.env.example` vide ; gitleaks ; Mode repli manuel ; garde-fou modèle de classification ≠ `modele_corpus`.
- AD-20 Suites de contrat par port dans `tests/contrat/<port>/`, exécutées par tous les adaptateurs ; fixtures Jira enregistrées ; pas de réseau en tests unitaires ; `evaluation/` et `evals/` hors CI.
- AD-21 Propriété des répertoires par lane (carte des lanes) ; fichiers propriété de `main` ; sous-application typer par lane enregistrée en E0 ; contrôle des chemins en CI sur `lane/<n>-*`.
- AD-22 Étapes injectées via `ports.Etape` et registre construit par `composition.py` ; seule `chaine` écrit dans le Passage (le rendu renvoie des octets).
- AD-23 Vocabulaire canonique (`Champ`, domaines de valeurs) dans `contrats.tickets` ; correspondance Jira dans `config/jira.yaml`, appliquée dans les adaptateurs ; `TicketEtat` / `TicketTexte` ; vérité terrain hors `Evenement`, lue seulement par `evals/`.
- AD-24 `demo/repli/passage/` et `demo/repli/agent/*.json` versionnés (`usine agent --enregistrer`) ; questions enregistrées en choix fermés en Mode repli ; Corpus produit par `outils/generer_corpus.py` via `FournisseurLLM`.

**Organisation en lanes (worktrees après `contrats-v1`)**
- Dépendances de recette finale : E0 → L1, L2, L3, L6, L8 ; L3 → L4, L5 ; L5 → L7 ; L6 → L7. Avant, chaque lane travaille sur contrats, doublures et fixtures.
- Répertoires par lane : L1 `generateur/`, `outils/`, `config/programme.yaml`, `donnees/corpus/` ; L2 `adaptateurs/{jira_http,jira_cloud,jira_dc,journal,composite,entrepot_duckdb,cli}`, `config/jira.yaml`, `tests/fixtures/jira_*` ; L3 `domaine/{instantanes,kpi,meteo}`, `config/grille_meteo.yaml`, `tests/fixtures/reference` ; L4 `domaine/prevision`, `evaluation/` ; L5 `chaine/`, `consultation/`, `rendu/`, `gabarits/` ; L6 `ia/` sauf `ia/agent`, `domaine/causes`, `adaptateurs/{llm,presidio,pseudonymisation,stockage_sqlite}`, `config/{llm,pseudonymisation}.yaml`, `evals/` sauf `evals/agent` ; L7 `ia/agent`, `ui/`, `demo/`, `config/demo.yaml`, `evals/agent` ; L8 `docs/`.

**Stack et infrastructure** : Python 3.12, uv, versions figées par le spine (pydantic 2.14, polars 1.44.2, duckdb 1.5.6, pydantic-ai-slim 2.55, presidio 2.2.364, spacy 3.8.16 + `fr_core_news_md` 3.8.0, openpyxl 3.1.5, python-pptx 1.0.2, streamlit 1.65, scikit-learn 1.9.1, pymongo 4.18.3, pytest 9.1.1, ruff 0.17, mypy 2.4, import-linter 2.15, gitleaks v8.30.1) ; CI GitHub Actions Windows + Linux ; un seul site Jira Cloud Free, injection du projet `DEMO` depuis `main`.

**Spikes différés à planifier** : création du workflow et des champs Jira par API (½ jour en début de L1, repli manuel documenté) ; organisation du dump Zenodo (½ jour en début de L4) ; calibrage des modèles par tâche et du plafond de coût (L6) ; quotas Mistral (L6).

### Exigences UX

Aucun document UX (`bmad-ux`) n'a été produit. Les contenus de l'Excel (9 onglets), du PowerPoint (7 sections) et des écrans (FR-43) sont fixés par le PRD ; la mise en page est différée à L5 et L7 (spine, *Différé*). Exigences de présentation tirées du PRD et du spine :
- Formatage français commun (`contrats.format` : milliers à espace insécable, virgule décimale, %, dates) pour Excel, PowerPoint, UI et Agent (AD-11, NFR-11).
- Gabarit PowerPoint neutre et fictif `gabarits/rapport.pptx`, sans charte réelle (FR-27, NFR-4).
- Chaque écran de l'UI à un clic de la carte météo ; bandeau « Mode repli » permanent ; questions enregistrées en choix fermés en Mode repli (FR-43, FR-45, AD-24).

### Carte de couverture des FR

- FR-1 : Epic 1 - Configuration du Programme
- FR-2 : Epic 1 - Génération reproductible et Corpus de textes
- FR-3 : Epic 1 - Scénarios de démo (calage en recette, après l'Epic 3)
- FR-4 : Epic 1 - Identifiants sensibles fictifs
- FR-5 : Epic 1 - Injection idempotente dans Jira Cloud
- FR-6 : Epic 2 - Extraction incrémentale Jira Cloud
- FR-7 : Epic 2 - Adaptateur Jira Data Center
- FR-8 : Epic 2 - Source Journal d'événements (amorcée en Epic 0)
- FR-9 : Epic 2 - Extraction en lecture seule
- FR-49 : Epic 2 - Source composite et test de cohérence
- FR-10 : Epic 3 - Instantané quotidien (amorcé en Epic 0)
- FR-11 : Epic 3 - KPI quotidiens
- FR-12 : Epic 3 - Tendances hebdomadaires
- FR-13 : Epic 3 - Réconciliation avec le Rapport de référence
- FR-14 : Epic 3 - Déterminisme du calcul ; Epic 5 - Rejeu idempotent de bout en bout ; Epic 6 - réutilisation du cache LLM
- FR-15 : Epic 3 - Grille de météo en configuration
- FR-16 : Epic 3 - Calcul de la Météo (amorcé en Epic 0)
- FR-17 : Epic 3 - Restitution des Règles déclenchantes
- FR-18 : Epic 3 - Validation de la Grille
- FR-19 : Epic 3 - Évolution de la Météo J-1 / J-5
- FR-20 : Epic 4 - Prévision de sortie du rouge (Baseline)
- FR-21 : Epic 4 - Risque d'entrée en rouge
- FR-51 : Epic 4 - Évaluation de la Baseline sur le Public Jira Dataset
- FR-22 : Epic 4 - [BONUS] Modèle ML
- FR-23 : Epic 4 - [BONUS] Facteurs explicatifs du Modèle ML
- FR-25 : Epic 5 - Commande unique (amorcée en Epic 0)
- FR-26 : Epic 5 - Classeur Excel 9 onglets
- FR-27 : Epic 5 - PowerPoint 7 sections
- FR-28 : Epic 5 - Fonctionnement en Palier 1 seul
- FR-29 : Epic 5 - Liens vers les tickets (Epic 7 pour l'interface)
- FR-24 : Epic 6 - Narration de la Prévision
- FR-30 : Epic 6 - Fournisseur LLM interchangeable
- FR-31 : Epic 6 - Pseudonymisation (vue côte à côte en Epic 7)
- FR-32 : Epic 6 - Explication sourcée (amorcée en Epic 0)
- FR-33 : Epic 6 - Brouillon de commentaire
- FR-34 : Epic 6 - Journal de traçabilité
- FR-35 : Epic 6 - Classification des Causes racines
- FR-50 : Epic 6 - Suites d'évaluation LLM
- FR-36 : Epic 6 - [BONUS] Détection de doublons
- FR-37 : Epic 6 - [BONUS] Mode LLM local
- FR-38 : Epic 6 - [BONUS] Observabilité externe
- FR-39 : Epic 7 - Outils de consultation de l'Agent
- FR-40 : Epic 7 - Chiffres issus des outils
- FR-41 : Epic 7 - Agent en lecture seule
- FR-42 : Epic 7 - Suite d'évaluation de l'Agent
- FR-43 : Epic 7 - Écrans de démonstration (amorcés en Epic 0)
- FR-44 : Epic 7 - Avant / après
- FR-45 : Epic 7 - Mode repli
- FR-46 : Epic 7 - Comparaison Palier 1 / Palier 2
- FR-47 : Epic 8 - Fiche « outillage demandé »
- FR-48 : Epic 8 - [BONUS] Conteneur et note de portage détaillée

## Liste des epics

**Ordre de réalisation.** Epic 0 → Epics 1 à 5 et stories Palier 1 de l'Epic 7 → **porte Palier 1 (M3)** : Rapport quotidien en moins de 5 minutes, démo Palier 1 jouable → Epic 6 puis stories Palier 2 de l'Epic 7. L'Epic 8 se fait à tout moment ; sa story de validation (NFR-13) vient en dernier. Aucune story `[BONUS]` ne démarre avant la fin de toutes les stories indispensables.

**Dépendances.** Carte des lanes du spine : E0 → L1, L2, L3, L6, L8 ; L3 → L4, L5 ; L5 → L7 ; L6 → L7. Dépendances de recette ajoutées : L3 → recette de L1 (calage des Scénarios, Story 1.8) ; L1 → recette de L2 (FR-49 en direct, Story 2.7) ; L1 et L3 → recette de L4 (SM-6, Story 4.5) ; L1, L2 et L4 → recette de L5 (Story 5.6). Dépendances de story à story entre lanes : Story 2.1 (transport `jira_http`) → Story 1.6 (injection) ; Story 6.1 (adaptateurs LLM) → Story 1.9 (Corpus définitif) → Story 6.9 (évaluation de la classification) ; Story 8.1 → Story 7.5 ; Story 7.12 → Story 8.2. Avant ces recettes, chaque lane travaille sur les contrats, les doublures et les fixtures. Toute modification de `contrats/` ou `ports/` passe par une PR dédiée sur `main` (AD-2).

### Epic 0 : Walking skeleton (E0, sur `main`)
`usine rapport` publie de bout en bout un Passage sur le mini-jeu (Excel à 1 onglet, PowerPoint à 1 slide, carte météo dans l'UI) ; CI verte sous Windows et Linux ; étiquette `contrats-v1` posée.
**FR amorcées :** FR-8, FR-10, FR-16, FR-25, FR-32, FR-43 (tranches fines, terminées dans les lanes). **NFR :** NFR-2 (mesure), NFR-4, NFR-7, NFR-10.

### Epic 1 : Programme fictif dans Jira (L1 Données)
L'auteur génère le Programme fictif, ses 8 semaines d'historique et ses trois Scénarios de démo, puis l'injecte dans Jira Cloud Free de façon idempotente.
**FR couvertes :** FR-1, FR-2, FR-3, FR-4, FR-5. **NFR :** NFR-3, NFR-4, NFR-10.

### Epic 2 : Extraction fiable de l'historique (L2 Extraction)
Le Pilote dispose de l'historique complet des tickets depuis Jira Cloud, Jira Data Center ou le seul Journal, de façon incrémentale et en lecture seule, Jira faisant foi.
**FR couvertes :** FR-6, FR-7, FR-8, FR-9, FR-49. **NFR :** NFR-7, NFR-8.

### Epic 3 : Météo calculée et justifiée (L3 Calcul)
Le Pilote obtient Instantanés, KPI, Tendances et Météo par règles, avec les Règles déclenchantes et leurs tickets en cause, réconciliés à 100 % avec le Rapport de référence.
**FR couvertes :** FR-10 à FR-19 (FR-14 pour le déterminisme du calcul). **NFR :** NFR-1, NFR-3, NFR-6, NFR-10.

### Epic 4 : Prévision de sortie du rouge (L4 Prévision)
Le Pilote sait quand une Entité rouge devrait sortir et quelles Entités risquent d'y entrer, avec une méthode évaluée sur données réelles publiques.
**FR couvertes :** FR-20, FR-21, FR-51 ; bonus FR-22, FR-23. **NFR :** NFR-1.

### Epic 5 : Rapport quotidien en une commande (L5 Rapport)
Le Pilote produit en une commande, en moins de 5 minutes, l'Excel en 9 onglets et le PowerPoint en 7 sections d'une Date d'arrêté, rejouables à l'identique. Porte Palier 1 (M3).
**FR couvertes :** FR-25, FR-26, FR-27, FR-28, FR-29 ; recette de bout en bout de FR-14. **NFR :** NFR-2, NFR-3.

### Epic 6 : Couche LLM sourcée et contrôlée (L6 Couche LLM)
Le Rapport quotidien s'enrichit des Causes racines proposées, d'Explications sourcées, de Brouillons de commentaire et d'une narration de la Prévision, pseudonymisés, contrôlés, mis en cache et tracés.
**FR couvertes :** FR-24, FR-30, FR-31, FR-32, FR-33, FR-34, FR-35, FR-50 ; bonus FR-36, FR-37, FR-38. **NFR :** NFR-1, NFR-2 (Palier 2), NFR-5, NFR-6, NFR-9.

### Epic 7 : Interface de démo et Agent (L7 Agent et UI)
Le Pilote et l'auteur disposent des écrans de la démo de 10 minutes (avant / après, Mode repli, comparaison des Paliers), puis d'un Agent en lecture seule évalué sur 15 questions. Stories Palier 1 avant la porte M3, stories Palier 2 après l'Epic 6.
**FR couvertes :** FR-39 à FR-46. **NFR :** NFR-1, NFR-5, NFR-11, NFR-12.

### Epic 8 : Dossier de portage (L8 Portage)
Le Sponsor dispose d'une fiche d'une page qui liste l'outillage demandé et les points d'attention du portage ; la démo est validée par le Responsable de mission.
**FR couvertes :** FR-47 ; bonus FR-48. **NFR :** NFR-8, NFR-13.

## Epic 0 : Walking skeleton (E0, sur `main`)

`usine rapport` publie de bout en bout un Passage sur le mini-jeu ; la CI est verte sous Windows et Linux ; l'étiquette `contrats-v1` est posée. Stories séquentielles sur `main`, chaque couche traversée une fois (spine, *Epic E0*). Les répertoires touchés sont propriété de `main` ou amorcés pour les lanes.

### Story 0.1 : Socle du dépôt (E0-1)

As a auteur du démonstrateur,
I want un dépôt outillé (uv, ruff, mypy, import-linter, pytest, CI Windows + Linux, gitleaks, chargeur de configuration),
So that chaque lane démarre sur des règles vérifiées automatiquement plutôt que sur des conventions orales.

**Exigences :** NFR-4, NFR-7, NFR-8, NFR-10 · **AD :** AD-1, AD-19, AD-20, AD-21 · **Écrit dans :** `pyproject.toml`, `uv.lock`, `.github/`, `.env.example`, `src/usine/config/`, `src/usine/cli.py`, `tests/conftest.py`

**Acceptance Criteria:**

**Given** un clone frais sous Windows ou Linux avec Python 3.12 et uv
**When** l'auteur lance `uv sync` puis `uv run pytest`
**Then** l'environnement s'installe aux versions du spine (*Stack*), `fr_core_news_md` 3.8.0 compris (roue référencée par URL)
**And** les tests passent sans accès réseau (marqueur `@pytest.mark.reseau` exclu par défaut)

**Given** le tableau des couches du spine
**When** `[tool.importlinter]` est exécuté en CI
**Then** il reprend tel quel les contrats `layers` et `forbidden` du tableau
**And** une importation de `usine.adaptateurs` depuis `usine.domaine` fait échouer la CI (test de non-régression du contrat)

**Given** un push sur n'importe quelle branche
**When** le workflow GitHub Actions tourne sur Windows et Linux
**Then** il enchaîne ruff, mypy, import-linter, pytest et gitleaks v8.30.1
**And** sur une branche `lane/<n>-*`, un contrôle échoue si un fichier modifié sort des répertoires de la lane n (carte des lanes, AD-21)

**Given** un fichier `config/*.yaml` avec une clé de type erroné
**When** le chargeur `usine.config` le lit
**Then** il lève une `UsineErreur` qui nomme le fichier, la clé et la valeur fautive
**And** un test vérifie que chaque clé des YAML livrés porte un commentaire en français (NFR-10)

**Given** le dépôt
**When** on inspecte `.env.example` et `.gitignore`
**Then** `.env.example` liste `JIRA_EMAIL`, `JIRA_TOKEN_LECTURE`, `JIRA_TOKEN_INJECTION`, `JIRA_DC_PAT`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `USINE_CLE_PSEUDO`, `USINE_MODE_REPLI` sans valeur
**And** `.env`, `donnees/` (hors `donnees/corpus/`) et `sorties/` sont ignorés par git

**Given** l'application typer `usine`
**When** on lance `usine --help`
**Then** les sous-applications des paquets (`generateur`, `chaine`, `ia`, `ui`, etc.) sont enregistrées une fois dans `cli.py`, chacune depuis `<paquet>/cli.py` (AD-21)

### Story 0.2 : Contrats v0 et ports (E0-2)

As a auteur travaillant en lanes parallèles,
I want tous les contrats et ports du spine définis dans leur forme complète, avec les doublures et les suites de contrat câblées,
So that chaque lane code contre une forme unique et testable sans attendre les autres.

**Exigences :** NFR-1, NFR-6, NFR-7 · **AD :** AD-2, AD-3, AD-8, AD-10, AD-11, AD-13, AD-16, AD-17, AD-20, AD-22, AD-23 · **Écrit dans :** `src/usine/contrats/`, `src/usine/ports/`, `tests/doublures/`, `tests/contrat/`

**Acceptance Criteria:**

**Given** la table *Contrats v1* du spine
**When** on inspecte `usine.contrats`
**Then** chaque contrat listé existe dans le module indiqué (`evenements`, `tickets`, `calcul`, `meteo`, `prevision`, `llm`, `agent`, `trace`, `passage`, `config`)
**And** les enregistrements unitaires sont des modèles Pydantic `frozen=True`, les données tabulaires des schémas Polars `SCHEMA_X`

**Given** un `polars.DataFrame` dont une colonne manque ou a le mauvais type
**When** on appelle `contrats.valider(df, SCHEMA_X)`
**Then** une `UsineErreur` nomme le schéma et la colonne fautive

**Given** les énumérations des *Conventions de cohérence*
**When** on les importe
**Then** `Couleur` est ordonnée `vert < jaune < orange < rouge`, `Etape` suit l'ordre d'AD-8, `Champ` exclut `cause_racine` (AD-23)
**And** les domaines de valeurs canoniques reprennent le workflow et les causes `[HYPOTHÈSE H-17]` `[HYPOTHÈSE H-18]`

**Given** `contrats.calendrier`
**When** on teste `jour_local`, `jour_ouvre_de`, Fenêtre glissante, J-1, J-5 et `semaine_programme`
**Then** un événement du samedi à 23 h UTC est rattaché au lundi suivant (Europe/Paris, H-25) et J-5 d'un lundi est le lundi précédent `[HYPOTHÈSE H-19]`
**And** aucun autre module du dépôt ne redéfinit ces notions (AD-17)

**Given** `contrats.format` et `contrats.versions`
**When** on formate `12345.5` et `Fraction(1, 8)`
**Then** on obtient `12 345,5` (espace insécable) et `12,5 %`
**And** `version_grille`, `version_prompt`, `version_modele` et `version_donnees` sont calculées selon AD-16 et testées sur des entrées fixes

**Given** le répertoire `ports/`
**When** on l'inspecte
**Then** `SourceTickets`, `EntrepotExtraction`, `FournisseurLLM` (deux méthodes `generer_structure` et `executer_agent`), `Pseudonymiseur`, `Consultation` et `Etape` sont des `typing.Protocol`
**And** `Consultation` expose toutes les lectures exigées par FR-17, FR-19, FR-26, FR-27, FR-39, FR-43 à FR-46, plus `url_ticket(cle)`, `dernier_passage()` et le filtre `palier` (AD-2, AD-11)

**Given** `tests/doublures/` et `tests/contrat/`
**When** on lance `pytest tests/contrat`
**Then** `FournisseurFactice` et le `Pseudonymiseur` factice passent leur suite de contrat
**And** les suites `SourceTickets`, `FournisseurLLM`, `Pseudonymiseur` et `Consultation` existent, paramétrées par adaptateur, prêtes à recevoir ceux des lanes (AD-20)

**Given** une enveloppe de fichier de Passage
**When** on la sérialise puis on la relit avec une version majeure différente
**Then** elle porte `contrats_version` et la relecture lève une `UsineErreur` (AD-2)

### Story 0.3 : Mini-générateur déterministe (E0-3)

As a auteur,
I want un mini-générateur qui produit, pour une graine donnée, un Journal JSONL de 2 Entités et environ 30 tickets au vocabulaire canonique,
So that le calcul, la Chaîne et le rendu ont une entrée réelle dès le walking skeleton.

**Exigences :** FR-2 (amorce), NFR-3 · **AD :** AD-1, AD-3, AD-17, AD-23 · **Écrit dans :** `src/usine/generateur/`, `config/programme.yaml` (version réduite)

**Acceptance Criteria:**

**Given** une configuration réduite (2 Entités, ~30 Anomalies, Cas de test et Certifications) et une graine
**When** l'auteur lance la commande de génération avec `--graine 42`
**Then** un Journal JSONL est écrit, précédé d'un `EnteteJournal` (graine, date de génération, Date d'injection, version et `modele_corpus`)
**And** deux exécutions avec la même graine produisent des fichiers identiques octet pour octet

**Given** le Journal produit
**When** on le valide contre `Evenement`
**Then** chaque création est suivie, au même horodatage, d'un `modification_champ` par attribut initial, titre et description compris (AD-3)
**And** les identifiants valent `J-<rang>` et tous les `champ` et `vers` appartiennent aux domaines canoniques de `contrats.tickets` (AD-23)

**Given** le générateur
**When** on inspecte son code
**Then** il ne lit ni `datetime.now` ni `random` global : la date de génération et la graine sont des paramètres (AD-1)
**And** aucun `Evenement` ne porte de Cause racine ; la vérité terrain est écrite à part dans `donnees/verite_terrain.json` (AD-23)

### Story 0.4 : Calcul minimal de la Météo (E0-4)

As a Pilote,
I want qu'une Météo soit calculée à partir du Journal pour IND-1 via une Grille YAML réduite,
So that la chaîne de calcul est prouvée de l'événement à la couleur avant d'être élargie.

**Exigences :** FR-8, FR-10, FR-15, FR-16 (amorces) · **AD :** AD-9, AD-10, AD-17, AD-20, AD-23 · **Écrit dans :** `src/usine/adaptateurs/journal/`, `src/usine/domaine/`, `config/grille_meteo.yaml` (version réduite)

**Acceptance Criteria:**

**Given** le Journal du mini-générateur
**When** `SourceJournal` le lit
**Then** il émet un flux d'`Evenement` conforme et passe la suite de contrat `SourceTickets` (AD-20)

**Given** ce flux et une Date d'arrêté
**When** le domaine calcule les `TicketEtat` puis l'Instantané
**Then** seuls les événements dont `jour_ouvre_de` ≤ Date d'arrêté sont pris en compte (AD-17)
**And** les fonctions sont pures, en Polars, sans I/O (AD-9)

**Given** une Grille réduite à IND-1 (rouge ≥ 3, orange ≥ 1)
**When** le domaine calcule l'Indicateur puis la Météo
**Then** une Entité à 3 Anomalies bloquantes ouvertes est rouge, avec une `RegleDeclenchante` IND-1 qui porte la valeur, le seuil et les clés en cause
**And** une Entité sans bloquante est verte, et chaque Météo porte `version_grille`

### Story 0.5 : Chaîne et Passage atomique (E0-5)

As a Pilote,
I want que `usine rapport` exécute le registre d'étapes et publie un Passage complet ou rien,
So that je ne trouve jamais de Rapport quotidien partiel et que l'UI peut suivre la progression.

**Exigences :** FR-25 (amorce), NFR-2 (mesure) · **AD :** AD-6, AD-7, AD-8, AD-22 · **Écrit dans :** `src/usine/chaine/`, `src/usine/composition.py`, `config/chaine.yaml`

**Acceptance Criteria:**

**Given** le registre construit par `composition.py` (étapes déterministes réelles, étapes LLM `sautee`, autres étapes en bouchon)
**When** l'auteur lance `usine rapport --date-arrete <jour ouvré>`
**Then** le Passage se construit dans `sorties/passages/.en-cours-<passage_id>/` puis est publié par un seul renommage vers `sorties/passages/<date_arrete>/<passage_id>/`
**And** `passage_id` suit le format `AAAAMMJJTHHMMSSZ-<6 hex>` et le manifeste porte la durée de chaque étape

**Given** une étape qui lève une exception
**When** la Chaîne s'exécute
**Then** le répertoire est déplacé sous `sorties/echecs/`, aucun fichier de rapport n'est publié, le code de sortie est non nul et le message nomme l'étape (FR-25)

**Given** une Date d'arrêté tombant un samedi
**When** on lance `usine rapport --date-arrete` sur ce jour
**Then** une `UsineErreur` nomme la date refusée (AD-8)

**Given** un `usine rapport` en cours
**When** un second est lancé
**Then** il échoue proprement en nommant le verrou `donnees/.verrou-passage` (AD-6)

**Given** un Passage en cours
**When** chaque étape démarre puis se termine
**Then** une ligne `EvenementProgression` est ajoutée à `sorties/progression/<passage_id>.jsonl`, hors du répertoire renommé (AD-8)

**Given** un Journal synthétique à la volumétrie cible (5 000 Anomalies, 10 Entités, 8 semaines)
**When** on mesure `usine rapport` en Palier 1
**Then** la durée par étape est consignée dans le README avec les caractéristiques du poste
**And** l'écart à la cible de 5 minutes est signalé, sans être bloquant à ce stade (NFR-2)

### Story 0.6 : Consultation et rendu minimal (E0-6)

As a Pilote,
I want un Excel à 1 onglet Synthèse et un PowerPoint à 1 slide carte météo, lus via `Consultation`,
So that la sortie de la Chaîne est visible dans les formats du comité et rejouable à l'identique.

**Exigences :** FR-26, FR-27, FR-29 (amorces), FR-14 · **AD :** AD-7, AD-9, AD-11, AD-22 · **Écrit dans :** `src/usine/consultation/`, `src/usine/rendu/`, `gabarits/rapport.pptx`

**Acceptance Criteria:**

**Given** un Passage en cours avec Météo calculée
**When** l'étape `rendu` s'exécute
**Then** elle lit les valeurs via `Consultation` uniquement et renvoie les octets du xlsx et du pptx, que `chaine` écrit sous `rapport-AAAA-MM-JJ.xlsx` et `rapport-AAAA-MM-JJ.pptx` (AD-22)

**Given** l'Excel produit
**When** on lit l'onglet Synthèse
**Then** il porte une ligne par Entité avec sa Météo
**And** chaque clé de ticket affichée est un lien construit par `consultation.url_ticket(cle)` (FR-29)

**Given** deux Passages sur la même Date d'arrêté et le même Journal
**When** on compare leurs sorties
**Then** les valeurs des cellules, les textes des slides et les `docProps` sont identiques, hors de la liste nommée d'exclusions d'AD-7

**Given** `Consultation`
**When** on appelle `dernier_passage()`
**Then** il renvoie le Passage publié de `(date_arrete, horodatage_fin)` maximal, sans pointeur mutable
**And** l'implémentation passe la suite de contrat `Consultation`

### Story 0.7 : Passerelle LLM minimale (E0-7)

As a auteur,
I want une passerelle LLM qui pseudonymise, met en cache, appelle `FournisseurFactice`, contrôle les Citations et trace une Explication sourcée,
So that l'ordre imposé de la couche LLM est en place avant que L6 n'y branche de vrais fournisseurs.

**Exigences :** FR-31, FR-32, FR-34 (amorces), NFR-5, NFR-7 · **AD :** AD-12, AD-13, AD-14, AD-15, AD-16 · **Écrit dans :** `src/usine/ia/` (passerelle, contrôles, tâche `explication`, `prompts/explication.md`), `src/usine/adaptateurs/stockage_sqlite/`

**Acceptance Criteria:**

**Given** une entrée contenant un numéro de compte fictif et `USINE_CLE_PSEUDO` défini
**When** la passerelle traite une tâche `explication`
**Then** elle applique l'ordre Pseudonymisation → cache → `FournisseurLLM` → `controler_citations` → ré-identification → `EntreeTrace` (AD-12)
**And** le numéro est remplacé par un jeton `<TYPE>_<6 hex HMAC>` identique d'une exécution à l'autre (AD-15)

**Given** une réponse factice dont une phrase cite un ticket hors des tickets en cause
**When** `controler_citations` s'applique
**Then** la phrase est retirée et `phrases_retirees` vaut 1 dans `SortieExplication`

**Given** un second appel identique
**When** la passerelle s'exécute
**Then** la réponse vient de `donnees/cache_llm.sqlite` (WAL), repasse le contrôle, et la trace porte `depuis_cache=true`

**Given** l'`EntreeTrace` produite
**When** on l'inspecte
**Then** elle porte les quatre versions, le `passage_id` et les entrées pseudonymisées
**And** le numéro de compte fictif n'y figure pas en clair (AD-16)

### Story 0.8 : UI minimale (E0-8)

As a Pilote,
I want une page Streamlit qui affiche la carte météo du dernier Passage, lance la Chaîne et suit sa progression, avec le bandeau Mode repli,
So that la démo a une surface visible dès le walking skeleton.

**Exigences :** FR-43, FR-45 (amorces) · **AD :** AD-8, AD-11, AD-19 · **Écrit dans :** `src/usine/ui/`

**Acceptance Criteria:**

**Given** un Passage publié
**When** l'auteur lance l'UI
**Then** la carte météo affiche une ligne par Entité avec sa couleur, lue via `Consultation` uniquement (AD-11)

**Given** l'écran de lancement
**When** le Pilote lance la Chaîne
**Then** l'UI démarre `usine rapport` en sous-processus et affiche chaque étape d'`Etape` en lisant `sorties/progression/<passage_id>.jsonl` en ouvrir-lire-fermer (AD-8, H-28)
**And** l'UI n'ouvre jamais `entrepot.duckdb` ni un répertoire `.en-cours-*`

**Given** `USINE_MODE_REPLI=1`
**When** l'UI s'affiche
**Then** un bandeau « Mode repli » est visible en permanence (AD-19, H-30)

### Story 0.9 : Gel des contrats v1 (E0-9)

As a auteur,
I want relire les contrats contre le spine puis poser l'étiquette `contrats-v1`,
So that les lanes s'ouvrent en worktrees sur une base figée.

**Exigences :** — (critère de sortie de l'Epic 0) · **AD :** AD-2, AD-7, AD-12, AD-15, AD-17, AD-21 · **Écrit dans :** `src/usine/contrats/`, `src/usine/ports/` (corrections de relecture et décisions D1 à D10 de `preparation-0-9-gel-contrats.md`, § 7) ; consommateurs migrés dans la même PR (D2, D8) : `ia/`, `chaine/`, `consultation/`, `domaine/meteo.py`, `rendu/`, `ui/`, `generateur/cli.py`, `composition.py`, `adaptateurs/` ; `.github/scripts/controle_lanes.py` ; `tests/` correspondants. Ces écritures hors des deux répertoires sont acceptées : tous ces fichiers appartiennent encore à `main` avant le gel.

**Acceptance Criteria:**

**Given** les stories 0.1 à 0.8 terminées
**When** l'auteur lance `usine rapport` sur le mini-jeu
**Then** un Passage est publié de bout en bout et la CI est verte sous Windows et Linux

**Given** la table *Contrats v1* et AD-1 à AD-24
**When** l'auteur relit `contrats/` et `ports/`
**Then** chaque contrat, énumération et lecture de `Consultation` exigés est présent, et les écarts trouvés sont corrigés avant le gel
**And** `CONTRATS_VERSION` vaut `1.0.0`

**Given** le spine amendé le 2026-10-12 (`sprint-change-proposal-2026-10-12.md`)
**When** l'auteur relit `contrats/` et `ports/`
**Then** `EXCLUSIONS_REJEU` est un `Mapping` du nom logique de fichier vers ses chemins de champ, avec la liste d'AD-7, et le test de Rejeu de la Chaîne l'applique par fichier
**And** `CacheLLM` est un port de `ports/`, couvert par une suite `tests/contrat/cache_llm/` (SQLite et doublure)
**And** `EnveloppeCache`, `ReponseExplication`, la grammaire des jetons (dans `contrats.llm`) et `DonneesPassage` (dans `contrats.passage`, `@dataclass(frozen=True)`) ne sont plus définis hors de `contrats`
**And** la carte de `.github/scripts/controle_lanes.py` égale la *Carte des lanes* du spine, `adaptateurs/pseudonymisation` en L6 compris

**Given** la relecture validée
**When** l'auteur pose l'étiquette git `contrats-v1`
**Then** les branches `lane/1-donnees` à `lane/8-portage` sont créées depuis cette étiquette, une par worktree, avec un `donnees/` et un `.env` propres à chacune

## Epic 1 : Programme fictif dans Jira (L1 Données)

L'auteur génère le Programme fictif, ses 8 semaines d'historique et ses trois Scénarios de démo, puis l'injecte dans Jira Cloud Free de façon idempotente. **Écrit seulement dans :** `generateur/`, `outils/`, `config/programme.yaml`, `donnees/corpus/` et `tests/unit/` correspondant. **Dépendances externes :** Story 2.1 (transport `jira_http`) avant la Story 1.6 ; Epic 3 terminé avant la Story 1.8 ; Story 6.1 (adaptateurs LLM) avant la Story 1.9.

### Story 1.1 : Configuration complète du Programme

As a auteur,
I want décrire les 10 Entités, les 3 Vagues, les Domaines, le calendrier des Phases et la volumétrie dans `config/programme.yaml`,
So that je change la taille ou la forme du Programme sans toucher au code.

**Exigences :** FR-1, NFR-4, NFR-10 · **AD :** AD-17, AD-19, AD-23

**Acceptance Criteria:**

**Given** `config/programme.yaml` livré
**When** le chargeur `usine.config` le valide contre `ConfigProgramme`
**Then** il décrit le Programme « Banque Exemple — migration SI cœur », 10 Entités `ENT-A` à `ENT-J`, 3 Vagues avec leur calendrier de Phases (migration à blanc, recette, TNR) et la volumétrie cible (3 000 à 5 000 Anomalies, 200 à 500 Entrées par semaine)
**And** chaque clé porte un commentaire en français et aucun nom réel d'organisation ou de personne n'y figure

**Given** une copie de la configuration avec 6 Entités et une volumétrie divisée par deux
**When** l'auteur lance la génération
**Then** le Journal produit respecte ces valeurs sans modification de code

**Given** une configuration dont une Entité référence une Vague inconnue
**When** elle est chargée
**Then** une `UsineErreur` nomme le fichier, la clé et la valeur fautive

### Story 1.2 : Corpus de textes provisoire et outil de génération

As a auteur,
I want un Corpus de textes provisoire construit par gabarits, et l'outil `outils/generer_corpus.py` prêt à produire le Corpus définitif via le port `FournisseurLLM`,
So that la génération des données avance sans aucun appel LLM avant la porte Palier 1.

**Exigences :** FR-2 · **AD :** AD-19, AD-24

**Acceptance Criteria:**

**Given** `donnees/corpus/`
**When** on l'inspecte
**Then** il contient un Corpus provisoire (titres et descriptions d'Anomalies, de Cas de test et de Certifications, par Domaine et par Cause racine) avec la métadonnée `modele_corpus: gabarits-provisoires`

**Given** `outils/generer_corpus.py`
**When** on le lance avec un `FournisseurFactice`
**Then** il produit un Corpus au même format, via `generer_structure` uniquement, en écrivant le `modele_corpus` utilisé
**And** l'outil n'importe aucun SDK de fournisseur (AD-12, AD-24)

**Given** le Corpus versionné
**When** l'auteur régénère les données
**Then** aucun appel LLM n'est émis (test avec un fournisseur qui échoue à tout appel)

### Story 1.3 : Génération reproductible à la volumétrie cible

As a auteur,
I want générer Anomalies, Cas de test et Certifications avec 8 semaines d'historique daté sous forme de Journal d'événements,
So that le Programme fictif a l'épaisseur d'une vraie usine et se régénère à l'identique.

**Exigences :** FR-2, NFR-3 · **AD :** AD-1, AD-3, AD-17, AD-23

**Acceptance Criteria:**

**Given** la configuration livrée, une graine et une date de génération
**When** l'auteur lance la génération
**Then** le Journal contient 3 000 à 5 000 Anomalies, 200 à 500 Entrées par semaine et 10 Entités
**And** l'historique se termine au dernier Jour ouvré avant la date de génération et la semaine 1 commence 8 semaines plus tôt (AD-17)

**Given** deux exécutions avec la même graine et le même Corpus
**When** on compare les Journaux
**Then** structure, dates relatives, affectations et textes sont identiques

**Given** le Journal
**When** on rejoue les transitions des Anomalies
**Then** elles suivent le workflow Nouvelle → En analyse → En correction → À retester → Fermée ou Rejetée, réouvertures comprises `[HYPOTHÈSE H-17]`
**And** chaque Anomalie a une Cause racine parmi les 7 de H-18, écrite seulement dans `donnees/verite_terrain.json`, jamais dans un `Evenement` (test, AD-23) `[HYPOTHÈSE H-18]`

### Story 1.4 : Identifiants sensibles fictifs

As a auteur,
I want que le générateur insère des numéros de compte, noms de clients et identifiants fictifs dans au moins 10 % des descriptions d'Anomalies,
So that la Pseudonymisation a quelque chose de visible à démontrer et à tester.

**Exigences :** FR-4, NFR-4 · **AD :** AD-15

**Acceptance Criteria:**

**Given** un Journal généré
**When** on compte les descriptions d'Anomalies porteuses d'un identifiant injecté
**Then** elles représentent au moins 10 %

**Given** un identifiant injecté
**When** on le vérifie
**Then** il a un format plausible mais invalide (par exemple un IBAN fictif à clé de contrôle fausse), et aucun nom de client ne correspond à une personne réelle connue

**Given** la génération
**When** elle se termine
**Then** la liste des identifiants injectés est écrite dans `donnees/` (ignoré par git), pour le test de balayage SM-7 de l'Epic 6

### Story 1.5 : Scénarios de démo scriptés

As a auteur,
I want scripter les trajectoires des Entités A, B et C dans le générateur,
So that la démo du jour montre un rouge qui sort, un rouge qui dure et un orange qui menace.

**Exigences :** FR-3 · **AD :** AD-17

**Acceptance Criteria:**

**Given** la configuration des Scénarios dans `config/programme.yaml`
**When** le Journal est généré
**Then** A accumule des Anomalies bloquantes de reprise de données à partir de la semaine 6, avec des Sorties supérieures aux Entrées à partir de la semaine 7
**And** B a des Entrées d'Anomalies supérieures aux Sorties de la semaine 2 à la fin, et C voit son taux de KO en TNR monter à partir de la semaine 4

**Given** les autres Entités
**When** le Journal est généré
**Then** leurs paramètres visent au plus 3 Jours ouvrés rouges consécutifs et au moins 80 % de couples Entité × Date d'arrêté verts ou jaunes
**And** le calage au jour près est vérifié à la Story 1.8

### Story 1.6 : Injection initiale dans Jira Cloud Free

As a auteur,
I want injecter le Programme sur un site Jira Cloud Free vierge,
So that la démo s'appuie sur une vraie API Jira.

**Exigences :** FR-5, NFR-4 · **AD :** AD-1, AD-4, AD-5, AD-19, AD-23 · **Prérequis externe :** Story 2.1

**Acceptance Criteria:**

**Given** un spike d'une demi-journée sur la création du workflow et des champs personnalisés par l'API sur Jira Free
**When** il se conclut
**Then** sa conclusion est consignée ; si l'API ne le permet pas, la procédure manuelle de repli est documentée et les tickets restent injectés par l'API

**Given** un site vierge, `JIRA_TOKEN_INJECTION` et l'URL du site en configuration
**When** l'auteur lance l'injection depuis `main` sur le projet `DEMO`
**Then** le projet, les types de tickets, le workflow et les champs Entité, Vague, Domaine, Gravité et Phase existent
**And** les tickets sont créés par l'API REST dans un ordre déterministe puis amenés à leur état à la Date d'injection, sans import CSV (AD-4)

**Given** l'injection terminée
**When** on lit `donnees/injection/manifeste_injection.json`
**Then** il porte la Date d'injection, `debut_injection`, `horodatage_fin_injection`, `correspondance_cles` et la clé de projet

**Given** le code de l'injecteur
**When** on l'inspecte
**Then** seul `generateur/injecteur` construit un client d'écriture, avec `JIRA_TOKEN_INJECTION` ; la composition de `usine rapport` ne lit jamais cette variable (AD-1, AD-5)

### Story 1.7 : Réinjection idempotente et clés stables

As a auteur,
I want relancer l'injection sans créer de doublons et retrouver les mêmes clés,
So that un site Jira Free désactivé ou une démo à refaire se reconstruisent sans casser les liens ni les Citations.

**Exigences :** FR-5, NFR-3 · **AD :** AD-4

**Acceptance Criteria:**

**Given** un projet `DEMO` déjà injecté
**When** l'auteur relance l'injection
**Then** aucun ticket n'est créé en double et l'état des tickets est inchangé

**Given** un site vierge
**When** on injecte deux fois le même Journal, sur deux sites successifs
**Then** les clés de ticket sont identiques, ou la `correspondance_cles` du manifeste est mise à jour et appliquée à la lecture du Journal (AD-4)

### Story 1.8 : Calage des Scénarios de démo au jour près

As a auteur,
I want vérifier par un test, avec la Grille de météo par défaut et le calcul complet, que les trajectoires de FR-3 sont tenues au jour près,
So that la démo montre exactement ce que le scénario promet.

**Exigences :** FR-3, FR-16 · **AD :** AD-17 · **Prérequis externe :** Epic 3 terminé

**Acceptance Criteria:**

**Given** le Journal généré et la Grille par défaut
**When** le test calcule la Météo de chaque Entité pour chaque Jour ouvré de l'historique
**Then** A est verte ou jaune jusqu'à la semaine 5 puis rouge de la semaine 6 à la fin ; B est rouge de la semaine 2 à la fin ; C est verte jusqu'à la semaine 3, jaune en semaines 4 à 6, orange en semaines 7 et 8
**And** hors A, B et C, aucune Entité n'est rouge plus de 3 Jours ouvrés consécutifs, au moins 80 % des couples sont verts ou jaunes et au plus 2 Entités sont rouges en fin d'historique

**Given** un écart au scénario
**When** l'auteur le corrige
**Then** il ajuste les paramètres du générateur et jamais les seuils de la Grille (SM-C3)

### Story 1.9 : Corpus de textes définitif par LLM

As a auteur,
I want produire une fois le Corpus de textes définitif par un vrai LLM, distinct du classifieur des Causes racines,
So that la classification est évaluée sur des textes réalistes rédigés par un autre modèle (SM-9).

**Exigences :** FR-2 · **AD :** AD-19, AD-24 · **Prérequis externe :** Story 6.1

**Acceptance Criteria:**

**Given** les adaptateurs LLM réels de la Story 6.1
**When** l'auteur lance `outils/generer_corpus.py` avec un modèle choisi
**Then** le Corpus est écrit dans `donnees/corpus/` avec `modele_corpus` égal à ce modèle, puis versionné

**Given** le nouveau Corpus
**When** l'auteur régénère les données et relance le test de la Story 1.8
**Then** les Scénarios de démo restent tenus au jour près

**Given** une configuration où le modèle de classification égale `modele_corpus`
**When** `usine.config` la charge
**Then** elle est refusée avec un message nommant les deux valeurs (garde-fou d'AD-19)

## Epic 2 : Extraction fiable de l'historique (L2 Extraction)

Le Pilote dispose de l'historique complet des tickets depuis Jira Cloud, Jira Data Center ou le seul Journal, de façon incrémentale et en lecture seule, Jira faisant foi. **Écrit seulement dans :** `adaptateurs/{jira_http,jira_cloud,jira_dc,journal,composite,entrepot_duckdb,cli}`, `config/jira.yaml`, `tests/fixtures/jira_*` et les tests miroirs (AD-21). **Dépendance externe :** Story 1.7 avant la Story 2.7.

### Story 2.1 : Transport Jira commun et client de lecture à liste blanche

As a Sponsor,
I want que l'extraction ne puisse techniquement émettre aucune écriture vers Jira,
So that je peux accorder un compte de service sans risque pour les données de l'usine.

**Exigences :** FR-9, NFR-7 · **AD :** AD-5, AD-19, AD-20

**Acceptance Criteria:**

**Given** `adaptateurs/jira_http`
**When** on l'utilise contre des fixtures enregistrées
**Then** il gère la pagination Cloud (`nextPageToken`) et DC (`startAt` / `maxResults`), l'authentification Cloud (e-mail + jeton) et DC (PAT), et reprend sur 429 en respectant `Retry-After`

**Given** `ClientJiraLecture` construit avec `JIRA_TOKEN_LECTURE`
**When** il reçoit une requête hors de sa liste blanche `(méthode, gabarit de chemin)`, par exemple `POST /rest/api/3/issue`
**Then** il la refuse avant tout envoi
**And** `POST search/jql` et `POST changelog/bulkfetch` restent autorisés ; un test de contrat vérifie la liste blanche sur Cloud et sur DC

**Given** le transport
**When** l'injecteur (Story 1.6) en a besoin
**Then** il peut construire un client d'écriture distinct, que seule la composition du générateur instancie (AD-5)

### Story 2.2 : Adaptateur Jira Cloud v3 et vocabulaire canonique

As a Pilote,
I want que les tickets et leur changelog Jira Cloud soient convertis en `Evenement` canoniques,
So that le calcul ne voit jamais un nom de champ ou de statut propre à Jira.

**Exigences :** FR-6 · **AD :** AD-3, AD-20, AD-23

**Acceptance Criteria:**

**Given** `config/jira.yaml` avec la table de correspondance (champs personnalisés → `Champ`, noms de statuts → statuts H-17)
**When** l'adaptateur Cloud lit des fixtures `tests/fixtures/jira_cloud/`
**Then** il émet des `Evenement` d'identifiants `<id changelog>-<rang item>` et `C-<id ticket>`, dont toutes les valeurs appartiennent aux domaines canoniques
**And** la correspondance n'est appliquée que dans l'adaptateur (AD-23)

**Given** un changelog tronqué dans la réponse de recherche
**When** l'adaptateur le détecte
**Then** il complète l'historique par l'endpoint dédié

**Given** la suite de contrat `SourceTickets`
**When** on l'exécute sur l'adaptateur Cloud
**Then** elle passe, y compris le contrôle des domaines de valeurs (AD-20)

### Story 2.3 : Entrepôt DuckDB et extraction incrémentale

As a Pilote,
I want que chaque Passage n'extraie que les tickets modifiés depuis le dernier Passage réussi,
So that le rapport du matin reste rapide et qu'une coupure ne corrompt pas l'historique.

**Exigences :** FR-6, NFR-2 · **AD :** AD-6

**Acceptance Criteria:**

**Given** un entrepôt `donnees/entrepot.duckdb` avec un repère d'extraction
**When** l'extraction s'exécute
**Then** elle demande `updated >= repère − marge` (marge dans `config/jira.yaml`) et dédoublonne par `id_evenement`

**Given** un deuxième Passage sans modification dans Jira (fixtures identiques)
**When** l'extraction s'exécute
**Then** aucun événement stocké n'est ajouté ni modifié

**Given** une coupure simulée au milieu de la pagination
**When** l'extraction échoue
**Then** ni les événements ni le repère ne sont validés (transaction unique, AD-6)

**Given** l'entrepôt
**When** on recherche ses ouvertures dans le code
**Then** seule l'étape `extraction` l'ouvre ; DuckDB stocke et relit sans calcul métier (AD-9)

### Story 2.4 : Adaptateur Jira Data Center v2 et sélection par configuration

As a Sponsor,
I want que la chaîne fonctionne aussi sur Jira Data Center,
So that le démonstrateur est crédible sur l'outillage réel de la banque.

**Exigences :** FR-7, NFR-8 · **AD :** AD-5, AD-20, AD-23

**Acceptance Criteria:**

**Given** des fixtures `tests/fixtures/jira_dc/` équivalentes aux fixtures Cloud
**When** la suite de contrat `SourceTickets` s'exécute sur l'adaptateur DC
**Then** elle passe avec les mêmes tests que l'adaptateur Cloud, sans accès à un vrai Data Center

**Given** `config/jira.yaml` avec `adaptateur: dc`
**When** la composition construit la source
**Then** l'adaptateur DC est utilisé, avec `JIRA_DC_PAT` ; la sélection elle-même est câblée dans `composition.py` par une PR courte sur `main` (AD-21)

### Story 2.5 : Source Journal à l'échelle et correspondance des clés

As a auteur,
I want charger le Journal d'événements complet comme seule source, avec les clés Jira appliquées,
So that toute Date d'arrêté de l'historique se calcule sans Jira, avec des clés cohérentes avec les liens.

**Exigences :** FR-8 · **AD :** AD-3, AD-4

**Acceptance Criteria:**

**Given** un Journal à la volumétrie cible et un `ManifesteInjection`
**When** `SourceJournal` le lit
**Then** il applique `correspondance_cles` à la lecture et émet des `Evenement` à clé Jira (AD-4)

**Given** `adaptateur: journal` en configuration et aucun accès réseau
**When** on calcule un Instantané pour une date quelconque de l'historique
**Then** le calcul aboutit, avec le même modèle de données en sortie que les autres sources

### Story 2.6 : Source composite et cohérence à la Date d'injection

As a Pilote,
I want un historique continu qui combine le Journal jusqu'à l'injection et le changelog Jira après,
So that j'ai 8 semaines de tendances tout en voyant les mises à jour faites en direct dans Jira.

**Exigences :** FR-49 · **AD :** AD-3, AD-4

**Acceptance Criteria:**

**Given** un Journal, un manifeste d'injection et des événements Jira fixtures
**When** `SourceComposite` produit le flux
**Then** il contient tout le Journal puis les seuls événements Jira dont `horodatage > horodatage_fin_injection`, ceux de l'intervalle d'injection étant ignorés

**Given** l'état Jira juste après injection converti en `Evenement` `alignement`
**When** le domaine calcule les deux Instantanés à la Date d'injection
**Then** ils sont identiques (test de cohérence FR-49)

**Given** un ticket dont l'état rejoué diffère de son état Jira
**When** l'étape `extraction` le détecte
**Then** elle persiste une seule fois un `Evenement` `alignement` d'identifiant `A-<cle>-<champ>-<sha8(vers)>`, horodaté à sa première détection
**And** le nombre d'alignements est exposé pour le manifeste du Passage (H-27)

### Story 2.7 : Recette en direct sur Jira Cloud

As a auteur,
I want vérifier la Source composite sur le vrai projet `DEMO`,
So that la démo en direct se comporte comme les tests.

**Exigences :** FR-6, FR-49, FR-9 · **AD :** AD-4, AD-6 · **Prérequis externe :** Story 1.7

**Acceptance Criteria:**

**Given** le projet `DEMO` injecté et `JIRA_TOKEN_LECTURE` défini
**When** l'auteur lance deux extractions successives sans modification (test marqué `@pytest.mark.reseau`)
**Then** la seconde n'ajoute aucun événement

**Given** une transition faite à la main dans Jira sur un ticket de A
**When** le Passage suivant s'exécute
**Then** l'Instantané reflète la transition

**Given** les fixtures enregistrées
**When** l'auteur les rafraîchit depuis `DEMO`
**Then** elles ne contiennent aucun secret (gitleaks vert)

## Epic 3 : Météo calculée et justifiée (L3 Calcul)

Le Pilote obtient Instantanés, KPI, Tendances et Météo par règles, avec les Règles déclenchantes et leurs tickets en cause, réconciliés à 100 % avec le Rapport de référence. **Écrit seulement dans :** `domaine/{instantanes,kpi,meteo}`, `config/grille_meteo.yaml`, `tests/fixtures/reference` et `tests/unit/` correspondant. Toutes les fonctions sont pures, en Polars (AD-9).

### Story 3.1 : Instantanés quotidiens complets

As a Pilote,
I want l'état de chaque Entité à n'importe quelle Date d'arrêté de l'historique, y compris passée,
So that je peux comparer aujourd'hui à hier ou à la semaine dernière.

**Exigences :** FR-10, FR-14 · **AD :** AD-9, AD-17, AD-23

**Acceptance Criteria:**

**Given** un flux d'`Evenement` (Anomalies, Cas de test, Certifications)
**When** le domaine calcule les `TicketEtat` pour chaque Jour ouvré ≤ D, puis les Instantanés
**Then** les sorties respectent `SCHEMA` de `contrats.tickets` et `contrats.calcul` (validées par `valider()`)

**Given** un flux et une date passée D
**When** on ajoute des événements postérieurs à D
**Then** l'Instantané en D est inchangé (test de propriété)

**Given** deux calculs sur le même flux
**When** on compare les DataFrames
**Then** ils sont identiques, ordre des lignes compris (déterminisme, FR-14)

### Story 3.2 : KPI quotidiens

As a Pilote,
I want les stocks, flux, âges, taux et Certifications de chaque Entité et du Programme,
So that je n'ai plus à les recalculer dans Excel.

**Exigences :** FR-11, NFR-1 · **AD :** AD-9, AD-10, AD-17

**Acceptance Criteria:**

**Given** des Instantanés
**When** le domaine calcule les KPI
**Then** il produit, par Entité et pour le Programme : stock d'Anomalies ouvertes par Gravité et par Phase ; Entrées et Sorties du jour et sur la Fenêtre glissante ; âge médian et maximum des Anomalies ouvertes en Jours ouvrés depuis la dernière Entrée ; taux de KO et de non-exécution par Phase ; Certifications par statut
**And** Entrée, Sortie et Anomalie ouverte suivent les définitions du Glossaire `[HYPOTHÈSE H-17]`, la Fenêtre glissante vient de `contrats.calendrier` `[HYPOTHÈSE H-19]`

**Given** un taux
**When** on l'inspecte
**Then** il est porté en colonnes `numerateur` et `denominateur` entières, sans flottant (AD-10)

**Given** une Anomalie réouverte
**When** on calcule son âge
**Then** il part de la réouverture (dernière Entrée)

### Story 3.3 : Tendances hebdomadaires

As a Pilote,
I want les KPI agrégés par semaine sur 8 semaines,
So that je montre la trajectoire de l'usine en comité.

**Exigences :** FR-12 · **AD :** AD-9, AD-17

**Acceptance Criteria:**

**Given** les KPI quotidiens de l'historique
**When** le domaine calcule les Tendances
**Then** chaque semaine porte la valeur du dernier Jour ouvré et les Entrées et Sorties cumulées de la semaine, numérotée par `semaine_programme` de 1 à 8

**Given** une Date d'arrêté en milieu de semaine
**When** on calcule la semaine en cours
**Then** elle est partielle et prend la valeur de la Date d'arrêté (AD-17)

### Story 3.4 : Grille de météo complète et validation

As a Pilote,
I want lire et ajuster la Grille de météo dans un YAML commenté en français, et être arrêté net si je la rends incohérente,
So that les règles restent lisibles par un non-développeur et ne produisent jamais une Météo absurde.

**Exigences :** FR-15, FR-18, NFR-6, NFR-10 · **AD :** AD-10, AD-16, AD-19

**Acceptance Criteria:**

**Given** `config/grille_meteo.yaml` livré
**When** il est chargé
**Then** il porte les seuils IND-1 à IND-8 du PRD § 4.4, les garde-fous (20 Cas de test exécutés, 5 Entrées), l'activation de chaque règle et un commentaire français par clé
**And** `version_grille` vaut le SHA-256 du fichier (12 hex)

**Given** une Grille où le seuil orange d'IND-1 est plus sévère que le rouge
**When** elle est chargée
**Then** une `UsineErreur` nomme le fichier, la règle et la valeur fautive

**Given** une Grille avec un indicateur `IND-9` ou une couleur `violet`
**When** elle est chargée
**Then** elle est refusée avec un message nommant l'élément inconnu

**Given** un seuil décimal du YAML (par exemple `0.20`)
**When** il est converti
**Then** il devient une `Fraction` exacte (AD-10)

### Story 3.5 : Indicateurs de météo IND-1 à IND-8

As a Pilote,
I want les huit Indicateurs de météo calculés exactement, avec un statut explicite quand ils ne sont pas évaluables,
So that une couleur ne dépend jamais d'un arrondi ou d'un zéro par défaut.

**Exigences :** FR-11, FR-16, NFR-1 · **AD :** AD-10, AD-17

**Acceptance Criteria:**

**Given** les KPI d'une Entité à une Date d'arrêté
**When** le domaine calcule IND-1 à IND-8
**Then** IND-4 porte sur la Phase en cours, IND-5 et IND-6 sur la Vague en cours, IND-8 compare IND-4 à J-5

**Given** moins de 20 Cas de test exécutés dans la Phase en cours
**When** on calcule IND-4
**Then** il porte `statut = non_evaluable` et un `motif`, sans valeur NaN ni `None`
**And** IND-8 est non évaluable si IND-4 l'est à l'une des deux dates

**Given** 6 Entrées et 0 Sortie sur la Fenêtre glissante
**When** on calcule IND-7
**Then** le ratio vaut l'infini et déclenche orange ; avec 4 Entrées, IND-7 est non évaluable

### Story 3.6 : Météo et Règles déclenchantes

As a Pilote,
I want la Météo de chaque Entité avec toutes les Règles déclenchantes de la couleur retenue et leurs tickets en cause,
So that je justifie chaque rouge devant le comité avec des tickets précis.

**Exigences :** FR-16, FR-17, NFR-6 · **AD :** AD-9, AD-10, AD-16

**Acceptance Criteria:**

**Given** les Indicateurs d'une Entité
**When** le domaine calcule la Météo
**Then** la couleur la plus grave déclenchée l'emporte, verte sans Règle déclenchante, sans état d'un jour à l'autre
**And** un indicateur non évaluable ne fait pas changer la couleur

**Given** une Entité rouge par IND-1 et IND-5
**When** on lit sa `MeteoEntite`
**Then** elle liste les deux Règles déclenchantes rouges avec valeur mesurée, seuil franchi et tickets en cause, et porte `version_grille`

**Given** chaque type de règle
**When** on lit ses tickets en cause
**Then** IND-1, IND-2, IND-3 renvoient les Anomalies ouvertes concernées ; IND-4, IND-8 les Cas de test KO de la Phase en cours ; IND-5, IND-6 les Certifications ; IND-7 les Anomalies entrées et sorties sur la Fenêtre glissante

### Story 3.7 : Évolution de la Météo à J-1 et J-5

As a Pilote,
I want voir pour chaque Entité la Météo de la veille et de la semaine précédente,
So that je repère d'un coup d'œil ce qui a changé.

**Exigences :** FR-19 · **AD :** AD-17

**Acceptance Criteria:**

**Given** la Météo calculée pour chaque Jour ouvré
**When** on demande l'évolution d'une Entité à la Date d'arrêté D
**Then** on obtient la Météo de J-1 et de J-5 (Jours ouvrés) et un drapeau de changement de couleur pour chacune `[HYPOTHÈSE H-19]`

**Given** D égal au premier Jour ouvré de l'historique
**When** on demande J-1
**Then** la valeur est explicitement absente, pas une couleur par défaut

### Story 3.8 : Rapport de référence et réconciliation à 100 %

As a Sponsor,
I want une preuve automatique que les KPI et la Météo calculés égalent un calcul fait à la main,
So that je peux faire confiance aux chiffres du rapport.

**Exigences :** FR-13, NFR-1 · **AD :** AD-10

**Acceptance Criteria:**

**Given** `tests/fixtures/reference/` : un mini-Journal JSONL (environ 2 Entités, 60 tickets, 1 Date d'arrêté) et un YAML de valeurs attendues calculées à la main `[HYPOTHÈSE H-20]`
**When** on inspecte le jeu
**Then** il fait jouer chacun des 8 Indicateurs et chacun des 3 garde-fous de volume, au moins une fois déclenché et une fois non évaluable

**Given** ce jeu
**When** le test de réconciliation calcule KPI, Indicateurs et Météo
**Then** 100 % des valeurs sont égales, entiers et fractions comparés strictement (SM-1)

## Epic 4 : Prévision de sortie du rouge (L4 Prévision)

Le Pilote sait quand une Entité rouge devrait sortir et quelles Entités risquent d'y entrer, avec une méthode évaluée sur données réelles publiques. **Écrit seulement dans :** `domaine/prevision`, `evaluation/` et `tests/unit/` correspondant. **Dépendances externes :** Story 1.8 et Epic 3 avant la Story 4.5. Les paramètres (vélocité, horizons) vivent dans la configuration de la Chaîne, propriété de `main` : toute clé manquante passe par une PR courte.

### Story 4.1 : Prévision de sortie du rouge par Baseline

As a Pilote,
I want savoir, pour chaque Entité rouge, quand elle devrait sortir du rouge, avec une fourchette, une probabilité et les facteurs qui l'expliquent,
So that je réponds au comité « quand est-ce que ça repasse ? » avec des faits.

**Exigences :** FR-20, NFR-1 · **AD :** AD-9, AD-17, AD-18

**Acceptance Criteria:**

**Given** une `SerieStock` d'Entité (stock de bloquantes ouvertes, Entrées, Sorties par Jour ouvré) et IND-1 rouge
**When** `domaine.prevision.baseline` s'exécute avec une vélocité sur 10 Jours ouvrés et un horizon de 10 Jours ouvrés (configuration, H-7)
**Then** il renvoie une `Prevision` (`methode=baseline`) avec la date de sortie estimée (premier Jour ouvré où le stock projeté passe sous le seuil rouge d'IND-1), la fourchette des vélocités au 25ᵉ et 75ᵉ centile des fenêtres de 5 Jours ouvrés sur 20 jours, la probabilité empirique de sortie dans l'horizon et les facteurs explicatifs (stock, Entrées, Sorties, vélocité nette et sa variation)

**Given** une vélocité nette nulle ou défavorable
**When** la Baseline s'exécute
**Then** la `Prevision` porte « pas de sortie projetée », sans date

**Given** une Entité rouge aussi par IND-5
**When** la Baseline s'exécute
**Then** aucune date n'est produite et la `Prevision` porte « règle non projetable : IND-5 »

**Given** la fonction
**When** on l'inspecte
**Then** elle est pure, sans horloge ni hasard, et c'est la seule implémentation de la Baseline du dépôt (AD-18)

### Story 4.2 : Risque d'entrée en rouge

As a Pilote,
I want être prévenu qu'une Entité non rouge risque de franchir un seuil rouge la semaine prochaine,
So that j'agis avant qu'elle ne passe au rouge.

**Exigences :** FR-21, NFR-1 · **AD :** AD-9, AD-18

**Acceptance Criteria:**

**Given** les séries d'IND-1, IND-3 et IND-4 d'une Entité non rouge sur 10 Jours ouvrés
**When** le domaine calcule la régression linéaire projetée à 5 Jours ouvrés (H-8)
**Then** un `RisqueEntreeRouge` est émis si une projection franchit un seuil rouge, en nommant l'indicateur concerné et la valeur projetée

**Given** IND-4 non évaluable sur une partie de la fenêtre
**When** le risque est calculé
**Then** IND-4 est exclu de la projection, avec le motif restitué

### Story 4.3 : Conversion du Public Jira Dataset en SerieStock

As a auteur,
I want lire le dump Zenodo du Public Jira Dataset et le convertir en `SerieStock` par projet,
So that la même Baseline peut être évaluée sur des données réelles.

**Exigences :** FR-51 · **AD :** AD-18, AD-20

**Acceptance Criteria:**

**Given** un spike d'une demi-journée sur l'organisation du dump (pymongo)
**When** il se conclut
**Then** la procédure de téléchargement et de chargement est documentée dans `evaluation/zenodo/`

**Given** le dump chargé
**When** `evaluation/zenodo` convertit les tickets de priorité maximale de chaque projet
**Then** il produit des `SerieStock` validées par le schéma de `contrats.prevision`, en Jours ouvrés

**Given** la CI
**When** elle s'exécute
**Then** `evaluation/` n'y est pas lancée (AD-20) ; un test unitaire couvre la conversion sur un petit extrait figé

### Story 4.4 : Évaluation de la Baseline sur données réelles

As a Sponsor,
I want voir la Baseline évaluée sur des données Jira réelles et comparée à une prévision naïve,
So that la Prévision n'est pas jugée « trop synthétique ».

**Exigences :** FR-51 · **AD :** AD-18

**Acceptance Criteria:**

**Given** les `SerieStock` Zenodo et le protocole de l'addendum § E (couples projet × date échantillonnés chaque semaine, cible : stock sous le seuil dans les 10 Jours ouvrés)
**When** l'auteur lance l'évaluation
**Then** elle appelle `domaine.prevision.baseline` telle quelle, sans copie ni variante (AD-18)
**And** elle compare la Baseline à la référence naïve (taux historique de la cible sur le projet), avec un découpage temporel et des projets tenus à l'écart `[HYPOTHÈSE H-21]`

**Given** l'évaluation terminée
**When** on lit les résultats publiés dans `evaluation/`
**Then** ils donnent le score de Brier, l'AUC et l'erreur absolue moyenne sur le stock projeté, pour les deux prédicteurs

**Given** le score de Brier de la Baseline
**When** il n'est pas meilleur que celui de la référence naïve
**Then** le résultat est publié tel quel dans `evaluation/` et l'écart est signalé à l'auteur pour arbitrage (SM-10), sans retoucher la Baseline pour la seule évaluation

### Story 4.5 : Recette de la Prévision sur les Scénarios de démo

As a auteur,
I want vérifier qu'en fin d'historique A sort dans l'horizon, B ne sort pas et C est signalée,
So that l'étape Prévision de la démo est garantie.

**Exigences :** FR-20, FR-21 · **AD :** AD-18 · **Prérequis externe :** Story 1.8

**Prérequis :** contrats 1.2 (flux scripté des Scénarios A et B, Certification de B réservée, C à 50 Cas de test : partie générateur livrée par la PR de contrats). La story ne garde que la recette.

**Acceptance Criteria:**

**Given** le Journal généré et la Grille par défaut
**When** le test calcule les Prévisions au dernier Jour ouvré de l'historique par le chemin de la Chaîne (`prevision_du_passage`, étape `prevision`)
**Then** A a une date de sortie dans l'horizon, B porte « pas de sortie projetée » et C porte un Risque d'entrée en rouge (SM-6)

**Given** un écart
**When** l'auteur le corrige
**Then** il le corrige dans le générateur (Epic 1), jamais par un réglage de la Baseline sur les Scénarios (SM-C3)

**Given** une Entité non rouge qui porte un Risque d'entrée en rouge
**When** l'étape `prevision` publie `previsions.json`
**Then** la valeur projetée du Risque (`valeur_projetee_*`) est remplie depuis `risque.py`

### Story 4.6 : [BONUS] Modèle ML validé sur données réelles

As a Sponsor,
I want un Modèle ML qui prédit la résolution des bloquantes et bat la Baseline sur données réelles,
So that la Prévision gagne en précision sans perdre son contrat.

**Exigences :** FR-22 · **AD :** AD-18

**Acceptance Criteria:**

**Given** le protocole de la Story 4.4 et LightGBM 4.7.0
**When** l'auteur entraîne le Modèle ML sur le Public Jira Dataset
**Then** il prédit la probabilité de résolution d'une bloquante sous N Jours ouvrés (N = horizon de FR-20) et bat la Baseline en AUC et en score de Brier sur le jeu de test tenu à l'écart (SM-8)

**Given** une Entité rouge
**When** le Modèle ML s'applique
**Then** il produit une `Prevision` `methode=ml` par la règle d'agrégation de l'addendum (au moins k bloquantes résolues, indépendance assumée et documentée)
**And** appliqué aux Scénarios de démo, il anticipe la sortie de A et le maintien de B

### Story 4.7 : [BONUS] Facteurs explicatifs du Modèle ML

As a Pilote,
I want les principaux facteurs de chaque Prévision du Modèle ML, en mots simples,
So that je peux défendre une prévision ML devant un Sponsor bancaire.

**Exigences :** FR-23 · **AD :** AD-18

**Acceptance Criteria:**

**Given** une `Prevision` `methode=ml`
**When** on lit ses facteurs explicatifs
**Then** elle porte au plus 5 `FacteurExplicatif` libellés en français, calculés par contributions de variables (par exemple `pred_contrib` de LightGBM ; un ajout de SHAP passe par une PR sur `main`)
**And** un gain d'AUC qui rendrait ces facteurs illisibles n'est pas retenu (SM-C4)

## Epic 5 : Rapport quotidien en une commande (L5 Rapport)

Le Pilote produit en une commande, en moins de 5 minutes, l'Excel en 9 onglets et le PowerPoint en 7 sections d'une Date d'arrêté, rejouables à l'identique. Se termine par la **porte Palier 1 (M3)**. **Écrit seulement dans :** `chaine/`, `consultation/`, `rendu/`, `gabarits/` et `tests/unit/` correspondant. Les rendus affichent dès maintenant les champs Palier 2 quand ils existent (fixtures de contrats), pour que l'Epic 6 n'ait pas à toucher `rendu/`. **Dépendances externes :** Epics 3 et 4 pour les étapes réelles ; Epics 1 et 2 avant la Story 5.7.

### Story 5.1 : Étapes déterministes complètes et Passage autoportant

As a Pilote,
I want qu'un Passage contienne tous les Instantanés, KPI, Indicateurs, Météos, Tendances et Prévisions de chaque Jour ouvré jusqu'à la Date d'arrêté,
So that le rapport, l'UI, l'Agent et le Mode repli lisent tous les mêmes chiffres.

**Exigences :** FR-10 à FR-21, FR-34 (traces des Prévisions), FR-25 · **AD :** AD-7, AD-9, AD-16, AD-22

**Acceptance Criteria:**

**Given** le registre de `composition.py`
**When** les étapes `extraction`, `instantanes`, `kpi`, `meteo` et `prevision` s'exécutent
**Then** elles enveloppent les fonctions du domaine sans recalcul, et `EcrivainPassage` écrit `tickets_etats.parquet`, `tickets_textes.parquet`, `instantanes.parquet`, `kpi.parquet`, `indicateurs.parquet`, `meteo.json`, `tendances.parquet`, `previsions.json`, chacun validé par son contrat
**And** les sorties déterministes couvrent chaque Jour ouvré ≤ la Date d'arrêté (AD-7)

**Given** l'étape `prevision`
**When** elle se termine
**Then** chaque Prévision donne une `EntreeTrace` écrite dans `trace/previsions.jsonl` avec ses versions (AD-16)

**Given** le manifeste du Passage
**When** on le lit
**Then** il porte la Date d'arrêté, la source, `horodatage_extraction`, le nombre de tickets, le nombre d'alignements, `version_grille`, `version_donnees`, les durées par étape et `contrats_version`

### Story 5.2 : Consultation complète

As a Pilote,
I want un lecteur unique qui sert toutes les lectures d'un Passage,
So that l'Excel, le PowerPoint, l'UI et l'Agent affichent exactement les mêmes chiffres.

**Exigences :** FR-17, FR-19, FR-26, FR-27, FR-29, FR-39, FR-43 à FR-46 · **AD :** AD-2, AD-7, AD-9, AD-11

**Acceptance Criteria:**

**Given** un Passage publié ou en cours
**When** un consommateur appelle une lecture du port `Consultation`
**Then** la valeur est lue dans les fichiers du Passage sans aucune dérivation, et la suite de contrat `Consultation` passe sur l'implémentation complète

**Given** `consultation.url_ticket("DEMO-123")`
**When** le Mode repli est inactif
**Then** l'URL est construite depuis `config/jira.yaml` ; en Mode repli elle vaut `None`

**Given** un Passage Palier 2 et le filtre `palier=1`
**When** on lit une Entité
**Then** les sorties LLM sont masquées (FR-46)

**Given** un Passage dont `contrats_version` a une version majeure différente
**When** `Consultation` l'ouvre
**Then** il est refusé avec une `UsineErreur` (AD-2)

### Story 5.3 : Classeur Excel en 9 onglets

As a Pilote,
I want le classeur du jour en 9 onglets, avec des liens Jira et des chiffres identiques aux Instantanés,
So that je n'ai plus de retraitement Excel à faire.

**Exigences :** FR-26, FR-28, FR-29, NFR-11 · **AD :** AD-9, AD-11, AD-22

**Acceptance Criteria:**

**Given** un Passage
**When** l'étape `rendu` produit le classeur
**Then** il contient, dans l'ordre : Synthèse, Météo détaillée, KPI, Tendances, Anomalies ouvertes, Tests, Certifications, Commentaires, Traçabilité, au contenu du PRD § 4.6 (H-9)
**And** les nombres sont formatés par `contrats.format`

**Given** le classeur et le Passage
**When** le test automatique compare chaque valeur chiffrée aux données lues par `Consultation`
**Then** elles sont identiques (SM-1)

**Given** un Passage Palier 1
**When** on lit l'onglet Commentaires et la colonne Cause racine proposée
**Then** ils portent « commentaire non généré (Palier 1) » (FR-28)
**And** avec une fixture Palier 2, ils affichent les Explications, les Brouillons « brouillon IA, à valider », la répartition des Causes racines et leurs Citations en liens

**Given** une clé de ticket dans une cellule
**When** on l'inspecte
**Then** c'est un lien hypertexte issu de `url_ticket` (FR-29)

### Story 5.4 : Présentation PowerPoint en 7 sections

As a Pilote,
I want la présentation du jour sur un gabarit neutre, avec une slide par Entité rouge ou orange,
So that je présente en comité sans copier-coller.

**Exigences :** FR-27, FR-28, FR-29, NFR-4, NFR-11 · **AD :** AD-7, AD-11, AD-22

**Acceptance Criteria:**

**Given** `gabarits/rapport.pptx`, neutre et fictif
**When** l'étape `rendu` produit la présentation
**Then** elle contient Titre, Synthèse (Entités par couleur, changements depuis J-1 et J-5, trois messages clés), Carte météo (flèche de tendance, Règle déclenchante principale), une slide par Entité rouge ou orange (Règles, KPI clés, zone Brouillon de commentaire, Prévision), Tendances (stock de bloquantes et taux de KO sur 8 semaines), les 10 bloquantes les plus anciennes, l'Annexe méthode (H-10)

**Given** la présentation et le Passage
**When** le test compare les chiffres des slides aux données lues par `Consultation`
**Then** ils sont identiques

**Given** un Passage Palier 1
**When** on lit la zone de commentaire d'une slide d'Entité
**Then** elle porte « commentaire non généré (Palier 1) » ; avec une fixture Palier 2, elle porte le Brouillon et la mention « brouillon IA, à valider » (FR-33)

**Given** les trois messages clés de la Synthèse
**When** ils sont produits
**Then** ils sont construits par gabarit à partir des valeurs de `Consultation`, sans LLM

### Story 5.5 : Commande unique et Rejeu idempotent

As a Pilote,
I want produire le Rapport quotidien d'une seule commande, et obtenir le même rapport si je rejoue une date,
So that le rapport du matin est fiable et auditable.

**Exigences :** FR-25, FR-14, FR-28, NFR-3 · **AD :** AD-7, AD-8

**Acceptance Criteria:**

**Given** aucune option
**When** le Pilote lance `usine rapport`
**Then** la Date d'arrêté est le dernier Jour ouvré écoulé et les fichiers sont nommés `rapport-AAAA-MM-JJ.xlsx` et `.pptx`

**Given** `ConfigChaine.palier = 1`
**When** la Chaîne s'exécute
**Then** les étapes `classification`, `repartition_causes`, `explications` et `narration` sont enregistrées `sautee` et le Rapport est complet (FR-28)

**Given** deux Passages de la même Date d'arrêté sur les mêmes données
**When** le test de Rejeu compare tables, JSON, valeurs de cellules et textes de slides
**Then** tout est identique hors des exclusions qualifiées par fichier d'AD-7 (`contrats.passage.EXCLUSIONS_REJEU`), chaque champ exclu restant comparé dans les autres fichiers
**And** les cellules de Traçabilité qui affichent un champ exclu, déclarées en contrats 1.2 sous `rapport_xlsx` (`Traçabilité!B5`, `!B8`) et `rapport_pptx` (`Annexe méthode!<libellé>`), sont ignorées, et elles seules

**Given** l'échec d'une étape quelconque
**When** la commande se termine
**Then** le code de sortie est non nul, le message nomme l'étape et aucun fichier de Rapport n'est publié

**Given** une console Windows
**When** `usine rapport` journalise sa progression
**Then** les messages s'affichent en UTF-8 sans erreur d'encodage

### Story 5.6 : Recette du Rapport sur données complètes

As a auteur,
I want produire le Rapport quotidien sur le Journal complet et sur la Source composite,
So that les formats tiennent à la volumétrie réelle et avec les Scénarios de démo.

**Exigences :** FR-25, FR-26, FR-27 · **AD :** AD-4, AD-7 · **Prérequis externes :** Stories 1.8, 2.6, 4.5, 5.5 ; réinjection de `DEMO` depuis le Journal recalé (contrats 1.2)

**Acceptance Criteria:**

**Given** le Journal généré à la volumétrie cible
**When** l'auteur lance `usine rapport` en Palier 1
**Then** le Rapport montre A et B rouges, C orange, une slide pour chacune et les Prévisions attendues

**Given** la Source composite sur le projet `DEMO`
**When** l'auteur lance `usine rapport`
**Then** le Passage est publié et les liens des tickets ouvrent les tickets de `DEMO`

**Given** le Passage recalé de la volumétrie cible
**When** l'auteur régénère `demo/repli/passage/`
**Then** le Mode repli montre A et B rouges et C orange, comme en direct (AD-24)

### Story 5.7 : Porte Palier 1 (M3)

As a Sponsor,
I want une démo Palier 1 complète, sans LLM, qui produit le rapport du jour en moins de 5 minutes,
So that la demande d'outillage reste recevable même si la banque refuse tout LLM.

**Exigences :** NFR-2, FR-25, FR-28 · **AD :** AD-8

**Acceptance Criteria:**

**Given** le poste de l'auteur, dont les caractéristiques figurent dans le README, et la volumétrie de FR-2
**When** l'auteur mesure `usine rapport` en Palier 1, extraction incrémentale comprise
**Then** la durée est inférieure à 5 minutes et la mesure est consignée (SM-2)

**Given** la porte M3
**When** l'auteur la passe
**Then** la CI est verte, la réconciliation est à 100 %, le Rejeu est idempotent, et le journal de fin de jalon M3 est écrit
**And** aucune story de l'Epic 6 ne démarre avant ce point

## Epic 6 : Couche LLM sourcée et contrôlée (L6 Couche LLM)

Le Rapport quotidien s'enrichit des Causes racines proposées, d'Explications sourcées, de Brouillons de commentaire et d'une narration de la Prévision, pseudonymisés, contrôlés, mis en cache et tracés. **Démarre après la porte Palier 1 (Story 5.7).** **Écrit seulement dans :** `ia/` sauf `ia/agent`, `domaine/causes`, `adaptateurs/{llm,presidio,pseudonymisation,stockage_sqlite}`, `config/{llm,pseudonymisation}.yaml`, `evals/` sauf `evals/agent` et les tests miroirs (AD-21). Les schémas `ReponseClassification` et `ReponseNarration` passent par une PR courte sur `main` au début de l'epic (AD-12). Les rendus de l'Epic 5 affichent déjà les champs Palier 2 : cet epic ne touche pas `rendu/`. **Dépendance externe :** Story 1.9 avant la Story 6.9.

### Story 6.1 : Adaptateurs Anthropic et Mistral

As a auteur,
I want choisir le fournisseur et le modèle LLM en configuration, avec Anthropic et Mistral opérationnels derrière le même port,
So that la couche LLM n'est liée à aucun fournisseur et suit l'outillage que la banque validera.

**Exigences :** FR-30, NFR-7, NFR-9 · **AD :** AD-12, AD-13, AD-19, AD-20

**Acceptance Criteria:**

**Given** `config/llm.yaml` avec `fournisseur: anthropic` ou `fournisseur: mistral` et un modèle
**When** la composition construit le `FournisseurLLM`
**Then** l'adaptateur correspondant est utilisé sans modification de code, avec `ANTHROPIC_API_KEY` ou `MISTRAL_API_KEY` (H-23)
**And** `pydantic_ai` n'est importé que dans `adaptateurs/llm/` (vérifié par import-linter)

**Given** un appel `generer_structure` et un appel `executer_agent`
**When** l'adaptateur les exécute
**Then** le premier utilise le mode Tool Output avec le schéma demandé, le second `output_type=str` avec les seuls outils reçus ; aucun appel ne combine les deux (AD-13)

**Given** une doublure qui renvoie deux 429 avec `Retry-After` puis un succès
**When** l'adaptateur appelle
**Then** il attend de façon croissante en respectant `Retry-After` et réussit ; au-delà du nombre maximal de tentatives en configuration, il lève une `UsineErreur`

**Given** la suite de contrat `FournisseurLLM`
**When** on l'exécute
**Then** elle passe pour Anthropic, Mistral (enregistrements ou tests `@pytest.mark.reseau`) et `FournisseurFactice`
**And** le registre des quotas et des prix par modèle est renseigné, quotas gratuits de Mistral compris

### Story 6.2 : Pseudonymisation par Presidio

As a Sponsor,
I want qu'aucun identifiant sensible ne parte vers un LLM,
So that la banque peut autoriser un LLM distant sans fuite de données.

**Exigences :** FR-31, NFR-5 · **AD :** AD-15, AD-20

**Acceptance Criteria:**

**Given** Presidio, `fr_core_news_md` et les reconnaisseurs de `config/pseudonymisation.yaml` (comptes, clients, identifiants fictifs de FR-4)
**When** l'adaptateur `presidio` pseudonymise une description générée, en déléguant la dérivation des jetons et la table à `adaptateurs/pseudonymisation` (AD-15)
**Then** chaque identifiant devient `<TYPE>_<6 hex de HMAC-SHA256(USINE_CLE_PSEUDO, valeur)>`, identique d'un Passage et d'un worktree à l'autre
**And** les clés de ticket (`DEMO-123`) ne sont jamais remplacées

**Given** la liste des identifiants injectés par le générateur
**When** on pseudonymise tout le jeu généré
**Then** aucun identifiant injecté ne subsiste dans les textes pseudonymisés

**Given** un texte pseudonymisé
**When** la ré-identification est demandée
**Then** elle se fait localement via `donnees/pseudonymes.sqlite` (WAL, ignoré par git), uniquement par le port `Pseudonymiseur`
**And** `Pseudonymiseur.apercu(texte)` renvoie le couple original / pseudonymisé pour l'UI (AD-11)

**Given** la suite de contrat `Pseudonymiseur`, cas des jetons préfixés compris
**When** on l'exécute sur Presidio, sur le moteur par expressions régulières et sur la doublure
**Then** elle passe, et une même valeur donne le même jeton avec les deux moteurs

### Story 6.3 : Passerelle complète, cache, coût et dégradation

As a auteur,
I want que chaque appel LLM soit mis en cache, chiffré, tracé et dégradé proprement en cas d'échec,
So that le Palier 2 reste auditable, bon marché et ne casse jamais un Passage pour un contrôle raté.

**Exigences :** FR-14, FR-34, NFR-6, NFR-9 · **AD :** AD-12, AD-16

**Acceptance Criteria:**

**Given** la passerelle de l'Epic 0
**When** elle sert les tâches `classification`, `explication` et `narration`
**Then** la clé de cache vaut `(tache, cible, date_arrete, version_prompt, version_modele, empreinte de l'entrée pseudonymisée, tentative)`, sans Date d'arrêté pour la classification

**Given** un Rejeu à versions identiques
**When** les étapes LLM s'exécutent
**Then** aucun appel fournisseur n'est émis ; un changement de prompt, de modèle ou d'entrée relance l'appel (FR-14)

**Given** chaque appel
**When** il se termine
**Then** l'`EntreeTrace` porte horodatage, Date d'arrêté, Entité, quatre versions, fournisseur, entrées pseudonymisées, sortie, résultat des contrôles, `jetons_entree`, `jetons_sortie` et `cout_estime_eur` ; la Chaîne l'écrit dans `trace/llm.jsonl` et le manifeste porte `cout_llm_eur`

**Given** le plafond de coût par Passage de `config/llm.yaml` atteint
**When** une étape LLM demande un nouvel appel
**Then** l'élément est dégradé en libellé explicite et le Passage continue

**Given** un fournisseur injoignable au démarrage d'une étape LLM
**When** la Chaîne s'exécute
**Then** l'étape échoue et le Passage aussi, en nommant l'étape (H-31)

### Story 6.4 : Classification incrémentale des Causes racines

As a Pilote,
I want une Cause racine proposée pour chaque Anomalie,
So that je vois de quoi souffre chaque Entité sans relire les tickets un par un.

**Exigences :** FR-35, NFR-5, NFR-9 · **AD :** AD-12, AD-19, AD-23

**Acceptance Criteria:**

**Given** les `TicketTexte` du Passage
**When** l'étape `classification` s'exécute
**Then** seules les Anomalies nouvelles ou modifiées depuis le dernier Passage sont envoyées, après Pseudonymisation ; les autres viennent du cache
**And** chaque `SortieClassification` porte une des 7 Causes racines de H-18 et un `statut_controle` `[HYPOTHÈSE H-18]`

**Given** un entrepôt sans classification antérieure
**When** le stock complet est classé
**Then** le manifeste porte `classification_initiale = true`, et ce Passage est exclu des mesures de NFR-2 et NFR-9 (AD-8)

**Given** la Cause racine proposée
**When** on recherche son usage
**Then** elle n'est affichée que comme suggestion et n'est jamais écrite dans Jira

### Story 6.5 : Répartition des Causes racines

As a Pilote,
I want la répartition des Causes racines proposées par Entité,
So that l'Explication sourcée et l'onglet Commentaires disent de quoi souffre chaque Entité.

**Exigences :** FR-35 · **AD :** AD-9

**Acceptance Criteria:**

**Given** les `SortieClassification` du Passage
**When** l'étape `repartition_causes` appelle `domaine.causes.repartition`
**Then** elle produit `repartition_causes.parquet` (`RepartitionCauses`), compte entier et part en fraction par Entité et Cause racine
**And** la fonction est pure et déterministe ; aucun autre module ne recalcule la répartition (AD-9)

### Story 6.6 : Explication sourcée et Brouillon de commentaire

As a Pilote,
I want une explication de chaque rouge ou orange où chaque phrase cite ses tickets, et un brouillon de commentaire pour la slide,
So that je défends la Météo en comité avec des faits vérifiables.

**Exigences :** FR-32, FR-33, NFR-1, NFR-11 · **AD :** AD-12, AD-14

**Acceptance Criteria:**

**Given** une Entité rouge ou orange avec ses Règles déclenchantes, ses KPI, ses tickets en cause (FR-17) et sa répartition des Causes racines
**When** l'étape `explications` appelle la tâche `explication` (prompt `ia/prompts/explication.md`, en français)
**Then** la `SortieExplication` porte des phrases contenant chacune au moins une Citation, et un `brouillon_commentaire`

**Given** une phrase dont une Citation n'existe pas, n'appartient pas à l'Entité ou ne figure pas parmi les tickets en cause à la Date d'arrêté
**When** `controler_citations` s'applique
**Then** la phrase est retirée et `phrases_retirees` est incrémenté, affiché et journalisé

**Given** plus de la moitié des phrases retirées
**When** le contrôle se termine
**Then** l'explication est régénérée une fois ; si l'échec persiste, elle est remplacée par « explication indisponible »

**Given** un Passage Palier 2 produit
**When** on ouvre l'Excel et le PowerPoint
**Then** le Brouillon figure sur la slide de chaque Entité rouge ou orange et dans l'onglet Commentaires avec la mention « brouillon IA, à valider », sans modification de `rendu/`

### Story 6.7 : Narration de la Prévision

As a Pilote,
I want une phrase qui raconte la Prévision de chaque Entité, sans aucun chiffre inventé,
So that la Prévision se lit d'un coup d'œil sur la slide.

**Exigences :** FR-24, NFR-1 · **AD :** AD-12, AD-14

**Acceptance Criteria:**

**Given** une `Prevision` ou un `RisqueEntreeRouge`
**When** l'étape `narration` appelle la tâche `narration`
**Then** la `SortieNarration` est une phrase en français construite à partir des seules valeurs fournies

**Given** une narration contenant un nombre ou une date absents des valeurs fournies
**When** `controler_nombres` s'applique (clés, `IND-n`, `ENT-x`, `J-n` et jetons ignorés ; nombres lus au format français)
**Then** la narration est rejetée et la Prévision brute est affichée

### Story 6.8 : Suite d'évaluation de l'Explication sourcée

As a auteur,
I want 10 cas d'évaluation de l'Explication sourcée, contrôlés automatiquement et notés à la main,
So that je mesure la fidélité des explications avant la démo (SM-3).

**Exigences :** FR-50, FR-32 · **AD :** AD-14, AD-20

**Acceptance Criteria:**

**Given** `evals/explication/` avec 10 cas versionnés (Entité, Date d'arrêté, entrées attendues)
**When** l'auteur lance la suite à la demande (hors CI)
**Then** `controler_citations` est appliqué à chaque sortie et le taux de Citations valides après contrôle est publié

**Given** la grille de notation humaine de 1 à 5 (exactitude, utilité)
**When** l'auteur note les 10 cas
**Then** la note moyenne est enregistrée avec les versions de prompt et de modèle ; SM-3 est atteint à 100 % de Citations valides et une moyenne ≥ 4/5

### Story 6.9 : Suite d'évaluation de la classification

As a auteur,
I want mesurer la classification sur la vérité terrain du générateur et sur 30 tickets rédigés à la main,
So that je sais si la classification tient F1 macro ≥ 0,8 (SM-9).

**Exigences :** FR-50, FR-35 · **AD :** AD-19, AD-23 · **Prérequis externe :** Story 1.9

**Acceptance Criteria:**

**Given** le Corpus définitif (Story 1.9) et `donnees/verite_terrain.json`
**When** l'auteur lance `evals/classification/` à la demande
**Then** seule la suite `evals/` lit la vérité terrain (AD-23), et le F1 macro est publié par Cause racine et au global

**Given** 30 tickets rédigés à la main, versionnés dans `evals/classification/`
**When** la suite s'exécute
**Then** leur F1 macro est publié séparément
**And** le modèle de classification diffère de `modele_corpus` (garde-fou d'AD-19)

### Story 6.10 : Recette Palier 2

As a Sponsor,
I want un Passage Palier 2 complet, rapide, peu coûteux et sans fuite,
So that je juge la couche LLM sur pièces.

**Exigences :** NFR-2, NFR-5, NFR-9, FR-31, FR-14 · **AD :** AD-12, AD-15

**Acceptance Criteria:**

**Given** le Journal généré, au plus 4 Entités rouges ou oranges et un cache de classification initialisé
**When** l'auteur lance `usine rapport` en Palier 2
**Then** le Passage est produit en moins de 10 minutes, classification incrémentale comprise, pour un coût LLM inférieur à 1 € (`cout_llm_eur` du manifeste)

**Given** les traces du Passage et les requêtes émises vers le fournisseur
**When** le test de balayage SM-7 recherche les identifiants injectés par le générateur
**Then** il n'en trouve aucun

**Given** le même Passage rejoué
**When** il s'exécute
**Then** aucun nouvel appel LLM n'est émis et le Rapport est identique hors exclusions

### Story 6.11 : [BONUS] Détection de doublons

As a Pilote,
I want des paires d'Anomalies probablement en doublon, avec un score,
So that je fais nettoyer le stock sans fusion automatique.

**Exigences :** FR-36 · **AD :** AD-2, AD-12

**Acceptance Criteria:**

**Given** les Anomalies ouvertes pseudonymisées
**When** la détection s'exécute
**Then** elle produit des paires avec un score, à revoir par le Pilote, sans aucune fusion ni écriture dans Jira
**And** la nouvelle tâche et son contrat de sortie sont ajoutés par une PR dédiée sur `main` (`contrats/`, liste des tâches d'AD-12), avant le code de la lane

### Story 6.12 : [BONUS] Mode LLM local

As a Sponsor,
I want que la couche LLM fonctionne avec un modèle exécuté sur le poste,
So that la démo reste possible si la banque refuse tout LLM distant.

**Exigences :** FR-37 · **AD :** AD-13, AD-20

**Acceptance Criteria:**

**Given** `llama-server` (tag b11552) et un modèle quantifié tenant dans 8 Go de VRAM
**When** `config/llm.yaml` désigne le fournisseur local
**Then** l'adaptateur passe la suite de contrat `FournisseurLLM`, sans combiner schéma et outils dans un même appel
**And** les suites d'évaluation de l'Explication et de la classification sont relancées et leurs résultats publiés

### Story 6.13 : [BONUS] Observabilité externe

As a auteur,
I want tracer les appels LLM dans Langfuse auto-hébergé, en plus du Journal de traçabilité,
So that j'analyse latences et coûts dans un outil dédié.

**Exigences :** FR-38, NFR-5 · **AD :** AD-12, AD-15

**Acceptance Criteria:**

**Given** Langfuse 4.17.0 auto-hébergé configuré
**When** la passerelle émet une `EntreeTrace`
**Then** elle est aussi envoyée à Langfuse, avec les seuls textes pseudonymisés
**And** le test de balayage SM-7 s'applique aux données envoyées à Langfuse

## Epic 7 : Interface de démo et Agent (L7 Agent et UI)

Le Pilote et l'auteur disposent des écrans de la démo de 10 minutes, puis d'un Agent en lecture seule évalué sur 15 questions. **Stories 7.1 à 7.6 : Palier 1, avant la porte M3** (prérequis : Story 5.2). **Stories 7.7 à 7.12 : Palier 2, après l'Epic 6.** **Écrit seulement dans :** `ia/agent`, `ui/`, `demo/`, `config/demo.yaml`, `evals/agent` et `tests/unit/` correspondant. L'UI ne lit les Passages que via `Consultation` (AD-11).

### Story 7.1 : Carte météo et navigation

As a Pilote,
I want une carte météo du Programme d'où chaque écran est à un clic,
So that je trouve tout de suite l'Entité qui pose problème.

**Exigences :** FR-43, FR-29, NFR-11 · **AD :** AD-11

**Acceptance Criteria:**

**Given** le dernier Passage réussi (`consultation.dernier_passage()`)
**When** le Pilote ouvre l'UI
**Then** la carte affiche chaque Entité avec sa Météo, une flèche de tendance J-1 / J-5 et sa Règle déclenchante principale

**Given** la carte météo
**When** le Pilote cherche le détail d'une Entité, l'Agent, le lancement de la Chaîne, l'avant / après ou l'écran outillage
**Then** chaque écran est atteignable en un clic

**Given** une clé de ticket affichée dans l'UI
**When** le Pilote clique dessus
**Then** le ticket s'ouvre dans Jira via `url_ticket` (FR-29)

### Story 7.2 : Détail d'une Entité (Palier 1)

As a Pilote,
I want voir, pour une Entité, ses Règles déclenchantes, ses KPI, sa Prévision et ses facteurs explicatifs,
So that je comprends pourquoi elle a cette couleur et quand elle en sortira.

**Exigences :** FR-43, FR-17, FR-20, FR-21 · **AD :** AD-9, AD-11

**Acceptance Criteria:**

**Given** une Entité rouge
**When** le Pilote ouvre son détail
**Then** l'écran affiche chaque Règle déclenchante (valeur, seuil, tickets en cause en liens), les KPI clés, la Prévision avec sa fourchette, sa probabilité et ses facteurs explicatifs, ou « pas de sortie projetée »

**Given** une Entité non rouge avec un Risque d'entrée en rouge
**When** le Pilote ouvre son détail
**Then** l'indicateur concerné et sa projection sont affichés

**Given** un Passage Palier 1
**When** on regarde la zone Explication
**Then** elle porte « commentaire non généré (Palier 1) »

### Story 7.3 : Lancement de la Chaîne et progression

As a Pilote,
I want lancer la Chaîne depuis l'UI et voir chaque étape avancer,
So that je montre en direct que le rapport se fait en une commande.

**Exigences :** FR-43, FR-25 · **AD :** AD-8

**Acceptance Criteria:**

**Given** l'écran de lancement
**When** le Pilote lance la Chaîne
**Then** chaque étape d'`Etape` s'affiche avec son statut (en cours, réussie, `sautee`, en échec) et sa durée, lue dans `sorties/progression/<passage_id>.jsonl`

**Given** une étape en échec
**When** la CLI se termine
**Then** l'UI nomme l'étape fautive et n'affiche aucun rapport partiel

**Given** la Chaîne terminée avec succès
**When** l'UI se rafraîchit
**Then** la carte météo affiche le nouveau Passage

### Story 7.4 : Avant / après

As a Sponsor,
I want comparer le temps de reporting manuel au temps mesuré de la Chaîne, par jour et par semaine,
So that je vois le gain de temps, argument central de la démo.

**Exigences :** FR-44 · **AD :** AD-8, AD-19

**Acceptance Criteria:**

**Given** le temps manuel déclaré dans `config/demo.yaml` (valeur fictive commentée, Q-5)
**When** le Pilote ouvre l'écran avant / après
**Then** il voit ce temps à côté du temps mesuré (`horodatage_fin − horodatage_debut` du dernier Passage réussi sans classification initiale), par Rapport quotidien et cumulé sur 5 Rapports

**Given** que seul un Passage avec `classification_initiale = true` existe
**When** l'écran s'affiche
**Then** il l'indique au lieu d'afficher un temps trompeur

### Story 7.5 : Écran « Ce qu'il faut pour le faire en vrai »

As a Sponsor,
I want un écran qui liste l'outillage demandé et la correspondance avec mes outils,
So that la démo se conclut sur une demande claire.

**Exigences :** FR-43, FR-47 · **AD :** AD-11 · **Prérequis externe :** Story 8.1

**Acceptance Criteria:**

**Given** la fiche `docs/` de la Story 8.1
**When** le Pilote ouvre l'écran
**Then** l'UI affiche son contenu en lecture seule, sans en dupliquer le texte dans `ui/`

### Story 7.6 : Mode repli sur un Passage enregistré

As a auteur,
I want basculer la démo sur un Passage enregistré quand Jira ou le réseau tombe,
So that la démo continue quoi qu'il arrive.

**Exigences :** FR-45, NFR-12 · **AD :** AD-11, AD-19, AD-24

**Acceptance Criteria:**

**Given** `demo/repli/passage/`, copie versionnée d'un Passage publié entièrement fictif
**When** l'auteur active le Mode repli (bascule de l'UI ou `USINE_MODE_REPLI=1`)
**Then** toute l'UI lit cette copie via `Consultation`, la mention « Mode repli » est visible en permanence et les liens Jira sont inactifs

**Given** un clone frais sans réseau
**When** l'auteur lance l'UI en Mode repli
**Then** carte météo, détail d'Entité, Prévisions et avant / après fonctionnent

**Given** le Mode repli
**When** on cherche une détection automatique
**Then** il n'y en a pas : l'activation est toujours manuelle (H-30)

### Story 7.7 : Explication sourcée à l'écran et comparaison des Paliers

As a Pilote,
I want voir l'Explication sourcée d'une Entité avec ses liens, et basculer entre Palier 1 et Palier 2,
So that je montre ce que la couche LLM apporte, et rien de plus.

**Exigences :** FR-43, FR-46, FR-31, FR-32 · **AD :** AD-11, AD-15

**Acceptance Criteria:**

**Given** un Passage Palier 2 et une Entité rouge
**When** le Pilote ouvre son détail
**Then** l'Explication sourcée s'affiche, chaque Citation est un lien Jira, et le nombre de phrases retirées est indiqué
**And** la narration de la Prévision remplace la Prévision brute quand elle a passé le contrôle

**Given** le sélecteur de Palier
**When** le Pilote choisit Palier 1
**Then** la même Entité s'affiche sans aucune sortie LLM (filtre `palier` de `Consultation`)

**Given** l'écran de Pseudonymisation
**When** le Pilote choisit une description
**Then** l'original et la version pseudonymisée s'affichent côte à côte via `Pseudonymiseur.apercu`, en local seulement

### Story 7.8 : Outils de consultation de l'Agent

As a Pilote,
I want que l'Agent dispose d'outils qui lisent la Météo, les Anomalies, les Tendances, les Prévisions et les Risques,
So that il répond à partir des chiffres du Passage, pour n'importe quelle Date d'arrêté disponible.

**Exigences :** FR-39, FR-41 · **AD :** AD-2, AD-5, AD-11

**Acceptance Criteria:**

**Given** `ia/agent`
**When** on liste ses outils
**Then** il expose exactement `get_meteo`, `list_anomalies` (filtres Entité, Gravité, Phase, statut), `get_tendance`, `get_prevision` et `get_risques`, aux signatures et résultats définis dans `contrats.agent`, servis par `Consultation`

**Given** l'inventaire des outils et des dépendances de l'Agent
**When** le test de lecture seule s'exécute
**Then** aucun outil n'écrit (Jira, mail, configuration) et l'Agent n'a aucun accès à Jira (AD-5)

**Given** une Date d'arrêté sans Passage
**When** un outil est appelé
**Then** il renvoie un résultat explicite « aucune donnée pour cette date »

### Story 7.9 : Agent conversationnel aux chiffres contrôlés

As a Pilote,
I want poser mes questions en langage naturel et obtenir des réponses dont chaque chiffre vient des outils,
So that j'anticipe la semaine suivante sans craindre un chiffre inventé.

**Exigences :** FR-40, FR-41, NFR-1, NFR-5, NFR-11 · **AD :** AD-12, AD-13, AD-14, AD-16

**Acceptance Criteria:**

**Given** l'écran Agent
**When** le Pilote demande « Quelles entités risquent de passer au rouge la semaine prochaine, et pourquoi ? »
**Then** l'Agent appelle les outils via `executer_agent` de la passerelle, chaque résultat d'outil étant pseudonymisé et tracé avant d'atteindre le fournisseur (AD-13)
**And** la réponse cite C, l'indicateur en hausse et ses Cas de test KO

**Given** une réponse contenant un nombre absent des résultats d'outils de la conversation ou un ticket non retourné
**When** `controler_nombres` et `controler_citations` s'appliquent
**Then** la réponse est rejetée et remplacée par un message explicite

**Given** une question sans réponse dans les données
**When** l'Agent répond
**Then** il dit que les données ne permettent pas de répondre

**Given** une session de l'Agent
**When** elle se termine
**Then** ses traces sont dans `sorties/agent/<AAAA-MM-JJ>/<session>.jsonl`, hors de tout Passage (AD-16)

### Story 7.10 : Suite d'évaluation de l'Agent

As a auteur,
I want 15 questions types du Pilote avec leurs éléments attendus vérifiés automatiquement,
So that je sais si l'Agent atteint 13/15 sans chiffre inventé (SM-4).

**Exigences :** FR-42, FR-40 · **AD :** AD-14, AD-20

**Acceptance Criteria:**

**Given** `evals/agent/` avec 15 questions versionnées, dont la question de la démo et au moins 2 questions sans réponse possible
**When** l'auteur lance la suite à la demande (hors CI)
**Then** chaque réponse est vérifiée automatiquement contre ses éléments attendus (chiffres, Entités, tickets) et le nombre de chiffres inventés est compté

**Given** les résultats
**When** ils sont publiés
**Then** ils donnent le score sur 15, le nombre de chiffres inventés et le nombre de refus sur les 13 questions répondables, au plus 1 visé `[HYPOTHÈSE H-22]`

### Story 7.11 : Réponses enregistrées de l'Agent et Mode repli complet

As a auteur,
I want enregistrer les réponses de l'Agent aux questions de la démo lors d'une répétition, puis les rejouer en Mode repli,
So that la démo reste jouable de bout en bout sans réseau, Agent compris.

**Exigences :** FR-45, NFR-12 · **AD :** AD-24

**Acceptance Criteria:**

**Given** le Passage copié dans `demo/repli/passage/`
**When** l'auteur lance `usine agent --enregistrer` sur les questions de la démo
**Then** des `ReponseAgentEnregistree` portant le `passage_id` de cette copie sont écrites dans `demo/repli/agent/*.json` et versionnées

**Given** le Mode repli actif
**When** le Pilote ouvre l'écran Agent
**Then** les questions enregistrées sont proposées sous forme de choix, sans saisie libre, et les réponses sont rejouées avec la mention « Mode repli »

**Given** des réponses dont le `passage_id` diffère de la copie
**When** l'UI les charge
**Then** elles sont refusées avec un message explicite

### Story 7.12 : Répétitions chronométrées de la démo

As a auteur,
I want répéter la démo de 10 minutes au moins trois fois, dont une en Mode repli,
So that je la présente sans intervention hors script (SM-5).

**Exigences :** FR-43 à FR-46, NFR-12 · **AD :** AD-24

**Acceptance Criteria:**

**Given** le script de la démo (UJ-4) dans `demo/`
**When** l'auteur réalise les répétitions
**Then** au moins 3 répétitions durent 10 minutes au plus, dont une en Mode repli, sans intervention hors script
**And** chaque répétition est consignée (date, durée, mode, incidents) dans `demo/`

## Epic 8 : Dossier de portage (L8 Portage)

Le Sponsor dispose d'une fiche d'une page qui liste l'outillage demandé et les points d'attention du portage ; la démo est validée par le Responsable de mission. **Écrit seulement dans :** `docs/`. La Story 8.1 peut se faire à tout moment ; la Story 8.2 vient après la Story 7.12.

### Story 8.1 : Fiche « outillage demandé » et note de portage courte

As a Sponsor,
I want une fiche d'une page qui priorise l'outillage demandé et dit comment chaque brique se porte sur mes outils,
So that je sais exactement quoi accorder et avec quels risques.

**Exigences :** FR-47, NFR-8 · **AD :** AD-1, AD-19

**Acceptance Criteria:**

**Given** le tableau de la spec § 8 (addendum § G)
**When** l'auteur rédige `docs/fiche-outillage.md`
**Then** elle tient en une page et contient la liste priorisée des demandes (compte de service Jira en lecture, environnement Python, LLM validé…), un tableau de correspondance par brique (extraction, calcul, Météo, Prévision, rendu, LLM, UI) et, pour chaque cible (VM Python, Dataiku, Power Platform, poste seul), les points d'attention du portage

**Given** la fiche
**When** on la relit
**Then** elle ne contient aucun nom réel de client et chaque affirmation de portabilité renvoie à une règle vérifiée (AD-1, AD-19, NFR-8)

### Story 8.2 : Validation par le Responsable de mission (M7)

As a Responsable de mission,
I want valider la démo et la fiche avant toute présentation à un client,
So that rien ne sort chez le client sans contrôle.

**Exigences :** NFR-13, NFR-4 · **AD :** — · **Prérequis externe :** Story 7.12

**Acceptance Criteria:**

**Given** la démo répétée (Story 7.12) et la fiche (Story 8.1)
**When** le Responsable de mission les valide
**Then** la validation (date, version du dépôt, réserves éventuelles) est consignée dans le journal du jalon M7 sous `docs/`

**Given** une réserve émise
**When** elle est levée
**Then** la levée est consignée au même journal avant toute présentation

### Story 8.3 : [BONUS] Conteneur et note de portage détaillée

As a Sponsor,
I want une image conteneur de la Chaîne et une note de portage détaillée vers Dataiku et Power Platform,
So that le portage est démontré et pas seulement décrit.

**Exigences :** FR-48, NFR-8 · **AD :** AD-1, AD-19, AD-21

**Acceptance Criteria:**

**Given** un `Dockerfile` à la racine, ajouté par une PR sur `main` (hors répertoires de la lane)
**When** l'auteur construit et lance l'image avec un `.env` et le Journal
**Then** `usine rapport` produit un Passage en Palier 1 sans autre dépendance

**Given** `docs/portage-detaille.md`
**When** on le lit
**Then** il décrit, pour Dataiku et Power Platform, le découpage des briques, la gestion des secrets et de la configuration, et les limites connues
