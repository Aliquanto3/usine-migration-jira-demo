---
title: 'Story 7.1 : Carte météo et navigation'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '77b443aefb4bbf6db5cab500c79db074f3cb7d3a'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-7-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-0-8-ui-minimale.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** La page de l'Epic 0 n'affiche qu'une couleur par Entité et un bouton de lancement. Le Pilote ne voit ni la tendance, ni la Règle déclenchante principale, ni les tickets en cause. Aucun écran de la démo (détail, Agent, lancement, avant / après, outillage) n'est atteignable depuis la carte (Story 7.1, FR-43, FR-29, NFR-11).

**Approach:**
- La carte météo du dernier Passage montre, par Entité :
  - sa Météo ;
  - une flèche de tendance J-1 / J-5 ;
  - sa Règle déclenchante principale ;
  - les tickets en cause, en liens Jira via `url_ticket`.
- Une navigation latérale rend chaque écran atteignable en un clic.
- Un bouton par Entité ouvre directement son détail.
- Les écrans des stories suivantes sont des emplacements nommés.

## Boundaries & Constraints

**Always:**
- **Couches.** `usine.ui` n'importe ni `ports` ni `config` (contrat import-linter). Les lectures passent par les services de `ui/cli.py` (`racine_ui`, `mode_repli`, `consultation_dernier_passage`). Le `Protocol` local de `carte.py` est tenu aligné sur `Consultation` par un test (mêmes noms de méthodes et mêmes paramètres).
- **Source des données.** Tout vient de `Consultation` : `manifeste()`, `meteo()`, `evolution_meteo()`, `url_ticket()`. L'UI ne calcule aucun chiffre. Elle compare seulement des `Couleur` (ordre de gravité) et formate les valeurs avec `contrats.format`.
- **Flèche de tendance.** Une flèche par horizon :
  - `↗` : aggravation (couleur actuelle plus grave que celle de J-n) ;
  - `↘` : amélioration ;
  - `→` : stable ;
  - `—` : couleur à J-n inconnue (`None`), ou Entité absente de `evolution_meteo()`.
  
  Rendu : `J-1 ↗ · J-5 →`. Une légende sous la carte explique les flèches.
- **Règle déclenchante principale.**
  - C'est la première Règle de `MeteoEntite.regles`, dans l'ordre de la Grille rendu par `Consultation`.
  - Format : `IND-2 : 11 (seuil ≥ 10)`. Valeur et seuil passent par `formater_fraction`, `∞` si le dénominateur vaut 0. C'est le même format que `rendu.commun.formater_regle`, que `ui` ne peut pas importer.
  - Les autres Règles sont signalées par `(+N)`.
  - Une Entité verte affiche `—`.
- **Tickets en cause.** Ce sont ceux de la Règle principale : les 3 premiers, puis `+N` s'il y en a d'autres. Chaque clé affichée passe par un seul assistant, `lien_ticket(cle, url)` :
  - si `url_ticket(cle)` rend une URL, la clé devient un lien Markdown ;
  - sinon (Mode repli), la clé reste en texte simple.
  
  Les caractères Markdown de la clé sont échappés.
- **Rendu de la carte.** La carte est un tableau Markdown construit par une fonction pure. Les liens y sont cliquables, ce que `st.table` ne permet pas. Le `|` est échappé dans chaque cellule.
- **Navigation.**
  - Un `st.sidebar.radio` de clé `ecran` liste, dans l'ordre : `Carte météo`, `Détail d'une Entité`, `Lancement de la Chaîne`, `Avant / après`, `Agent`, `Ce qu'il faut pour le faire en vrai`. Chaque écran est à un clic de la carte, et la carte est l'écran par défaut.
  - Sous la carte, un bouton `Détail ENT-x` par Entité règle, dans son rappel, `ecran` = détail et `entite` = l'Entité, ce qui fait un seul clic.
- **Écrans.**
  - **Détail (emplacement de la 7.2)** : l'Entité choisie (sélecteur, préréglé par le bouton), sa Météo, et la mention « Détail complet : Story 7.2 ».
  - **Lancement** : le bouton et le suivi existants de la Story 0.8, inchangés.
  - **Avant / après, Agent, outillage** : un `st.info` qui nomme la story qui les livre (7.4, 7.9, 7.5).
