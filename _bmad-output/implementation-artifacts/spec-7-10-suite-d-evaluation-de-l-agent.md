---
title: "Story 7.10 : Suite d'évaluation de l'Agent"
type: 'feature'
created: '2026-10-13'
status: 'done'
baseline_revision: '38d1faf858e561cf1b70f736eb791daf8be5493b'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** l'Agent (7.9) n'a aucune mesure de fiabilité. Rien ne dit s'il atteint 13/15 sans chiffre inventé (SM-4, FR-42). De plus, une exception en cours de conversation fait perdre les traces des outils déjà exécutés (report medium de 7.9).

**Approach:** créer `evals/agent/` sur le modèle d'`evals/explication` : 15 questions versionnées sur le Passage fictif `demo/repli/passage/`, avec leurs éléments attendus (Entités, tickets, chiffres) et un tour enregistré par question (appels d'outils puis texte). Le rejeu passe par la vraie `SessionAgent` (outils, passerelle, contrôle) sans réseau ; il est testé en CI. Le mode `--reel` est lancé à la demande. Pour le report, `executer_agent` transmet chaque trace dès qu'elle est produite.

## Boundaries & Constraints

**Always:** même session que l'UI (`composition.construire_session_agent`) ; les outils réels lisent le Passage ; en rejeu, aucun réseau ni secret (fournisseur enregistré, pseudonymiseur identité) ; publication du score sur 15, des chiffres inventés (nombres refusés par le contrôle dans le texte brut), des tickets inventés et des refus sur les questions répondables ; verdict SM-4 = score ≥ 13, 0 chiffre inventé, refus ≤ 1 ; textes en français.

**Never:** modifier `contrats/` ou `ports/` ; importer `usine.ia`, `usine.consultation` ou `usine.ui` depuis `evals` (règle import-linter « hors produit ») ; lancer `--reel` en CI ; écrire dans un Passage ; réponses enregistrées du Mode repli (7.11).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Rejeu nominal | 15 questions, Passage `demo/repli/passage/` | score 15/15, 0 chiffre inventé, 0 refus, `sm4_atteint=true` | — |
| Question de la démo | `get_risques` puis `get_meteo(ENT-C)` | réponse conforme citant ENT-C, IND-4 et des tickets en cause | — |
| Sans réponse possible | ≥ 2 questions, texte « Les données ne permettent pas de répondre. » | réussie si conforme et refus explicite | — |
| Chiffre inventé | tour enregistré dont le texte porte « 42 » absent des résultats | question échouée, `chiffres_inventes` compte 1 | — |
| Refus sur une répondable | texte de refus à une question répondable | échouée, `refus_repondables` compte 1 | — |
| Passage différent | `passage_id` du Passage ≠ celui des questions (rejeu) | arrêt, message nommant les deux identifiants | `UsineErreur`, code 1 |
| Tour absent | question sans tour enregistré | arrêt nommant la question | `UsineErreur` |
| Exception en cours | un outil a tourné, puis le fournisseur lève | la trace de l'outil est déjà dans le JSONL de la session | l'exception remonte |

</intent-contract>

## Code Map

- `evals/explication/{__main__,suite,cas}.py`, `README.md` -- modèle : `FournisseurEnregistre`, `PseudonymiseurIdentite` (réutilisable par import), `ecrire_resultat`, CLI `executer [--reel]`.
- `src/usine/composition.py:611` -- `construire_session_agent(racine, consultation, fournisseur, pseudonymiseur)` ; ajouter `consultation_repertoire(repertoire)` (ConsultationPassage sans URL Jira), car `evals` ne peut pas importer `usine.consultation`.
- `src/usine/ia/agent/session.py` -- `SessionAgent.repondre`, `controler_reponse`, `valeurs_outils`, `tickets_cites`, `SANS_REPONSE` ; capter la réponse brute contrôlée pour compter les nombres et tickets refusés.
- `src/usine/ia/passerelle.py:356` -- `executer_agent` : `traces_outils` n'est rendu qu'au retour ; ajouter un rappel `sur_trace`.
- `tests/doublures/fournisseur_factice.py:83` -- construction d'une conversation d'Agent scriptée (modèle du fournisseur enregistré).
- `demo/repli/passage/` -- Passage `20261012T221158Z-96c621`, Date d'arrêté 2026-10-09 : ENT-A et ENT-B rouges (IND-1 4 et 9), ENT-C orange (IND-4 27/150) avec Risque de franchissement le 2026-10-14, ENT-D vert, ENT-E à ENT-J jaunes (IND-6).
- `config/llm.yaml` (dépôt principal) -- tâche `agent` sur `claude-sonnet-5-5`.

