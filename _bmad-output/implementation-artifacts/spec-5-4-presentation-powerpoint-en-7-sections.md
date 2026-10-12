---
title: 'Story 5.4 : Présentation PowerPoint en 7 sections'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '60781c2f980ec30d41106d3619ed9b657d7acce7'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-5-context.md'
warnings: ['multiple-goals', 'oversized']
deferred:
  - summary: >-
      Déclarer les cellules de l'Annexe méthode qui affichent l'horodatage d'extraction et la version des données sous EXCLUSIONS_REJEU["rapport_pptx"] avant le Rejeu de la Story 5.5.
    evidence: |-
      Le tableau de traçabilité de l'Annexe affiche deux champs exclus du Rejeu au manifeste ; en source composite, deux Passages de mêmes données donnent des présentations différentes. La déclaration modifie contrats/passage.py, gelé pendant le run (même cas que Traçabilité!B5/B8 de l'Excel).
    location: >-
      src/usine/rendu/powerpoint.py (_annexe), src/usine/contrats/passage.py (EXCLUSIONS_REJEU)
    severity: medium
  - summary: >-
      decalage_comparaison (H-19) ne dimensionne que l'historique d'EtapeMeteo ; IND-8 (domaine/meteo.py, DECALAGE_IND8), evolution_meteo (consultation, 5 en dur) et les libellés « J-5 » du PowerPoint restent à 5.
    evidence: |-
      Brancher le décalage dans le domaine relève de la lane L3 et dans la Consultation d'un changement de signature ; l'intention autorise la constante si consignée. Un chaine.yaml avec decalage_comparaison ≠ 5 ne change aucune sortie (commentaire de config/chaine.yaml mis à jour).
    location: >-
      src/usine/domaine/meteo.py:66, src/usine/consultation/passage.py (evolution_meteo), src/usine/rendu/powerpoint.py (libellés J-5)
    severity: low
---

<intent-contract>

## Intent

**Problem:** La présentation du Rapport n'a qu'une slide (Carte météo, Story 0.6) : le Pilote ne peut pas présenter en comité sans copier-coller. En amont, les paramètres de Prévision (H-7, H-8) et le décalage de comparaison (H-19), désormais portés par `ConfigChaine` (contrats v1.1), ne sont pas lus : la Chaîne utilise des constantes.

