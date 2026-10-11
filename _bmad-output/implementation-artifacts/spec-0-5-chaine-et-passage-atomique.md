---
title: 'Story 0.5 (E0-5) : Chaîne et Passage atomique'
type: 'feature'
created: '2026-10-11'
status: 'done'
baseline_revision: 'e4fbc43850d7c8e5ebd77dfe62a78297d8baeed2'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-0-context.md'
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Le calcul de la Météo existe, mais aucune commande ne l'enchaîne ni ne publie de Passage. `usine rapport` n'a pas de commande, et rien ne garantit un Passage complet ou rien, la progression, le verrou ou l'échec propre (Story 0.5 de `epics.md` ; amorce de FR-25 ; mesure NFR-2).

**Approach:** `usine.chaine` exécute un registre `dict[Etape, ports.Etape]` construit par `composition.py`. L'`EcrivainPassage`, seul écrivain, construit le Passage dans `.en-cours-<passage_id>/` puis le publie par un seul renommage, tient la progression hors Passage et prend le verrou. Les étapes déterministes réelles (instantanés, Météo) enveloppent le domaine ; les étapes LLM sont `sautee` en Palier 1 ; les autres sont des bouchons. Un lecteur de Passage minimal, dans `usine.consultation`, sert aux étapes en attendant la Story 0.6.

## Boundaries & Constraints

**Always:**
- Seule `chaine` écrit dans le Passage (AD-22). Les étapes renvoient un `ResultatEtape` et lisent les sorties précédentes via `ctx.consultation`.
- Disposition des fichiers (AD-7, AD-8) :
  - construction dans `sorties/passages/.en-cours-<passage_id>/` ;
  - publication par un seul `rename` vers `sorties/passages/<date_arrete>/<passage_id>/` ;
  - en échec, déplacement sous `sorties/echecs/<passage_id>/`, sans fichier de rapport publié ;
  - progression dans `sorties/progression/<passage_id>.jsonl`, une ligne `EvenementProgression` par début (`en_cours`) et par fin (`reussie`, `sautee` ou `echouee`) d'étape, en ouvrir-ajouter-fermer.
- `passage_id` = `former_passage_id(horodatage_debut, secrets.token_hex(3))`. Le manifeste (`ManifestePassage`) est écrit en dernier, avec une `ExecutionEtape` par étape, `version_grille`, `version_donnees` et `nb_tickets`.
- Écriture des sorties :
  - une table : validée par le `SCHEMA_X` du nom de fichier, puis écrite en Parquet avec la métadonnée `contrats_version` ;
  - un JSON de `CONTENUS_JSON` : écrit dans une `EnveloppeFichier` ;
  - des `bytes` : écrits tels quels ;
  - les `EntreeTrace` : ajoutées à `trace/llm.jsonl` (traces LLM) ou à `trace/previsions.jsonl` (traces de prévision).
- Verrou exclusif `donnees/.verrou-passage`, créé atomiquement et toujours rendu (succès comme échec). S'il est déjà pris : `UsineErreur` qui nomme le chemin du verrou.
- Date d'arrêté : `--date-arrete AAAA-MM-JJ`, ou par défaut `dernier_jour_ouvre_ecoule(jour_local(maintenant))`. Une date non ouvrée ou mal formée lève une `UsineErreur` qui la nomme.
- Échec d'une étape (toute exception) : code de sortie non nul, message qui nomme l'étape. Une `UsineErreur` garde son message d'origine dans le message final.
- Palier : lu seulement dans `ConfigChaine.palier` (via `ConfigUsine`). En Palier 1, les étapes `classification`, `repartition_causes`, `explications` et `narration` sont `sautee`.
- `composition.py` est le seul lieu qui instancie `SourceJournal`, lit `config/*.yaml` (`chaine`, `programme`, `grille_meteo`) et calcule `version_grille` et `version_donnees`.

