# Journal de fin de jalon M3 : porte Palier 1

Date : 2026-10-13. Story 5.7. Contrats 1.6.0, `version_grille` `c344967e71de`.

La porte M3 vérifie que le Rapport quotidien est complet, exact et rejouable sans aucun LLM (Palier 1). La demande d'outillage reste ainsi recevable même si la banque refuse tout LLM. Toutes les exécutions réelles ont été faites depuis le dépôt principal (`donnees/`, secrets), en Palier 1, avec Jira en lecture seule.

## Critères et preuves

| Critère | Résultat | Preuve |
|---|---|---|
| CI verte | Vérifiée par l'orchestrateur | Sur le SHA de la Story 5.7 intégré à `main`, après push |
| Réconciliation à 100 % (FR-13, SM-1) | Conforme | `uv run pytest tests/unit/domaine/meteo/test_reconciliation.py` : 9 tests passés. KPI, Indicateurs et Météo du Rapport de référence égaux à `attendu.yaml` (calcul à la main), en égalité stricte |
| Rejeu idempotent | Conforme | `outils/verifier_rejeu.py --date 2026-10-09` : code 0 sur deux Passages composites réels (détail ci-dessous) |
| NFR-2 : moins de 5 minutes | Conforme | 5,4 s en synthétique (5 000 Anomalies) et 9,3 s sur `DEMO` (3 547 tickets, extraction incrémentale). Consigné dans le README, section « Performance (NFR-2) » |
| Journal de fin de jalon | Écrit | Ce document |

## Rejeu sur données réelles

Commandes, depuis le dépôt principal :

```
uv run usine rapport --date-arrete 2026-10-09
uv run python outils/verifier_rejeu.py --date 2026-10-09
```

L'outil compare les deux derniers Passages publiés de la date, fichier par fichier : tables Parquet, JSON et JSONL champ par champ, cellules et liens de l'Excel, textes des slides. Le test `tests/unit/chaine/test_rejeu.py` utilise la même comparaison, avec les mêmes différences attendues.

Passages comparés : `20261012T223154Z-8a7542` et `20261012T223234Z-d4f585`. Tous deux sont en source `composite`, en Palier 1, avec 3 547 tickets. Les 16 différences observées sont toutes dans `EXCLUSIONS_REJEU` :

- `manifeste` : `passage_id`, `horodatage_debut`, `horodatage_fin`, `horodatage_extraction`, `version_donnees`, `etapes[].horodatage_debut`, `etapes[].horodatage_fin` ;
- `meteo`, `previsions` : `passage_id` ;
- `trace_previsions` : `horodatage`, `passage_id`, `version_donnees` ;
- `rapport_xlsx` : `Traçabilité!B5`, `Traçabilité!B8` ;
- `rapport_pptx` : `Annexe méthode!Horodatage d'extraction`, `Annexe méthode!Version des données`.

Les tables Parquet, la Météo, les Prévisions, et toutes les autres cellules et slides sont identiques.

**Constat : `nb_alignements`.** Le premier essai comparait `20261012T222702Z-ec5fab` (Story 5.6, premier Passage après la réinjection de `DEMO`) à `20261012T223154Z-8a7542`. Il a échoué (code 1) sur un seul champ : `manifeste : nb_alignements` (20 014 contre 0). Ce champ compte les alignements *nouvellement* persistés par le Passage (AD-4, « Jira fait foi »). Il vaut donc le total au premier Passage sur un entrepôt neuf, puis 0. Toutes les données du Passage étaient identiques ; seul l'état de l'entrepôt différait. Le Rejeu est conforme dès que l'entrepôt est stable, ce qui est le cas des deux Passages retenus ci-dessus. `EXCLUSIONS_REJEU` n'a pas été modifié (contrats gelés). Deux voies possibles, à trancher hors de cette story :
- ajouter `nb_alignements` aux exclusions du manifeste, par une PR de contrats mineure ;
- ou garder la règle actuelle : le Rejeu se compare entrepôt stable.

## Performance (NFR-2)

Poste : AMD Ryzen 5 7600 (6 cœurs), 32 Go de RAM, Windows 11, Python 3.12.14. Toutes les étapes déterministes sont réelles : les bouchons de la mesure de la Story 1.3 ont disparu.

| Mesure | Volumétrie | Durée |
|---|---|---|
| Synthétique, `outils/mesurer_nfr2.py` | 10 Entités, 5 000 Anomalies, 8 semaines, 5 036 tickets | 5,39 s (Chaîne) |
| `DEMO`, extraction incrémentale | 10 Entités, 3 547 tickets | 9,3 s (commande de bout en bout, dont 1,5 s d'extraction) |
| `DEMO`, extraction complète (Story 5.6) | 10 Entités, 3 547 tickets | 22,9 s (commande, dont 15 s d'extraction) |

L'étape la plus lente est `meteo`, avec environ 3 s. La marge par rapport aux 300 s de la cible est supérieure à un facteur 10.

## Avance de l'Epic 6

L'orchestrateur a décidé de démarrer l'Epic 6 avant la porte. Les Stories 6.1 à 6.7 sont `done`, commits `f6a9ec5` à `16584cc` (voir `_bmad-output/implementation-artifacts/journal-run-autonome.md`). Cette avance ne dépend d'aucune sortie du Palier 1 validée par cette porte :
- les étapes LLM s'appuient sur les contrats (1.3 à 1.6, tous additifs) et sur des fixtures ;
- elles ne modifient ni `rendu/` ni les étapes déterministes ;
- elles restent `sautee` en Palier 1, comme le montrent les Passages de cette porte.

La Story 6.8 (suite d'évaluation de l'explication sourcée, sur fixtures) a été intégrée en parallèle de cette porte, sur le même principe. Les Stories 6.9 à 6.13 restent en backlog ; la 6.10 (recette Palier 2) part de ce Palier 1 validé.

## Arbitrages en attente d'Anaël

Ils ne bloquent pas la porte, mais ils sont consignés ici. Aucun n'a été tranché.

- **SM-10** : la Baseline bat la référence naïve sur le test temporel (Brier 0,011922 contre 0,013638). Elle perd en revanche sur les projets tenus à l'écart (0,047625 contre 0,045207, soit un écart de 0,0024). Voir `evaluation/zenodo/RAPPORT.md`. Le résultat est publié tel quel et la Baseline n'a pas été retouchée.
- **AD-16** : `version_donnees` inclut le manifeste d'injection (Story 2.6). C'est un écart à la lettre du Glossaire, qui prévoit « SHA-256 du Journal + `horodatage_extraction` ».
- **Nouveau, Rejeu** : `nb_alignements` au manifeste (voir plus haut).

## Clôture par l'orchestrateur (13/10/2026)

- CI GitHub verte (Ubuntu et Windows) sur `b00c5d7`, poussé le 13/10 : la porte M3 est passée.
- Rejeu entre le premier Passage après réinjection (`ec5fab`) et le suivant : écart sur `manifeste.nb_alignements` (20 014 contre 0). Décision technique : on garde la règle « Rejeu sur entrepôt stable ». Le premier Passage après une réinjection construit l'entrepôt et n'entre donc pas dans le Rejeu. Les contrats ne changent pas.