**Approach:** Tâche préalable : la composition lit `ConfigChaine.prevision` (→ `ParametresBaseline`, `ParametresRisque` injectés dans `prevision_du_passage`) et `ConfigChaine.decalage_comparaison` (→ taille du tampon d'`EtapeMeteo`). Story : `rendu/powerpoint.py` produit les 7 sections de H-10 sur `gabarits/rapport.pptx`, en lisant tout via `Consultation` et le `ContexteRendu`, nombres formatés par `contrats.format`, clés liées par `url_ticket`.

## Boundaries & Constraints

**Always:** le rendu ne calcule aucune valeur métier : il lit, sélectionne, ordonne et formate. Les trois messages clés sont des gabarits de phrase remplis par des valeurs lues, jamais un LLM. Rendu déterministe (propriétés fixes, `archive_deterministe`, ordre stable). Palier 1 : zone de commentaire des slides d'Entité = « commentaire non généré (Palier 1) » ; Palier 2 : Brouillon préfixé « brouillon IA, à valider ». Toute clé de ticket affichée est un lien `url_ticket` quand il existe. Valeur projetée d'un Risque affichée seulement si présente. Tout en français. Défauts de `ConfigChaine` identiques aux constantes : un Passage sans `prevision` ni `decalage_comparaison` dans `chaine.yaml` est inchangé.

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` (gelés). Renseigner la valeur projetée dans le domaine ou la Chaîne (L4). Modifier `domaine/meteo.py` pour brancher `DECALAGE_IND8` (L3) : il reste en constante, consigné. Écrire un fichier du Rapport ailleurs que par l'`EcrivainPassage`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Passage réel | graine 42, D = 2026-10-09, ENT-A et ENT-B rouges | 6 slides fixes + 1 par Entité rouge/orange, dans l'ordre H-10 | Aucune |
| Aucune Entité rouge ni orange | Passage tout vert/jaune | 6 slides, aucune slide d'Entité | Aucune |
| Passage vide | aucune Météo | 6 slides, tableaux à en-têtes seuls, messages « aucune » | Aucune |
| Palier 2 (fixture) | `llm/explications.json` écrit | zone Brouillon « brouillon IA, à valider : … » ; sans Explication pour l'Entité : « aucun Brouillon de commentaire » | Aucune |
| Risque avec valeur projetée | `RisqueEntreeRouge` v1.1 | phrase du Risque suivie de « valeur projetée X » | Aucune |
| Mode repli | `url_jira=None` | clés sans lien | Aucune |
| `chaine.yaml` paramétré | `prevision.baseline.horizon: 7`, `decalage_comparaison: 7` | Prévisions à horizon 7 ; tampon `max(7, DECALAGE_IND8, fenêtre) + 1` | Aucune |

</intent-contract>

## Code Map

- `src/usine/rendu/powerpoint.py` -- slide unique actuelle ; `_gabarit`, `_rvb`, propriétés fixes à conserver.
- `src/usine/rendu/commun.py` -- `ContexteRendu`, `formater_regle`, `formater_risque`, `formater_kpi`, `formater_seuils`, `texte_prevision`, `tickets_en_cause`, `libelle*`, `MENTION_*`, `TEINTES_COULEURS`/`TEXTES_COULEURS`.
- `src/usine/rendu/excel.py:123-150,445-478` -- `LIBELLES_TRACABILITE`, `_versions_llm`, `_tracabilite` : valeurs à partager avec l'Annexe.
- `src/usine/rendu/etape.py` -- `EtapeRendu.contexte` (ajout du nom du Programme : `ctx.configuration.programme`, `None` possible).
- `src/usine/ports/consultation.py` -- `meteo`, `evolution_meteo`, `kpi(D, entite)`, `tendances()`, `anomalies(D, gravite, palier)` (triées par clé : le rendu trie par âge), `explications(entite, palier)`, `url_ticket`.
- `src/usine/domaine/kpi.py:57-95` -- codes et dimensions : `anomalies_ouvertes_gravite`/`bloquante`, `taux_ko_cas_de_test` ventilé par Phase seulement (pas de valeur globale).
- `src/usine/contrats/config.py:51-108` -- `ConfigBaseline`, `ConfigRisque` (mêmes champs que `ParametresBaseline`/`ParametresRisque`), `decalage_comparaison`.
- `src/usine/chaine/etapes.py:81-105,170-213` -- tampon `max(DECALAGE_IND8, TAILLE_FENETRE_GLISSANTE) + 1` ; `prevision_du_passage` crée les paramètres par défaut.
- `src/usine/composition.py:325,363-367` -- lecture de `chaine.yaml`, registre ; docstring l. 29-35.
- `gabarits/rapport.pptx` -- dispositions « Title Slide », « Title Only » ; 16:9 (12 192 000 × 6 858 000 EMU).
- `tests/unit/rendu/conftest.py` -- `passage`, `passage_repli`, `passage_jaune_rouge`, `completer_palier_2`, `CONTEXTE_FICTIF`.

## Tasks & Acceptance

**Execution:**
- `src/usine/chaine/etapes.py` -- `prevision_du_passage(..., baseline=ParametresBaseline(), risque=ParametresRisque())` ; `EtapeMeteo(..., decalage=DECALAGE_IND8)`, tampon `max(decalage, DECALAGE_IND8, TAILLE_FENETRE_GLISSANTE) + 1` ; docstrings.
- `src/usine/composition.py` (hors lane) -- construit `ParametresBaseline(**chaine.prevision.baseline.model_dump())`, idem Risque, passe `chaine.decalage_comparaison` ; docstring.
- `src/usine/rendu/commun.py` -- `ContexteRendu.programme: str = ""` ; `formater_risque` ajoute « , valeur projetée X » si présente ; `lignes_tracabilite(consultation, jour, contexte)` et constantes associées déplacées depuis `excel.py`.
- `src/usine/rendu/excel.py` -- utilise `lignes_tracabilite` (contenu inchangé).
- `src/usine/rendu/etape.py` -- `programme` dans le contexte ; `rendre_powerpoint(consultation, gabarit, date_arrete, contexte)`.
- `src/usine/rendu/powerpoint.py` -- 7 sections (Design Notes).
- `tests/unit/rendu/test_powerpoint.py`, `test_commun.py`, `test_excel.py` -- ordre et titres des slides ; SM-1 slide par slide ; Palier 1 / Palier 2 ; liens et Mode repli ; Passage vide ; déterminisme ; valeur projetée.
- `tests/unit/chaine/test_etapes.py`, `tests/unit/test_composition.py` (hors lane) -- paramètres lus de `chaine.yaml` ; tampon.

**Acceptance Criteria:**
- Given un Passage publié par `lancer_rapport`, when on ouvre `rapport-<D>.pptx`, then ses slides sont, dans l'ordre : Titre, Synthèse, Carte météo, une slide par Entité rouge ou orange (ordre de `meteo(D)`), Tendances, Bloquantes les plus anciennes, Annexe méthode.
- Given cette présentation et `ConsultationPassage`, when le test compare chaque nombre des slides au formatage de la valeur lue, then l'égalité est stricte.
- Given un Passage Palier 1, when on lit la zone de commentaire d'une slide d'Entité, then elle porte « commentaire non généré (Palier 1) » ; avec la fixture Palier 2, le Brouillon et « brouillon IA, à valider ».
- Given les trois messages clés, when ils sont produits, then ils égalent les gabarits remplis par les valeurs de `Consultation`.
- Given `chaine.yaml` avec `prevision` et `decalage_comparaison`, when la composition construit le registre, then la Prévision reçoit ces paramètres et `EtapeMeteo` ce décalage.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 33 findings — high 0, medium 4, low 19, false 10, maybe-false 0
- findings:
  - `[medium]` `[patch]` (intent) Risques et Entité orange jamais rendus sur une slide — `test_slide_entite_orange_et_valeur_projetee` : orange, rouge, jaune ; Risque avec valeur projetée affiché sur la slide orange.
  - `[low]` `[reject]` (intent) attendus SM-1 construits avec les mêmes formateurs — formateurs figés par des littéraux dans `test_commun.py`.
  - `[low]` `[defer]` (intent) `decalage_comparaison` sans effet observable — autorisé par l'intention, consigné (`deferred`).
  - `[low]` `[reject]` (intent) pas de test de bout en bout des paramètres H-7/H-8 — injection testée de la composition au domaine en deux maillons.
  - `[false]` `[reject]` (intent) repli « aucun Brouillon de commentaire » hors story — prévu par la matrice I/O de la spec.
  - `[false]` `[reject]` (intent) disposition « Title Slide » non vérifiée — tous les rendus complets l'utilisent.
  - `[false]` `[reject]` (intent) refactor Traçabilité de l'Excel non testé — `test_excel.py` inchangé et vert, Traçabilité = manifeste.
  - `[low]` `[defer]` (blind) H-19 à moitié branché — groupé avec le constat intent, consigné.
  - `[low]` `[defer]` (blind) libellés « J-5 » en dur — même cause (décalage constant en aval), consigné.
  - `[low]` `[reject]` (blind) `changements(rang)` traite tout rang ≠ 1 comme J-5 — fonction appelée avec 1 et 5 seulement.
  - `[medium]` `[defer]` (blind) Annexe : champs exclus du Rejeu non déclarés pour `rapport_pptx` — contrats gelés pendant le run, consigné (`deferred`), comme l'Excel.
  - `[low]` `[reject]` (blind) Annexe proche du bas de slide — tient avec la Grille livrée (8 Indicateurs) ; pagination hors proportion.
  - `[low]` `[reject]` (blind) débordement Tendances / Règles d'Entité — 10 Entités tiennent (≈ 5,3 M EMU sur 6,9 M) ; contrôle visuel à la recette 5.6.
  - `[low]` `[patch]` (blind) assertion vide `<= {3}` — `assert contenu.risques` et `== {3}`.
  - `[low]` `[reject]` (blind) tests de `taille_historique` sans `executer` — la propriété est le `maxlen` direct du tampon.
  - `[false]` `[reject]` (blind) parité `ConfigBaseline`/`ParametresBaseline` non testée, docstring « construira » — le test des défauts construit tous les champs par `model_dump()` ; la docstring est dans `contrats/`, gelé.
  - `[low]` `[patch]` (blind) docstring B5/B8 sur la mauvaise constante — commentaire qui lie B5/B8 à l'ordre de `LIBELLES_TRACABILITE`.
  - `[false]` `[reject]` (blind) oracle `meteo.regles[0]` sans garde — `MeteoEntite` impose des règles dès que la Météo n'est pas verte.
  - `[false]` `[reject]` (blind) valeur projetée partielle ignorée — le validateur du contrat refuse une paire incomplète.
  - `[low]` `[reject]` (blind) `brouillon()` ne garde que la première Explication — une Explication par Entité à la Date d'arrêté.
  - `[low]` `[reject]` (blind) `KPI_CLES` en valeurs magiques — cosmétique.
  - `[low]` `[reject]` (blind) `test_rendu_deterministe` lit toujours le Passage Palier 2 — le contexte Palier 1 couvre la branche Palier 1 sur les mêmes fichiers ; cosmétique.
  - `[medium]` `[patch]` (verification) slide d'Entité orange jamais testée — groupé avec le premier constat, même test.
  - `[medium]` `[patch]` (verification) limite à 10 bloquantes jamais exercée — `test_bloquantes_limite_a_10` : 12 anomalies, égalité d'âge, « 10 sur 12 ».
  - `[low]` `[defer]` (verification) `decalage_comparaison` sans effet visible — groupé, consigné.
  - `[low]` `[reject]` (edge) `placeholders[1]` absent → `KeyError` — gabarit livré fixe et testé.
  - `[low]` `[reject]` (edge) tables sans pagination — même motif que le constat blind.
  - `[low]` `[reject]` (edge) Annexe sans borne — même motif.
  - `[false]` `[reject]` (edge) taux de KO à dimension vide — `taux_ko_cas_de_test` n'est ventilé que par Phase (`DIMENSIONS_KPI`).
  - `[false]` `[reject]` (edge) lien perdu si cellule vide — la clé (non vide par contrat) est écrite avant `_lier`.
  - `[false]` `[reject]` (edge) oracle `regles[0]` — même réfutation que le constat blind.
  - `[low]` `[defer]` (edge) H-19 sans effet — groupé, consigné.
  - `[false]` `[reject]` (edge) `test_excel.py` non modifié — l'Excel est inchangé, ses tests passent.

## Design Notes

**Sections.** 1 Titre (« Title Slide ») : « Rapport quotidien du JJ/MM/AAAA » ; sous-titre : Programme, Date d'arrêté, périmètre (« N Entités : A, B… »), Palier. 2 Synthèse : tableau Couleur × Entités (du plus grave au moins grave, nombre et liste) ; changements depuis J-1 et depuis J-5 (« ENT-A : Orange → Rouge », sinon « aucun changement ») ; trois messages clés : M1 « N Entités en rouge et M en orange sur T », M2 « K Entités ont changé de Météo depuis J-1 » (ou « Aucune Entité … »), M3 « Anomalies bloquantes ouvertes sur le Programme : X ; Entrées et Sorties de la Fenêtre glissante : a et b » (KPI Programme). 3 Carte météo : Entité, Météo (teinte), Tendance vs J-5 (↗ aggravation, ↘ amélioration, → stable, – non couverte, ordre de `Couleur`), Règle déclenchante principale (première règle, `formater_regle`, « — » si vert). 4 Entité : titre « ENT-A — Rouge » ; Règles (`formater_regle`) ; KPI clés (ouvertes, bloquantes, majeures, entrées/sorties Fenêtre, âge médian/max, taux de KO par Phase) ; zone « Brouillon de commentaire » ; Prévision (`texte_prevision`). 5 Tendances : colonnes = semaines de `tendances()` ; lignes : bloquantes ouvertes Programme puis chaque Entité, taux de KO Programme par Phase. 6 Les 10 bloquantes les plus anciennes : `anomalies(D, bloquante, palier)` triées par âge décroissant puis ordre lu, 10 premières (clé liée, Entité, Phase, Domaine, Statut, Âge) ; « sur N bloquantes ouvertes ». 7 Annexe méthode : Grille (code, libellé, seuils, version) et `lignes_tracabilite`.

**Aucun calcul.** Compter les Entités affichées et trier pour sélectionner sont de la mise en forme de valeurs lues, pas une valeur métier. La flèche compare deux couleurs lues.

**Rejeu.** L'Annexe affiche `horodatage_extraction` et `version_donnees` : déclaration sous `EXCLUSIONS_REJEU["rapport_pptx"]` (contrats) à faire avant la 5.5, comme pour l'Excel.

**Fichiers hors lane.** `src/usine/composition.py`, `tests/unit/test_composition.py` : seule la composition lit `chaine.yaml` et construit le registre (AD-22). `config/chaine.yaml` : commentaire d'en-tête seul (les clés sont désormais lues ; `DECALAGE_IND8` reste constant).

## Verification

**Commands:**
- `uv run pytest -q tests/unit/rendu tests/unit/chaine tests/unit/test_composition.py` -- expected: tout passe
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout passe

## Auto Run Result

Status: done

**Résumé.** La composition lit `ConfigChaine.prevision` (→ `ParametresBaseline`, `ParametresRisque` injectés dans `prevision_du_passage`) et `ConfigChaine.decalage_comparaison` (→ `EtapeMeteo.taille_historique = max(décalage, DECALAGE_IND8, Fenêtre) + 1`). `DECALAGE_IND8` reste une constante du domaine (L3), consigné. La présentation compte les 7 sections de H-10 : Titre, Synthèse (Entités par couleur, changements J-1 et J-5, trois messages clés par gabarit), Carte météo (tendance vs J-5, Règle principale), une slide par Entité rouge ou orange (Règles et tickets liés, KPI clés, zone Brouillon, Prévision ou Risques avec valeur projetée si présente), Tendances sur 8 semaines, 10 bloquantes les plus anciennes, Annexe méthode (Grille et traçabilité partagée avec l'Excel).

**Fichiers modifiés.**
- `src/usine/chaine/etapes.py` : paramètres injectés, tampon dimensionné par le décalage.
- `src/usine/composition.py` (hors lane) : lecture de `chaine.yaml`, docstring.
- `config/chaine.yaml` (hors lane) : commentaire d'en-tête.
- `src/usine/rendu/commun.py` : `ContexteRendu.programme`, valeur projetée dans `formater_risque`, `lignes_tracabilite` partagée.
- `src/usine/rendu/excel.py` : utilise `lignes_tracabilite` (contenu inchangé).
- `src/usine/rendu/etape.py` : nom du Programme, contexte passé au PowerPoint.
- `src/usine/rendu/powerpoint.py` : les 7 sections.
- Tests : `tests/unit/rendu/test_powerpoint.py` (20 tests), `test_commun.py`, `tests/unit/chaine/test_etapes.py`, `tests/unit/test_composition.py` (hors lane).

**Revue.** 33 constats : 0 high, 4 medium, 19 low, 10 false.
- Correctifs : slide orange avec Risque et valeur projetée (medium), limite à 10 bloquantes (medium), assertion vide (low), commentaire B5/B8 (low).
- Différés : exclusions Rejeu de l'Annexe (`rapport_pptx`, contrats) ; décalage H-19 sans effet en aval (domaine, Consultation, libellés J-5).
- Rejetés : voir le Review Triage Log (mise en page sans pagination, cosmétique, réfutations par contrat).

**Revue de suivi recommandée : oui** (2 medium corrigés). Risque nommé non vérifié : la mise en page n'a été contrôlée par aucun rendu visuel ; avec 10 Entités et plusieurs Règles par Entité, la zone Règles peut chevaucher le tableau des KPI. À vérifier à l'ouverture du pptx lors de la recette 5.6 (Scénarios calés : A et B rouges, C orange).

**Vérification.** `ruff check`, `ruff format --check`, `mypy` (249 fichiers), `lint-imports` (13 contrats) et `pytest -q` passent : 2054 réussis, 1 ignoré, 29 désélectionnés.

**Risques résiduels.** Rejeu des Passages composites (Annexe) jusqu'à la déclaration des exclusions ; décalage H-19 limité au tampon ; mise en page non contrôlée visuellement.
