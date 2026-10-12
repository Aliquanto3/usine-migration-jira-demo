"""Outils de consultation de l'Agent, en lecture seule (Story 7.8, FR-39, FR-41, AD-11)."""

import ast
import inspect
from datetime import date
from pathlib import Path
from typing import cast

import polars as pl
import pytest
from pydantic import ValidationError

from tests.contrat.consultation.fabriques import passage_palier_2
from tests.unit.ia.espions import DATE_ARRETE, meteo_rouge, prevision_rouge, risque_entree_rouge
from usine.contrats.agent import (
    AnomalieResume,
    ArgumentsGetMeteo,
    ArgumentsGetPrevision,
    ArgumentsGetRisques,
    ArgumentsGetTendance,
    ArgumentsListAnomalies,
    AucuneDonnee,
    ResultatGetMeteo,
    ResultatGetPrevision,
    ResultatGetRisques,
    ResultatGetTendance,
    ResultatListAnomalies,
)
from usine.contrats.calcul import SCHEMA_TENDANCE
from usine.contrats.meteo import EvolutionMeteo, MeteoEntite
from usine.contrats.passage import ManifestePassage
from usine.contrats.prevision import Prevision, RisqueEntreeRouge
from usine.contrats.tickets import Gravite, Phase, StatutAnomalie
from usine.ia.agent import outils as module_outils
from usine.ia.agent.outils import NOMS_OUTILS, OutilsConsultation, outils_consultation
from usine.ports.consultation import Consultation

AUTRE_DATE = date(2026, 10, 8)
SANS_PASSAGE = date(2026, 10, 1)
NOMS_ATTENDUS = ("get_meteo", "list_anomalies", "get_tendance", "get_prevision", "get_risques")
OUTILS_DATES = ("get_meteo", "list_anomalies", "get_prevision", "get_risques")


def _anomalie(cle: str, statut: StatutAnomalie, entite: str = "ENT-A") -> AnomalieResume:
    return AnomalieResume(
        cle_ticket=cle,
        entite=entite,
        gravite=Gravite.majeure,
        phase=Phase.recette,
        domaine="clients",
        statut=statut,
        age_jours_ouvres=2,
    )


ANOMALIES = (
    _anomalie("DEMO-1", StatutAnomalie.en_analyse),
    _anomalie("DEMO-2", StatutAnomalie.nouvelle),
    _anomalie("DEMO-3", StatutAnomalie.en_analyse),
    _anomalie("DEMO-4", StatutAnomalie.en_analyse),
)


