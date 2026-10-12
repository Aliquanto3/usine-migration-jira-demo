"""Extraction incrémentale : repère, marge, atomicité et bout en bout sur Jira Cloud (Story 2.3)."""

import json
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from tests.contrat.source_tickets.fabriques import evenements_essai
from tests.doublures import SourceEnMemoire
from tests.unit.adaptateurs.jira_cloud.outils import (
    CHEMIN_RECHERCHE,
    ServeurFixtures,
    evenements_attendus,
)
from tests.unit.adaptateurs.jira_http.outils import config_jira
from usine.adaptateurs.entrepot_duckdb import (
    EntrepotDuckDB,
    EtapeExtraction,
    ResultatExtraction,
    extraire,
)
from usine.adaptateurs.jira_cloud import SourceJiraCloud
from usine.contrats.config import ConfigChaine, ConfigUsine
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement
from usine.contrats.passage import ContextePassage, StatutEtape
from usine.ports import Etape
from usine.ports.consultation import Consultation

MARGE = timedelta(minutes=10)
T1 = datetime(2026, 9, 5, 0, 0, tzinfo=UTC)
T2 = T1 + timedelta(hours=1, seconds=30)


class SourceEspion:
    """`SourceEnMemoire` qui note chaque `depuis` demandé et le moment de l'appel."""

    def __init__(self, evenements: tuple[Evenement, ...], journal: list[str]) -> None:
        self._source = SourceEnMemoire(evenements)
        self._journal = journal
        self.depuis: list[datetime | None] = []

    def evenements(self, depuis: datetime | None = None) -> Iterator[Evenement]:
        self._journal.append("source")
        self.depuis.append(depuis)
        return self._source.evenements(depuis)


def _horloge(instant: datetime, journal: list[str]) -> Callable[[], datetime]:
    def horloge() -> datetime:
        journal.append("horloge")
        return instant

    return horloge


def _entrepot(tmp_path: Path) -> EntrepotDuckDB:
    return EntrepotDuckDB(tmp_path / "entrepot.duckdb")


def test_premier_passage_sans_depuis_repere_pris_avant_la_source(tmp_path: Path) -> None:
    journal: list[str] = []
    source = SourceEspion(evenements_essai(), journal)
    entrepot = _entrepot(tmp_path)
    resultat = extraire(source, entrepot, MARGE, _horloge(T1, journal))
    assert resultat == ResultatExtraction(ajouts=len(evenements_essai()), repere=T1, depuis=None)
    assert source.depuis == [None]
    assert journal == ["horloge", "source"]
    assert entrepot.repere() == T1
    assert tuple(entrepot.evenements()) == evenements_essai()


