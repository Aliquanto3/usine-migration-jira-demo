---
title: 'Story 1.4 : Identifiants sensibles fictifs'
type: 'feature'
created: '2026-10-12'
baseline_revision: 'b2b1eb7e359ee6586cd4b744174b5335d065569f'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
warnings: [oversized]
deferred:
  - summary: >-
      Les types CLIENT et ID_CLIENT injectés n'ont encore aucun motif de détection : seul COMPTE figure dans MOTIFS_PAR_DEFAUT, et config/pseudonymisation.yaml n'existe pas.
    evidence: |-
      src/usine/adaptateurs/pseudonymisation/__init__.py:30 ne déclare que COMPTE. Un balayage SM-7 sur identifiants_injectes.json trouverait aujourd'hui les noms (civilité + prénom + NOM des listes inventées) et les identifiants 99\d{8} en clair. À traiter par L6 (Story 6.2, reconnaisseurs de config/pseudonymisation.yaml) avec les formats décrits dans generateur/identifiants.py.
    location: >-
      src/usine/adaptateurs/pseudonymisation/__init__.py:30 (L6)
    severity: medium
  - summary: >-
      Le nom du fichier des identifiants injectés (NOM_IDENTIFIANTS) est une constante de generateur.journal, faute de pouvoir étendre contrats.passage (gelé) ; le test SM-7 de L6 devra l'importer du générateur ou la recopier.
    evidence: |-
      contrats.passage déclare CHEMIN_JOURNAL et CHEMIN_VERITE_TERRAIN mais pas la liste. À reprendre dans une prochaine version des contrats (CHEMIN_IDENTIFIANTS_INJECTES), par une PR dédiée sur main.
    location: >-
      src/usine/generateur/journal.py (NOM_IDENTIFIANTS)
    severity: low
---

<intent-contract>

## Intent

**Problem:** Les descriptions d'Anomalies générées (Stories 1.2, 1.3) ne contiennent aucun identifiant sensible : la Pseudonymisation (Epic 6) n'a rien de visible à démontrer, et le test de balayage SM-7 n'a pas de liste des valeurs à rechercher (FR-4, H-4).

**Approach:** Après tous les tirages existants, le générateur choisit au moins 15 % des Anomalies et ajoute à leur description une phrase portant un à trois identifiants fictifs : compte (IBAN français à clé fausse), nom de client inventé, identifiant client à clé de Luhn fausse. La liste des identifiants injectés accompagne la `Generation` et `ecrire_journal` l'écrit dans `donnees/identifiants_injectes.json` (ignoré par git). Tâche reportée de la 1.3 : le marqueur `lent` passe dans `pyproject.toml`.

## Boundaries & Constraints

