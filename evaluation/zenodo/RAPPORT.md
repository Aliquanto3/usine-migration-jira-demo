# Rapport d'évaluation : Baseline sur le Public Jira Dataset (FR-51, SM-10)

Évaluation du 2026-10-12. Mesures agrégées : [`resultats/evaluation.json`](resultats/evaluation.json),
produites par :

```bash
uv run python -m evaluation.zenodo.evaluation --series ../externe/series/*.parquet \
  --sortie evaluation/zenodo/resultats/evaluation.json
```

Hors CI (AD-20). Les `SerieStock` d'entrée viennent de la Story 4.3 (voir [`README.md`](README.md))
et restent hors du dépôt ; seuls des agrégats y sont publiés. Entrées de ce run : dataset
Zenodo version 2025-06-23 (DOI `10.5281/zenodo.15719919`) ; cinq Parquet produits par
`evaluation.zenodo.chargement` sans `--fin`, avec la priorité par défaut pour Spring et
Hyperledger, `--priorite "1 - Blocker"` (JFrog), `--priorite P1-Urgent` (IntelDAOS) et
`--priorite Showstopper` (SecondLife). Le joker `*.parquet` suppose Git Bash ; sous
PowerShell, lister les cinq fichiers.

## Verdict SM-10

| Jeu de test | Brier Baseline | Brier naïve | Baseline meilleure ? |
|---|---|---|---|
| Test temporel (périodes récentes) | **0,011922** | 0,013638 | oui |
| Projets tenus à l'écart | 0,047625 | **0,045207** | **non** |

La Baseline bat la référence naïve en score de Brier sur le test temporel, mais pas sur les
projets tenus à l'écart (écart de 0,0024). Conformément à SM-10, **le résultat est publié tel
quel et l'écart est signalé à l'auteur pour arbitrage** ; la Baseline n'a pas été retouchée.

## Protocole

Addendum PRD § E et hypothèse H-21 (référence naïve = taux historique de sortie sous N jours,
critère = score de Brier), avec les valeurs par défaut suivantes :

- **Baseline** : l'unique implémentation `usine.domaine.prevision.baseline.prevoir_sortie`,
  appelée telle quelle avec `ParametresBaseline()` (vélocité sur 10 Jours ouvrés, horizon 10,
  fenêtres de 5 sur 20) (AD-18). Pour chaque unité, une Météo rouge synthétique porte la seule
  règle IND-1 `>= 3`.
- **Séries** : stock de tickets de priorité maximale ouverts par projet et par Jour ouvré.
  Chaque série est prolongée jusqu'à la dernière date de son dépôt (stock constant).
- **Unité** : (projet, premier Jour ouvré de chaque semaine ISO) où le stock est d'au moins 3
  (seuil rouge IND-1 de la Grille par défaut), avec au moins 20 Jours ouvrés d'historique et
  les 10 Jours ouvrés suivants observés.
