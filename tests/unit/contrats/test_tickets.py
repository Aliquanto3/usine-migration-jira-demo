"""Vocabulaire canonique des tickets (AD-23, H-17, H-18)."""

import re
from datetime import date
from enum import StrEnum

import polars as pl
import pytest

from usine.contrats import UsineErreur, valider
from usine.contrats.tickets import (
    CHAMPS_PAR_TYPE,
    DOMAINES_CANONIQUES,
    LIBELLES,
    MOTIF_CLE_TICKET,
    SCHEMA_TICKET_ETAT,
    SCHEMA_TICKET_TEXTE,
    STATUTS_FERMES,
    CauseRacine,
    Champ,
    Gravite,
    Phase,
    StatutAnomalie,
    StatutCertification,
    StatutTest,
    TypeTicket,
    rang_cle,
)

ENUMERATIONS: tuple[type[StrEnum], ...] = (
    TypeTicket,
    Champ,
    StatutAnomalie,
    Gravite,
    Phase,
    StatutTest,
    StatutCertification,
    CauseRacine,
)


def test_champ_sans_cause_racine() -> None:
    assert "cause_racine" not in {c.value for c in Champ}
    assert len(Champ) == 10


def test_effectifs_des_enumerations() -> None:
    assert [g.value for g in Gravite] == ["bloquante", "majeure", "mineure"]


def test_statuts_d_anomalie_h17() -> None:
    assert [s.value for s in StatutAnomalie] == [
        "nouvelle",
        "en_analyse",
        "en_correction",
        "a_retester",
        "fermee",
        "rejetee",
    ]


def test_causes_racines_h18() -> None:
    assert [c.value for c in CauseRacine] == [
        "reprise_donnees",
        "regle_transformation",
        "parametrage",
        "interface_flux",
        "environnement",
        "donnee_test",
        "hors_perimetre",
    ]


def test_colonnes_d_enumeration_des_tickets() -> None:
    assert SCHEMA_TICKET_ETAT.colonnes["statut"] == pl.Enum([s.value for s in StatutAnomalie])
    assert SCHEMA_TICKET_ETAT.colonnes["gravite"] == pl.Enum(["bloquante", "majeure", "mineure"])
    assert SCHEMA_TICKET_TEXTE.colonnes["type_ticket"] == pl.Enum([t.value for t in TypeTicket])
    for libre in ("entite", "vague", "domaine", "cle_ticket"):
        assert SCHEMA_TICKET_ETAT.colonnes[libre] == pl.Utf8()
    ligne = {
        "date": [date(2026, 10, 12)],
        "cle_ticket": ["DEMO-1"],
        "type_ticket": ["anomalie"],
        "entite": ["ENT-A"],
        "vague": ["V1"],
        "domaine": ["credits"],
        "gravite": ["bloquante"],
        "phase": ["recette"],
        "statut": ["En correction"],
        "statut_test": [None],
        "statut_certification": [None],
        "date_derniere_entree": [date(2026, 10, 5)],
    }
    with pytest.raises(pl.exceptions.InvalidOperationError):
        pl.DataFrame(ligne, schema=dict(SCHEMA_TICKET_ETAT.colonnes))
    texte = pl.DataFrame(ligne).with_columns(pl.col("statut").replace("En correction", "x"))
    with pytest.raises(UsineErreur, match="SCHEMA_TICKET_ETAT"):
        valider(texte, SCHEMA_TICKET_ETAT)
    ligne["statut"] = ["en_correction"]
    valider(pl.DataFrame(ligne, schema=dict(SCHEMA_TICKET_ETAT.colonnes)), SCHEMA_TICKET_ETAT)


def test_valeurs_canoniques_snake_case_sans_accent() -> None:
    for enumeration in ENUMERATIONS:
        for membre in enumeration:
            assert re.fullmatch(r"[a-z][a-z0-9_]*", membre.value), membre
            assert membre.name == membre.value


def test_domaine_canonique_de_chaque_champ() -> None:
    assert set(DOMAINES_CANONIQUES) == set(Champ)
    assert DOMAINES_CANONIQUES[Champ.statut] == frozenset(s.value for s in StatutAnomalie)
    assert DOMAINES_CANONIQUES[Champ.gravite] == frozenset(g.value for g in Gravite)
    for libre in (Champ.entite, Champ.vague, Champ.domaine, Champ.titre, Champ.description):
        assert DOMAINES_CANONIQUES[libre] is None


def test_champs_par_type() -> None:
    assert set(CHAMPS_PAR_TYPE) == set(TypeTicket)
    assert Champ.statut in CHAMPS_PAR_TYPE[TypeTicket.anomalie]
    assert Champ.statut_test in CHAMPS_PAR_TYPE[TypeTicket.cas_de_test]
    assert Champ.statut_certification in CHAMPS_PAR_TYPE[TypeTicket.certification]
    assert Champ.gravite not in CHAMPS_PAR_TYPE[TypeTicket.cas_de_test]
    assert set().union(*CHAMPS_PAR_TYPE.values()) == set(Champ)


def test_statuts_fermes() -> None:
    assert {StatutAnomalie.fermee, StatutAnomalie.rejetee} == STATUTS_FERMES


def test_libelle_pour_chaque_valeur() -> None:
    for enumeration in ENUMERATIONS:
        if enumeration is Champ:
            continue
        for membre in enumeration:
            assert LIBELLES[membre]
    assert LIBELLES["a_retester"] == "À retester"
    assert LIBELLES["en_correction"] == "En correction"


def test_motif_cle_ticket() -> None:
    assert re.fullmatch(MOTIF_CLE_TICKET, "DEMO-123")
    assert not re.fullmatch(MOTIF_CLE_TICKET, "demo-123")
    assert not re.fullmatch(MOTIF_CLE_TICKET, "ENT-A")


def test_rang_cle() -> None:
    cles = ["DEMO-10", "AUTRE-1", "DEMO-2", "DEMO-X", "DEMO-²", "DEMO-1"]
    assert sorted(cles, key=rang_cle) == [
        "AUTRE-1",
        "DEMO-X",
        "DEMO-²",
        "DEMO-1",
        "DEMO-2",
        "DEMO-10",
    ]
    assert rang_cle("DEMO-12") == ("DEMO", 12, "DEMO-12")
    assert rang_cle("SANSTIRET") == ("", -1, "SANSTIRET")
