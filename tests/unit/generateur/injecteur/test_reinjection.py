"""Réinjection idempotente : liste exacte, rapprochement, reprise et clés stables (Story 1.7)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from tests.unit.generateur.injecteur.conftest import FabriqueClient
from tests.unit.generateur.injecteur.faux_jira import API, FauxJira, Requete
from tests.unit.generateur.injecteur.test_injection import HORLOGE, Compteur, _etat_jira
from usine.adaptateurs.journal import SourceJournal
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.tickets import Champ, StatutAnomalie, TypeTicket
from usine.generateur.injecteur.injection import (
    BilanInjection,
    EtatInjectionPartielle,
    EtatPrecedent,
    InjectionInterrompue,
    TicketExistant,
    injecter,
    lister_tickets,
    rapprocher,
)
from usine.generateur.injecteur.plan import STATUT_INITIAL, PlanInjection, chemin_statuts
from usine.generateur.injecteur.site import ClientJira, SiteDemo, preparer_site

PLUS_TARD = HORLOGE + timedelta(days=1)


def _preparer(
    faux: FauxJira, fabrique: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> tuple[ClientJira, SiteDemo]:
    client = fabrique(faux)
    return client, preparer_site(client, config, plan.valeurs_libres)


def _injecter(
    client: ClientJira,
    site: SiteDemo,
    config: ConfigJira,
    plan: PlanInjection,
    precedent: EtatPrecedent | None = None,
    horloge: datetime = HORLOGE,
) -> BilanInjection:
    return injecter(client, plan, site, config, lambda: horloge, Compteur(), precedent)


def _depuis_manifeste(bilan: BilanInjection) -> EtatPrecedent:
    manifeste = bilan.manifeste
    return EtatPrecedent(
        manifeste.debut_injection, manifeste.horodatage_fin_injection, manifeste.correspondance_cles
    )


def _depuis_partiel(etat: EtatInjectionPartielle) -> EtatPrecedent:
    return EtatPrecedent(etat.debut_injection, None, etat.correspondance_cles)


def _verifier_etat_final(
    faux: FauxJira, bilan: BilanInjection, site: SiteDemo, config: ConfigJira, plan: PlanInjection
) -> None:
    assert len(faux.tickets) == len(plan.tickets)
    assert list(bilan.manifeste.correspondance_cles) == [t.cle for t in plan.tickets]
    for ticket in plan.tickets:
        cle_jira = bilan.manifeste.correspondance_cles[ticket.cle]
        assert _etat_jira(faux, cle_jira, site, config) == dict(ticket.valeurs), ticket.cle


def _interrompre(
    faux: FauxJira,
    client: ClientJira,
    site: SiteDemo,
    config: ConfigJira,
    plan: PlanInjection,
    echec: "Echec",
    precedent: EtatPrecedent | None = None,
) -> EtatInjectionPartielle:
    faux.avant = echec
    with pytest.raises(InjectionInterrompue) as erreur:
        _injecter(client, site, config, plan, precedent)
    faux.avant = None
    return erreur.value.etat


class Echec:
    """Rend 500 à la `rang`-ième requête qui vérifie `filtre`, après l'avoir exécutée ou non."""

    def __init__(self, faux: FauxJira, filtre: str, rang: int, *, executer: bool = False) -> None:
        self.faux = faux
        self.filtre = filtre
        self.rang = rang
        self.executer = executer
        self.vues = 0

    def __call__(self, requete: Requete) -> httpx.Response | None:
        if requete.methode == "POST" and requete.chemin.endswith(self.filtre):
            self.vues += 1
            if self.vues == self.rang:
                if self.executer:  # écriture faite côté Jira, réponse perdue.
                    self.faux.avant = None
                    self.faux._post_ticket(requete)
                return httpx.Response(500, json={"errorMessages": ["panne"]})
        return None


