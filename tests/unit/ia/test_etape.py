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
from usine.contrats.config import ConfigChaine, ConfigUsine
from usine.contrats.llm import StatutControle
from usine.contrats.meteo import Couleur, MeteoEntite
from usine.contrats.passage import ContextePassage, StatutEtape
from usine.contrats.trace import TypeTrace
from usine.contrats.versions import version_prompt
from usine.ia.etape import EtapeExplications
from usine.ia.explication import ReponseExplication
from usine.ia.passerelle import Passerelle
from usine.ports.consultation import Consultation
from usine.ports.etape import Etape as PortEtape


class ConsultationMinimale:
    """Consultation réduite aux deux lectures de l'étape."""

    def __init__(self, meteos: tuple[MeteoEntite, ...], table: pl.DataFrame) -> None:
        self._meteos = meteos
        self._table = table
        self.dates: list[date | None] = []

    def meteo(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[MeteoEntite, ...]:
        self.dates.append(date_arrete)
        return self._meteos

    def textes_tickets(self) -> pl.DataFrame:
        return self._table


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
    gabarit = "Explique {{entite}} ({{couleur}}, {{date_arrete}}).\n{{regles}}\n{{tickets}}\n"
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
