# SPEC — Démonstrateur « Copilote de pilotage d'une usine de migration »

> Version 0.2 — 10/10/2026 — Auteur : Anaël Yahi
> Statut : à valider (voir § 11 « Questions ouvertes »)
> Objectif du démonstrateur : **convaincre de fournir l'outillage** (environnement d'exécution, accès API, LLM validé) en montrant, sur des données fictives, ce qu'une chaîne pro code apporte au reporting d'une usine de migration bancaire.

---

## 1. Problème illustré

Une usine de migration de SI pilote son programme à partir de Jira : anomalies, tests, certifications de migration, par entité et par vague. Aujourd'hui, ce reporting est produit **à la main** :

1. Extractions Jira.
2. Retraitements Excel.
3. Copier-coller dans PowerPoint.
4. Rédaction manuelle des commentaires de météo.

Conséquences : temps consommé chaque semaine, risque d'erreur, et justification des météos « rouges » laissée au jugement de chacun.

## 2. Ce que le démonstrateur doit prouver

| # | Message à faire passer | Preuve dans la démo |
|---|---|---|
| 1 | L'ETL Jira → reporting est **automatisable et fiable** | Excel + PPT générés en quelques minutes, chiffres réconciliés avec un rapport de référence |
| 2 | La météo peut être **calculée par des règles explicites** et non plus déclarée | Règles de météo en configuration, auditables |
| 3 | Un LLM peut **expliquer un rouge en citant les anomalies** | Synthèse par entité, chaque affirmation renvoyant à des tickets |
| 4 | On peut **estimer la sortie du rouge**, avec un niveau de confiance | Prévision statistique, narrée par le LLM — et non devinée par lui |
| 5 | Le pilote peut **interroger son programme en langage naturel** | Agent conversationnel en lecture seule |
| 6 | Le tout est **portable** sur l'outillage que la banque fournira | Tableau de correspondance (§ 8) et architecture découplée |

**Principe de démonstration : deux paliers de valeur.**
- **Palier 1, sans LLM** : ETL, KPI, météo, Excel/PPT automatiques. Il apporte déjà l'essentiel du gain de temps et peut être demandé **même si aucun LLM n'est autorisé**.
- **Palier 2, avec LLM** : explication, classification, prévision narrée, agent conversationnel.

## 3. Données (100 % publiques ou fictives)

| Source | Rôle | Accès |
|---|---|---|
| **Jira Cloud Free** (site personnel, ≤ 10 utilisateurs, API REST v3 incluse) | Héberge un **programme de migration fictif**. Démontre l'appel à une vraie API Jira | https://support.atlassian.com/jira-cloud-administration/docs/explore-jira-cloud-plans/ |
| **Générateur de données synthétiques** (dans le repo) | Crée entités, vagues, anomalies, tests et certifications, avec des dynamiques réalistes et des scénarios scénarisés | Script Python + LLM pour les textes |
| **Public Jira Dataset** (Univ. Hambourg, 16 instances Jira publiques, 2,7 M tickets, historiques de changements, données anonymisées) | **Valider la méthode de prévision sur des données réelles**, car une prévision évaluée sur des données synthétiques ne prouve rien (circularité) | https://zenodo.org/doi/10.5281/zenodo.5882881 |

### Modèle fictif (configurable)
- **Programme** : « Banque Exemple — migration SI cœur ». **Aucun nom réel.**
- **Entités** : 10 à 15. **Vagues** : 3. **Domaines** : crédits, dépôts, paiements, référentiel clients…
- **Types de tickets** :
  - Anomalie : gravité bloquante / majeure / mineure, phase (migration à blanc, recette, TNR), cause racine cachée servant de vérité terrain.
  - Cas de test : OK / KO / non exécuté.
  - Certification : accordée / réservée / refusée.
- **Champs personnalisés Jira** : Entité, Vague, Domaine, Gravité, Phase.

### Scénarios scénarisés (pour la démo)
- **Entité A** : passe au rouge en semaine 3 (anomalies bloquantes de reprise de données), puis revient à l'orange en semaine 5.
- **Entité B** : reste rouge, car le flux entrant d'anomalies dépasse la capacité de résolution. La prévision doit le signaler.
- **Entité C** : se dégrade lentement (TNR KO en hausse). Signal faible à détecter.
- **Historique** : 8 semaines générées via des transitions datées, pour que les tendances et le changelog soient exploitables.