def test_reinjection_complete_n_ecrit_rien(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    premier = _injecter(client, site, config, plan)
    statuts = {cle: t.statut for cle, t in faux.tickets.items()}
    faux.requetes.clear()
    second = _injecter(client, site, config, plan, _depuis_manifeste(premier), PLUS_TARD)
    assert faux.ecritures() == []
    assert not any(r.chemin.endswith("/serverInfo") for r in faux.requetes)
    assert second.manifeste == premier.manifeste
    assert second.crees == () and second.transitions == 0
    assert second.repris == tuple(premier.manifeste.correspondance_cles.values())
    assert {cle: t.statut for cle, t in faux.tickets.items()} == statuts


def test_reinjection_sans_etat_precedent_reprend_par_cle_generee(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    premier = _injecter(client, site, config, plan)
    faux.requetes.clear()
    second = _injecter(client, site, config, plan, None, PLUS_TARD)
    assert faux.ecritures_tickets() == []
    assert second.manifeste.correspondance_cles == premier.manifeste.correspondance_cles
    assert second.manifeste.debut_injection == PLUS_TARD  # sans précédent : nouveau début.


def test_reprise_apres_interruption_au_statut_intermediaire(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    # 6e transition : 2e transition de DEMO-2 (chemin de 4) ; DEMO-2 reste intermédiaire.
    etat = _interrompre(faux, client, site, config, plan, Echec(faux, "/transitions", 6))
    assert etat.tickets_crees == ("DEMO-1", "DEMO-2")
    assert faux.tickets["DEMO-2"].statut == "En analyse"
    faux.requetes.clear()
    bilan = _injecter(client, site, config, plan, _depuis_partiel(etat), PLUS_TARD)
    assert bilan.repris == ("DEMO-1", "DEMO-2")
    assert bilan.crees == tuple(f"DEMO-{n}" for n in range(3, len(plan.tickets) + 1))
    creations = [r for r in faux.requetes if r.chemin == f"{API}/issue"]
    assert len(creations) == len(plan.tickets) - 2
    assert not any(r.chemin == f"{API}/issue/DEMO-1/transitions" for r in faux.ecritures())
    assert bilan.manifeste.debut_injection == HORLOGE  # début d'origine conservé.
    _verifier_etat_final(faux, bilan, site, config, plan)


def test_ticket_cree_sans_cle_enregistree_repris(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    echec = Echec(faux, f"{API}/issue", 3, executer=True)
    faux.avant = echec
    with pytest.raises(InjectionInterrompue) as erreur:
        _injecter(client, site, config, plan)
    etat = erreur.value.etat
    assert "DEMO-3" in faux.tickets and "DEMO-3" not in etat.correspondance_cles
    bilan = _injecter(client, site, config, plan, _depuis_partiel(etat), PLUS_TARD)
    assert "DEMO-3" in bilan.repris
    _verifier_etat_final(faux, bilan, site, config, plan)


def test_numerotation_decalee(
    fabrique_client: FabriqueClient,
    config: ConfigJira,
    plan: PlanInjection,
    chemin_journal: Path,
) -> None:
    faux = FauxJira(premier_numero=4)
    client, site = _preparer(faux, fabrique_client, config, plan)
    # Interruption après 5 créations : DEMO-1 → DEMO-4 … DEMO-5 → DEMO-8.
    etat = _interrompre(faux, client, site, config, plan, Echec(faux, f"{API}/issue", 6))
    assert dict(etat.correspondance_cles) == {f"DEMO-{n}": f"DEMO-{n + 3}" for n in range(1, 6)}
    # Les 5 tickets connus sont repris sous leur clé réelle (DEMO-4 à DEMO-8). Les clés
    # Jira DEMO-6 à DEMO-8, revendiquées, ne sont pas prises pour les clés générées
    # DEMO-6 à DEMO-8 : ces tickets du Journal sont créés.
    bilan = _injecter(client, site, config, plan, _depuis_partiel(etat), PLUS_TARD)
    assert bilan.repris == tuple(f"DEMO-{n}" for n in range(4, 9))
    assert len(bilan.crees) == len(plan.tickets) - 5
    assert bilan.crees[0] == "DEMO-9"
    correspondance = bilan.manifeste.correspondance_cles
    assert correspondance["DEMO-1"] == "DEMO-4"
    assert list(correspondance.values()) == [
        f"DEMO-{n + 3}" for n in range(1, len(plan.tickets) + 1)
    ]
    _verifier_etat_final(faux, bilan, site, config, plan)
    relu = SourceJournal(chemin_journal, bilan.manifeste)
    assert {e.cle_ticket for e in relu.evenements()} == set(correspondance.values())


def test_ticket_etranger_refuse(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    premier = _injecter(client, site, config, plan)
    faux.ajouter_ticket("DEMO-99", site.types[TypeTicket.anomalie], "Intrus", "En analyse")
    faux.requetes.clear()
    with pytest.raises(UsineErreur, match="DEMO-99") as erreur:
        _injecter(client, site, config, plan, _depuis_manifeste(premier))
    assert not isinstance(erreur.value, InjectionInterrompue)
    assert faux.ecritures() == []


def test_ticket_d_identite_differente_refuse(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    premier = _injecter(client, site, config, plan)
    faux.tickets["DEMO-7"].champs["summary"] = "Autre résumé"
    faux.requetes.clear()
    with pytest.raises(UsineErreur, match="DEMO-7"):
        _injecter(client, site, config, plan, _depuis_manifeste(premier))
    assert faux.ecritures() == []
    # Espaces de bord ignorés.
    faux.tickets["DEMO-7"].champs["summary"] = f"  {plan.tickets[6].valeurs[Champ.titre]} "
    assert _injecter(client, site, config, plan, _depuis_manifeste(premier)).crees == ()


def test_ticket_de_type_different_refuse(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    _injecter(client, site, config, plan)
    faux.tickets["DEMO-1"].type_id = site.types[TypeTicket.certification]
    faux.requetes.clear()
    with pytest.raises(UsineErreur, match="DEMO-1 de type"):
        _injecter(client, site, config, plan)
    assert faux.ecritures() == []


def test_ticket_connu_absent_refuse(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    premier = _injecter(client, site, config, plan)
    del faux.tickets["DEMO-5"]
    faux.requetes.clear()
    with pytest.raises(UsineErreur, match=r"DEMO-5.*index de recherche"):
        _injecter(client, site, config, plan, _depuis_manifeste(premier))
    assert faux.ecritures() == []


def test_statut_cible_inaccessible_refuse(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    premier = _injecter(client, site, config, plan)
    nouvelle = next(t for t in plan.tickets if t.statut_final is StatutAnomalie.nouvelle)
    cle_jira = premier.manifeste.correspondance_cles[nouvelle.cle]
    faux.tickets[cle_jira].statut = "En analyse"
    faux.requetes.clear()
    with pytest.raises(UsineErreur, match=f"{cle_jira} : workflow H-17"):
        _injecter(client, site, config, plan, _depuis_manifeste(premier))
    assert faux.ecritures() == []


def test_statut_inconnu_refuse(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    premier = _injecter(client, site, config, plan)
    faux.tickets["DEMO-1"].statut = "Statut inconnu"
    faux.requetes.clear()
    with pytest.raises(UsineErreur, match="DEMO-1 au statut « Statut inconnu »"):
        _injecter(client, site, config, plan, _depuis_manifeste(premier))
    assert faux.ecritures() == []


def test_reprise_ramene_un_ticket_en_retard_a_son_statut(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    premier = _injecter(client, site, config, plan)
    fermee = next(t for t in plan.tickets if t.statut_final is StatutAnomalie.fermee)
    cle_jira = premier.manifeste.correspondance_cles[fermee.cle]
    faux.tickets[cle_jira].statut = "En analyse"
    faux.requetes.clear()
    bilan = _injecter(client, site, config, plan, _depuis_manifeste(premier), PLUS_TARD)
    assert bilan.transitions == len(
        chemin_statuts(StatutAnomalie.en_analyse, StatutAnomalie.fermee)
    )
    assert {r.chemin for r in faux.ecritures()} == {f"{API}/issue/{cle_jira}/transitions"}
    assert bilan.manifeste.horodatage_fin_injection >= premier.manifeste.horodatage_fin_injection
    _verifier_etat_final(faux, bilan, site, config, plan)


def test_interruption_de_la_reinjection_garde_toute_la_correspondance(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    premier = _interrompre(faux, client, site, config, plan, Echec(faux, f"{API}/issue", 5))
    assert len(premier.correspondance_cles) == 4
    second = _interrompre(
        faux, client, site, config, plan, Echec(faux, f"{API}/issue", 3), _depuis_partiel(premier)
    )
    assert second.tickets_repris == tuple(premier.correspondance_cles.values())
    assert second.tickets_crees == ("DEMO-5", "DEMO-6")
    assert list(second.correspondance_cles) == [t.cle for t in plan.tickets[:6]]
    assert second.debut_injection == HORLOGE
    assert second.url_site == site.url_site and second.id_projet == site.id_projet


def test_correspondance_precedente_hors_journal_refusee(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    _injecter(client, site, config, plan)  # projet non vide : l'état précédent compte.
    faux.requetes.clear()
    precedent = EtatPrecedent(HORLOGE, None, {"DEMO-999": "DEMO-1"})
    with pytest.raises(UsineErreur, match="DEMO-999"):
        _injecter(client, site, config, plan, precedent)
    precedent = EtatPrecedent(HORLOGE, None, {"DEMO-1": "DEMO-1", "DEMO-2": "DEMO-1"})
    with pytest.raises(UsineErreur, match="non injective"):
        _injecter(client, site, config, plan, precedent)
    assert faux.ecritures() == []


def test_lister_tickets_pagine_par_jeton(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira(taille_page=3)
    client, site = _preparer(faux, fabrique_client, config, plan)
    _injecter(client, site, config, plan)
    faux.requetes.clear()
    compteur = Compteur()
    tickets = lister_tickets(client, "DEMO", compteur)
    assert [t.cle for t in tickets] == [f"DEMO-{n}" for n in range(1, len(plan.tickets) + 1)]
    pages = [r for r in faux.requetes if r.chemin == f"{API}/search/jql"]
    assert len(pages) == compteur.appels == -(-len(plan.tickets) // 3)
    assert "nextPageToken" not in pages[0].corps
    assert pages[1].corps["nextPageToken"] == "3"
    assert pages[0].corps["maxResults"] == 100
    premier = tickets[0]
    assert premier.resume == plan.tickets[0].valeurs[Champ.titre]
    assert premier.id_type == site.types[plan.tickets[0].type_ticket]


def test_lister_tickets_refuse_un_jeton_qui_boucle(
    fabrique_client: FabriqueClient, config: ConfigJira
) -> None:
    faux = FauxJira()
    faux.avant = lambda r: httpx.Response(
        200, json={"issues": [], "isLast": False, "nextPageToken": "x"}
    )
    with pytest.raises(UsineErreur, match="deux fois"):
        lister_tickets(fabrique_client(faux), "DEMO", Compteur())


def test_lister_tickets_refuse_une_page_non_terminale_sans_jeton(
    fabrique_client: FabriqueClient,
) -> None:
    faux = FauxJira()
    faux.avant = lambda r: httpx.Response(200, json={"issues": [], "isLast": False})
    with pytest.raises(UsineErreur, match="page non terminale sans nextPageToken"):
        lister_tickets(fabrique_client(faux), "DEMO", Compteur())


def test_projet_vide_ignore_l_etat_precedent(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    client, site = _preparer(faux, fabrique_client, config, plan)
    premier = _injecter(client, site, config, plan)
    faux.tickets.clear()  # site recréé, même identifiant de projet, projet vide.
    bilan = _injecter(client, site, config, plan, _depuis_manifeste(premier), PLUS_TARD)
    assert bilan.repris == () and len(bilan.crees) == len(plan.tickets)
    assert bilan.manifeste.correspondance_cles == premier.manifeste.correspondance_cles
    assert bilan.manifeste.debut_injection == PLUS_TARD


def test_rapprocher_est_pur(config: ConfigJira, plan: PlanInjection) -> None:
    site = SiteDemo(
        url_site="https://exemple.invalid",
        cle_projet="DEMO",
        id_projet="1",
        types={
            TypeTicket.anomalie: "1",
            TypeTicket.cas_de_test: "2",
            TypeTicket.certification: "3",
        },
        noms_types={t: t.value for t in TypeTicket},
        champs={},
    )
    premier = plan.tickets[0]
    existants = [TicketExistant("DEMO-1", "1", premier.valeurs[Champ.titre], "En analyse")]
    rapprochement = rapprocher(plan, existants, site, config, None)
    assert [e.ticket.cle for e in rapprochement.repris] == ["DEMO-1"]
    assert rapprochement.repris[0].depart is StatutAnomalie.en_analyse
    assert len(rapprochement.a_creer) == len(plan.tickets) - 1
    assert rapprochement.a_creer[0].depart is STATUT_INITIAL


def test_etat_partiel_relu(plan: PlanInjection) -> None:
    etat = EtatInjectionPartielle(
        cle_projet="DEMO",
        date_injection=plan.date_injection,
        debut_injection=datetime(2026, 10, 12, 8, tzinfo=UTC),
        tickets_crees=("DEMO-2",),
        correspondance_cles={"DEMO-1": "DEMO-1", "DEMO-2": "DEMO-2"},
        derniere_erreur="panne",
        url_site="https://exemple.invalid",
        id_projet="10002",
        tickets_repris=("DEMO-1",),
    )
    assert EtatInjectionPartielle.depuis_json(etat.vers_json(), "e.json") == etat
    ancien = etat.vers_json()
    for cle in ("url_site", "id_projet", "tickets_repris"):
        del ancien[cle]
    relu = EtatInjectionPartielle.depuis_json(ancien, "e.json")
    assert relu.url_site is None and relu.id_projet is None and relu.tickets_repris == ()
    with pytest.raises(UsineErreur, match=r"e.json.*debut_injection"):
        EtatInjectionPartielle.depuis_json({**ancien, "debut_injection": "2026-10-12"}, "e.json")
    with pytest.raises(UsineErreur, match="correspondance_cles"):
        EtatInjectionPartielle.depuis_json({**ancien, "correspondance_cles": []}, "e.json")
    with pytest.raises(UsineErreur, match="objet JSON"):
        EtatInjectionPartielle.depuis_json([], "e.json")
