"""Événement canonique et Journal (AD-3, AD-4)."""

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import polars as pl
import pytest
from pydantic import ValidationError

from usine.contrats.evenements import (
    SCHEMA_EVENEMENT,
    EnteteJournal,
    Evenement,
    ManifesteInjection,
    NatureEvenement,
    evenements_en_table,
)

H = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)


def _evenement(**champs: Any) -> Evenement:
    base: dict[str, Any] = {
        "id_evenement": "J-1",
        "cle_ticket": "DEMO-1",
        "type_ticket": "anomalie",
        "horodatage": H,
        "nature": "transition",
        "champ": "statut",
        "de": "nouvelle",
        "vers": "en_correction",
        "source": "journal",
    }
    base.update(champs)
    return Evenement.model_validate(base)


def test_transition_valide() -> None:
    evenement = _evenement()
    assert evenement.nature is NatureEvenement.transition


def test_gele() -> None:
    evenement = _evenement()
    with pytest.raises(ValidationError):
        evenement.vers = "fermee"  # type: ignore[misc]


def test_horodatage_ramene_en_utc() -> None:
    paris = timezone(timedelta(hours=2))
    evenement = _evenement(horodatage=datetime(2026, 10, 12, 10, 0, tzinfo=paris))
    assert evenement.horodatage == H
    assert evenement.horodatage.tzinfo == UTC


def test_horodatage_naif_refuse() -> None:
    with pytest.raises(ValidationError):
        _evenement(horodatage=datetime(2026, 10, 12, 10, 0))  # noqa: DTZ001


def test_libelle_d_affichage_refuse() -> None:
    with pytest.raises(ValidationError):
        _evenement(vers="Fermée")


def test_creation_sans_champ() -> None:
    _evenement(nature="creation", champ=None, de=None, vers=None)
    with pytest.raises(ValidationError):
        _evenement(nature="creation")


def test_transition_hors_statut_refusee() -> None:
    with pytest.raises(ValidationError):
        _evenement(champ="gravite", de="mineure", vers="majeure")


def test_transition_sans_vers_ou_sans_effet() -> None:
    with pytest.raises(ValidationError, match="exige « vers »"):
        _evenement(vers=None)
    with pytest.raises(ValidationError, match="sans effet"):
        _evenement(de="en_correction", vers="en_correction")
    assert _evenement(de=None, vers="nouvelle").de is None


@pytest.mark.parametrize("nature", ["modification_champ", "alignement"])
def test_modification_ou_alignement_sans_effet_refuse(nature: str) -> None:
    with pytest.raises(ValidationError, match="sans effet"):
        _evenement(nature=nature, de="en_correction", vers="en_correction")
    with pytest.raises(ValidationError, match="sans effet"):
        _evenement(nature=nature, champ="entite", de="ENT-A", vers="ENT-A")
    assert _evenement(nature=nature, de=None, vers="nouvelle").vers == "nouvelle"


def test_modification_exige_un_champ() -> None:
    with pytest.raises(ValidationError):
        _evenement(nature="modification_champ", champ=None)


def test_champ_sans_objet_pour_le_type() -> None:
    with pytest.raises(ValidationError):
        _evenement(
            type_ticket="cas_de_test",
            nature="modification_champ",
            champ="gravite",
            de=None,
            vers="majeure",
        )


def test_champ_libre() -> None:
    evenement = _evenement(nature="modification_champ", champ="entite", de=None, vers="ENT-A")
    assert evenement.vers == "ENT-A"


def test_cause_racine_refusee() -> None:
    with pytest.raises(ValidationError):
        _evenement(nature="modification_champ", champ="cause_racine", de=None, vers="parametrage")
    with pytest.raises(ValidationError):
        _evenement(cause_racine="parametrage")


def test_alignement() -> None:
    _evenement(id_evenement="A-DEMO-1-statut-1a2b3c4d", nature="alignement", source="jira_cloud")


def test_cle_de_ticket_invalide() -> None:
    with pytest.raises(ValidationError):
        _evenement(cle_ticket="demo 1")


