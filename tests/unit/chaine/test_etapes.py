"""Étapes déterministes `EtapeKpi` et `EtapePrevision` (Story 5.1)."""

import json
from datetime import UTC, date, datetime
from typing import cast

import polars as pl
import pytest

from tests.unit.chaine.environnement import INSTANT, contenu_previsions, horloge_pas_a_pas
from tests.unit.domaine.constructeur import Flux
from usine.chaine.etapes import EtapeKpi, EtapePrevision
from usine.contrats.calcul import SCHEMA_KPI, SCHEMA_TENDANCE
from usine.contrats.calendrier import jours_ouvres
from usine.contrats.config import ConfigChaine, ConfigUsine
from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import ContextePassage, StatutEtape
from usine.contrats.prevision import ContenuPrevisions
from usine.contrats.trace import TypeTrace
from usine.domaine.instantanes import tickets_etats
from usine.domaine.kpi import kpi, tendances
from usine.ports.consultation import Consultation
from usine.ports.etape import Etape as PortEtape

PASSAGE_ID = "20261012T073000Z-abc123"
PREMIER_JOUR = date(2026, 9, 28)  # lundi, ancrage des semaines
DATE_ARRETE = date(2026, 10, 9)
ENTITES = ("ENT-A", "ENT-B")
VERSION_DONNEES = "d" * 64


class ConsultationEtats:
    """Consultation réduite à `tickets_etats(jour)`, sur une table fixée."""

    def __init__(self, etats: pl.DataFrame) -> None:
        self._etats = etats
        self.dates: list[date | None] = []

    def tickets_etats(self, date_arrete: date | None = None) -> pl.DataFrame:
        self.dates.append(date_arrete)
        return self._etats.filter(pl.col("date") == date_arrete)


def _ctx(consultation: object, date_arrete: date = DATE_ARRETE) -> ContextePassage[Consultation]:
    return ContextePassage(
        date_arrete,
        PASSAGE_ID,
        ConfigUsine(chaine=ConfigChaine(palier=1)),
        cast(Consultation, consultation),
    )


def _historique() -> pl.DataFrame:
    """États des tickets de `PREMIER_JOUR` à `DATE_ARRETE` : Entrées, Sorties, deux Entités."""
    flux = Flux()
    flux.anomalie("DEMO-1", datetime(2026, 9, 28, 9, tzinfo=UTC))
    flux.anomalie("DEMO-2", datetime(2026, 9, 30, 9, tzinfo=UTC), entite="ENT-B")
    flux.anomalie("DEMO-3", datetime(2026, 10, 2, 9, tzinfo=UTC), gravite="majeure")
    flux.transition("DEMO-1", datetime(2026, 10, 6, 9, tzinfo=UTC), "nouvelle", "rejetee")
    flux.anomalie("DEMO-4", datetime(2026, 10, 8, 9, tzinfo=UTC), entite="ENT-B")
    return tickets_etats(flux.evenements, jours_ouvres(PREMIER_JOUR, DATE_ARRETE))


# --- EtapeKpi ---


def test_kpi_enveloppe_le_domaine() -> None:
    etats = _historique()
    consultation = ConsultationEtats(etats)
    etape = EtapeKpi(ENTITES, PREMIER_JOUR)
    assert isinstance(etape, PortEtape)
    resultat = etape.executer(_ctx(consultation))
    assert resultat.statut is StatutEtape.reussie
    assert resultat.traces == ()
    jours = jours_ouvres(PREMIER_JOUR, DATE_ARRETE)
    assert consultation.dates == list(jours)
    quotidiens = resultat.sorties["kpi"]
    assert isinstance(quotidiens, pl.DataFrame)
    attendu = kpi(etats, ENTITES)
    assert quotidiens.equals(attendu)
    assert sorted(quotidiens.get_column("date").unique().to_list()) == list(jours)
    hebdo = resultat.sorties["tendances"]
    assert isinstance(hebdo, pl.DataFrame)
    assert hebdo.equals(tendances(attendu, DATE_ARRETE, PREMIER_JOUR))
    assert not hebdo.is_empty()


