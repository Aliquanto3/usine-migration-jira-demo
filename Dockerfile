# Image de la Chaîne de reporting (Story 8.3, FR-48, NFR-8). Build non vérifié localement.
#
# Construire :  docker build -t usine-jira-demo .
#   avec le groupe optionnel `bonus` (lightgbm, langfuse) :  docker build --build-arg AVEC_BONUS=1 -t usine-jira-demo:bonus .
# Lancer l'interface (même port des deux côtés, publication sur la boucle locale de l'hôte seulement) :
#   docker run --rm -p 127.0.0.1:8000:8000 --env-file .env -v "$PWD/donnees:/app/donnees" -v "$PWD/sorties:/app/sorties" usine-jira-demo
# Produire un Passage en Palier 1 (Journal monté) :
#   docker run --rm --env-file .env -v "$PWD/donnees:/app/donnees" -v "$PWD/sorties:/app/sorties" usine-jira-demo rapport
# Aucun secret dans l'image : `.env` n'est jamais copié (voir `.dockerignore`), il est fourni au lancement.

# Tag vérifié sur ghcr.io le 2026-10-18 (la variante bookworm n'existe pas pour uv 0.12), épinglé par digest.
FROM ghcr.io/astral-sh/uv:0.12.23-python3.12-trixie-slim@sha256:28d570c06d150303b39adfa731ada20956c63fc86b1277d7ff2ad63185974092

ARG AVEC_BONUS=0

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# Bibliothèque OpenMP, requise par lightgbm : installée seulement avec le groupe bonus.
# hadolint ignore=DL3008
RUN if [ "${AVEC_BONUS}" = "1" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends libgomp1 \
        && rm -rf /var/lib/apt/lists/*; \
    fi

# Dépendances d'abord (couche en cache tant que pyproject.toml et uv.lock ne changent pas).
# `--no-default-groups` écarte `dev` et `evaluation` ; `bonus` n'entre que par l'argument de build.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN if [ "${AVEC_BONUS}" = "1" ]; then groupes="--group bonus"; else groupes=""; fi \
    && uv sync --locked --no-dev --no-default-groups --no-install-project ${groupes}

# Code et fichiers lus à l'exécution (racine = répertoire courant, /app).
COPY src ./src
COPY config ./config
COPY gabarits ./gabarits
COPY demo ./demo
COPY docs/fiche-outillage.md ./docs/fiche-outillage.md
RUN if [ "${AVEC_BONUS}" = "1" ]; then groupes="--group bonus"; else groupes=""; fi \
    && uv sync --locked --no-dev --no-default-groups ${groupes}

# Utilisateur non root ; `donnees/` (Journal, entrepôt) et `sorties/` (Passages) se montent en volumes.
RUN useradd --create-home --uid 10001 usine \
    && mkdir -p /app/donnees /app/sorties \
    && chown usine:usine /app/donnees /app/sorties
USER usine

# Écoute sur toutes les interfaces du conteneur seulement (lu par `usine ui`, AD-25 ; refusé hors
# conteneur, sans `/.dockerenv` ni `/run/.containerenv`) : l'hôte publie sur 127.0.0.1.
ENV USINE_UI_HOTE=0.0.0.0
EXPOSE 8000

ENTRYPOINT ["usine"]
CMD ["ui"]
