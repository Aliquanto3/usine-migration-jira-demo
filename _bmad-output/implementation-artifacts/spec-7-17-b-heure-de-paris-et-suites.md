---
title: "Story 7.17-b : Heure de Paris à l'affichage, badge hors périmètre robuste, reprise de Chaîne"
type: 'feature'
created: '2026-10-18'
status: 'review'
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
| Messages d'erreur citant un instant brut (`alignements`, `journal`, `entrepot`, `contrats.passage`) | ISO 8601 avec décalage, ou `repr` | inchangés : citation de la donnée fautive, non ambiguë |
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
