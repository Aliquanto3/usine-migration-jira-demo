"""Plan d'injection : repli à la Date d'injection, ordre des clés, H-17, ADF (Story 1.6)."""

from datetime import UTC, date, datetime
from itertools import product

import pytest

from usine.adaptateurs.jira_cloud.conversion import texte_adf
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import EnteteJournal, Evenement, NatureEvenement, SourceEvenement
from usine.contrats.tickets import Champ, StatutAnomalie, TypeTicket, rang_cle
from usine.generateur.injecteur.plan import (
    CHAMPS_SELECTION,
    TRANSITIONS_H17,
    PlanInjection,
    champs_creation,
    chemin_statuts,
    document_adf,
    noms_jira,
    planifier,
)
from usine.generateur.journal import Generation

ENTETE = EnteteJournal(
    graine=1,
    date_generation=date(2026, 10, 12),
    date_injection=date(2026, 10, 9),
    ancrage_semaines=date(2026, 8, 17),
    version_corpus="essai",
    modele_corpus="essai",
)


def _ev(
    rang: int,
    cle: str,
    quand: datetime,
    nature: NatureEvenement,
    champ: Champ | None = None,
    vers: str | None = None,
    de: str | None = None,
    type_ticket: TypeTicket = TypeTicket.anomalie,
) -> Evenement:
    return Evenement(
        id_evenement=f"J-{rang}",
        cle_ticket=cle,
        type_ticket=type_ticket,
        horodatage=quand,
        nature=nature,
        champ=champ,
        de=de,
        vers=vers,
        source=SourceEvenement.journal,
    )


def _creation(rang: int, cle: str, quand: datetime, **valeurs: str) -> list[Evenement]:
    evenements = [_ev(rang, cle, quand, NatureEvenement.creation)]
    for i, (champ, valeur) in enumerate(valeurs.items(), start=1):
        evenements.append(
            _ev(
                rang * 100 + i, cle, quand, NatureEvenement.modification_champ, Champ(champ), valeur
            )
        )
    return evenements


LUNDI = datetime(2026, 10, 5, 9, tzinfo=UTC)
VENDREDI_SOIR = datetime(2026, 10, 9, 21, 30, tzinfo=UTC)
"""Vendredi 9 octobre 21 h 30 UTC = 23 h 30 à Paris : encore la Date d'injection."""
SAMEDI = datetime(2026, 10, 9, 22, 30, tzinfo=UTC)
"""Vendredi 22 h 30 UTC = samedi 0 h 30 à Paris : après la Date d'injection."""


def test_repli_jusqu_a_la_date_d_injection_en_jour_local() -> None:
    evenements = [
        *_creation(1, "DEMO-10", LUNDI, statut="nouvelle", titre="Dix", gravite="mineure"),
        *_creation(2, "DEMO-2", LUNDI, statut="nouvelle", titre="Deux", description="a\nb"),
        _ev(3, "DEMO-10", VENDREDI_SOIR, NatureEvenement.transition, Champ.statut,
            "en_analyse", "nouvelle"),
        _ev(4, "DEMO-10", VENDREDI_SOIR, NatureEvenement.modification_champ, Champ.gravite,
            "majeure", "mineure"),
        _ev(5, "DEMO-2", VENDREDI_SOIR, NatureEvenement.modification_champ, Champ.description,
            None, "a\nb"),
        _ev(6, "DEMO-10", SAMEDI, NatureEvenement.transition, Champ.statut, "rejetee",
            "en_analyse"),
        _ev(7, "DEMO-2", SAMEDI, NatureEvenement.modification_champ, Champ.entite, "ENT-Z"),
    ]  # fmt: skip
    plan = planifier(ENTETE, evenements)
    assert [t.cle for t in plan.tickets] == ["DEMO-2", "DEMO-10"]
    deux, dix = plan.tickets
    assert dict(dix.valeurs) == {
        Champ.statut: "en_analyse",
        Champ.titre: "Dix",
        Champ.gravite: "majeure",
    }
    assert dix.statut_final is StatutAnomalie.en_analyse
    assert dict(deux.valeurs) == {Champ.statut: "nouvelle", Champ.titre: "Deux"}
    # Les options des listes libres couvrent tout le Journal, après la Date d'injection compris.
    assert plan.valeurs_libres[Champ.entite] == ("ENT-Z",)


def test_ticket_cree_apres_la_date_d_injection_refuse() -> None:
    evenements = [
        *_creation(1, "DEMO-1", LUNDI, titre="Un"),
        *_creation(2, "DEMO-2", SAMEDI, titre="Deux"),
    ]
    with pytest.raises(UsineErreur, match="DEMO-2"):
        planifier(ENTETE, evenements)


def test_ticket_sans_titre_refuse() -> None:
    with pytest.raises(UsineErreur, match="DEMO-1 sans titre"):
        planifier(ENTETE, _creation(1, "DEMO-1", LUNDI, statut="nouvelle"))


