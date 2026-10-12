"""Composition : `FournisseurLLM` choisi par `config/llm.yaml`, sans modification de code (H-23)."""

from pathlib import Path

import pytest

from usine.composition import construire_fournisseur, construire_fournisseurs_par_tache
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import Tache
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


def test_configuration_du_depot_modele_par_tache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 6.5 : la classification sur Haiku 5.5, l'explication sur le modèle par défaut."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    racine = Path(__file__).resolve().parents[2]
    par_tache = construire_fournisseurs_par_tache(racine)
    assert set(par_tache) == {Tache.classification}
    assert par_tache[Tache.classification].version_modele == "anthropic:claude-haiku-5-5"
    for fournisseur in par_tache.values():
        getattr(fournisseur, "fermer", lambda: None)()


def _avec_modeles_par_tache(racine: Path, lignes: str) -> Path:
    chemin = racine / "config" / "llm.yaml"
    chemin.write_text(
        chemin.read_text(encoding="utf-8") + "modeles_par_tache:\n" + lignes, encoding="utf-8"
    )
    return racine


def test_modele_par_tache_identique_sans_fournisseur_dedie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    racine = _avec_modeles_par_tache(
        _racine(tmp_path, "anthropic", "claude-sonnet-5-5"),
        "  explication: claude-sonnet-5-5\n",
    )
    assert construire_fournisseurs_par_tache(racine) == {}


def test_modele_par_tache_hors_registre(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    racine = _avec_modeles_par_tache(
        _racine(tmp_path, "anthropic", "claude-sonnet-5-5"),
        "  classification: claude-haiku-5-5\n  narration: claude-inconnu\n",
    )
    with pytest.raises(UsineErreur, match="claude-inconnu"):
        construire_fournisseurs_par_tache(racine)


def test_sans_modele_par_tache(tmp_path: Path) -> None:
    racine = _racine(tmp_path, "anthropic", "claude-sonnet-5-5")
    assert construire_fournisseurs_par_tache(racine) == {}
    assert construire_fournisseurs_par_tache(tmp_path / "absente") == {}
