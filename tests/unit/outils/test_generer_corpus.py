"""Outil `outils/generer_corpus.py` : Corpus provisoire ou produit par un faux LLM (1.2, 1.9)."""

from decimal import Decimal
from pathlib import Path

import pytest

import outils.generer_corpus as outil
from outils.generer_corpus import generer, generer_par_llm, main
from tests.doublures.fournisseur_factice import FournisseurFactice
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import Tache
from usine.contrats.tickets import CauseRacine
from usine.generateur.corpus import ReponseCorpus, TexteTicket, charger_corpus

RACINE = Path(__file__).resolve().parents[3]
CORPUS_VERSIONNE = RACINE / "donnees" / "corpus" / "textes.json"
PROGRAMME_REDUIT = RACINE / "tests" / "unit" / "generateur" / "programme_reduit.yaml"
"""Domaines `comptabilite`, `achats`, `paie`."""


def _reponses(nombre: int) -> list[ReponseCorpus]:
    return [
        ReponseCorpus(
            textes=(TexteTicket(titre=f"Titre {r}", description=f"Constaté sur {{entite}} ({r})"),)
        )
        for r in range(nombre)
    ]


def test_outil_faux_llm(tmp_path: Path) -> None:
    nombre = (3 + 1) * (len(CauseRacine) + 1) + 1
    fournisseur = FournisseurFactice(
        reponses_structurees=_reponses(nombre), version_modele="factice:redacteur"
    )
    sortie = tmp_path / "corpus" / "textes.json"
    chemin = generer(
        fournisseur, config=PROGRAMME_REDUIT, sortie=sortie, version_corpus="llm-essai"
    )
    assert chemin == sortie
    corpus = charger_corpus(chemin)
    assert corpus.modele_corpus == "factice:redacteur"
    assert corpus.version_corpus == "llm-essai"
    assert tuple(corpus.domaines) == ("comptabilite", "achats", "paie")
    assert len(fournisseur.appels) == nombre
    assert all(a.methode == "generer_structure" for a in fournisseur.appels)
    assert all(a.parametres.tache is Tache.narration for a in fournisseur.appels)


def test_outil_sans_fournisseur_ni_provisoire(tmp_path: Path) -> None:
    sortie = tmp_path / "textes.json"
    with pytest.raises(UsineErreur, match=r"--fournisseur et --modele.*--provisoire"):
        generer(None, config=PROGRAMME_REDUIT, sortie=sortie)
    assert not sortie.exists()


def test_outil_provisoire_memes_domaines_que_le_versionne(tmp_path: Path) -> None:
    sortie = tmp_path / "textes.json"
    generer(None, provisoire=True, sortie=sortie)
    provisoire = charger_corpus(sortie)
    assert provisoire.modele_corpus == "gabarits-provisoires"
    assert tuple(provisoire.domaines) == tuple(charger_corpus(CORPUS_VERSIONNE).domaines)


def test_outil_provisoire_ignore_le_fournisseur(tmp_path: Path) -> None:
    fournisseur = FournisseurFactice()
    sortie = tmp_path / "textes.json"
    generer(fournisseur, provisoire=True, config=PROGRAMME_REDUIT, sortie=sortie)
    assert charger_corpus(sortie).modele_corpus == "gabarits-provisoires"
    assert fournisseur.appels == []


