"""Étapes déterministes `EtapeKpi`, `EtapePrevision` (Story 5.1) et `prevision_du_passage` (5.3)."""

import json
from datetime import UTC, date, datetime
from typing import cast

import polars as pl
import pytest

from tests.unit.chaine.environnement import (
    INSTANT,
    PROGRAMME_REDUIT,
    RACINE_DEPOT,
    contenu_previsions,
    horloge_pas_a_pas,
)
from tests.unit.domaine.constructeur import Flux
from usine.chaine.etapes import EtapeKpi, EtapeMeteo, EtapePrevision, prevision_du_passage
from usine.config import charger_yaml
from usine.contrats.calcul import SCHEMA_KPI, SCHEMA_TENDANCE
from usine.contrats.calendrier import TAILLE_FENETRE_GLISSANTE, jours_ouvres
from usine.contrats.config import ConfigChaine, ConfigProgramme, ConfigUsine, GrilleMeteo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import Couleur, MeteoEntite
from usine.contrats.passage import ContextePassage, StatutEtape
from usine.contrats.prevision import ContenuPrevisions, StatutPrevision
from usine.contrats.trace import TypeTrace
from usine.domaine.instantanes import tickets_etats
from usine.domaine.kpi import kpi, tendances
from usine.domaine.meteo import DECALAGE_IND8, indicateurs, meteo
from usine.domaine.prevision.baseline import ParametresBaseline, prevoir_sortie
from usine.domaine.prevision.risque import ParametresRisque, risques_entree_rouge
from usine.domaine.prevision.serie import series_stock
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


# --- prevision_du_passage (Story 5.3) ---