**Never:**
- Modifier `src/usine/contrats/`, `src/usine/ports/`, `pyproject.toml`, `uv.lock` ; ajouter une dépendance.
- Écrire un fichier du Passage hors de `chaine`, ou un fichier de progression dans le Passage.
- Implémenter le rendu Excel/PowerPoint, la Consultation complète (Story 0.6), l'extraction Jira ou DuckDB (L2), les KPI, la Prévision ou les étapes LLM.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Passage publié | Journal (graine 42, 2026-10-12) ; `usine rapport --date-arrete 2026-10-09` | répertoire `sorties/passages/2026-10-09/<id>/` avec `manifeste.json`, `tickets_etats.parquet`, `instantanes.parquet`, `indicateurs.parquet`, `meteo.json` ; aucun `.en-cours-*` restant ; code 0 | N/A |
| Identifiant | tout Passage | `passage_id` conforme à `AAAAMMJJTHHMMSSZ-<6 hex>` | N/A |
| Manifeste | Passage publié | dix `ExecutionEtape` dans l'ordre d'AD-8, LLM `sautee` en Palier 1, horodatages de début et de fin par étape | N/A |
| Progression | Passage publié | `sorties/progression/<id>.jsonl` : une ligne `en_cours` puis une ligne finale par étape, dans l'ordre | N/A |
| Autoportance | Passage publié | `meteo.json` porte une `MeteoEntite` par Entité et par Jour ouvré entre le premier jour de l'historique et la Date d'arrêté | N/A |
| Échec d'étape | étape `kpi` remplacée par une étape qui lève `RuntimeError` | répertoire sous `sorties/echecs/<id>/`, rien sous `sorties/passages/<date>/`, ligne `echouee` dans la progression, code ≠ 0, message nommant `kpi` | `UsineErreur` |
| Samedi | `--date-arrete 2026-10-10` | message nommant 2026-10-10, code 1, aucun répertoire créé | `UsineErreur` |
| Date mal formée | `--date-arrete 2026-13-01` | message nommant la valeur, code 1 | `UsineErreur` |
| Verrou pris | `donnees/.verrou-passage` déjà présent | message nommant le verrou, code 1, verrou laissé intact | `UsineErreur` |
| Verrou rendu | après succès comme après échec d'étape | `donnees/.verrou-passage` absent | N/A |
| Journal absent | aucun `donnees/journal.jsonl` | message nommant le fichier, code 1 | `UsineErreur` |
| Jours sans ticket | Date d'arrêté et premiers jours de l'historique sans aucun ticket créé | Météo verte pour ces jours (pas d'erreur de date absente) | N/A |
| Sortie hors schéma | étape qui renvoie une table non conforme | échec de l'étape nommée, Passage sous `echecs/` | `UsineErreur` |

</intent-contract>

## Code Map

- `src/usine/contrats/passage.py` -- `Etape` (ordre AD-8), `StatutEtape`, `EvenementProgression`, `ExecutionEtape` (statut final `reussie`/`sautee`), `ManifestePassage`, `FICHIERS_PASSAGE`, `CONTENUS_JSON`, `chemin_fichier_passage`, `former_passage_id`, `EnveloppeFichier`, `lire_enveloppe`, `ContextePassage` (`palier` = `configuration.chaine.palier`), `ResultatEtape` (vérifie noms et types JSON).
- `src/usine/contrats/versions.py` -- `CLE_VERSION`, `version_grille(octets)`, `version_donnees(journal, horodatage_extraction)`, `verifier_version`.
- `src/usine/contrats/config.py` -- `ConfigUsine(chaine, programme, grille_meteo, …)`, `ConfigProgramme.entites`.
- `src/usine/contrats/calendrier.py` -- `jours_ouvres`, `est_jour_ouvre`, `dernier_jour_ouvre_ecoule`, `jour_local`.
- `src/usine/contrats/schemas.py` -- `valider`.
- `src/usine/ports/etape.py`, `src/usine/ports/consultation.py` -- `Etape.executer(ctx: ContextePassage[Consultation])` et les lectures du port.
- `src/usine/adaptateurs/journal/__init__.py` -- `SourceJournal(chemin)` ; `.entete.ancrage_semaines` donne le premier jour de l'historique.
- `src/usine/domaine/instantanes.py` -- `tickets_etats(evenements, dates)`, `instantane(etats)`.
- `src/usine/domaine/meteo.py:90-105` -- `_mesures` : la garde « Date d'arrêté absente » refuse aujourd'hui une date sans ticket. La remplacer par : `UsineErreur` seulement si `date_arrete` est postérieure à la dernière date de la table (états non calculés jusque-là). Une date sans ligne avant ou dans la plage signifie « aucun ticket », donc vert. Adapter `test_date_d_arrete_absente_de_l_etat` en conséquence.
- `src/usine/chaine/cli.py` -- sous-application `rapport` (callback seul) : en faire la commande `usine rapport [--date-arrete]` (`invoke_without_command=True`, sans `no_args_is_help`).
- `src/usine/cli.py` -- `main()` traduit `UsineErreur` en code 1 ; ne pas modifier.
- `src/usine/composition.py` -- vide ; y construire configuration, source, registre et Consultation.
- `config/chaine.yaml` -- `palier: 1` ; ne changer que les commentaires si besoin.
- `src/usine/generateur/cli.py` -- écrit `donnees/journal.jsonl` par défaut : chemin du Journal lu par la composition.
- `tests/contrat/consultation/` -- suite vide : ne pas y enregistrer le lecteur minimal (Story 0.6).

## Tasks & Acceptance

**Execution:**
- `src/usine/chaine/ecrivain.py` -- `EcrivainPassage(racine_sorties)` : création de `.en-cours-<id>`, `ecrire(sorties)`, `ajouter_traces`, `progression(etape, statut, message)`, `publier(manifeste)` (manifeste puis renommage), `abandonner()` (déplacement vers `echecs/`).
- `src/usine/chaine/verrou.py` -- verrou exclusif par création atomique (`os.open` avec `O_CREAT | O_EXCL`), gestionnaire de contexte qui le rend dans tous les cas.
- `src/usine/chaine/etapes.py` -- `EtapeInstantanes(source, premier_jour)` (sorties `tickets_etats`, `instantanes`), `EtapeMeteo(grille, version_grille, entites, premier_jour)` (lit `tickets_etats` via `ctx.consultation`, sorties `indicateurs` et `meteo` pour chaque Jour ouvré de `premier_jour` à la Date d'arrêté), `EtapeBouchon` (`reussie`, sans sortie), `EtapeSautee` (`sautee`).
- `src/usine/chaine/execution.py` -- `executer_passage(registre, configuration, date_arrete, ecrivain, fabrique_consultation, horloge, alea) -> ManifestePassage` : boucle dans l'ordre d'`Etape`, progression, écriture, `ExecutionEtape`, manifeste, publication ; en échec, ligne `echouee`, `abandonner()`, `UsineErreur` qui nomme l'étape. L'horloge et l'aléa sont injectés (testables).
- `src/usine/consultation/passage.py` -- `ConsultationPassage(repertoire)` minimal : `tickets_etats(date_arrete=None)` lit et valide `tickets_etats.parquet` (version de la métadonnée vérifiée) ; les autres lectures du port lèvent `UsineErreur("lecture disponible à la Story 0.6")`.
- `src/usine/domaine/meteo.py` -- garde de date amendée (voir Code Map).
- `src/usine/composition.py` -- `construire_rapport(racine) -> ...` : charge `chaine`, `programme`, `grille_meteo` (`charger_yaml`), calcule `version_grille` (octets du YAML) et `version_donnees` (octets du Journal, `None`), instancie `SourceJournal(donnees/journal.jsonl)` et construit le registre (Palier 1 : LLM `sautee` ; `extraction`, `kpi`, `prevision`, `rendu` en bouchon).
- `src/usine/chaine/cli.py` -- commande `usine rapport [--date-arrete]` : date par défaut, refus d'un jour non ouvré, verrou, exécution, affichage du chemin publié.
- `outils/mesurer_nfr2.py` -- génère un Journal à la volumétrie cible (10 Entités, 5 000 Anomalies, 8 semaines) dans un répertoire temporaire, exécute la Chaîne en Palier 1 et affiche la durée de chaque étape et la durée totale.
- `README.md` -- section « Performance (NFR-2) » : durées mesurées par étape, caractéristiques du poste, écart à la cible de 5 minutes signalé s'il existe.
- `tests/unit/chaine/test_ecrivain.py`, `test_verrou.py`, `test_execution.py`, `test_cli.py`, `tests/unit/consultation/test_passage.py`, `tests/unit/domaine/test_meteo.py` -- matrice I/O dans `tmp_path`, horloge figée.

**Acceptance Criteria:**
- Given un Journal généré et la configuration livrée, when `usine rapport --date-arrete 2026-10-09` tourne deux fois, then deux Passages distincts sont publiés, et leurs `meteo.json` et Parquet sont identiques hors des champs d'`EXCLUSIONS_REJEU`.
- Given `outils/mesurer_nfr2.py`, when l'auteur le lance, then il affiche une durée par étape, et le README consigne ces durées avec le poste.
- Given le dépôt, when `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest`, then tout passe.

## Spec Change Log

## Review Triage Log

### 2026-10-11 — Review pass
- verdicts: 43 findings — high 0, medium 5, low 35, false 3, maybe-false 0
- findings:
  - `[low]` `[reject]` (intention) Écritures hors de « Écrit dans » (garde du domaine, lecteur minimal, outil) — exigées par la spec (lecteur pour `ContextePassage`, suivi de la Story 0.4, mesure NFR-2).
  - `[low]` `[reject]` (intention) Pas de test de deux processus concurrents — l'exclusion vient de `O_CREAT | O_EXCL`, garantie par le système ; le test du fichier présent couvre le refus.
  - `[low]` `[reject]` (intention) Aucune lecture de la progression par une UI — c'est la Story 0.8.
  - `[low]` `[reject]` (intention) Aucun fichier de rapport retenu en échec, faute de rendu — le rendu arrive en Story 0.6 ; l'absence de publication sous `passages/` est testée.
  - `[false]` `[reject]` (intention) Durée des étapes non portée par le manifeste — elle se déduit des horodatages de chaque `ExecutionEtape` (propriété `duree`).
  - `[low]` `[patch]` (intention) Refus du samedi seulement en CLI — `verifier_date_arrete` appelée aussi par `lancer_rapport`.
  - `[low]` `[reject]` (intention) NFR-2 mesuré en processus et non par la commande — la mesure couvre composition et Chaîne ; le démarrage de la CLI est négligeable devant la cible.
  - `[false]` `[reject]` (intention) Deux étapes réelles sur six — l'AC dit « autres étapes en bouchon ».
  - `[low]` `[reject]` (intention) Branche Palier 2 non exercée — les étapes LLM arrivent en Story 0.7.
  - `[false]` `[reject]` (intention) Date par défaut ajoutée — exigée par FR-25 (« sans option, le dernier Jour ouvré écoulé »).
  - `[low]` `[patch]` (verification-gap) `nb_tickets` vérifié `> 0` seulement — comparé à la table publiée.
  - `[low]` `[patch]` (verification-gap) Échecs de publication et d'abandon non testés — `test_echec_de_publication`, `test_abandon_en_panne_garde_l_erreur_d_etape`.
  - `[low]` `[patch]` (verification-gap) `lancer_rapport` n'impose pas un Jour ouvré — garde ajoutée.
  - `[medium]` `[patch]` (blind) Garde Météo ambiguë pour une date non calculée — précondition documentée (états calculés pour chaque Jour ouvré, comme le fait `EtapeMeteo`) ; aucun appelant actuel ne laisse de trou.
  - `[low]` `[patch]` (blind) Échec après la boucle sans ligne de progression — libellé « publication du Passage » et test ; une ligne `echouee` exigerait une `Etape` hors énumération (contrat), donc rejetée.
  - `[low]` `[patch]` (blind) Libellé « publication » trop large — même correctif.
  - `[low]` `[patch]` (blind) Écrivain sans état terminal — état « publié » ou « abandonné », toute écriture ultérieure refusée.
  - `[medium]` `[patch]` (blind) Interruption (Ctrl+C) sans nettoyage — nettoyage sur `BaseException`, interruption relancée telle quelle.
  - `[low]` `[reject]` (blind) `version_donnees` et événements lus en deux fois — fenêtre de course minime ; le générateur n'est pas lancé pendant un Passage en E0.
  - `[low]` `[reject]` (blind) Date d'arrêté future acceptée — avec la Source composite (L2), une date postérieure à l'injection est légitime.
  - `[low]` `[reject]` (blind) CLI liée au répertoire courant — convention du projet (lancement depuis la racine du dépôt).
  - `[low]` `[reject]` (blind) Manifeste sans distinction bouchon/réelle — `StatutEtape` est fixé par contrat ; le README signale les bouchons.
  - `[low]` `[reject]` (blind) Écarts entre la spec et le code — le correctif serait une édition de la spec.
  - `[low]` `[patch]` (blind) Branches d'échec non testées — tests de publication, d'abandon et d'interruption ajoutés.
  - `[low]` `[reject]` (blind) Mesure NFR-2 sans répétition — 0,91 s pour une cible de 5 minutes : le bruit ne change pas la conclusion ; `outils/` passe mypy.
  - `[medium]` `[patch]` (edge) Jour non calculé lu comme vert — même correctif que la ligne blind.
  - `[low]` `[reject]` (edge) Date postérieure au Journal — même raison que la ligne blind.
  - `[low]` `[patch]` (edge) `lancer_rapport` avec un jour non ouvré — même correctif que la ligne verification-gap.
  - `[medium]` `[patch]` (edge) `KeyboardInterrupt` sans nettoyage — même correctif.
  - `[low]` `[reject]` (edge) Horloge murale qui recule — rare ; les durées sont informatives.
  - `[low]` `[reject]` (edge) Répertoire orphelin si le `mkdir` de la progression échoue — disque plein ou droits : cas improbable.
  - `[low]` `[patch]` (edge) Échec du calcul de `nb_tickets` attribué à la publication — libellé précisé.
  - `[low]` `[reject]` (edge) Cible de publication déjà existante — collision de seconde et de 6 hex aléatoires (1 sur 16 millions).
  - `[low]` `[patch]` (edge) `publier` appelé deux fois — état terminal.
  - `[low]` `[reject]` (edge) Trace d'une autre date — aucune étape ne produit encore de trace.
  - `[low]` `[reject]` (edge) Verrou supprimé à la main puis repris — scénario manuel hors usage normal.
  - `[low]` `[reject]` (edge) Journal relu entre empreinte et lecture — même raison que la ligne blind.
  - `[low]` `[reject]` (edge) Le générateur ne prend pas le verrou — hors périmètre de la Chaîne ; usage séquentiel en E0.
  - `[low]` `[reject]` (edge) `vagues` vide dans l'outil — `ConfigProgramme` exige au moins une Vague.
  - `[medium]` `[patch]` (edge) « toute exception » non tenu pour `BaseException` — même correctif.
  - `[low]` `[reject]` (edge) L'outil lit `programme.yaml` directement — `outils/` est hors produit ; la config dérivée est revalidée par la composition.
  - `[low]` `[patch]` (edge) Palier non forcé dans la mesure — `palier: 1` écrit explicitement.
  - `[low]` `[reject]` (edge) Le verrou est pris par la composition, pas par l'écrivain — le verrou couvre tout le Passage, ce qui est l'intention d'AD-6.

## Design Notes

**Pourquoi un lecteur minimal ici.** `ContextePassage` exige une `Consultation` du Passage en cours (AD-22), et l'étape Météo doit relire `tickets_etats` écrit par l'étape précédente. La Story 0.6 complète ce lecteur (Météo, `dernier_passage`, `url_ticket`) et l'enregistre dans la suite de contrat. Ici, seules les lectures utiles aux étapes réelles sont implémentées.

**Séquence d'un Passage.**

```text
verrou → passage_id → .en-cours-<id>/
pour chaque Etape (ordre AD-8) :
    progression en_cours → executer(ctx) → valider + écrire sorties/traces → progression reussie|sautee
manifeste.json → rename .en-cours-<id> → <date>/<id> → verrou rendu
en cas d'exception : progression echouee → rename vers echecs/<id> → UsineErreur(étape) → verrou rendu
```

Sous Windows, rien ne doit garder un fichier ouvert dans `.en-cours-*` au moment du renommage : écrire et lire en ouvrir-fermer.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check .` -- expected: aucun écart.
- `uv run mypy` -- expected: aucune erreur.
- `uv run lint-imports` -- expected: tous les contrats KEPT.
- `uv run pytest` -- expected: tout vert.
- `uv run usine donnees generer --graine 42 --date-generation 2026-10-12` puis `uv run usine rapport --date-arrete 2026-10-09` -- expected: un Passage publié sous `sorties/passages/2026-10-09/`.
- `uv run python outils/mesurer_nfr2.py` -- expected: durées par étape affichées.

## Auto Run Result

Status: done

**Résumé.** `usine rapport [--date-arrete]` exécute le registre d'étapes construit par `composition.py`. L'`EcrivainPassage` construit le Passage dans `.en-cours-<id>`, puis le publie par un seul renommage. En cas d'échec, il le déplace sous `echecs/` et le message nomme l'étape. La progression s'écrit hors Passage, et un verrou exclusif est toujours rendu.

Étapes : `instantanes` et `meteo` sont réelles ; les quatre étapes LLM sont `sautee` en Palier 1 ; `extraction`, `kpi`, `prevision` et `rendu` sont des bouchons. Un lecteur `ConsultationPassage` minimal sert aux étapes. La mesure NFR-2 est consignée dans le README : 0,91 s pour 5 000 Anomalies, étapes réelles seulement.

**Fichiers.**
- `src/usine/chaine/` : `ecrivain`, `verrou`, `etapes`, `execution`, `cli`.
- `src/usine/consultation/passage.py` : lecteur minimal.
- `src/usine/composition.py` : registre, `lancer_rapport`, `verifier_date_arrete`, `generer_journal`.
- `src/usine/domaine/meteo.py` : garde de date amendée et documentée.
- `outils/mesurer_nfr2.py` et `README.md` : mesure NFR-2.
- `tests/unit/chaine/`, `tests/unit/consultation/` : tests.

**Revue.** 43 findings : 17 lignes `patch` (5 medium, en 2 causes : interruption non nettoyée, garde Météo ambiguë) donnant 7 correctifs ; 0 différé ; 26 rejetées avec leur motif.

**Revue de suivi.** `true`. La garde Météo n'est que documentée : un appelant qui calcule les `TicketEtat` sur des dates non contiguës obtiendrait du vert pour un jour non calculé. À reprendre si un appel autre que `EtapeMeteo` apparaît (L3 ou L5).

**Vérification.** ruff, ruff format, mypy, lint-imports et pytest : 695 passés, 11 ignorés. Exécution réelle : `usine donnees generer` puis `usine rapport --date-arrete 2026-10-09` publient le Passage.

**Risques résiduels.**
- Un processus tué brutalement (et non interrompu) laisse le verrou ; le message indique de le supprimer à la main.
- La mesure NFR-2 est à refaire quand les bouchons seront remplacés.

### Revue de suivi (2026-10-12)

Pas de nouvelle passe. Le seul risque nommé ci-dessus était une garde Météo seulement documentée : un jour non calculé lu comme vert. La revue de suivi de la Story 0.4 (commit 37baee3) l'a fermé : `_mesures` refuse désormais une Date d'arrêté absente alors que des états antérieurs existent, avec des tests pour un week-end et pour un trou dans les dates calculées.
