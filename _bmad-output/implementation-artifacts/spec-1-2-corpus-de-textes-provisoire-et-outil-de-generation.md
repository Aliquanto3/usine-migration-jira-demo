---
title: 'Story 1.2 : Corpus de textes provisoire et outil de génération'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '9688d4d01624f95a9808c547f797bed210fe9210'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
warnings: [oversized]
deferred:
  - summary: >-
      composition.generer_journal (mesure NFR-2, fixtures de contrat et de Chaîne) génère avec le Corpus provisoire en mémoire, pas avec donnees/corpus/textes.json.
    evidence: |-
      Sortie identique aujourd'hui (le fichier versionné égale corpus_provisoire des Domaines livrés, test à l'appui). Divergence dès que la Story 1.9 versionne un Corpus LLM : usine donnees generer lirait les textes LLM, generer_journal les gabarits. Docstring mise à jour ; à charger en Story 1.9 (composition.py appartient à main).
    location: >-
      src/usine/composition.py (generer_journal)
    severity: medium
  - summary: >-
      La production LLM du Corpus n'est ni reprenable ni robuste : erreurs du fournisseur non converties en UsineErreur, case fautive non nommée, nombre et unicité des paires non vérifiés, {domaine} admis dans une section de Domaine nommé, écriture non atomique.
    evidence: |-
      produire_corpus enchaîne (D+1)×8+1 appels sans sauvegarde partielle ; ReponseCorpus accepte une seule paire ou des doublons. Inatteignable avant les adaptateurs réels (Story 6.1) ; à durcir en Story 1.9 avant le premier run payant.
    location: >-
      src/usine/generateur/corpus.py (produire_corpus, ecrire_corpus)
    severity: low
---

<intent-contract>

## Intent

**Problem:** Les titres et descriptions du Journal viennent d'un mini-corpus figé dans `generateur/textes.py` (`mini-e0`, `aucun`), sans lien avec la Cause racine ni le Domaine, et rien ne permet de produire le Corpus définitif par un LLM (FR-2, AD-24).