## 4. Architecture cible

```
[Jira Cloud Free]  ──API──►  [1] Extraction incrémentale (JQL updated >= dernier run, changelog inclus)
                                   │   adaptateurs : Jira Cloud v3 / Jira Data Center v2
                                   ▼
                            [2] Modèle de données (DuckDB) : tickets, historique des statuts,
                                instantanés hebdomadaires par entité
                                   │
                ┌──────────────────┼────────────────────────────────┐
                ▼                  ▼                                ▼
   [3] KPI déterministes   [4] Météo par règles (YAML)   [5] Prévision de sortie du rouge
       (stocks, flux,          rouge/orange/vert             baseline burndown → modèle ML
        âges, taux KO)         + règle déclenchante          (probabilité + facteurs explicatifs)
                │                  │                                │
                └──────────────────┼────────────────────────────────┘
                                   ▼
                [6] Couche LLM (palier 2, sur un texte préalablement pseudonymisé)
                     a. Classification des causes racines + détection de doublons
                     b. Explication du rouge, en citant les tickets (citations vérifiées)
                     c. Brouillon des commentaires de météo pour le PPT
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
 [7] Excel (openpyxl)     [8] PPT (python-pptx,      [9] Agent conversationnel
     onglets KPI/météo        gabarit neutre)            outils lecture seule :
                                                         get_meteo, list_anomalies,
                                                         get_tendance, get_prevision
```

### Principes
- **Les chiffres ne passent jamais par le LLM.** KPI et météo sont déterministes et testés. Le LLM ne fait que lire, classer et rédiger.
- **La prévision est un modèle statistique ou ML, pas un LLM.**
  - Démarrer par une *baseline* : projection du stock de bloquantes à vélocité de résolution constante.
  - Passer ensuite à un modèle (gradient boosting ou analyse de survie) qui donne une **probabilité de sortie du rouge sous N jours ouvrés** avec ses facteurs explicatifs (SHAP).
  - Le LLM se contente de la narrer. Indispensable pour qu'un sponsor bancaire puisse auditer le résultat.
