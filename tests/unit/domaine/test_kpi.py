"""Tests des KPI quotidiens (Story 3.2, FR-11)."""

from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from tests.unit.domaine.constructeur import Flux
from usine.config import charger_yaml
from usine.contrats.calcul import PERIMETRE_PROGRAMME, SCHEMA_KPI
from usine.contrats.calendrier import fenetre_glissante, jour_ouvre_precedent, jours_ouvres
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.schemas import valider
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, STATUTS_FERMES, Champ, TypeTicket
from usine.domaine.instantanes import instantane, tickets_etats
from usine.domaine.kpi import CODES_KPI, DIMENSIONS_KPI, kpi
from usine.generateur.journal import Generation, generer

RACINE = Path(__file__).resolve().parents[3]

LUNDI_28 = date(2026, 9, 28)
JEUDI = date(2026, 10, 1)
VENDREDI = date(2026, 10, 2)
LUNDI = date(2026, 10, 5)
MARDI = date(2026, 10, 6)
MERCREDI = date(2026, 10, 7)

_CODES_COMPTES = (
    "anomalies_ouvertes",
    "anomalies_ouvertes_gravite",
    "anomalies_ouvertes_phase",
    "entrees_jour",
    "sorties_jour",
    "entrees_fenetre",
    "sorties_fenetre",
    "certifications",
)


def _ts(d: date, heure: int = 9) -> datetime:
    return datetime(d.year, d.month, d.day, heure, tzinfo=UTC)


def _v(
    table: pl.DataFrame, d: date, perimetre: str, code: str, dimension: str = ""
) -> tuple[int, int]:
    lignes = table.filter(
        (pl.col("date") == d)
        & (pl.col("perimetre") == perimetre)
        & (pl.col("code_kpi") == code)
        & (pl.col("dimension") == dimension)
    ).rows()
    assert len(lignes) == 1, f"{d} {perimetre} {code} {dimension} : {len(lignes)} ligne(s)"
    return lignes[0][4], lignes[0][5]


def _cas(flux: Flux, cle: str, d: date, phase: str, statut: str, entite: str = "ENT-A") -> None:
    flux.creer(
        cle,
        TypeTicket.cas_de_test,
        _ts(d),
        {
            Champ.statut_test: statut,
            Champ.entite: entite,
            Champ.vague: "V1",
            Champ.domaine: "paie",
            Champ.phase: phase,
        },
    )


def _certification(flux: Flux, cle: str, d: date, statut: str, entite: str = "ENT-A") -> None:
    flux.creer(
        cle,
        TypeTicket.certification,
        _ts(d),
        {Champ.statut_certification: statut, Champ.entite: entite, Champ.vague: "V1"},
    )


def test_stock() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(VENDREDI))
    flux.anomalie("DEMO-2", _ts(VENDREDI))
    flux.anomalie("DEMO-3", _ts(VENDREDI), entite="ENT-B", gravite="majeure")
    flux.transition("DEMO-3", _ts(VENDREDI, 10), "nouvelle", "fermee")
    table = kpi(tickets_etats(flux.evenements, [VENDREDI]), ["ENT-A", "ENT-B"])
    assert _v(table, VENDREDI, "ENT-A", "anomalies_ouvertes") == (2, 1)
    assert _v(table, VENDREDI, "ENT-B", "anomalies_ouvertes") == (0, 1)
    assert _v(table, VENDREDI, PERIMETRE_PROGRAMME, "anomalies_ouvertes") == (2, 1)
    assert _v(table, VENDREDI, "ENT-A", "anomalies_ouvertes_gravite", "bloquante") == (2, 1)
    assert _v(table, VENDREDI, "ENT-A", "anomalies_ouvertes_gravite", "majeure") == (0, 1)
    assert _v(table, VENDREDI, "ENT-B", "anomalies_ouvertes_gravite", "majeure") == (0, 1)
    assert _v(table, VENDREDI, "ENT-A", "anomalies_ouvertes_phase", "recette") == (2, 1)
    assert _v(table, VENDREDI, "ENT-A", "anomalies_ouvertes_phase", "tnr") == (0, 1)