**Approach:** Définir le format du Corpus (titres et descriptions d'Anomalies par Domaine et par Cause racine, de Cas de test par Domaine, de Certifications), construire le Corpus provisoire par gabarits (`modele_corpus: gabarits-provisoires`), le versionner dans `donnees/corpus/textes.json` et faire lire ce Corpus par la génération. Livrer `outils/generer_corpus.py`, qui écrit le Corpus provisoire ou produit un Corpus au même format via `FournisseurLLM.generer_structure` seulement.

## Boundaries & Constraints

**Always:** textes 100 % fictifs, sans nom réel de personne ou d'organisation ; génération pure et déterministe (le Corpus est passé en paramètre, une seule instance `Random`) ; la régénération des données n'émet aucun appel LLM ; un Corpus illisible ou invalide lève une `UsineErreur` qui nomme le fichier ; la Cause racine n'apparaît jamais dans un `Evenement`.

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` ; importer un SDK de fournisseur (anthropic, mistralai, pydantic_ai, openai…) ; appeler un vrai LLM (Story 1.9) ; ajouter le garde-fou `modele_corpus` ≠ modèle de classification (Story 1.9) ; viser la volumétrie, le workflow H-17 ou les identifiants sensibles (Stories 1.3, 1.4).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Corpus versionné | `donnees/corpus/textes.json` | `modele_corpus: gabarits-provisoires`, les 6 Domaines livrés × 7 Causes, Cas de test par Domaine, Certifications, section générique | — |
| Domaine absent du Corpus | config avec `achats` | textes tirés de la section `generique`, `{domaine}` remplacé | — |
| En-tête | génération avec un Corpus | `version_corpus`, `modele_corpus` du Corpus dans l'`EnteteJournal` | — |
| Corpus invalide | JSON mal formé, Cause manquante, liste vide | refus au chargement | `UsineErreur` nommant le fichier |
| Outil, faux LLM | `FournisseurFactice` scripté | Corpus au même format, `modele_corpus` = `version_modele` du fournisseur, uniquement des appels `generer_structure` | — |
| Outil sans fournisseur | ni `--provisoire` ni fournisseur | refus | `UsineErreur` : adaptateurs LLM réels à la Story 6.1, utiliser `--provisoire` |
| Régénération | fournisseur qui échoue à tout appel | `usine donnees generer` aboutit, zéro appel | — |

</intent-contract>

## Code Map

- `src/usine/generateur/textes.py` -- mini-corpus E0 (`TITRES`, `DESCRIPTIONS`, `VERSION_CORPUS`, `MODELE_CORPUS`) : à remplacer par les gabarits du Corpus provisoire.
- `src/usine/generateur/journal.py` -- `_textes` (l.157), appelée par `_anomalie` (cause tirée juste avant, l.228), `_cas_de_test`, `_certification` ; `generer` (l.411) construit l'`EnteteJournal` avec `VERSION_CORPUS`/`MODELE_CORPUS` (l.512).
- `src/usine/generateur/cli.py` -- `usine donnees generer` : ajouter `--corpus` (défaut `donnees/corpus/textes.json`).
- `src/usine/composition.py` (l.311, `generer_journal`) -- modèle de délégation : `outils/` ne peut importer ni `usine.generateur` ni `usine.config` (`pyproject.toml`, contrat import-linter « hors produit », `allow_indirect_imports`).
- `src/usine/ports/fournisseur_llm.py` (gelé) -- `generer_structure(prompt, schema, parametres) -> ReponseStructuree[T]`, `version_modele`.
- `src/usine/contrats/llm.py` (gelé) -- `ParametresAppel(tache, max_jetons_sortie, temperature)` ; `Tache` n'a pas de valeur « corpus ».
- `src/usine/contrats/modele.py` (gelé) -- `Enregistrement`, `MappingFige` à réutiliser pour le format.
- `src/usine/contrats/tickets.py` -- `CauseRacine` (7 valeurs), `TypeTicket`.
- `tests/doublures/fournisseur_factice.py` -- `FournisseurFactice(reponses_structurees=..., version_modele=...)`, `appels`.
- `tests/depot/test_environnement.py` -- exige déjà `donnees/corpus/textes.json` versionné (non ignoré).
- `tests/unit/generateur/test_journal.py` (l.80-81 attend `mini-e0`/`aucun`), `test_cli.py` (config réduite : Domaines `comptabilite`, `achats`, `paie`).

## Tasks & Acceptance

**Execution:**
- `src/usine/generateur/corpus.py` -- créer : `TexteTicket` (titre, description), `TextesDomaine` (Anomalies par les 7 Causes, Cas de test), `Corpus` (`version_corpus`, `modele_corpus`, `domaines`, `generique`, `certifications`), `ReponseCorpus` (schéma demandé au LLM) ; `charger_corpus`, `serialiser_corpus`, `ecrire_corpus`, `CHEMIN_CORPUS`, `MODELE_GABARITS = "gabarits-provisoires"` ; `produire_corpus(fournisseur, domaines, *, version_corpus)` : une case par appel `generer_structure` (Domaine × Cause, Cas de test par Domaine, section générique, Certifications), `Tache.narration`.
- `src/usine/generateur/textes.py` -- réécrire en gabarits : `corpus_provisoire(domaines) -> Corpus`, vocabulaire par Domaine livré, vocabulaire générique sinon, gabarits par Cause racine.
- `src/usine/generateur/journal.py` -- `generer(..., corpus: Corpus | None = None)` (défaut : `corpus_provisoire(config.domaines)`) ; texte tiré dans la case (Domaine ou générique, Cause) ; `{entite}`/`{domaine}` remplacés ; en-tête depuis le Corpus.
- `src/usine/generateur/cli.py` -- option `--corpus`, chargée par `charger_corpus` et passée à `generer`.
- `src/usine/composition.py` -- `generer_corpus(fournisseur | None, domaines, chemin, *, version_corpus)` en délégation (hors lane, voir Design Notes).
- `outils/generer_corpus.py` -- créer : `--config`, `--sortie`, `--provisoire`, `--version-corpus` ; `generer(fournisseur, ...)` testable ; sans fournisseur ni `--provisoire` : `UsineErreur`.
- `donnees/corpus/textes.json` -- écrit par `outils/generer_corpus.py --provisoire`.
- `tests/unit/generateur/test_corpus.py`, `tests/unit/outils/test_generer_corpus.py`, `test_journal.py`, `test_cli.py` -- tests de la matrice et des AC.

**Acceptance Criteria:**
- Given `donnees/corpus/textes.json`, when on le charge, then il est valide, porte `modele_corpus: gabarits-provisoires` et est identique octet pour octet à `corpus_provisoire` des Domaines de `config/programme.yaml`.
- Given `outils/generer_corpus.py` lancé avec un `FournisseurFactice`, when il écrit le Corpus, then le fichier se recharge par `charger_corpus`, porte le `modele_corpus` du fournisseur, et seuls des appels `generer_structure` ont été enregistrés.
- Given les sources de `outils/generer_corpus.py` et `generateur/corpus.py`, when on liste leurs imports, then aucun SDK de fournisseur n'y figure.
- Given le Corpus versionné et un fournisseur qui échoue à tout appel branché sur `produire_corpus`, when on lance `usine donnees generer`, then le Journal est écrit et aucun appel n'a eu lieu.
- Given un Journal généré, when on regarde les Anomalies, then le titre de chacune appartient à la case (Domaine, Cause racine de la vérité terrain) du Corpus.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 31 findings — high 0, medium 5, low 17, false 9, maybe-false 0
- findings:
  - `[medium]` `[patch]` (blind) `composition.generer_journal` ignore le Corpus versionné — docstring explicite (Corpus provisoire, à charger en Story 1.9) ; entrée `deferred` pour le code.
  - `[low]` `[patch]` (blind) `generer(corpus=None)` retombe sans bruit sur le provisoire — même racine que la ligne précédente, même correctif.
  - `[medium]` `[patch]` (blind) `test_regeneration_sans_appel_llm` vrai par construction — contrôle AST ajouté : `generateur/cli.py` et `journal.py` n'importent ni `ports.fournisseur_llm`, ni `composition`, ni `ia`, ni `produire_corpus`.
  - `[false]` `[reject]` (blind) Domaines de config non vérifiés contre le Corpus — repli voulu sur `generique` (Design Notes) pour qu'un Domaine nouveau ne demande ni code ni Corpus.
  - `[low]` `[reject]` (blind) `TEXTES_PAR_CASE` et unicité non vérifiés — chemin LLM inatteignable avant 6.1 ; ajout de garde ; consigné en `deferred` pour 1.9.
  - `[low]` `[reject]` (blind) `{domaine}` admis dans une section de Domaine nommé — le format le permet et le remplace ; consigné en `deferred`.
  - `[low]` `[reject]` (blind) Run LLM non reprenable, erreur sans la case — inatteignable avant 6.1 ; consigné en `deferred`.
  - `[low]` `[reject]` (blind) Prompts avec l'identifiant brut du Domaine — cosmétique, à revoir avec le vrai modèle (1.9).
  - `[low]` `[reject]` (blind) `ecrire_corpus` non atomique — outil manuel, fichier versionné restaurable par git ; consigné en `deferred`.
  - `[false]` `[reject]` (blind) `CHEMIN_CORPUS` relatif au répertoire courant — même convention que `--config` (`config/programme.yaml`) et `--config-jira`, déjà relatifs ; la commande se lance à la racine.
  - `[false]` `[reject]` (blind) Rupture du déterminisme non documentée — consignée dans les Design Notes (« Flux du hasard »).
  - `[low]` `[reject]` (blind) Validateur qui mêle deux contrôles — cosmétique.
  - `[low]` `[reject]` (blind) Chemins d'erreur partiellement testés — Corpus invalide couvert par `test_corpus_invalide` (CLI) et `test_corpus.py` ; le reste relève du chemin LLM (1.9).
  - `[medium]` `[patch]` (verification-gap) Pas de test de la source du Corpus dans `generer_journal` — même racine que la première ligne ; docstring + `deferred`.
  - `[medium]` `[patch]` (verification-gap) Test « aucun appel LLM » limité à deux attributs — même correctif AST que la ligne blind.
  - `[low]` `[patch]` (edge) `UnicodeDecodeError` non capturée dans `domaines_programme` — ajoutée, test `test_main_config_non_utf8`.
  - `[low]` `[reject]` (edge) Écriture non atomique — doublon de la ligne blind.
  - `[low]` `[reject]` (edge) Nombre ou doublons de paires LLM — doublon de la ligne blind.
  - `[low]` `[reject]` (edge) Exception du fournisseur non convertie — doublon de la ligne blind.
  - `[false]` `[reject]` (edge) Domaine vide dans le prompt — `ConfigProgramme` (gelé) et le validateur du Corpus refusent un Domaine vide avant tout appel facturé utile ; chemin inatteignable par l'outil.
  - `[low]` `[reject]` (edge) Domaines en double dans la séquence — l'outil lit les Domaines de `ConfigProgramme` ; garde à ajouter sans cas réel.
  - `[low]` `[reject]` (edge) Clé de Domaine avec espaces → repli générique — fichier produit par l'outil, jamais saisi à la main.
  - `[low]` `[reject]` (edge) `--version-corpus ""` remplacé par le défaut — sans conséquence (valeur vide refusée de toute façon par `Corpus`).
  - `[low]` `[reject]` (edge) `{domaine}` dans un texte LLM de Domaine nommé — doublon de la ligne blind.
  - `[medium]` `[patch]` (edge) AC « aucun appel » vérifié trivialement — même correctif AST.
  - `[false]` `[reject]` (intent) Outil non lançable en ligne de commande avec un faux LLM — la CLI d'un vrai modèle relève de la Story 1.9 ; l'AC est tenue par `generer(fournisseur, ...)`, point d'entrée de l'outil.
  - `[low]` `[patch]` (intent) Contrôle « aucun SDK » limité aux imports directs — `test_outil_sans_sdk_transitif` importe l'outil dans un sous-processus et vérifie les modules chargés.
  - `[false]` `[reject]` (intent) Régénération par le CLI non démontrée — `test_corpus_autre_chemin` montre que le Journal reprend l'en-tête du fichier passé.
  - `[false]` `[reject]` (intent) Chemin `composition` hors Corpus versionné — doublon de la première ligne (reporté).
  - `[false]` `[reject]` (intent) `composition.py` hors lane — justifié dans les Design Notes (« Fichiers hors lane »).
  - `[false]` `[reject]` (intent) Certifications sans Domaine — une Certification porte sur une Entité, pas un Domaine (`CHAMPS_PAR_TYPE`) ; lecture 1a retenue.

## Design Notes

- **Où vit le format.** AD-2 veut toute forme de fichier dans `contrats/` (gelé, sans modèle de Corpus). Pour ne pas en créer une seconde ailleurs, `generateur` possède seul le format : il écrit, relit et produit le Corpus. `outils/generer_corpus.py` ne manipule pas le modèle : il passe le fournisseur et le chemin à `composition.generer_corpus`. Un `Corpus` dans `contrats` reste souhaitable à la prochaine version des contrats.
- **Appel hors passerelle.** AD-24 et l'AC prévoient l'appel direct de `generer_structure` hors produit. `ParametresAppel` exige une `Tache` : `narration` (rédaction de texte), jamais `classification` dont le modèle doit différer de `modele_corpus`.
- **Section générique.** Un Domaine de configuration absent du Corpus tire dans `generique` (`{domaine}` remplacé), pour que changer les Domaines ne demande ni code ni nouveau Corpus.
- **Fichiers hors lane** : `src/usine/composition.py` (délégation `generer_corpus`, indispensable car `outils/` ne peut importer ni `generateur` ni `config`).
- **Flux du hasard.** Un seul tirage par texte (paire titre, description) : le Journal d'une graine change par rapport à la Story 1.1.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check .` -- expected: aucun écart
- `uv run mypy && uv run lint-imports` -- expected: succès
- `uv run pytest -q` -- expected: tout passe, durée proche de 44 s
- `uv run python outils/generer_corpus.py --provisoire` -- expected: `donnees/corpus/textes.json` inchangé (git diff vide)

## Auto Run Result

Status: done

**Résumé.** Le Corpus de textes a un format (`generateur/corpus.py`) : paires (titre, description) d'Anomalies par Domaine × Cause racine, de Cas de test par Domaine, de Certifications, et une section `generique` pour tout Domaine absent. Le Corpus provisoire est construit par gabarits (`generateur/textes.py`, `modele_corpus: gabarits-provisoires`, `version_corpus: provisoire-1`) et versionné dans `donnees/corpus/textes.json`. `usine donnees generer` lit ce fichier (`--corpus`) ; l'en-tête du Journal en reprend version et modèle. `outils/generer_corpus.py` écrit le Corpus provisoire (`--provisoire`) ou, avec un fournisseur, un Corpus au même format via `generer_structure` seul (`Tache.narration`).

**Fichiers.**
- `src/usine/generateur/corpus.py` : format, chargement, écriture, production par LLM.
- `src/usine/generateur/textes.py` : gabarits du Corpus provisoire (6 Domaines livrés, vocabulaire générique).
- `src/usine/generateur/journal.py` : textes tirés dans la case (Domaine, Cause), en-tête depuis le Corpus.
- `src/usine/generateur/cli.py` : option `--corpus`.
- `outils/generer_corpus.py` : outil de génération du Corpus.
- `donnees/corpus/textes.json` : Corpus provisoire versionné.
- Tests : `tests/unit/generateur/test_corpus.py`, `tests/unit/outils/test_generer_corpus.py`, `test_journal.py`, `test_cli.py`.
- Hors lane : `src/usine/composition.py` (délégation `generer_corpus`, docstring de `generer_journal`).

**Revue.** 31 constats : 5 correctifs (2 entrées medium : contrôle AST de l'absence de chemin LLM dans la génération, docstring de `generer_journal` ; 2 low : `UnicodeDecodeError`, contrôle transitif des SDK), 2 entrées `deferred`, le reste rejeté avec sa raison dans le journal de triage. Correctifs par verdict : medium 2, low 2. Revue complémentaire recommandée : non — les deux entrées medium corrigées sont un test et une docstring, sans changement de comportement à revérifier ; le risque réel (chemin `composition` sur le Corpus provisoire) est reporté à la Story 1.9.

**Vérification.** `ruff check`, `ruff format --check`, `mypy`, `lint-imports` (13 contrats) : succès. `pytest -q` : 1 318 passés, 1 ignoré, 52 s. `outils/generer_corpus.py --provisoire` réécrit un fichier identique (test octet pour octet).

**Risques résiduels.** Journal d'une même graine différent de celui de la Story 1.1 (un seul tirage par paire). `composition.generer_journal` reste sur le Corpus provisoire en mémoire jusqu'à la Story 1.9. Production LLM non durcie (reportée à la 1.9). `controle_lanes.py` signalera `src/usine/composition.py`.
