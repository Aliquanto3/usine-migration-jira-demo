"""`SerieStock` des Anomalies bloquantes depuis l'état des tickets (Story 5.3, tâche préalable).

Jours ouvrés d'essai : lundi 05/10/2026 (J1), mardi 06/10 (J2), mercredi 07/10 (J3).
"""

from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from tests.unit.chaine.environnement import DATE_ARRETE, horloge_figee, preparer_racine
from tests.unit.domaine.constructeur import Flux
from usine.composition import lancer_rapport
from usine.contrats.calendrier import jours_ouvres
from usine.contrats.erreurs import UsineErreur
from usine.contrats.prevision import SCHEMA_SERIE_STOCK
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, Champ, TypeTicket
from usine.domaine.instantanes import tickets_etats
from usine.domaine.prevision.serie import series_stock

J1, J2, J3 = date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7)
JOURS = (J1, J2, J3)


def _a(jour: date) -> datetime:
    """9 h UTC le jour donné."""
    return datetime(jour.year, jour.month, jour.day, 9, tzinfo=UTC)


def _serie(flux: Flux, entites: tuple[str, ...] = ("ENT-A",)) -> dict[str, list[tuple[int, ...]]]:
    """Série par Entité : (stock, entrées, sorties) de chaque jour de `JOURS`."""
    table = series_stock(tickets_etats(flux.evenements, JOURS), entites, JOURS)
    assert table.schema == pl.Schema(SCHEMA_SERIE_STOCK.colonnes)
    assert table.select("serie", "date").rows() == [(e, j) for e in entites for j in JOURS]
    return {
        entite: table.filter(pl.col("serie") == entite).select("stock", "entrees", "sorties").rows()
        for entite in entites
    }


def test_serie_nominale() -> None:
    """Ouverture J1, seconde J2 ; J3 : fermeture de la première, majeure passée bloquante."""
    flux = Flux()
    flux.anomalie("DEMO-1", _a(J1))
    flux.anomalie("DEMO-3", _a(J1), gravite="majeure")
    flux.anomalie("DEMO-2", _a(J2))
    flux.transition("DEMO-1", _a(J3), "nouvelle", "fermee")
    flux.modifier("DEMO-3", TypeTicket.anomalie, _a(J3), Champ.gravite, "majeure", "bloquante")
    assert _serie(flux)["ENT-A"] == [(1, 1, 0), (2, 1, 0), (2, 1, 1)]


def test_transfert_d_entite() -> None:
    """Une bloquante ouverte passe de ENT-A à ENT-B : Sortie de A, Entrée de B le même jour."""
    flux = Flux()
    flux.anomalie("DEMO-1", _a(J1))
    flux.modifier("DEMO-1", TypeTicket.anomalie, _a(J2), Champ.entite, "ENT-A", "ENT-B")
    series = _serie(flux, ("ENT-A", "ENT-B"))
    assert series["ENT-A"] == [(1, 1, 0), (0, 0, 1), (0, 0, 0)]
    assert series["ENT-B"] == [(0, 0, 0), (1, 1, 0), (1, 0, 0)]


def test_jour_sans_ticket() -> None:
    """J1 sans aucun état : une ligne à 0/0/0 pour chaque Entité."""
    flux = Flux()
    flux.anomalie("DEMO-1", _a(J2))
    series = _serie(flux, ("ENT-A", "ENT-B"))
    assert series["ENT-A"] == [(0, 0, 0), (1, 1, 0), (1, 0, 0)]
    assert series["ENT-B"] == [(0, 0, 0)] * 3


def test_table_vide() -> None:
    vide = pl.DataFrame(schema=dict(SCHEMA_TICKET_ETAT.colonnes))
    table = series_stock(vide, ("ENT-A", "ENT-B"), JOURS)
    assert table.height == 6
    assert set(table.select("stock", "entrees", "sorties").rows()) == {(0, 0, 0)}


def test_gravite_changee() -> None:
    """Bloquante rétrogradée en majeure : Sortie ; mineure ou majeure ouvertes : hors stock."""
    flux = Flux()
    flux.anomalie("DEMO-1", _a(J1))
    flux.anomalie("DEMO-2", _a(J1), gravite="mineure")
    flux.modifier("DEMO-1", TypeTicket.anomalie, _a(J2), Champ.gravite, "bloquante", "majeure")
    assert _serie(flux)["ENT-A"] == [(1, 1, 0), (0, 0, 1), (0, 0, 0)]


