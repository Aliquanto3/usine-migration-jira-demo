"""Composition : `FournisseurLLM` choisi par `config/llm.yaml`, sans modification de code (H-23)."""

from pathlib import Path

import pytest

from usine.composition import construire_fournisseur
from usine.contrats.erreurs import UsineErreur
from usine.ports import FournisseurLLM


def _racine(tmp_path: Path, fournisseur: str, modele: str) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "llm.yaml").write_text(
        f"fournisseur: {fournisseur}\nmodele: {modele}\nplafond_cout_passage_eur: 1\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize(
    ("fournisseur", "modele", "variable"),
    [
        ("anthropic", "claude-sonnet-5-5", "ANTHROPIC_API_KEY"),
        ("mistral", "mistral-large-latest", "MISTRAL_API_KEY"),
    ],
)
def test_fournisseur_choisi_par_la_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fournisseur: str, modele: str, variable: str
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    racine = _racine(tmp_path, fournisseur, modele)
    with pytest.raises(UsineErreur, match=variable):
        construire_fournisseur(racine)
    monkeypatch.setenv(variable, "cle-de-test")
    adaptateur = construire_fournisseur(racine)
    assert isinstance(adaptateur, FournisseurLLM)
    assert adaptateur.version_modele == f"{fournisseur}:{modele}"


def test_sans_llm_yaml(tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match=r"llm\.yaml"):
        construire_fournisseur(tmp_path)


def test_configuration_du_depot_valide(monkeypatch: pytest.MonkeyPatch) -> None:
    """`config/llm.yaml` du dépôt : Anthropic, `claude-sonnet-5-5`, présent au registre."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    racine = Path(__file__).resolve().parents[2]
    assert construire_fournisseur(racine).version_modele == "anthropic:claude-sonnet-5-5"