def test_entete_journal() -> None:
    entete = EnteteJournal(
        graine=42,
        date_generation=date(2026, 10, 12),
        date_injection=date(2026, 10, 9),
        ancrage_semaines=date(2026, 8, 17),
        version_corpus="1",
        modele_corpus="mistral:petit",
    )
    assert entete.contrats_version == "1.3.0"
    with pytest.raises(ValidationError, match="lundi"):
        EnteteJournal.model_validate(entete.model_dump() | {"ancrage_semaines": date(2026, 8, 18)})


@pytest.mark.parametrize(
    "remplacement",
    [
        {"date_injection": date(2026, 10, 13)},
        {"ancrage_semaines": date(2026, 10, 12), "date_injection": date(2026, 10, 9)},
        {"date_generation": date(2026, 10, 8)},
    ],
    ids=["injection_apres_generation", "ancrage_apres_injection", "generation_avant_injection"],
)
def test_entete_journal_ordre_des_dates(remplacement: dict[str, Any]) -> None:
    base: dict[str, Any] = {
        "graine": 42,
        "date_generation": date(2026, 10, 12),
        "date_injection": date(2026, 10, 9),
        "ancrage_semaines": date(2026, 8, 17),
        "version_corpus": "1",
        "modele_corpus": "mistral:petit",
    }
    with pytest.raises(ValidationError, match="ordre attendu"):
        EnteteJournal.model_validate(base | remplacement)


def test_entete_journal_version_majeure_differente() -> None:
    with pytest.raises(ValidationError, match="incompatible"):
        EnteteJournal(
            contrats_version="2.0.0",
            graine=42,
            date_generation=date(2026, 10, 12),
            date_injection=date(2026, 10, 9),
            ancrage_semaines=date(2026, 8, 17),
            version_corpus="1",
            modele_corpus="mistral:petit",
        )


def test_manifeste_injection() -> None:
    manifeste = ManifesteInjection(
        date_injection=date(2026, 10, 9),
        debut_injection=H,
        horodatage_fin_injection=H + timedelta(minutes=5),
        cle_projet="DEMO",
        correspondance_cles={"GEN-1": "DEMO-1"},
    )
    assert manifeste.correspondance_cles["GEN-1"] == "DEMO-1"
    with pytest.raises(ValidationError):
        ManifesteInjection.model_validate(
            manifeste.model_dump() | {"horodatage_fin_injection": H - timedelta(minutes=1)}
        )
    with pytest.raises(ValidationError, match="hors du projet DEMO"):
        ManifesteInjection.model_validate(
            manifeste.model_dump() | {"correspondance_cles": {"GEN-1": "AUTRE-1"}}
        )
    with pytest.raises(ValidationError, match="injective"):
        ManifesteInjection.model_validate(
            manifeste.model_dump() | {"correspondance_cles": {"GEN-1": "DEMO-1", "GEN-2": "DEMO-1"}}
        )
    with pytest.raises(ValidationError, match="incompatible"):
        ManifesteInjection.model_validate(manifeste.model_dump() | {"contrats_version": "2.0.0"})


def test_evenements_en_table() -> None:
    evenements = [
        _evenement(nature="creation", champ=None, de=None, vers=None),
        _evenement(id_evenement="J-2"),
    ]
    table = evenements_en_table(evenements)
    assert table.columns == list(SCHEMA_EVENEMENT.colonnes)
    assert table["horodatage"].dtype == pl.Datetime("us", "UTC")
    assert table["champ"].to_list() == [None, "statut"]
    assert table["horodatage"][0] == H


def test_evenements_en_table_vide() -> None:
    assert evenements_en_table([]).is_empty()


def test_colonnes_d_enumeration() -> None:
    table = evenements_en_table([_evenement()])
    for colonne in ("type_ticket", "nature", "champ", "source"):
        assert isinstance(table[colonne].dtype, pl.Enum), colonne
    assert table["de"].dtype == pl.Utf8
    assert table["nature"].dtype == pl.Enum([n.value for n in NatureEvenement])