def test_fermeture_et_reouverture() -> None:
    """Rejet J2 : Sortie ; réouverture J3 : Entrée."""
    flux = Flux()
    flux.anomalie("DEMO-1", _a(J1))
    flux.transition("DEMO-1", _a(J2), "nouvelle", "rejetee")
    flux.transition("DEMO-1", _a(J3), "rejetee", "nouvelle")
    assert _serie(flux)["ENT-A"] == [(1, 1, 0), (0, 0, 1), (1, 1, 0)]


def test_cas_de_test_et_certifications_ignores() -> None:
    flux = Flux()
    flux.creer(
        "DEMO-9",
        TypeTicket.cas_de_test,
        _a(J1),
        {Champ.statut_test: "ko", Champ.entite: "ENT-A", Champ.phase: "recette"},
    )
    assert _serie(flux)["ENT-A"] == [(0, 0, 0)] * 3


@pytest.mark.parametrize(
    ("jours", "motif"),
    [
        ((J1, J3), "non consécutifs"),
        ((J1, date(2026, 10, 10)), "pas un Jour ouvré"),
        ((J2, J1), "non consécutifs"),
    ],
)
def test_jours_refuses(jours: tuple[date, ...], motif: str) -> None:
    vide = pl.DataFrame(schema=dict(SCHEMA_TICKET_ETAT.colonnes))
    with pytest.raises(UsineErreur, match=motif):
        series_stock(vide, ("ENT-A",), jours)


def test_entites_en_double() -> None:
    vide = pl.DataFrame(schema=dict(SCHEMA_TICKET_ETAT.colonnes))
    with pytest.raises(UsineErreur, match="ENT-A"):
        series_stock(vide, ("ENT-A", "ENT-A"), JOURS)


def test_table_hors_schema() -> None:
    with pytest.raises(UsineErreur, match="SCHEMA_TICKET_ETAT"):
        series_stock(pl.DataFrame({"x": [1]}), ("ENT-A",), JOURS)


# --- Passage réel (graine 42, Date d'arrêté 2026-10-09) ---


@pytest.fixture(scope="module")
def repertoire(tmp_path_factory: pytest.TempPathFactory) -> Path:
    racine = preparer_racine(tmp_path_factory.mktemp("serie"))
    return lancer_rapport(racine, DATE_ARRETE, horloge_figee(), lambda: "5e7e00").repertoire


def test_passage_reel_identite_et_ind1(repertoire: Path) -> None:
    """Stock = IND-1 chaque Jour ouvré, et stock(j) = stock(j−1) + entrées(j) − sorties(j)."""
    etats = pl.read_parquet(repertoire / "tickets_etats.parquet")
    indicateurs = pl.read_parquet(repertoire / "indicateurs.parquet")
    jours = sorted(indicateurs.get_column("date").unique().to_list())
    assert jours == list(jours_ouvres(jours[0], DATE_ARRETE))
    entites = ("ENT-A", "ENT-B")
    serie = series_stock(etats, entites, jours)
    assert serie.height == len(entites) * len(jours)
    ind1 = {
        (entite, jour): numerateur
        for jour, entite, numerateur in indicateurs.filter(pl.col("code") == "IND-1")
        .select("date", "entite", "numerateur")
        .iter_rows()
    }
    maxima = {}
    for entite in entites:
        lignes = serie.filter(pl.col("serie") == entite).sort("date").to_dicts()
        precedent = 0
        for ligne in lignes:
            assert ligne["stock"] == ind1[(entite, ligne["date"])]
            assert ligne["stock"] == precedent + ligne["entrees"] - ligne["sorties"]
            precedent = ligne["stock"]
        maxima[entite] = max(ligne["stock"] for ligne in lignes)
    # Flux scripté (contrats 1.2) : sur le Programme réduit, les bloquantes de B prennent les
    # créations de chaque semaine ; ENT-A n'a jamais de bloquante ouverte.
    assert maxima["ENT-B"] > 0
