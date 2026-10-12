---
title: "Story 7.2 : Détail d'une Entité (Palier 1)"
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '73560cbf6e3da30e1e9666f1521730c5fde95bc9'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-7-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-7-1-carte-meteo-et-navigation.md'
warnings: [oversized]
deferred:
  - summary: >-
      Message AUCUN_KPI jamais rendu par l'app dans un test.
    evidence: |-
      Le Passage d'essai a des KPI pour chaque Entité ; seul le texte de la constante est testé.
    location: >-
      src/usine/ui/app.py
    severity: low
  - summary: >-
      Aucun Risque réel du Passage n'est rendu par AppTest.
    evidence: |-
      Graine 42 : ENT-A et ENT-B rouges, aucun Risque publié. Un Passage d'essai avec une Entité non rouge et un Risque trancherait.
    location: >-
      tests/unit/ui/test_app.py
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** L'écran « Détail d'une Entité » livré par la 7.1 est un emplacement : il n'affiche que la Météo. Le Pilote ne voit ni chaque Règle déclenchante, ni les KPI, ni la Prévision de sortie du rouge, ni le Risque d'entrée en rouge (Story 7.2, FR-43, FR-17, FR-20, FR-21).

**Approach:** Un module pur `ui/detail.py` construit, à partir de `Consultation`, les blocs de l'écran : Règles déclenchantes, KPI clés, Prévision, Risques et zone Explication. `app.afficher_detail` les affiche sous le sélecteur d'Entité existant. Prévisions et Risques sont publiés dans le Passage depuis la Story 5.3 (fusionnée dans `main`) : l'écran affiche les valeurs réelles. Si l'étape `prevision` n'a pas réussi, l'écran l'annonce par un état explicite « non calculée ».

## Boundaries & Constraints

