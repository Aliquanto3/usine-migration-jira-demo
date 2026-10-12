---
title: 'Story 1.8 : Calage des Scénarios de démo au jour près'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'dfb33e339759e2158a9258452148f305632a9bfb'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** La Story 1.5 ne vérifie la forme de FR-3 qu'au dernier Jour ouvré de chaque semaine. Calculée Jour ouvré par Jour ouvré avec la Grille par défaut (graine 42, 2026-10-12), la Météo s'écarte du scénario : B n'est rouge que le mercredi de la semaine 2, C reste jaune du lundi au jeudi de la semaine 7, et la Certification réservée de C, qui donne son jaune, est créée un jour tiré de la semaine 4. La revue de suivi de la 1.5 signale aussi deux risques. Une configuration qui contient ENT-A, ENT-B ou ENT-C sur moins de 6 semaines lève une erreur avec les Scénarios par défaut. Et la CLI ne permet pas de désactiver les Scénarios.

**Approach:** Caler le générateur au jour près par ses seuls paramètres. A et B reçoivent leurs premières bloquantes lentes le premier Jour ouvré de leur semaine de bascule. Les Certifications des Scénarios sont créées le premier Jour ouvré de leur semaine. Les Cas de test de C sont exécutés chaque Jour ouvré, et leurs KO suivent un taux cumulé visé dans la Phase en cours, d'où un IND-4 piloté jour par jour. Un test de calage parcourt chaque Jour ouvré avec le calcul complet du domaine (`tickets_etats` puis `meteo`) et la Grille livrée. Les Scénarios par défaut s'adaptent aux programmes courts, les Scénarios explicites restent contrôlés strictement, et la CLI reçoit `--sans-scenarios`.

## Boundaries & Constraints

**Always:**
- Le générateur reste pur et déterministe : une seule instance `Random`, un ordre de tirage fixe.
- La volumétrie de la 1.3 est tenue : les bloquantes de bascule comptent dans les créations de la semaine.
- Les identifiants (1.4) sont toujours tirés en dernier.
- Les paramètres sont typés, validés par `UsineErreur` et documentés en français.
- Le calcul de la Météo dans le test reproduit celui de la Chaîne : l'état des tickets de J-5 au jour, la Grille et le Programme livrés.
- Hors A, B et C, les règles se vérifient sur tous les couples Entité × Jour ouvré.

**Never:**
- Ne pas modifier `config/grille_meteo.yaml` ni le domaine (SM-C3).
- Ne pas toucher `src/usine/contrats/` ni `src/usine/ports/`.
- Ne pas ajouter de clé à `config/programme.yaml`.
- Ne pas ajouter de dépendance.
- Ne pas affaiblir une assertion de la 1.5 sans la remplacer par une assertion au jour près.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Config livrée | graine 42, 2026-10-12 (8 semaines pleines) | Chaque Jour ouvré : A verte ou jaune en semaines 1 à 5, puis rouge ; B rouge de la semaine 2 à la fin ; C verte en semaines 1 à 3, jaune en 4 à 6, orange en 7 et 8. Les autres : au plus 3 Jours ouvrés rouges consécutifs, au moins 80 % de couples verts ou jaunes, au plus 2 rouges le dernier jour | — |
| Dernière semaine partielle | graine 42, date de génération du mardi au samedi d'une même semaine | mêmes trajectoires (test `lent`) | — |
| Programme court, Scénarios par défaut | ENT-A à ENT-C, 5 semaines, `scenarios` omis | A ignoré (vague en semaine 6), B et C appliqués, pas d'erreur | — |
| Scénarios explicites trop longs | `Scenarios(sortie=ScenarioSortie(semaine_vague=9))`, 8 semaines | refus | `UsineErreur` nommant le Scénario, le paramètre et la dernière semaine |
| CLI sans Scénarios | `usine donnees generer --sans-scenarios` | Journal identique à `scenarios=AUCUN_SCENARIO`, sortie « Scénarios appliqués : aucun » | — |
| Paramètre invalide | bloquantes de bascule < 0, taux visé hors [0, 1] | refus à la construction | `UsineErreur` nommant le paramètre |

</intent-contract>

## Code Map

