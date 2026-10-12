"""Injection des tickets : ordre, état final, manifeste, refus et interruption (Story 1.6)."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.unit.adaptateurs.jira_http.outils import Attentes
from tests.unit.generateur.injecteur.conftest import FabriqueClient
from tests.unit.generateur.injecteur.faux_jira import API, FauxJira, Requete
from tests.unit.generateur.injecteur.test_site import verifier_sans_import
from usine.adaptateurs.jira_cloud.conversion import texte_adf
from usine.adaptateurs.journal import SourceJournal
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import ManifesteInjection
from usine.contrats.tickets import DOMAINES_CANONIQUES, Champ, TypeTicket
from usine.generateur.injecteur.injection import InjectionInterrompue, injecter
from usine.generateur.injecteur.plan import CHAMPS_SELECTION, PlanInjection
from usine.generateur.injecteur.site import SiteDemo, preparer_site

HORLOGE = datetime(2026, 10, 12, 10, tzinfo=UTC)


class Compteur:
    """Limiteur de débit des tests : compte ses appels."""

    def __init__(self) -> None:
        self.appels = 0

    def __call__(self) -> None:
        self.appels += 1


def _injecter(
    faux: FauxJira,
    fabrique: FabriqueClient,
    config: ConfigJira,
    plan: PlanInjection,
    *,
    limiter: Callable[[], None] | None = None,
    horloge: datetime = HORLOGE,
) -> tuple[SiteDemo, ManifesteInjection]:
    client = fabrique(faux)
    site = preparer_site(client, config, plan.valeurs_libres)
    manifeste = injecter(client, plan, site, config, lambda: horloge, limiter or Compteur())
    return site, manifeste


def _etat_jira(faux: FauxJira, cle: str, site: SiteDemo, config: ConfigJira) -> dict[Champ, str]:
    """État canonique d'un ticket du faux Jira, relu comme le ferait l'adaptateur L2."""
    ticket = faux.tickets[cle]
    etat: dict[Champ, str] = {Champ.titre: ticket.champs["summary"]}
    if "description" in ticket.champs:
        etat[Champ.description] = texte_adf(ticket.champs["description"], cle)
    for champ in CHAMPS_SELECTION:
        valeur = ticket.champs.get(site.champs[champ])
        if valeur is None:
            continue
        nom = valeur["value"]
        etat[champ] = nom if DOMAINES_CANONIQUES[champ] is None else config.valeurs[champ][nom]
    if ticket.type_id == site.types[TypeTicket.anomalie]:
        etat[Champ.statut] = config.valeurs[Champ.statut][ticket.statut]
    return etat


def test_injection_sur_site_vierge(
    fabrique_client: FabriqueClient,
    config: ConfigJira,
    plan: PlanInjection,
    chemin_journal: Path,
) -> None:
    faux = FauxJira()
    site, manifeste = _injecter(faux, fabrique_client, config, plan)
    creations = [r for r in faux.requetes if r.methode == "POST" and r.chemin == f"{API}/issue"]
    assert [r.corps["fields"]["summary"] for r in creations] == [
        t.valeurs[Champ.titre] for t in plan.tickets
    ]
    assert list(manifeste.correspondance_cles) == [t.cle for t in plan.tickets]
    for ticket in plan.tickets:
        cle_jira = manifeste.correspondance_cles[ticket.cle]
        assert faux.tickets[cle_jira].type_id == site.types[ticket.type_ticket]
        assert _etat_jira(faux, cle_jira, site, config) == dict(ticket.valeurs), ticket.cle
    assert manifeste.cle_projet == "DEMO"
    assert manifeste.date_injection == plan.date_injection
    assert manifeste.debut_injection == HORLOGE
    # Fin = max(horloge locale, serverTime) : ici l'heure du serveur, en avance.
    assert manifeste.horodatage_fin_injection == datetime(2099, 1, 1, 11, tzinfo=UTC)
    relu = SourceJournal(chemin_journal, manifeste)
    assert {e.cle_ticket for e in relu.evenements()} == set(manifeste.correspondance_cles.values())
    # Les transitions sont lues une fois par statut de départ (cache).
    lectures = [
        r for r in faux.requetes if r.chemin.endswith("/transitions") and r.methode == "GET"
    ]
    assert len(lectures) <= 4
    verifier_sans_import(faux)


def test_fin_d_injection_couvre_l_horloge_locale(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    tardive = datetime(2100, 1, 1, tzinfo=UTC)
    _, manifeste = _injecter(FauxJira(), fabrique_client, config, plan, horloge=tardive)
    assert manifeste.horodatage_fin_injection == tardive


def test_suite_de_requetes_deterministe(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    def suite() -> list[tuple[str, str, dict[str, str], Any]]:
        faux = FauxJira()
        _injecter(faux, fabrique_client, config, plan)
        return [(r.methode, r.chemin, r.params, r.corps) for r in faux.requetes]

    assert suite() == suite()


def test_limiteur_appele_avant_chaque_requete(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client = fabrique_client(faux)
    site = preparer_site(client, config, plan.valeurs_libres)
    avant = len(faux.requetes)
    compteur = Compteur()
    injecter(client, plan, site, config, lambda: HORLOGE, compteur)
    assert compteur.appels == len(faux.requetes) - avant


def test_projet_non_vide_refuse(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    _injecter(faux, fabrique_client, config, plan)
    client = fabrique_client(faux)
    site = preparer_site(client, config, plan.valeurs_libres)
    faux.requetes.clear()
    with pytest.raises(UsineErreur, match=r"Story 1.7") as erreur:
        injecter(client, plan, site, config, lambda: HORLOGE, Compteur())
    assert not isinstance(erreur.value, InjectionInterrompue)
    assert [r.chemin for r in faux.requetes] == [f"{API}/search/approximate-count"]


def test_reprise_sur_429(
    fabrique_client: FabriqueClient,
    config: ConfigJira,
    plan: PlanInjection,
    attentes: Attentes,
) -> None:
    faux = FauxJira()
    creations = 0

    def limiter_le_debit(requete: Requete) -> httpx.Response | None:
        nonlocal creations
        if requete.methode == "POST" and requete.chemin == f"{API}/issue":
            creations += 1
            if creations == 3:
                return httpx.Response(429, headers={"Retry-After": "7"})
        return None

    faux.avant = limiter_le_debit
    _, manifeste = _injecter(faux, fabrique_client, config, plan)
    assert attentes.durees == [7.0]
    assert len(manifeste.correspondance_cles) == len(plan.tickets)
    assert len(faux.tickets) == len(plan.tickets)


def test_echec_a_mi_parcours(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client = fabrique_client(faux)
    site = preparer_site(client, config, plan.valeurs_libres)
    creations = 0

    def echouer(requete: Requete) -> httpx.Response | None:
        nonlocal creations
        if requete.methode == "POST" and requete.chemin == f"{API}/issue":
            creations += 1
            if creations == 5:
                return httpx.Response(500, json={"errorMessages": ["secret-du-corps"]})
        return None

    faux.avant = echouer
    with pytest.raises(InjectionInterrompue) as erreur:
        injecter(client, plan, site, config, lambda: HORLOGE, Compteur())
    etat = erreur.value.etat
    assert len(etat.tickets_crees) == 4
    assert dict(etat.correspondance_cles) == {
        t.cle: cle for t, cle in zip(plan.tickets, etat.tickets_crees, strict=False)
    }
    assert "500" in etat.derniere_erreur
    assert "secret-du-corps" not in str(erreur.value)
    assert "4 ticket(s) créé(s)" in str(erreur.value)
    contenu = etat.vers_json()
    assert contenu["tickets_crees"] == list(etat.tickets_crees)
    assert contenu["debut_injection"] == HORLOGE.isoformat()


def test_server_time_illisible_interrompt(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()

    def heure_illisible(requete: Requete) -> httpx.Response | None:
        if requete.chemin == f"{API}/serverInfo":
            return httpx.Response(200, json={"serverTime": "demain"})
        return None

    faux.avant = heure_illisible
    with pytest.raises(InjectionInterrompue, match="serverTime illisible") as erreur:
        _injecter(faux, fabrique_client, config, plan)
    assert len(erreur.value.etat.correspondance_cles) == len(plan.tickets)


def test_erreur_inattendue_a_mi_parcours_garde_l_etat_partiel(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client = fabrique_client(faux)
    site = preparer_site(client, config, plan.valeurs_libres)
    creations = 0

    def planter(requete: Requete) -> httpx.Response | None:
        nonlocal creations
        if requete.methode == "POST" and requete.chemin == f"{API}/issue":
            creations += 1
            if creations == 3:
                raise KeyError("panne inattendue")
        return None

    faux.avant = planter
    with pytest.raises(InjectionInterrompue) as erreur:
        injecter(client, plan, site, config, lambda: HORLOGE, Compteur())
    assert isinstance(erreur.value.__cause__, KeyError)
    etat = erreur.value.etat
    assert len(etat.tickets_crees) == 2
    assert list(etat.correspondance_cles) == [t.cle for t in plan.tickets[:2]]
    assert "panne inattendue" in etat.derniere_erreur