class ConsultationPrevision:
    """Consultation réduite à `tickets_etats`, `indicateurs` et `meteo` d'un jour, fixés."""

    def __init__(
        self, etats: pl.DataFrame, tables: pl.DataFrame, meteos: tuple[MeteoEntite, ...]
    ) -> None:
        self._etats = etats
        self._tables = tables
        self._meteos = meteos

    def tickets_etats(self, date_arrete: date | None = None) -> pl.DataFrame:
        return self._etats.filter(pl.col("date") == date_arrete)

    def indicateurs(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> pl.DataFrame:
        return self._tables.filter(pl.col("date") == date_arrete)

    def meteo(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[MeteoEntite, ...]:
        return tuple(m for m in self._meteos if m.date_arrete == date_arrete)


def _grille_et_programme() -> tuple[GrilleMeteo, ConfigProgramme]:
    grille = charger_yaml(RACINE_DEPOT / "config" / "grille_meteo.yaml", GrilleMeteo)
    return grille, charger_yaml(PROGRAMME_REDUIT, ConfigProgramme)


def _passage_a_risque() -> tuple[pl.DataFrame, pl.DataFrame, tuple[MeteoEntite, ...]]:
    """ENT-A rouge par IND-1 puis orange ; ENT-B orange, bloquantes en hausse (Risque)."""
    flux = Flux()
    for cle in ("DEMO-1", "DEMO-2", "DEMO-3"):
        flux.anomalie(cle, datetime(2026, 9, 28, 9, tzinfo=UTC))
    flux.anomalie("DEMO-4", datetime(2026, 10, 1, 9, tzinfo=UTC))
    flux.transition("DEMO-1", datetime(2026, 10, 5, 9, tzinfo=UTC), "nouvelle", "fermee")
    flux.transition("DEMO-2", datetime(2026, 10, 7, 9, tzinfo=UTC), "nouvelle", "fermee")
    flux.transition("DEMO-3", datetime(2026, 10, 7, 10, tzinfo=UTC), "nouvelle", "fermee")
    flux.anomalie("DEMO-10", datetime(2026, 10, 5, 9, tzinfo=UTC), entite="ENT-B")
    flux.anomalie("DEMO-11", datetime(2026, 10, 7, 9, tzinfo=UTC), entite="ENT-B")
    jours = jours_ouvres(PREMIER_JOUR, DATE_ARRETE)
    etats = tickets_etats(flux.evenements, jours)
    grille, programme = _grille_et_programme()
    tables: list[pl.DataFrame] = []
    meteos: list[MeteoEntite] = []
    for jour in jours:
        jusque = etats.filter(pl.col("date") <= jour)
        tables.append(
            indicateurs(jusque, jour, ENTITES, grille, programme=programme, ancrage=PREMIER_JOUR)
        )
        meteos.extend(
            meteo(
                jusque, jour, ENTITES, grille, "grille", programme=programme, ancrage=PREMIER_JOUR
            )
        )
    return etats, pl.concat(tables, how="vertical"), tuple(meteos)


def test_prevision_du_passage_egale_le_domaine() -> None:
    etats, tables, meteos = _passage_a_risque()
    grille, _ = _grille_et_programme()
    prevoir = prevision_du_passage(grille, ENTITES, PREMIER_JOUR)
    contenu = prevoir(_ctx(ConsultationPrevision(etats, tables, meteos)))

    jours = jours_ouvres(PREMIER_JOUR, DATE_ARRETE)
    series = series_stock(etats, ENTITES, jours)
    previsions = tuple(prevoir_sortie(series, m) for m in meteos if m.couleur is Couleur.rouge)
    risques = tuple(
        projete.risque
        for m in meteos
        if m.couleur is not Couleur.rouge
        for projete in risques_entree_rouge(tables, m, grille).risques
    )
    assert contenu == ContenuPrevisions(previsions=previsions, risques=risques)
    # Une Prévision par Entité rouge et par Jour ouvré, des Risques pour ENT-B.
    rouges = [(m.date_arrete, m.entite) for m in meteos if m.couleur is Couleur.rouge]
    assert rouges
    assert {entite for _, entite in rouges} == {"ENT-A"}
    assert [(p.date_arrete, p.entite) for p in contenu.previsions] == rouges
    assert {p.statut for p in contenu.previsions} <= {
        StatutPrevision.sortie_projetee,
        StatutPrevision.pas_de_sortie_projetee,
    }
    assert contenu.risques
    assert {r.entite for r in contenu.risques} == {"ENT-B"}
    dates = [r.date_arrete for r in contenu.risques]
    assert dates == sorted(dates)


def test_prevision_du_passage_parametres_injectes() -> None:
    """Story 5.4 : les paramètres H-7 et H-8 reçus (de `chaine.yaml`) vont au domaine."""
    etats, tables, meteos = _passage_a_risque()
    grille, _ = _grille_et_programme()
    baseline = ParametresBaseline(horizon=7)
    risque = ParametresRisque(fenetre=6, horizon=3)
    prevoir = prevision_du_passage(grille, ENTITES, PREMIER_JOUR, baseline=baseline, risque=risque)
    contenu = prevoir(_ctx(ConsultationPrevision(etats, tables, meteos)))

    series = series_stock(etats, ENTITES, jours_ouvres(PREMIER_JOUR, DATE_ARRETE))
    previsions = tuple(
        prevoir_sortie(series, m, baseline) for m in meteos if m.couleur is Couleur.rouge
    )
    risques = tuple(
        projete.risque
        for m in meteos
        if m.couleur is not Couleur.rouge
        for projete in risques_entree_rouge(tables, m, grille, risque).risques
    )
    assert contenu == ContenuPrevisions(previsions=previsions, risques=risques)
    assert {p.horizon_jours_ouvres for p in contenu.previsions} == {7}
    assert contenu.risques
    assert {r.horizon_jours_ouvres for r in contenu.risques} == {3}


@pytest.mark.parametrize(
    ("decalage", "taille"),
    [(None, max(DECALAGE_IND8, TAILLE_FENETRE_GLISSANTE) + 1), (7, 8), (1, 6)],
)
def test_etape_meteo_taille_historique(decalage: int | None, taille: int) -> None:
    """Le tampon d'`EtapeMeteo` couvre `max(décalage, DECALAGE_IND8, Fenêtre) + 1` jours."""
    grille, programme = _grille_et_programme()
    if decalage is None:
        etape = EtapeMeteo(grille, "grille", ENTITES, PREMIER_JOUR, programme)
    else:
        etape = EtapeMeteo(grille, "grille", ENTITES, PREMIER_JOUR, programme, decalage=decalage)
    assert etape.taille_historique == taille


def test_prevision_du_passage_date_anterieure() -> None:
    etats, tables, meteos = _passage_a_risque()
    grille, _ = _grille_et_programme()
    prevoir = prevision_du_passage(grille, ENTITES, PREMIER_JOUR)
    with pytest.raises(UsineErreur, match="2026-09-25"):
        prevoir(_ctx(ConsultationPrevision(etats, tables, meteos), date(2026, 9, 25)))