**Always:**
- **Couches.** `usine.ui` n'importe ni `ports`, ni `domaine`, ni `config`. Les lectures passent par `ui/cli.consultation_dernier_passage`. Le `Protocol` local `LectureDetail` (`manifeste`, `meteo`, `kpi`, `previsions`, `risques`, `url_ticket`) est tenu aligné sur `Consultation` par un test `inspect.signature`, comme `LectureCarte`.
- **Aucun chiffre dérivé.** L'UI formate les fractions de `Consultation` avec `contrats.format` (`formater_fraction`, `formater_pourcentage`, `formater_date`). Elle ne calcule ni ratio, ni écart, ni date.
- **Règles déclenchantes.** Une ligne par Règle de `MeteoEntite.regles`, dans l'ordre de la Grille. Colonnes `Règle` (format `carte.formater_regle` : `IND-2 : 11 (seuil ≥ 10)`) et `Tickets en cause` : **tous** les tickets, chacun via `lien_ticket(cle, url_ticket(cle))` (texte simple en Mode repli), `—` sans ticket. Entité verte : « Aucune Règle déclenchante (Entité verte). »
- **KPI clés.** Ceux de l'Entité à la Date d'arrêté du Passage (`kpi(entite=…)`), pour les codes, dans cet ordre : `anomalies_ouvertes` (Anomalies ouvertes), `entrees_fenetre` (Entrées sur la fenêtre), `sorties_fenetre` (Sorties sur la fenêtre), `age_median_anomalies_ouvertes` (Âge médian des Anomalies ouvertes), `age_max_anomalies_ouvertes` (Âge maximal des Anomalies ouvertes), `taux_ko_cas_de_test` (Taux KO des Cas de test). Une ligne par dimension présente ; un KPI ventilé ajoute ` (dimension)` à son libellé. Valeur : `formater_fraction`, `formater_pourcentage` pour `taux_*`, `∞` si `n/0` avec `n > 0`, `—` si `0/0`. Les codes sont des chaînes déclarées dans `ui` (le domaine n'est pas importable) ; un test les vérifie présents dans le Passage d'essai.
- **Prévision (Entité rouge).**
  - `sortie_projetee` : date estimée, fourchette `optimiste – pessimiste` (quand elle existe), probabilité de sortie dans l'horizon (`formater_pourcentage`), horizon en jours ouvrés, méthode.
  - `pas_de_sortie_projetee` : « pas de sortie projetée », avec probabilité et horizon.
  - `regle_non_projetable` : « pas de sortie projetée : règle non projetable (IND-x, …) ».
  - Puis les facteurs explicatifs : `libellé : valeur` (`formater_fraction`).
  - Entité non rouge : « Sans objet : l'Entité n'est pas rouge. »
- **Risque d'entrée en rouge (Entité non rouge).** Pour chaque `RisqueEntreeRouge` de l'Entité : indicateur, valeur courante, seuil rouge, date de franchissement estimée et horizon ; colonne « Valeur projetée » (contrats 1.1.0, optionnelle) seulement si un Risque la porte, `—` pour les autres. Aucun Risque : « Aucun Risque d'entrée en rouge dans l'horizon. » Entité rouge : « Sans objet : l'Entité est déjà rouge. »
- **État « non calculée ».** Les Prévisions sont calculées pour ce Passage si et seulement si l'étape `prevision` du manifeste est `reussie` (même règle que `consultation.prevision.previsions_calculees`, réécrite dans `ui` qui n'importe pas `consultation`). Sinon, les deux blocs portent « Prévision non calculée pour ce Passage » et « Risque d'entrée en rouge non calculé pour ce Passage ». Si elles sont calculées mais qu'une Entité rouge n'a pas de Prévision : « Prévision non calculée pour cette Entité ».
- **Explication.** Passage `palier == 1` : la zone porte exactement « commentaire non généré (Palier 1) ». Palier 2 : « Explication sourcée : Story 7.7 ».
- **Navigation.** L'écran Détail n'est plus un emplacement : `Ecran.detail` sort de `STORY_A_VENIR`. Sélecteur, bouton `Détail ENT-x`, messages « Aucun Passage publié » et « Lecture du dernier Passage impossible » de la 7.1 sont conservés.
- **Tests.** Les valeurs attendues sont tirées du Passage (`consultation_dernier_passage`), jamais figées. Les cas avec Prévisions et Risques utilisent une doublure de `Consultation`, injectée dans `AppTest` en remplaçant `usine.ui.cli.consultation_dernier_passage`.

**Never:**
- Modifier `src/usine/contrats/`, `src/usine/ports/`, `pyproject.toml`, `uv.lock`, ou écrire hors de `src/usine/ui/` et `tests/unit/ui/`.
- Lire un Passage hors de `Consultation`, ou fabriquer une Prévision dans l'UI.
- Livrer l'Explication sourcée, le sélecteur de Palier ou la narration (Story 7.7).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Entité rouge, Passage d'essai | ENT-A, Palier 1, étape `prevision` réussie | chaque Règle de `meteo(entite)` avec tous ses tickets en liens ; KPI clés ; Prévision réelle du Passage et ses facteurs ; Risque sans objet ; « commentaire non généré (Palier 1) » | N/A |
| Étape `prevision` non réussie | manifeste : `prevision` sautée | « Prévision non calculée pour ce Passage », « Risque d'entrée en rouge non calculé pour ce Passage » | N/A |
| Valeur projetée | Risque avec `valeur_projetee_*` | colonne « Valeur projetée » | N/A |
| Sortie projetée | doublure : Prévision `sortie_projetee` de l'Entité | dates estimée, optimiste, pessimiste en `JJ/MM/AAAA`, probabilité en %, facteurs | N/A |
| Pas de sortie | Prévision `pas_de_sortie_projetee` | « pas de sortie projetée » et facteurs | N/A |
| Non projetable | Prévision `regle_non_projetable` (IND-2) | « règle non projetable (IND-2) » | N/A |
| Rouge sans Prévision | Prévisions calculées pour d'autres Entités seulement | « Prévision non calculée pour cette Entité » | N/A |
| Non rouge avec Risque | doublure : Risque IND-1 de ENT-B | indicateur, valeur, seuil, date de franchissement, horizon | N/A |
| Non rouge sans Risque | Prévisions calculées, aucun Risque de l'Entité | « Aucun Risque d'entrée en rouge dans l'horizon. » | N/A |
| Verte | Météo verte | « Aucune Règle déclenchante (Entité verte). » ; Prévision sans objet | N/A |
| KPI `0/0`, `n/0` | lignes KPI factices | `—`, `∞` | N/A |
| Mode repli | `USINE_MODE_REPLI=1` | tickets en texte simple, aucun `](http` | N/A |
| Palier 2 | manifeste `palier = 2` | « Explication sourcée : Story 7.7 » | N/A |

