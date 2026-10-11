---
type: review
lens: reconciliation spine ↔ PRD / addendum / QUESTIONS
cible: ../ARCHITECTURE-SPINE.md
date: 2026-10-10
---

# Revue de réconciliation : spine d'architecture contre PRD, addendum et QUESTIONS

Périmètre : ce qui, dans le PRD (`prd.md`), l'addendum ou `docs/QUESTIONS.md`, n'a pas atterri dans le spine, ou y est contredit. Ne sont retenus que les points où deux lanes indépendantes pourraient diverger, ou une contradiction avec la source. Les détails UX ou de contenu que le PRD fixe déjà sont ignorés.

## Verdict

**À reprendre avant le gel `contrats-v1` (E0-9).** Le spine couvre bien l'ossature (hexagonal, Passage immuable, passerelle LLM, contrôles partagés, calendrier). Mais deux trous de contrat et une contradiction de cache touchent plusieurs lanes à la fois :

1. il n'existe aucun contrat de **ticket** (attributs, textes, état à une date), alors que l'Excel, l'Agent, la classification et la Pseudonymisation en ont besoin ;
2. la clé de cache, telle que `version_donnees` est définie, **ne touche jamais** d'un Passage à l'autre, ce qui casse FR-14, FR-35, NFR-2 et NFR-9 ;
3. les traces de l'Agent n'ont pas d'emplacement compatible avec l'immuabilité du Passage.

Sévérités : **Critique** (contradiction ou divergence certaine entre lanes, bloque le gel), **Majeure** (divergence probable, à trancher dans le spine), **Mineure** (à préciser, coût faible).

## Constats

### R-1 [Critique] `version_donnees` dans la clé de cache invalide le cache à chaque Passage (FR-14, FR-35, NFR-2, NFR-9)

- **Source.** FR-14 : le Rejeu réutilise les sorties LLM en cache « pour la même Date d'arrêté, la même Entité et les mêmes versions de prompt, de modèle et de données ». FR-35 : classification incrémentale, seules les Anomalies nouvelles ou modifiées sont reclassées. NFR-9 : < 1 € par Passage, classification initiale exclue.
- **Spine.** AD-12 met `version_donnees` dans la clé. AD-16 la définit comme « SHA-256 du Journal + `horodatage_extraction` ». Or chaque Passage refait une extraction (AD-8, l'étape `extraction` est la première), donc `horodatage_extraction` change à chaque Passage.
- **Conséquence.** Aucune entrée du cache n'est réutilisée d'un Passage à l'autre, ni au Rejeu. Toutes les Anomalies sont reclassées chaque jour, ce qui revient à la classification initiale (3 000 à 5 000 appels). NFR-2 (< 10 min) et NFR-9 (< 1 €) sont alors intenables. La tension existe déjà dans le PRD (FR-14 cite « version de données » et le Glossaire y met l'horodatage). C'est au spine de la résoudre.
- **Correctif proposé.** Garder `version_donnees` dans `EntreeTrace` pour l'audit (NFR-6), mais la retirer de la clé de cache. L'identité des données est déjà portée par l'empreinte de l'entrée pseudonymisée. Écrire explicitement « clé = (tache, cible, date_arrete sauf classification, version_prompt, version_modele, empreinte_entree) ».

### R-2 [Critique] Aucun contrat de ticket : attributs, textes et état à une date (FR-2, FR-5, FR-11, FR-26 onglets 5 à 7, FR-31, FR-35, FR-39)

