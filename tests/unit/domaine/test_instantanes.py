"""État des tickets et Instantané (Story 0.4, FR-10, AD-17)."""

from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from tests.unit.domaine.constructeur import Flux
from usine.config import charger_yaml
from usine.contrats.calcul import SCHEMA_INSTANTANE
from usine.contrats.calendrier import jours_ouvres
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import NatureEvenement
from usine.contrats.schemas import valider
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, SCHEMA_TICKET_TEXTE, Champ, TypeTicket
from usine.domaine.instantanes import instantane, tickets_etats, tickets_textes
from usine.generateur.journal import Generation, generer

RACINE = Path(__file__).resolve().parents[3]

VENDREDI = date(2026, 10, 2)
LUNDI = date(2026, 10, 5)
MARDI = date(2026, 10, 6)


def _ts(jour: int, heure: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, jour, heure, minute, tzinfo=UTC)


def _ligne(etats: pl.DataFrame, d: date, cle: str) -> dict[str, object]:
    lignes = etats.filter((pl.col("date") == d) & (pl.col("cle_ticket") == cle)).to_dicts()
    assert len(lignes) == 1, f"{cle} en {d} : {len(lignes)} ligne(s)"
    return lignes[0]


def test_schema_et_ticket_cree_au_plus_tard_en_d() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.anomalie("DEMO-2", _ts(6, 9))  # mardi : après le lundi D
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI, MARDI])
    valider(etats, SCHEMA_TICKET_ETAT)
    assert etats.filter(pl.col("date") == LUNDI)["cle_ticket"].to_list() == ["DEMO-1"]
    assert etats.filter(pl.col("date") == MARDI)["cle_ticket"].to_list() == ["DEMO-1", "DEMO-2"]


def test_coupure_week_end_rattachee_au_lundi() -> None:
    flux = Flux()
    # Samedi 23 h UTC = dimanche 1 h à Paris : Jour ouvré = lundi.
    flux.anomalie("DEMO-1", _ts(3, 23))
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI])
    assert etats.filter(pl.col("date") == VENDREDI).is_empty()
    assert _ligne(etats, LUNDI, "DEMO-1")["date_derniere_entree"] == LUNDI


def test_vendredi_soir_utc_rattache_au_lundi() -> None:
    flux = Flux()
    # Vendredi 22 h 30 UTC = samedi 0 h 30 à Paris.
    flux.anomalie("DEMO-1", _ts(2, 22, 30))
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI])
    assert etats.filter(pl.col("date") == VENDREDI).is_empty()
    assert etats.filter(pl.col("date") == LUNDI).height == 1


def test_derniere_valeur_et_fermeture() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.transition("DEMO-1", _ts(2, 9), "nouvelle", "en_correction")
    flux.transition("DEMO-1", _ts(5, 9), "en_correction", "fermee")
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI])
    assert _ligne(etats, VENDREDI, "DEMO-1")["statut"] == "en_correction"
    assert _ligne(etats, LUNDI, "DEMO-1")["statut"] == "fermee"
    assert _ligne(etats, LUNDI, "DEMO-1")["date_derniere_entree"] == date(2026, 10, 1)


def test_reouverture_fixe_la_derniere_entree() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.transition("DEMO-1", _ts(1, 10), "nouvelle", "en_correction")
    flux.transition("DEMO-1", _ts(1, 11), "en_correction", "a_retester")
    flux.transition("DEMO-1", _ts(2, 9), "a_retester", "fermee")
    flux.transition("DEMO-1", _ts(5, 9), "fermee", "en_analyse")
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI])
    assert _ligne(etats, VENDREDI, "DEMO-1")["date_derniere_entree"] == date(2026, 10, 1)
    lundi = _ligne(etats, LUNDI, "DEMO-1")
    assert lundi["statut"] == "en_analyse"
    assert lundi["date_derniere_entree"] == LUNDI


def test_meme_horodatage_ordre_du_flux() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9), gravite="mineure")
    flux.modifier("DEMO-1", TypeTicket.anomalie, _ts(1, 9), Champ.gravite, "mineure", "majeure")
    etats = tickets_etats(flux.evenements, [VENDREDI])
    assert _ligne(etats, VENDREDI, "DEMO-1")["gravite"] == "majeure"


def test_ordre_d_arrivee_indifferent_hors_egalite() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.transition("DEMO-1", _ts(2, 9), "nouvelle", "en_analyse")
    melange = list(reversed(flux.evenements[-1:])) + flux.evenements[:-1]
    assert tickets_etats(melange, [VENDREDI]).equals(tickets_etats(flux.evenements, [VENDREDI]))


