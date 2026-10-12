"""Tests des KPI quotidiens et des Tendances hebdomadaires (Stories 3.2 et 3.3)."""

from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from tests.unit.domaine.constructeur import Flux
from usine.config import charger_yaml
from usine.contrats.calcul import PERIMETRE_PROGRAMME, SCHEMA_KPI, SCHEMA_TENDANCE
from usine.contrats.calendrier import (
    fenetre_glissante,
    jour_ouvre_precedent,
    jours_ouvres,
    semaine_programme,
)
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.schemas import valider
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, STATUTS_FERMES, Champ, TypeTicket
from usine.domaine.instantanes import instantane, tickets_etats
from usine.domaine.kpi import (
    CODES_KPI,
    CODES_TENDANCE,
    DIMENSIONS_KPI,
    NOMBRE_SEMAINES_TENDANCE,
    kpi,
    tendances,
)
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


# --- Tendances hebdomadaires (Story 3.3, FR-12) ---


def _kpi_a_la_main(
    jours: list[date],
    entrees: list[int] | None = None,
    sorties: list[int] | None = None,
    perimetres: tuple[str, ...] = ("ENT-A", PERIMETRE_PROGRAMME),
) -> pl.DataFrame:
    """Table `SCHEMA_KPI` réduite : stock = rang du jour + 1, Entrées et Sorties données."""
    entrees = entrees or [0] * len(jours)
    sorties = sorties or [0] * len(jours)
    lignes = []
    for rang, jour in enumerate(jours):
        for perimetre in perimetres:
            lignes += [
                (jour, perimetre, "anomalies_ouvertes", "", rang + 1, 1),
                (jour, perimetre, "anomalies_ouvertes_gravite", "bloquante", rang, 1),
                (jour, perimetre, "anomalies_ouvertes_gravite", "majeure", 1, 1),
                (jour, perimetre, "entrees_jour", "", entrees[rang], 1),
                (jour, perimetre, "sorties_jour", "", sorties[rang], 1),
                (jour, perimetre, "taux_ko_cas_de_test", "recette", rang, rang + 2),
            ]
    return pl.DataFrame(lignes, schema=dict(SCHEMA_KPI.colonnes), orient="row")


def _semaines(table: pl.DataFrame) -> list[int]:
    return sorted({semaine_programme(d, LUNDI_28) for d in table["date"].to_list()})


def test_tendance_semaine_complete() -> None:
    entree = _kpi_a_la_main(list(jours_ouvres(LUNDI_28, VENDREDI)))
    table = tendances(entree, VENDREDI, LUNDI_28)
    valider(table, SCHEMA_TENDANCE)
    assert set(table["date"]) == {VENDREDI}
    du_vendredi = entree.filter(pl.col("date") == VENDREDI)
    assert table.filter(pl.col("code_kpi").is_in(CODES_KPI)).equals(du_vendredi)
    assert _v(table, VENDREDI, "ENT-A", "taux_ko_cas_de_test", "recette") == (4, 6)


def test_tendance_cumul_de_la_semaine() -> None:
    jours = list(jours_ouvres(LUNDI_28, VENDREDI))
    table = tendances(_kpi_a_la_main(jours, [1, 0, 2, 0, 1], [0, 1, 1, 0, 0]), VENDREDI, LUNDI_28)
    for perimetre in ("ENT-A", PERIMETRE_PROGRAMME):
        assert _v(table, VENDREDI, perimetre, "entrees_semaine") == (4, 1)
        assert _v(table, VENDREDI, perimetre, "sorties_semaine") == (2, 1)
        assert _v(table, VENDREDI, perimetre, "entrees_jour") == (1, 1)


def test_tendance_semaine_partielle() -> None:
    jours = list(jours_ouvres(LUNDI_28, MERCREDI))
    entree = _kpi_a_la_main(jours, [1, 1, 1, 1, 1, 2, 3, 4], [0, 1, 0, 0, 0, 1, 0, 2])
    table = tendances(entree, MERCREDI, LUNDI_28)
    assert sorted(set(table["date"])) == [VENDREDI, MERCREDI]
    assert _v(table, MERCREDI, "ENT-A", "anomalies_ouvertes") == (8, 1)
    assert _v(table, MERCREDI, "ENT-A", "entrees_semaine") == (9, 1)
    assert _v(table, MERCREDI, "ENT-A", "sorties_semaine") == (3, 1)
    assert _v(table, VENDREDI, "ENT-A", "entrees_semaine") == (5, 1)
    assert _v(table, VENDREDI, "ENT-A", "sorties_semaine") == (1, 1)


def test_tendance_ignore_le_futur() -> None:
    jours = list(jours_ouvres(LUNDI_28, date(2026, 10, 9)))
    complete = _kpi_a_la_main(jours, list(range(len(jours))), [1] * len(jours))
    tronquee = complete.filter(pl.col("date") <= MERCREDI)
    assert tendances(complete, MERCREDI, LUNDI_28).equals(tendances(tronquee, MERCREDI, LUNDI_28))


def test_tendance_huit_dernieres_semaines() -> None:
    fin = date(2026, 12, 2)  # mercredi de la semaine 10
    table = tendances(_kpi_a_la_main(list(jours_ouvres(LUNDI_28, fin))), fin, LUNDI_28)
    assert semaine_programme(fin, LUNDI_28) == 10
    assert _semaines(table) == list(range(3, 11))
    assert len(_semaines(table)) == NOMBRE_SEMAINES_TENDANCE


