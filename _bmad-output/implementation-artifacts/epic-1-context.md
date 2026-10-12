# Epic 1 Context: Programme fictif dans Jira (L1 Données)

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

L'auteur génère, à partir d'une configuration et d'une graine, le Programme fictif « Banque Exemple — migration SI cœur » : ses tickets (Anomalies, Cas de test, Certifications), ses 8 semaines d'historique sous forme de Journal d'événements et ses trois Scénarios de démo (A, B, C). Il l'injecte ensuite dans Jira Cloud Free de façon idempotente. Toute la démo repose sur ces données : elles doivent être reproductibles, entièrement fictives et assez épaisses pour ressembler à une vraie usine. Elles doivent aussi être calées pour que la Météo, la Prévision et la Pseudonymisation montrent le jour de la démo exactement ce que le scénario promet.

## Stories

- Story 1.1 : Configuration complète du Programme
- Story 1.2 : Corpus de textes provisoire et outil de génération
- Story 1.3 : Génération reproductible à la volumétrie cible
- Story 1.4 : Identifiants sensibles fictifs
- Story 1.5 : Scénarios de démo scriptés
- Story 1.6 : Injection initiale dans Jira Cloud Free
- Story 1.7 : Réinjection idempotente et clés stables
- Story 1.8 : Calage des Scénarios de démo au jour près
- Story 1.9 : Corpus de textes définitif par LLM

## Requirements & Constraints

- **Configuration** (`config/programme.yaml`) : 10 Entités `ENT-A` à `ENT-J`, 3 Vagues, chacune avec son calendrier de Phases (migration à blanc, recette, TNR), des Domaines et la volumétrie. Changer le nombre d'Entités ou la volumétrie ne demande aucun code. Chaque clé porte un commentaire en français (vérifié par test). Aucun nom réel d'organisation ou de personne. Une erreur nomme le fichier, la clé et la valeur.
- **Volumétrie cible** : 3 000 à 5 000 Anomalies sur 8 semaines, 200 à 500 Entrées par semaine.
- **Reproductibilité** : même graine et même Corpus donnent un Journal identique (structure, dates relatives, affectations, textes). Régénérer les données n'émet aucun appel LLM.
- **Calendrier** : l'historique se termine au dernier Jour ouvré avant la date de génération, et la semaine 1 commence 8 semaines plus tôt. Jours ouvrés du lundi au vendredi, sans jour férié.
- **Workflow des Anomalies** : Nouvelle → En analyse → En correction → À retester → Fermée ou Rejetée, réouvertures comprises (hypothèse H-17). Une Entrée est une création ou une réouverture ; une Sortie est un passage à Fermée ou Rejetée. Gravité : bloquante, majeure ou mineure. Cas de test : OK, KO ou non exécuté. Certification : accordée, réservée ou refusée.
- **Cause racine** : chaque Anomalie en a une parmi 7 (reprise de données, règle de transformation, paramétrage, interface ou flux, environnement, donnée de test, hors périmètre ; hypothèse H-18). Elle n'est jamais exposée dans Jira ni dans un `Evenement`.
- **Identifiants sensibles fictifs** dans au moins 10 % des descriptions d'Anomalies : comptes, clients, identifiants, au format plausible mais invalide (par exemple un IBAN à clé fausse). La liste des identifiants injectés est écrite dans `donnees/`, hors git, pour le test de balayage de la Pseudonymisation.
- **Scénarios avec la Grille par défaut** :
  - A : verte ou jaune jusqu'à la semaine 5, rouge à partir de la semaine 6 (bloquantes de reprise de données), Sorties > Entrées à partir de la semaine 7. Sortie projetée dans l'horizon.
  - B : rouge de la semaine 2 à la fin (Entrées > Sorties), sans sortie projetée.
  - C : verte jusqu'à la semaine 3, jaune en semaines 4 à 6, orange en semaines 7 et 8 (taux de KO en TNR en hausse), avec un Risque d'entrée en rouge.
  - Hors A, B et C : aucune Entité rouge plus de 3 Jours ouvrés consécutifs, au moins 80 % des couples Entité × Date d'arrêté verts ou jaunes, au plus 2 Entités rouges en fin d'historique.
- **Interdit** : ajuster les seuils de la Grille pour faire passer un scénario. Ce sont les paramètres du générateur qui s'adaptent.
- **Injection** : sur un site vierge, elle recrée le projet `DEMO`, les types de tickets, le workflow et les champs Entité, Vague, Domaine, Gravité et Phase. Elle charge l'état courant à la Date d'injection. Une réinjection ne crée aucun doublon. Les clés sont stables, ou une table de correspondance est produite. L'URL du site est en configuration. L'injection est lancée depuis `main`.
- **Corpus** : il est produit une fois par un LLM distinct du classifieur des Causes racines, puis versionné. Le Corpus provisoire, construit par gabarits, porte `modele_corpus: gabarits-provisoires`.
- **Dépôt public** : tout est fictif, aucun secret. gitleaks tourne en CI. Les tests unitaires n'appellent ni Jira ni un LLM réel.

## Technical Decisions