- **Cible** : le stock passe sous 3 à au moins un des 10 Jours ouvrés suivants.
- **Prédicteurs** : Baseline = probabilité de la `Prevision` (part des fenêtres de vélocité
  historiques qui ramènent le stock sous le seuil dans l'horizon) ; naïve = taux de la cible
  sur les unités d'entraînement du projet, ou taux global d'entraînement à défaut (toujours le
  cas des projets tenus à l'écart).
- **Découpage** : projets tenus à l'écart = SHA-256 du nom de série ≡ 0 mod 4 (toutes leurs
  unités forment le second test) ; pour les autres, coupure par dépôt au 70ᵉ centile (rang le
  plus proche) des dates d'unités ; entraînement = unités dont la cible se termine avant la
  coupure (les unités qui la chevauchent sont purgées) ; test temporel = unités à partir de la
  coupure.
- **Mesures** : score de Brier, AUC (Mann-Whitney, ex aequo comptés 1/2) et erreur absolue
  moyenne du stock à 10 Jours ouvrés, calculés en fractions exactes puis arrondis à 6
  décimales. Stock projeté : Baseline = max(0, S − v·10), v étant le facteur vélocité nette de
  la `Prevision` ; naïve = persistance du stock courant.

## Données

| Dépôt | Séries | dont tenues à l'écart | Unités | Coupure |
|---|---|---|---|---|
| Hyperledger | 24 | 8 | 775 | 2019-09-30 |
| IntelDAOS | 2 | 1 | 162 | 2020-07-27 |
| JFrog | 7 | 3 | 1 437 | 2019-01-28 |
| SecondLife | 2 | 1 | 22 | 2011-10-03 |
| Spring | 58 | 20 | 2 761 | 2019-06-03 |
| **Total** | **93** | **33** | **5 157** | |

Entraînement : 2 743 unités, 107 positives (taux 3,90 %).

## Résultats

| Jeu (effectif, positives, séries) | Prédicteur | Brier | AUC | Erreur absolue moyenne du stock |
|---|---|---|---|---|
| Test temporel (1 191, 15, 15) | Baseline | 0,011922 | 0,657653 | 0,498741 |
| | Naïve | 0,013638 | 0,400879 | 0,342569 |
| Projets tenus à l'écart (1 203, 57, 10) | Baseline | 0,047625 | 0,637657 | 1,281796 |
| | Naïve | 0,045207 | 0,500000 | 0,842062 |

## Lecture

- **Classement** : la Baseline sépare mieux les unités qui sortent de celles qui restent
  (AUC 0,66 et 0,64 contre 0,40 et 0,50) ; la naïve d'un projet tenu à l'écart est une
  constante, d'où son AUC de 0,5.
- **Calibrage** : l'événement est rare (1,3 % et 4,7 % de positives). Une naïve proche de ce
  taux de base obtient mécaniquement un bon Brier ; la Baseline, empirique et sans calibrage,
  peut donner des probabilités élevées (fenêtres de forte vélocité), probable cause de son Brier
  plus élevé sur les projets inconnus (hypothèse non vérifiée unité par unité).
- **Stock projeté** : la persistance bat la projection linéaire S − v·10 (0,34 contre 0,50 et
  0,84 contre 1,28) ; la vélocité de 10 Jours ouvrés extrapole des variations qui ne durent pas.

## Limites

- **Prolongation des séries** : une série est prolongée jusqu'à la dernière date de son
  dépôt, stock constant. C'est fidèle à l'historique (aucun événement, donc aucun mouvement),
  mais un projet laissé à l'abandon avec 3 tickets ouverts ou plus fournit des unités
  toujours négatives, surtout après la coupure : cela explique sans doute une partie de
  l'écart de taux de positives entre entraînement (3,9 %) et test temporel (1,3 %) et
  avantage la persistance du stock. La part de ces unités n'est pas mesurée.
- **Incertitude** : sans intervalle de confiance, l'écart de Brier sur les projets tenus à
  l'écart (0,0024, 57 positives sur 10 séries) n'est pas départagé statistiquement.
- Cinq dépôts sur seize (les plus petits restaurés au spike de la 4.3) ; Apache, Mojang,
  RedHat… ne sont pas couverts.
- Noms de priorité maximale propres à chaque instance (`Blocker`, `Highest`, `1 - Blocker`,
  `P1-Urgent`, `Showstopper`) ; seuil de 3 tickets commun à tous les projets, quelle que soit
  leur taille.
- Unités hebdomadaires d'un même projet corrélées entre elles ; aucun intervalle de confiance
  n'est publié.
- Limites de conversion de la 4.3 (fuseau Europe/Paris, projet courant, changelogs tronqués).

## Arbitrage demandé à l'auteur (SM-10)

SM-10 n'est atteint que sur le test temporel. Options, sans modifier la Baseline pour la seule
évaluation : accepter le résultat en l'état (meilleur classement, Brier comparable), étendre
l'évaluation à d'autres dépôts, ou confier l'amélioration du calibrage au Modèle ML (Story 4.6).
