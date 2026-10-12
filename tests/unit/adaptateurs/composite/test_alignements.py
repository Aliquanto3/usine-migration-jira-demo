"""Alignements « Jira fait foi » : rejeu, identifiant, détection (Story 2.6, H-27)."""

import hashlib
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.unit.adaptateurs.composite.outils import (
    autre_valeur,
    etat_a_l_injection,
    generation_reduite,
    injection_simulee,
    journal_aux_cles_jira,
    premiere_anomalie,
    transition_jira,
)
from usine.adaptateurs.composite import (
    CHAMPS_ETAT,
    DetecteurAlignements,
    EtatTicket,
    alignements,
    etats_tickets,
    id_alignement,
)
from usine.adaptateurs.journal import SourceJournal
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, NatureEvenement, SourceEvenement
from usine.contrats.tickets import Champ, TypeTicket
from usine.domaine.instantanes import CHAMPS_ETAT as CHAMPS_ETAT_DOMAINE
from usine.generateur.journal import Generation

INSTANT = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)


@pytest.fixture(scope="module")
def generation() -> Generation:
    return generation_reduite()


@pytest.fixture
def journal(tmp_path: Path, generation: Generation) -> SourceJournal:
    return journal_aux_cles_jira(tmp_path, generation)


def _fin(journal: SourceJournal) -> datetime:
    assert journal.manifeste is not None
    return journal.manifeste.horodatage_fin_injection


def _modification(
    rang: int, cle: str, champ: Champ, vers: str | None, instant: datetime, de: str | None = None
) -> Evenement:
    return Evenement(
        id_evenement=f"30000-{rang}",
        cle_ticket=cle,
        type_ticket=TypeTicket.anomalie,
        horodatage=instant,
        nature=NatureEvenement.modification_champ,
        champ=champ,
        de=de,
        vers=vers,
        source=SourceEvenement.jira_cloud,
    )


def test_champs_d_etat_sans_textes() -> None:
    assert set(CHAMPS_ETAT) == set(Champ) - {Champ.titre, Champ.description}


def test_champs_d_etat_identiques_a_ceux_du_domaine() -> None:
    """Parité avec les Instantanés : l'adaptateur ne peut pas importer `domaine`."""
    assert set(CHAMPS_ETAT) == set(CHAMPS_ETAT_DOMAINE)


def test_identifiant_d_alignement() -> None:
    attendu = hashlib.sha256(b"mineure").hexdigest()[:8]
    assert id_alignement("DEMO-7", Champ.gravite, "mineure") == f"A-DEMO-7-gravite-{attendu}"
    assert re.fullmatch(r"A-DEMO-7-statut-[0-9a-f]{8}", id_alignement("DEMO-7", Champ.statut, "x"))


def test_rejeu_derniere_valeur_et_premiere_occurrence() -> None:
    t0 = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    gravite = _modification(1, "DEMO-1", Champ.gravite, "majeure", t0 + timedelta(hours=2))
    evenements = [
        _modification(2, "DEMO-1", Champ.gravite, "mineure", t0 + timedelta(hours=3)),
        gravite,
        gravite.model_copy(update={"vers": "bloquante"}),  # même id : ignoré
        _modification(3, "DEMO-1", Champ.titre, "Titre", t0),
    ]
    etats = etats_tickets(evenements)
    assert etats == {
        "DEMO-1": EtatTicket(
            TypeTicket.anomalie,
            SourceEvenement.jira_cloud,
            cree=False,
            valeurs={Champ.gravite: "mineure"},
        )
    }


def test_valeur_jira_vide_sans_alignement() -> None:
    rejoues = {
        "DEMO-1": EtatTicket(
            TypeTicket.anomalie, SourceEvenement.journal, True, {Champ.domaine: "Finance"}
        )
    }
    jira = {
        "DEMO-1": EtatTicket(
            TypeTicket.anomalie, SourceEvenement.jira_dc, True, {Champ.domaine: None}
        )
    }
    assert alignements(rejoues, jira, INSTANT) == []


def test_alignement_sans_fuseau_refuse() -> None:
    with pytest.raises(UsineErreur, match="sans fuseau"):
        alignements({}, {}, datetime(2026, 10, 12, 7, 30))  # noqa: DTZ001


def test_injection_fidele_aucun_alignement(journal: SourceJournal) -> None:
    detecter = DetecteurAlignements(journal)
    assert detecter(injection_simulee(journal), INSTANT) == []


