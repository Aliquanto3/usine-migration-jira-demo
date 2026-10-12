---
title: 'Story 6.2 : Pseudonymisation par Presidio'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'bdfe6b28ad13c248f7acd58bb89f7d4fc8860abc'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: []
deferred:
  - summary: >-
      Presidio n'est pas branché dans la composition : la clé de choix du moteur manque à ConfigPseudonymisation (contrats gelés).
    evidence: |-
      AD-15 veut un choix du moteur par une clé de config/pseudonymisation.yaml lue par la composition ; ConfigPseudonymisation (extra=forbid) n'a pas de clé moteur. Le Palier 2 tourne donc sur le moteur regex (avec les reconnaisseurs du YAML livré) jusqu'à l'ajout de la clé.
    location: >-
      src/usine/composition.py:179-230
    severity: medium
  - summary: >-
      Un motif maison qui dépasse le délai regex de Presidio serait ignoré avec un simple avertissement.
    evidence: |-
      Non vérifié (lecture de presidio_analyzer bloquée par une règle de refus) : si PatternRecognizer attrape le TimeoutError et ne fait que journaliser, la détection est sautée sans erreur. À trancher en lisant pattern_recognizer.py ; motifs livrés simples, risque faible en pratique.
    location: >-
      src/usine/adaptateurs/presidio/__init__.py
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** Seul le moteur de repli par expressions régulières (`PseudonymiseurHmac`, motif d'amorce COMPTE) existe ; aucun moteur Presidio + spaCy `fr_core_news_md`, aucun `config/pseudonymisation.yaml` couvrant les identifiants fictifs de FR-4 (CLIENT, COMPTE, ID_CLIENT), donc pas de garantie qu'aucun identifiant injecté ne parte vers un LLM.

**Approach:** Extraire de `adaptateurs/pseudonymisation` une base commune (dérivation HMAC, protection des clés de ticket, regroupement des chevauchements, table) paramétrée par un détecteur de plages ; `PseudonymiseurHmac` la réutilise avec ses regex, et un nouvel adaptateur `adaptateurs/presidio/` (`PseudonymiseurPresidio`) la réutilise avec Presidio (reconnaisseurs maison + entités spaCy de `entites_presidio`). Livrer `config/pseudonymisation.yaml` et étendre la suite de contrat.

## Boundaries & Constraints

**Always:** jetons `<TYPE>_<6 hex HMAC-SHA256(cle, valeur)>` dérivés par le code de `adaptateurs/pseudonymisation` (un seul endroit) ; même valeur détectée par un reconnaisseur maison → même jeton sur les deux moteurs ; clés de ticket jamais remplacées ; regex Presidio compilées sans drapeaux globaux (`global_regex_flags=0`) pour coller au moteur regex ; une plage d'entité spaCy qui chevauche une plage de reconnaisseur maison est écartée (le reconnaisseur maison prime) ; aucun téléchargement de modèle : modèle spaCy absent → `UsineErreur` explicite ; tests sans réseau ni LLM, moteur Presidio construit une fois par session de test.

**Never:** toucher `contrats/` ou `ports/` (gelés) ; toucher les adaptateurs LLM (lane 6.1) ; brancher Presidio dans `composition.py` (la clé de choix du moteur n'existe pas dans `ConfigPseudonymisation`, gelée : point reporté à Anaël) ; changer le comportement observable de `PseudonymiseurHmac`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Phrase générée | « Cas cité par l'Entité ENT-B : client Mme Simulie MAQUETTEAU, compte FR42 9999 …, identifiant client 9912345670. » | `CLIENT_xxxxxx`, `COMPTE_xxxxxx`, `ID_CLIENT_xxxxxx`, jetons identiques à ceux de `PseudonymiseurHmac` | — |
| Clé de ticket | « voir DEMO-204518 » | inchangée | — |
| Entité spaCy seule | « Jean Dupont a validé. » avec `entites_presidio: [PERSON]` | `PERSON_xxxxxx` | — |
| Entité spaCy chevauchant un CLIENT | « Mme Simulie MAQUETTEAU » détectée aussi comme PER | un seul jeton `CLIENT_…` sur la valeur du reconnaisseur | — |
| Modèle absent | `modele_spacy: inexistant_xx` | — | `UsineErreur` nommant le modèle, sans téléchargement |
| Entité invalide | `entites_presidio: [person]` | — | `UsineErreur` (type de jeton invalide) |

</intent-contract>

## Code Map

- `src/usine/adaptateurs/pseudonymisation/__init__.py` -- `PseudonymiseurHmac` : `jeton`, `_plages` (filtre clés de ticket, regroupement, `fragments_hors_cles`), `_remplacer`, `pseudonymiser/reidentifier/apercu` ; `Protocol` local `TablePseudonymes` ; à factoriser en base à détecteur.
- `src/usine/adaptateurs/presidio/` -- à créer (AD-15). Import-linter autorise `presidio_*` et `spacy` dans `usine.adaptateurs`, interdit `fr_core_news_md` (charger par nom via spaCy).
- `src/usine/contrats/config.py:463-486` -- `Reconnaisseur(type_jeton, motif, score)`, `ConfigPseudonymisation(langue, modele_spacy, entites_presidio, reconnaisseurs)` ; lecture seule.
- `src/usine/contrats/llm.py` -- `est_type_jeton`, `CANDIDAT_JETON`, `variantes_jeton` ; lecture seule.
- `src/usine/composition.py:179-200` -- `_motifs_pseudonymisation` lit `config/pseudonymisation.yaml` (sinon `MOTIFS_PAR_DEFAUT`) pour le moteur regex ; non modifié, mais le nouveau YAML y passe.
- `src/usine/generateur/identifiants.py` -- formes des identifiants : IBAN `FRkk 9999 9ddd … ddd` (groupes de 4, dernier de 3), « M./Mme Prénom NOM », ID client 10 chiffres préfixés `99`.
- `src/usine/generateur/journal.py:899` -- `generer(config, graine, date)` → `Generation.identifiants`, `evenements` (champ `description`, valeur dans `vers`).
- `tests/contrat/pseudonymiseur/fabriques.py` -- `FABRIQUES` (factice, hmac), `MOTIFS_FACTICES`, `EXEMPLES` : ajouter `presidio`.
- `tests/unit/generateur/programme_reduit.yaml` + `test_journal.py:59-93` -- configuration réduite et graines réutilisables pour le balayage.
- `pyproject.toml` -- dépendances presidio 2.2.364, spacy 3.8.16, `fr_core_news_md` déjà présentes et verrouillées ; CI `uv sync --locked` sur Ubuntu et Windows.

## Tasks & Acceptance

**Execution:**
- `src/usine/adaptateurs/pseudonymisation/__init__.py` -- extraire `PseudonymiseurDerive` (clé, table, `jeton`, `_plages` sur `_detecter(texte)`, remplacement, port) ; `PseudonymiseurHmac` en hérite avec ses regex -- un seul lieu de dérivation (AD-15).
- `src/usine/adaptateurs/presidio/__init__.py` -- `PseudonymiseurPresidio(cle, config, table)` : vérifie le modèle (`spacy.util.is_package`), construit `AnalyzerEngine` (NLP spaCy, `PatternRecognizer` par type de jeton, `SpacyRecognizer` pour `entites_presidio`), détecte, fait primer les reconnaisseurs maison -- moteur du Palier 2.
- `config/pseudonymisation.yaml` -- reconnaisseurs COMPTE, CLIENT, ID_CLIENT couvrant FR-4, `entites_presidio: [PERSON]`.
- `tests/contrat/pseudonymiseur/fabriques.py` -- fabrique `presidio` (moteur partagé en cache module) -- suite de contrat sur les trois moteurs.
- `tests/unit/adaptateurs/presidio/test_presidio.py` -- matrice I/O, égalité des jetons entre moteurs, balayage du jeu généré (graines du programme réduit) sur les deux moteurs avec le YAML livré.

**Acceptance Criteria:**
- Given le YAML livré et une clé, when `PseudonymiseurPresidio` et `PseudonymiseurHmac` pseudonymisent une même description générée, then ils produisent les mêmes jetons pour chaque identifiant et laissent les clés de ticket intactes.
- Given les identifiants injectés de `generer` sur les graines du programme réduit, when on pseudonymise toutes les descriptions avec chaque moteur, then aucun identifiant injecté ne subsiste.
- Given un texte pseudonymisé par Presidio, when on appelle `reidentifier`, then le texte d'origine revient via la table SQLite ; `apercu` ne l'écrit pas.
- Given la suite de contrat `Pseudonymiseur`, when elle tourne sur factice, hmac et presidio, then elle passe.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 9 findings — high 0, medium 3, low 4, false 1, maybe-false 1
- findings:
  - `[medium]` `[patch]` Entité spaCy partiellement chevauchante écartée en entier, sa partie hors plage maison fuit — corrigé : fragments hors plages maison gardés via `fragments_hors_cles`, test dédié.
  - `[maybe-false]` `[defer]` Délai regex Presidio dépassé → détection sautée silencieusement — à trancher en lisant `PatternRecognizer` ; reporté (medium non vérifié).
  - `[low]` `[reject]` Texte au-delà de `nlp.max_length` (10^6 caractères) → ValueError brute — les descriptions sont loin de cette taille ; le garde ajouterait une branche.
  - `[false]` `[reject]` Modèle spaCy exigé même sans `entites_presidio` — voulu : le moteur Presidio repose sur spaCy (AD-15) ; le repli sans modèle est le moteur regex.
  - `[medium]` `[patch]` Entité de `entites_presidio` non produite par le moteur NLP jamais détectée, sans erreur — corrigé : `UsineErreur` si absente de `get_supported_entities()`, test dédié.
  - `[low]` `[patch]` Type maison égal à une entité Presidio : déduplication Presidio absorbe le résultat maison — corrigé : intersection refusée par `UsineErreur`, test dédié.
  - `[low]` `[reject]` Motif CLIENT sans prénom capitalisé ou avec apostrophe typographique — le générateur (FR-4) ne produit pas ces formes ; PERSON spaCy sert de filet sous Presidio.
  - `[low]` `[reject]` `avec_table` partage l'analyseur entre usages concurrents — aucun usage concurrent dans la Chaîne ; garde sans état démontré.
  - `[medium]` `[defer]` Presidio non branché dans la composition (moteur du Palier 2 de nom seulement) — exige une clé dans `ConfigPseudonymisation` gelée ; reporté à Anaël.

## Design Notes

AC « `apercu` renvoie le couple original / pseudonymisé » : le port gelé renvoie `str` (texte pseudonymisé) ; l'original est l'argument, le couple se forme côté UI. Pas de changement de port.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert.

## Auto Run Result

Status: done

- **Changement :** base `PseudonymiseurDerive` extraite d'`adaptateurs/pseudonymisation` (dérivation HMAC, clés de ticket, regroupement, table) ; nouvel adaptateur `adaptateurs/presidio` (`PseudonymiseurPresidio` : reconnaisseurs maison + entités spaCy, priorité maison, aucun téléchargement) ; `config/pseudonymisation.yaml` (COMPTE, CLIENT, ID_CLIENT, PERSON).
- **Fichiers :** `src/usine/adaptateurs/pseudonymisation/__init__.py` (base commune, `verifier_types_jeton`, `avec_table`) ; `src/usine/adaptateurs/presidio/__init__.py` (moteur Presidio) ; `config/pseudonymisation.yaml` (reconnaisseurs FR-4) ; `tests/contrat/pseudonymiseur/fabriques.py` (fabrique presidio) ; `tests/unit/adaptateurs/presidio/test_presidio.py` (matrice, parité des moteurs, balayage SM-7) ; `tests/unit/contrats/test_config.py` (YAML livré attendu).
- **Revue (Edge Case Hunter seul, mode économique) :** 3 correctifs (2 medium, 1 low), 2 reports, 4 rejets (motifs dans le triage).
- **Revue de suivi :** recommandée par la règle (2 medium corrigés) ; risque à vérifier : le découpage des entités spaCy autour des plages maison sur des textes réels. Non lancée (mode économique, aucun high).
- **Vérification :** ruff check, ruff format --check, mypy, lint-imports (13 contrats) et pytest -q (2368 passés, 1 sauté) verts.
- **Risques résiduels :** Presidio non branché dans la composition (clé de moteur absente des contrats gelés) ; CI Ubuntu/Windows pas encore exécutée sur cette lane (dépendances déjà verrouillées).
