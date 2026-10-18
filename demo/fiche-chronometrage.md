# Fiche de chronométrage des répétitions (Story 7.12)

À imprimer ou à ouvrir à côté du chrono. Script suivi : [`script-demo.md`](script-demo.md) ;
résultats consolidés : [`repetitions.md`](repetitions.md) (critère SM-5 : 3 répétitions de
10 minutes au plus, dont une en Mode repli, sans intervention hors script).

## 1. Tests manuels encore ouverts (`docs/tests-manuels.md`)

Aucune section « Résultats » n'est consignée dans `docs/tests-manuels.md` (état au 18/10/2026) :
tous les tests ci-dessous sont **non joués**. Ceux de la démo d'abord.

| Section | Objet | À jouer par un humain |
|---|---|---|
| 3.4 | Mode repli (lecture seule) | bandeau permanent, lancement désactivé |
| 3.5 | Interface de démo | carte, détail, Avant / après s'affichent |
| 3.6 | Cadre de l'interface web (7.13) | points 2 (clavier), 3 (hors réseau), 5 (serveur arrêté), 6 (320 px, zoom 200 %), 7 (`--port`) ; 1 et 4 sont couverts en partie par le contrôle ci-dessous |
| 3.7 | Carte, détail, livrables (7.14) | points 1 à 9, dont ouverture des deux livrables dans Excel et PowerPoint (9) |
| 3.8 | Lancement de la Chaîne et mode (7.15) | points 1 à 7 sans Jira ; 8 (vraie Chaîne) et 9 (échec) pour Anaël |
| 3.9 | Agent, Avant / après, Pseudonymisation, Outillage (7.16) | points 1, 2, 4 à 7 sans coût ; 3 (vraie question LLM, quelques centimes) pour Anaël |
| 3.1 | Rapport de bout en bout (Palier 1) | commande et ouverture des fichiers |
| 3.2 | Balayage SM-7 des traces | code de sortie 0 attendu (un 1 est bloquant) |
| 3.3 | Préchauffage du cache | appelle le LLM réel (environ 1 € de budget) : à ne jouer que sur décision |

## 2. Avant chaque répétition

```powershell
uv run python outils/verifier_demo.py          # données de la copie du Mode repli (code 0)
uv run python outils/controle_repetition.py    # sept écrans dans Edge + livrables (code 0)
```

Le second lance `usine ui` en Mode repli sur un port libre, charge les sept écrans dans Edge sans
fenêtre (ni « Chargement… », ni bandeau d'erreur, contenu affiché), puis télécharge les deux
livrables du Passage de repli. Il se lance à la racine du dépôt principal (le `.env` porte
`USINE_CLE_PSEUDO`, sinon l'écran Pseudonymisation sort en `[KO]`). Codes : 0 prêt, 1 écran ou
livrable en échec, 2 contrôle impossible (Edge introuvable, serveur muet). Durée : environ 20 s.
Il ne remplace pas la répétition : il ne vérifie ni le contenu des chiffres ni le temps de parole.

## 3. Chronométrage

Remplir les colonnes avec l'heure du chrono à la **fin** de chaque séquence (m:ss).
Répétition en Mode repli : **R__** (entourer une des trois). Date et heure : R1 ______ ;
R2 ______ ; R3 ______.

| # | Séquence | Durée cible | Cumul cible | R1 | R2 | R3 |
|---|---|---|---|---|---|---|
| 1 | Ouverture (Carte météo) | 0:30 | 0:30 |  |  |  |
| 2 | Avant / après | 1:00 | 1:30 |  |  |  |
| 3 | Lancement de la Chaîne | 1:15 | 2:45 |  |  |  |
| 4 | Carte météo, Scénarios A, B, C | 1:00 | 3:45 |  |  |  |
| 5 | Détail de ENT-A, Prévision | 1:15 | 5:00 |  |  |  |
| 6 | ENT-B et ENT-C | 1:00 | 6:00 |  |  |  |
| 7 | Explication sourcée et Paliers | 0:30 | 6:30 |  |  |  |
| 8 | Pseudonymisation | 0:45 | 7:15 |  |  |  |
| 9 | Agent | 1:15 | 8:30 |  |  |  |
| 10 | Ce qu'il faut pour le faire en vrai | 0:45 | 9:15 |  |  |  |
| 11 | Conclusion | 0:25 | 9:40 |  |  |  |
| | **Total** (10:00 au plus) | 9:40 | 9:40 |  |  |  |
| | **Incidents** (séquence, nature) | | |  |  |  |
| | **Interventions hors script** (séquence, geste) | | |  |  |  |

Séquence qui déborde de plus de 15 s : raccourcir sa phrase dans `script-demo.md`. Reporter
ensuite date, durée, mode, incidents et interventions dans `repetitions.md`.