- `src/usine/generateur/scenarios.py` -- `ScenarioSortie`, `ScenarioEnlisement`, `ScenarioMenace` (`taux_ko_initial`, `semaine_hausse`, `taux_ko_hausse`, `nombre_ko`), `Scenarios`, `AUCUN_SCENARIO`, `SCENARIOS_PAR_DEFAUT`.
- `src/usine/generateur/journal.py` -- `generer` (l.777) :
  - contrôle `_verifier_semaines_scenarios` (l.272, appelé l.834) ;
  - boucle des créations (l.857-866 : jour tiré, puis Entité tirée par poids) ;
  - `_profil` (l.243), `_poids_entites` (l.302) ;
  - `_cas_de_test_menace` (l.567 : créés un jour tiré, exécutés plus tard dans la semaine, KO tirés) ;
  - Certifications (l.867-893 : jour tiré dans `jours_par_semaine[semaine_certification]`) ;
  - `Generation` (l.170).
- `src/usine/generateur/cli.py` -- commande `generer` : appelle `generer_journal` sans `scenarios`.
- `src/usine/domaine/meteo.py` (L3, lecture seule) -- `meteo(etats, date_arrete, entites, grille, version, programme=, ancrage=)`. Précondition : l'état couvre J-5 à D.
  - IND-1 : bloquantes ouvertes, orange dès 1, rouge dès 3.
  - IND-2 : âge de la plus vieille bloquante, orange au-delà de 5 Jours ouvrés, rouge au-delà de 10.
  - IND-3 : majeures ouvertes, jaune dès 5, orange dès 10, rouge dès 20.
  - IND-4 : taux de KO cumulé des Cas de test exécutés dont la `phase` est la Phase en cours ; jaune dès 5 %, orange dès 10 %, rouge dès 20 %. Garde-fou : 20 exécutés.
  - IND-5 : Certifications refusées, rouge dès 1.
  - IND-6 : Certifications réservées, jaune dès 1, orange dès 2.
  - IND-7 : ratio des Entrées sur les Sorties, jaune au-delà de 1, orange au-delà de 1,5. Garde-fou : 5 Entrées.
  - IND-8 : IND-4(D) − IND-4(J-5), jaune dès 3 points, orange dès 5.
- `src/usine/chaine/etapes.py` l.80-110 (lecture seule) -- `EtapeMeteo` : l'historique de J-5 au jour est passé à `meteo`. C'est le modèle du test.
- `src/usine/domaine/instantanes.py` -- `tickets_etats(evenements, dates)`.
- `config/programme.yaml` -- V1 : migration à blanc en semaines 1-2, recette en 3-5, TNR en 6-8. `graine: 42`.
- `tests/unit/generateur/test_scenarios.py` -- tests de la 1.5. `test_nombre_ko_par_semaine` et `test_scenario_c_journal` dépendent de la sémantique actuelle des KO, et la semaine de Certification est vérifiée dans `test_certifications`.
- `tests/unit/generateur/test_cli.py` -- tests de la CLI `donnees generer`.
- `pyproject.toml` -- marqueur `lent`, exclu par défaut.
- Mesure de départ (graine 42, 2026-10-12, Météo par Jour ouvré) :
  - A tient déjà son scénario ;
  - B : `vvvvv vOORR` ;
  - C en semaine 7 : `jjjjO` ;
  - les autres Entités respectent déjà les règles.

## Tasks & Acceptance

**Execution:**
- `src/usine/generateur/scenarios.py`
  - Ajouter `bloquantes_bascule` à A et B : bloquantes lentes créées le premier Jour ouvré de la vague (A) ou du début de l'enlisement (B), entier ≥ 0.
  - Redéfinir la sémantique des taux de C : taux de KO cumulé visé dans la Phase en cours, plancher. `ko_cumules(semaine, executes)` remplace `nombre_ko`.
  - Fonction `scenarios_applicables(scenarios, codes, derniere_semaine)` : garde les Scénarios dont l'Entité est présente et dont les semaines tiennent dans l'historique.
  - Docstrings à jour.