- **Bandeau Mode repli.** Il reste le premier élément de la zone principale, quel que soit l'écran.
- **Constat 23 de la rétro E0.** Un test lance un vrai `usine rapport` (`Popen` réel, Date d'arrêté 09/10/2026) sur le mini-jeu depuis l'écran de lancement. Il sonde jusqu'à la fin (60 s au plus), puis vérifie que l'étape `publication` est réussie et que la carte affiche le Passage publié.

**Never:**
- Modifier `src/usine/contrats/`, `src/usine/ports/`, `pyproject.toml`, `uv.lock`, ou écrire hors de `src/usine/ui/` et `tests/unit/ui/`.
- Lire un Passage hors de `Consultation`, ou dériver un chiffre (ratio, écart au seuil) dans l'UI.
- Construire le contenu des écrans 7.2 à 7.6.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Carte | Passage d'essai (graine 42, 09/10/2026) | ENT-A : 🔴 Rouge, `J-1 ↗ · J-5 ↗`, `IND-2 : 11 (seuil ≥ …)`, 1 ticket en lien ; ENT-B : `J-1 → · J-5 →`, IND-1 suivi de `(+2)` | N/A |
| Verte | Météo verte, sans Règle | Règle `—`, tickets `—` | N/A |
| J-n inconnue | `couleur_j1 = None` | `J-1 —` | N/A |
| Amélioration | J-5 rouge, J orange | `J-5 ↘` | N/A |
| Plus de 3 tickets | Règle principale avec 5 tickets | 3 liens puis `+2` | N/A |
| Mode repli | `USINE_MODE_REPLI=1` | clés en texte simple, aucun `](http` dans la carte | N/A |
| Clé avec `]` ou `\|` | clé factice `A]B` | échappée, Markdown intact | N/A |
| Navigation | radio sur chacun des 6 écrans | l'écran correspondant s'affiche, sans exception, avec le bandeau en tête s'il est actif | N/A |
| Bouton Entité | clic sur `Détail ENT-B` | écran Détail, ENT-B sélectionnée, sa Météo affichée | N/A |
| Sans Passage | `sorties/passages/` vide | carte : message « Aucun Passage publié » ; détail : même message | N/A |
| Bout en bout | vrai `usine rapport` lancé depuis l'écran de lancement | `publication` réussie, succès affiché, carte du 09/10/2026 | échec du test au-delà de 60 s |

</intent-contract>

## Code Map

- `src/usine/ui/app.py` -- page actuelle (bandeau, `afficher_carte`, `afficher_lancement`, `principal`). Elle accueille la navigation et les écrans. Garder intactes `_lancer`, `_suivre` et les clés de `session_state` : les tests de la 0.8 les utilisent.
- `src/usine/ui/carte.py` -- `LectureMeteo`, `date_carte` et `lignes_carte`, à étendre (`evolution_meteo` et `url_ticket` dans le Protocol).
- `src/usine/ui/cli.py` -- services de la page. Ne pas changer, sauf besoin avéré.
- `src/usine/ports/consultation.py` -- signatures de référence pour le test d'alignement (lecture seule).
- `src/usine/contrats/meteo.py` -- `Couleur` (comparaisons par gravité), `RegleDeclenchante`, `EvolutionMeteo`, `LIBELLES_COULEURS`, `Operateur`.
- `src/usine/contrats/format.py` -- `formater_fraction`, `formater_date`.
- `src/usine/rendu/commun.py:59` -- `formater_regle`, le modèle de format à reproduire (non importable par `ui`).
- `src/usine/ui/lancement.py` -- `lancer_chaine(racine, date_arrete, popen, erreurs)`. Le test de bout en bout le remplace par `partial(..., date_arrete=DATE_ARRETE)`.
- `tests/unit/ui/conftest.py` -- `racine_publiee` (Passage publié, module).
- `tests/unit/chaine/environnement.py` -- `preparer_racine`, `DATE_ARRETE`.
- `tests/unit/ui/test_app.py` -- tests AppTest de la 0.8. Ils lisent `page.table` et `page.button[0]`, et doivent passer par l'écran de lancement.

## Tasks & Acceptance

**Execution:**
- `src/usine/ui/liens.py` -- `lien_ticket(cle, url) -> str` et `echapper_markdown(texte) -> str`. Ce sont les seuls points de rendu d'une clé de ticket (FR-29).
- `src/usine/ui/carte.py` -- Protocol `LectureCarte` (`manifeste`, `meteo`, `evolution_meteo`, `url_ticket`) ; `fleche(avant, maintenant)`, `tendance(evolution | None)`, `formater_regle(regle)`, `regle_principale(meteo)`, `tickets_principaux(meteo, url_ticket)` ; `lignes_carte` → colonnes `Entité`, `Météo`, `Tendance`, `Règle principale`, `Tickets en cause` ; `tableau_markdown(lignes)`.
- `src/usine/ui/navigation.py` -- `Ecran` (StrEnum, libellés et ordre ci-dessus), `ECRAN_PAR_DEFAUT`, `STORY_A_VENIR` (écran → numéro de story).
- `src/usine/ui/app.py` -- radio latéral ; `afficher_carte` (tableau Markdown, légende, boutons Détail) ; `afficher_detail` ; `afficher_a_venir` ; écran de lancement ; bandeau toujours en tête.
- `tests/unit/ui/test_carte.py`, `test_liens.py`, `test_navigation.py` -- matrice I/O en fonctions pures, et alignement `LectureCarte` / `Consultation` par `inspect.signature`.
- `tests/unit/ui/test_app.py` -- adapter à la navigation ; ajouter les cas Navigation, Bouton Entité et Mode repli sur la carte.
- `tests/unit/ui/test_bout_en_bout.py` -- vrai `usine rapport` depuis la page (constat 23).

**Acceptance Criteria:**
- Given le dépôt, when `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest -q`, then tout passe, et `usine.ui` n'importe ni `usine.ports` ni `usine.config`.
- Given la page sur le Passage d'essai, when on affiche la carte, then chaque clé de ticket visible est un lien `…/browse/<clé>` égal à `consultation.url_ticket(clé)`.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 29 findings — high 0, medium 0, low 22, false 6, maybe-false 1
- findings:
  - `[low]` `[reject]` (blind) Suivi de la Chaîne interrompu hors de l'écran Lancement — au retour sur l'écran, le fragment reprend, affiche la fin et ferme le fichier d'erreurs ; la carte relit le dernier Passage à chaque exécution. Le suivi transverse relève de la 7.3 (consigné).
  - `[low]` `[reject]` (blind) Nouvelle carte invisible depuis l'écran Lancement après succès — un clic ; « la carte affiche le nouveau Passage » est un critère de la 7.3 (consigné).
  - `[low]` `[patch]` (blind) `formater_regle` recopié de `rendu` sans test de parité — `test_formater_regle_identique_au_rendu` (4 variantes).
  - `[false]` `[reject]` (blind) `_SYMBOLES` incomplet pour `Operateur` — `Operateur` (contrat gelé v1) n'a que `>=` et `>`, tous deux couverts.
  - `[false]` `[reject]` (blind) `∞` pour 0/0 ou pour le seuil — `RegleDeclenchante` refuse 0/0 et impose `seuil_denominateur > 0`.
  - `[low]` `[patch]` (blind) Libellé du bouton Détail non échappé, clés en double, colonnes trop nombreuses — libellé passé par `echapper_markdown` ; doublons impossibles (une Météo par Entité, `domaine/meteo.py`) ; Programme à quelques Entités.
  - `[low]` `[reject]` (blind) Entité choisie oubliée après un détour par un autre écran — le bouton `Détail ENT-x` la rétablit en un clic ; la persistance relève de l'écran complet (7.2).
  - `[low]` `[reject]` (blind) Test de bout en bout sans marqueur `lent` — il dure environ 5 s, et la spec l'exige dans `pytest -q`.
  - `[low]` `[patch]` (blind) `—` à deux sens dans la carte — la légende couvre désormais « aucune règle ou aucun ticket ».
  - `[low]` `[reject]` (blind) `_DESTINATION` laisse passer le saut de ligne et ne contrôle pas le schéma — l'URL vient de `config/jira.yaml` validé ; improbable.
  - `[low]` `[reject]` (blind) Tests fondés sur des indices de position — cosmétique.
  - `[low]` `[reject]` (blind) Second `except UsineErreur` d'`afficher_carte` non testé — même message que la branche testée ; garde de robustesse.
  - `[low]` `[patch]` (verification-gap) Parité `ui` / `rendu` de `formater_regle` non vérifiée — même correctif que la ligne blind.
  - `[low]` `[patch]` (verification-gap) Échappement de la cellule Entité non testé — `test_entite_echappee` (`ENT_*A$`).
  - `[low]` `[reject]` (verification-gap, autre) `pop` de l'Entité absente sans effet observable sous Streamlit 1.65 — redondant mais inoffensif.
  - `[low]` `[reject]` (edge) Pas de sondage hors de l'écran Lancement — même raison que la première ligne blind.
  - `[false]` `[reject]` (edge) Deux Météo pour une même Entité — `domaine/meteo.py` produit une `MeteoEntite` par Entité.
  - `[low]` `[patch]` (edge) Libellé de bouton interprété en Markdown — même correctif que la ligne blind.
  - `[maybe-false]` `[reject]` (edge) Exception autre qu'`UsineErreur` dans `lignes_carte` — `Consultation` traduit ses erreurs de lecture en `UsineErreur` (revue 0.8) ; à confirmer par une lecture corrompue d'`evolution_meteo`. Au pire `low`.
  - `[low]` `[reject]` (edge) `:` et `&` non échappés — clés `DEMO-n` et Entités `ENT-x` ; improbable.
  - `[low]` `[reject]` (edge) Saut de ligne dans l'URL — même raison que la ligne blind.
  - `[false]` `[reject]` (edge) Tickets en double dans une Règle — `tickets_en_cause` vient des mesures du domaine, sans doublon.
  - `[low]` `[reject]` (edge) Boutons serrés avec des dizaines d'Entités — le Programme de démo en compte quelques-unes.
  - `[false]` `[reject]` (edge) `KeyError` si un `Ecran` n'a pas d'entrée dans `STORY_A_VENIR` — `test_stories_a_venir` impose la couverture.
  - `[low]` `[reject]` (intention) AC3 vérifié sur la chaîne Markdown, pas dans un navigateur — aucun navigateur disponible ; `AppTest` est la surface prévue.
  - `[low]` `[reject]` (intention) Quatre écrans sont des emplacements — leur contenu appartient aux stories 7.2, 7.4, 7.5 et 7.9.
  - `[low]` `[reject]` (intention) Règle principale prise dans l'ordre de la Grille — choix motivé dans les Design Notes (aucun ratio calculé dans l'UI).
  - `[false]` `[reject]` (intention) Nom `LectureMeteo` des artefacts devenu `LectureCarte` — seul le nom change ; l'alignement sur `Consultation` est testé.
  - `[low]` `[reject]` (intention) Étape `publication` inexistante dans `Etape` — le correctif serait une édition de la spec ; le test vérifie la dernière étape (`rendu`) réussie et le Passage publié.

