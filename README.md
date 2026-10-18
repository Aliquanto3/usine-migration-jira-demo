# Copilote de pilotage d'une usine de migration

Démonstrateur personnel : automatiser le reporting d'une usine de migration de SI à partir de Jira (ETL, KPI, météo calculée par règles, Excel et PowerPoint générés), puis l'enrichir par un LLM (explication sourcée des météos rouges, prévision de sortie du rouge narrée, agent conversationnel en lecture seule).

![Aperçu d'une version précédente de l'interface : carte météo des Entités, détail de ENT-A avec sa prévision de sortie du rouge, gain de temps avant / après, puis réponse contrôlée de l'Agent](docs/media/demo-ui.gif)

*Aperçu d'une version précédente de l'interface de démo, à réenregistrer sur l'interface web actuelle (`uv run usine ui`, Story 7.12). Ce qu'il montre en 30 secondes : la météo de chaque Entité calculée par règles depuis Jira, le détail d'une Entité rouge (tickets en cause, KPI, prévision de sortie du rouge), le temps du reporting manuel face à celui de la Chaîne, puis l'Agent dont chaque chiffre et chaque ticket cité est vérifié. Enregistrée en Mode repli, sur le Passage fictif de `demo/repli/`. Vidéo source : [`docs/media/demo-ui.mp4`](docs/media/demo-ui.mp4).*

Toutes les données sont **fictives ou publiques**. Aucun nom, libellé, gabarit ni règle d'une organisation réelle.

- Spécification : [`SPEC-usine-migration-jira-demo.md`](SPEC-usine-migration-jira-demo.md)
- Artefacts de conception (méthode BMAD) : `_bmad-output/`

Version 0.10.1 : chaîne de reporting utilisable et testée (CI verte), exécutée sur le projet Jira Cloud `DEMO`, avec une interface web locale (FastAPI + HTML statique) ; les dernières stories sont en cours. Licence MIT.

## Performance (NFR-2)

Cible : un Passage `usine rapport` en Palier 1 en moins de 5 minutes à la volumétrie cible (3 000 à 5 000 Anomalies, 10 Entités), extraction incrémentale comprise. Mesures du 2026-10-13 (porte M3, Story 5.7), toutes les étapes déterministes réelles.

Poste : AMD Ryzen 5 7600 (6 cœurs), 32 Go de RAM, Windows 11 (10.0.26300), Python 3.12.14.

**Synthétique** : `uv run python outils/mesurer_nfr2.py` (graine 42, date de génération 2026-10-12, répertoire temporaire). Journal de 10 Entités, 5 000 Anomalies, 8 semaines (63 817 événements, 5 036 tickets ; généré en 1,1 s), Date d'arrêté 2026-10-09.

**Réel sur `DEMO`** : `uv run usine rapport --date-arrete 2026-10-09` depuis le dépôt principal, source composite (Journal + Jira Cloud `DEMO` en lecture seule), extraction incrémentale sur l'entrepôt existant. 3 547 tickets, 10 Entités (Passage `20261012T223234Z-d4f585`).

| Étape | Synthétique (s) | `DEMO` (s) |
|-------|----------------:|-----------:|
| extraction | 0,00 | 1,51 |
| instantanes | 0,66 | 0,68 |
| kpi | 0,08 | 0,07 |
| meteo | 3,06 | 3,01 |
| prevision | 0,73 | 0,68 |
| classification, repartition_causes, explications, narration | sautées | sautées |
| rendu | 0,35 | 0,26 |
| **Total** (synthétique : `lancer_rapport` ; `DEMO` : `uv run usine rapport` de bout en bout) | **5,39** | **9,3** |

Les deux mesures sont très loin de la cible de 300 s. En source synthétique, l'étape `extraction` ne fait que lire le Journal. Sur `DEMO`, le premier Passage après réinjection (extraction complète, 20 014 alignements persistés) a pris 22,9 s pour la commande, dont 15 s d'extraction (Story 5.6) ; les Passages suivants, incrémentaux, prennent 9 à 10 s.
