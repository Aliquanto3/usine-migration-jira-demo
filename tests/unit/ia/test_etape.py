"""`EtapeExplications` : une Explication par Entité rouge ou orange, lue via la Consultation."""

from datetime import date
from typing import cast

import polars as pl

from tests.doublures.fournisseur_factice import FournisseurFactice
from tests.unit.ia.espions import (
    DATE_ARRETE,
    PASSAGE_ID,
    CacheMemoire,
    horloge_espion,
    meteo_rouge,
    pseudonymiseur,
    textes,
)
from usine.contrats.calcul import SCHEMA_KPI
from usine.contrats.config import ConfigChaine, ConfigUsine
from usine.contrats.llm import SCHEMA_REPARTITION_CAUSES, ReponseExplication, StatutControle
from usine.contrats.meteo import Couleur, MeteoEntite
from usine.contrats.passage import ContextePassage, StatutEtape
from usine.contrats.trace import TypeTrace
from usine.contrats.versions import version_prompt
from usine.ia.etape import EtapeExplications
from usine.ia.passerelle import Passerelle
from usine.ports.consultation import Consultation
from usine.ports.etape import Etape as PortEtape


class ConsultationMinimale:
    """Consultation réduite aux lectures de l'étape ; KPI et répartition vides par défaut."""

    def __init__(
        self,
        meteos: tuple[MeteoEntite, ...],
        table: pl.DataFrame,
        kpi: pl.DataFrame | None = None,
        repartition: pl.DataFrame | None = None,
    ) -> None:
        self._meteos = meteos
        self._table = table
        self._kpi = kpi if kpi is not None else pl.DataFrame(schema=dict(SCHEMA_KPI.colonnes))
        self._repartition = (
            repartition
            if repartition is not None
            else pl.DataFrame(schema=dict(SCHEMA_REPARTITION_CAUSES.colonnes))
        )
        self.dates: list[date | None] = []
        self.lectures_kpi: list[tuple[date | None, str | None]] = []
        self.lectures_repartition: list[str | None] = []

    def meteo(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[MeteoEntite, ...]:
        self.dates.append(date_arrete)
        return self._meteos

    def textes_tickets(self) -> pl.DataFrame:
        return self._table

    def kpi(self, date_arrete: date | None = None, entite: str | None = None) -> pl.DataFrame:
        self.lectures_kpi.append((date_arrete, entite))
        return self._kpi.filter(pl.col("perimetre") == entite)

    def repartition_causes(self, entite: str | None = None, palier: int = 2) -> pl.DataFrame:
        self.lectures_repartition.append(entite)
        return self._repartition.filter(pl.col("entite") == entite)


def test_explications_rouges_et_orange() -> None:
    verte = MeteoEntite(
        date_arrete=DATE_ARRETE,
        entite="ENT-V",
        couleur=Couleur.vert,
        regles=(),
        version_grille="grille123456",
    )
    rouge = meteo_rouge("ENT-A", ("DEMO-3",))
    regle_orange = (
        meteo_rouge("ENT-B", ("DEMO-5",)).regles[0].model_copy(update={"couleur": Couleur.orange})
    )
    orange = MeteoEntite(
        date_arrete=DATE_ARRETE,
        entite="ENT-B",
        couleur=Couleur.orange,
        regles=(regle_orange,),
        version_grille="grille123456",
    )
    consultation = ConsultationMinimale(
        (verte, rouge, orange),
        textes({"DEMO-3": ("Titre 3", "Desc 3"), "DEMO-5": ("Titre 5", "Desc 5")}),
    )
    factice = FournisseurFactice(
        [ReponseExplication(texte="DEMO-3 bloque."), ReponseExplication(texte="DEMO-5 tarde.")]
    )
    etape = EtapeExplications(
        Passerelle(factice, pseudonymiseur(), CacheMemoire(), horloge_espion([])),
        "d" * 64,
    )
    assert isinstance(etape, PortEtape)
    ctx = ContextePassage(
        DATE_ARRETE,
        PASSAGE_ID,
        ConfigUsine(chaine=ConfigChaine(palier=2)),
        cast(Consultation, consultation),
    )
    resultat = etape.executer(ctx)
    assert resultat.statut is StatutEtape.reussie
    explications = resultat.sorties["explications"]
    assert isinstance(explications, tuple)
    assert [e.entite for e in explications] == ["ENT-A", "ENT-B"]
    assert [e.statut_controle for e in explications] == [StatutControle.conforme] * 2
    assert consultation.dates == [DATE_ARRETE]
    assert consultation.lectures_kpi == [(DATE_ARRETE, "ENT-A"), (DATE_ARRETE, "ENT-B")]
    assert consultation.lectures_repartition == ["ENT-A", "ENT-B"]
    assert len(resultat.traces) == 2
    assert {t.type_trace for t in resultat.traces} == {TypeTrace.llm}
    assert {t.passage_id for t in resultat.traces} == {PASSAGE_ID}
    assert {t.version_donnees for t in resultat.traces} == {"d" * 64}


def test_aucune_entite_a_expliquer() -> None:
    consultation = ConsultationMinimale((), textes({}))
    factice = FournisseurFactice()
    etape = EtapeExplications(
        Passerelle(factice, pseudonymiseur(), CacheMemoire(), horloge_espion([])), "d"
    )
    ctx = ContextePassage(
        DATE_ARRETE,
        PASSAGE_ID,
        ConfigUsine(chaine=ConfigChaine(palier=2)),
        cast(Consultation, consultation),
    )
    resultat = etape.executer(ctx)
    assert resultat.sorties["explications"] == ()
    assert resultat.traces == ()
    assert factice.appels == []


def _ctx(consultation: ConsultationMinimale) -> ContextePassage[Consultation]:
    return ContextePassage(
        DATE_ARRETE,
        PASSAGE_ID,
        ConfigUsine(chaine=ConfigChaine(palier=2)),
        cast(Consultation, consultation),
    )


def test_prompt_contient_les_titres_lus_via_la_consultation() -> None:
    consultation = ConsultationMinimale(
        (meteo_rouge("ENT-A", ("DEMO-3", "DEMO-7")),),
        textes(
            {
                "DEMO-3": ("Virement rejeté en recette", "Desc 3"),
                "DEMO-7": ("Solde client faux", "Desc 7"),
                "DEMO-9": ("Ticket hors cause", "Desc 9"),
            }
        ),
    )
    factice = FournisseurFactice([ReponseExplication(texte="DEMO-3 bloque.")])
    etape = EtapeExplications(
        Passerelle(factice, pseudonymiseur(), CacheMemoire(), horloge_espion([])), "d" * 64
    )
    etape.executer(_ctx(consultation))
    (appel,) = factice.appels
    prompt = str(appel.entree)
    assert "Virement rejeté en recette" in prompt
    assert "Solde client faux" in prompt
    assert "Ticket hors cause" not in prompt


def test_version_prompt_du_gabarit_envoye() -> None:
    gabarit = (
        "Explique {{entite}} ({{couleur}}, {{date_arrete}}).\n"
        "{{regles}}\n{{kpi}}\n{{tickets}}\n{{causes}}\n"
    )
    octets = gabarit.encode("utf-8")
    consultation = ConsultationMinimale(
        (meteo_rouge("ENT-A", ("DEMO-3",)),), textes({"DEMO-3": ("Titre 3", "Desc 3")})
    )
    factice = FournisseurFactice([ReponseExplication(texte="DEMO-3 bloque.")])
    etape = EtapeExplications(
        Passerelle(factice, pseudonymiseur(), CacheMemoire(), horloge_espion([])),
        "d" * 64,
        octets,
    )
    resultat = etape.executer(_ctx(consultation))
    (trace,) = resultat.traces
    assert trace.version_prompt == version_prompt(octets)
    assert str(factice.appels[0].entree).startswith("Explique ENT-A (rouge, 2026-10-09).")


def _etape(factice: FournisseurFactice) -> EtapeExplications:
    return EtapeExplications(
        Passerelle(factice, pseudonymiseur(), CacheMemoire(), horloge_espion([])), "d" * 64
    )


def test_prompt_contient_kpi_et_causes_lus_via_la_consultation() -> None:
    kpi = pl.DataFrame(
        {
            "date": [DATE_ARRETE] * 4,
            "perimetre": ["ENT-A", "ENT-A", "ENT-A", "ENT-B"],
            "code_kpi": ["KPI-STOCK", "KPI-TAUX", "KPI-TAUX", "KPI-AUTRE"],
            "dimension": ["", "", "bloquante", ""],
            "numerateur": [12, 3, 1, 99],
            "denominateur": [1, 8, 2, 1],
        },
        schema=dict(SCHEMA_KPI.colonnes),
    )
    repartition = pl.DataFrame(
        {
            "date": [DATE_ARRETE] * 4,
            "entite": ["ENT-A", "ENT-A", "ENT-A", "ENT-B"],
            "cause_racine": ["reprise_donnees", "parametrage", "environnement", "donnee_test"],
            "nombre": [2, 5, 2, 7],
            "part": [2 / 9, 5 / 9, 2 / 9, 1.0],
        },
        schema=dict(SCHEMA_REPARTITION_CAUSES.colonnes),
    )
    consultation = ConsultationMinimale(
        (meteo_rouge("ENT-A", ("DEMO-3",)),),
        textes({"DEMO-3": ("Titre 3", "Desc 3")}),
        kpi,
        repartition,
    )
    factice = FournisseurFactice([ReponseExplication(texte="DEMO-3 bloque.")])
    _etape(factice).executer(_ctx(consultation))
    prompt = str(factice.appels[0].entree)
    assert "IND-1" in prompt  # Règles déclenchantes
    assert "Titre 3" in prompt  # tickets en cause
    assert "- KPI-STOCK : 12\n- KPI-TAUX : 3/8\n" in prompt
    assert "1/2" not in prompt  # KPI ventilé exclu
    assert "KPI-AUTRE" not in prompt  # autre Entité
    assert (
        "- parametrage : 5 (56 %)\n- environnement : 2 (22 %)\n- reprise_donnees : 2 (22 %)\n"
        in prompt
    )
    assert "donnee_test" not in prompt


def test_prompt_sans_kpi_ni_repartition() -> None:
    """Story 6.5 non livrée : répartition vide, section « non disponible », sans erreur."""
    consultation = ConsultationMinimale(
        (meteo_rouge("ENT-A", ("DEMO-3",)),), textes({"DEMO-3": ("Titre 3", "Desc 3")})
    )
    factice = FournisseurFactice([ReponseExplication(texte="DEMO-3 bloque.")])
    resultat = _etape(factice).executer(_ctx(consultation))
    assert resultat.statut is StatutEtape.reussie
    prompt = str(factice.appels[0].entree)
    assert "### KPI de l'Entité\n\n- aucun\n" in prompt
    assert "### Causes racines proposées\n\n- non disponible\n" in prompt
