"""`SourceComposite` : coupure à la fin d'injection, ordre, `depuis` (Story 2.6, AD-4)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.unit.adaptateurs.composite.outils import (
    generation_reduite,
    injection_simulee,
    journal_aux_cles_jira,
    transition_jira,
)
from tests.unit.adaptateurs.journal.outils import manifeste_pour
from usine.adaptateurs.composite import SourceComposite
from usine.adaptateurs.journal import SourceJournal
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, NatureEvenement, SourceEvenement
from usine.contrats.tickets import Champ, TypeTicket
from usine.generateur.journal import Generation
from usine.ports import SourceTickets


@pytest.fixture(scope="module")
def generation() -> Generation:
    return generation_reduite()


@pytest.fixture
def journal(tmp_path: Path, generation: Generation) -> SourceJournal:
    return journal_aux_cles_jira(tmp_path, generation)


def _creation(cle: str, instant: datetime, id_ticket: int) -> list[Evenement]:
    """Ticket créé à la main dans Jira : création et un attribut initial."""
    communs = {
        "cle_ticket": cle,
        "type_ticket": TypeTicket.anomalie,
        "source": SourceEvenement.jira_cloud,
        "horodatage": instant,
    }
    return [
        Evenement(id_evenement=f"C-{id_ticket}", nature=NatureEvenement.creation, **communs),
        Evenement(
            id_evenement=f"C-{id_ticket}-statut",
            nature=NatureEvenement.modification_champ,
            champ=Champ.statut,
            vers="nouvelle",
            **communs,
        ),
    ]


def test_implemente_le_port(journal: SourceJournal) -> None:
    source = SourceComposite(journal, list)
    assert isinstance(source, SourceTickets)
    assert source.journal is journal
    assert source.manifeste is journal.manifeste
    assert journal.manifeste is not None
    assert source.horodatage_fin_injection == journal.manifeste.horodatage_fin_injection


def test_coupure_strictement_apres_la_fin_d_injection(journal: SourceJournal) -> None:
    manifeste = journal.manifeste
    assert manifeste is not None
    debut, fin = manifeste.debut_injection, manifeste.horodatage_fin_injection
    injection = injection_simulee(journal)
    cle = injection[0].cle_ticket
    avant_debut = transition_jira(cle, None, "en_analyse", debut - timedelta(hours=1), "1")
    a_la_fin = transition_jira(cle, None, "en_correction", fin, "2")
    apres = transition_jira(cle, None, "fermee", fin + timedelta(seconds=1), "3")
    creation = _creation("DEMO-999999", fin + timedelta(hours=2), 99)
    jira = [*creation, apres, a_la_fin, *injection, avant_debut]
    assert all(debut <= e.horodatage <= fin for e in injection)

    rendus = list(SourceComposite(journal, lambda: jira).evenements())

    attendus = [*journal.evenements(), apres, *creation]
    assert rendus == attendus


def test_journal_avant_jira_a_horodatage_egal(tmp_path: Path, generation: Generation) -> None:
    # Fin d'injection avancée à 09:00 : des événements du Journal la suivent (fin à 10:02).
    manifeste = manifeste_pour(generation.entete, generation.evenements)
    fin = datetime(2026, 10, 9, 9, 0, tzinfo=UTC)
    manifeste = manifeste.model_copy(
        update={"debut_injection": fin - timedelta(minutes=5), "horodatage_fin_injection": fin}
    )
    journal = journal_aux_cles_jira(tmp_path, generation, manifeste)
    dernier = list(journal.evenements())[-1]
    assert dernier.horodatage > fin
    jira = [transition_jira(dernier.cle_ticket, None, "en_analyse", dernier.horodatage)]
    rendus = list(SourceComposite(journal, lambda: jira).evenements())
    assert rendus[-2:] == [dernier, jira[0]]
    horodatages = [e.horodatage for e in rendus]
    assert horodatages == sorted(horodatages)


def test_depuis_garde_les_deux_origines(journal: SourceJournal) -> None:
    manifeste = journal.manifeste
    assert manifeste is not None
    fin = manifeste.horodatage_fin_injection
    cle = injection_simulee(journal)[0].cle_ticket
    tot = transition_jira(cle, None, "en_analyse", fin + timedelta(hours=1), "1")
    tard = transition_jira(cle, None, "fermee", fin + timedelta(hours=3), "2")
    source = SourceComposite(journal, lambda: [tard, tot])
    depuis = fin + timedelta(hours=2)
    assert list(source.evenements(depuis)) == [tard]
    milieu = list(journal.evenements())[100].horodatage
    attendus = [*journal.evenements(milieu), tot, tard]
    assert list(source.evenements(milieu)) == attendus


def test_depuis_sans_fuseau_refuse_avant_tout_parcours(journal: SourceJournal) -> None:
    appels: list[str] = []

    def jira() -> list[Evenement]:
        appels.append("jira")
        return []

    with pytest.raises(UsineErreur, match="sans fuseau"):
        SourceComposite(journal, jira).evenements(datetime(2026, 10, 9, 19, 0))  # noqa: DTZ001
    assert appels == []


def test_journal_sans_manifeste_refuse(tmp_path: Path, generation: Generation) -> None:
    sans = SourceJournal(journal_aux_cles_jira(tmp_path, generation).chemin)
    with pytest.raises(UsineErreur) as erreur:
        SourceComposite(sans, list)
    assert str(sans.chemin) in str(erreur.value)
    assert "manifeste d'injection" in str(erreur.value)


def test_identifiants_uniques_et_jira_relu_a_chaque_appel(journal: SourceJournal) -> None:
    manifeste = journal.manifeste
    assert manifeste is not None
    cle = injection_simulee(journal)[0].cle_ticket
    transition = transition_jira(
        cle, None, "fermee", manifeste.horodatage_fin_injection + timedelta(hours=1)
    )
    jira: list[Evenement] = []
    source = SourceComposite(journal, lambda: jira)
    assert list(source.evenements()) == list(journal.evenements())
    jira.extend([transition, transition])
    rendus = list(source.evenements())
    assert rendus[-1] == transition
    assert len({e.id_evenement for e in rendus}) == len(rendus)
