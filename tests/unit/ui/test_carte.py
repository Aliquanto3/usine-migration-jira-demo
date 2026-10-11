"""Carte météo : une ligne par Entité, couleur de `Consultation.meteo()` et Date d'arrêté."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from usine.composition import consultation_dernier_passage, mode_repli
from usine.config import charger_yaml
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import Couleur, MeteoEntite
from usine.contrats.passage import ManifestePassage
from usine.ui.carte import LIBELLES_COULEURS, date_carte, lignes_carte


def test_carte_du_passage_publie(racine_publiee: Path) -> None:
    consultation = consultation_dernier_passage(racine_publiee)
    assert consultation is not None
    lignes = lignes_carte(consultation)
    assert [ligne["Entité"] for ligne in lignes] == ["ENT-A", "ENT-B"]
    for ligne, meteo in zip(lignes, consultation.meteo(), strict=True):
        assert ligne["Météo"].endswith(LIBELLES_COULEURS[meteo.couleur])
    assert date_carte(consultation) == "09/10/2026"


def test_url_jira(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    url = charger_yaml(racine_publiee / "config" / "jira.yaml", ConfigJira).url_site.rstrip("/")
    consultation = consultation_dernier_passage(racine_publiee)
    assert consultation is not None
    assert consultation.url_ticket("DEMO-1") == f"{url}/browse/DEMO-1"
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    en_repli = consultation_dernier_passage(racine_publiee)
    assert en_repli is not None
    assert en_repli.url_ticket("DEMO-1") is None


def test_mode_repli_illisible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USINE_MODE_REPLI", "peut-etre")
    with pytest.raises(UsineErreur, match="USINE_MODE_REPLI"):
        mode_repli(tmp_path)


def test_sans_passage(tmp_path: Path) -> None:
    assert consultation_dernier_passage(tmp_path) is None


class _ConsultationFigee:
    def manifeste(self) -> ManifestePassage:
        instant = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)
        return ManifestePassage(
            passage_id="20261012T073000Z-aaaaaa",
            date_arrete=date(2026, 10, 9),
            palier=1,
            source="journal",
            horodatage_debut=instant,
            horodatage_fin=instant,
            version_grille="abc",
            version_donnees="def",
            cout_llm_eur=Decimal(0),
            nb_alignements=0,
            nb_tickets=0,
            etapes=(),
        )

    def meteo(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[MeteoEntite, ...]:
        return (
            MeteoEntite(
                date_arrete=date(2026, 10, 9),
                entite="ENT-A",
                couleur=Couleur.vert,
                regles=(),
                version_grille="abc",
            ),
        )


def test_libelles_francais() -> None:
    consultation = _ConsultationFigee()
    assert lignes_carte(consultation) == [{"Entité": "ENT-A", "Météo": "🟢 Vert"}]
    assert date_carte(consultation) == "09/10/2026"
    assert set(LIBELLES_COULEURS) == set(Couleur)
