---
title: 'Story 1.1 : Configuration complète du Programme'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '0714669752662ca46ca4afecbf08fc62b4bd2463'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
warnings: [oversized]
deferred:
  - summary: >-
      La dernière semaine partielle (Date d'injection un lundi) reçoit au moins entrees_semaine_min créations sur un seul jour.
    evidence: |-
      _repartition_par_semaine applique le même plancher à chaque semaine ; avec une date de génération un mardi, la semaine 8 n'a qu'un Jour ouvré et reçoit au moins 200 créations ce jour-là, ce qui fausse les KPI quotidiens. À proratiser en Story 1.3.
    location: >-
      src/usine/generateur/journal.py (_repartition_par_semaine)
    severity: medium
  - summary: >-
      Les créations peuvent saturer le maximum hebdomadaire d'Entrées et ne laisser presque aucune place aux réouvertures, attribuées en outre dans l'ordre de génération.
    evidence: |-
      _bornes_anomalies borne les créations à nb_semaines × entrees_semaine_max ; accepter_reouverture refuse ensuite toute réouverture d'une semaine pleine, au profit des Anomalies générées tôt. Taux de réouverture à modéliser avec le workflow H-17 complet (Story 1.3).
    location: >-
      src/usine/generateur/journal.py (_bornes_anomalies, _Calendrier.accepter_reouverture)
    severity: medium
  - summary: >-
      Aucun test ne fait tourner la Chaîne complète sur le Programme livré (10 Entités, environ 3 600 Anomalies).
    evidence: |-
      Toutes les fixtures des autres lanes passent sur programme_reduit.yaml pour garder la suite rapide (la config complète la portait à plus de 10 min). La recette de bout en bout relève de la Story 5.6.
    location: >-
      tests/unit/chaine/environnement.py
    severity: medium
  - summary: >-
      La config livrée annonce 5 000 Anomalies au plus alors que 8 × 500 Entrées plafonnent la génération à 4 000.
    evidence: |-
      Valeurs reprises telles quelles de l'AC de la Story 1.1 ; le générateur tire dans l'intersection. Ajustement de la volumétrie à trancher en Story 1.3.
    location: >-
      config/programme.yaml (volumetrie)
    severity: low
  - summary: >-
      outils/mesurer_nfr2.py n'a aucun test de l'élargissement des Entrées qui garde 5 000 Anomalies atteignables.
    evidence: |-
      Aucun test sous tests/ ne référence programme_cible ; une régression lèverait « volumétrie infaisable » à la mesure manuelle.
    location: >-
      outils/mesurer_nfr2.py (programme_cible)
    severity: low
  - summary: >-
      L'erreur de Vague inconnue affiche la clé « (racine) » et tout le contenu du fichier au lieu de entites[i].vague.
    evidence: |-
      Le validateur _references de ConfigProgramme (contrats gelés) lève à la racine ; le message nomme l'Entité, la Vague et la valeur. Une clé précise demande une PR sur main (contrats).
    location: >-
      src/usine/contrats/config.py (ConfigProgramme._references)
    severity: low
---

<intent-contract>

## Intent

**Problem:** `config/programme.yaml` décrit encore le Programme réduit du walking skeleton (2 Entités, 1 Vague, 25 à 35 Anomalies). Le mini-générateur ignore le calendrier des Phases et les Entrées par semaine, fixe le préfixe `DEMO` en dur et recalcule le lundi de la semaine hors de `contrats.calendrier` (rétrospective Epic 0, constat 12).

**Approach:** Livrer la configuration complète « Banque Exemple — migration SI cœur » (10 Entités, 3 Vagues, Domaines, Phases, volumétrie cible). Rendre le générateur fidèle à toute la configuration : Entités, bornes d'Anomalies et d'Entrées par semaine, Phase tirée du calendrier de la Vague, préfixe de clé passé par l'appelant depuis `ConfigJira.cle_projet`, semaines calculées par `contrats.calendrier`. Les tests des autres lanes passent sur une copie figée de l'ancienne configuration réduite, pour garder leur durée et leurs attendus.

## Boundaries & Constraints

**Always:** générateur pur et déterministe (graine, date, une seule instance `Random`) ; Journal et vérité terrain inchangés dans leur format ; chaque clé YAML commentée en français ; données 100 % fictives ; erreurs en `UsineErreur`.

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` (gelés, AD-2) ; modifier `config/jira.yaml` ; viser la volumétrie fine, le workflow complet H-17 ou les Scénarios (Stories 1.3 et 1.5) ; ajouter une dépendance.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Config livrée | `config/programme.yaml` | 10 Entités `ENT-A`…`ENT-J`, 3 Vagues avec 3 Phases, Anomalies dans [3000, 5000], Entrées par semaine dans [200, 500] | — |
| Copie réduite | 6 Entités, volumétrie divisée par deux | Journal avec exactement ces 6 Entités, Anomalies dans [1500, 2500], Entrées/semaine dans [100, 250] | — |
| Vague inconnue | Entité avec `vague: V9` | refus au chargement | `UsineErreur` nommant le fichier, l'Entité, « Vague » et `V9` |
| Volumétrie infaisable | bornes d'Anomalies hors de `[nb_semaines × min, nb_semaines × max]` d'Entrées | refus à la génération | `UsineErreur` nommant les bornes |
| Vague sans Phase | `phases: []` | refus à la génération | `UsineErreur` nommant la Vague |
| Clé de projet | `cle_projet` du `config/jira.yaml` | clés `<cle_projet>-<n>` | clé hors `^[A-Z][A-Z0-9]+$` → `UsineErreur` |

</intent-contract>

## Code Map

- `config/programme.yaml` -- à réécrire ; validé par `ConfigProgramme` (`src/usine/contrats/config.py`, gelé : `extra="forbid"`, `_references` refuse doublons, Vague inconnue, Phase au-delà de `nb_semaines`).
- `src/usine/generateur/journal.py` -- `PREFIXE_CLE` (l.41), `fenetre_generation` (l.255-267, boucle du lundi à remplacer), `generer` (l.317, tirage du nombre d'Anomalies et de leur jour), `_anomalie`/`_cas_de_test` (Phase tirée au hasard), `_statut_suivant` (réouverture `fermee → en_analyse`).
- `src/usine/generateur/cli.py` -- `usine donnees generer` ; doit lire `config/jira.yaml` (option `--config-jira`) pour la clé de projet.
- `src/usine/contrats/calendrier.py` -- réutiliser `jour_ouvre_precedent`, `verifier_lundi`, `semaine_programme`, `jours_ouvres`, `jour_local`.
- `src/usine/config/chargeur.py` -- `charger_yaml` produit déjà « fichier : clé « … », valeur … refusée (msg) » (lecture seule).
- `tests/unit/generateur/test_journal.py`, `tests/unit/generateur/test_cli.py` -- tests de la lane, utilisent `config/programme.yaml`.
- Consommateurs hors lane de `config/programme.yaml` (attendus fondés sur ENT-A/ENT-B et quelques centaines d'événements) : `tests/unit/chaine/environnement.py` (`preparer_racine`, utilisé par chaine, rendu, ui, composition), `tests/contrat/consultation/fabriques.py`, `tests/contrat/source_tickets/fabriques.py`, `tests/unit/adaptateurs/journal/test_source_journal.py`, `tests/unit/domaine/test_instantanes.py`, `tests/unit/domaine/test_meteo.py`, `tests/unit/test_composition.py`. Avec la config complète la suite passe de 47 s à plus de 10 min et `test_autoportance_meteo` échoue.

## Tasks & Acceptance

**Execution:**
- `config/programme.yaml` -- réécrire : nom « Banque Exemple — migration SI cœur », graine 42, 8 semaines ; ENT-A…ENT-D en V1, ENT-E…ENT-G en V2, ENT-H…ENT-J en V3 (libellés lettres grecques) ; V1 mab 1-2 / recette 3-5 / tnr 6-8, V2 mab 1-3 / recette 4-6 / tnr 7-8, V3 mab 1-4 / recette 5-7 / tnr 8-8 ; Domaines credits, depots, paiements, referentiel_clients, comptabilite, epargne ; volumétrie 3000/5000/200/500 ; un commentaire français par clé.
- `tests/unit/generateur/programme_reduit.yaml` -- copie exacte de l'ancienne configuration réduite, en-tête expliquant son rôle de fixture d'essai.
- `src/usine/generateur/journal.py` -- (a) `generer(config, graine, date_generation, *, cle_projet=CLE_PROJET_ESSAI)` valide la clé et l'utilise ; (b) `fenetre_generation` via `jour_ouvre_precedent(date_injection, weekday)` + `verifier_lundi` ; (c) nombre d'Anomalies tiré dans l'intersection des bornes d'Anomalies et de `nb_semaines × bornes d'Entrées`, réparti par semaine (minimum puis complément aléatoire sous le maximum), jour et Entité tirés dans la semaine ; (d) réouvertures acceptées seulement si la semaine n'a pas atteint son maximum d'Entrées ; (e) Phase d'une Anomalie ou d'un Cas de test = Phase du calendrier de la Vague de l'Entité pour la semaine de création (dernière Phase commencée, sinon la première).
- `src/usine/generateur/cli.py` -- option `--config-jira` (défaut `config/jira.yaml`), clé de projet passée à `generer`.
- `tests/unit/generateur/test_journal.py`, `tests/unit/generateur/test_cli.py` -- tests des AC et de la matrice ; tests existants basés sur la fixture réduite sauf ceux propres à la config livrée.
- Fichiers hors lane (tests) -- remplacer `config/programme.yaml` par la fixture réduite (copie sur `racine/config/programme.yaml` dans `preparer_racine` et `consultation/fabriques.py` ; chemin direct ailleurs).

**Acceptance Criteria:**
- Given `config/programme.yaml` livré, when `charger_yaml(..., ConfigProgramme)` le valide, then il décrit « Banque Exemple — migration SI cœur », `ENT-A`…`ENT-J`, 3 Vagues avec migration à blanc, recette et TNR, et la volumétrie 3000-5000 / 200-500, chaque clé commentée, sans nom réel.
- Given la config livrée, when on génère (graine 42, 2026-10-12), then le Journal porte les 10 Entités, un nombre d'Anomalies et des Entrées par semaine dans les bornes.
- Given une copie à 6 Entités et volumétrie divisée par deux, when l'auteur lance `usine donnees generer --config <copie>`, then le Journal respecte ces valeurs sans modification de code.
- Given une Entité référençant une Vague inconnue, when elle est chargée, then une `UsineErreur` nomme le fichier, l'Entité, la Vague et la valeur fautive.
- Given `cle_projet: PILOTE` dans la config Jira passée à la CLI, when on génère, then toutes les clés commencent par `PILOTE-`.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 28 findings — high 0, medium 6, low 15, false 7, maybe-false 0
- findings:
  - `[low]` `[reject]` (intent) Aucun test du critère « aucun nom réel » — impossible à tester sans liste de noms réels ; valeurs relues : libellés en lettres grecques, nom « Banque Exemple ».
  - `[false]` `[reject]` (intent) `cle_projet`/`--config-jira` hors intention — exigé par le run (rétrospective Epic 0, constat 12, à traiter en L1).
  - `[low]` `[defer]` (intent) Volumétrie réduite à 3 000-4 000 par l'intersection des bornes — choix documenté dans les Design Notes ; reporté en Story 1.3.
  - `[medium]` `[defer]` (intent) Les autres lanes ne testent plus le Programme livré — fixtures réduites indispensables à la durée de la suite ; recette de bout en bout en Story 5.6.
  - `[low]` `[defer]` (blind) `anomalies_max: 5000` inatteignable — même cause que la ligne d'intention ci-dessus.
  - `[medium]` `[defer]` (blind) Créations proches du maximum : plus de place pour les réouvertures — réel ; modèle de réouverture en Story 1.3.
  - `[low]` `[defer]` (blind) Capacité de réouverture attribuée dans l'ordre de génération — même racine que la ligne précédente.
  - `[low]` `[patch]` (blind) Mesure NFR-2 sans réouverture — `entrees_semaine_max` porté à 2 × ceil(5000/8) ; 42 réouvertures gardées, toujours 5 000 Anomalies.
  - `[low]` `[patch]` (blind) Docstring du module : sortie fonction de (config, graine, date) seulement — `cle_projet` ajouté.
  - `[low]` `[reject]` (blind) La CLI exige `config/jira.yaml` — fichier livré ; son absence lève une `UsineErreur` explicite ; un repli ajouterait une branche sans besoin.
  - `[low]` `[reject]` (blind) Motif de clé de projet dupliqué — le motif vit dans un `Field` de `contrats.config` (gelé), non exportable sans PR contrats.
  - `[low]` `[reject]` (blind) Erreurs de volumétrie et de Vague sans Phase sans le chemin du fichier — le message nomme la Vague ou les bornes ; ajouter le chemin demande une surface publique nouvelle ; l'appel redondant de `_verifier_phases` est négligeable.
  - `[medium]` `[patch]` (blind) `semaine_fin` ignoré : Phase terminée attribuée — `_phase_du_calendrier` choisit d'abord une Phase qui contient la semaine ; tests de trou et de Phase terminée ajoutés.
  - `[false]` `[reject]` (blind) `KeyError` pour une semaine sans Jour ouvré — impossible : l'ancrage est un lundi et chaque semaine 1..nb_semaines contient son lundi, antérieur ou égal à la Date d'injection.
  - `[medium]` `[defer]` (blind) Plancher d'Entrées appliqué à la dernière semaine partielle — réel ; proratisation en Story 1.3.
  - `[low]` `[patch]` (blind) Borne haute 2 500 trop lâche dans le test à 6 Entités — assertion ramenée à 2 000.
  - `[medium]` `[defer]` (blind) Pas de Chaîne complète sur le Programme livré — même racine que la ligne d'intention.
  - `[false]` `[reject]` (blind) Tests lents sans budget — suite complète en 44 s contre 47 s avant la story.
  - `[low]` `[patch]` (blind) Commentaires périmés de `programme_reduit.yaml` (« non utilisé ») — reformulés ; la docstring de `tests/contrat/source_tickets/fabriques.py` (hors lane) est laissée.
  - `[medium]` `[patch]` (edge) `semaine_fin` jamais lu — même correctif que la ligne blind correspondante.
  - `[low]` `[reject]` (edge) `jira.yaml` requis par la génération — voir la ligne blind correspondante.
  - `[low]` `[reject]` (edge) `composition.generer_journal` écrit toujours `DEMO-` — `composition.py` appartient à `main` ; le `jira.yaml` livré vaut DEMO ; comportement documenté dans `CLE_PROJET_ESSAI`.
  - `[medium]` `[defer]` (edge) Dernière semaine partielle — même racine que la ligne blind correspondante.
  - `[false]` `[reject]` (edge) `fenetre_generation` s'écarte du mécanisme de la spec — un test garde interdit `.weekday(` hors du calendrier ; le résultat est identique et passe par `jour_ouvre_precedent`.
  - `[low]` `[patch]` (verification-gap) Départage de deux Phases de même début non testé — `test_phase_meme_debut_rang_le_plus_eleve` ajouté.
  - `[low]` `[defer]` (verification-gap) Élargissement de `mesurer_nfr2` non testé — disposition déposée : defer (outil manuel, erreur bruyante).
  - `[false]` `[reject]` (verification-gap, autre) Mesure NFR-2 sans réouverture — doublon de la ligne blind déjà corrigée.
  - `[false]` `[reject]` (verification-gap, autre) Clé de projet non appliquée dans `composition` — doublon de la ligne edge déjà rejetée.

## Design Notes

- **Bornes infaisables dans la config livrée.** 3 000 à 5 000 Anomalies et 200 à 500 Entrées par semaine sur 8 semaines ne se recoupent que sur [3 000, 4 000] : le générateur tire dans l'intersection. Les valeurs de l'AC sont reprises telles quelles ; l'ajustement fin relève de la Story 1.3.
- **Clé de projet.** `ConfigProgramme` est gelé et `config/jira.yaml` appartient à L2 : la CLI lit `ConfigJira.cle_projet` et le passe à `generer`. Le défaut `CLE_PROJET_ESSAI = "DEMO"` ne sert qu'aux appelants sans config Jira (tests, `composition.generer_journal`, hors lane, non modifié).
- **Message de Vague inconnue.** Le validateur gelé `_references` lève à la racine : la clé affichée est « (racine) » mais le message nomme l'Entité, la Vague et la valeur. Une clé précise `entites[i].vague` demanderait de modifier `contrats/` : reporté.
- **Fichiers hors lane** (indispensables : la config complète rend la suite dix fois plus lente et casse les attendus ENT-A/ENT-B des autres lanes) : `tests/unit/chaine/environnement.py`, `tests/contrat/consultation/fabriques.py`, `tests/contrat/source_tickets/fabriques.py`, `tests/unit/adaptateurs/journal/test_source_journal.py`, `tests/unit/domaine/test_instantanes.py`, `tests/unit/domaine/test_meteo.py` (une ou deux lignes chacun : chemin de la fixture réduite).

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check .` -- expected: aucun écart
- `uv run mypy && uv run lint-imports` -- expected: succès
- `uv run pytest -q` -- expected: tout passe, durée proche de l'actuelle (< 90 s)
- `uv run usine donnees generer --graine 42 --date-generation 2026-10-12 --sortie <tmp>` -- expected: Journal écrit, clés `DEMO-<n>`

## Auto Run Result

Status: done

**Résumé.** `config/programme.yaml` décrit désormais « Banque Exemple — migration SI cœur » : 10 Entités ENT-A à ENT-J, 3 Vagues avec leur calendrier de Phases, 6 Domaines bancaires, volumétrie 3 000-5 000 et 200-500. Le générateur applique toute la configuration : bornes d'Anomalies et d'Entrées par semaine, Phase tirée du calendrier de la Vague, clé de projet issue de `ConfigJira.cle_projet` (constat 12). Le lundi de la semaine est calculé par `contrats.calendrier`.

**Fichiers.**
- `config/programme.yaml` : configuration complète, commentée.
- `src/usine/generateur/journal.py` : volumétrie par semaine, Phase du calendrier, plafond des réouvertures, `cle_projet`.
- `src/usine/generateur/cli.py` : option `--config-jira`.
- `outils/mesurer_nfr2.py` : Entrées élargies pour garder 5 000 Anomalies.
- `tests/unit/generateur/programme_reduit.yaml` : fixture réduite figée.
- `tests/unit/generateur/test_journal.py`, `test_cli.py` : tests des AC et de la matrice.
- Hors lane (une ou deux lignes, passage à la fixture réduite) : `tests/unit/chaine/environnement.py`, `tests/contrat/consultation/fabriques.py`, `tests/contrat/source_tickets/fabriques.py`, `tests/unit/adaptateurs/journal/test_source_journal.py`, `tests/unit/domaine/test_instantanes.py`, `tests/unit/domaine/test_meteo.py`.

**Revue.** 28 constats : 7 correctifs appliqués (dont 2 constats sur `semaine_fin`), 8 reportés (6 entrées `deferred`), 13 rejetés avec leur raison dans le journal de triage. Correctifs par verdict : medium 1 (entrée groupée `semaine_fin`), low 5. Revue complémentaire recommandée : non (aucun `high`, un seul `medium` corrigé).

**Vérification.** `ruff check`, `ruff format --check`, `mypy`, `lint-imports` (13 contrats) : succès. `pytest -q` : 1 007 passés, 1 ignoré, 44 s. `usine donnees generer --graine 42 --date-generation 2026-10-12` : 39 741 événements, clés `DEMO-<n>`.

**Risques résiduels.** Même graine, Journal différent de celui de l'Epic 0 (ordre de tirage changé). `controle_lanes.py` signale les six fichiers de tests hors lane listés ci-dessus. Volumétrie fine et dernière semaine partielle laissées à la Story 1.3.
