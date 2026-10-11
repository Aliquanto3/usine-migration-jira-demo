"""Passages publiés pour les tests du rendu : normal et en Mode repli (graine 42, 2026-10-09)."""

from pathlib import Path

import pytest

from tests.unit.chaine.environnement import DATE_ARRETE, horloge_figee, preparer_racine
from usine.composition import lancer_rapport
from usine.consultation.passage import ConsultationPassage
from usine.contrats.meteo import CodeIndicateur, Couleur, MeteoEntite, Operateur, RegleDeclenchante
from usine.contrats.passage import EnveloppeFichier


def _publier(
    racine: Path, mode_repli: bool, monkeypatch: pytest.MonkeyPatch, sans_jira: bool = False
) -> Path:
    preparer_racine(racine)
    if sans_jira:
        (racine / "config" / "jira.yaml").unlink()
    monkeypatch.chdir(racine)  # aucun `.env` du poste lu par `Secrets`
    if mode_repli:
        monkeypatch.setenv("USINE_MODE_REPLI", "1")
    else:
        monkeypatch.delenv("USINE_MODE_REPLI", raising=False)
    return lancer_rapport(racine, DATE_ARRETE, horloge_figee(), lambda: "abcdef").repertoire


@pytest.fixture(scope="module")
def passage(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Répertoire d'un Passage publié avec `config/jira.yaml`."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        return _publier(tmp_path_factory.mktemp("normal"), False, monkeypatch)


@pytest.fixture(scope="module")
def passage_repli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Répertoire d'un Passage publié en Mode repli (`USINE_MODE_REPLI=1`)."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        return _publier(tmp_path_factory.mktemp("repli"), True, monkeypatch)


@pytest.fixture(scope="module")
def passage_sans_jira(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Répertoire d'un Passage publié sans `config/jira.yaml`."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        return _publier(tmp_path_factory.mktemp("sans-jira"), False, monkeypatch, sans_jira=True)


@pytest.fixture
def consultation(passage: Path) -> ConsultationPassage:
    """Consultation du Passage publié, avec l'URL du site Jira de `config/jira.yaml`."""
    return ConsultationPassage(passage, url_jira="https://jira.example.invalid")


REGLE_JAUNE = RegleDeclenchante(
    code=CodeIndicateur.ind_2,
    couleur=Couleur.jaune,
    operateur=Operateur.superieur,
    numerateur=3,
    denominateur=8,
    seuil_numerateur=3,
    seuil_denominateur=10,
    tickets_en_cause=("DEMO-2",),
)
"""Règle `>` à valeur fractionnaire : `IND-2 : 0,4 (seuil > 0,3)`."""

REGLE_ROUGE = RegleDeclenchante(
    code=CodeIndicateur.ind_1,
    couleur=Couleur.rouge,
    operateur=Operateur.superieur_ou_egal,
    numerateur=7,
    denominateur=1,
    seuil_numerateur=3,
    seuil_denominateur=1,
    tickets_en_cause=("DEMO-6", "DEMO-24"),
)
"""Règle `>=` à valeur entière : `IND-1 : 7 (seuil ≥ 3)`."""


@pytest.fixture
def passage_jaune_rouge(tmp_path: Path) -> ConsultationPassage:
    """Passage réduit à un `meteo.json` : ENT-J jaune, ENT-R rouge, à la Date d'arrêté."""
    meteos = (
        MeteoEntite(
            date_arrete=DATE_ARRETE,
            entite="ENT-J",
            couleur=Couleur.jaune,
            regles=(REGLE_JAUNE,),
            version_grille="abc",
        ),
        MeteoEntite(
            date_arrete=DATE_ARRETE,
            entite="ENT-R",
            couleur=Couleur.rouge,
            regles=(REGLE_ROUGE,),
            version_grille="abc",
        ),
    )
    modele = EnveloppeFichier[tuple[MeteoEntite, ...]]
    enveloppe = modele(
        passage_id="20261012T073000Z-abcdef", date_arrete=DATE_ARRETE, contenu=meteos
    )
    (tmp_path / "meteo.json").write_text(enveloppe.model_dump_json(), encoding="utf-8")
    return ConsultationPassage(tmp_path, date_arrete=DATE_ARRETE)
