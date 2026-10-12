"""État de la Prévision d'une Entité : Prévision, Risque, aucun Risque, non calculée (Story 5.3)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.unit.chaine.environnement import DATE_ARRETE, contenu_previsions
from usine.consultation.passage import ConsultationPassage
from usine.consultation.prevision import EtatPrevision, etat_prevision, previsions_calculees
from usine.contrats.meteo import (
    CodeIndicateur,
    Couleur,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.passage import (
    EnveloppeFichier,
    Etape,
    ExecutionEtape,
    ManifestePassage,
    StatutEtape,
)
from usine.contrats.prevision import ContenuPrevisions

PASSAGE_ID = "20261012T073000Z-abcdef"
INSTANT = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)

ROUGE = RegleDeclenchante(
    code=CodeIndicateur.ind_1,
    couleur=Couleur.rouge,
    operateur=Operateur.superieur_ou_egal,
    numerateur=12,
    denominateur=1,
    seuil_numerateur=3,
    seuil_denominateur=1,
    tickets_en_cause=("DEMO-1",),
)


def _meteo(entite: str, couleur: Couleur) -> MeteoEntite:
    regles = () if couleur is Couleur.vert else (ROUGE.model_copy(update={"couleur": couleur}),)
    return MeteoEntite(
        date_arrete=DATE_ARRETE,
        entite=entite,
        couleur=couleur,
        regles=regles,
        version_grille="grille",
    )


def _ecrire[T](chemin: Path, contenu: T) -> None:
    enveloppe = EnveloppeFichier[T](passage_id=PASSAGE_ID, date_arrete=DATE_ARRETE, contenu=contenu)
    chemin.write_text(enveloppe.model_dump_json(), encoding="utf-8")


@pytest.fixture
def consultation(tmp_path: Path) -> ConsultationPassage:
    """ENT-A rouge avec Prévision, ENT-B jaune avec Risque, ENT-C verte, ENT-R rouge sans."""
    meteos = (
        _meteo("ENT-A", Couleur.rouge),
        _meteo("ENT-B", Couleur.jaune),
        _meteo("ENT-C", Couleur.vert),
        _meteo("ENT-R", Couleur.rouge),
    )
    _ecrire(tmp_path / "meteo.json", meteos)
    _ecrire(tmp_path / "previsions.json", contenu_previsions(DATE_ARRETE, "grille"))
    return ConsultationPassage(tmp_path, date_arrete=DATE_ARRETE)


@pytest.mark.parametrize(
    ("entite", "attendu"),
    [
        ("ENT-A", EtatPrevision.prevision),
        ("ENT-B", EtatPrevision.risque),
        ("ENT-C", EtatPrevision.aucun_risque),
        ("ENT-R", EtatPrevision.non_calculee),  # rouge sans Prévision
        ("ENT-Z", EtatPrevision.non_calculee),  # absente de la Météo
    ],
)
def test_etats_calcules(
    consultation: ConsultationPassage, entite: str, attendu: EtatPrevision
) -> None:
    assert etat_prevision(consultation, entite, DATE_ARRETE, calculees=True) is attendu
    assert etat_prevision(consultation, entite, None, calculees=True) is attendu


@pytest.mark.parametrize("entite", ["ENT-A", "ENT-B", "ENT-C"])
def test_non_calculees(consultation: ConsultationPassage, entite: str) -> None:
    """Étape `prevision` non réussie : « non calculée », même avec un `previsions.json`."""
    assert etat_prevision(consultation, entite, DATE_ARRETE, calculees=False) is (
        EtatPrevision.non_calculee
    )


def test_aucun_previsions_json(tmp_path: Path) -> None:
    """Prévision calculée sans `previsions.json` : aucun Risque (cas des anciens bouchons)."""
    _ecrire(tmp_path / "meteo.json", (_meteo("ENT-B", Couleur.jaune),))
    consultation = ConsultationPassage(tmp_path, date_arrete=DATE_ARRETE)
    assert consultation.previsions() == ()
    assert etat_prevision(consultation, "ENT-B", DATE_ARRETE, True) is EtatPrevision.aucun_risque
    vide = ContenuPrevisions(previsions=(), risques=())
    _ecrire(tmp_path / "previsions.json", vide)
    assert etat_prevision(consultation, "ENT-B", DATE_ARRETE, True) is EtatPrevision.aucun_risque


def _manifeste(etapes: dict[Etape, StatutEtape]) -> ManifestePassage:
    return ManifestePassage(
        passage_id=PASSAGE_ID,
        date_arrete=DATE_ARRETE,
        palier=1,
        source="journal",
        horodatage_debut=INSTANT,
        horodatage_fin=INSTANT + timedelta(seconds=1),
        version_grille="grille",
        version_donnees="donnees",
        cout_llm_eur=0,
        nb_alignements=0,
        nb_tickets=0,
        etapes=tuple(
            ExecutionEtape(
                etape=etape, statut=statut, horodatage_debut=INSTANT, horodatage_fin=INSTANT
            )
            for etape, statut in etapes.items()
        ),
    )


@pytest.mark.parametrize(
    ("etapes", "attendu"),
    [
        ({Etape.meteo: StatutEtape.reussie, Etape.prevision: StatutEtape.reussie}, True),
        ({Etape.meteo: StatutEtape.reussie, Etape.prevision: StatutEtape.sautee}, False),
        ({Etape.meteo: StatutEtape.reussie}, False),
    ],
    ids=["reussie", "sautee", "absente"],
)
def test_previsions_calculees(etapes: dict[Etape, StatutEtape], attendu: bool) -> None:
    assert previsions_calculees(_manifeste(etapes)) is attendu
