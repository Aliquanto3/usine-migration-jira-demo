"""Contrat de `SourceTickets` : tout adaptateur rend le même flux canonique (AD-3, AD-20)."""

from datetime import datetime

import pytest

from tests.contrat.source_tickets.fabriques import CasSourceTickets
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, NatureEvenement
from usine.contrats.tickets import CHAMPS_PAR_TYPE, DOMAINES_CANONIQUES
from usine.ports import SourceTickets


def test_implemente_le_port(cas: CasSourceTickets) -> None:
    assert isinstance(cas.source, SourceTickets)


def test_rend_les_evenements_attendus(cas: CasSourceTickets) -> None:
    rendus = list(cas.source.evenements())
    assert all(isinstance(e, Evenement) for e in rendus)
    assert sorted(e.id_evenement for e in rendus) == sorted(
        e.id_evenement for e in cas.evenements_attendus
    )
    assert set(rendus) == set(cas.evenements_attendus)


def test_ordre_chronologique_et_identifiants_uniques(cas: CasSourceTickets) -> None:
    rendus = list(cas.source.evenements())
    horodatages = [e.horodatage for e in rendus]
    assert horodatages == sorted(horodatages)
    assert len({e.id_evenement for e in rendus}) == len(rendus)


def test_creation_suivie_de_ses_attributs_au_meme_horodatage(cas: CasSourceTickets) -> None:
    rendus = list(cas.source.evenements())
    for rang, evenement in enumerate(rendus):
        if evenement.nature is NatureEvenement.creation:
            suivants = [
                e
                for e in rendus[rang + 1 :]
                if e.cle_ticket == evenement.cle_ticket and e.horodatage == evenement.horodatage
            ]
            assert suivants, f"création de {evenement.cle_ticket} sans attribut initial"
            assert all(e.nature is NatureEvenement.modification_champ for e in suivants)
            precedents = [
                e
                for e in rendus[:rang]
                if e.cle_ticket == evenement.cle_ticket and e.horodatage == evenement.horodatage
            ]
            assert not precedents, (
                f"{evenement.cle_ticket} : événement émis avant sa création au même horodatage"
            )


def test_valeurs_dans_le_domaine_canonique(cas: CasSourceTickets) -> None:
    for evenement in cas.source.evenements():
        assert "cause_racine" not in evenement.model_dump()
        if evenement.champ is None:
            continue
        assert evenement.champ in CHAMPS_PAR_TYPE[evenement.type_ticket]
        domaine = DOMAINES_CANONIQUES[evenement.champ]
        if domaine is not None:
            for valeur in (evenement.de, evenement.vers):
                assert valeur is None or valeur in domaine


def test_horodatages_en_utc(cas: CasSourceTickets) -> None:
    for evenement in cas.source.evenements():
        assert evenement.horodatage.utcoffset() is not None
        assert evenement.horodatage.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_depuis_garde_les_evenements_a_partir_de_l_instant(cas: CasSourceTickets) -> None:
    horodatages = sorted({e.horodatage for e in cas.evenements_attendus})
    depuis = horodatages[len(horodatages) // 2]
    attendus = {e.id_evenement for e in cas.evenements_attendus if e.horodatage >= depuis}
    assert {e.id_evenement for e in cas.source.evenements(depuis)} == attendus


def test_depuis_sans_fuseau_refuse(cas: CasSourceTickets) -> None:
    with pytest.raises(UsineErreur):
        list(cas.source.evenements(datetime(2026, 10, 5, 8, 0)))  # noqa: DTZ001