## Tasks & Acceptance

**Execution:**
- `src/usine/ia/passerelle.py` -- paramètre `sur_trace: Callable[[EntreeTrace], None] | None` d'`executer_agent`, appelé pour chaque trace d'outil dès sa production et pour la trace finale -- report 7.9.
- `src/usine/ia/agent/session.py` -- `repondre` écrit chaque trace via `sur_trace` ; `derniers_refus` (nombres et tickets refusés de la dernière réponse brute) exposé.
- `src/usine/composition.py` -- `consultation_repertoire(repertoire) -> Consultation`.
- `evals/agent/questions.json` -- 15 questions : identifiant, question, `repondable`, `demo`, `attendus` (`entites`, `tickets`, `chiffres`), `tour` (`appels`, `texte`) ; `passage_id` en tête.
- `evals/agent/questions.py`, `suite.py`, `__main__.py`, `__init__.py`, `README.md` -- chargement validé, fournisseur enregistré par question, notation automatique, résultat `resultats/<horodatage>.json`, ligne dans `historique.jsonl`, CLI `executer [--reel]`, coût estimé du réel.
- `tests/unit/evals/agent/test_suite.py`, `tests/unit/ia/agent/test_session.py`, `tests/unit/ia/test_passerelle_agent.py` -- matrice ci-dessus.

**Acceptance Criteria:**
- Given `evals/agent/`, when l'auteur lance `uv run python -m evals.agent executer`, then le résultat donne le score sur 15, les chiffres inventés, les refus sur les 13 répondables et le verdict SM-4.
- Given le fichier de questions, when il est chargé, then il compte 15 questions, une seule `demo`, au moins 2 non répondables, et la question de la démo est exactement celle de l'epic.

## Spec Change Log

## Review Triage Log

Revue Edge Case Hunter (une passe, run autonome) : aucun constat medium ou high. Constats rejetés (low) :
- rejeté : en `--reel`, une erreur réseau non `UsineErreur` remonte en trace Python au lieu du code 1 ; exécution manuelle, l'erreur reste lisible. Corrigé (7.10-a).
- rejeté : en `--reel`, une réponse servie du cache n'exécute aucun outil ; la notation reste juste (contrôle sur la conversation en cache) et `depuis_cache` figure dans la trace.
- rejeté : un `sur_trace` qui lève (disque plein) interrompt la conversation ; comportement voulu, les traces déjà écrites restent.
- rejeté : la détection du refus est sensible à la casse (« ne permettent pas de répondre ») ; c'est la phrase imposée par les consignes de l'Agent.

## Design Notes

Une question réussit si la réponse est conforme au contrôle et si elle contient chaque élément attendu (Entité et ticket : mot entier ; chiffre : nombre isolé, écrit à la française). Une question sans réponse possible réussit si la réponse conforme contient « ne permettent pas de répondre ». Un refus est une réponse conforme contenant cette phrase à une question répondable. Coût réel estimé (Sonnet 5.5, 3 $ / 15 $ par million) : environ 3 tours par question avec des résultats d'outils de 2 000 à 5 000 jetons, soit 0,40 à 0,90 €. C'est au-delà de 0,30 €, donc l'exécution réelle n'est pas lancée dans ce run.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert
- `uv run python -m evals.agent executer --sortie <tmp>` -- expected: 15/15, SM-4 atteint

## Auto Run Result

Status: done
Livré : `evals/agent/` (15 questions, rejeu sans réseau par la vraie `SessionAgent`, notation, CLI `executer [--reel]`, historique), `consultation_repertoire`, rappel `sur_trace` d'`executer_agent` (report 7.9 : traces des outils écrites dès leur production, conservées sur exception), `SessionAgent.derniers_refus`. Rejeu : 15/15, 0 chiffre inventé, 0 refus, SM-4 atteint. Contrôles verts (ruff, format, mypy, lint-imports, pytest : 2763 passés).
Revue : une passe Edge Case Hunter, aucun constat medium ou high (4 low rejetés, voir le triage).
Exécution réelle non lancée (0,40 à 0,90 € estimés), à faire par Anaël : `uv run python -m evals.agent executer --reel`.
