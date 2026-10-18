---
title: "Story 7.12 : Répétitions chronométrées de la démo"
type: 'feature'
created: '2026-10-13'
status: 'review'
baseline_revision: '319a7c8'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: ['la copie du Mode repli et le dernier Passage DEMO sont en Palier 1 : pas d Explication sourcée ni de sélecteur de Palier à l écran tant que la Story 6.10 n a pas publié de Passage Palier 2']
deferred: ['3 répétitions chronométrées, dont une en Mode repli, à faire et consigner par Anaël dans `demo/repetitions.md` (SM-5)', 'clé `DEMO-n` du ticket de l écran Pseudonymisation en mode normal, à repérer la veille']
---

<intent-contract>

## Intent

**Problem:** SM-5 exige 3 répétitions chronométrées de 10 minutes au plus, dont une en Mode repli, sans intervention hors script. Il n'existe ni script minuté, ni gabarit de consignation, ni moyen de savoir avant une répétition si un écran arrivera vide.

**Approach:** un script minuté écran par écran (`demo/script-demo.md`, UJ-4), avec plan B en Mode repli pour chaque séquence ; un gabarit de consignation (`demo/repetitions.md`) ; un outil `outils/verifier_demo.py` qui charge la copie du Mode repli sans réseau, vérifie séquence par séquence que chaque écran a ses données, chronomètre les lectures et rend 0 ou 1. Les répétitions elles-mêmes restent à faire par Anaël.

## Boundaries & Constraints

**Always:** lecture du Passage par le port `Consultation` (`composition.consultation_repertoire`, même lecteur que `ui/cli.consultation_repli`) ; aucun réseau ni LLM ; chiffres du script limités aux valeurs mesurées (Stories 5.6, 5.7, copie de repli) ; textes en français.

**Never:** importer `usine.ui` ou `usine.ia` depuis `outils` (contrat « hors produit ») ; modifier `contrats/`, `ports/` ou l'UI ; afficher la clé ou les textes pseudonymisés ; appel LLM réel ou écriture Jira.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Déroulé complet | copie de repli, réponses, `config/demo.yaml`, fiche, `USINE_CLE_PSEUDO` | 9 lignes `[OK]`, « déroulé complet », code 0 | — |
| Copie absente | pas de `demo/repli/passage/manifeste.json` | séquence 0 `[KO]`, arrêt | code 1 |
| Météo inattendue | A, B non rouges ou C non orange | séquence 2 `[KO]` qui nomme l'écart | code 1 |
| Palier 1 | copie Palier 1 (cas actuel) | séquence 5 `[OK]` : message « commentaire non généré (Palier 1) » attendu | — |
| Palier 2 | copie Palier 2 | Explications A et B, narration A, filtre Palier 1 vide exigés | code 1 sinon |
| Réponse d'un autre Passage | `passage_id` différent dans `demo/repli/agent/*.json` | séquence 7 `[KO]` qui nomme le fichier | code 1 |
| Clé de pseudonymisation absente | `USINE_CLE_PSEUDO` absente | séquence 6 `[KO]` qui nomme la variable | code 1 |

</intent-contract>

## Code Map

- `src/usine/ui/navigation.py` -- libellés exacts des 7 écrans, repris par le script.
- `src/usine/ui/app.py` -- bascule « Mode repli », bouton « Lancer la Chaîne », « Détail ENT-x », « Palier affiché », « Question enregistrée » / « Rejouer la réponse ».
- `src/usine/ui/cli.py` -- `REPERTOIRE_REPLI`, `consultation_repli`, `reponses_repli` (alignés par le test).
- `src/usine/composition.py:618` -- `consultation_repertoire`, `apercu_pseudonymisation` (autorisés pour `outils`).
- `demo/repli/` -- copie `20261012T221158Z-96c621` (Palier 1) et 5 réponses de l'Agent (Story 7.11).

## Tasks & Acceptance

**Execution:**
- `demo/script-demo.md` -- préparation (veille, 15 min avant, bascule), 11 séquences minutées (durée cible, écran, clic, phrases, plan B), chiffres de référence ; 9 min 40 s prévues.
- `demo/repetitions.md` -- critère SM-5 en tête, définition de l'intervention hors script, tableau à 3 lignes vides.
- `outils/verifier_demo.py` -- 9 contrôles chronométrés dans l'ordre du script, compte rendu, code 0 / 1.
- `tests/unit/outils/test_verifier_demo.py` -- matrice ci-dessus ; constantes et chargement des réponses alignés sur l'UI.

**Acceptance Criteria:**
- Given le script de la démo (UJ-4) dans `demo/`, when l'auteur réalise les répétitions, then au moins 3 répétitions durent 10 minutes au plus, dont une en Mode repli, sans intervention hors script. **En attente : répétitions d'Anaël.**
- And chaque répétition est consignée (date, durée, mode, incidents) dans `demo/repetitions.md`. **Gabarit livré, lignes vides.**

## Design Notes

