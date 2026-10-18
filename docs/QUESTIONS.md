# Questions et hypothèses

Journal des hypothèses prises sans confirmation et des questions ouvertes. Chaque entrée renvoie à l'exigence concernée du PRD (`_bmad-output/planning-artifacts/prds/prd-usine-migration-jira-demo-2026-10-10/prd.md`).

Statuts : **à confirmer**, **confirmée**, **modifiée**, **rejetée**.

Rappel : dépôt public. Toutes les valeurs ci-dessous sont **inventées** ; aucune ne provient d'un client.

## Hypothèses

| ID | Hypothèse | Exigences | Impact si fausse | Statut |
|---|---|---|---|---|
| H-1 | Le calendrier fictif ne compte aucun jour férié (Jours ouvrés = lundi à vendredi) | Glossaire, FR-10, FR-20 | Ajout d'un calendrier de jours fériés en configuration | acceptée par défaut (10/10/2026) |
| H-2 | Volumétrie : 3 000 à 5 000 Anomalies sur 8 semaines, 200 à 500 nouvelles par semaine, 10 Entités (traduction de « plusieurs milliers, quelques centaines par semaine, une dizaine d'entités ») | FR-2, NFR-2 | Ajustement du générateur et des seuils IND-3 | modifiée (12/10/2026) : 3 000 à 4 000 Anomalies |
| H-3 | Au plus 2 Entités rouges en fin d'historique | FR-3 | Démo moins lisible si trop de rouges | acceptée par défaut (10/10/2026) |
| H-4 | Au moins 10 % des descriptions contiennent un identifiant sensible fictif | FR-4, FR-31 | Démonstration de la Pseudonymisation moins visible | acceptée par défaut (10/10/2026) |
| H-5 | L'API Jira ne permettant pas d'antidater les transitions, l'historique de 8 semaines vient du journal d'événements du générateur ; Jira Cloud porte l'état courant et les mises à jour en direct | FR-5, FR-8 | Si refusé : import CSV ou champ « date d'effet » (voir addendum § C) | confirmée (10/10/2026) |
| H-6 | Grille de météo par défaut : 8 indicateurs, seuils du § 4.4 du PRD, règle « la couleur la plus grave l'emporte », garde-fous de volume | FR-15, FR-16 | Seuils à revoir ; la règle d'agrégation change la restitution | confirmée telle quelle (10/10/2026) |
| H-7 | Baseline : vélocité nette sur 10 Jours ouvrés, horizon de prévision de 10 Jours ouvrés | FR-20 | Paramètres en configuration, impact faible | acceptée par défaut (10/10/2026) |
| H-8 | Risque d'entrée en rouge projeté à 5 Jours ouvrés (« la semaine prochaine ») | FR-21, FR-42 | Paramètre en configuration, impact faible | acceptée par défaut (10/10/2026) |
| H-9 | Format Excel en 9 onglets (Synthèse, Météo détaillée, KPI, Tendances, Anomalies ouvertes, Tests, Certifications, Commentaires, Traçabilité) | FR-26 | Ajout ou retrait d'onglets | acceptée par défaut (10/10/2026) |
| H-10 | Format PowerPoint en 7 sections, une slide par Entité rouge ou orange | FR-27 | Ajout ou retrait de slides | acceptée par défaut (10/10/2026) |
| H-11 | Fournisseurs LLM : Anthropic plus un second fournisseur distant parmi OpenAI, Mistral, Google, Groq | FR-30 | Faible : interface interchangeable | acceptée par défaut (10/10/2026) |
| H-12 | Classification des Causes racines classée **bonus** (non citée dans l'indispensable, inutile au scénario de démo) | FR-35, SM-9 | Si indispensable : M4 plus long, F1 ≥ 0,8 à tenir avant la démo | modifiée (10/10/2026) : classification **indispensable** |
| H-13 | Mode LLM local classé **bonus**, bien qu'il réponde au risque « LLM refusé par la banque » | FR-37 | Si indispensable : modèle à choisir pour 8 Go de VRAM, qualité d'explication à revalider | confirmée (10/10/2026) |
| H-14 | Palier 2 : Rapport quotidien en moins de 10 minutes pour au plus 4 Entités rouges ou oranges | NFR-2 | Ajustement de la cible de performance | acceptée par défaut (10/10/2026) |
| H-15 | Coût LLM d'un passage de démo complet inférieur à 1 € | NFR-9 | Choix de modèles moins chers ou mise en cache | acceptée par défaut (10/10/2026) |
| H-16 | Classés **indispensables** bien que non cités dans la consigne : Baseline de prévision et narration (étape 4 de la démo), adaptateur Data Center sur fixtures (§ 11 Q4), Pseudonymisation (§ 7 de la spec), Journal de traçabilité local (Langfuse étant bonus), mode repli de la démo | FR-7, FR-20, FR-21, FR-24, FR-31, FR-34, FR-45 | Si certains passent en bonus : périmètre indispensable réduit | confirmée (10/10/2026), les cinq briques restent indispensables |
| H-17 | Workflow fictif des Anomalies : Nouvelle, En analyse, En correction, À retester, Fermée, Rejetée. Anomalie ouverte = ni Fermée ni Rejetée ; Entrée = création ou réouverture ; Sortie = passage à Fermée ou Rejetée | Glossaire, FR-11, FR-13, IND-1, IND-7 | Correspondance de statuts à revoir dans le générateur et le calcul des KPI | à confirmer |
| H-18 | Sept catégories de Cause racine : reprise de données, règle de transformation, paramétrage, interface ou flux, environnement, donnée de test, hors périmètre (faux positif) | Glossaire, FR-2, FR-35, SM-9 | Le F1 macro dépend du nombre de classes | à confirmer |
| H-19 | Fenêtre glissante = 5 derniers Jours ouvrés (une semaine) au lieu de « 7 jours » ; comparaison de Météo à J-5 au lieu de J-7 | Glossaire, FR-11, FR-19, IND-7, IND-8 | Paramètre en configuration, impact faible | à confirmer |
| H-20 | Rapport de référence calculé à la main sur un jeu réduit figé (environ 2 Entités, 60 tickets, 1 Date d'arrêté) qui fait jouer chaque indicateur et chaque garde-fou | FR-13, SM-1 | Plus de travail manuel si le jeu doit être plus large | à confirmer |
| H-21 | Évaluation de la Baseline sur le Public Jira Dataset : référence naïve = taux historique de sortie sous N jours ; critère de réussite = score de Brier | FR-51, SM-10 | Protocole à revoir dans l'addendum § E | à confirmer |
| H-22 | Contre-indicateur de l'Agent : au plus 1 refus sur les 13 questions répondables | SM-C5, FR-42 | Seuil à ajuster | à confirmer |
| H-23 | Second fournisseur LLM = Mistral (offre gratuite aux limites publiées, éditeur français) | FR-30, AD-13 | Ajout d'un autre adaptateur derrière le même port | confirmée (10/10/2026) |
| H-24 | Polars 1.44.x plutôt que 2.0.0 (sortie le 2026-10-06, ruptures, agents formés sur la 1.x) | Stack, AD-9 | Migration vers 2.x à revoir le 2026-11-01 | confirmée (10/10/2026) |
| H-25 | Un horodatage est rattaché à un Jour ouvré dans le fuseau Europe/Paris | FR-10, AD-17 | Décalage d'un jour pour les événements nocturnes | confirmée (10/10/2026) |
| H-26 | Taux portés en fraction exacte (numérateur, dénominateur) ; seuils comparés en `Fraction` ; arrondi au rendu seulement | FR-13, AD-10 | Réconciliation par tolérance au lieu d'une égalité stricte | confirmée (10/10/2026) |
| H-27 | Si l'état rejoué d'un ticket diffère de l'état Jira, un événement d'alignement daté de l'extraction est émis et compté | FR-49, AD-4 | Autre règle de priorité Journal / Jira | confirmée (10/10/2026) |
| H-28 | L'interface lance la Chaîne de reporting en sous-processus (CLI) et suit `progression.jsonl` | FR-43, AD-8 | Exécution dans le processus de l'UI | confirmée (10/10/2026) |
| H-29 | Pseudonymes dérivés par HMAC d'une clé locale (`USINE_CLE_PSEUDO`), donc stables entre Passages et worktrees ; table de ré-identification locale (SQLite), hors Passage, hors traces et hors dépôt | FR-31, AD-15 | Cache LLM et réponses enregistrées invalidés si la clé change | confirmée (10/10/2026) |
| H-30 | Le Mode repli s'active à la main (bascule ou variable d'environnement), sans détection automatique | FR-45, AD-19 | Ajout d'une sonde de disponibilité | confirmée (10/10/2026) |
| H-31 | Un contrôle LLM en échec dégrade l'élément (libellé explicite) sans faire échouer le Passage ; un fournisseur injoignable fait échouer l'étape | FR-25, FR-32, AD-12 | Passage produit en Palier 1 quand le LLM tombe | confirmée (10/10/2026) |

## Questions ouvertes

| ID | Question | Exigences | Proposition par défaut | Statut |
|---|---|---|---|---|
| Q-1 | Accepte-t-on que l'historique vienne du journal d'événements (H-5) ? | FR-5, FR-8 | Oui | tranchée (10/10/2026) : journal d'événements |
| Q-2 | Faut-il des seuils de Grille différents par Phase ou par Vague ? | FR-15 | Non en v1, mais la configuration doit le permettre plus tard | proposition par défaut acceptée (10/10/2026) |
| Q-3 | Faut-il une hystérésis pour sortir du rouge (ex. 2 Jours ouvrés consécutifs sous le seuil) ? | FR-16 | Non en v1 | proposition par défaut acceptée (10/10/2026) |
| Q-4 | Le Pilote peut-il forcer une Météo avec justification ? | Hors objectifs | Non en v1 | proposition par défaut acceptée (10/10/2026) |
| Q-5 | Quel temps de reporting manuel afficher dans l'avant / après ? | FR-44, SM-2 | Valeur déclarative fictive en configuration | valeur à fournir en configuration, non bloquante |
| Q-6 | Les Entités orange reçoivent-elles aussi une Explication sourcée ? | FR-32, FR-33 | Oui (rouge et orange) | proposition par défaut acceptée (10/10/2026) |

## Décisions de la relecture du PRD (10/10/2026)

- **Entité A décalée** : rouge à partir de la semaine 6 et encore rouge en fin d'historique, avec une sortie projetée, pour que la démo du jour la montre rouge (FR-3). Écart assumé avec la spec § 3 (rouge en semaine 3, orange en semaine 5).
- **Baseline évaluée sur données réelles** : la méthode est testée sur le Public Jira Dataset (FR-51, indispensable) et restitue une probabilité et des facteurs explicatifs déterministes (FR-20). Le Modèle ML reste en bonus.
- **Agent en Mode repli** : les réponses aux questions de la démo sont enregistrées lors d'une répétition et rejouées, avec une mention visible (FR-45).
