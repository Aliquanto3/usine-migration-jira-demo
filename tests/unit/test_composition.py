"""Racine de composition : secrets, URL Jira et sélection de l'extraction Jira (Story 2.4)."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.unit.adaptateurs.jira_dc.outils import ServeurFixturesDC
from tests.unit.adaptateurs.jira_dc.outils import (
    evenements_attendus as evenements_attendus_dc,
)
from tests.unit.adaptateurs.jira_http.outils import Attentes
from tests.unit.chaine.environnement import DATE_ARRETE, INSTANT, horloge_figee, preparer_racine
from usine import composition
from usine.adaptateurs.entrepot_duckdb import EntrepotDuckDB, EtapeExtraction
from usine.adaptateurs.jira_cloud import SourceJiraCloud
from usine.adaptateurs.jira_dc import SourceJiraDC
from usine.adaptateurs.jira_http import construire_client_lecture
from usine.chaine.etapes import EtapeBouchon
from usine.config import charger_yaml
from usine.contrats.config import ConfigJira, ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import Etape
from usine.ports.etape import Etape as PortEtape

_VARIABLES_JIRA = ("USINE_MODE_REPLI", "JIRA_EMAIL", "JIRA_TOKEN_LECTURE", "JIRA_DC_PAT")


@pytest.fixture
def racine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for variable in _VARIABLES_JIRA:
        monkeypatch.delenv(variable, raising=False)
    return preparer_racine(tmp_path, journal=False)


def test_url_jira(racine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    url = charger_yaml(racine / "config" / "jira.yaml", ConfigJira).url_site
    assert composition.url_jira(racine) == url
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    assert composition.url_jira(racine) is None


def test_url_jira_sans_configuration(racine: Path) -> None:
    (racine / "config" / "jira.yaml").unlink()
    assert composition.url_jira(racine) is None


def test_secrets_illisibles(racine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USINE_MODE_REPLI", "peut-être")
    with pytest.raises(UsineErreur, match="USINE_MODE_REPLI"):
        composition.construire_rapport(racine)


def test_generer_journal_delegue(racine: Path) -> None:
    programme = charger_yaml(racine / "config" / "programme.yaml", ConfigProgramme)
    chemin = composition.generer_journal(programme, 42, date(2026, 10, 12), racine)
    assert chemin == racine / "donnees" / "journal.jsonl"
    assert chemin.is_file()
    assert (racine / "donnees" / "verite_terrain.json").is_file()


def test_grille_incoherente_refusee_au_chargement(racine: Path) -> None:
    """FR-18 : orange plus sévère que rouge refusé avant tout Passage (Story 3.4)."""
    chemin = racine / "config" / "grille_meteo.yaml"
    texte = chemin.read_text(encoding="utf-8")
    assert 'orange: ">= 1"' in texte
    chemin.write_text(texte.replace('orange: ">= 1"', 'orange: ">= 4"', 1), encoding="utf-8")
    with pytest.raises(UsineErreur) as erreur:
        composition.construire_rapport(racine)
    message = str(erreur.value)
    assert str(chemin) in message
    assert "IND-1" in message
    assert "« >= 4 »" in message


# --- Sélection de l'étape `extraction` (Story 2.4) ---


def _passer_en_dc(racine: Path) -> None:
    chemin = racine / "config" / "jira.yaml"
    texte = chemin.read_text(encoding="utf-8")
    assert "\nmode: cloud\n" in texte
    chemin.write_text(texte.replace("\nmode: cloud\n", "\nmode: dc\n", 1), encoding="utf-8")


def _etape_extraction(racine: Path) -> PortEtape:
    return composition.construire_rapport(racine).registre[Etape.extraction]


def _interdire_le_client(monkeypatch: pytest.MonkeyPatch) -> None:
    def construire(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("client Jira construit sans extraction attendue")

    monkeypatch.setattr(composition, "construire_client_lecture", construire)


@pytest.fixture
def racine_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for variable in _VARIABLES_JIRA:
        monkeypatch.delenv(variable, raising=False)
    return preparer_racine(tmp_path)


def test_sans_secret_extraction_bouchon(
    racine_journal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _interdire_le_client(monkeypatch)
    assert isinstance(_etape_extraction(racine_journal), EtapeBouchon)
    # Le secret de l'autre plateforme ne suffit pas.
    monkeypatch.setenv("JIRA_DC_PAT", "pat-fictif")
    assert isinstance(_etape_extraction(racine_journal), EtapeBouchon)


@pytest.mark.parametrize("mode", ["cloud", "dc"])
def test_secret_blanc_extraction_bouchon(
    racine_journal: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    if mode == "dc":
        _passer_en_dc(racine_journal)
    monkeypatch.setenv("JIRA_DC_PAT", "   ")
    monkeypatch.setenv("JIRA_TOKEN_LECTURE", "   ")
    monkeypatch.setenv("JIRA_EMAIL", "lecteur@example.invalid")
    _interdire_le_client(monkeypatch)
    assert isinstance(_etape_extraction(racine_journal), EtapeBouchon)


def test_sans_configuration_jira_extraction_bouchon(
    racine_journal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (racine_journal / "config" / "jira.yaml").unlink()
    monkeypatch.setenv("JIRA_DC_PAT", "pat-fictif")
    monkeypatch.setenv("JIRA_TOKEN_LECTURE", "jeton-fictif")
    _interdire_le_client(monkeypatch)
    assert isinstance(_etape_extraction(racine_journal), EtapeBouchon)


def test_mode_repli_coupe_l_extraction(
    racine_journal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _passer_en_dc(racine_journal)
    monkeypatch.setenv("JIRA_DC_PAT", "pat-fictif")
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    _interdire_le_client(monkeypatch)
    assert isinstance(_etape_extraction(racine_journal), EtapeBouchon)


def test_cloud_avec_jeton_et_email(racine_journal: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIRA_TOKEN_LECTURE", "jeton-fictif")
    monkeypatch.setenv("JIRA_EMAIL", "lecteur@example.invalid")
    etape = _etape_extraction(racine_journal)
    assert isinstance(etape, EtapeExtraction)
    assert isinstance(etape.source, SourceJiraCloud)
    assert etape.chemin == racine_journal / "donnees" / "entrepot.duckdb"
    assert etape.marge == timedelta(minutes=10)


def test_dc_avec_pat(racine_journal: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _passer_en_dc(racine_journal)
    monkeypatch.setenv("JIRA_DC_PAT", "pat-fictif")
    etape = _etape_extraction(racine_journal)
    assert isinstance(etape, EtapeExtraction)
    assert isinstance(etape.source, SourceJiraDC)
    assert etape.chemin == racine_journal / "donnees" / "entrepot.duckdb"
    marge = charger_yaml(
        racine_journal / "config" / "jira.yaml", ConfigJira
    ).marge_extraction_minutes
    assert etape.marge == timedelta(minutes=marge)


def test_cloud_sans_email_nomme_la_variable(
    racine_journal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JIRA_TOKEN_LECTURE", "jeton-fictif")
    with pytest.raises(UsineErreur, match="JIRA_EMAIL"):
        composition.construire_rapport(racine_journal)


def test_passage_sans_secret_journal_seul_sans_requete(
    racine_journal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _interdire_le_client(monkeypatch)
    lance = composition.lancer_rapport(racine_journal, DATE_ARRETE, horloge_figee())
    assert lance.manifeste.source == "journal"
    assert lance.repertoire.is_dir()
    assert not (racine_journal / "donnees" / "entrepot.duckdb").exists()


def test_passage_dc_de_bout_en_bout(racine_journal: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _passer_en_dc(racine_journal)
    monkeypatch.setenv("JIRA_DC_PAT", "pat-fictif")
    serveur = ServeurFixturesDC()
    fermetures: list[str] = []

    def construire_simule(*args: Any, **kwargs: Any) -> Any:
        client = construire_client_lecture(
            *args, **kwargs, attendre=Attentes(), transport_http=httpx.MockTransport(serveur)
        )
        fermer = client.fermer

        def fermer_espion() -> None:
            fermetures.append("fermé")
            fermer()

        monkeypatch.setattr(client, "fermer", fermer_espion)
        return client

    monkeypatch.setattr(composition, "construire_client_lecture", construire_simule)
    lance = composition.lancer_rapport(racine_journal, DATE_ARRETE, horloge_figee())
    assert lance.repertoire.is_dir()
    assert lance.manifeste.source == "journal"
    assert serveur.inattendues == []
    assert {r.headers["Authorization"] for r in serveur.requetes} == {"Bearer pat-fictif"}
    assert fermetures == ["fermé"]
    entrepot = EntrepotDuckDB(racine_journal / "donnees" / "entrepot.duckdb")
    assert tuple(entrepot.evenements()) == evenements_attendus_dc()
    assert entrepot.repere() == INSTANT


def test_client_ferme_si_le_passage_echoue_avant_l_extraction(
    racine_journal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _passer_en_dc(racine_journal)
    monkeypatch.setenv("JIRA_DC_PAT", "pat-fictif")
    serveur = ServeurFixturesDC()
    fermetures: list[str] = []

    def construire_simule(*args: Any, **kwargs: Any) -> Any:
        client = construire_client_lecture(
            *args, **kwargs, attendre=Attentes(), transport_http=httpx.MockTransport(serveur)
        )
        monkeypatch.setattr(client, "fermer", lambda: fermetures.append("fermé"))
        return client

    def echouer(*args: Any, **kwargs: Any) -> Any:
        raise UsineErreur("Passage avorté avant l'extraction")

    monkeypatch.setattr(composition, "construire_client_lecture", construire_simule)
    monkeypatch.setattr(composition, "executer_passage", echouer)
    with pytest.raises(UsineErreur, match="avorté"):
        composition.lancer_rapport(racine_journal, DATE_ARRETE, horloge_figee())
    assert fermetures == ["fermé"]
    assert serveur.requetes == []