- **Source.** Les Anomalies portent Entité, Vague, Domaine, Gravité, Phase et un texte (FR-2, FR-4, FR-5). L'onglet 5 liste les Anomalies ouvertes avec clé, Domaine, âge et Cause racine proposée. `list_anomalies` filtre les Anomalies « pour toute Date d'arrêté disponible » (FR-39). La classification et l'Explication lisent les textes après Pseudonymisation (FR-31, FR-35).
- **Spine.** `Evenement` porte un seul triplet `champ / de / vers` et `type_ticket`, sans Entité ni texte. AD-6 parle d'un « état courant » stocké dans l'entrepôt, sans contrat. La liste des fichiers d'un Passage ne contient aucune table au niveau du ticket : `instantanes.parquet` est au niveau de l'Entité selon le Glossaire. AD-11 interdit à `rendu`, `ui` et `ia` de lire autre chose que le Passage.
- **Conséquence.** La lane L1 (forme de la création dans le Journal), la lane L2 (état courant Jira), la lane L3 (rattachement d'un ticket à une Entité), la lane L5 (onglets 5 à 7) et la lane L6 (d'où viennent les textes à classer) inventeront chacune leur forme. Sans table de tickets dans le Passage, AD-11 rend l'onglet 5 et `list_anomalies` impossibles.
- **Correctif proposé.** Ajouter aux Contrats v1 :
  - `TicketCourant` (clé, type, Entité, Vague, Domaine, Gravité, Phase, statut, titre, description), exposé par `SourceTickets` ;
  - la règle de forme d'une création dans le Journal (un événement `creation` suivi d'événements `modification_champ` par attribut, ou un payload d'attributs) ;
  - un fichier de Passage `tickets.parquet` (état de chaque ticket par Jour ouvré, ou à la Date d'arrêté plus les dates de transition), alimenté par le domaine.

### R-3 [Critique] Traces de l'Agent incompatibles avec l'immuabilité du Passage (FR-34, AD-7, AD-16)

- **Source.** FR-34 : chaque appel LLM est tracé localement, ce qui inclut les appels de l'Agent.
- **Spine.** AD-16 écrit les traces dans `<Passage>/trace/llm.jsonl`. AD-7 interdit de modifier un Passage publié. Or l'Agent s'exécute dans l'UI, après publication.
- **Conséquence.** Les traces de l'Agent seront soit perdues, soit écrites dans un Passage publié en violation d'AD-7. Le choix variera selon le développeur de L7.
- **Correctif proposé.** Écrire les traces de l'Agent hors Passage, dans `donnees/traces/agent-<date>.jsonl` en ajout seul, chaque entrée portant le `passage_id` consulté. Le test SM-7 balaie aussi ce fichier.

### R-4 [Majeure] Autoportance du Passage : périmètre des sorties LLM et des Prévisions par jour ambigu (AD-7, NFR-2, NFR-9, FR-39)

- **Spine.** AD-7 demande que le Passage permette de « rendre et répondre à toute Date d'arrêté ≤ sa Date d'arrêté », puis énumère « Instantanés, KPI, Indicateurs et Météo de chaque Jour ouvré », suivis de « Tendances, Prévisions, sorties LLM ».
- **Conséquence.** On peut lire que les Explications et les Prévisions sont attendues pour chacun des 40 Jours ouvrés de l'historique. Pour le LLM, cela ferait environ 40 × 4 explications par Passage, hors budget NFR-9. Une autre lane ne les produira qu'à la Date d'arrêté, et l'Agent (FR-39, « toute Date d'arrêté disponible ») ne saura pas quoi répondre pour une Prévision passée.
- **Correctif proposé.** Préciser : les calculs déterministes (Instantanés, KPI, Météo, Prévisions et Risques) sont produits pour chaque Jour ouvré, et les sorties LLM pour la seule Date d'arrêté du Passage. Pour une date passée, l'Agent répond sans Explication, ou lit le Passage de cette date s'il existe.

### R-5 [Majeure] Définition de la « semaine » non fixée (FR-3, FR-12, FR-16)

- **Source.** FR-12 : la Tendance agrège par semaine (valeur du dernier Jour ouvré, Entrées et Sorties cumulées), sur 8 semaines. FR-3 : trajectoires par numéro de semaine 1 à 8, vérifiées « au jour près » (FR-16). FR-2 : la semaine 1 commence 8 semaines avant la fin de l'historique.
- **Spine.** AD-17 définit le Jour ouvré, la Fenêtre glissante, J-1 et J-5, mais pas la semaine du Programme.
- **Conséquence.** La semaine peut être une semaine ISO du lundi au vendredi, ou un bloc de 5 Jours ouvrés compté à rebours depuis la Date d'arrêté. Selon la lecture retenue par L1 (scénarios) et par L3 (Tendances, test FR-16), le test au jour près échoue. La Tendance de la semaine en cours (partielle) n'est pas définie non plus.
- **Correctif proposé.** `domaine.calendrier.semaine_programme(d)` : semaine ISO du lundi au vendredi, numérotée de 1 à 8 depuis l'ancrage du générateur. La semaine en cours est partielle, et sa valeur est celle de la Date d'arrêté.

### R-6 [Majeure] Rejeu : les fichiers de rapport et l'onglet Traçabilité ne peuvent pas être identiques (FR-14, AD-7)

- **Source.** FR-14 : le Rapport quotidien est identique au Rejeu, « à l'exception de l'horodatage de génération ».
- **Spine.** Le test d'AD-7 compare les tables et les JSON, hors horodatages du manifeste. Il ne dit rien du `.xlsx` ni du `.pptx` : métadonnées `docProps`, dates des entrées zip, onglet 9 avec horodatage d'extraction et `version_donnees`.
- **Conséquence.** Un développeur compare les octets et le test échoue toujours. Un autre ne compare rien et FR-14 n'est pas tenu sur le rapport.
- **Correctif proposé.** Écrire que le rendu est déterministe : `docProps` fixés sur la Date d'arrêté, ordre stable. Le test de Rejeu compare les valeurs des cellules et les textes des slides, en excluant une liste nommée de champs (horodatage de génération, horodatage d'extraction, `passage_id`).

### R-7 [Majeure] « Dernier Passage réussi » choisi sur `horodatage_fin`, donc un Rejeu d'une date ancienne devient la vue courante (AD-7, FR-43, FR-45)

- **Spine.** AD-7 définit le dernier Passage comme le plus récent publié, au sens de `ManifestePassage.horodatage_fin`.
- **Conséquence.** Après le Rejeu d'une date passée (cas prévu par FR-14 et utile en répétition), l'UI et le Mode repli affichent cette vieille Date d'arrêté comme « le jour ». La carte météo de la démo est fausse.
- **Correctif proposé.** Prendre le Passage courant au maximum de `date_arrete`, puis au maximum de `horodatage_fin`.

### R-8 [Majeure] Événements `alignement` : non idempotents et datés de l'extraction (FR-6, FR-14, AD-4)

- **Spine.** AD-4 émet un `Evenement nature=alignement` « horodaté de l'extraction » quand l'état rejoué diffère de l'état Jira. Les identifiants d'AD-3 ne couvrent que le Journal et le changelog.
- **Conséquence.** Si l'écart persiste, chaque Passage émet un nouvel événement avec un nouvel horodatage, ce qui contredit FR-6 (« un deuxième Passage sans modification n'ajoute ni ne modifie aucun ticket stocké »). Selon qu'il est persisté ou recalculé à la lecture, deux lanes produiront des Instantanés différents.
- **Correctif proposé.** `id_evenement` déterministe `ALN-<cle>-<champ>-<valeur cible>`, horodaté à la première détection, persisté une seule fois dans l'entrepôt par l'étape `extraction`.