**Always:** générateur pur et déterministe (une seule instance `Random`) ; tirages des identifiants **après** tous les tirages existants, pour que structure, dates, affectations et titres d'une graine restent ceux de la Story 1.3 ; seules les descriptions des Anomalies choisies changent ; identifiants entièrement fictifs et de forme manifestement factice (code banque `99999`, identifiant client préfixé `99`, noms de clients construits à partir de racines « fictif, simulé, exemple, leurre, maquette… ») ; aucun nom réel ; types d'identifiants au format des types de jetons (`COMPTE`, `CLIENT`, `ID_CLIENT`, `contrats.llm.MOTIF_TYPE_JETON`).

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` (le chemin du fichier est donc une constante du générateur) ; toucher à `config/pseudonymisation.yaml` ou aux adaptateurs de Pseudonymisation (L6) ; exposer la Cause racine ; ajouter une dépendance ; écrire la liste ailleurs que dans le répertoire de sortie du Journal.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Config livrée | graine 42, 2026-10-12 | ⌈15 % × Anomalies⌉ descriptions porteuses, ≥ 10 % ; les trois types présents | — |
| Programme réduit | 25 à 35 Anomalies | au moins ⌈15 % × n⌉ ≥ 4 descriptions porteuses | — |
| IBAN | tout compte injecté | motif `FR\d{2}( \d{4}){5} \d{3}`, code banque `99999`, contrôle mod 97 ≠ 1 | — |
| Identifiant client | tout identifiant injecté | 10 chiffres commençant par `99`, contrôle de Luhn faux | — |
| Nom de client | tout nom injecté | civilité + prénom et NOM pris dans les listes inventées | — |
| Reproductibilité | même graine, même Corpus | Journal, vérité terrain et liste identiques octet pour octet | — |
| Écriture | `ecrire_journal(g, rep)` | `rep/identifiants_injectes.json` écrit avec le Journal | `UsineErreur` nommant le répertoire |

</intent-contract>

## Code Map

- `src/usine/generateur/journal.py` -- `Generation` (l.109, ajouter `identifiants`), `generer` (l.511 : tirage final après la boucle des Certifications l.582-587, avant les clés l.589), `_Ticket.attributs[Champ.description]`, `ecrire_journal` (l.633), `serialiser_verite` (modèle de sérialisation JSON triée).
- `src/usine/generateur/identifiants.py` -- à créer : fabrication pure des identifiants fictifs (IBAN à clé fausse, nom inventé, identifiant à clé de Luhn fausse) et de la phrase insérée.
- `src/usine/generateur/cli.py` -- message de fin : nombre d'identifiants et chemin de la liste.
- `src/usine/adaptateurs/pseudonymisation/__init__.py` (L6, lecture seule) -- `MOTIFS_PAR_DEFAUT = {"COMPTE": r"FR\d{2}(?: \d{4}){5} \d{3}"}` : l'IBAN généré doit suivre ce motif.
- `src/usine/contrats/llm.py` (gelé) -- `MOTIF_TYPE_JETON` : forme des noms de types.
- `src/usine/composition.py` (main, inchangé) -- appelle `ecrire_journal` : la liste suit automatiquement.
- `.gitignore` -- `donnees/*` sauf `donnees/corpus/` : la liste est ignorée.
- `tests/unit/generateur/test_journal.py` -- `test_corpus_passe_en_parametre` (l.736) compare la description à l'égalité : passer à un préfixe ; `test_ecrire_journal` (l.279).
- `tests/unit/generateur/conftest.py`, `tests/unit/outils/conftest.py` -- enregistrement du marqueur `lent` (report 1.3), à supprimer.
- `pyproject.toml` (hors lane) -- `[tool.pytest.ini_options]` : `addopts = ["-m", "not reseau", "--strict-markers"]`, `markers`.

## Tasks & Acceptance

**Execution:**
- `src/usine/generateur/identifiants.py` -- créer : `TypeIdentifiant` (`COMPTE`, `CLIENT`, `ID_CLIENT`), `IdentifiantInjecte` (clé de ticket, type, valeur), `iban_fictif`, `nom_client_fictif`, `identifiant_client_fictif`, `phrase_identifiants` (sous-ensemble non vide de types), fonctions de contrôle `iban_valide` et `luhn_valide` ; docstrings en français.
- `src/usine/generateur/journal.py` -- `PROPORTION_IDENTIFIANTS_POURCENT = 15` ; dans `generer`, après les Certifications, tirer ⌈15 % × n⌉ Anomalies (`rng.sample`) dans l'ordre de création des tickets, ajouter la phrase à leur description, puis rattacher les identifiants aux clés attribuées ; `Generation.identifiants` (tuple trié par numéro de clé) ; `serialiser_identifiants` et écriture dans `ecrire_journal` (`NOM_IDENTIFIANTS = "identifiants_injectes.json"`) ; docstrings à jour.
- `src/usine/generateur/cli.py` -- mentionner la liste écrite.
- `tests/unit/generateur/test_identifiants.py` -- créer : formats, invalidité (mod 97, Luhn), noms inventés, phrase non vide, déterminisme.
- `tests/unit/generateur/test_journal.py` -- proportion ≥ 10 % mesurée sur le Journal sérialisé et la liste écrite (config réduite et livrée), trois types présents, identifiants absents des titres et des tickets autres qu'Anomalies, chaque identifiant de la liste présent dans la description de sa clé, écriture et reproductibilité de la liste ; `test_corpus_passe_en_parametre` en préfixe.
- `tests/unit/generateur/test_cli.py` -- la commande écrit `identifiants_injectes.json`.
- `pyproject.toml` (hors lane) -- marqueur `lent` enregistré, `addopts` exclut `lent` par défaut ; supprimer les deux `conftest.py` de la lane.

**Acceptance Criteria:**
- Given un Journal généré et écrit, when on compte les descriptions d'Anomalies du Journal qui contiennent une valeur de `identifiants_injectes.json`, then elles représentent au moins 10 % des Anomalies.
- Given un identifiant injecté, when on le vérifie, then un compte est un IBAN au format français dont la clé est fausse, un identifiant client a une clé de Luhn fausse, et un nom de client est composé uniquement de prénoms et noms inventés de la liste du générateur.
- Given la génération par `usine donnees generer`, when elle se termine, then `identifiants_injectes.json` est écrit à côté du Journal dans `donnees/`, chemin ignoré par git.
- Given `uv run pytest -q`, when la suite tourne, then les tests `lent` sont exclus ; `uv run pytest -m lent` les exécute et ils passent.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 29 findings — high 0, medium 4, low 17, false 8, maybe-false 0
- findings:
  - `[medium]` `[defer]` (blind) CLIENT et ID_CLIENT sans motif de Pseudonymisation — vrai, mais les reconnaisseurs relèvent de L6 (Story 6.2) ; consigné en `deferred`.
  - `[low]` `[defer]` (blind) `NOM_IDENTIFIANTS` hors de `contrats` — `contrats.passage` gelé ; consigné en `deferred` pour une prochaine version des contrats.
  - `[low]` `[patch]` (blind) `iban_valide`/`luhn_valide` lèvent `ValueError` sur des chiffres Unicode — `isascii()` exigé, cas « ² » ajoutés.
  - `[medium]` `[patch]` (blind) Motif `COMPTE` recopié dans les tests — remplacé par `MOTIFS_PAR_DEFAUT["COMPTE"]` importé de l'adaptateur, plus un `search` dans la description.
  - `[low]` `[patch]` (blind) `15` et `{"M.", "Mme"}` codés en dur dans `_verifier_identifiants` — `PROPORTION_IDENTIFIANTS_POURCENT` et `CIVILITES`.
  - `[low]` `[reject]` (blind) 288 noms possibles, doublons, civilité indépendante du prénom — les prénoms inventés n'ont pas de genre ; un doublon ne gêne ni la démonstration ni le balayage SM-7 (liste par clé) ; forcer l'unicité ajouterait une branche.
  - `[low]` `[reject]` (blind) Écriture non atomique des trois fichiers — même schéma que Journal et vérité terrain depuis la 0.3 ; une écriture partielle lève une `UsineErreur` visible ; renommage atomique = complexité sans cas observé.
  - `[low]` `[reject]` (blind) Test « ignoré par git » textuel — `git check-ignore` vérifié à la main ; appeler git dans un test unitaire ajoute une dépendance d'environnement pour un cas improbable.
  - `[false]` `[reject]` (blind) Changement du marqueur `lent` non consigné — consigné dans les Design Notes (« Fichiers hors lane ») et au journal du run ; la CI ne lançait déjà pas les tests `lent` (sautés).
  - `[low]` `[patch]` (blind) IBAN valide réel (exemple normatif) dans les tests — cas valide construit sur le code banque 99999 avec clé calculée.
  - `[low]` `[reject]` (blind) Clé RIB parfois juste — l'IBAN complet est toujours invalide (clé mod 97 fausse) ; forcer aussi la clé RIB n'ajoute rien à l'AC.
  - `[low]` `[patch]` (edge) `iban_valide` sur chiffre Unicode — même correctif que la ligne blind.
  - `[low]` `[patch]` (edge) `luhn_valide` sur chiffre Unicode — même correctif.
  - `[low]` `[reject]` (edge) Doublons de noms clients — même raison que la ligne blind.
  - `[false]` `[reject]` (edge) Proportion > 100 ou < 0 — constante de module fixée à 15, aucune configuration ne la change.
  - `[false]` `[reject]` (edge) Description vide ou finissant par une espace — toutes les descriptions du Corpus (gabarits et Corpus versionné) sont des phrases non vides terminées par un point.
  - `[low]` `[reject]` (edge) Écriture non atomique — même raison que la ligne blind.
  - `[low]` `[reject]` (edge) `--sortie` hors de `donnees/` — choix explicite de l'utilisateur ; l'AC porte sur la génération par défaut dans `donnees/`.
  - `[low]` `[reject]` (edge) `-m "not reseau"` explicite lance désormais les tests `lent` — usage manuel ; la CI lance `uv run pytest` sans `-m`.
  - `[low]` `[patch]` (edge) Docstring « ordre de création » inexacte — « ordre de construction de la liste des tickets ».
  - `[false]` `[reject]` (edge) Liste toujours ignorée par git — la docstring et l'AC parlent du répertoire par défaut ; même raison que la ligne `--sortie`.
  - `[medium]` `[patch]` (verification-gap) IBAN vérifié contre une copie du motif — même correctif que la ligne blind (import de `MOTIFS_PAR_DEFAUT`).
  - `[medium]` `[defer]` (verification-gap, other) CLIENT et ID_CLIENT sans motif — même entrée `deferred` que la ligne blind.
  - `[false]` `[reject]` (intent) 10 % mesurés sur le Journal plutôt que dans Jira — l'AC dit « un Journal généré » ; l'injection est la Story 1.6.
  - `[low]` `[patch]` (intent) Plausibilité testée contre les définitions du générateur — pour COMPTE, désormais contre le motif de l'adaptateur ; CLIENT/ID_CLIENT : entrée `deferred`.
  - `[false]` `[reject]` (intent) Absence de personne réelle vérifiée par construction — c'est la lecture imposée par le run (« forme manifestement factice ») ; une liste de noms réels serait elle-même des données réelles.
  - `[false]` `[reject]` (intent) Fichier écrit dans `--sortie` et non toujours dans `donnees/` — défaut `donnees/`, testé par `test_chemins_par_defaut`.
  - `[low]` `[defer]` (intent) Format de la liste fixé côté générateur — même entrée `deferred` que `NOM_IDENTIFIANTS`.
  - `[false]` `[reject]` (intent) Marqueur `lent` au-delà de l'enregistrement — le report de la 1.3 demandait l'enregistrement **et** l'exclusion par défaut dans `pyproject.toml`, puis le retrait des deux conftest.

## Design Notes

- **Ordre des tirages.** Les identifiants sont tirés à la fin : le Journal d'une graine ne change que par les descriptions choisies, ce qui préserve les attendus fondés sur une graine (Météo, Excel, contrats).
- **Proportion.** ⌈15 %⌉ par construction (`rng.sample`) plutôt qu'une probabilité par Anomalie : l'AC ≥ 10 % tient même sur le Programme réduit.
- **Forme factice.** Code banque `99999` et préfixe `99` signalent le faux au premier regard ; la clé fausse garantit qu'aucun contrôle de validité ne passe. Exemple : « Cas cité par l'Entité ENT-B : client Mme Simulie MAQUETTEAU, compte FR42 9999 9123 4512 3456 7890 123, identifiant client 9912345670. »
- **Fichier.** `[{"cle_ticket", "type", "valeur"}]` en JSON, UTF-8, trié par numéro de clé. Le nom est une constante du générateur, `contrats.passage` étant gelé ; L6 le lira par ce nom (à reprendre dans `contrats` lors d'une prochaine version si besoin).
- **Fichiers hors lane** : `pyproject.toml` (enregistrement du marqueur `lent` et exclusion par défaut, report de la Story 1.3 demandé par le run ; remplace les deux `conftest.py` de la lane).

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check .` -- expected: aucun écart
- `uv run mypy && uv run lint-imports` -- expected: succès
- `uv run pytest -q` -- expected: tout passe, tests `lent` désélectionnés
- `uv run pytest -q -m lent` -- expected: tests lents exécutés et verts

## Auto Run Result

Status: done

**Résumé.** Après tous les tirages de la Story 1.3, le générateur choisit ⌈15 %⌉ des Anomalies (`rng.sample`) et ajoute à leur description une phrase citant un à trois identifiants fictifs : compte (IBAN français, code banque `99999`, clé mod 97 fausse, au motif `COMPTE` de la Pseudonymisation), client (civilité, prénom et NOM inventés sur les racines fictif, simulé, exemple, leurre, maquette, factice) et identifiant client (`99` + 8 chiffres, clé de Luhn fausse). Le reste du Journal d'une graine est inchangé. `ecrire_journal` écrit la liste `identifiants_injectes.json` (`[{cle_ticket, type, valeur}]`) à côté du Journal, sous `donnees/`, hors git. Sur la config livrée (graine 42) : 917 identifiants. Le marqueur `lent` est enregistré et exclu par défaut dans `pyproject.toml` ; les deux `conftest.py` de la lane sont supprimés.

**Fichiers.**
- `src/usine/generateur/identifiants.py` (nouveau) : fabrication et contrôle des identifiants fictifs, phrase insérée.
- `src/usine/generateur/journal.py` : `_injecter_identifiants`, `Generation.identifiants`, `serialiser_identifiants`, écriture de la liste.
- `src/usine/generateur/cli.py` : annonce de la liste écrite.
- `tests/unit/generateur/test_identifiants.py` (nouveau), `test_journal.py`, `test_cli.py` : proportion mesurée sur le Journal et la liste écrits, formats, placement, seules les descriptions changent, reproductibilité.
- `tests/unit/generateur/conftest.py`, `tests/unit/outils/conftest.py` : supprimés.
- Hors lane : `pyproject.toml` (marqueur `lent`).

**Revue.** 29 constats : 5 entrées corrigées (medium 1 : motif `COMPTE` importé de l'adaptateur au lieu d'une copie ; low 4 : validateurs en ASCII, IBAN valide de test construit sur le code banque 99999, constantes au lieu de valeurs codées en dur, docstring). 2 entrées `deferred` : motifs CLIENT et ID_CLIENT à fournir par L6 (Story 6.2), nom du fichier à reprendre dans une future version des contrats. Rejets, avec leur raison dans le journal de triage : doublons de noms, écriture non atomique, `--sortie` hors `donnees/`, clé RIB, test textuel du `.gitignore`, sélection `-m` explicite, et les constats `false`. Revue complémentaire recommandée : non (un seul `medium` corrigé, aucun `high`).

**Vérification.** `ruff check`, `ruff format --check`, `mypy` et `lint-imports` (13 contrats) : succès. `pytest -q` : 1 515 passés, 1 sauté (préexistant), 21 désélectionnés (`lent`). `pytest -q -m lent` : 21 passés.

**Risques résiduels.** Les descriptions des Anomalies choisies changent pour toute graine ; un attendu externe qui compare une description exacte devra suivre (aucun dans la suite). Le balayage SM-7 de L6 ne trouvera CLIENT et ID_CLIENT qu'une fois ses reconnaisseurs ajoutés. `controle_lanes.py` signalera `pyproject.toml`.
