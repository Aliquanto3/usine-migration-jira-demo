---
title: 'Story 8.1 : fiche « outillage demandé » et note de portage courte'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '0714669752662ca46ca4afecbf08fc62b4bd2463'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-8-context.md'
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Le Sponsor n'a aucun document qui dit quel outillage accorder, dans quel ordre, et comment chaque brique de la démo se porte sur ses outils (FR-47, NFR-8). La Story 7.5 doit afficher ce document tel quel.

**Approach:** Rédiger `docs/fiche-outillage.md`, une page en Markdown simple et en français. Elle contient la liste priorisée des demandes (spec § 8), le tableau de correspondance par brique, complété d'une ligne UI et d'une colonne « Appui dans le dépôt » qui renvoie chaque affirmation de portabilité à AD-1, AD-19 ou NFR-8, puis les points d'attention par cible. Un test unitaire de la lane garde la fiche dans ces bornes.

## Boundaries & Constraints

**Always:** écrire seulement dans `docs/` et `tests/unit/docs/` (lane L8, AD-21). Reprendre mot pour mot les 7 lignes et les 4 colonnes cibles du tableau de la spec § 8 (addendum § G). Chaque affirmation de portabilité cite AD-1, AD-19 ou NFR-8 et nomme le contrôle qui la vérifie (`lint-imports`, chargeur de `usine.config`, gitleaks, CI Windows et Linux). Le fichier se lit seul (lien relatif vers le spine et le PRD au plus, aucun HTML).

