"""Cohérence à la Date d'injection (FR-49) : Instantané(Journal) = Instantané(état Jira).

L'état Jira juste après injection est converti en créations + alignements
(`convertir_etat_jira`), puis le vrai domaine calcule les deux Instantanés.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from tests.unit.adaptateurs.composite.outils import (
    autre_valeur,
    etat_a_l_injection,
    generation_reduite,
    injection_simulee,
    journal_aux_cles_jira,
    premiere_anomalie,
    transition_jira,
)
from usine.adaptateurs.composite import DetecteurAlignements, convertir_etat_jira
from usine.adaptateurs.journal import SourceJournal
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, NatureEvenement
from usine.contrats.tickets import Champ
from usine.domaine.instantanes import instantane, tickets_etats
from usine.generateur.journal import Generation

INSTANT = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)


@pytest.fixture(scope="module")
def generation() -> Generation:
    return generation_reduite()


@pytest.fixture
def journal(tmp_path: Path, generation: Generation) -> SourceJournal:
    return journal_aux_cles_jira(tmp_path, generation)


def _instantanes(journal: SourceJournal, jira: list[Evenement]) -> tuple[pl.DataFrame, ...]:
    manifeste = journal.manifeste
    assert manifeste is not None
    dates = [manifeste.date_injection]
    convertis = convertir_etat_jira(jira, manifeste.horodatage_fin_injection)
    return (
        instantane(tickets_etats(list(journal.evenements()), dates)),
        instantane(tickets_etats(convertis, dates)),
    )


def test_instantanes_identiques_a_la_date_d_injection(journal: SourceJournal) -> None:
    depuis_journal, depuis_jira = _instantanes(journal, injection_simulee(journal))
    assert depuis_journal.height > 0
    assert depuis_journal["nombre"].sum() == len({e.cle_ticket for e in journal.evenements()})
    assert_frame_equal(depuis_journal, depuis_jira)


def test_injection_infidele_instantanes_differents_un_alignement(journal: SourceJournal) -> None:
    cle = premiere_anomalie(journal)
    autre = autre_valeur(Champ.gravite, etat_a_l_injection(journal, cle, Champ.gravite))
    jira = injection_simulee(journal, {cle: {Champ.gravite: autre}})
    depuis_journal, depuis_jira = _instantanes(journal, jira)
    assert not depuis_journal.equals(depuis_jira)
    detectes = DetecteurAlignements(journal)(jira, INSTANT)
    assert [(e.cle_ticket, e.champ, e.vers) for e in detectes] == [(cle, Champ.gravite, autre)]


def test_conversion_creations_puis_un_alignement_par_champ(journal: SourceJournal) -> None:
    manifeste = journal.manifeste
    assert manifeste is not None
    fin = manifeste.horodatage_fin_injection
    injection = injection_simulee(journal)
    cle = premiere_anomalie(journal)
    statut = etat_a_l_injection(journal, cle, Champ.statut)
    apres = transition_jira(
        cle, statut, autre_valeur(Champ.statut, statut), fin + timedelta(hours=1)
    )
    convertis = convertir_etat_jira([*injection, apres], fin)
    creations = [e for e in convertis if e.nature is NatureEvenement.creation]
    alignes = [e for e in convertis if e.nature is NatureEvenement.alignement]
    assert creations == [e for e in injection if e.nature is NatureEvenement.creation]
    assert convertis == [*creations, *alignes]
    attributs = [e for e in injection if e.nature is NatureEvenement.modification_champ]
    assert {(e.cle_ticket, e.champ, e.vers) for e in alignes} == {
        (e.cle_ticket, e.champ, e.vers) for e in attributs
    }
    assert all(e.horodatage == fin and e.de is None for e in alignes)
    # La transition postérieure à l'instant de conversion n'y entre pas.
    statut_converti = next(
        e.vers for e in alignes if e.cle_ticket == cle and e.champ is Champ.statut
    )
    assert statut_converti == statut


def test_conversion_sans_fuseau_refusee(journal: SourceJournal) -> None:
    with pytest.raises(UsineErreur, match="sans fuseau"):
        convertir_etat_jira(injection_simulee(journal), datetime(2026, 10, 9, 18, 20))  # noqa: DTZ001