- `src/usine/generateur/journal.py`
  - Bloquantes de bascule placées au premier Jour ouvré, prises sur le nombre de créations de la semaine.
  - Certifications des Scénarios créées au premier Jour ouvré de leur semaine.
  - `_cas_de_test_menace` : Cas de test répartis sur chaque Jour ouvré de la semaine, créés le matin et exécutés l'après-midi. Les KO de chaque jour sont égaux à `ko_cumules` moins les KO déjà comptés dans la Phase.
  - `generer(..., scenarios: Scenarios | None = None)` : `None` applique `SCENARIOS_PAR_DEFAUT` réduits par `scenarios_applicables` ; des Scénarios explicites sont contrôlés strictement, comme aujourd'hui.
  - `Generation.scenarios` : les Scénarios appliqués.
- `src/usine/generateur/cli.py` -- option `--sans-scenarios` (`AUCUN_SCENARIO`). La sortie liste les Scénarios appliqués.
- `tests/unit/generateur/test_calage.py` -- créer :
  - Test rapide, graine 42 et 2026-10-12 : Météo de chaque Entité à chaque Jour ouvré, calcul de la Chaîne, Grille livrée. Assertions de l'AC 1.8.
  - Test `lent` : dates de génération du mardi au samedi.
  - Tests des Scénarios applicables (programme court) et de `bloquantes_bascule`.
- `tests/unit/generateur/test_scenarios.py` -- aligner les tests de C sur les KO cumulés. Ajouter le premier Jour ouvré des Certifications et les nouveaux paramètres invalides.
- `tests/unit/generateur/test_cli.py` -- `--sans-scenarios` et ligne des Scénarios appliqués.

