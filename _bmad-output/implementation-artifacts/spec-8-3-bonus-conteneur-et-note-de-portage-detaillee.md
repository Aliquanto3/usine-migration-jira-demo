---
title: "Story 8.3 : [BONUS] Conteneur et note de portage détaillée"
type: 'feature'
created: '2026-10-18'
status: 'review'
baseline_revision: 'e930409'
review_loop_iteration: 0
followup_review_recommended: false
context: ['_bmad-output/implementation-artifacts/epic-8-context.md']
warnings: ['build du Dockerfile non vérifié localement : Docker et hadolint absents du poste']
deferred: ['construire l image et rejouer `usine rapport` en Palier 1 sur un poste avec Docker (tag uv `0.12.23-python3.12-bookworm-slim` à confirmer)', 'intégration (AD-21) : `Dockerfile`, `.dockerignore`, `ui/cli.py` et `tests/depot/` sortent des chemins de L8 : PR sur `main`, la lane seule échouerait au contrôle des lanes', 'mode LLM local (FR-37) non couvert par l image']
---

## Intent

**Problem:** le portage est décrit (fiche 8.1) mais pas démontré (FR-48) : pas d'image exécutable ni de note détaillée par plateforme.

**Approach:** un `Dockerfile` basé sur uv qui lance `usine ui` (ou toute commande `usine`), un `.dockerignore` sans secret ni donnée, une variable `USINE_UI_HOTE` réservée au conteneur pour écouter sur `0.0.0.0`, et `docs/portage-detaille.md` (Dataiku, Power Platform, section Conteneur).

## Boundaries & Constraints

**Always:** `usine ui` écoute sur `127.0.0.1` par défaut ; `0.0.0.0` seulement si `USINE_UI_HOTE=0.0.0.0` dans l'environnement du processus (jamais `.env`). Le contrôle du `Host` (`HOTES_AUTORISES`) et de l'`Origin` est inchangé : la doc impose `-p 127.0.0.1:8000:8000`. Installation `uv sync --locked --no-dev --no-default-groups` ; `bonus` seulement avec `--build-arg AVEC_BONUS=1`. Utilisateur non root (UID 10001).

**Never:** copier `.env`, `donnees/`, `sorties/` ou `.git` dans l'image ; toucher à `contrats/` ou `ports/` ; valeur d'hôte autre que `127.0.0.1` ou `0.0.0.0`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Poste local | `USINE_UI_HOTE` absente | uvicorn sur `127.0.0.1` | — |
| Conteneur | `USINE_UI_HOTE=0.0.0.0` | uvicorn sur `0.0.0.0`; message : URL `http://127.0.0.1:8000/` + rappel `-p 127.0.0.1:8000:8000` | `Host` `0.0.0.0` refusé (400) |
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