**Never:** aucun nom réel de client, d'entreprise cliente ou de personne. Aucune promesse que le dépôt ne tient pas aujourd'hui (pas de conteneur : c'est la Story 8.3 ; pas de mode LLM local livré : bonus FR-37). Ne pas toucher `src/`, `config/`, `tests/depot/`, ni `contrats/` ou `ports/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Fiche conforme | `docs/fiche-outillage.md` présent | le test passe : ≤ 700 mots, 4 demandes numérotées, les 8 briques et les 4 cibles présentes, AD-1, AD-19 et NFR-8 cités | No error expected |
| Fiche trop longue | > 700 mots | le test échoue en donnant le nombre de mots | message d'assertion explicite |
| Brique ou cible manquante | une ligne ou une section de cible supprimée | le test échoue en nommant l'élément manquant | message d'assertion explicite |

</intent-contract>

## Code Map

- `SPEC-usine-migration-jira-demo.md` § 8 (l. 140-157) -- source du tableau par brique et de la liste priorisée (lecture seule).
- `_bmad-output/planning-artifacts/architecture/architecture-usine-migration-jira-demo-2026-10-10/ARCHITECTURE-SPINE.md` -- AD-1 (l. 68), AD-19, AD-21 ; « NFR-8 est tenu par AD-1 et AD-19 » (lecture seule).
- `_bmad-output/implementation-artifacts/epic-8-context.md` -- énoncés exacts FR-47, NFR-8, AD-1, AD-19 et faits citables (Cloud/DC par configuration, LLM derrière un port unique, Palier 1 sans LLM).
- `pyproject.toml` `[tool.importlinter]` (l. 87+) -- contrôle de AD-1 (`uv run lint-imports`).
- `src/usine/config/chargeur.py`, `src/usine/config/secrets.py` -- contrôle de AD-19 (configuration `config/*.yaml`, secrets par variables d'environnement).
- `.github/workflows/ci.yml` -- matrice `ubuntu-latest` / `windows-latest`, `lint-imports`, gitleaks : preuve de NFR-8 (poste seul, sans service propriétaire).
- `src/usine/ui/` -- UI Streamlit (ligne UI du tableau) ; `tests/depot/test_controle_lanes.py:131` attend déjà `docs/fiche-outillage.md` dans la lane 8.
- `tests/unit/chaine/__init__.py` -- modèle de paquet de tests miroir ; trouver la racine par `Path(__file__).resolve().parents[3]`.

## Tasks & Acceptance

**Execution:**
- `docs/fiche-outillage.md` -- créer la fiche : titre, une phrase d'objet ; § « Demandes, par ordre de priorité » (4 items de la spec § 8, « validé par la banque » remplacé par « validé par le client ») ; § « Correspondance par brique » (7 lignes de la spec + ligne « UI de démo (Streamlit) », colonne « Appui dans le dépôt ») ; § « Points d'attention par cible » (VM Python, Dataiku, Power Platform, poste seul, 2 ou 3 puces chacune) ; ligne finale de références (AD-1, AD-19, NFR-8 et leurs contrôles) -- FR-47, NFR-8.
- `tests/unit/docs/__init__.py` -- créer (vide) -- paquet de tests miroir de `docs`.
- `tests/unit/docs/test_fiche_outillage.py` -- tester les bornes de la matrice : nombre de mots (`re.findall(r"\w+", texte)`) ≤ 700, 4 demandes numérotées, présence des 8 libellés de brique et des 4 cibles, présence de `AD-1`, `AD-19`, `NFR-8` -- empêche une régression silencieuse avant la Story 7.5.

**Acceptance Criteria:**
- Given `docs/fiche-outillage.md`, when on l'ouvre, then elle tient en une page (≤ 700 mots) et contient la liste priorisée, le tableau par brique (extraction, calcul, Météo, Prévision, rendu, LLM, UI) et les points d'attention pour VM Python, Dataiku, Power Platform et poste seul.
- Given la fiche, when on la relit, then elle ne contient aucun nom réel de client et chaque affirmation de portabilité renvoie à AD-1, AD-19 ou NFR-8 avec le contrôle qui la vérifie.
- Given la branche `lane/8-portage`, when on lance `controle_lanes.py --branche lane/8-portage --base main`, then tous les fichiers modifiés sont dans la lane.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 35 findings — high 0, medium 10, low 22, false 3, maybe-false 0
- findings:
  - `false` `reject` (verification-gap) Tableau non repris tel quel sans justification — la dérogation (ligne UI, colonne Appui, « banque » → « client ») est justifiée dans les Design Notes de la spec.
  - `low` `patch` (intent) Puce Power Platform « calcul peu maintenable ; Prévision sans équivalent » sans règle — renvoi ajouté au tableau de la spec § 8 et à AD-1.
  - `low` `patch` (intent) Palier 1 sans LLM rattaché à NFR-8 seul — FR-28 ajouté.
  - `false` `reject` (intent) FR-37 hors du jeu AD-1/AD-19/NFR-8 — la puce dit qu'un mode n'est pas livré, ce n'est pas une affirmation de portabilité.
  - `medium` `patch` (intent) Le test ne rattache pas chaque affirmation à une règle — groupe « tests » : chaque cellule Appui doit citer AD-1, AD-19 ou NFR-8.
  - `low` `reject` (intent) « une page » mesuré en mots et non en rendu — proxy assumé par la spec ; mesurer le rendu ajouterait un outil de rendu.
  - `low` `reject` (intent) Libellés de briques de la spec et non ceux de l'AC — choix documenté (Design Notes).
  - `low` `reject` (intent) Pas de test de puces sous chaque cible — contenu relu par l'humain (Story 8.2), garde-fou supplémentaire sans dommage nommé.
  - `low` `reject` (intent) Aucun nom réel de client non testé — impossible sans lister les noms dans un dépôt public ; relecture humaine (AC « quand on la relit »).
  - `false` `reject` (blind) Écart au « tel quel » non consigné — même réfutation que la première ligne.
  - `low` `patch` (blind) Contradiction LLM local / Agent ✅ sur poste seul — puce « l'Agent en dépend aussi » ajoutée.
  - `low` `patch` (blind) Références : FR-28 au lieu de NFR-8, FR-7 absent — FR-28 ajouté ; FR-7 non requis par l'AC.
  - `medium` `patch` (blind) Affirmations au présent sur des briques non livrées (adaptateurs Jira, LLM, Agent) — groupe « promesses » : phrase sous le tableau et « Le code livré tourne sans adaptation ».
  - `medium` `patch` (blind) Pseudonymisation avant tout appel LLM absente — ajoutée dans la cellule Appui de la ligne LLM (`USINE_CLE_PSEUDO`, AD-19) ; mention d'une offre LLM nommée non retenue.
  - `medium` `patch` (blind) VM Python : proxy, TLS, miroir PyPI, droits du compte absents — ajoutés à la première puce.
  - `medium` `patch` (blind) Dataiku : adaptateurs de stockage et de sortie à réécrire, une composition par recette — ajouté.
  - `low` `patch` (blind) Liens relatifs morts dans l'UI de la Story 7.5 — remplacés par des chemins entre backticks ; codes internes gardés, l'AC les exige.
  - `medium` `patch` (blind) Test de référence global, pas par affirmation — groupe « tests ».
  - `low` `reject` (blind) Pas de garde « banque » — mot de secteur, pas un nom de client.
  - `low` `reject` (blind) Pas de test de résolution des liens — sans objet, les liens sont supprimés.
  - `low` `patch` (blind) Pas de contrôle des 6 cellules ni de l'en-tête — groupe « tests ».
  - `low` `reject` (blind) Comptage par mots imparfait et seuil 700 non justifié — proxy assumé par la spec, marge connue (694 mots).
  - `low` `reject` (blind) BRIQUES sans correspondance avec les termes de l'AC — choix documenté (Design Notes).
  - `low` `patch` (blind) `_section` par préfixe — comparaison exacte de la première ligne.
  - `low` `reject` (blind) Le contexte d'epic ne précise pas le journal M7 de la Story 8.2 — la Story 8.2 le tranchera ; aucun dommage pour 8.1.
  - `low` `patch` (edge) Ligne de brique tronquée acceptée — groupe « tests » : 6 cellules non vides.
  - `low` `patch` (edge) En-tête du tableau non vérifié — `test_entete_du_tableau` ajouté.
  - `low` `patch` (edge) Sections de même préfixe — même correctif que `_section`.
  - `medium` `patch` (edge) Référence non exigée par cellule Appui — groupe « tests ».
  - `low` `reject` (edge) Garde « banque » — même raison que plus haut.
  - `medium` `patch` (edge) « date et graine en paramètre (`lint-imports`) » faux : `datetime` non interdit — reformulé en « domaine sans I/O ni `random`, graine passée en paramètre ».
  - `medium` `patch` (edge) Extraction Cloud/DC présentée comme livrée — groupe « promesses ».
  - `medium` `patch` (edge) Agent présenté comme branché sur le port LLM alors qu'il est une ébauche — groupe « promesses ».
  - `low` `patch` (edge) Fournisseur LLM « branché dans composition.py » sans adaptateur livré — groupe « promesses ».
  - `low` `patch` (edge) « seule composition.py » contredit AD-1 (modules `cli`) — corrigé en « seuls `composition.py` et les modules `cli` ».

### 2026-10-12 — Review pass (revue de suivi)
- verdicts: 27 findings — high 0, medium 2, low 21, false 4, maybe-false 0 ; 12 `carried` (verdict de la passe précédente conservé)
- findings:
  - `low` `reject` (intent) Les cellules du tableau ne sont pas comparées à la spec § 8, seulement leur présence — comparer au texte de la spec ajouterait une lecture hors lane et un parseur ; contenu relu par l'humain (Story 8.2).
  - `false` `reject` (intent) « validé par le client » s'écarte de la spec — carried : écart documenté dans les Design Notes, la contrainte « mot pour mot » ne vise que le tableau.
  - `low` `reject` (intent) Le test ne vérifie pas qu'un contrôle est nommé par affirmation, ni les puces — carried : relecture humaine, garde-fou sans dommage nommé.
  - `false` `reject` (intent) La fiche citerait `config/llm.yaml` et `usine.ui.cli` échapperait au contrat UI — la fiche ne cite pas `config/llm.yaml` ; `usine.ui.cli` n'importe aucun `usine.adaptateurs` en direct (imports : composition, config, consultation, contrats, ports).
  - `low` `reject` (intent) Ni HTML ni noms de client testés — carried : impossible sans lister des noms dans un dépôt public.
  - `low` `reject` (intent) « Une page » mesurée en mots — carried : proxy assumé par la spec.
  - `medium` `patch` (blind) Dataiku : « Stockage SQLite » omet l'entrepôt DuckDB (`donnees/entrepot.duckdb`, spine l. 131), le stockage principal à porter — remplacé par « Entrepôt DuckDB, bases SQLite et fichiers Excel/PPT ».
  - `low` `reject` (blind) Cellule Agent ✅ en poste seul contredite par la puce — carried : cellule de la spec reprise mot pour mot, la puce « l'Agent en dépend aussi » nuance déjà.
  - `low` `patch` (blind) Pseudonymisation rattachée à AD-19 et gitleaks, qui ne la vérifient pas — déplacée sous AD-1 (passerelle `usine.ia`, `lint-imports`) ; AD-19 ne porte plus que les clés, dont `USINE_CLE_PSEUDO` (gitleaks).
  - `low` `reject` (blind) Rien sur Jira Data Center, « jeton API » au vocabulaire Cloud — la demande 1 reprend la spec mot pour mot et la ligne Extraction nomme Data Center.
  - `medium` `patch` (blind) Le modèle spaCy `fr_core_news_md` est un wheel hébergé sur GitHub (`pyproject.toml` l. 23) : un miroir PyPI ne suffit pas, `uv sync` échoue sur une VM fermée — accès GitHub au modèle ajouté à la première puce VM.
  - `low` `reject` (blind) Power Platform ne dit pas qu'il faut aussi l'environnement Python — la demande 2 le couvre et les puces disent « garder l'extraction en Python ».
  - `low` `reject` (blind) Liste des demandes sans proxy ni miroir — liste reprise de la spec § 8 ; les prérequis sont aux points d'attention VM.
  - `low` `reject` (blind) Phrase sous le tableau annonçant des briques en construction — carried : correctif « promesses » de la passe précédente.
  - `low` `reject` (blind) Aucun test NFR-4 (noms de client) — carried.
  - `low` `reject` (blind) Contenu de la spec § 8 non testé — même raison que la première ligne.
  - `low` `reject` (blind) Proxy « une page » en mots — carried.
  - `low` `reject` (blind) Libellés de briques sans correspondance avec l'AC — carried : choix documenté (Design Notes).
  - `low` `patch` (edge) `_section` lève `IndexError` sur un premier morceau vide — `morceau.partition("\n")[0]` remplace `splitlines()[0]`.
  - `low` `reject` (edge) Section en double non détectée — ajoute une garde pour un cas jamais rencontré.
  - `low` `reject` (edge) Pipe échappé dans une cellule — aucune cellule n'en contient ; le parseur serait plus complexe.
  - `low` `reject` (edge) Titre de cible avec espace final — garde sans cas réel.
  - `low` `reject` (edge) Largeur du tableau non bornée — carried : proxy « une page » en mots.
  - `false` `reject` (edge) Le chargeur de `usine.config` ne validerait pas `config/jira.yaml` ni les autres YAML — `composition.py` charge `jira.yaml`, `chaine.yaml`, `programme.yaml` et la grille par `usine.config.charger_yaml` avec leur modèle (l. 174, 206-215).
  - `low` `patch` (edge) Pseudonymisation attribuée à gitleaks — même entrée que la ligne blind correspondante.
  - `false` `reject` (edge) Bascule Data Center présentée comme livrée — carried : la clé `mode: Literal["cloud", "dc"]` existe dans `ConfigJira`, la phrase sous le tableau signale l'extraction en construction.
  - `low` `reject` (edge) Marge de 6 mots — carried ; la fiche compte 696 mots après correctifs.

## Design Notes

Le tableau de la spec ne nomme pas toutes les briques de la story : « KPI, météo » couvre le calcul et la Météo, « Excel / PPT » le rendu, « Agent conversationnel » l'Agent ; seule l'UI manque. On ajoute donc une ligne au lieu de renommer celles de la spec, ce qui respecte « reprendre tel quel » (addendum § G) et l'AC de la story. Le dépôt étant public, « la banque » devient « le client » : la fiche s'adresse au Sponsor de tout client.

## Verification

**Commands:**
- `uv run pytest -q tests/unit/docs` -- expected: tous les tests passent.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: succès.
- `uv run python .github/scripts/controle_lanes.py --branche lane/8-portage --base main` -- expected: « tous les fichiers modifiés sont dans la lane ».

## Auto Run Result

Status: done

**Résumé :** `docs/fiche-outillage.md` livre la fiche « outillage demandé » d'une page (694 mots) : 4 demandes priorisées, tableau par brique de la spec § 8 complété d'une ligne UI et d'une colonne « Appui dans le dépôt » qui rattache chaque brique à AD-1, AD-19 ou NFR-8 et à son contrôle, points d'attention pour VM Python, Dataiku, Power Platform et poste seul. Un test de la lane en garde la structure.

**Fichiers :**
- `docs/fiche-outillage.md` -- la fiche (FR-47, NFR-8).
- `tests/unit/docs/__init__.py` -- paquet de tests miroir de `docs`.
- `tests/unit/docs/test_fiche_outillage.py` -- 18 tests : longueur, demandes, en-tête et lignes du tableau avec règle par cellule Appui, cibles, références.
- `_bmad-output/implementation-artifacts/epic-8-context.md` -- contexte compilé de l'Epic 8.

**Revue :** 35 constats ; 21 corrigés (10 medium, 11 low, regroupés en 12 correctifs), 0 différé, 14 rejetés (3 false, 11 low, raisons au Review Triage Log).

**Revue de suivi recommandée :** oui, car plusieurs entrées medium ont été corrigées (groupe « promesses », pseudonymisation, VM Python, Dataiku, Prévision, groupe « tests »). Risque non vérifié : aucune couche indépendante n'a relu les points d'attention réécrits pour Dataiku et la VM. Corrigés par verdict d'entrée : high 0, medium 6, low 6.

**Vérification :** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports` OK ; `uv run pytest -q` : 991 passed, 1 skipped ; `controle_lanes.py --branche lane/8-portage --base main` : tous les fichiers dans la lane.

**Risques résiduels :** la fiche compte 694 mots pour une limite de 700. Les cellules Dataiku et Power Platform de la ligne UI sont des jugements, à confirmer à la validation M7 (Story 8.2). Aucun contrôle automatique ne détecte les noms de client : seule la relecture les écarte.

### Revue de suivi (2026-10-12)

**Résumé :** quatre couches (blind, edge, verification-gap, intent) ont relu la fiche et son test, en particulier les points d'attention Dataiku et VM réécrits par la première revue. Quatre entrées corrigées : le stockage Dataiku nomme l'entrepôt DuckDB en plus des bases SQLite ; la VM demande aussi l'accès GitHub au wheel spaCy `fr_core_news_md`, qu'un miroir PyPI ne sert pas ; la pseudonymisation de la ligne LLM est rattachée à AD-1 et à la passerelle `usine.ia` au lieu de gitleaks ; `_section` du test ne lève plus `IndexError` sur un morceau vide. Deux phrases resserrées pour rester sous 700 mots.

**Fichiers :**
- `docs/fiche-outillage.md` -- points d'attention Dataiku et VM, cellule Appui de la ligne LLM, phrase d'objet et deux puces resserrées (696 mots).
- `tests/unit/docs/test_fiche_outillage.py` -- `_section` robuste à un morceau vide.

**Revue :** 27 constats ; 5 corrigés en 4 correctifs (2 medium, 3 low, dont un doublon blind/edge), 0 différé, 22 rejetés (4 false, 18 low, raisons au Review Triage Log). Aucun nom réel de client dans la fiche.

**Revue de suivi recommandée :** non. Passe de suivi sans correctif high : le travail a convergé. Corrigés par verdict d'entrée : high 0, medium 2, low 2.

**Vérification :** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports` (13 contrats tenus) OK ; `uv run pytest -q` : 991 passed, 1 skipped ; `controle_lanes.py --branche lane/8-portage --base main` : tous les fichiers dans la lane.

**Risques résiduels :** marge de 4 mots sous la limite de 700. Les cellules Dataiku et Power Platform de la ligne UI restent des jugements à confirmer à la validation M7 (Story 8.2).