- **Périmètre d'écriture de la lane** : `generateur/`, `outils/`, `config/programme.yaml`, `donnees/corpus/` et leurs tests miroirs (`tests/unit/...`). La CI le contrôle sur `lane/1-*`.
  - `contrats/`, `ports/`, le chargeur `config/`, `composition.py`, `cli.py`, `tests/contrat/` et `tests/doublures/` appartiennent à `main`. Pour les modifier, ouvrir une PR courte sur `main`, puis rebaser.
  - `config/jira.yaml` appartient à L2.
- **Couches** : `generateur/` n'importe que `contrats` et `ports`, sans externe hors du socle (pydantic, polars, stdlib). `outils/` est hors produit et peut importer `composition`. Le générateur reçoit la graine et la date en paramètre : pas de `datetime.now` ni de hasard implicite dans le code pur.
- **Contrat `Evenement`** (`contrats.evenements`) : `id_evenement`, `cle_ticket`, `type_ticket`, `horodatage` (UTC, avec fuseau), `nature` ∈ {creation, transition, modification_champ, alignement}, `champ`, `de`, `vers`, `source`.
  - Une création est suivie, au même horodatage, d'un `modification_champ` par attribut initial, titre et description compris.
  - Les identifiants du Journal sont `J-<rang>`, déterministes.
- **Journal** : fichier JSONL de `Evenement`, précédé d'un `EnteteJournal` (graine, date de génération, Date d'injection, version et `modele_corpus` du Corpus, `ancrage_semaines` = lundi de la semaine 1). Il n'est jamais au format Jira.
- **Vocabulaire canonique** (`contrats.tickets`) : énumération `Champ` (statut, entite, vague, domaine, gravite, phase, titre, description, statut_test, statut_certification) et ses domaines de valeurs. Le Journal n'émet que des valeurs canoniques. La correspondance vers les noms Jira (champs personnalisés, statuts) vient de `config/jira.yaml` et ne s'applique qu'au moment de l'injection.
- **Vérité terrain** : `donnees/verite_terrain.json`, lue seulement par `evals/`. Un test vérifie qu'aucun `Evenement` ne la porte.
- **Temps** : `contrats.calendrier` est la seule source de `jour_local` (Europe/Paris), `jour_ouvre_de`, Fenêtre glissante, J-1, J-5 et `semaine_programme(d, ancrage)`.
- **Injecteur** (`generateur/injecteur`) : seul écrivain Jira, avec `JIRA_TOKEN_INJECTION`. La composition de `usine rapport` ne lit jamais cette variable.
  - Il passe uniquement par l'API REST, via le transport commun `adaptateurs/jira_http` (pagination, authentification, reprise sur 429 avec `Retry-After`). Pas d'import CSV ou JSON : l'API ne permet pas d'antidater, d'où l'historique porté par le Journal.
  - Les tickets sont créés dans un ordre déterministe, puis amenés à leur état à la Date d'injection.
  - Il écrit `donnees/injection/manifeste_injection.json` (`ManifesteInjection` : Date d'injection, `debut_injection`, `horodatage_fin_injection`, `correspondance_cles`, clé de projet). La clé canonique en aval est la clé Jira, et la correspondance s'applique à la lecture du Journal.
  - Limites Jira Cloud Free pour un jeton API : rafales d'environ 100 requêtes/s par endpoint, et par ticket 20 écritures par 2 s et 100 par 30 s. Prévoir un débit de quelques requêtes par seconde.
- **Spike d'une demi-journée en début de lane** : créer le workflow et les champs personnalisés par l'API sur Jira Free. Repli : procédure manuelle documentée, les tickets restant injectés par l'API.
- **Corpus** : `outils/generer_corpus.py` passe par le port `FournisseurLLM` (`generer_structure` seulement), sans aucun SDK de fournisseur importé. La graine sélectionne et affecte les textes. Garde-fou : `usine.config` refuse un modèle de classification égal au `modele_corpus`.
- **Secrets** : uniquement en variables d'environnement (`JIRA_EMAIL`, `JIRA_TOKEN_INJECTION`…). Une lane qui doit écrire dans Jira utilise sa propre clé de projet (`JIRA_PROJET`).
- **Erreurs** : exceptions dérivées de `UsineErreur`. Logs en français.

## Cross-Story Dependencies

- 1.1 → 1.3 → 1.4 et 1.5 : la configuration précède la génération, qui précède les identifiants et les scénarios.
- 1.2 précède 1.3 : le Corpus provisoire suffit jusqu'à la porte Palier 1.
- 1.6 → 1.7.
- **Externes** :
  - Story 2.1 (transport `jira_http`, L2) avant la 1.6.
  - Epic 3 terminé (calcul complet de la Météo et Grille par défaut) avant la 1.8.
  - Story 6.1 (adaptateurs LLM réels) avant la 1.9. La 1.9 relance ensuite le test de la 1.8, puis alimente la Story 6.9 (évaluation de la classification).
- **En aval** :
  - L2 consomme le Journal et le manifeste (Source composite, test de cohérence à la Date d'injection, Story 2.7).
  - L4 consomme les Scénarios (Story 4.5).
  - L5 en fait la recette de bout en bout (Story 5.6).
  - L6 utilise la liste des identifiants injectés pour le balayage de la Pseudonymisation.
