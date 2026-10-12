"""Outil `outils/mesurer_nfr2.py` : Programme à la volumétrie de la mesure NFR-2 (Story 1.3)."""

from datetime import date

import pytest

from outils.mesurer_nfr2 import NB_ANOMALIES, NB_ENTITES, NB_SEMAINES, programme_cible
from usine.contrats.evenements import NatureEvenement
from usine.contrats.tickets import Champ, TypeTicket
from usine.generateur.journal import generer


def test_programme_cible() -> None:
    programme = programme_cible(42)
    assert programme.graine == 42
    assert programme.nb_semaines == NB_SEMAINES == 8
    assert len(programme.entites) == NB_ENTITES == 10
    assert len({e.code for e in programme.entites}) == 10
    volumetrie = programme.volumetrie
    assert volumetrie.anomalies_min == volumetrie.anomalies_max == NB_ANOMALIES == 5000
    # Entrées élargies : 5 000 Anomalies tiennent dans 8 semaines, marge de réouvertures comprise.
    assert volumetrie.entrees_semaine_max == 1250
    assert NB_SEMAINES * volumetrie.entrees_semaine_max * 9 // 10 >= NB_ANOMALIES


@pytest.mark.lent
def test_generation_a_5000_anomalies() -> None:
    generation = generer(programme_cible(42), 42, date(2026, 10, 12))
    anomalies = [
        e
        for e in generation.evenements
        if e.nature is NatureEvenement.creation and e.type_ticket is TypeTicket.anomalie
    ]
    assert len(anomalies) == NB_ANOMALIES
    entites = {e.vers for e in generation.evenements if e.champ is Champ.entite}
    assert len(entites) == NB_ENTITES
    assert len(generation.verite_terrain) == NB_ANOMALIES