def test_plan_du_journal_reduit(generation: Generation, plan: PlanInjection) -> None:
    cles = {e.cle_ticket for e in generation.evenements}
    assert [t.cle for t in plan.tickets] == sorted(cles, key=rang_cle)
    assert planifier(generation.entete, generation.evenements) == plan
    assert {t.type_ticket for t in plan.tickets} == set(TypeTicket)
    for ticket in plan.tickets:
        attendu: dict[Champ, str] = {}
        for evenement in generation.evenements:
            if evenement.cle_ticket == ticket.cle and evenement.champ is not None:
                if evenement.vers is None:
                    attendu.pop(evenement.champ, None)
                else:
                    attendu[evenement.champ] = evenement.vers
        assert dict(ticket.valeurs) == attendu


def test_transitions_h17_couvrent_le_generateur(generation: Generation) -> None:
    transitions = {
        (StatutAnomalie(e.de or ""), StatutAnomalie(e.vers or ""))
        for e in generation.evenements
        if e.nature is NatureEvenement.transition
    }
    assert transitions <= set(TRANSITIONS_H17)


def test_chemin_statuts_plus_court_et_valide() -> None:
    nouvelle = StatutAnomalie.nouvelle
    assert chemin_statuts(nouvelle, nouvelle) == ()
    assert chemin_statuts(nouvelle, StatutAnomalie.fermee) == (
        StatutAnomalie.en_analyse,
        StatutAnomalie.en_correction,
        StatutAnomalie.a_retester,
        StatutAnomalie.fermee,
    )
    assert chemin_statuts(nouvelle, StatutAnomalie.rejetee) == (
        StatutAnomalie.en_analyse,
        StatutAnomalie.rejetee,
    )
    for depart, arrivee in product(StatutAnomalie, StatutAnomalie):
        if arrivee is nouvelle and depart is not nouvelle:
            with pytest.raises(UsineErreur, match="nouvelle inaccessible"):
                chemin_statuts(depart, arrivee)
            continue
        chemin = chemin_statuts(depart, arrivee)
        etapes = list(zip((depart, *chemin), chemin, strict=False))
        assert all(etape in TRANSITIONS_H17 for etape in etapes)
        assert (chemin[-1] if chemin else depart) is arrivee


@pytest.mark.parametrize("texte", ["une ligne", "a\n\nb", "", "fin\n", "été ; l’année"])
def test_document_adf_relu_par_la_conversion_l2(texte: str) -> None:
    document = document_adf(texte)
    assert document["type"] == "doc" and document["version"] == 1
    assert all(
        ("content" in p) == bool(p.get("content")) for p in document["content"]
    )  # paragraphe vide : sans nœud texte
    assert texte_adf(document, "essai") == texte


def test_document_adf_paragraphe_vide_sans_noeud_texte() -> None:
    assert document_adf("a\n\nb")["content"][1] == {"type": "paragraph"}


def test_champs_creation(plan: PlanInjection, config: ConfigJira) -> None:
    identifiants = {champ: f"customfield_{i}" for i, champ in enumerate(CHAMPS_SELECTION)}
    noms = noms_jira(config)
    anomalie = next(t for t in plan.tickets if t.type_ticket is TypeTicket.anomalie)
    champs = champs_creation(
        anomalie, cle_projet="DEMO", id_type="10010", identifiants=identifiants, noms=noms
    )
    assert champs["project"] == {"key": "DEMO"}
    assert champs["issuetype"] == {"id": "10010"}
    assert champs["summary"] == anomalie.valeurs[Champ.titre]
    assert texte_adf(champs["description"], "essai") == anomalie.valeurs[Champ.description]
    assert "status" not in champs
    gravite = anomalie.valeurs[Champ.gravite]
    assert champs[identifiants[Champ.gravite]] == {"value": noms[Champ.gravite][gravite]}
    assert champs[identifiants[Champ.entite]] == {"value": anomalie.valeurs[Champ.entite]}
    assert identifiants[Champ.statut_test] not in champs
    certification = next(t for t in plan.tickets if t.type_ticket is TypeTicket.certification)
    champs = champs_creation(
        certification, cle_projet="DEMO", id_type="10012", identifiants=identifiants, noms=noms
    )
    assert set(champs) == {
        "project",
        "issuetype",
        "summary",
        "description",
        identifiants[Champ.entite],
        identifiants[Champ.vague],
        identifiants[Champ.statut_certification],
    }


def test_noms_jira_inverse_la_configuration(config: ConfigJira) -> None:
    noms = noms_jira(config)
    assert noms[Champ.statut][StatutAnomalie.a_retester] == "À retester"
    assert noms[Champ.statut_test]["non_execute"] == "Non exécuté"
    incomplete = config.model_copy(
        update={"valeurs": {**config.valeurs, Champ.phase: {"Recette": "recette"}}}
    )
    with pytest.raises(UsineErreur, match=r"valeurs\.phase.*migration_a_blanc"):
        noms_jira(incomplete)