def test_flux_du_jour() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(LUNDI))
    flux.transition("DEMO-1", _ts(MARDI), "nouvelle", "fermee")
    flux.transition("DEMO-1", _ts(MERCREDI, 9), "fermee", "en_analyse")
    flux.transition("DEMO-1", _ts(MERCREDI, 10), "en_analyse", "rejetee")
    table = kpi(tickets_etats(flux.evenements, [LUNDI, MARDI, MERCREDI]), ["ENT-A"])
    for perimetre in ("ENT-A", PERIMETRE_PROGRAMME):
        entrees = [_v(table, d, perimetre, "entrees_jour")[0] for d in (LUNDI, MARDI, MERCREDI)]
        sorties = [_v(table, d, perimetre, "sorties_jour")[0] for d in (LUNDI, MARDI, MERCREDI)]
        assert entrees == [1, 0, 1]
        assert sorties == [0, 1, 1]


def test_creee_et_fermee_le_meme_jour() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(LUNDI, 9))
    flux.transition("DEMO-1", _ts(LUNDI, 10), "nouvelle", "fermee")
    table = kpi(tickets_etats(flux.evenements, [LUNDI]), ["ENT-A"])
    assert _v(table, LUNDI, "ENT-A", "entrees_jour") == (1, 1)
    assert _v(table, LUNDI, "ENT-A", "sorties_jour") == (1, 1)
    assert _v(table, LUNDI, "ENT-A", "anomalies_ouvertes") == (0, 1)


def test_fenetre_glissante() -> None:
    jours = jours_ouvres(LUNDI_28, MARDI)
    assert len(jours) == 7
    flux = Flux()
    for i, d in enumerate(jours):
        for n in range(i + 1):
            flux.anomalie(f"DEMO-{10 * i + n}", _ts(d))
        if i >= 1:
            flux.transition(f"DEMO-{10 * (i - 1)}", _ts(d), "nouvelle", "fermee")
    table = kpi(tickets_etats(flux.evenements, jours), ["ENT-A"])
    for d in jours:
        for code_jour, code_fenetre in (
            ("entrees_jour", "entrees_fenetre"),
            ("sorties_jour", "sorties_fenetre"),
        ):
            attendu = sum(
                _v(table, j, "ENT-A", code_jour)[0] for j in fenetre_glissante(d) if j in jours
            )
            assert _v(table, d, "ENT-A", code_fenetre) == (attendu, 1)
    # Jours antérieurs à la table : 0. Lundi 28 : 1 ; jeudi 1er : 1 + 2 + 3 + 4.
    assert _v(table, LUNDI_28, "ENT-A", "entrees_fenetre") == (1, 1)
    assert _v(table, JEUDI, "ENT-A", "entrees_fenetre") == (10, 1)
    # Mardi 6 : du mercredi 30 au mardi 6, 3 + 4 + 5 + 6 + 7.
    assert _v(table, MARDI, "ENT-A", "entrees_fenetre") == (25, 1)
    assert _v(table, MARDI, "ENT-A", "sorties_fenetre") == (5, 1)


def test_age_median_et_maximum() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(JEUDI))
    flux.anomalie("DEMO-2", _ts(VENDREDI))
    table = kpi(tickets_etats(flux.evenements, jours_ouvres(JEUDI, MERCREDI)), ["ENT-A"])
    assert _v(table, MERCREDI, "ENT-A", "age_median_anomalies_ouvertes") == (7, 2)
    assert _v(table, MERCREDI, "ENT-A", "age_max_anomalies_ouvertes") == (4, 1)
    assert _v(table, JEUDI, "ENT-A", "age_median_anomalies_ouvertes") == (0, 1)
    assert _v(table, JEUDI, "ENT-A", "age_max_anomalies_ouvertes") == (0, 1)