### R-9 [Majeure] Côte à côte original et pseudonymisé sans chemin de données (FR-31)

- **Source.** FR-31 : « l'interface peut montrer côte à côte un texte original et sa version pseudonymisée ».
- **Spine.** `ui` ne peut importer que `contrats`, `consultation` et `composition`. La table des pseudonymes est lue « seulement par `ia.passerelle` » (AD-15). Les traces ne contiennent que le texte pseudonymisé, et le Passage ne contient aucun texte original (voir R-2).
- **Conséquence.** L7 devra soit violer AD-15 ou le diagramme d'import, soit renoncer à l'écran.
- **Correctif proposé.** Ajouter au Passage un fichier `llm/exemples_pseudonymisation.json` (échantillon de couples original et pseudonymisé), produit par la passerelle et ignoré par git. On peut aussi exposer `Pseudonymiseur.apercu(texte)` via `composition`, en lecture locale.

### R-10 [Majeure] Calcul de la répartition des Causes racines non attribué (FR-35, FR-32, AD-9)

- **Source.** FR-35 : la répartition des Causes racines par Entité alimente l'Explication et l'onglet 8.
- **Spine.** AD-9 interdit à `ia` et à `rendu` de dériver un nombre. Pourtant, la répartition dépend des sorties de classification, produites après les étapes du domaine. Aucune étape ni aucun fichier ne la porte.
- **Conséquence.** L6 la calculera dans `ia`, contre AD-9, ou L5 dans `rendu`. Ses chiffres ne seront pas dans `valeurs_autorisees` pour `controler_nombres`.
- **Correctif proposé.** Créer une fonction pure `domaine.causes.repartition(classifications)`, appelée par `chaine` après l'étape `classification`. Elle écrit `llm/repartition_causes.parquet`, et ses valeurs entrent dans `valeurs_autorisees`.