def test_kpi_sans_ticket_a_la_date_d_arrete() -> None:
    """Date d'arrêté antérieure à toute création : tables vides, étape réussie."""
    flux = Flux()
    flux.anomalie("DEMO-1", datetime(2026, 10, 7, 9, tzinfo=UTC))
    etats = tickets_etats(flux.evenements, jours_ouvres(PREMIER_JOUR, DATE_ARRETE))
    resultat = EtapeKpi(ENTITES, PREMIER_JOUR).executer(
        _ctx(ConsultationEtats(etats), date(2026, 10, 6))
    )
    quotidiens, hebdo = resultat.sorties["kpi"], resultat.sorties["tendances"]
    assert isinstance(quotidiens, pl.DataFrame)
    assert isinstance(hebdo, pl.DataFrame)
    assert quotidiens.is_empty()
    assert hebdo.is_empty()
    assert quotidiens.schema == pl.Schema(SCHEMA_KPI.colonnes)
    assert hebdo.schema == pl.Schema(SCHEMA_TENDANCE.colonnes)


def test_kpi_date_anterieure_a_l_historique() -> None:
    etape = EtapeKpi(ENTITES, PREMIER_JOUR)
    with pytest.raises(UsineErreur, match="2026-09-25"):
        etape.executer(_ctx(ConsultationEtats(_historique()), date(2026, 9, 25)))


# --- EtapePrevision ---


def test_prevision_contenu_et_traces() -> None:
    contenu = contenu_previsions(DATE_ARRETE, "grille123456")
    recus: list[ContextePassage[Consultation]] = []

    def prevoir(ctx: ContextePassage[Consultation]) -> ContenuPrevisions:
        recus.append(ctx)
        return contenu

    etape = EtapePrevision(prevoir, VERSION_DONNEES, horloge_pas_a_pas())
    assert isinstance(etape, PortEtape)
    ctx = _ctx(object())
    resultat = etape.executer(ctx)
    assert recus == [ctx]
    assert resultat.statut is StatutEtape.reussie
    assert resultat.sorties["previsions"] == contenu
    prevision, risque = contenu.previsions[0], contenu.risques[0]
    traces = resultat.traces
    # Une trace par Prévision puis par Risque, dans l'ordre du contenu.
    assert [(t.entite, t.cible) for t in traces] == [("ENT-A", "ENT-A"), ("ENT-B", "ENT-B")]
    assert [t.horodatage for t in traces] == [INSTANT, INSTANT.replace(second=1)]
    for trace in traces:
        assert trace.type_trace is TypeTrace.prevision
        assert trace.passage_id == PASSAGE_ID
        assert trace.date_arrete == DATE_ARRETE
        assert trace.version_grille == "grille123456"
        assert trace.version_donnees == VERSION_DONNEES
        assert trace.tache is None
        assert trace.version_prompt is None
        assert trace.version_modele is None
    assert traces[0].sortie == prevision.model_dump_json()
    assert traces[1].sortie == risque.model_dump_json()
    assert json.loads(traces[0].entree_pseudonymisee) == {
        "date_arrete": "2026-10-09",
        "entite": "ENT-A",
        "methode": "baseline",
    }
    assert json.loads(traces[1].entree_pseudonymisee) == {
        "date_arrete": "2026-10-09",
        "entite": "ENT-B",
        "indicateur": "IND-1",
    }


def test_prevision_sans_contenu() -> None:
    vide = ContenuPrevisions(previsions=(), risques=())
    etape = EtapePrevision(lambda ctx: vide, VERSION_DONNEES, horloge_pas_a_pas())
    resultat = etape.executer(_ctx(object()))
    assert resultat.sorties["previsions"] == vide
    assert resultat.traces == ()


def test_prevision_d_un_autre_type() -> None:
    def prevoir(ctx: ContextePassage[Consultation]) -> ContenuPrevisions:
        return cast(ContenuPrevisions, ())

    etape = EtapePrevision(prevoir, VERSION_DONNEES, horloge_pas_a_pas())
    with pytest.raises(UsineErreur, match=r"tuple.*ContenuPrevisions"):
        etape.executer(_ctx(object()))