def test_age_part_de_la_reouverture() -> None:
    jours = jours_ouvres(LUNDI_28, MARDI)  # J0 … J6
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(jours[0]))
    flux.transition("DEMO-1", _ts(jours[2]), "nouvelle", "fermee")
    flux.transition("DEMO-1", _ts(jours[5]), "fermee", "en_analyse")
    table = kpi(tickets_etats(flux.evenements, jours), ["ENT-A"])
    assert _v(table, jours[6], "ENT-A", "age_median_anomalies_ouvertes") == (1, 1)
    assert _v(table, jours[6], "ENT-A", "age_max_anomalies_ouvertes") == (1, 1)
    assert _v(table, jours[5], "ENT-A", "entrees_jour") == (1, 1)


def test_aucune_ouverte_age_sans_valeur() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(LUNDI, 9))
    flux.transition("DEMO-1", _ts(LUNDI, 10), "nouvelle", "rejetee")
    table = kpi(tickets_etats(flux.evenements, [LUNDI]), ["ENT-A", "ENT-B"])
    for perimetre in ("ENT-A", "ENT-B", PERIMETRE_PROGRAMME):
        assert _v(table, LUNDI, perimetre, "age_median_anomalies_ouvertes") == (0, 0)
        assert _v(table, LUNDI, perimetre, "age_max_anomalies_ouvertes") == (0, 0)


def test_taux_par_phase() -> None:
    flux = Flux()
    for i, statut in enumerate(("ok", "ok", "ok", "ko", "non_execute", "non_execute")):
        _cas(flux, f"DEMO-{i + 1}", LUNDI, "recette", statut)
    table = kpi(tickets_etats(flux.evenements, [LUNDI]), ["ENT-A"])
    for perimetre in ("ENT-A", PERIMETRE_PROGRAMME):
        assert _v(table, LUNDI, perimetre, "taux_ko_cas_de_test", "recette") == (1, 4)
        assert _v(table, LUNDI, perimetre, "taux_non_execution_cas_de_test", "recette") == (2, 6)
        assert _v(table, LUNDI, perimetre, "taux_ko_cas_de_test", "tnr") == (0, 0)
        assert _v(table, LUNDI, perimetre, "taux_non_execution_cas_de_test", "tnr") == (0, 0)


def test_certifications_par_statut() -> None:
    flux = Flux()
    _certification(flux, "DEMO-1", LUNDI, "accordee")
    _certification(flux, "DEMO-2", LUNDI, "reservee")
    _certification(flux, "DEMO-3", LUNDI, "reservee")
    table = kpi(tickets_etats(flux.evenements, [LUNDI]), ["ENT-A"])
    assert _v(table, LUNDI, "ENT-A", "certifications", "accordee") == (1, 1)
    assert _v(table, LUNDI, "ENT-A", "certifications", "reservee") == (2, 1)
    assert _v(table, LUNDI, "ENT-A", "certifications", "refusee") == (0, 1)


def test_trou_de_dates_refuse() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(LUNDI))
    etats = tickets_etats(flux.evenements, [LUNDI, MERCREDI])
    with pytest.raises(UsineErreur, match="2026-10-06"):
        kpi(etats, ["ENT-A"])


def test_historique_tronque_refuse() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(VENDREDI))
    etats = tickets_etats(flux.evenements, [LUNDI])
    with pytest.raises(UsineErreur, match="DEMO-1"):
        kpi(etats, ["ENT-A"])


def _etat_a_la_main(d: date, statut: str, entree: date | None) -> pl.DataFrame:
    ligne: dict[str, object] = dict.fromkeys(SCHEMA_TICKET_ETAT.colonnes)
    ligne.update(
        date=d,
        cle_ticket="DEMO-1",
        type_ticket="anomalie",
        entite="ENT-A",
        statut=statut,
        date_derniere_entree=entree,
    )
    return pl.DataFrame([ligne], schema=dict(SCHEMA_TICKET_ETAT.colonnes))


