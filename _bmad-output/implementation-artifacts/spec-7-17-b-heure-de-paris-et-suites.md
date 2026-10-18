---
title: "Story 7.17-b : Heure de Paris à l'affichage, badge hors périmètre robuste, reprise de Chaîne"
type: 'feature'
created: '2026-10-18'
status: 'done'
baseline_revision: '8c43854'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---
## Intent

**Problem:** Décisions d'Anaël du 18/10/2026 : (1) toute heure lue par un humain s'affichait en UTC (pastille « Passage publié · … UTC », traçabilité Excel et PowerPoint, journal de la Chaîne, journaux de la CLI) ; (2) le badge « hors périmètre » de l'Agent comparait la réponse du LLM à `SANS_REPONSE` par égalité stricte ; (3) la reprise d'une Chaîne après un redémarrage de `usine ui` n'était pas documentée.

**Approach:** Un point unique de mise en forme dans `contrats.format` (`heure_de_paris`, `formater_heure`, `formater_horodatage`, `Europe/Paris` via `calendrier.FUSEAU`, sans mention de fuseau), réutilisé par l'UI, le rendu et la CLI ; contrats 1.10.0 (ajout sans rupture, commit dédié). Les données restent en UTC. Comparaison normalisée et pure `ui.agent.est_hors_perimetre`. Remarque ajoutée au script de démo et aux tests manuels.

## Boundaries & Constraints

**Always:** les données restent en UTC (entrepôt DuckDB, manifestes, JSONL de progression, `passage_id`, contrats, comparaisons et calculs). Heure d'été et d'hiver gérées, changement de jour compris.

**Never:** modifier `src/usine/ports/` ; convertir l'heure ailleurs que dans `contrats.format` ; toucher les contrats pour le badge.

## Inventaire des heures affichées