- **Explication fidèle.** Chaque phrase de l'explication cite des identifiants de tickets. Un contrôle déterministe vérifie que ces tickets existent et appartiennent bien à l'entité.
- **Fournisseur LLM interchangeable.** La même interface sert pour Claude, Azure OpenAI (souvent l'option disponible en banque) ou un modèle local via llama.cpp. Démontrer **le mode local** est un argument fort si la banque refuse un LLM externe.
- **Jira Cloud ≠ Jira Data Center.** Une banque est probablement en Data Center (API v2, PAT, pagination `startAt`), alors que Jira Cloud v3 pagine par `nextPageToken`. On prévoit deux adaptateurs, et celui de Data Center est testé sur fixtures.
- **Idempotence.** Rejouer une semaine produit le même rapport.

### Stack proposée (low-cost, open source)
| Brique | Choix |
|---|---|
| Langage, dépendances | Python 3.12, `uv` |
| Stockage, calcul | DuckDB + Polars |
| Règles de météo | YAML + moteur de règles maison (lisible par le métier) |
| Prévision | scikit-learn / LightGBM, `lifelines` en option, SHAP |
| LLM | Interface unique (LiteLLM ou équivalent) + sorties structurées Pydantic |
| Pseudonymisation | Microsoft Presidio (open source), adapté aux identifiants bancaires fictifs |
| Agent | LangGraph ou Pydantic AI, outils en lecture seule |
| Restitution | openpyxl, python-pptx, Streamlit pour l'agent et la démo |
| Observabilité, évaluations | Langfuse auto-hébergé, pytest, Inspect AI ou promptfoo |

## 5. Évaluation

| Composant | Méthode | Cible |
|---|---|---|
| KPI, météo | Rapport de référence calculé à la main sur un instantané figé ; test de réconciliation | **100 % d'égalité** |
| Classification des causes | Vérité terrain issue du générateur. Contre la circularité : textes générés par un autre modèle que le classifieur, plus 30 tickets rédigés à la main | F1 macro ≥ 0,8 |
| Explication du rouge | Citations vérifiées automatiquement + grille humaine 1–5 (exactitude, utilité) sur 10 cas | 100 % de citations valides ; ≥ 4/5 |
| Prévision | Sur le Public Jira Dataset : prédire la résolution des tickets bloquants sous N jours, comparée à la baseline (AUC, score de Brier). Sur les scénarios : A sort, B reste | Meilleur que la baseline ; scénarios conformes |
| Agent | 15 questions types du pilote, réponses vérifiées | ≥ 13/15 correctes, 0 chiffre inventé |
| Gain de temps | Chronométrage du reporting manuel vs automatique (déclaratif côté usine) | À mesurer : c'est l'argument central de la démo |

## 6. Scénario de démo (10 minutes)

1. **Avant / après** (1 min) : temps actuel du reporting hebdomadaire contre temps automatique.
2. **Lancement du pipeline** (2 min) : extraction Jira en direct, puis génération de l'Excel et du PPT.
3. **Météo** (2 min) : l'entité A est rouge, avec la règle déclenchante affichée et l'explication LLM sourcée (clic sur les tickets).
4. **Prévision** (2 min) : A sort probablement sous 10 jours, B non, avec les facteurs explicatifs.
5. **Agent** (2 min) : « Quelles entités risquent de passer au rouge la semaine prochaine, et pourquoi ? »
6. **Ce qu'il faut pour le faire en vrai** (1 min) : la liste d'outillage du § 8.

## 7. Sécurité et confidentialité

- **Démo 100 % fictive.** Aucun nom, aucun gabarit, aucun libellé ni aucune règle de météo réels de la banque. Les règles réelles ne seront intégrées qu'une fois dans l'environnement de la banque.
- **En cible réelle, pseudonymisation obligatoire avant tout appel LLM.** Les descriptions d'anomalies de migration bancaire contiennent typiquement des numéros de compte, des noms de clients ou des identifiants. Le démonstrateur doit **montrer** ce traitement (avec des identifiants fictifs injectés dans les données).
- **Agent en lecture seule.** Aucune écriture dans Jira, aucun envoi de mail dans le démonstrateur.
- **Traçabilité.** Chaque explication et chaque prévision sont journalisées avec la version du prompt et du modèle (exigence d'auditabilité en banque).
- **Validation préalable** du responsable de mission avant de présenter la démo au client.

## 8. Correspondance avec l'outillage cible et liste des demandes

### Correspondance par brique
| Brique | Serveur / VM Python | Dataiku | Power Platform | Poste local seul |
|---|---|---|---|---|
| Extraction Jira | ✅ | ✅ recette Python | ✅ connecteur Jira (limité sur le changelog et les volumes) | ✅ |
| KPI, météo | ✅ | ✅ recettes et scénarios | ⚠️ possible, peu maintenable | ✅ |
| Prévision ML | ✅ | ✅ (Visual ML) | ❌ | ✅ |
| LLM | ✅ endpoint validé | ✅ LLM Mesh | ✅ AI Builder / Copilot Studio | ⚠️ modèle local uniquement |
| Excel / PPT | ✅ | ✅ | ✅ | ✅ |
| Agent conversationnel | ✅ | ✅ (agents Dataiku) | ✅ Copilot Studio | ✅ |
| Planification | ✅ cron | ✅ scénarios | ✅ Power Automate | ⚠️ poste allumé |

### Demandes d'outillage, par ordre de priorité
1. **Compte de service Jira en lecture seule + jeton API.** Indispensable pour le palier 1.
2. **Environnement d'exécution Python** (VM ou Dataiku) avec accès réseau à Jira, plus un dépôt Git interne.
3. **Ordonnanceur et cible de publication** (SharePoint ou partage réseau).
4. **Endpoint LLM validé par la banque.** Palier 2. À défaut, modèle on-prem.

## 9. Plan de réalisation incrémental

Comme pour le projet précédent : jalons courts, critères d'acceptation vérifiables, point de contrôle avant chaque jalon suivant. **La démo est montrable dès M3 (palier 1).**

| Jalon | Contenu | Critères d'acceptation |
|---|---|---|
| **M0 — Socle** | Repo, `uv`, `CLAUDE.md`, tests, CI, configuration (entités, règles météo) | CI verte |
| **M1 — Données fictives** | Générateur et scénarios A/B/C ; création du site Jira Cloud Free, des champs personnalisés et injection via API ; 8 semaines d'historique | Tickets visibles dans Jira ; scénarios reproductibles par graine aléatoire |
| **M2 — ETL et modèle de données** | Extraction incrémentale + changelog, adaptateurs Cloud et Data Center, DuckDB, instantanés hebdomadaires, KPI, météo par règles | Réconciliation à 100 % avec le rapport de référence ; relance idempotente |
| **M3 — Reporting automatique (palier 1)** | Excel multi-onglets + PPT (gabarit neutre : synthèse, météo par entité, tendances, top anomalies) | Rapport hebdomadaire complet en < 5 min, une commande ; **démo palier 1 possible** |
| **M4 — Couche LLM** | Pseudonymisation, classification des causes, doublons, explication du rouge sourcée, brouillon des commentaires PPT, suite d'évaluation | Cibles du § 5 ; zéro donnée identifiante dans les traces Langfuse |
| **M5 — Prévision** | Baseline, modèle validé sur le Public Jira Dataset puis appliqué aux scénarios, SHAP, narration LLM | Meilleur que la baseline ; A et B correctement anticipés |
| **M6 — Agent et démo** | Agent conversationnel (outils en lecture seule) dans Streamlit, script de démo du § 6 | 13/15 aux questions types ; démo de 10 min répétée sans accroc |
| **M7 — Portage** | Dockerfile, note de portage Dataiku / Power Platform, fiche « outillage demandé » d'une page | Note validée par le responsable de mission |

**Modalités Claude Code** : reprendre les règles du `CLAUDE.md` du projet précédent (jalon par jalon, mode plan, `docs/QUESTIONS.md`, journal de fin de jalon, aucun appel LLM réel dans les tests unitaires).

## 10. Risques

| Risque | Mitigation |
|---|---|
| Démo jugée « trop synthétique » | Vraie API Jira ; prévision validée sur des données réelles publiques ; scénarios inspirés de cas plausibles |
| Promesse non tenable sur l'outillage réel (Data Center, réseau, droits) | Adaptateur Data Center dès M2 ; paliers 1 et 2 dissociés |
| LLM refusé par la banque | Palier 1 autonome ; mode modèle local démontré |
| Code développé sur temps personnel puis réutilisé chez le client | Décidé le 10/10/2026 : **projet personnel, dépôt public**. Aucune donnée, aucun libellé ni aucune règle réels du client dans le dépôt ; une réutilisation chez le client passe par la licence du dépôt |
| Site Jira Free désactivé après inactivité prolongée | Script de réinjection idempotent ; données régénérables |

## 11. Questions ouvertes et décisions

Réponses du 10/10/2026. Le PRD les intègre et remplace, là où elles divergent, les hypothèses des sections précédentes (notamment le rythme hebdomadaire).

1. **Grille de météo** : quatre couleurs, **vert / jaune / orange / rouge**. Aucune grille réelle ne sera fournie : le PRD propose des critères et des seuils plausibles (anomalies bloquantes ouvertes et leur âge, taux de KO des tests, certifications refusées ou réservées, tendance du flux), en configuration YAML.
2. **Volumétrie** : plusieurs milliers d'anomalies au total, quelques centaines de nouvelles par semaine, une dizaine d'entités. **Reporting quotidien** : instantanés et rapport par jour, tendances à la semaine.
3. **Contenu du reporting** : aucun modèle existant à reproduire. Le démonstrateur conçoit son propre format générique (onglets Excel et slides).
4. **Jira de la banque** : inconnu (Cloud ou Data Center). Les deux adaptateurs restent prévus ; la détection se fait par configuration.
5. ~~**Statut du travail**~~ : projet personnel, dépôt public, licence MIT.
6. **Priorité** : ce projet passe avant le projet « agent appels d'offres ».
7. **Moyens** :
   - **LLM disponibles** : clés Anthropic, OpenAI, Mistral, Google AI Studio ; Groq (offre gratuite, limites de débit à respecter). **Local** : GPU de 8 Go de VRAM sur le poste de développement.
   - **Référence d'implémentation** : la couche fournisseurs du dépôt voisin `agentic-harness-training-demo` (adaptateurs OpenAI Chat, Anthropic Messages, catalogue de modèles, espacement des appels, compression Headroom).
   - **Temps** : environ 1 h le matin et 1 h le soir en semaine, plus le week-end.