def test_date_hors_jour_ouvre_refusee() -> None:
    samedi = date(2026, 10, 3)
    with pytest.raises(UsineErreur, match="hors Jour ouvré : 2026-10-03"):
        kpi(_etat_a_la_main(samedi, "nouvelle", samedi), ["ENT-A"])


def test_ouverte_sans_date_de_derniere_entree_refusee() -> None:
    with pytest.raises(UsineErreur, match=r"DEMO-1 .* sans date de dernière Entrée"):
        kpi(_etat_a_la_main(LUNDI, "nouvelle", None), ["ENT-A"])


def test_changement_d_entite() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(LUNDI))
    flux.modifier("DEMO-1", TypeTicket.anomalie, _ts(MARDI), Champ.entite, "ENT-A", "ENT-B")
    table = kpi(tickets_etats(flux.evenements, [LUNDI, MARDI]), ["ENT-A", "ENT-B"])
    assert _v(table, LUNDI, "ENT-A", "anomalies_ouvertes") == (1, 1)
    assert _v(table, MARDI, "ENT-A", "anomalies_ouvertes") == (0, 1)
    assert _v(table, LUNDI, "ENT-B", "anomalies_ouvertes") == (0, 1)
    assert _v(table, MARDI, "ENT-B", "anomalies_ouvertes") == (1, 1)
    for perimetre in ("ENT-A", "ENT-B", PERIMETRE_PROGRAMME):
        assert _v(table, MARDI, perimetre, "entrees_jour") == (0, 1)
        assert _v(table, MARDI, perimetre, "sorties_jour") == (0, 1)
    assert _v(table, LUNDI, PERIMETRE_PROGRAMME, "anomalies_ouvertes") == (1, 1)
    assert _v(table, MARDI, PERIMETRE_PROGRAMME, "anomalies_ouvertes") == (1, 1)


@pytest.mark.parametrize(
    ("entites", "valeur"), [(["ENT-A", "ENT-B", "ENT-A"], "ENT-A"), (["PROGRAMME"], "PROGRAMME")]
)
def test_entites_refusees(entites: list[str], valeur: str) -> None:
    with pytest.raises(UsineErreur, match=valeur):
        kpi(tickets_etats([], []), entites)


def test_table_vide() -> None:
    table = kpi(tickets_etats([], []), ["ENT-A"])
    assert table.is_empty()
    assert table.schema == pl.Schema(dict(SCHEMA_KPI.colonnes))


def test_sortie_dense_et_ordonnee() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(LUNDI))
    table = kpi(tickets_etats(flux.evenements, [LUNDI, MARDI]), ["ENT-B", "ENT-A"])
    valider(table, SCHEMA_KPI)
    attendu = [
        (d, perimetre, code, dimension)
        for d in (LUNDI, MARDI)
        for perimetre in ("ENT-B", "ENT-A", PERIMETRE_PROGRAMME)
        for code in CODES_KPI
        for dimension in DIMENSIONS_KPI[code]
    ]
    assert table.select("date", "perimetre", "code_kpi", "dimension").rows() == attendu
    assert len(CODES_KPI) == 12


def test_programme_compte_les_entites_hors_liste() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(LUNDI))
    flux.anomalie("DEMO-2", _ts(LUNDI), entite="ENT-Z")
    table = kpi(tickets_etats(flux.evenements, [LUNDI]), ["ENT-A"])
    assert _v(table, LUNDI, "ENT-A", "anomalies_ouvertes") == (1, 1)
    assert _v(table, LUNDI, PERIMETRE_PROGRAMME, "anomalies_ouvertes") == (2, 1)
    assert set(table["perimetre"]) == {"ENT-A", PERIMETRE_PROGRAMME}