### R-11 [Majeure] Corpus de textes : outil et garde-fou « LLM distinct du classifieur » absents (FR-2, SM-9, addendum § C)

- **Source.** FR-2 : le Corpus est généré une fois par un LLM distinct du classifieur, puis versionné. SM-9 mesure le F1 sur des textes générés par un autre modèle.
- **Spine.** `generateur` ne peut importer que `domaine.calendrier`, donc ni `ia` ni les adaptateurs. Aucun composant ne génère le Corpus. Rien n'enregistre le modèle qui l'a produit, et rien n'empêche `config/llm.yaml` de désigner le même modèle pour la classification.
- **Conséquence.** L1 appellera un SDK directement, contre AD-12 et AD-13, ou bien le Corpus sera écrit à la main. Le critère de SM-9 n'est pas vérifiable.
- **Correctif proposé.** Ajouter un script ponctuel hors produit (`outils/generer_corpus`, passant par `FournisseurLLM`) qui écrit `donnees/corpus/` avec une métadonnée `modele_corpus`. `usine.config` refuse une configuration où le modèle de classification est égal à `modele_corpus`.

### R-12 [Majeure] Vérité terrain des Causes racines : emplacement non fixé (FR-2, FR-50, Glossaire)

- **Source.** Glossaire : la Cause racine générée est une « vérité terrain cachée à la Chaîne de reporting ». FR-50 l'utilise pour évaluer la classification.
- **Spine.** Le spine ne dit pas si elle figure dans le Journal (en en-tête, ou comme `champ` d'un événement). Si c'est le cas, `SourceJournal` la fera entrer dans la chaîne, puis dans le prompt de classification.
- **Correctif proposé.** Écrire la vérité terrain dans un fichier séparé, `donnees/verite_terrain.json`, jamais dans le Journal ni dans Jira. Seul `evals/` le lit. Un test vérifie qu'aucun `Evenement` ne porte le champ `cause_racine`.

### R-13 [Majeure] Mode repli : contenu de `demo/repli/` et appariement des questions (FR-45, NFR-12)

- **Source.** FR-45 : affichage du dernier Passage enregistré et des réponses de l'Agent enregistrées en répétition. NFR-12 : jouable sans réseau.
- **Spine.** Le contrat `ReponseAgentEnregistree` existe, et `demo/repli/` est versionné. Le spine ne précise pas :
  - si le Passage de repli est dans `sorties/` (non versionné) ou copié dans `demo/repli/` ;
  - comment une réponse est rattachée au Passage, pour que ses chiffres concordent avec la Météo affichée ;
  - comment une question saisie est appariée à une réponse enregistrée ;
  - quelle commande enregistre les réponses.
- **Correctif proposé.** `demo/repli/` contient une copie d'un Passage publié et des réponses portant ce `passage_id`. En Mode repli, l'UI propose les questions enregistrées sous forme de choix (pas de saisie libre). L'enregistrement se fait par `usine agent --enregistrer`.

### R-14 [Majeure] Coût par Passage : aucun champ pour le mesurer (NFR-9)

- **Spine.** Le plafond de coût est différé à `config/llm.yaml` et un registre des prix est évoqué (AD-13). Mais ni `EntreeTrace` ni `ManifestePassage` ne portent de jetons ou de coût, et le comportement en cas de dépassement n'est pas défini.
- **Conséquence.** NFR-9 n'est pas vérifiable. L6 et L7 choisiront chacune leur réaction au dépassement : échec, dégradation ou simple alerte.
- **Correctif proposé.** Ajouter `jetons_entree`, `jetons_sortie` et `cout_estime_eur` à `EntreeTrace`, ainsi que `cout_llm_eur` et `classification_initiale: bool` à `ManifestePassage`. Au-delà du plafond, la passerelle dégrade les éléments restants (AD-12) sans faire échouer le Passage.

### R-15 [Majeure] Tokenisation des nombres par `controler_nombres` non définie (FR-24, FR-40, NFR-11)

- **Spine.** AD-14 compare les nombres du texte aux valeurs fournies et à leurs formes françaises, mais ne dit pas ce qu'est un « nombre » dans le texte.
- **Conséquence.** `DEMO-123`, `IND-4`, `ENT-A`, `J-5`, une date « 10/10/2026 », « semaine 6 », « 6 points » ou « 1 234,5 » seront traités différemment par la narration et par l'Agent. Les deux contrôleurs sont censés être partagés, et la suite d'évaluation SM-4 compte « zéro chiffre inventé » selon cette définition.
- **Correctif proposé.** Fixer dans `ia.controles` l'expression d'extraction : les clés de ticket, les codes IND et ENT et les J-n sont exclus ; les dates doivent figurer dans les dates autorisées ; les nombres sont lus au format français (espace insécable, virgule, %).

### R-16 [Mineure] Régénération unique de l'Explication bloquée par le cache (FR-32, AD-12)

- **Source.** FR-32 : si plus de la moitié des phrases sont retirées, l'Explication est régénérée une fois.
- **Spine.** La clé de cache ne distingue pas les tentatives. La régénération retombe donc sur la même sortie en cache.
- **Correctif proposé.** Ajouter `tentative` à la clé. Le cache stocke la réponse brute avant contrôle, et le Rejeu rejoue les deux tentatives.

### R-17 [Mineure] Avant / après : « temps mesuré » et cumul hebdomadaire ambigus (FR-44, NFR-2, SM-2)

- **Spine.** AD-8 enregistre les durées des étapes, mais ne fixe pas la mesure affichée. Elle peut être celle du dernier Passage, ou une moyenne. Il faut aussi savoir si un Passage servi par le cache ou un Passage de classification initiale est exclu (NFR-2 l'exclut), et si le cumul hebdomadaire vaut 5 fois le dernier Passage ou la somme des 5 derniers Passages.
- **Correctif proposé.** Temps mesuré = `horodatage_fin − horodatage_debut` du Passage courant, à condition que `classification_initiale = false`. Cumul hebdomadaire = 5 × ce temps. Le temps manuel déclaré vient de `ConfigDemo` (Q-5).

### R-18 [Mineure] Rapport de référence : forme des fixtures non fixée (FR-13, H-20)

- **Spine.** AD-10 précise la comparaison et L3 possède `tests/fixtures/reference`. Mais rien ne fixe que le jeu réduit soit un Journal, ni comment écrire les valeurs attendues (taux, valeurs infinies, non évaluable).
- **Correctif proposé.** `reference/journal.jsonl` est un Journal au format AD-3. `reference/attendu.yaml` contient des entiers et des fractions `"n/d"`, `infini` et `non_evaluable`. Le jeu est écrit à la main et indépendant du générateur.

### R-19 [Mineure] Mode Journal seul : clés et liens (FR-8, FR-29, AD-4, AD-11)

- **Spine.** En source Journal seule, il n'y a pas de manifeste d'injection, donc les clés restent celles du générateur. `url_ticket` n'est désactivé qu'en Mode repli, si bien qu'il produira des liens vers des tickets Jira inexistants.
- **Correctif proposé.** `url_ticket` renvoie `None` quand la source n'est pas Jira ou que la clé est absente de la correspondance. Les suites d'évaluation (vérité terrain par clé générée) appliquent la même correspondance.

### R-20 [Mineure] Bornes de l'historique pour J-5, la Fenêtre glissante et la vélocité (FR-19, FR-20, IND-8)

- **Spine.** Rien n'est dit quand J-5, la Fenêtre de 10 Jours ouvrés ou les 20 Jours ouvrés de la fourchette tombent avant le début de l'historique.
- **Correctif proposé.** `domaine.calendrier` renvoie « non disponible ». L'indicateur passe alors en `non_evaluable` avec un motif (AD-10), plutôt que de compter zéro.

## Points vérifiés sans écart

- **FR-35, suggestion jamais écrite dans Jira** : tenu par AD-5. Seul l'injecteur écrit, et l'Agent n'a aucun accès à Jira.
- **FR-46** : le filtre `palier` de `Consultation` suffit. **FR-28** : étapes `sautee`.
- **FR-19** : J-1 et J-5 dans `domaine.calendrier`, Météo de chaque jour dans le Passage, sous réserve de R-20.
- **FR-12** : le contrat `Tendance` existe. La définition de la semaine manque (R-5).
- **NFR-11** : prompts, journalisation et formatage en français sont couverts. Aucun contrôle de langue des sorties LLM n'est prévu, ce qui est acceptable pour une démo.
- **NFR-13** : porte hors logiciel, sans conséquence d'architecture.
- **NFR-2** : pas d'AD dédiée. Les risques réels passent par R-1, R-4 et R-14. Un test de durée sur la volumétrie de FR-2, avec chronométrage des étapes depuis le manifeste, suffirait.
- **FR-9, FR-30, FR-31 (ordre de la ré-identification), FR-34 (Prévisions), FR-18, NFR-4, NFR-10** : couverts par AD-5, AD-13, AD-12, AD-16 et AD-19.

## Synthèse des correctifs à porter au spine avant E0-9

| # | Où | Changement |
| --- | --- | --- |
| R-1 | AD-12, AD-16 | Retirer `version_donnees` de la clé de cache (conservée en trace) |
| R-2 | Contrats v1, fichiers d'un Passage | `TicketCourant`, forme de la création dans le Journal, `tickets.parquet` |
| R-3 | AD-16 | Traces de l'Agent hors Passage, avec `passage_id` |
| R-4 | AD-7 | Calculs déterministes pour chaque Jour ouvré ; sorties LLM à la Date d'arrêté seulement |
| R-5 | AD-17 | `semaine_programme` (semaine ISO, numérotée de 1 à 8) |
| R-6 | AD-7 | Rendu déterministe ; Rejeu comparé sur le contenu, avec une liste d'exclusions |
| R-7 | AD-7 | Passage courant au maximum de `date_arrete`, puis de `horodatage_fin` |
| R-8 | AD-3, AD-4 | `id_evenement` d'alignement déterministe, persisté une fois |
| R-9 | AD-11, AD-15 | Fichier d'exemples de Pseudonymisation dans le Passage |
| R-10 | AD-9, AD-8 | `domaine.causes.repartition` après l'étape de classification |
| R-11 | Arborescence, AD-19 | `outils/generer_corpus` et `modele_corpus` différent du classifieur |
| R-12 | AD-3 | Vérité terrain hors Journal |
| R-13 | AD-19, arborescence | Contenu de `demo/repli/`, appariement des questions, commande d'enregistrement |
| R-14 | Contrats `EntreeTrace`, `ManifestePassage` | Jetons, coût, `classification_initiale`, comportement au plafond |
| R-15 | AD-14 | Grammaire des nombres de `controler_nombres` |
| R-16 à R-20 | AD-12, AD-8, L3, AD-11, AD-17 | Précisions mineures |
