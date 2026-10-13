# Suite d'évaluation de la classification des Causes racines (SM-9)

Mesure la classification des Anomalies par Cause racine. Cible SM-9 : **F1 macro ≥ 0,8** sur
la vérité terrain du générateur et, séparément, sur 30 tickets rédigés à la main.

## Contenu

- `tickets_manuels.json` : les 30 tickets rédigés à la main (`EVAL-1` … `EVAL-30`). Chacun
  porte son domaine (repris comme Entité), son titre, sa description, la Cause racine attendue
  (`cause_attendue`) et la réponse enregistrée du fournisseur (`reponse`), rejouée hors
  réseau. Les sept Causes racines sont couvertes (4 ou 5 tickets chacune), sur six domaines ;
  quatre réponses enregistrées sont des erreurs réalistes (doublon de chargement pris pour un
  faux positif, environnement pris pour une règle de calcul…).
- `tickets.py` : chargement des tickets manuels et de la source générateur (Journal et vérité
  terrain d'un répertoire de données). Seule cette suite lit `verite_terrain.json` (AD-23).
- `metriques.py` : précision, rappel et F1 par Cause racine, F1 macro, exactitude, matrice de
  confusion (fonction pure `evaluer`).
- `suite.py` : exécution (`executer_suite`), résultat, historique.
- `resultats/<horodatage>.json` : un fichier par exécution.
- `historique.jsonl` : une ligne par exécution réelle.

## Métriques

Pour chaque Cause racine : précision = VP ÷ (VP + FP), rappel = VP ÷ (VP + FN),
F1 = 2·P·R ÷ (P + R), chacun à 0 si son dénominateur est nul. Le **F1 macro** est la moyenne
des F1 des Causes racines présentes dans la vérité ou dans les propositions. Une Anomalie non
classée (plafond de coût atteint) compte comme fausse et figure dans `non_classes`.
`sm9_atteint` vaut vrai quand les deux F1 macro sont ≥ 0,8, `null` si une source manque.

## Protocole

1. **Tickets manuels, hors réseau.** `uv run python -m evals.classification executer` passe
   les 30 tickets par la vraie tâche `classer`, passerelle comprise (cache en mémoire), avec
   les réponses enregistrées. C'est ce que teste la CI.
2. **Journal du Corpus définitif.** La source générateur exige un Journal généré avec le
   Corpus de textes versionné (`donnees/corpus/textes.json`), non provisoire : l'en-tête du
   Journal doit porter les mêmes `version_corpus` et `modele_corpus`. Le générer dans un
   répertoire à part pour ne pas toucher `donnees/` :

   ```sh
   uv run usine donnees generer --sortie <répertoire>
   ```

3. **Exécution réelle (réseau, coût).**

   ```sh
   uv run python -m evals.classification executer --reel --donnees <répertoire>
   ```

   Lit `config/llm.yaml` (modèle de la tâche `classification`, plafond de coût), la clé du
   fournisseur et `USINE_CLE_PSEUDO`, comme un Passage Palier 2 ; le cache de production
   n'est ni lu ni écrit (la table de pseudonymes `donnees/pseudonymes.sqlite` l'est, comme en
   Passage). Garde-fou AD-19 : le modèle de classification doit différer du `modele_corpus`
   du Journal, sinon la commande s'arrête avant tout appel. Le résultat publie le F1 macro de
   chaque source, `modele_corpus`, `modele_classification` et `sm9_atteint` ; une ligne est
   ajoutée à `historique.jsonl`. Un échec isolé du fournisseur (réponse hors schéma, par
   exemple) laisse l'Anomalie non classée, comptée fausse et listée dans
   `erreurs_fournisseur` ; 10 échecs d'affilée arrêtent la commande.
4. **Rejeu d'un run réel, hors réseau.** Les `propositions` de la source générateur d'un
   résultat antérieur servent de réponses enregistrées :

   ```sh
   uv run python -m evals.classification executer --donnees <répertoire> \
     --reponses evals/classification/resultats/<horodatage>.json
   ```

   Une Anomalie sans réponse dans ce résultat arrête la commande en la nommant.

Options : `--source manuels|generateur|toutes` (défaut : `toutes` avec `--reel` ou
`--reponses`, sinon `manuels`), `--sortie` (répertoire des résultats), `--historique`.

## Coût estimé du mode réel

Haiku 5.5 (0,1 $ / 0,5 $ par million de jetons d'entrée / de sortie, 50 requêtes/min) :
environ 3 150 appels de ~700 jetons d'entrée et ~100 de sortie, soit **~0,40 $ (~0,35 €)**
pour la source générateur ; les 30 tickets manuels sont négligeables. Durée bornée par le
quota : **environ 65 min**.
