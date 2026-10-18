"""Carte météo : Météo, tendance J-1 / J-5, Règle principale et tickets en cause."""

import inspect
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from usine.config import charger_yaml
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import (
    LIBELLES_COULEURS,
    CodeIndicateur,
    Couleur,
    EvolutionMeteo,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.passage import ManifestePassage
from usine.ports.consultation import Consultation
from usine.rendu.commun import formater_regle as formater_regle_rendu
from usine.ui.carte import (
    LEGENDE,
    LectureCarte,
    fleche,
    formater_regle,
    regle_principale,
    tendance,
)
from usine.ui.cli import consultation_dernier_passage, mode_repli

DATE = date(2026, 10, 9)
LIEN = re.compile(r"\[((?:\\.|[^\]\\])+)\]\(([^)]+)\)")


def _url(cle: str) -> str:
    return f"https://jira.example.invalid/browse/{cle}"


def _sans_url(_cle: str) -> None:
    return None


def _regle(
    tickets: tuple[str, ...] = ("DEMO-1",),
    code: CodeIndicateur = CodeIndicateur.ind_2,
    numerateur: int = 11,
    denominateur: int = 1,
    operateur: Operateur = Operateur.superieur,
) -> RegleDeclenchante:
    return RegleDeclenchante(
        code=code,
        couleur=Couleur.rouge,
        operateur=operateur,
        numerateur=numerateur,
        denominateur=denominateur,
        seuil_numerateur=10,
        seuil_denominateur=1,
        tickets_en_cause=tickets,
    )


def _meteo(entite: str = "ENT-A", regles: tuple[RegleDeclenchante, ...] = ()) -> MeteoEntite:
    return MeteoEntite(
        date_arrete=DATE,
        entite=entite,
        couleur=Couleur.rouge if regles else Couleur.vert,
        regles=regles,
        version_grille="abc",
    )


def _evolution(
    couleur: Couleur, j1: Couleur | None, j5: Couleur | None, entite: str = "ENT-A"
) -> EvolutionMeteo:
    return EvolutionMeteo(
        entite=entite,
        date_arrete=DATE,
        couleur=couleur,
        date_j1=date(2026, 10, 8),
        couleur_j1=j1,
        date_j5=date(2026, 10, 2),
        couleur_j5=j5,
    )


# Passage publié (graine 42, 09/10/2026)


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


# Alignement du Protocol local sur le port


@pytest.mark.parametrize("nom", ["manifeste", "meteo", "evolution_meteo", "url_ticket"])
def test_lecture_carte_alignee_sur_consultation(nom: str) -> None:
    assert inspect.signature(getattr(LectureCarte, nom)) == inspect.signature(
        getattr(Consultation, nom)
    )


def test_lecture_carte_sans_methode_inconnue() -> None:
    def methodes(classe: type) -> set[str]:
        return {
            nom
            for nom, valeur in vars(classe).items()
            if inspect.isfunction(valeur) and not nom.startswith("_")
        }

    assert methodes(LectureCarte) == {"manifeste", "meteo", "evolution_meteo", "url_ticket"}
    assert methodes(LectureCarte) <= methodes(Consultation)


# Fonctions pures


@pytest.mark.parametrize(
    ("avant", "maintenant", "attendue"),
    [
        (Couleur.orange, Couleur.rouge, "↗"),
        (Couleur.rouge, Couleur.orange, "↘"),
        (Couleur.jaune, Couleur.jaune, "→"),
        (None, Couleur.rouge, "—"),
    ],
)
def test_fleche(avant: Couleur | None, maintenant: Couleur, attendue: str) -> None:
    assert fleche(avant, maintenant) == attendue


def test_tendance() -> None:
    assert tendance(_evolution(Couleur.rouge, Couleur.orange, Couleur.orange)) == "J-1 ↗ · J-5 ↗"
    assert tendance(_evolution(Couleur.orange, None, Couleur.rouge)) == "J-1 — · J-5 ↘"
    assert tendance(None) == "J-1 — · J-5 —"
    assert all(symbole in LEGENDE for symbole in "↗↘→—")


def test_formater_regle() -> None:
    assert formater_regle(_regle()) == "IND-2 : 11 (seuil > 10)"
    regle = _regle(numerateur=21, denominateur=2, operateur=Operateur.superieur_ou_egal)
    assert formater_regle(regle) == "IND-2 : 10,5 (seuil ≥ 10)"
    assert formater_regle(_regle(numerateur=1, denominateur=0)) == "IND-2 : ∞ (seuil > 10)"


@pytest.mark.parametrize(
    "regle",
    [
        _regle(),
        _regle(operateur=Operateur.superieur_ou_egal),
        _regle(numerateur=21, denominateur=2, operateur=Operateur.superieur_ou_egal),
        _regle(numerateur=1, denominateur=0),
    ],
)
def test_formater_regle_identique_au_rendu(regle: RegleDeclenchante) -> None:
    assert formater_regle(regle) == formater_regle_rendu(regle)


def test_regle_principale() -> None:
    assert regle_principale(_meteo()) == "—"
    assert regle_principale(_meteo(regles=(_regle(),))) == "IND-2 : 11 (seuil > 10)"
    trois = (_regle(code=CodeIndicateur.ind_1), _regle(), _regle(code=CodeIndicateur.ind_5))
    assert regle_principale(_meteo(regles=trois)) == "IND-1 : 11 (seuil > 10) (+2)"


class _ConsultationFigee:
    def __init__(self, evolutions: tuple[EvolutionMeteo, ...] = ()) -> None:
        self.evolutions = evolutions

    def manifeste(self) -> ManifestePassage:
        instant = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)
        return ManifestePassage(
            passage_id="20261012T073000Z-aaaaaa",
            date_arrete=DATE,
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
        return (_meteo("ENT-A"), _meteo("ENT-B", regles=(_regle(),)))

    def evolution_meteo(self, date_arrete: date | None = None) -> tuple[EvolutionMeteo, ...]:
        return self.evolutions

    def url_ticket(self, cle: str) -> str | None:
        return _url(cle)


def test_libelles_francais() -> None:
    assert set(LIBELLES_COULEURS) == set(Couleur)