class ConsultationFactice:
    """Consultation réduite aux lectures servies par les outils ; journalise les appels."""

    def __init__(self, dates: tuple[date, ...] = (AUTRE_DATE, DATE_ARRETE)) -> None:
        self._dates = dates
        self.appels: list[tuple[str, dict[str, object]]] = []

    def _noter(self, nom: str, **parametres: object) -> None:
        self.appels.append((nom, parametres))

    def dates_disponibles(self) -> tuple[date, ...]:
        return self._dates

    def manifeste(self) -> ManifestePassage:
        self._noter("manifeste")
        return cast(ManifestePassage, type("M", (), {"date_arrete": DATE_ARRETE})())

    def meteo(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[MeteoEntite, ...]:
        self._noter("meteo", date_arrete=date_arrete, entite=entite)
        return tuple(
            m for m in (meteo_rouge("ENT-A"), meteo_rouge("ENT-B")) if entite in (None, m.entite)
        )

    def evolution_meteo(self, date_arrete: date | None = None) -> tuple[EvolutionMeteo, ...]:
        self._noter("evolution_meteo", date_arrete=date_arrete)
        return tuple(
            EvolutionMeteo.model_validate(
                {
                    "entite": entite,
                    "date_arrete": DATE_ARRETE,
                    "couleur": "rouge",
                    "date_j1": AUTRE_DATE,
                    "couleur_j1": None,
                    "date_j5": date(2026, 10, 2),
                    "couleur_j5": None,
                }
            )
            for entite in ("ENT-A", "ENT-B")
        )

    def anomalies(
        self,
        date_arrete: date | None = None,
        entite: str | None = None,
        gravite: Gravite | None = None,
        phase: Phase | None = None,
        domaine: str | None = None,
        limite: int | None = None,
        palier: int = 2,
    ) -> ResultatListAnomalies:
        self._noter("anomalies", date_arrete=date_arrete, limite=limite)
        assert date_arrete is not None
        retenues = ANOMALIES if limite is None else ANOMALIES[:limite]
        return ResultatListAnomalies(
            date_arrete=date_arrete, anomalies=retenues, total=len(ANOMALIES)
        )

    def tendances(self, entite: str | None = None, code_kpi: str | None = None) -> pl.DataFrame:
        self._noter("tendances", entite=entite, code_kpi=code_kpi)
        lignes = [
            {
                "date": DATE_ARRETE,
                "perimetre": "ENT-A",
                "code_kpi": "KPI-1",
                "dimension": "global",
                "numerateur": 3,
                "denominateur": 4,
            }
        ]
        table = pl.DataFrame(lignes, schema=dict(SCHEMA_TENDANCE.colonnes))
        return table.filter(pl.col("perimetre") == entite) if entite is not None else table

    def previsions(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[Prevision, ...]:
        self._noter("previsions", date_arrete=date_arrete, entite=entite)
        return (prevision_rouge(),)

    def risques(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[RisqueEntreeRouge, ...]:
        self._noter("risques", date_arrete=date_arrete, entite=entite)
        return (risque_entree_rouge(),)


def _executer(nom: str, arguments: dict[str, object], consultation: ConsultationFactice) -> object:
    (outil,) = (o for o in outils_consultation(cast(Consultation, consultation)) if o.nom == nom)
    return outil.executer(arguments)


# --- Inventaire -------------------------------------------------------------------------------


def test_noms_exacts_et_classes_des_contrats() -> None:
    outils = outils_consultation(cast(Consultation, ConsultationFactice()))
    assert tuple(o.nom for o in outils) == NOMS_ATTENDUS == NOMS_OUTILS
    for outil in outils:
        assert outil.description
        assert outil.arguments.__module__ == "usine.contrats.agent"
        methode = getattr(OutilsConsultation, outil.nom)
        retour = inspect.signature(methode, eval_str=True).return_annotation
        resultats = getattr(retour, "__args__", (retour,))
        assert all(r.__module__ == "usine.contrats.agent" for r in resultats)


# --- Matrice I/O ------------------------------------------------------------------------------


def test_date_absente_prend_la_date_du_manifeste() -> None:
    factice = ConsultationFactice()
    resultat = _executer("get_meteo", {}, factice)
    assert isinstance(resultat, ResultatGetMeteo)
    assert resultat.date_arrete == DATE_ARRETE
    assert len(resultat.meteos) == 2
    assert ("meteo", {"date_arrete": DATE_ARRETE, "entite": None}) in factice.appels


def test_date_disponible() -> None:
    factice = ConsultationFactice()
    resultat = _executer("get_prevision", {"date_arrete": AUTRE_DATE.isoformat()}, factice)
    assert resultat == ResultatGetPrevision(date_arrete=AUTRE_DATE, previsions=(prevision_rouge(),))
    assert ("previsions", {"date_arrete": AUTRE_DATE, "entite": None}) in factice.appels


def test_meteo_filtree_par_entite() -> None:
    resultat = _executer("get_meteo", {"entite": "ENT-B"}, ConsultationFactice())
    assert isinstance(resultat, ResultatGetMeteo)
    assert [m.entite for m in resultat.meteos] == ["ENT-B"]
    assert [e.entite for e in resultat.evolutions] == ["ENT-B"]


@pytest.mark.parametrize("nom", OUTILS_DATES)
def test_date_sans_passage(nom: str) -> None:
    factice = ConsultationFactice()
    resultat = _executer(nom, {"date_arrete": SANS_PASSAGE.isoformat()}, factice)
    assert resultat == AucuneDonnee(date_arrete=SANS_PASSAGE)
    assert isinstance(resultat, AucuneDonnee)
    assert resultat.message == "aucune donnée pour cette date"
    assert [n for n, _ in factice.appels] == []


@pytest.mark.parametrize("nom", OUTILS_DATES)
def test_passage_sans_aucune_date(nom: str) -> None:
    resultat = _executer(nom, {}, ConsultationFactice(dates=()))
    assert resultat == AucuneDonnee(date_arrete=None)


def test_tendance_sans_date_ni_aucune_donnee() -> None:
    outils = OutilsConsultation(cast(Consultation, ConsultationFactice(dates=())))
    plein = outils.get_tendance(ArgumentsGetTendance())
    vide = outils.get_tendance(ArgumentsGetTendance(entite="ENT-Z"))
    assert isinstance(plein, ResultatGetTendance)
    assert [(p.perimetre, p.numerateur, p.denominateur) for p in plein.points] == [("ENT-A", 3, 4)]
    assert vide == ResultatGetTendance(points=())


def test_filtre_statut_avant_limite() -> None:
    factice = ConsultationFactice()
    resultat = _executer("list_anomalies", {"statut": "en_analyse", "limite": 2}, factice)
    assert isinstance(resultat, ResultatListAnomalies)
    assert [a.cle_ticket for a in resultat.anomalies] == ["DEMO-1", "DEMO-3"]
    assert resultat.total == 3
    assert ("anomalies", {"date_arrete": DATE_ARRETE, "limite": None}) in factice.appels


def test_sans_statut_la_limite_va_a_la_consultation() -> None:
    factice = ConsultationFactice()
    resultat = _executer("list_anomalies", {"limite": 1}, factice)
    assert isinstance(resultat, ResultatListAnomalies)
    assert [a.cle_ticket for a in resultat.anomalies] == ["DEMO-1"]
    assert resultat.total == 4
    assert ("anomalies", {"date_arrete": DATE_ARRETE, "limite": 1}) in factice.appels


@pytest.mark.parametrize(
    ("nom", "arguments"),
    [
        ("list_anomalies", {"limite": 0}),
        ("list_anomalies", {"statut": "inconnu"}),
        ("get_meteo", {"champ_inconnu": 1}),
        ("get_risques", {"date_arrete": "pas une date"}),
    ],
)
def test_arguments_json_invalides(nom: str, arguments: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _executer(nom, arguments, ConsultationFactice())


def test_risques() -> None:
    outils = OutilsConsultation(cast(Consultation, ConsultationFactice()))
    resultat = outils.get_risques(ArgumentsGetRisques(entite="ENT-B"))
    assert resultat == ResultatGetRisques(date_arrete=DATE_ARRETE, risques=(risque_entree_rouge(),))


# --- Lecture seule ----------------------------------------------------------------------------

_VERBES_ECRITURE = ("ecrire", "creer", "modifier", "supprimer", "envoyer", "publier", "set_", "put")
_IMPORTS_PERMIS = ("usine.contrats", "usine.ports.consultation", "usine.consultation")
_PORTS_INTERDITS = (
    "usine.ports.source_tickets",
    "usine.ports.entrepot",
    "usine.ports.etape",
    "usine.ports.fournisseur_llm",
    "usine.ports.cache_llm",
)


def test_aucun_outil_ne_porte_un_verbe_d_ecriture() -> None:
    noms = [*NOMS_OUTILS, *(n for n in vars(OutilsConsultation) if not n.startswith("__"))]
    assert all(n.startswith(("get_", "list_", "_")) for n in noms)
    assert not [n for n in noms for v in _VERBES_ECRITURE if v in n]


def test_modules_de_l_agent_lecture_seule() -> None:
    """Hors `cli` (Typer), `ia.agent` n'importe que contrats, `Consultation` et la stdlib."""
    paquet = Path(module_outils.__file__).parent
    for fichier in sorted(paquet.rglob("*.py")):
        if fichier.name == "cli.py":
            continue
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom) and noeud.module:
                modules = [noeud.module]
            elif isinstance(noeud, ast.Import):
                modules = [a.name for a in noeud.names]
            else:
                continue
            for module in modules:
                assert not module.startswith(("usine.adaptateurs", "pydantic_ai", "httpx")), module
                assert not module.startswith(_PORTS_INTERDITS), module
                if module.startswith("usine"):
                    assert module.startswith(_IMPORTS_PERMIS), (fichier.name, module)
    assert "url_ticket" not in Path(module_outils.__file__).read_text(encoding="utf-8")


# --- Intégration ------------------------------------------------------------------------------


def test_integration_passage_palier_2() -> None:
    cas = passage_palier_2()
    outils = OutilsConsultation(cas.consultation)
    jour = cas.consultation.manifeste().date_arrete

    meteo = outils.get_meteo(ArgumentsGetMeteo(entite=cas.entite))
    assert isinstance(meteo, ResultatGetMeteo)
    assert meteo.date_arrete == jour
    assert meteo.meteos == cas.consultation.meteo(jour, cas.entite)

    anomalies = outils.list_anomalies(ArgumentsListAnomalies(entite=cas.entite))
    assert anomalies == cas.consultation.anomalies(jour, entite=cas.entite, limite=50)
    assert isinstance(anomalies, ResultatListAnomalies)
    statut = anomalies.anomalies[0].statut
    filtrees = outils.list_anomalies(ArgumentsListAnomalies(entite=cas.entite, statut=statut))
    assert isinstance(filtrees, ResultatListAnomalies)
    assert filtrees.anomalies
    assert all(a.statut == statut for a in filtrees.anomalies)

    previsions = outils.get_prevision(ArgumentsGetPrevision(entite=cas.entite))
    assert isinstance(previsions, ResultatGetPrevision)
    assert previsions.previsions
    risques = outils.get_risques(ArgumentsGetRisques())
    assert isinstance(risques, ResultatGetRisques)
    assert risques.risques == cas.consultation.risques(jour)

    tendance = outils.get_tendance(ArgumentsGetTendance(entite=cas.entite))
    assert isinstance(tendance, ResultatGetTendance)
    assert len(tendance.points) == cas.consultation.tendances(cas.entite).height

    absent = outils.get_meteo(ArgumentsGetMeteo(date_arrete=date(2000, 1, 3)))
    assert absent == AucuneDonnee(date_arrete=date(2000, 1, 3))