| Point | Avant | Sort |
|-------|-------|------|
| `ui/vues.libelle_passage` (pastille de l'en-tête) | `16/10/2026 19:05 UTC` | Paris : `16/10/2026 21:05` |
| `ui/chaine._journal` (lignes du journal de la Chaîne) | `HH:MM:SS` UTC | Paris (`formater_heure`) |
| `ui/agent.mention_repli` (date d'enregistrement) | date UTC | date de Paris |
| `rendu/commun.formater_horodatage` (traçabilité Excel et Annexe PowerPoint, « Horodatage d'extraction ») | `12/10/2026 07:05:09 UTC` | supprimée, remplacée par `contrats.format.formater_horodatage` : `12/10/2026 09:05:09` |
| `cli.configurer_console` (horodatage des journaux) | heure locale du poste, `AAAA-MM-JJ` | `FormateurJournal` : heure de Paris `JJ/MM/AAAA HH:MM:SS` quel que soit le poste |
| `rendu/commun.horodatage_fixe` (`docProps/core.xml`, horodatages zip) | minuit UTC de la Date d'arrêté | inchangé : métadonnées de fichier (W3CDTF en `Z`), pas un texte affiché ; garant du rejeu octet pour octet |
| `passage_id`, noms de répertoires, manifestes, JSONL, `empreinte_*`, entrepôt | UTC | inchangés (données) |
| Messages d'erreur citant un instant valide (`alignements` détection trop tôt, `journal` ordre des horodatages) | ISO 8601 UTC | heure de Paris + « (heure de Paris) » (revue) ; le numéro de ligne situe la donnée |
| Messages d'erreur citant un instant sans fuseau ou illisible (`repr`) | `repr` | inchangés : rien à convertir |
| Jour courant par défaut du `Classificateur` (suite d'évaluation) | date UTC | jour de Paris, `calendrier.jour_local` (revue) |
| Agent, narration, explication, prompts | aucune heure formatée | sans objet |

## Code Map

- `src/usine/contrats/format.py` -- `heure_de_paris` (naïf refusé), `formater_heure`, `formater_horodatage` (`secondes=False` pour `HH:MM`) ; `contrats/versions.py` 1.10.0.
- `src/usine/rendu/commun.py`, `src/usine/ui/vues.py`, `src/usine/ui/chaine.py`, `src/usine/ui/agent.py`, `src/usine/cli.py` -- appels au point unique.
- `src/usine/ui/agent.py` -- `est_hors_perimetre` (casse, ponctuation finale, guillemets droits, typographiques et français, espaces multiples et insécables) ; `src/usine/ui/ecrans.py` l'utilise.
- `demo/script-demo.md` (§ 3), `docs/tests-manuels.md` (§ 3.6 pastille, § 3.8 point 11).

## Rejeu et références

Le rejeu idempotent (Story 5.5) n'est pas affecté : l'horodatage d'extraction est dans `EXCLUSIONS_REJEU` et sa mise en forme reste déterministe ; les métadonnées fixes des fichiers ne changent pas. Références de test mises à jour à la nouvelle valeur exacte (pas d'affaiblissement) : `test_commun`, `test_excel`, `test_exclusions_rejeu` (07:05:09 UTC d'octobre → 09:05:09), `test_serveur` (19:05 → 21:05), `test_chaine` (07:30:00 → 09:30:00), `test_cli` (formateur vérifié en été et en hiver). Version 1.9.0 → 1.10.0 dans les tests de contrats.

## Tests

`test_format` (12/10/2026 22:12 UTC → 13/10/2026 00:12 ; 15/01/2026 22:12 UTC → 23:12 ; 31/12 → 01/01 ; autre fuseau ; naïf refusé ; pas de « UTC »), `test_cli` (journaux en heure de Paris), `test_agent_textes` (12 variantes acceptées, 5 phrases différentes refusées dont la phrase suivie d'un autre texte, badge de la vue, date de la mention de repli en été et en hiver).

## Reports

Aucun.

## Revue

Revue unique (Opus) du diff `8c43854..40e44ad`, avec la liste du second avis (Haiku).

- medium, second avis 1 : corrigé. `alignements` (détection avant la fin d'injection) et `journal` (horodatage décroissant) citent l'heure de Paris via `formater_horodatage`, suivie de « (heure de Paris) » ; tests sur la valeur littérale (`03/01/2000 01:00:00`). Les `date_injection` du `journal` sont des dates sans heure (restent ISO) ; les `repr` d'instants sans fuseau ou illisibles n'ont rien à convertir.
- medium, second avis 2 : corrigé (texte). `lancement.lancer_chaine` lance `Popen` sans nouveau groupe ni détachement : la Chaîne partage la console, Ctrl+C ou la fermeture du terminal l'arrêtent aussi. Le script de démo (§ 3) et les tests manuels (§ 3.8 point 11) l'écrivent désormais : aucun Passage publié, relancer après redémarrage, verrou à supprimer après une fermeture brutale. Mode de lancement inchangé (un détachement change le cycle de vie et le Job Object de `uv run` ; hors périmètre).
- medium, second avis 3 : corrigé en partie, le reste écarté. `chaine/cli` (défaut de `usine rapport`, donc de l'UI) et `generateur/cli` utilisent déjà `jour_local` (Paris). Seul `Classificateur.__call__` (`composition`, date tracée de la suite d'évaluation) prenait la date UTC : passé à `jour_local(_maintenant())`, test lundi 00:30 Paris (dimanche 22:30 UTC) → lundi. `passage_id` et horodatages restent en UTC (données).
- low, second avis 4 : écarté. La décision fixe « sans mention de fuseau » ; la pastille de l'UI n'en porte pas, l'Excel et le PowerPoint restent cohérents avec elle.
- low, second avis 5 : corrigé. Ponctuation finale retirée limitée à `.`, `!`, `…` ; « …répondre : », « ; », « , » refusés (tests).
- low, second avis 6 : corrigé. Forme NFC et retrait de U+200B, U+00AD, U+FEFF, U+2060 avant comparaison ; tests (NFD, BOM, trait d'union conditionnel, espace sans chasse).
- low, second avis 7 : corrigé. `test_configurer_console_ecrit_en_utf8` vérifie aussi que le formateur installé utilise `FORMAT_JOURNAL`.
- low, second avis 8 : écarté. Le journal de la Chaîne est un suivi en direct de quelques minutes, déjà ordonné ; la date n'y apporte rien.

Report : vérifier à la main (Windows, `uv run usine ui`) qu'un Ctrl+C pendant une vraie Chaîne arrête bien `python -m usine rapport` et rend le verrou (point 11 des tests manuels).