**Acceptance Criteria:**
- Given le Journal de la configuration livrée (graine 42) et la Grille par défaut, when le test calcule la Météo de chaque Entité pour chaque Jour ouvré, then les trajectoires de FR-3 sont tenues au jour près et les règles hors A, B et C sont tenues.
- Given un écart au scénario, when il est corrigé, then seuls les paramètres du générateur changent : `git diff` ne touche ni `config/grille_meteo.yaml` ni `src/usine/domaine/`.
- Given `uv run pytest -q`, when la suite tourne, then tout passe et le test de calage rapide dure moins de 10 s.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
Le diff relu couvre les Stories 1.5 et 1.8 (`26311420..` sur les fichiers de la lane), pour faire relire aussi les correctifs de la 1.5 (revue de suivi recommandée).
- verdicts: 31 findings — high 0, medium 2, low 24, false 5, maybe-false 0
- findings:
  - `[low]` `[reject]` (blind) Bloquantes de bascule rejetables (`PROBA_REJET`), le rouge de A et B dépendrait de la graine. Les autres bloquantes lentes de la vague (A) ou de l'enlisement (B) prennent le relais avant tout rejet possible, au plus tôt 4 Jours ouvrés après la bascule. Le calage tient sur les graines 42, 1, 7 et 123 et sur 6 dates de génération. Une exemption de rejet ajouterait une branche sans cas observé.
  - `[low]` `[patch]` (blind) Calage vérifié sur la seule graine 42. Ajout de `test_calage_autres_graines` (`lent`, graines 1, 7 et 123), qui passe.
  - `[low]` `[reject]` (blind) Scénarios appliqués absents des sorties écrites. Le constat est déjà en `deferred` dans la spec 1.5 (`EnteteJournal` gelé). La CLI affiche désormais les Scénarios appliqués.
  - `[low]` `[reject]` (blind) Changement du générateur sans marqueur de version. `EnteteJournal` est gelé. La rupture « même graine, même Journal » est attendue et consignée (1.5 et Risques résiduels ci-dessous).
  - `[low]` `[reject]` (blind) Scénarios écartés sans message. Une Entité absente est ignorée par conception (matrice de la 1.5), et la CLI liste les Scénarios appliqués : l'écart se voit.
  - `[low]` `[reject]` (blind) Scénarios liés au calendrier V1 sans garde. C'est documenté dans `programme.yaml`. Un changement du calendrier livré fait échouer `test_calage`.
  - `[low]` `[reject]` (blind) Validations croisées absentes : taux croissants, `semaine_vague = 1`, vague de A et début de B la même semaine. Ces cas n'arrivent pas avec les défauts. Les gardes ajouteraient de la complexité sans cas réel.
  - `[low]` `[reject]` (blind) Statut de Certification de C codé en dur. Le même constat a été rejeté à la 1.5 : FR-3 fixe la réserve de C.
  - `[low]` `[reject]` (blind) Lacunes de `_ecarts` : B en semaine 1 non contraint (FR-3 est muet), 2 rouges tolérés contre 0 dans la 1.5 (le test de la 1.5 est plus strict que l'AC, et les deux tiennent), plantage sans Entité hors Scénario (helper de test appelé sur la configuration livrée seulement).
  - `[low]` `[reject]` (blind) Deux calculs de Météo dans les tests. `meteo` filtre `date ≤ D` et ne lit que J-5 à D, donc le résultat est identique. Le test de calage reproduit la fenêtre de la Chaîne comme demandé (calcul complet du domaine).
  - `[low]` `[reject]` (blind) Préparation dupliquée entre les deux fichiers de test. C'est cosmétique (environ 1 s).
  - `[low]` `[reject]` (blind) Le test de bascule ne vérifie pas que les bloquantes restent ouvertes. Le résultat (rouge chaque jour) est vérifié par le test de calage.
  - `[low]` `[reject]` (blind) Profils normal et calme sans test direct. Le même constat a été rejeté à la 1.5 : ils sont couverts par les trajectoires, désormais au jour près.
  - `[low]` `[reject]` (blind) Volume de C (6 Cas de test par jour) jugé peu plausible. 240 Cas de test sur 8 semaines pour l'Entité en TNR restent plausibles, avec environ 500 événements de plus sur un Journal de plus de 30 000.
  - `[medium]` `[patch]` (verification-gap) Calage d'une dernière semaine partielle (cas par défaut de la CLI en milieu de semaine) seulement en `lent`. Ajout de `test_calage_derniere_semaine_partielle_rapide` (mercredi, 2 Jours ouvrés en semaine 8) dans la suite rapide.
  - `[low]` `[patch]` (verification-gap) Répartition du reste dans `_cas_du_jour` jamais exercée. Ajout de `test_cas_du_jour` (30, 32, 4, 1, avec la somme hebdomadaire).
  - `[low]` `[reject]` (edge) Vague de A et début de B la même semaine : la bascule de B serait tronquée. Ce n'est pas le cas avec les défauts. Même racine que la ligne « validations croisées ».
  - `[false]` `[reject]` (edge) Bascule supérieure aux créations de la semaine, troncature silencieuse. C'est le comportement voulu et testé (`test_bloquantes_bascule_prises_sur_la_semaine`, cas 50), et documenté dans la docstring.
  - `[low]` `[reject]` (edge) Bloquantes de bascule rejetées ou fermées avant la fin. Même racine et même réponse que la première ligne.
  - `[low]` `[reject]` (edge) `statut_certification` non typé. Le même constat a été rejeté à la 1.5 (usage interne typé, mypy).
  - `[low]` `[reject]` (edge) Scénario d'un mauvais type dans un emplacement de `Scenarios`. C'est exclu par le typage (mypy strict), et aucun appelant non typé n'existe.
  - `[low]` `[reject]` (edge) `_ecarts` plante si toutes les Entités sont scénarisées. Helper de test, appelé seulement sur des configurations qui ont 7 Entités hors Scénario.
  - `[low]` `[reject]` (edge) KO du jour bornés, donc l'égalité avec `ko_cumules` peut céder pour des taux décroissants ou des jours sans Cas de test. Les bornes sont documentées dans la docstring. Elles ne mordent pas avec les défauts, et `test_scenario_c_journal` vérifie l'égalité chaque jour.
  - `[false]` `[reject]` (intent) Le test contourne la Chaîne. L'intention demande le calcul complet du domaine, que le test appelle (`tickets_etats` puis `meteo`) avec la fenêtre de la Chaîne et la Grille livrée.
  - `[medium]` `[patch]` (intent) Calage sur le Corpus provisoire alors que la démo génère avec le Corpus versionné : l'équivalence ne tenait qu'à la taille égale des cases. `test_calage` génère désormais avec `donnees/corpus/textes.json` (`_corpus_versionne`).
  - `[low]` `[reject]` (intent) SM-C3 sans assertion sur la Grille. La Grille appartient à L3. Le contrôle passe par la commande de Vérification (`git diff` vide sur la Grille et le domaine).
  - `[low]` `[reject]` (intent) Programme court : B et C appliqués sans garantie de trajectoire hors calendrier V1. Même racine que « calendrier V1 sans garde ». L'intention demandait que ces programmes restent utilisables, pas calés.
  - `[false]` `[reject]` (intent) Les autres appelants reçoivent les Scénarios par défaut sans le cibler. C'était déjà le cas depuis la 1.5 (défaut `SCENARIOS_PAR_DEFAUT`), et la suite complète passe.
  - `[low]` `[reject]` (intent) Troisième variante de calcul de la Météo dans `test_scenarios.py`. Même racine que « deux calculs de Météo » : résultat identique.
  - `[false]` `[reject]` (intent) `test_meteo_hors_scenarios` plus strict que l'AC. Ce n'est pas un défaut : les deux contrôles tiennent.
  - `[false]` `[reject]` (intent) `test_excel.py` passe de « orange ou rouge » à « rouge ». C'est voulu (report de la 1.3, relu à la 1.5).

## Design Notes

- **KO cumulés.** IND-4 est un taux cumulé par Phase, évalué en fin de journée. Les KO de C se décident jour par jour pour que le cumul de la Phase vaille ⌊taux visé × exécutés⌋. IND-4 reste ainsi sous le taux visé, à moins d'un exécuté près, quel que soit le jour.
  - Valeurs visées : 0,03 en semaines 1 à 3, puis (0,045 ; 0,065 ; 0,07 ; 0,14 ; 0,17) à partir de la semaine 4. Le plan initial visait 0,05 et 0,07 en semaines 4 et 5, mais le vendredi de la semaine 4 donnait alors 3 KO sur 60 contre 0 sur 30 à J-5 : exactement 5 points sur IND-8, donc orange. L'écart a été mesuré à l'implémentation et corrigé par ces paramètres.
  - Vert ou jaune selon la semaine : IND-4 reste sous 5 % jusqu'à la semaine 3 et sous 10 % jusqu'à la semaine 6, et IND-8 reste sous 3 puis 5 points.
  - Orange dès le lundi de la semaine 7 : 0,14 − 1/36 ≥ 0,10, et le taux visé reste sous 20 %.
- **Bascule au lundi.** Avec la Grille par défaut, le rouge par IND-1 demande 3 bloquantes ouvertes. Une vague dont les créations sont tirées sur toute la semaine bascule donc un jour aléatoire. Placer `bloquantes_bascule` (3) le premier Jour ouvré fixe la bascule. Les délais lents (correction de 15 à 30 Jours ouvrés) maintiennent le rouge.
- **Scénarios par défaut, programmes courts.** Lever une erreur sur un Scénario par défaut trop long empêchait toute génération courte qui contient ENT-A, ENT-B ou ENT-C (risque de la 1.5). Les défauts sont donc réduits aux Scénarios qui tiennent dans l'historique. Des Scénarios fournis explicitement restent refusés s'ils débordent : le correctif medium de la 1.5 est conservé.
- **Fichiers hors lane** : aucun prévu.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check .` -- expected: aucun écart
- `uv run mypy && uv run lint-imports` -- expected: succès
- `uv run pytest -q` -- expected: tout passe
- `uv run pytest -q -m lent tests/unit/generateur` -- expected: calage tenu sur les dates de génération testées
- `git diff --stat dfb33e339759e2158a9258452148f305632a9bfb -- config/grille_meteo.yaml src/usine/domaine` -- expected: vide

## Auto Run Result

Status: done

**Résumé.** Avec la graine 42, la Météo calculée Jour ouvré par Jour ouvré (calcul complet du domaine, fenêtre de la Chaîne, Grille livrée) suit FR-3 au jour près :
- **A** : verte ou jaune en semaines 1 à 5, rouge chaque jour à partir du lundi de la semaine 6.
- **B** : rouge chaque jour à partir du lundi de la semaine 2.
- **C** : verte en semaines 1 à 3, jaune en 4 à 6, orange en 7 et 8.
- **Autres Entités** : aucune n'est jamais rouge.

Le calage tient pour une génération le 2026-10-12 (8 semaines pleines) et pour chaque date du mardi au samedi (dernière semaine partielle). Il tient aussi pour les graines 1, 7 et 123. Seuls les paramètres et la mécanique du générateur ont changé. La Grille et le domaine sont intacts (SM-C3).

Moyens mis en œuvre :
- Bloquantes de bascule (3) de A et B, créées le premier Jour ouvré de leur semaine de bascule.
- Certifications des Scénarios créées le premier Jour ouvré de leur semaine.
- Cas de test de C répartis sur chaque Jour ouvré (créés le matin, exécutés l'après-midi), avec des KO décidés jour par jour sur un taux cumulé visé dans la Phase en cours.

Risque de la 1.5 traité :
- `generer(..., scenarios=None)` réduit les Scénarios par défaut à ceux qui tiennent dans l'historique : un programme court génère sans erreur.
- Des Scénarios explicites restent contrôlés strictement.
- La CLI reçoit `--sans-scenarios` et affiche les Scénarios appliqués.

**Fichiers.**
- `src/usine/generateur/scenarios.py` : `bloquantes_bascule`, KO cumulés visés (`ko_cumules`), `scenarios_applicables`, `Scenarios.actifs` et `resume`.
- `src/usine/generateur/journal.py` : bascules au premier Jour ouvré, Certifications des Scénarios au premier Jour ouvré, Cas de test de C jour par jour, `scenarios=None`, `Generation.scenarios`.
- `src/usine/generateur/cli.py` : `--sans-scenarios` et ligne « Scénarios appliqués ».
- `tests/unit/generateur/test_calage.py` (nouveau) : calage au jour près, en rapide (lundi et mercredi, Corpus versionné) et en `lent` (autres dates et graines). S'y ajoutent les tests de bascule, de programme court, de `scenarios_applicables` et de `_cas_du_jour`.
- `tests/unit/generateur/test_scenarios.py` : KO cumulés jour par jour pour C, premier Jour ouvré des Certifications, nouveaux paramètres invalides.
- `tests/unit/generateur/test_cli.py` : `--sans-scenarios` et Scénarios appliqués.
- Aucun fichier hors lane.

**Revue.** Elle porte sur les diffs de la 1.5 et de la 1.8 (revue de suivi de la 1.5 comprise). 31 constats :
- 4 corrigés : medium (2), Corpus versionné dans le calage et dernière semaine partielle dans la suite rapide ; low (2), graines supplémentaires en `lent` et test de `_cas_du_jour`.
- 0 reporté.
- 27 rejetés, avec leur raison dans le journal de triage : bascules rejetables, garde de calendrier, validations croisées, traçabilité dans l'en-tête (déjà en `deferred` à la 1.5), duplication des tests, etc.

Les correctifs de la 1.5 relus (contrôle des semaines, cause `reprise_donnees` forcée, poids borné) n'appellent aucun nouveau correctif. Le contrôle des semaines est désormais réservé aux Scénarios explicites.

**Écart au plan.** Les taux visés de C en semaines 4 et 5 sont 0,045 et 0,065, au lieu de 0,05 et 0,07. Avec 0,05, IND-8 atteignait exactement 5 points le vendredi de la semaine 4 et passait C en orange (voir Design Notes).

**Revue complémentaire recommandée : oui** (2 entrées medium corrigées). Risque non vérifié : les deux correctifs ne touchent que les tests (Corpus versionné, date partielle en rapide), mais la suite rapide exécute désormais deux calages complets d'environ 2,6 s chacun. Le passage au Corpus versionné n'a pas été relu de façon indépendante.

**Vérification.**
- `ruff check`, `ruff format --check`, `mypy` et `lint-imports` (13 contrats) passent.
- `pytest -q` : 1 678 passés, 1 sauté.
- `pytest -q -m lent tests/unit/generateur` : 27 passés.
- `git diff` sur la Grille et le domaine : vide.
- Durées : environ 2,6 s pour le test de calage du lundi, autant pour celui du mercredi.

**Risques résiduels.**
- Le Journal de toute graine change encore : les lanes aval (Story 2.7, Story 4.5, injection) doivent régénérer.
- Le calage dépend du calendrier V1 livré et du Corpus versionné. La Story 1.9 doit relancer `test_calage`.
- Les autres graines ne sont pas garanties au-delà de 1, 7, 42 et 123.
- Les bloquantes de bascule restent soumises au rejet du workflow : le rouge repose sur l'accumulation des autres bloquantes lentes.
