"""Conteneur (Story 8.3, FR-48) : aucun secret dans l'image, utilisateur non root, base épinglée."""

import re
from pathlib import Path

import pytest


@pytest.fixture
def dockerfile(racine_depot: Path) -> str:
    return (racine_depot / "Dockerfile").read_text(encoding="utf-8")


def _lignes(texte: str) -> list[str]:
    return [ligne.strip() for ligne in texte.splitlines() if not ligne.strip().startswith("#")]


def test_dockerignore_exclut_secrets_et_donnees(racine_depot: Path) -> None:
    lignes = (racine_depot / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for motif in (".env", "donnees/", "sorties/", ".venv/", ".git/"):
        assert motif in lignes, motif


def test_image_de_base_epinglee(dockerfile: str) -> None:
    bases = [ligne for ligne in _lignes(dockerfile) if ligne.startswith("FROM ")]
    assert bases
    assert all(":" in b and not b.endswith(":latest") for b in bases)


def test_utilisateur_non_root(dockerfile: str) -> None:
    utilisateurs = [ligne for ligne in _lignes(dockerfile) if ligne.startswith("USER ")]
    assert utilisateurs
    assert utilisateurs[-1] not in ("USER root", "USER 0")


def test_aucun_secret_copie_dans_l_image(dockerfile: str) -> None:
    for ligne in _lignes(dockerfile):
        if ligne.startswith(("COPY ", "ADD ")):
            assert not re.search(r"\.env(\s|$)", ligne), ligne
            assert "donnees" not in ligne, ligne


def test_installation_verrouillee_et_bonus_par_argument(dockerfile: str) -> None:
    assert "ARG AVEC_BONUS=0" in dockerfile
    assert "uv sync --locked --no-dev" in dockerfile
    assert "--group bonus" in dockerfile
    assert 'ENTRYPOINT ["usine"]' in dockerfile
    assert 'CMD ["ui"]' in dockerfile
