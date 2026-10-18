---
title: "Story 8.3 : [BONUS] Conteneur et note de portage détaillée"
type: 'feature'
created: '2026-10-18'
status: 'done'
baseline_revision: 'e930409'
review_loop_iteration: 0
followup_review_recommended: false
context: ['_bmad-output/implementation-artifacts/epic-8-context.md']
warnings: ['build du Dockerfile non vérifié localement : Docker et hadolint absents du poste']
deferred: ['construire l image et rejouer `usine rapport` en Palier 1 sur un poste avec Docker (base `uv:0.12.23-python3.12-trixie-slim` vérifiée sur ghcr.io, épinglée par digest)', 'intégration (AD-21) : `Dockerfile`, `.dockerignore`, `ui/cli.py` et `tests/depot/` sortent des chemins de L8 : PR sur `main`, la lane seule échouerait au contrôle des lanes', 'mode LLM local (FR-37) non couvert par l image']
---

## Intent

**Problem:** le portage est décrit (fiche 8.1) mais pas démontré (FR-48) : pas d'image exécutable ni de note détaillée par plateforme.

**Approach:** un `Dockerfile` basé sur uv qui lance `usine ui` (ou toute commande `usine`), un `.dockerignore` sans secret ni donnée, une variable `USINE_UI_HOTE` réservée au conteneur pour écouter sur `0.0.0.0`, et `docs/portage-detaille.md` (Dataiku, Power Platform, section Conteneur).

## Boundaries & Constraints

**Always:** `usine ui` écoute sur `127.0.0.1` par défaut ; `0.0.0.0` seulement si `USINE_UI_HOTE=0.0.0.0` dans l'environnement du processus (jamais `.env`) et dans un conteneur (`/.dockerenv` ou `/run/.containerenv`). Le contrôle du `Host` (`HOTES_AUTORISES`) et de l'`Origin` est inchangé : la doc impose `-p 127.0.0.1:8000:8000`. Installation `uv sync --locked --no-dev --no-default-groups` ; `bonus` seulement avec `--build-arg AVEC_BONUS=1`. Utilisateur non root (UID 10001).

**Never:** copier `.env`, `donnees/`, `sorties/` ou `.git` dans l'image ; toucher à `contrats/` ou `ports/` ; valeur d'hôte autre que `127.0.0.1` ou `0.0.0.0`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Poste local | `USINE_UI_HOTE` absente | uvicorn sur `127.0.0.1` | — |
| Conteneur | `USINE_UI_HOTE=0.0.0.0` | uvicorn sur `0.0.0.0`; message : URL `http://127.0.0.1:8000/` + rappel `-p 127.0.0.1:8000:8000` | `Host` `0.0.0.0` refusé (400) |
| `0.0.0.0` hors conteneur | aucun marqueur de conteneur | rien ne démarre | `UsineErreur`, sortie 1 |
| Valeur étrangère | `USINE_UI_HOTE=192.168.1.5` | rien ne démarre | `UsineErreur` nommant la variable, sortie 1 |
| Port occupé | bind échoue | message avec l'adresse réellement écoutée | sortie 1 |

## Code Map

- `Dockerfile`, `.dockerignore` -- image uv, bonus par argument, `ENTRYPOINT ["usine"]`, `CMD ["ui"]` ; `usine rapport` en Palier 1 avec `donnees/` monté.
- `src/usine/ui/cli.py` -- `VARIABLE_HOTE`, `HOTE_CONTENEUR`, `hote_ecoute()`, message de démarrage.
- `docs/portage-detaille.md` -- découpage des briques, secrets et configuration, limites, section Conteneur ; liens depuis `README.md` et `docs/fiche-outillage.md`.

## Tests

`tests/unit/ui/test_cli.py` (hôte conteneur, valeur 127.0.0.1, valeur refusée, `Host` 0.0.0.0 refusé) ; `tests/depot/test_conteneur.py` (`.dockerignore`, base épinglée, USER non root, aucun COPY de secret, argument bonus). **Build non vérifié localement.**

## Reports

Construction et lancement réels de l'image, tag de base uv, droits d'écriture des volumes montés sous Linux, mode LLM local dans l'image.

## Revue

Revue unique (Edge Case Hunter, Opus) du commit `1fd8210`, avec la liste du second avis (Haiku). Docker et hadolint absents : Dockerfile relu à la main, tags vérifiés sur l'API du registre ghcr.io.

- high | revue | corrigé | `FROM ghcr.io/astral-sh/uv:0.12.23-python3.12-bookworm-slim` n'existe pas (404 sur ghcr.io, comme `0.12.22-…-bookworm-slim`) : le build échouait. Base `0.12.23-python3.12-trixie-slim` (200), épinglée par digest ; le test exige le digest.
- medium | second avis 1 | corrigé | `USINE_UI_HOTE=0.0.0.0` hors conteneur ouvrait au réseau une interface sans authentification (le contrôle du `Host` n'arrête pas un client qui forge `Host: 127.0.0.1`). `0.0.0.0` n'est plus accepté qu'en présence de `/.dockerenv` ou `/run/.containerenv` ; test du refus.
- medium | second avis 2 | corrigé | doc fausse : `-p 127.0.0.1:9000:8000` fonctionne (vérifié : `Host: 127.0.0.1:9000` → 200, `Origin` du même port → 200, d'un autre port → 403). Doc réécrite, limite du contrôle du `Host` et réseau Docker partagé ajoutés.
- low | second avis 3 | corrigé | `.dockerignore` : motifs `**/` pour `.env`, `.env.*`, `__pycache__`, `*.py[cod]`, `*.duckdb`.
- low | second avis 4 | corrigé par le correctif 1 | la bannière « dans le conteneur » ne peut plus s'afficher hors conteneur.
- low | second avis 5 | corrigé (doc) | volumes absents créés au nom de root : créer `donnees/` et `sorties/` avant le lancement, puis `chown 10001`.
- low | second avis 6 | rejeté | chemins relatifs au répertoire courant : préexistant, hors périmètre ; dans l'image le répertoire courant est `/app`. `usine agent --enregistrer` (écrit dans `demo/`, propriété de root) documenté comme non prévu dans l'image.
- low | second avis 7 | corrigé | tests renforcés : sources des `COPY` existantes, `ENTRYPOINT` = script de `[project.scripts]`, `--no-default-groups` sur les deux `uv sync`.
- low | second avis 8 | corrigé | voir le constat high (tag inexistant).
- low | revue | corrigé (doc) | `--env-file` garde les guillemets et transmettrait un `USINE_RACINE` propre au poste : précisé dans la note.
- reporté | revue | build et lancement réels de l'image (`docker build`, `usine ui` sur `http://127.0.0.1:8000/`, `usine rapport` en Palier 1, `hadolint Dockerfile`) sur un poste avec Docker.