def test_injection_infidele_un_alignement_gravite(journal: SourceJournal) -> None:
    cle = premiere_anomalie(journal)
    rejouee = etat_a_l_injection(journal, cle, Champ.gravite)
    jira_gravite = autre_valeur(Champ.gravite, rejouee)
    jira = injection_simulee(journal, {cle: {Champ.gravite: jira_gravite}})

    detectes = DetecteurAlignements(journal)(jira, INSTANT)

    assert detectes == [
        Evenement(
            id_evenement=id_alignement(cle, Champ.gravite, jira_gravite),
            cle_ticket=cle,
            type_ticket=TypeTicket.anomalie,
            horodatage=INSTANT,
            nature=NatureEvenement.alignement,
            champ=Champ.gravite,
            de=rejouee,
            vers=jira_gravite,
            source=SourceEvenement.jira_cloud,
        )
    ]


def test_source_de_l_alignement_celle_de_jira(journal: SourceJournal) -> None:
    cle = premiere_anomalie(journal)
    autre = autre_valeur(Champ.gravite, etat_a_l_injection(journal, cle, Champ.gravite))
    jira = injection_simulee(journal, {cle: {Champ.gravite: autre}}, SourceEvenement.jira_dc)
    (detecte,) = DetecteurAlignements(journal)(jira, INSTANT)
    assert detecte.source is SourceEvenement.jira_dc


def test_alignement_deja_rejoue_pas_redetecte(journal: SourceJournal) -> None:
    cle = premiere_anomalie(journal)
    autre = autre_valeur(Champ.gravite, etat_a_l_injection(journal, cle, Champ.gravite))
    jira = injection_simulee(journal, {cle: {Champ.gravite: autre}})
    detecter = DetecteurAlignements(journal)
    premiers = detecter(jira, INSTANT)
    assert len(premiers) == 1
    assert detecter([*jira, *premiers], INSTANT + timedelta(days=1)) == []


def test_transition_manuelle_apres_l_injection_sans_alignement(journal: SourceJournal) -> None:
    cle = premiere_anomalie(journal)
    statut = etat_a_l_injection(journal, cle, Champ.statut)
    vers = autre_valeur(Champ.statut, statut)
    transition = transition_jira(cle, statut, vers, _fin(journal) + timedelta(hours=1))
    assert DetecteurAlignements(journal)([*injection_simulee(journal), transition], INSTANT) == []


def test_texte_different_sans_alignement(journal: SourceJournal) -> None:
    cle = premiere_anomalie(journal)
    titre = _modification(1, cle, Champ.titre, "Titre retouché dans Jira", _fin(journal))
    description = _modification(
        2, cle, Champ.description, "Autre texte", _fin(journal) + timedelta(hours=1)
    )
    jira = [*injection_simulee(journal), titre, description]
    assert DetecteurAlignements(journal)(jira, INSTANT) == []


def test_ecart_sur_un_champ_hors_injection_aligne(journal: SourceJournal) -> None:
    """Modification Jira pendant l'injection (ignorée par la coupure) : Jira fait foi."""
    cle = premiere_anomalie(journal)
    phase = etat_a_l_injection(journal, cle, Champ.phase)
    assert phase is not None
    vers = "tnr" if phase != "tnr" else "recette"
    modification = _modification(1, cle, Champ.phase, vers, _fin(journal), de=phase)
    detectes = DetecteurAlignements(journal)([*injection_simulee(journal), modification], INSTANT)
    assert [(e.cle_ticket, e.champ, e.de, e.vers) for e in detectes] == [
        (cle, Champ.phase, phase, vers)
    ]


@pytest.mark.parametrize("decalage", [timedelta(0), timedelta(hours=-1)])
def test_detection_trop_tot_refusee(journal: SourceJournal, decalage: timedelta) -> None:
    instant = _fin(journal) + decalage
    with pytest.raises(UsineErreur) as erreur:
        DetecteurAlignements(journal)(injection_simulee(journal), instant)
    message = str(erreur.value)
    assert instant.isoformat() in message
    assert _fin(journal).isoformat() in message


def test_detection_sans_fuseau_refusee(journal: SourceJournal) -> None:
    with pytest.raises(UsineErreur, match="sans fuseau"):
        DetecteurAlignements(journal)([], datetime(2026, 10, 12, 7, 30))  # noqa: DTZ001


def test_detecteur_sans_manifeste_refuse(journal: SourceJournal) -> None:
    with pytest.raises(UsineErreur, match="manifeste d'injection"):
        DetecteurAlignements(SourceJournal(journal.chemin))