def test_colonnes_sans_objet_nulles() -> None:
    flux = Flux()
    flux.creer(
        "DEMO-1",
        TypeTicket.cas_de_test,
        _ts(1, 9),
        {
            Champ.statut_test: "non_execute",
            Champ.entite: "ENT-A",
            Champ.vague: "V1",
            Champ.domaine: "paie",
            Champ.phase: "tnr",
        },
    )
    flux.creer(
        "DEMO-2",
        TypeTicket.certification,
        _ts(1, 9),
        {Champ.statut_certification: "accordee", Champ.entite: "ENT-A", Champ.vague: "V1"},
    )
    flux.modifier(
        "DEMO-1", TypeTicket.cas_de_test, _ts(2, 9), Champ.statut_test, "non_execute", "ko"
    )
    etats = tickets_etats(flux.evenements, [VENDREDI])
    test = _ligne(etats, VENDREDI, "DEMO-1")
    assert test["statut_test"] == "ko"
    assert test["statut"] is None and test["gravite"] is None
    assert test["statut_certification"] is None and test["date_derniere_entree"] is None
    certification = _ligne(etats, VENDREDI, "DEMO-2")
    assert certification["statut_certification"] == "accordee"
    assert certification["domaine"] is None and certification["phase"] is None


def test_sans_evenement_ni_date() -> None:
    assert tickets_etats([], [LUNDI]).is_empty()
    assert tickets_etats([], []).schema == pl.Schema(dict(SCHEMA_TICKET_ETAT.colonnes))
    assert instantane(tickets_etats([], [LUNDI])).is_empty()


def test_instantane_compte_par_attributs() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.anomalie("DEMO-2", _ts(1, 10))
    flux.anomalie("DEMO-3", _ts(1, 11), entite="ENT-B", gravite="majeure")
    flux.transition("DEMO-2", _ts(2, 9), "nouvelle", "rejetee")
    table = instantane(tickets_etats(flux.evenements, [VENDREDI]))
    valider(table, SCHEMA_INSTANTANE)
    comptes = {
        (ligne["entite"], ligne["gravite"], ligne["statut"]): ligne["nombre"]
        for ligne in table.to_dicts()
    }
    assert comptes == {
        ("ENT-A", "bloquante", "nouvelle"): 1,
        ("ENT-A", "bloquante", "rejetee"): 1,
        ("ENT-B", "majeure", "nouvelle"): 1,
    }


@pytest.fixture(scope="module")
def generation() -> Generation:
    config = charger_yaml(RACINE / "tests/unit/generateur/programme_reduit.yaml", ConfigProgramme)
    return generer(config, 42, date(2026, 10, 12))


def test_journal_genere_instantane_complet(generation: Generation) -> None:
    entete = generation.entete
    jours = jours_ouvres(entete.ancrage_semaines, entete.date_injection)
    etats = tickets_etats(generation.evenements, jours)
    tickets = {e.cle_ticket for e in generation.evenements if e.nature is NatureEvenement.creation}
    finaux = etats.filter(pl.col("date") == entete.date_injection)
    assert set(finaux["cle_ticket"]) == tickets
    table = instantane(etats)
    par_date = table.group_by("date").agg(pl.col("nombre").sum()).sort("date")
    attendu = etats.group_by("date").len().sort("date")
    assert par_date["nombre"].to_list() == attendu["len"].cast(pl.Int64).to_list()
    assert table.filter(pl.col("statut").is_null()).is_empty()


def test_dates_en_double_refusees() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    with pytest.raises(UsineErreur, match="2026-10-02"):
        tickets_etats(flux.evenements, [VENDREDI, LUNDI, VENDREDI])


def test_tickets_textes_dernieres_valeurs_en_d() -> None:
    flux = Flux()
    flux.creer(
        "DEMO-1",
        TypeTicket.anomalie,
        _ts(1, 9),
        {Champ.entite: "ENT-A", Champ.titre: "Titre initial", Champ.description: "Desc"},
    )
    flux.modifier("DEMO-1", TypeTicket.anomalie, _ts(5, 10), Champ.titre, "Titre initial", "Lundi")
    flux.modifier("DEMO-1", TypeTicket.anomalie, _ts(6, 10), Champ.titre, "Lundi", "Mardi")
    flux.anomalie("DEMO-2", _ts(5, 11), entite="ENT-B")  # ni titre ni description
    flux.anomalie("DEMO-3", _ts(6, 9))  # créé après le lundi D
    textes = tickets_textes(flux.evenements, LUNDI)
    valider(textes, SCHEMA_TICKET_TEXTE)
    assert textes.to_dicts() == [
        {
            "cle_ticket": "DEMO-1",
            "type_ticket": "anomalie",
            "entite": "ENT-A",
            "titre": "Lundi",
            "description": "Desc",
        },
        {
            "cle_ticket": "DEMO-2",
            "type_ticket": "anomalie",
            "entite": "ENT-B",
            "titre": None,
            "description": None,
        },
    ]


def test_tickets_textes_vide() -> None:
    textes = tickets_textes([], LUNDI)
    assert textes.is_empty()
    assert textes.schema == dict(SCHEMA_TICKET_TEXTE.colonnes)