@pytest.fixture(scope="module")
def generation() -> Generation:
    config = charger_yaml(RACINE / "config" / "programme.yaml", ConfigProgramme)
    return generer(config, 42, date(2026, 10, 12))


@pytest.fixture(scope="module")
def etats_generes(generation: Generation) -> pl.DataFrame:
    entete = generation.entete
    return tickets_etats(
        generation.evenements, jours_ouvres(entete.ancrage_semaines, entete.date_injection)
    )


def _entites(etats: pl.DataFrame) -> list[str]:
    return sorted(etats["entite"].drop_nulls().unique().to_list())


def test_journal_genere_schema_sans_flottant_et_deterministe(etats_generes: pl.DataFrame) -> None:
    entites = _entites(etats_generes)
    table = kpi(etats_generes, entites)
    valider(table, SCHEMA_KPI)
    assert not any(dtype.is_float() for dtype in table.schema.values())
    assert table.equals(kpi(etats_generes, entites))
    assert table.filter(pl.col("denominateur") < 0).is_empty()
    assert table.filter(pl.col("numerateur") < 0).is_empty()


def test_journal_genere_programme_somme_des_entites(etats_generes: pl.DataFrame) -> None:
    entites = _entites(etats_generes)
    assert len(entites) >= 2
    comptes = kpi(etats_generes, entites).filter(pl.col("code_kpi").is_in(_CODES_COMPTES))
    cles = ["date", "code_kpi", "dimension"]
    somme = (
        comptes.filter(pl.col("perimetre") != PERIMETRE_PROGRAMME)
        .group_by(cles)
        .agg(pl.col("numerateur").sum())
        .sort(cles)
    )
    programme = (
        comptes.filter(pl.col("perimetre") == PERIMETRE_PROGRAMME).select(*cles, "numerateur")
    ).sort(cles)
    assert somme.equals(programme)
    assert comptes.filter(pl.col("denominateur") != 1).is_empty()


def test_journal_genere_stock_egal_instantane(etats_generes: pl.DataFrame) -> None:
    table = kpi(etats_generes, _entites(etats_generes))
    ouvertes = (
        instantane(etats_generes)
        .filter(
            (pl.col("type_ticket") == TypeTicket.anomalie.value)
            & ~pl.col("statut").cast(pl.Utf8).is_in([s.value for s in STATUTS_FERMES])
        )
        .group_by("date")
        .agg(pl.col("nombre").sum())
    )
    attendu = dict(ouvertes.rows())
    stock = table.filter(
        (pl.col("perimetre") == PERIMETRE_PROGRAMME) & (pl.col("code_kpi") == "anomalies_ouvertes")
    )
    assert stock.height == etats_generes["date"].n_unique()
    for d, numerateur in stock.select("date", "numerateur").rows():
        assert numerateur == attendu.get(d, 0)
    assert sum(attendu.values()) > 0


def test_journal_genere_conservation_du_stock(etats_generes: pl.DataFrame) -> None:
    entites = _entites(etats_generes)
    table = kpi(etats_generes, entites)
    dates = sorted(table["date"].unique().to_list())
    assert len(dates) > 10
    mouvements = 0
    for perimetre in (*entites, PERIMETRE_PROGRAMME):
        for d in dates:
            veille = jour_ouvre_precedent(d)
            stock_veille = (
                _v(table, veille, perimetre, "anomalies_ouvertes")[0] if d != dates[0] else 0
            )
            entrees = _v(table, d, perimetre, "entrees_jour")[0]
            sorties = _v(table, d, perimetre, "sorties_jour")[0]
            assert _v(table, d, perimetre, "anomalies_ouvertes")[0] - stock_veille == (
                entrees - sorties
            ), f"{perimetre} {d}"
            mouvements += entrees + sorties
    assert mouvements > 0