def test_main_provisoire(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sortie = tmp_path / "textes.json"
    code = main(["--provisoire", "--sortie", str(sortie), "--version-corpus", "provisoire-9"])
    assert code == 0
    assert str(sortie) in capsys.readouterr().out
    assert charger_corpus(sortie).version_corpus == "provisoire-9"


def test_main_sans_provisoire(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sortie = tmp_path / "textes.json"
    assert main(["--sortie", str(sortie)]) == 1
    erreur = capsys.readouterr().err
    assert "--fournisseur et --modele" in erreur
    assert "--provisoire" in erreur
    assert not sortie.exists()


def test_main_config_non_utf8(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "programme.yaml"
    config.write_bytes("domaines: [comptabilité]\n".encode("latin-1"))
    assert main(["--provisoire", "--config", str(config), "--sortie", str(tmp_path / "t")]) == 1
    assert str(config) in capsys.readouterr().err


def test_main_config_illisible(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "absente.yaml"
    assert main(["--provisoire", "--config", str(config), "--sortie", str(tmp_path / "t")]) == 1
    assert str(config) in capsys.readouterr().err


# --- Story 1.9 : Corpus définitif par LLM ---

NOMBRE_REDUIT = (3 + 1) * (len(CauseRacine) + 1) + 1


class _Construction:
    """Remplace `construire_fournisseur` : renvoie une doublure, sans clé ni réseau."""

    def __init__(self, nombre: int = NOMBRE_REDUIT) -> None:
        self.nombre = nombre
        self.appels: list[tuple[Path, dict[str, object]]] = []

    def __call__(self, racine: Path, **surcharges: str) -> FournisseurFactice:
        self.appels.append((racine, dict(surcharges)))
        version = f"{surcharges['fournisseur']}:{surcharges['modele']}"
        return FournisseurFactice(
            reponses_structurees=_reponses(self.nombre), version_modele=version
        )


@pytest.fixture
def construction(monkeypatch: pytest.MonkeyPatch) -> _Construction:
    doublure = _Construction()
    monkeypatch.setattr(outil, "construire_fournisseur", doublure)
    return doublure


def test_main_estimer(construction: _Construction, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--fournisseur", "mistral", "--modele", "mistral-medium-latest", "--estimer"])
    assert code == 0
    sortie = capsys.readouterr().out
    assert "57 appels" in sortie
    assert "mistral:mistral-medium-latest" in sortie
    assert construction.appels == []


def test_main_generation_par_llm(
    tmp_path: Path, construction: _Construction, capsys: pytest.CaptureFixture[str]
) -> None:
    sortie = tmp_path / "textes.json"
    arguments = ["--fournisseur", "mistral", "--modele", "mistral-medium-latest"]
    code = main([*arguments, "--config", str(PROGRAMME_REDUIT), "--sortie", str(sortie)])
    assert code == 0
    corpus = charger_corpus(sortie)
    assert corpus.modele_corpus == "mistral:mistral-medium-latest"
    assert corpus.version_corpus == "llm-1"
    assert construction.appels == [
        (outil.RACINE_DEPOT, {"fournisseur": "mistral", "modele": "mistral-medium-latest"})
    ]
    bilan = capsys.readouterr().out
    assert f"{NOMBRE_REDUIT} appels" in bilan
    assert "jetons d'entrée" in bilan
    assert "jetons de sortie" in bilan
    assert "coût estimé réel" in bilan


def test_main_plafond_depasse(
    tmp_path: Path, construction: _Construction, capsys: pytest.CaptureFixture[str]
) -> None:
    sortie = tmp_path / "textes.json"
    arguments = ["--fournisseur", "mistral", "--modele", "mistral-large-latest"]
    assert main([*arguments, "--plafond-eur", "0.01", "--sortie", str(sortie)]) == 1
    erreur = capsys.readouterr().err
    assert "plafond" in erreur
    assert "0.01" in erreur
    assert " € pour 57 appels" in erreur
    assert construction.appels == []
    assert not sortie.exists()


def test_main_estimer_plafond_depasse(
    construction: _Construction, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = ["--fournisseur", "mistral", "--modele", "mistral-large-latest", "--estimer"]
    assert main([*arguments, "--plafond-eur", "0"]) == 1
    assert "plafond" in capsys.readouterr().err


def test_main_garde_fou_classification(
    tmp_path: Path, construction: _Construction, capsys: pytest.CaptureFixture[str]
) -> None:
    """`config/llm.yaml` du dépôt : classification sur `anthropic:claude-haiku-5-5`."""
    sortie = tmp_path / "textes.json"
    arguments = ["--fournisseur", "anthropic", "--modele", "claude-haiku-5-5"]
    assert main([*arguments, "--sortie", str(sortie)]) == 1
    erreur = capsys.readouterr().err
    assert erreur.count("'anthropic:claude-haiku-5-5'") == 2
    assert "AD-19" in erreur
    assert construction.appels == []
    assert not sortie.exists()


def test_main_modele_hors_registre(
    construction: _Construction, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--fournisseur", "mistral", "--modele", "inconnu", "--estimer"]) == 1
    erreur = capsys.readouterr().err
    assert "mistral:inconnu" in erreur
    assert "modèles connus" in erreur
    assert construction.appels == []


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--fournisseur", "mistral"],
        ["--modele", "mistral-medium-latest"],
        ["--estimer"],
        ["--provisoire", "--fournisseur", "mistral", "--modele", "mistral-medium-latest"],
        ["--provisoire", "--estimer"],
    ],
)
def test_main_arguments_incomplets(
    tmp_path: Path,
    construction: _Construction,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
) -> None:
    sortie = tmp_path / "textes.json"
    assert main([*arguments, "--sortie", str(sortie)]) == 1
    assert "--" in capsys.readouterr().err
    assert construction.appels == []
    assert not sortie.exists()


@pytest.mark.parametrize("plafond", ["abc", "-1", "NaN", "inf"])
def test_main_plafond_invalide(plafond: str) -> None:
    with pytest.raises(SystemExit) as sortie:
        main(
            [
                "--fournisseur",
                "mistral",
                "--modele",
                "mistral-medium-latest",
                "--plafond-eur",
                plafond,
            ]
        )
    assert sortie.value.code == 2


def test_generer_par_llm_sans_llm_yaml(tmp_path: Path, construction: _Construction) -> None:
    """Racine sans `config/llm.yaml` : garde-fou sans objet, Corpus produit."""
    sortie = tmp_path / "corpus" / "textes.json"
    bilan = generer_par_llm(
        "anthropic",
        "claude-haiku-5-5",
        racine=tmp_path,
        config=PROGRAMME_REDUIT,
        sortie=sortie,
        version_corpus="llm-2",
        plafond_eur=Decimal("2.00"),
    )
    assert bilan.chemin == sortie
    assert bilan.appels == NOMBRE_REDUIT
    assert bilan.cout_eur > 0
    corpus = charger_corpus(sortie)
    assert corpus.modele_corpus == "anthropic:claude-haiku-5-5"
    assert corpus.version_corpus == "llm-2"
