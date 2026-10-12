# Epic 5 Context: Rapport quotidien en une commande (L5 Rapport)

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Permettre au Pilote de produire, d'une seule commande (`usine rapport`) et en moins de 5 minutes, le Rapport quotidien d'une Date d'arrêté : un classeur Excel en 9 onglets et une présentation PowerPoint en 7 sections, aux chiffres strictement identiques à ceux du Passage, avec des clés de ticket cliquables vers Jira, complet sans LLM (Palier 1) et rejouable à l'identique. C'est l'argument central de la démo (gain de temps face au retraitement manuel) et le critère de la porte Palier 1 (M3) : la demande d'outillage doit rester recevable même si la banque refuse tout LLM.

## Stories

- Story 5.1 : Étapes déterministes complètes et Passage autoportant
- Story 5.2 : Consultation complète
- Story 5.3 : Classeur Excel en 9 onglets
- Story 5.4 : Présentation PowerPoint en 7 sections
- Story 5.5 : Commande unique et Rejeu idempotent
- Story 5.6 : Recette du Rapport sur données complètes
- Story 5.7 : Porte Palier 1 (M3)

## Requirements & Constraints

- **Commande unique** : enchaîne extraction, Instantanés, KPI, Météo, Prévision, puis (Palier 2) classification, répartition des Causes racines, Explications, narration, et enfin le rendu. Sans option, Date d'arrêté = dernier Jour ouvré écoulé ; une date non ouvrée est rejetée par une `UsineErreur` qui la nomme. Fichiers nommés `rapport-AAAA-MM-JJ.xlsx` / `.pptx`.
- **Échec** : code de sortie non nul, message nommant l'étape fautive, aucun fichier de Rapport publié.
- **Excel, 9 onglets dans cet ordre** : Synthèse (une ligne par Entité : Météo J, J-1, J-5, Règles déclenchantes, Prévision ou Risque d'entrée en rouge) ; Météo détaillée (valeur de chaque Indicateur, seuils, indicateurs non évaluables) ; KPI (par Entité et Programme) ; Tendances (8 semaines) ; Anomalies ouvertes (bloquantes et majeures : clé en lien, Entité, Gravité, Phase, Domaine, âge, Cause racine proposée en Palier 2) ; Tests (par Entité et Phase : OK, KO, non exécutés, taux) ; Certifications (par Entité et Vague, avec statut) ; Commentaires (Palier 2 : Explications, Brouillons, répartition des Causes racines, Citations) ; Traçabilité (Date d'arrêté, source, horodatage d'extraction, nombre de tickets, versions de Grille, données, prompt, modèle).
- **PowerPoint, 7 sections sur gabarit neutre et fictif** : Titre (Programme, Date d'arrêté, périmètre) ; Synthèse (Entités par couleur, changements depuis J-1 et J-5, trois messages clés) ; Carte météo (Entités × Météo, flèche de tendance, Règle déclenchante principale) ; une slide par Entité rouge ou orange (Règles, KPI clés, zone Brouillon de commentaire, Prévision) ; Tendances (stock de bloquantes et taux de KO sur 8 semaines) ; les 10 bloquantes les plus anciennes ; Annexe méthode (Grille appliquée, sources, traçabilité).
- **Trois messages clés** de la Synthèse : construits par gabarit à partir des valeurs lues, jamais par LLM.
- **Palier 1** : Rapport complet ; zones de commentaire et colonne Cause racine portent « commentaire non généré (Palier 1) ». **Palier 2** (via fixtures dès maintenant) : Explications, Brouillons marqués « brouillon IA, à valider », répartition des Causes racines, Citations en liens.
- **Liens** : chaque clé de ticket affichée (Excel, PowerPoint) est un lien hypertexte vers Jira.
- **Fiabilité** : un test automatique compare chaque valeur chiffrée de l'Excel et des slides aux données lues par `Consultation` : égalité stricte.
- **Rejeu idempotent** : deux Passages de même Date d'arrêté sur mêmes données sont identiques (tables, JSON/JSONL, valeurs de cellules, textes de slides) hors exclusions déclarées.
- **Performance** : < 5 min en Palier 1 à la volumétrie cible (3 000 à 5 000 Anomalies, 10 Entités), extraction incrémentale comprise, mesure consignée avec les caractéristiques du poste dans le README.
- **Langue et format** : tout en français ; nombres, %, dates formatés par `contrats.format` (milliers à espace insécable, virgule décimale).
- **Porte M3** : CI verte, réconciliation à 100 %, Rejeu idempotent, mesure < 5 min, journal de fin de jalon M3 écrit ; aucune story de l'Epic 6 ne démarre avant.

## Technical Decisions

- **Périmètre d'écriture de la lane** : `chaine/`, `consultation/`, `rendu/`, `gabarits/` et leurs tests miroirs (`tests/unit/<dir>/...`). `contrats/`, `ports/`, `composition.py`, `cli.py`, `config/chaine.yaml`, `tests/contrat/`, `tests/doublures/` appartiennent à `main` : tout besoin passe par une PR courte sur `main`, puis rebase. Contrôle des chemins en CI sur `lane/5-*`.
- **Couches** : `chaine` importe contrats, ports, domaine, consultation (pas de code d'étape LLM ni de rendu) ; `rendu` importe contrats, ports, consultation, plus openpyxl et python-pptx seulement ; `consultation` importe contrats et ports. Vérifié par import-linter.
- **Étapes injectées** : chaque étape implémente `ports.Etape.executer(ctx: ContextePassage) -> ResultatEtape` ; le registre `dict[Etape, ports.Etape]` est construit par `composition.py`. `chaine` fournit elle-même les étapes déterministes, simples enveloppes des fonctions de `domaine/` sans aucun recalcul.
- **Écrivain unique** : seule `chaine` (`EcrivainPassage`) écrit dans `.en-cours-<passage_id>/` ; `rendu` renvoie les octets du xlsx et du pptx, que `chaine` écrit. Chaque fichier est validé par son contrat (`valider(df, SCHEMA_<NOM>)` pour les tables) et porte `contrats_version`.
- **Fichiers du Passage** : `manifeste.json`, `tickets_etats.parquet`, `tickets_textes.parquet`, `instantanes.parquet`, `kpi.parquet`, `indicateurs.parquet`, `meteo.json`, `tendances.parquet`, `previsions.json`, `llm/{classification,explications,narrations}.json`, `repartition_causes.parquet`, `trace/{llm,previsions}.jsonl`, les deux rapports. Enveloppes JSON définies dans `contrats.passage`.
- **Passage immuable et autoportant** : construit dans `sorties/passages/.en-cours-<passage_id>/`, publié par un seul renommage vers `sorties/passages/<date_arrete>/<passage_id>/`, déplacé sous `sorties/echecs/` en cas d'échec. Les sorties déterministes couvrent chaque Jour ouvré ≤ Date d'arrêté ; les sorties LLM, seulement la Date d'arrêté. `passage_id` = `AAAAMMJJTHHMMSSZ-<6 hex>`. Verrou exclusif `donnees/.verrou-passage`, échec propre et nommé s'il est pris.
- **Manifeste** : Date d'arrêté, source, `horodatage_extraction`, nombre de tickets, nombre d'alignements, `version_grille`, `version_donnees`, durées par étape, drapeau `classification_initiale`, coût LLM, `contrats_version`. Progression écrite hors Passage dans `sorties/progression/<passage_id>.jsonl` (l'UI la lit en ouvrir-lire-fermer).
- **Étapes et Palier** : ordre figé par l'énumération `Etape` (`extraction, instantanes, kpi, meteo, prevision, classification, repartition_causes, explications, narration, rendu`). Le Palier est uniquement `ConfigChaine.palier` ∈ {1, 2}, lu par la composition ; en Palier 1 les quatre étapes LLM sont enregistrées `sautee`.
- **Traces** : chaque Prévision produit une `EntreeTrace` (quatre versions + `passage_id`) que `chaine` écrit dans `trace/previsions.jsonl`. Empreintes définies une seule fois dans `contrats.versions`.
- **Consultation, lecteur unique** : seul lecteur des fichiers d'un Passage (publié ou en cours), pour étapes, rendu, UI, IA et Agent ; lit sans dériver de valeur métier. Dérivations de lecture admises : âge des anomalies en Jours ouvrés et appariement J-1 / J-5 d'`evolution_meteo()`, via `contrats.calendrier`. `url_ticket(cle)` construit l'URL depuis `config/jira.yaml`, `None` en Mode repli. Filtre `palier` ∈ {1, 2} sur toute lecture portant une sortie Palier 2, `anomalies()` comprise. Refus par `UsineErreur` d'un Passage de version majeure différente. Dernier Passage = max de `(date_arrete, horodatage_fin)` via `dernier_passage()` (option `sans_classification_initiale=True`), sans pointeur mutable. La suite de contrat `tests/contrat/` de `Consultation` doit passer sur l'implémentation complète.
- **Aucun calcul hors domaine** : rendu et consultation affichent des valeurs lues ; le formatage n'est pas un calcul. Nombres exacts : comptes entiers, taux en `numerateur`/`denominateur`, indicateur `non_evaluable` explicite (avec motif), jamais lu comme 0.
- **Rejeu** : rendu déterministe (`docProps` fixés depuis la Date d'arrêté, ordre stable). Exclusions dans `contrats.passage.EXCLUSIONS_REJEU`, `Mapping[str, frozenset[str]]` du nom logique de fichier vers des chemins de champ (`etapes[].horodatage_debut`) ; un champ exclu dans un fichier reste comparé partout ailleurs ; les Parquet n'ont aucune exclusion. Les cellules et textes de slides qui affichent un champ exclu (onglet Traçabilité) sont à déclarer sous `rapport_xlsx` et `rapport_pptx`, format `<onglet ou slide>!<repère>`, par une PR courte sur `main` (ajout mineur).
- **Erreurs et journaux** : exceptions dérivées de `UsineErreur`, traduites par la CLI en message nommant l'étape et code non nul ; `logging` en français ; aucun texte de ticket non pseudonymisé au-delà de DEBUG.
- **Stack** : openpyxl 3.1.5, python-pptx 1.0.2, polars 1.44.2, pydantic 2.14 ; tests sans réseau.

## UX & Interaction Patterns

- Aucun document UX : contenus fixés ci-dessus, mise en page de l'Excel et du PowerPoint laissée à la lane.
- Gabarit `gabarits/rapport.pptx` neutre et fictif, sans charte réelle ni nom réel (dépôt public).
- Les rendus affichent dès maintenant les champs Palier 2 quand ils existent (fixtures de contrats), pour que l'Epic 6 n'ait jamais à toucher `rendu/`.

## Cross-Story Dependencies

- **Socle E0** : Chaîne, Passage atomique, Consultation et rendu minimal (1 onglet, 1 slide) existent déjà en tranche fine ; cet epic les complète.
- **Internes** : 5.1 (fichiers du Passage) et 5.2 (Consultation complète) précèdent 5.3 et 5.4 ; 5.5 s'appuie sur les rendus déterministes ; 5.6 puis 5.7 viennent en dernier.
- **Epics 3 et 4** : fournissent les fonctions réelles du domaine (Instantanés, KPI, Indicateurs, Météo, Tendances, Prévisions, Risques) enveloppées par les étapes ; avant, travailler sur contrats, doublures et fixtures.
- **Story 5.6** : prérequis 1.8 (Scénarios calés : A et B rouges, C orange), 2.6 (Source composite sur le projet `DEMO`), 4.5 (Prévisions attendues sur les Scénarios).
- **Story 5.7** : Epics 1 et 2 terminés ; elle bloque le démarrage de l'Epic 6.
- **Aval** : L7 (UI, Agent, Mode repli) lit tout via `Consultation` ; L6 remplit les fichiers `llm/` et `trace/llm.jsonl` que les rendus savent déjà afficher.