def test_passage_incremental_depuis_repere_moins_marge(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    repere = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
    entrepot.enregistrer([], repere)
    journal: list[str] = []
    source = SourceEspion(evenements_essai(), journal)
    maintenant = repere + timedelta(days=1)
    resultat = extraire(source, entrepot, MARGE, _horloge(maintenant, journal))
    depuis = repere - MARGE
    assert source.depuis == [depuis]
    attendus = [e for e in evenements_essai() if e.horodatage >= depuis]
    assert resultat == ResultatExtraction(ajouts=len(attendus), repere=maintenant, depuis=depuis)
    assert list(entrepot.evenements()) == attendus
    assert entrepot.repere() == maintenant


def _source_cloud(serveur: ServeurFixtures, maintenant: datetime) -> SourceJiraCloud:
    config = config_jira("cloud")
    return SourceJiraCloud(serveur.client(config), config, lambda: maintenant)


def _jql(serveur: ServeurFixtures) -> list[str]:
    return [
        json.loads(r.content)["jql"]
        for r in serveur.requetes
        if r.method == "POST" and r.url.path == CHEMIN_RECHERCHE
    ]


def test_bout_en_bout_jira_cloud_puis_rejeu_identique(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    premier = ServeurFixtures()
    resultat = extraire(_source_cloud(premier, T1), entrepot, MARGE, lambda: T1)
    assert premier.inattendues == []
    assert all("updated" not in jql for jql in _jql(premier))
    assert resultat.ajouts == len(evenements_attendus())
    assert tuple(entrepot.evenements()) == evenements_attendus()
    assert entrepot.repere() == T1

    second = ServeurFixtures()
    resultat = extraire(_source_cloud(second, T2), entrepot, MARGE, lambda: T2)
    assert second.inattendues == []
    # T2 − (T1 − 10 min) = 70 min 30 s, arrondi à 71 minutes.
    assert (
        _jql(second)
        == [
            'project = "DEMO" AND issuetype in ("Anomalie", "Cas de test", "Certification")'
            ' AND updated >= "-71m" ORDER BY key ASC'
        ]
        * 2
    )
    assert resultat == ResultatExtraction(ajouts=0, repere=T2, depuis=T1 - MARGE)
    assert tuple(entrepot.evenements()) == evenements_attendus()
    assert entrepot.repere() == T2


def test_coupure_au_premier_passage_rien_n_est_valide(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    serveur = ServeurFixtures()
    del serveur.reponses["recherche_2"]
    with pytest.raises(UsineErreur):
        extraire(_source_cloud(serveur, T1), entrepot, MARGE, lambda: T1)
    assert entrepot.repere() is None
    assert list(entrepot.evenements()) == []


def test_coupure_en_pagination_laisse_l_etat_anterieur_intact(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    essai = evenements_essai()
    entrepot.enregistrer(essai, T1)
    serveur = ServeurFixtures()
    del serveur.reponses["recherche_2"]
    with pytest.raises(UsineErreur):
        extraire(_source_cloud(serveur, T2), entrepot, MARGE, lambda: T2)
    assert serveur.inattendues != []
    assert tuple(entrepot.evenements()) == essai
    assert entrepot.repere() == T1


def _contexte() -> ContextePassage[Consultation]:
    return ContextePassage(
        date(2026, 10, 12),
        "20261012T063000Z-abc123",
        ConfigUsine(chaine=ConfigChaine(palier=1)),
        cast(Consultation, object()),
    )


def test_etape_extraction_ouvre_l_entrepot_et_reussit(tmp_path: Path) -> None:
    chemin = tmp_path / "donnees" / "entrepot.duckdb"
    etape = EtapeExtraction(SourceEnMemoire(evenements_essai()), chemin, MARGE, lambda: T1)
    assert isinstance(etape, Etape)
    resultat = etape.executer(_contexte())
    assert resultat.statut is StatutEtape.reussie
    assert dict(resultat.sorties) == {}
    entrepot = EntrepotDuckDB(chemin)
    assert entrepot.repere() == T1
    assert tuple(entrepot.evenements()) == evenements_essai()
    # Deuxième exécution : rien d'ajouté, repère avancé.
    EtapeExtraction(SourceEnMemoire(evenements_essai()), chemin, MARGE, lambda: T2).executer(
        _contexte()
    )
    assert tuple(entrepot.evenements()) == evenements_essai()
    assert entrepot.repere() == T2


def test_etape_extraction_en_echec_propage_l_erreur(tmp_path: Path) -> None:
    chemin = tmp_path / "entrepot.duckdb"
    serveur = ServeurFixtures()
    del serveur.reponses["recherche_2"]
    etape = EtapeExtraction(_source_cloud(serveur, T1), chemin, MARGE, lambda: T1)
    with pytest.raises(UsineErreur):
        etape.executer(_contexte())
    entrepot = EntrepotDuckDB(chemin)
    assert entrepot.repere() is None
    assert list(entrepot.evenements()) == []


def test_etape_extraction_expose_sa_configuration(tmp_path: Path) -> None:
    source = SourceEnMemoire(evenements_essai())
    chemin = tmp_path / "entrepot.duckdb"
    etape = EtapeExtraction(source, chemin, MARGE, lambda: T1)
    assert (etape.source, etape.chemin, etape.marge) == (source, chemin, MARGE)


def test_etape_extraction_appelle_fermer_apres_succes(tmp_path: Path) -> None:
    fermetures: list[str] = []
    etape = EtapeExtraction(
        SourceEnMemoire(evenements_essai()),
        tmp_path / "entrepot.duckdb",
        MARGE,
        lambda: T1,
        fermer=lambda: fermetures.append("fermé"),
    )
    assert etape.executer(_contexte()).statut is StatutEtape.reussie
    assert fermetures == ["fermé"]


def test_etape_extraction_appelle_fermer_apres_echec(tmp_path: Path) -> None:
    serveur = ServeurFixtures()
    del serveur.reponses["recherche_2"]
    fermetures: list[str] = []
    etape = EtapeExtraction(
        _source_cloud(serveur, T1),
        tmp_path / "entrepot.duckdb",
        MARGE,
        lambda: T1,
        fermer=lambda: fermetures.append("fermé"),
    )
    with pytest.raises(UsineErreur):
        etape.executer(_contexte())
    assert fermetures == ["fermé"]
