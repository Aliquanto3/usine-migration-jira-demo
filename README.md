# Copilote de pilotage d'une usine de migration

Démonstrateur personnel : automatiser le reporting d'une usine de migration de SI à partir de Jira (ETL, KPI, météo calculée par règles, Excel et PowerPoint générés), puis l'enrichir par un LLM (explication sourcée des météos rouges, prévision de sortie du rouge narrée, agent conversationnel en lecture seule).

Toutes les données sont **fictives ou publiques**. Aucun nom, libellé, gabarit ni règle d'une organisation réelle.

- Spécification : [`SPEC-usine-migration-jira-demo.md`](SPEC-usine-migration-jira-demo.md)
- Artefacts de conception (méthode BMAD) : `_bmad-output/`

Projet en cours de cadrage. Licence MIT.

## Performance (NFR-2)

Mesure de `usine rapport` en Palier 1 sur un Journal synthétique à la volumétrie cible : 10 Entités, 5 000 Anomalies, 8 semaines (63 781 événements, 5 032 tickets ; Journal généré en 0,9 s), Date d'arrêté 2026-10-09. Commande : `uv run python outils/mesurer_nfr2.py` (graine 42, date de génération 2026-10-12, répertoire temporaire).

Poste : AMD Ryzen 5 7600 (6 cœurs), 32 Go de RAM, Windows 11, Python 3.12.14. Mesure du 2026-10-12 (Story 1.3, cycle de vie des Anomalies selon le workflow H-17).

| Étape | Statut | Durée (s) |
|-------|--------|----------:|
| extraction | bouchon (reussie) | 0,00 |
| instantanes | reussie | 0,64 |
| kpi | bouchon (reussie) | 0,00 |
| meteo | reussie | 0,10 |
| prevision | bouchon (reussie) | 0,00 |
| classification | sautee | 0,00 |
| repartition_causes | sautee | 0,00 |
| explications | sautee | 0,00 |
| narration | sautee | 0,00 |
| rendu | reussie | 0,05 |
| **Total de la commande** (lecture du Journal comprise) | | **1,27** |

Aucun écart à la cible de 5 minutes. Les étapes `extraction`, `kpi` et `prevision` ne sont encore que des bouchons : la mesure est à refaire quand les lanes les livrent. 5 000 Anomalies est un majorant de charge : la configuration livrée en génère 3 000 à 3 600 (8 semaines × 500 Entrées au plus, moins la marge de réouvertures).