`outils` n'a pas le droit d'importer `usine.ui` ni `usine.ia` : l'outil passe par `composition.consultation_repertoire` (le lecteur de `consultation_repli`) et relit les `ReponseAgentEnregistree` avec la même règle que `ia/agent/repli.charger_reponses`. Le test vérifie que les deux chargements rendent les mêmes réponses et que les chemins et le message Palier 1 sont ceux de l'UI : une divergence casse le test.

La séquence Pseudonymisation prend environ 4 s : construction du moteur à chaque appel. L'UI ne le met pas en cache, donc chaque changement de ticket à l'écran coûte autant. Le script demande de préchauffer l'écran et de ne choisir le ticket qu'une fois.

Le chronométrage porte sur les lectures de données, pas sur le rendu Streamlit : il ne remplace pas une répétition.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- vert (2797 passés, 1 sauté)
- `uv run python outils/verifier_demo.py` (racine du dépôt principal, qui porte `.env`) -- code 0

**Compte rendu (2026-10-13, `--racine` du dépôt principal) :**

```
Vérification du déroulé de la démo (Mode repli, sans réseau)
  [OK] 0. Chargement du Passage de repli (0 ms) : Passage 20261012T221158Z-96c621, arrêté au 09/10/2026, Palier 1, 3547 tickets
  [OK] 1. Avant / après (0 ms) : manuel 120 min contre 4.4 s mesurées (Passage de repli)
  [OK] 2. Carte météo (4 ms) : 10 Entités ; rouges : ENT-A, ENT-B ; ENT-C orange
  [OK] 3. Détail A, B, C (5 ms) : Règle principale ENT-A : IND-1, ENT-B : IND-1, ENT-C : IND-4
  [OK] 4. Prévision et narration (2 ms) : ENT-A sortie estimée le 13/10/2026 (8/16) ; ENT-B pas_de_sortie_projetee ; Risque ENT-C présent ; pas de narration (Palier 1)
  [OK] 5. Explication sourcée (0 ms) : Palier 1 : bloc Explication « commentaire non généré (Palier 1) », pas de sélecteur de Palier
  [OK] 6. Pseudonymisation (3826 ms) : 3547 descriptions ; la n° 4 change à la pseudonymisation
  [OK] 7. Agent (réponses enregistrées) (1 ms) : 5 réponses conformes sur 20261012T221158Z-96c621
  [OK] 8. Ce qu'il faut pour le faire en vrai (0 ms) : docs/fiche-outillage.md présente
Bilan : déroulé complet ; lectures en 3838 ms au total.
```

Depuis le worktree de lane (sans `.env`), seule la séquence 6 est `[KO]` (`USINE_CLE_PSEUDO` absente) : c'est le comportement attendu.

## Préparation outillée (18/10/2026)

- `outils/controle_repetition.py` : lance `usine ui` en Mode repli (port libre, 127.0.0.1), charge les sept écrans dans Edge sans fenêtre (`--dump-dom`, temps virtuel 5 s), exige ni « Chargement… » ni bandeau d'erreur visible et un bloc principal affiché, puis télécharge les livrables du Passage de repli (200, attachment, corps non vide). Code 0 / 1 ; 2 si Edge est introuvable ou le serveur muet ; serveur arrêté dans un `finally`. Complète `verifier_demo.py`, qu'il ne duplique pas.
- Tests : `tests/unit/outils/test_controle_repetition.py` (DOM, recherche d'Edge, livrables, rapport, arrêt du serveur) ; un test `lent` lance le contrôle réel.
- `demo/fiche-chronometrage.md` : tests manuels ouverts (aucun résultat consigné), commande de contrôle, tableau des 11 séquences pour R1 à R3. Lien depuis `repetitions.md`.
- Exécution réelle (poste d'Anaël, racine du dépôt principal) : 7 écrans et 2 livrables `[OK]`, code 0 (environ 20 s). Depuis un worktree sans `.env`, seul Pseudonymisation sort en `[KO]` (`USINE_CLE_PSEUDO` absente).
- Revue (Opus, avec second avis Haiku) : (1) medium, arrêt du serveur sous Windows : non reproduit (aucun processus ni port restant après l'exécution réelle), durci quand même par `taskkill /T /F` ; (2) medium, carte sans Entité : corrigé (au moins une ligne `data-meteo` exigée) ; (3) low, `#panneaux` exigé sur Pseudonymisation : corrigé ; Avant / après exige désormais `carte-chaine` visible et une durée de Chaîne non vide (5, corrigé) ; (4) « Chargement… » : gardé, dit dans la docstring ; (6) medium, fiche 3.8 : corrigé d'après `docs/tests-manuels.md` (points 6 et 7 pendant la Chaîne du 8, points 10 et 11 ajoutés) ; (7) `ignore_cleanup_errors=True` : corrigé ; (8) stderr du serveur capturé dans un fichier temporaire, dernières lignes citées en cas d'échec de démarrage : corrigé ; (9) course sur `port_libre` : accepté tel quel ; (12) `ruff format` propre.
- Les répétitions restent humaines : la story reste en `review`.

## Répétitions

À faire par Anaël, consignées dans `demo/repetitions.md`. La story passe à `done` quand SM-5 est atteint.