## Design Notes

**Règle principale = première Règle.** Classer les Règles par dépassement du seuil demanderait de calculer des ratios dans l'UI, ce qui est interdit (aucun chiffre dérivé hors du domaine). L'ordre de la Grille est déterministe et c'est celui du rendu. Le détail complet (7.2) liste toutes les Règles.

**Radio plutôt que `st.navigation`.** Une seule page, testable par `AppTest`. La sélection est mémorisée par `session_state`, et un bouton d'Entité y écrit avant le rendu du radio.

**Fichiers hors lane.** Aucun : `tests/unit/ui/` est le miroir de `src/usine/ui`.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check .` -- expected: aucun écart.
- `uv run mypy` -- expected: aucune erreur.
- `uv run lint-imports` -- expected: tous les contrats KEPT.
- `uv run pytest -q` -- expected: tout vert, test de bout en bout compris.

## Auto Run Result

Status: done

**Résumé.** La page Streamlit propose une navigation latérale à six écrans. La carte météo est l'écran par défaut et montre, par Entité :
- la Météo ;
- la tendance J-1 / J-5, en flèches avec une légende ;
- la Règle déclenchante principale, au format du rendu ;
- les tickets en cause, en liens Jira via `url_ticket` (texte simple en Mode repli).

Un bouton `Détail ENT-x` ouvre le détail de l'Entité en un clic. Détail, avant / après, Agent et outillage sont des emplacements qui nomment leur story. L'écran Lancement reprend la 0.8. Le bandeau Mode repli reste en tête sur chaque écran.

**Fichiers.**
- `src/usine/ui/liens.py` : rendu unique d'une clé de ticket (lien ou texte), avec échappement Markdown.
- `src/usine/ui/navigation.py` : écrans, ordre, stories à venir, rappel du bouton Détail.
- `src/usine/ui/carte.py` : `LectureCarte`, flèches, Règle principale, tickets, tableau Markdown.
- `src/usine/ui/app.py` : navigation et écrans.
- `tests/unit/ui/test_carte.py`, `test_liens.py`, `test_navigation.py`, `test_app.py` : matrice I/O, alignement sur `Consultation`, parité avec `rendu`.
- `tests/unit/ui/test_bout_en_bout.py` : vrai `usine rapport` lancé depuis la page. Il ferme le constat 23 de la rétro E0 et dure environ 5 s.

**Revue.** 29 findings : 0 high, 0 medium, 22 low, 6 false, 1 maybe-false.
- **Correctifs.** 7 lignes `patch` (low) ont donné 4 correctifs : test de parité de `formater_regle`, libellé du bouton échappé, légende de `—`, test d'échappement de l'Entité.
- **Différés.** Aucun.
- **Rejets.** Les autres findings sont rejetés, chacun avec sa raison dans le journal de tri.

**Revue de suivi.** `false` : aucun correctif high ou medium.

**Vérification.** ruff, ruff format, mypy, lint-imports (13 contrats KEPT) et pytest : 1881 passés, 1 ignoré.

**Écarts et risques résiduels (à reprendre en 7.3).**
- Si l'utilisateur quitte l'écran Lancement pendant un run, le suivi s'interrompt. Il reprend au retour sur l'écran.
- Après un succès, la nouvelle carte demande un clic sur « Carte météo ». Le critère « la carte affiche le nouveau Passage » appartient à la 7.3.
- La spec mentionne une étape `publication`, qui n'existe pas dans `Etape`. Le test de bout en bout vérifie plutôt la dernière étape (`rendu`) réussie, le Passage publié et la carte.