</intent-contract>

## Code Map

- `src/usine/ui/app.py:96` -- `afficher_detail` : sélecteur existant, puis les blocs du détail (sous-titres Règles déclenchantes, KPI clés, Prévision de sortie du rouge, Risque d'entrée en rouge, Explication). Tableaux en `st.markdown(carte.tableau_markdown(...))`.
- `src/usine/ui/carte.py` -- réutiliser `formater_regle`, `libelle_meteo`, `tableau_markdown`, `INCONNUE` ; modèle du `Protocol` et de son test d'alignement.
- `src/usine/ui/liens.py` -- `lien_ticket`, `echapper_markdown` (seul rendu d'une clé).
- `src/usine/ui/navigation.py:24` -- `STORY_A_VENIR` : retirer `Ecran.detail`.
- `src/usine/ports/consultation.py` -- signatures de référence : `kpi`, `previsions`, `risques` (lecture seule).
- `src/usine/consultation/passage.py:453` -- `previsions`/`risques` rendent `()` sans `previsions.json` ; l'étape `prevision` est encore un bouchon (`composition.py:349`).
- `src/usine/contrats/prevision.py` -- `Prevision`, `StatutPrevision`, `FacteurExplicatif`, `RisqueEntreeRouge`, `MethodePrevision`.
- `src/usine/contrats/calcul.py:55` -- colonnes KPI : `date`, `perimetre`, `code_kpi`, `dimension`, `numerateur`, `denominateur`.
- `src/usine/domaine/kpi.py:37` -- codes KPI (référence, non importable par `ui`).
- `tests/unit/ui/test_app.py` -- `test_navigation` et `test_bouton_entite` attendent l'emplacement 7.2 : à adapter.
- `tests/unit/ui/test_navigation.py:28` -- contenu de `STORY_A_VENIR` à adapter.
- `tests/unit/ui/conftest.py` -- `racine_publiee` (Passage d'essai, graine 42, 09/10/2026).

## Tasks & Acceptance

**Execution:**
- `src/usine/ui/detail.py` -- `LectureDetail` ; `KPI_CLES` ; `lignes_regles`, `lignes_kpi`, `previsions_calculees`, `texte_prevision`, `texte_risques`, `texte_explication` ; constantes des messages.
- `src/usine/ui/navigation.py` -- retirer `Ecran.detail` de `STORY_A_VENIR`.
- `src/usine/ui/app.py` -- `afficher_detail` complet ; lectures en `try/except UsineErreur`.
- `tests/unit/ui/test_detail.py` -- matrice I/O en fonctions pures (doublures de `Prevision` / `RisqueEntreeRouge`), alignement `LectureDetail` / `Consultation`, codes KPI présents dans le Passage d'essai.
- `tests/unit/ui/test_app.py`, `test_navigation.py` -- adapter ; ajouter détail de l'Entité rouge (valeurs tirées du Passage), Mode repli, doublure avec Prévision et Risque.

**Acceptance Criteria:**
- Given le dépôt, when `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest -q`, then tout passe.
- Given la page sur le Passage d'essai, when le Pilote clique `Détail` d'une Entité rouge, then chaque Règle et chaque ticket en cause de `consultation.meteo(entite=…)` apparaissent, les liens valant `url_ticket(clé)`.
- Given une doublure dont l'Entité rouge a une Prévision projetée et l'Entité non rouge un Risque, when on ouvre leur détail dans `AppTest`, then fourchette, probabilité, facteurs, indicateur et projection sont affichés.

## Spec Change Log

### 2026-10-12 — Reprise après coupure, fusion de `main`
- Déclencheur : `main` a reçu les contrats v1.1 (valeur projetée optionnelle du Risque) et la Story 5.3 (Prévisions et Risques publiés). Consigne de reprise : afficher Prévision et Risques réels et la valeur projetée si présente.
- Amendé : critère « calculée » (manifeste au lieu de la présence de données), colonne « Valeur projetée », matrice I/O.
- État écarté : heuristique « aucune Prévision ni Risque = non calculé », fausse dès qu'un Passage réel n'a ni rouge ni Risque.
- KEEP : blocs purs de `ui/detail.py`, `LectureDetail` aligné par `inspect.signature`, tests `AppTest` à valeurs tirées du Passage, doublure injectée via `cli.consultation_dernier_passage`.

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 22 findings — high 0, medium 2, low 9, false 9, maybe-false 2
- findings:
  - `[medium]` `[patch]` (verification-gap) Chemin d'erreur `UsineErreur` des lectures par Entité de `afficher_detail` jamais testé — ajouté `test_detail_lecture_entite_illisible` (doublure dont `previsions` lève, message d'erreur affiché, pas d'exception).
  - `[medium]` `[patch]` (verification-gap) `AUCUNE_REGLE` jamais rendu par l'app — ajouté `test_detail_entite_verte` (doublure ENT-B verte : Aucune Règle, Prévision sans objet).
  - `[low]` `[defer]` (verification-gap) `AUCUN_KPI` jamais rendu par l'app — le Passage d'essai a toujours des KPI ; fixture dédiée hors de proportion.
  - `[false]` `[reject]` (blind) Ordre `calculees` avant couleur dans `texte_prevision`/`texte_risques` — conforme au contrat : Passage non calculé, les deux blocs portent « non calculé ».
  - `[false]` `[reject]` (blind) Parenthèses vides pour `regle_non_projetable` sans code — le validateur de `Prevision` exige des règles non projetables pour ce statut.
  - `[low]` `[reject]` (blind) Métadonnées différentes selon le statut de Prévision — le contrat fixe le contenu par statut ; branches non testées (bornes simples de fourchette) rares, pas de défaut observé.
  - `[maybe-false]` `[reject]` (blind) Indicateurs de taux formatés en fraction dans les Risques — même formatage que `formater_regle` de la Carte ; au pire `low` (cosmétique) : à trancher avec la Grille si un IND projeté est un taux.
  - `[low]` `[reject]` (blind) Risques ou Prévisions multiples non triés — ordre du Passage (domaine), une ligne par indicateur ; correctif ajoute une règle non demandée.
  - `[low]` `[reject]` (blind) Message d'erreur non échappé dans `st.error` — motif existant de la 7.1 (`afficher_carte`), texte d'exception interne.
  - `[low]` `[patch]` (blind) `test_detail_entite_rouge` muet pour `pas_de_sortie_projetee` — branche ajoutée (`PAS_DE_SORTIE` attendu).
  - `[low]` `[patch]` (blind) Duplication dans `test_detail_prevision_non_calculee` — `_avec_doublure` prend la classe de doublure.
  - `[low]` `[reject]` (blind) Assertions dépendantes de l'ordre des colonnes — l'ordre des colonnes est le contrat d'affichage.
  - `[false]` `[reject]` (blind) `texte_explication` sans garde — `palier` est `Literal[1, 2]` (mypy et Pydantic).
  - `[false]` `[reject]` (blind) `∞` pour `n/0` masquerait une donnée fausse — règle explicite du contrat.
  - `[false]` `[reject]` (blind) Libellés KPI non vérifiés contre `domaine.kpi` — les libellés sont ceux de l'UI ; les codes sont vérifiés dans le Passage.
  - `[low]` `[patch]` (edge) `reelle` non vérifiée avant la doublure non calculée — passe désormais par `_avec_doublure` (assert).
  - `[false]` `[reject]` (edge) KPI `n/0` avec `n < 0` — numérateurs KPI de comptage, d'âge ou de taux jamais négatifs.
  - `[maybe-false]` `[defer]` (intent) Aucun Risque réel du Passage rendu par `AppTest` — le Passage d'essai (graine 42) n'a que des Entités rouges, donc aucun Risque ; si vrai, `medium` (non vérifié) : un Passage d'essai avec une Entité non rouge le trancherait.
  - `[false]` `[reject]` (intent) Valeur projetée testée seulement en doublure — aucun Risque dans le Passage d'essai ; la colonne est couverte en fonction pure et en `AppTest`.
  - `[false]` `[reject]` (intent) Littéraux dans les tests à doublure — valeurs de la doublure elle-même, autorisé par le contrat (« doublure de `Consultation` »).
  - `[low]` `[reject]` (intent) Vérification faible de la Prévision réelle — renforcée par le patch `pas_de_sortie_projetee` ; facteurs vérifiés.
  - `[false]` `[reject]` (intent) Injection par `monkeypatch` de `cli.consultation_dernier_passage` — `AppTest` réexécute le script ; les tests à doublure passent et échouent sans elle.

## Design Notes

**Critère « calculée ».** Depuis la Story 5.3, toute étape `prevision` réussie écrit `previsions.json` et son échec arrête le Passage : le manifeste suffit. Reste indiscernable un Passage publié avec l'ancien bouchon (étape réussie sans fichier), lu comme « aucun Risque » / « non calculée pour cette Entité » ; accepté (même limite que `consultation.prevision`).

**Fichiers hors lane.** Aucun : `tests/unit/ui/` est le miroir de `src/usine/ui`.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check .` -- expected: aucun écart.
- `uv run mypy` -- expected: aucune erreur.
- `uv run lint-imports` -- expected: tous les contrats KEPT.
- `uv run pytest -q tests/unit/ui` puis `uv run pytest -q` -- expected: tout vert.

## Auto Run Result

Status: done

- **Résumé.** L'écran Détail d'une Entité (Palier 1) affiche Météo, Règles déclenchantes (tous les tickets en liens Jira, texte en Mode repli), KPI clés, Prévision de sortie du rouge et Risque d'entrée en rouge réels du Passage (Story 5.3), valeur projetée du Risque si présente (contrats 1.1), et la zone Explication. État « non calculée » lu dans le manifeste (étape `prevision`).
- **Fichiers.**
  - `src/usine/ui/detail.py` — blocs purs du détail, `LectureDetail`, `previsions_calculees(manifeste)`.
  - `src/usine/ui/app.py` — `afficher_detail` complet, lectures sous `try/except UsineErreur`.
  - `src/usine/ui/navigation.py` — `Ecran.detail` sort de `STORY_A_VENIR`.
  - `tests/unit/ui/test_detail.py`, `test_app.py`, `test_navigation.py` — matrice I/O, `AppTest` à valeurs tirées du Passage, doublures (Prévision, Risque, non calculée, verte, illisible).
- **Revue (une passe, mode économique).** 22 constats : 5 patchs (2 medium, 3 low, tous en tests), 2 différés, 15 rejetés (motifs dans le Triage Log).
- **Revue de suivi recommandée :** non (aucun `high` patché, patchs `medium` limités aux tests).
- **Vérification.** `ruff check`, `ruff format --check`, `mypy`, `lint-imports` (13 contrats KEPT), `pytest -q` : tout vert après fusion de `main`.
- **Risques résiduels.** Le Passage d'essai n'a aucune Entité non rouge : le rendu d'un Risque réel n'est couvert que par doublure.
