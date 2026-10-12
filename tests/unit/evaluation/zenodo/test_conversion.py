"""Conversion du Public Jira Dataset en `SerieStock` (Story 4.3, FR-51).

Extrait figé fictif au format du dump (API Jira v2, mars 2021, Europe/Paris = UTC+1) :
ALPHA (clé projet dans `fields.project`), BETA (clé tirée du préfixe, priorité `Highest`) et
GAMMA (aucun ticket éligible) ; OMEGA réunit les cas limites (créé résolu, fermé par le
seul statut, résolution antérieure à la création). Mouvements d'ALPHA par Jour ouvré,
calculés à la main :

    01/03 : +A1 +A4          stock 2
    02/03 : +A2 +A3          stock 4
    03/03 : +A7 −A1 −A4      stock 3
    04/03 : −A2              stock 2
    05/03 : −A3 −A7          stock 0
    08/03 : +A2 +A6 +A9      stock 3
    09/03 : +A8 −A6 −A8      stock 2
    10/03 : −A2              stock 1
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from evaluation.zenodo.conversion import PRIORITES_MAXIMALES, convertir_en_series
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import (
    CodeIndicateur,
    Couleur,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.prevision import SCHEMA_SERIE_STOCK, MethodePrevision, StatutPrevision
from usine.contrats.schemas import valider
from usine.domaine.prevision.baseline import prevoir_sortie

DEPOT = "apache"
EXTRAIT: list[dict[str, Any]] = json.loads(
    (Path(__file__).with_name("extrait_tickets.json")).read_text(encoding="utf-8")
)


def _tickets(*cles: str) -> list[dict[str, Any]]:
    return [t for t in EXTRAIT if t["key"] in cles]


def _lignes(df: pl.DataFrame) -> list[tuple[str, date, int, int, int]]:
    """(série, date, stock, Entrées, Sorties) de chaque ligne."""
    return [tuple(ligne) for ligne in df.select(list(SCHEMA_SERIE_STOCK.colonnes)).rows()]


def _j(jour: int) -> date:
    return date(2021, 3, jour)


ALPHA = f"{DEPOT}/ALPHA"
BETA = f"{DEPOT}/BETA"
OMEGA = f"{DEPOT}/OMEGA"


def test_ticket_ouvert_puis_resolu() -> None:
    series = convertir_en_series(_tickets("ALPHA-1"), depot=DEPOT)
    assert _lignes(series) == [
        (ALPHA, _j(1), 1, 1, 0),
        (ALPHA, _j(2), 1, 0, 0),
        (ALPHA, _j(3), 0, 0, 1),
    ]


def test_reouverture_est_une_nouvelle_entree() -> None:
    # Historiques volontairement désordonnés dans l'extrait : rejoués par `created`.
    series = convertir_en_series(_tickets("ALPHA-2"), depot=DEPOT)
    assert _lignes(series) == [
        (ALPHA, _j(2), 1, 1, 0),
        (ALPHA, _j(3), 1, 0, 0),
        (ALPHA, _j(4), 0, 0, 1),
        (ALPHA, _j(5), 0, 0, 0),
        (ALPHA, _j(8), 1, 1, 0),
        (ALPHA, _j(9), 1, 0, 0),
        (ALPHA, _j(10), 0, 0, 1),
    ]


def test_passage_en_priorite_maximale_puis_sortie() -> None:
    series = convertir_en_series(_tickets("ALPHA-3"), depot=DEPOT)
    assert _lignes(series) == [
        (ALPHA, _j(2), 1, 1, 0),
        (ALPHA, _j(3), 1, 0, 0),
        (ALPHA, _j(4), 1, 0, 0),
        (ALPHA, _j(5), 0, 0, 1),
    ]


def test_priorite_initiale_tiree_du_premier_changement() -> None:
    # `fields.priority` vaut Major (priorité courante) ; le premier changement part de Blocker.
    series = convertir_en_series(_tickets("ALPHA-4"), depot=DEPOT)
    assert _lignes(series) == [
        (ALPHA, _j(1), 1, 1, 0),
        (ALPHA, _j(2), 1, 0, 0),
        (ALPHA, _j(3), 0, 0, 1),
    ]


def test_hors_priorite_maximale_sans_effet() -> None:
    assert convertir_en_series(_tickets("ALPHA-5"), depot=DEPOT).is_empty()
    assert convertir_en_series(_tickets("BETA-2", "GAMMA-1"), depot=DEPOT).is_empty()
    seule = convertir_en_series(_tickets("ALPHA-1", "ALPHA-5"), depot=DEPOT)
    assert seule.equals(convertir_en_series(_tickets("ALPHA-1"), depot=DEPOT))


def test_week_end_rattache_au_lundi_suivant() -> None:
    # Vendredi 05/03 23:30 UTC = samedi 00:30 à Paris → lundi 08/03.
    series = convertir_en_series(_tickets("ALPHA-6"), depot=DEPOT)
    assert _lignes(series) == [(ALPHA, _j(8), 1, 1, 0), (ALPHA, _j(9), 0, 0, 1)]


def test_resolu_sans_changelog() -> None:
    series = convertir_en_series(_tickets("ALPHA-7"), depot=DEPOT)
    assert _lignes(series) == [
        (ALPHA, _j(3), 1, 1, 0),
        (ALPHA, _j(4), 1, 0, 0),
        (ALPHA, _j(5), 0, 0, 1),
    ]


def test_entree_et_sortie_le_meme_jour() -> None:
    series = convertir_en_series(_tickets("ALPHA-8"), depot=DEPOT)
    assert _lignes(series) == [(ALPHA, _j(9), 0, 1, 1)]


def test_ticket_cree_resolu_n_entre_qu_a_la_reouverture() -> None:
    # Le premier item `resolution` part de « Fixed » : résolu dès la création (lundi 01/03).
    series = convertir_en_series(_tickets("OMEGA-1"), depot=DEPOT)
    assert _lignes(series) == [
        (OMEGA, _j(3), 1, 1, 0),
        (OMEGA, _j(4), 1, 0, 0),
        (OMEGA, _j(5), 0, 0, 1),
    ]


def test_ferme_par_le_seul_statut() -> None:
    # Ni item `resolution` ni `resolutiondate`, statut « done » : résolu au dernier item
    # `status` (jeudi 04/03), sinon à la création.
    series = convertir_en_series(_tickets("OMEGA-2"), depot=DEPOT)
    assert _lignes(series) == [
        (OMEGA, _j(2), 1, 1, 0),
        (OMEGA, _j(3), 1, 0, 0),
        (OMEGA, _j(4), 0, 0, 1),
    ]
    sans_changelog = convertir_en_series(_tickets("OMEGA-3"), depot=DEPOT)
    assert _lignes(sans_changelog) == [(OMEGA, _j(3), 0, 1, 1)]


def test_resolution_anterieure_a_la_creation_rabattue() -> None:
    # Résolu lundi 08/03 23:00 à Paris, créé mardi 09/03 03:00 : tout au mardi.
    series = convertir_en_series(_tickets("OMEGA-4"), depot=DEPOT)
    assert _lignes(series) == [(OMEGA, _j(9), 0, 1, 1)]


def test_ticket_encore_en_stock_a_la_fin() -> None:
    # ALPHA-2 rouvert le 08/03, résolu le 10/03 : encore en stock le 09/03.
    series = convertir_en_series(_tickets("ALPHA-2"), depot=DEPOT, fin=_j(9))
    assert _lignes(series)[-2:] == [(ALPHA, _j(8), 1, 1, 0), (ALPHA, _j(9), 1, 0, 0)]
    assert series.get_column("sorties").sum() == 1


ALPHA_COMPLET = [
    (ALPHA, _j(1), 2, 2, 0),
    (ALPHA, _j(2), 4, 2, 0),
    (ALPHA, _j(3), 3, 1, 2),
    (ALPHA, _j(4), 2, 0, 1),
    (ALPHA, _j(5), 0, 0, 2),
    (ALPHA, _j(8), 3, 3, 0),
    (ALPHA, _j(9), 2, 1, 2),
    (ALPHA, _j(10), 1, 0, 1),
]

OMEGA_COMPLET = [
    (OMEGA, _j(2), 1, 1, 0),
    (OMEGA, _j(3), 2, 2, 1),
    (OMEGA, _j(4), 1, 0, 1),
    (OMEGA, _j(5), 0, 0, 1),
    (OMEGA, _j(8), 0, 0, 0),
    (OMEGA, _j(9), 0, 1, 1),
]


def test_extrait_complet() -> None:
    series = convertir_en_series(EXTRAIT, depot=DEPOT)
    assert _lignes(series) == [
        *ALPHA_COMPLET,
        (BETA, _j(1), 1, 1, 0),
        (BETA, _j(2), 1, 0, 0),
        (BETA, _j(3), 1, 0, 0),
        (BETA, _j(4), 0, 0, 1),
        *OMEGA_COMPLET,
    ]
    assert valider(series, SCHEMA_SERIE_STOCK).equals(series)
    for _, lignes in series.group_by("serie", maintain_order=True):
        precedent = 0
        for _, _, stock, entrees, sorties in _lignes(lignes):
            assert stock == precedent + entrees - sorties >= 0
            precedent = stock


def test_borne_de_fin() -> None:
    series = convertir_en_series(EXTRAIT, depot=DEPOT, fin=_j(5))
    assert _lignes(series) == [
        *ALPHA_COMPLET[:5],
        (BETA, _j(1), 1, 1, 0),
        (BETA, _j(2), 1, 0, 0),
        (BETA, _j(3), 1, 0, 0),
        (BETA, _j(4), 0, 0, 1),
        (BETA, _j(5), 0, 0, 0),
        *OMEGA_COMPLET[:4],
    ]


def test_borne_de_fin_anterieure_a_tout_evenement() -> None:
    assert convertir_en_series(EXTRAIT, depot=DEPOT, fin=date(2021, 2, 26)).is_empty()


def test_fin_non_ouvree() -> None:
    with pytest.raises(UsineErreur, match="2021-03-06 n'est pas un Jour ouvré"):
        convertir_en_series(EXTRAIT, depot=DEPOT, fin=_j(6))


def test_priorites_parametrables() -> None:
    assert frozenset({"Blocker", "Highest"}) == PRIORITES_MAXIMALES
    series = convertir_en_series(_tickets("BETA-2"), depot=DEPOT, priorites=frozenset({"Medium"}))
    assert _lignes(series) == [(BETA, _j(2), 1, 1, 0)]


def _incomplet(**champs: object) -> dict[str, Any]:
    return {"key": "DELTA-7", "fields": {"priority": {"name": "Blocker"}, **champs}}


@pytest.mark.parametrize(
    ("ticket", "cause"),
    [
        (_incomplet(), "fields.created absent"),
        (_incomplet(created=None), "fields.created absent"),
        (_incomplet(created="2021-03-01T10:00:00.000"), "fields.created sans fuseau"),
        (_incomplet(created="hier"), "fields.created illisible"),
        (
            {
                **_incomplet(created="2021-03-01T10:00:00.000+0000"),
                "changelog": {"histories": [{"items": []}]},
            },
            "changelog.histories.created absent",
        ),
    ],
)
def test_document_incomplet(ticket: dict[str, Any], cause: str) -> None:
    with pytest.raises(UsineErreur, match=f"DELTA-7 : {cause}"):
        convertir_en_series([ticket], depot=DEPOT)


def test_ticket_sans_cle() -> None:
    with pytest.raises(UsineErreur, match="ticket sans clé"):
        convertir_en_series([{"fields": {}}], depot=DEPOT)


def test_serie_acceptee_par_la_baseline() -> None:
    series = convertir_en_series(EXTRAIT, depot=DEPOT)
    meteo = MeteoEntite(
        date_arrete=_j(10),
        entite=ALPHA,
        couleur=Couleur.rouge,
        regles=(
            RegleDeclenchante(
                code=CodeIndicateur.ind_1,
                couleur=Couleur.rouge,
                operateur=Operateur.superieur_ou_egal,
                numerateur=1,
                denominateur=1,
                seuil_numerateur=1,
                seuil_denominateur=1,
                tickets_en_cause=(),
            ),
        ),
        version_grille="grille-test",
    )
    prevision = prevoir_sortie(series, meteo)
    assert prevision.methode is MethodePrevision.baseline
    assert prevision.statut is StatutPrevision.pas_de_sortie_projetee
    facteurs = {f.nom: (f.numerateur, f.denominateur) for f in prevision.facteurs}
    assert facteurs["stock"] == (1, 1)
    assert facteurs["entrees"] == (9, 1)
    assert facteurs["sorties"] == (8, 1)
    assert facteurs["velocite_nette"] == (-1, 8)


def test_deterministe_et_independant_de_l_ordre() -> None:
    premiere = convertir_en_series(EXTRAIT, depot=DEPOT)
    assert convertir_en_series(EXTRAIT, depot=DEPOT).equals(premiere)
    assert convertir_en_series(reversed(EXTRAIT), depot=DEPOT).equals(premiere)