def test_tendance_semaine_sans_jour() -> None:
    fin = date(2026, 10, 14)  # mercredi de la semaine 3
    table = tendances(_kpi_a_la_main(list(jours_ouvres(LUNDI, fin))), fin, LUNDI_28)
    assert _semaines(table) == [2, 3]


def test_tendance_date_d_arrete_absente() -> None:
    entree = _kpi_a_la_main(list(jours_ouvres(LUNDI_28, VENDREDI)))
    with pytest.raises(UsineErreur, match="2026-10-07"):
        tendances(entree, MERCREDI, LUNDI_28)


def test_tendance_date_d_arrete_anterieure() -> None:
    entree = _kpi_a_la_main(list(jours_ouvres(LUNDI, MERCREDI)))
    with pytest.raises(UsineErreur, match="2026-10-01"):
        tendances(entree, JEUDI, LUNDI_28)


def test_tendance_code_inconnu() -> None:
    entree = _kpi_a_la_main([LUNDI]).with_columns(
        pl.when(pl.col("code_kpi") == "anomalies_ouvertes")
        .then(pl.lit("code_mystere"))
        .otherwise(pl.col("code_kpi"))
        .alias("code_kpi")
    )
    with pytest.raises(UsineErreur, match="code_mystere"):
        tendances(entree, LUNDI, LUNDI_28)


@pytest.mark.parametrize(("ancrage", "valeur"), [(LUNDI, "2026-10-01"), (MARDI, "2026-10-06")])
def test_tendance_ancrage_refuse(ancrage: date, valeur: str) -> None:
    entree = _kpi_a_la_main(list(jours_ouvres(JEUDI, LUNDI)))
    with pytest.raises(UsineErreur, match=valeur):
        tendances(entree, LUNDI, ancrage)


def test_tendance_table_vide() -> None:
    table = tendances(pl.DataFrame(schema=dict(SCHEMA_KPI.colonnes)), MERCREDI, LUNDI_28)
    assert table.is_empty()
    valider(table, SCHEMA_TENDANCE)


def test_tendance_ordre() -> None:
    jours = list(jours_ouvres(LUNDI_28, MARDI))
    entree = _kpi_a_la_main(jours, perimetres=("ENT-B", "ENT-A", PERIMETRE_PROGRAMME))
    table = tendances(entree.reverse(), MARDI, LUNDI_28)
    codes = [
        ("anomalies_ouvertes", ""),
        ("anomalies_ouvertes_gravite", "majeure"),
        ("anomalies_ouvertes_gravite", "bloquante"),
        ("entrees_jour", ""),
        ("sorties_jour", ""),
        ("taux_ko_cas_de_test", "recette"),
        ("entrees_semaine", ""),
        ("sorties_semaine", ""),
    ]
    attendu = [
        (d, perimetre, code, dimension)
        for d in (VENDREDI, MARDI)
        for perimetre in (PERIMETRE_PROGRAMME, "ENT-A", "ENT-B")
        for code, dimension in codes
    ]
    assert table.select("date", "perimetre", "code_kpi", "dimension").rows() == attendu


@pytest.fixture(scope="module")
def kpi_generes(etats_generes: pl.DataFrame) -> pl.DataFrame:
    return kpi(etats_generes, _entites(etats_generes))


def test_journal_genere_tendances(generation: Generation, kpi_generes: pl.DataFrame) -> None:
    d, ancrage = generation.entete.date_injection, generation.entete.ancrage_semaines
    table = tendances(kpi_generes, d, ancrage)
    valider(table, SCHEMA_TENDANCE)
    assert not any(dtype.is_float() for dtype in table.schema.values())
    assert table.equals(tendances(kpi_generes, d, ancrage))
    semaines = {semaine_programme(jour, ancrage): jour for jour in table["date"].unique()}
    assert sorted(semaines) == list(range(1, 9))
    assert semaines[8] == d
    assert set(table["code_kpi"]) == set(CODES_TENDANCE)
    numeros = {jour: semaine_programme(jour, ancrage) for jour in kpi_generes["date"].unique()}
    avec_semaine = kpi_generes.with_columns(
        pl.col("date").replace_strict(numeros, return_dtype=pl.Int64()).alias("semaine")
    )
    perimetres = kpi_generes["perimetre"].unique().to_list()
    for semaine, jour in semaines.items():
        assert (
            table.filter((pl.col("date") == jour) & pl.col("code_kpi").is_in(CODES_KPI))
            .sort("perimetre", "code_kpi", "dimension")
            .equals(
                kpi_generes.filter(pl.col("date") == jour).sort(
                    "perimetre", "code_kpi", "dimension"
                )
            )
        )
        for perimetre in perimetres:
            for cumul, quotidien in (
                ("entrees_semaine", "entrees_jour"),
                ("sorties_semaine", "sorties_jour"),
            ):
                somme = avec_semaine.filter(
                    (pl.col("semaine") == semaine)
                    & (pl.col("perimetre") == perimetre)
                    & (pl.col("code_kpi") == quotidien)
                )["numerateur"].sum()
                assert _v(table, jour, perimetre, cumul) == (somme, 1)
