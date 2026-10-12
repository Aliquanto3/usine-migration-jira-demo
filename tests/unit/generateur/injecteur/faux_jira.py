"""Faux Jira Cloud en mémoire, branché par `httpx.MockTransport` : aucun réseau.

Il reproduit les points d'accès REST v3 du spike de la Story 1.6, avec un état : types,
champs et options, statuts, workflows, schémas, écrans, projets, tickets et transitions.
Les recherches sont paginées par petites pages, pour exercer la pagination. Il refuse, comme
Jira, un champ absent de l'écran de création ou une option inconnue. Chaque requête est
journalisée ; `avant` permet à un test d'injecter une réponse (429, 500…).
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs

import httpx

API = "/rest/api/3"
WORKFLOW_DEFAUT = "jira"
STATUTS_DEFAUT = ("À faire", "En cours", "Terminé")
SERVER_TIME = "2099-01-01T12:00:00.000+0100"
"""Heure du serveur, volontairement en avance sur l'horloge locale des tests."""


@dataclass
class Requete:
    """Requête reçue : méthode, chemin, paramètres et corps JSON."""

    methode: str
    chemin: str
    params: dict[str, str]
    corps: Any


@dataclass
class Ticket:
    """Ticket stocké par le faux Jira."""

    id: str
    cle: str
    projet: str
    type_id: str
    champs: dict[str, Any]
    statut: str


@dataclass
class FauxJira:
    """État d'un site Jira Cloud simulé."""

    taille_page: int = 2
    premier_numero: int = 1
    """Numéro de la première clé de ticket d'un projet (numérotation décalée : plus de 1)."""
    types: list[dict[str, Any]] = field(default_factory=list)
    champs: dict[str, dict[str, Any]] = field(default_factory=dict)
    contextes: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    options: dict[str, list[str]] = field(default_factory=dict)
    statuts: list[dict[str, Any]] = field(default_factory=list)
    workflows: dict[str, dict[str, Any]] = field(default_factory=dict)
    schemas_workflow: list[dict[str, Any]] = field(default_factory=list)
    schemas_types: list[dict[str, Any]] = field(default_factory=list)
    ecrans: list[dict[str, Any]] = field(default_factory=list)
    onglets: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    champs_onglet: dict[str, list[str]] = field(default_factory=dict)
    schemas_ecrans: list[dict[str, Any]] = field(default_factory=list)
    ecrans_par_type: list[dict[str, Any]] = field(default_factory=list)
    projets: list[dict[str, Any]] = field(default_factory=list)
    tickets: dict[str, Ticket] = field(default_factory=dict)
    requetes: list[Requete] = field(default_factory=list)
    avant: Callable[[Requete], httpx.Response | None] | None = None
    premier_id: int = 20000
    """Base des identifiants attribués (un autre site : une autre base)."""
    _suivant: int = 0

    def __post_init__(self) -> None:
        self._suivant = self.premier_id
        self.types.append({"id": "10001", "name": "Tâche"})
        self.types.append({"id": "10002", "name": "Anomalie", "scope": {"type": "PROJECT"}})
        for nom in STATUTS_DEFAUT:
            self.statuts.append({"id": self._id(), "name": nom})
        self.statuts.append({"id": self._id(), "name": "Fermée"})  # statut réutilisé par nom
        self.projets.append({"id": "10000", "key": "KAN", "name": "Projet KAN"})

    def _id(self) -> str:
        self._suivant += 1
        return str(self._suivant)

    @property
    def transport(self) -> httpx.MockTransport:
        """Transport httpx à passer au client d'écriture."""
        return httpx.MockTransport(self)

    # --- Aiguillage ---

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        params = {k: v[-1] for k, v in parse_qs(requete.url.query.decode()).items()}
        corps = json.loads(requete.content) if requete.content else None
        recue = Requete(requete.method, requete.url.path, params, corps)
        self.requetes.append(recue)
        if self.avant is not None:
            reponse = self.avant(recue)
            if reponse is not None:
                return reponse
        chemin = requete.url.path.removeprefix(API)
        for methode, motif, gestionnaire in self._routes():
            correspondance = re.fullmatch(motif, chemin)
            if methode == requete.method and correspondance:
                return gestionnaire(recue, *correspondance.groups())
        return httpx.Response(404, json={"errorMessages": [f"inconnu : {chemin}"]})

    def _routes(self) -> list[tuple[str, str, Callable[..., httpx.Response]]]:
        return [
            ("GET", r"/issuetype", self._get_types),
            ("POST", r"/issuetype", self._post_type),
            ("GET", r"/field/search", self._get_champs),
            ("POST", r"/field", self._post_champ),
            ("GET", r"/field/([^/]+)/context", self._get_contextes),
            ("GET", r"/field/([^/]+)/context/([^/]+)/option", self._get_options),
            ("POST", r"/field/([^/]+)/context/([^/]+)/option", self._post_options),
            ("GET", r"/workflows/search", self._get_workflows),
            ("GET", r"/statuses/search", self._get_statuts),
            ("POST", r"/workflows/create", self._post_workflow),
            ("GET", r"/workflowscheme", self._lister(self.schemas_workflow)),
            ("POST", r"/workflowscheme", self._post_schema_workflow),
            ("GET", r"/issuetypescheme", self._lister(self.schemas_types)),
            ("POST", r"/issuetypescheme", self._post_schema_types),
            ("GET", r"/screens", self._get_ecrans),
            ("POST", r"/screens", self._post_ecran),
            ("GET", r"/screens/(\d+)/tabs", self._get_onglets),
            ("POST", r"/screens/(\d+)/tabs", self._post_onglet),
            ("GET", r"/screens/(\d+)/tabs/(\d+)/fields", self._get_champs_onglet),
            ("POST", r"/screens/(\d+)/tabs/(\d+)/fields", self._post_champ_onglet),
            ("GET", r"/screenscheme", self._lister(self.schemas_ecrans)),
            ("POST", r"/screenscheme", self._post_schema_ecrans),
            ("GET", r"/issuetypescreenscheme", self._lister(self.ecrans_par_type)),
            ("POST", r"/issuetypescreenscheme", self._post_ecrans_par_type),
            ("GET", r"/project/search", self._get_projets),
            ("GET", r"/myself", lambda r: httpx.Response(200, json={"accountId": "compte-1"})),
            ("POST", r"/project", self._post_projet),
            ("GET", r"/issue/createmeta/([A-Z0-9]+)/issuetypes", self._get_meta_types),
            ("GET", r"/issue/createmeta/([A-Z0-9]+)/issuetypes/(\d+)", self._get_meta_champs),
            ("POST", r"/search/jql", self._post_recherche),
            ("POST", r"/issue", self._post_ticket),
            ("GET", r"/issue/([A-Z0-9]+-\d+)/transitions", self._get_transitions),
            ("POST", r"/issue/([A-Z0-9]+-\d+)/transitions", self._post_transition),
            (
                "GET",
                r"/serverInfo",
                lambda r: httpx.Response(200, json={"serverTime": SERVER_TIME}),
            ),
        ]

    def _page(self, requete: Requete, elements: list[Any], cle: str = "values") -> httpx.Response:
        debut = int(requete.params.get("startAt", "0"))
        taille = min(int(requete.params.get("maxResults", "50")), self.taille_page)
        page = elements[debut : debut + taille]
        return httpx.Response(
            200,
            json={
                "startAt": debut,
                "maxResults": taille,
                "total": len(elements),
                "isLast": debut + len(page) >= len(elements),
                cle: page,
            },
        )

    def _lister(self, elements: list[dict[str, Any]]) -> Callable[[Requete], httpx.Response]:
        return lambda requete: self._page(requete, elements)

    @staticmethod
    def _refus(message: str) -> httpx.Response:
        return httpx.Response(400, json={"errorMessages": [message]})

    # --- Types, champs, options ---

    def _get_types(self, requete: Requete) -> httpx.Response:
        return httpx.Response(200, json=self.types)

    def _post_type(self, requete: Requete) -> httpx.Response:
        nouveau = {"id": self._id(), "name": requete.corps["name"]}
        self.types.append(nouveau)
        return httpx.Response(201, json=nouveau)

    def _get_champs(self, requete: Requete) -> httpx.Response:
        assert requete.params.get("type") == "custom"
        motif = requete.params.get("query", "").lower()
        trouves = [c for c in self.champs.values() if motif in c["name"].lower()]
        return self._page(requete, trouves)

    def _post_champ(self, requete: Requete) -> httpx.Response:
        identifiant = f"customfield_{self._id()}"
        self.champs[identifiant] = {"id": identifiant, "name": requete.corps["name"]}
        contexte = self._id()
        self.contextes[identifiant] = [{"id": contexte, "isGlobalContext": True}]
        self.options[contexte] = []
        return httpx.Response(201, json=self.champs[identifiant])

    def _get_contextes(self, requete: Requete, champ: str) -> httpx.Response:
        return self._page(requete, self.contextes[champ])

    def _get_options(self, requete: Requete, champ: str, contexte: str) -> httpx.Response:
        valeurs = [{"id": str(i), "value": v} for i, v in enumerate(self.options[contexte])]
        return self._page(requete, valeurs)

    def _post_options(self, requete: Requete, champ: str, contexte: str) -> httpx.Response:
        for option in requete.corps["options"]:
            if option["value"] in self.options[contexte]:
                return self._refus(f"option en double : {option['value']}")
            self.options[contexte].append(option["value"])
        return httpx.Response(200, json={"options": requete.corps["options"]})

    def options_du_champ(self, nom: str) -> list[str]:
        """Options du contexte du champ `nom` (aide des tests)."""
        identifiant = next(i for i, c in self.champs.items() if c["name"] == nom)
        return self.options[self.contextes[identifiant][0]["id"]]

    # --- Statuts et workflows ---

    def _get_workflows(self, requete: Requete) -> httpx.Response:
        motif = requete.params.get("queryString", "")
        valeurs = [{"id": {"name": n}, "name": n} for n in self.workflows if motif in n]
        return self._page(requete, valeurs)

    def _get_statuts(self, requete: Requete) -> httpx.Response:
        return self._page(requete, self.statuts)

    def _post_workflow(self, requete: Requete) -> httpx.Response:
        corps = requete.corps
        assert corps["scope"] == {"type": "GLOBAL"}
        par_reference: dict[str, str] = {}
        for statut in corps["statuses"]:
            existants = {s["name"]: s["id"] for s in self.statuts}
            if "id" in statut:
                if existants.get(statut["name"]) != statut["id"]:
                    return self._refus(f"statut {statut['name']} : id incohérent")
            elif statut["name"] in existants:
                return self._refus(f"statut {statut['name']} déjà existant sans id")
            else:
                self.statuts.append({"id": self._id(), "name": statut["name"]})
            par_reference[statut["statusReference"]] = statut["name"]
        (workflow,) = corps["workflows"]
        transitions: list[tuple[str, str | None, str]] = []
        for transition in workflow["transitions"]:
            vers = par_reference[transition["toStatusReference"]]
            if transition["type"] == "INITIAL":
                transitions.append((transition["id"], None, vers))
            for lien in transition["links"]:
                transitions.append(
                    (transition["id"], par_reference[lien["fromStatusReference"]], vers)
                )
        self.workflows[workflow["name"]] = {"transitions": transitions}
        return httpx.Response(200, json={"workflows": [{"name": workflow["name"]}]})

    def _transitions(self, nom_workflow: str) -> list[tuple[str, str | None, str]]:
        if nom_workflow == WORKFLOW_DEFAUT:
            a_faire, en_cours, termine = STATUTS_DEFAUT
            return [("1", None, a_faire), ("11", a_faire, en_cours), ("21", en_cours, termine)]
        transitions: list[tuple[str, str | None, str]] = self.workflows[nom_workflow]["transitions"]
        return transitions

    # --- Schémas et écrans ---

    def _post_schema_workflow(self, requete: Requete) -> httpx.Response:
        for workflow in requete.corps["issueTypeMappings"].values():
            if workflow not in self.workflows:
                return self._refus(f"workflow inconnu : {workflow}")
        nouveau = {"id": int(self._id()), **requete.corps}
        self.schemas_workflow.append(nouveau)
        return httpx.Response(201, json=nouveau)

    def _post_schema_types(self, requete: Requete) -> httpx.Response:
        identifiant = self._id()
        self.schemas_types.append({"id": identifiant, **requete.corps})
        return httpx.Response(201, json={"issueTypeSchemeId": identifiant})

    def _get_ecrans(self, requete: Requete) -> httpx.Response:
        motif = requete.params.get("queryString", "")
        return self._page(requete, [e for e in self.ecrans if motif in e["name"]])

    def _post_ecran(self, requete: Requete) -> httpx.Response:
        nouveau = {"id": int(self._id()), "name": requete.corps["name"]}
        self.ecrans.append(nouveau)
        self.onglets[str(nouveau["id"])] = []
        return httpx.Response(201, json=nouveau)

    def _get_onglets(self, requete: Requete, ecran: str) -> httpx.Response:
        return httpx.Response(200, json=self.onglets[ecran])

    def _post_onglet(self, requete: Requete, ecran: str) -> httpx.Response:
        nouveau = {"id": int(self._id()), "name": requete.corps["name"]}
        self.onglets[ecran].append(nouveau)
        self.champs_onglet[str(nouveau["id"])] = []
        return httpx.Response(201, json=nouveau)

    def _get_champs_onglet(self, requete: Requete, ecran: str, onglet: str) -> httpx.Response:
        return httpx.Response(200, json=[{"id": c, "name": c} for c in self.champs_onglet[onglet]])

    def _post_champ_onglet(self, requete: Requete, ecran: str, onglet: str) -> httpx.Response:
        champ = requete.corps["fieldId"]
        if champ in self.champs_onglet[onglet]:
            return self._refus(f"champ déjà sur l'écran : {champ}")
        self.champs_onglet[onglet].append(champ)
        return httpx.Response(200, json={"id": champ, "name": champ})

    def _post_schema_ecrans(self, requete: Requete) -> httpx.Response:
        nouveau = {"id": int(self._id()), **requete.corps}
        self.schemas_ecrans.append(nouveau)
        return httpx.Response(201, json={"id": nouveau["id"]})

    def _post_ecrans_par_type(self, requete: Requete) -> httpx.Response:
        nouveau = {"id": self._id(), **requete.corps}
        self.ecrans_par_type.append(nouveau)
        return httpx.Response(201, json={"id": nouveau["id"]})

    # --- Projets et métadonnées de création ---

    def _get_projets(self, requete: Requete) -> httpx.Response:
        cles = requete.params.get("keys", "").split(",")
        valeurs = [p for p in self.projets if p["key"] in cles]
        return httpx.Response(200, json={"isLast": True, "total": len(valeurs), "values": valeurs})

    def _post_projet(self, requete: Requete) -> httpx.Response:
        corps = requete.corps
        if any(p["key"] == corps["key"] for p in self.projets):
            return self._refus("clé de projet déjà prise")
        for cle in ("issueTypeScheme", "issueTypeScreenScheme", "workflowScheme"):
            assert isinstance(corps[cle], int)
        nouveau = {"id": self._id(), **corps}
        self.projets.append(nouveau)
        return httpx.Response(201, json={"id": int(nouveau["id"]), "key": corps["key"]})

    def projet(self, cle: str) -> dict[str, Any]:
        """Projet de clé `cle`."""
        return next(p for p in self.projets if p["key"] == cle)

    def _types_du_projet(self, projet: dict[str, Any]) -> list[str]:
        schema = next(s for s in self.schemas_types if int(s["id"]) == projet["issueTypeScheme"])
        return list(schema["issueTypeIds"])

    def _champs_creables(self, projet: dict[str, Any]) -> set[str]:
        par_type = next(
            e for e in self.ecrans_par_type if int(e["id"]) == projet["issueTypeScreenScheme"]
        )
        (mapping,) = par_type["issueTypeMappings"]
        schema = next(s for s in self.schemas_ecrans if s["id"] == int(mapping["screenSchemeId"]))
        ecran = str(schema["screens"]["default"])
        champs = {"project", "issuetype"}
        for onglet in self.onglets[ecran]:
            champs.update(self.champs_onglet[str(onglet["id"])])
        return champs

    def _workflow_du_type(self, projet: dict[str, Any], type_id: str) -> str:
        schema = next(s for s in self.schemas_workflow if s["id"] == projet["workflowScheme"])
        nom: str = schema["issueTypeMappings"].get(type_id, schema["defaultWorkflow"])
        return nom

    def _get_meta_types(self, requete: Requete, cle: str) -> httpx.Response:
        types = [t for t in self.types if t["id"] in self._types_du_projet(self.projet(cle))]
        return self._page(requete, types, "issueTypes")

    def _get_meta_champs(self, requete: Requete, cle: str, type_id: str) -> httpx.Response:
        champs = sorted(self._champs_creables(self.projet(cle)))
        valeurs = [{"fieldId": c, "name": c, "required": c == "summary"} for c in champs]
        return self._page(requete, valeurs, "fields")

    # --- Tickets ---

    def _post_recherche(self, requete: Requete) -> httpx.Response:
        """`search/jql` : tickets du projet par numéro de clé, pages par `nextPageToken`."""
        corps = requete.corps
        cle = re.fullmatch(r'project = "([A-Z0-9]+)" ORDER BY key ASC', corps["jql"])
        assert cle, corps["jql"]
        assert set(corps["fields"]) == {"summary", "issuetype", "status"}
        tickets = sorted(
            (t for t in self.tickets.values() if t.projet == cle.group(1)),
            key=lambda t: int(t.cle.rpartition("-")[2]),
        )
        debut = int(corps.get("nextPageToken", "0"))
        taille = min(int(corps.get("maxResults", 50)), self.taille_page)
        page = tickets[debut : debut + taille]
        noms_types = {t["id"]: t["name"] for t in self.types}
        issues = [
            {
                "id": t.id,
                "key": t.cle,
                "fields": {
                    "summary": t.champs.get("summary"),
                    "issuetype": {"id": t.type_id, "name": noms_types.get(t.type_id)},
                    "status": {"id": "0", "name": t.statut},
                },
            }
            for t in page
        ]
        contenu: dict[str, Any] = {"issues": issues, "isLast": debut + taille >= len(tickets)}
        if not contenu["isLast"]:
            contenu["nextPageToken"] = str(debut + taille)
        return httpx.Response(200, json=contenu)

    def _post_ticket(self, requete: Requete) -> httpx.Response:
        champs = dict(requete.corps["fields"])
        projet = self.projet(champs.pop("project")["key"])
        type_id = champs.pop("issuetype")["id"]
        if type_id not in self._types_du_projet(projet):
            return self._refus(f"type {type_id} non créable")
        creables = self._champs_creables(projet)
        for identifiant, valeur in champs.items():
            if identifiant not in creables:
                return self._refus(f"champ {identifiant} absent de l'écran")
            if identifiant.startswith("customfield_"):
                contexte = self.contextes[identifiant][0]["id"]
                if valeur["value"] not in self.options[contexte]:
                    return self._refus(f"option inconnue {valeur['value']!r}")
        if not champs.get("summary"):
            return self._refus("summary requis")
        numero = self.premier_numero + sum(
            1 for t in self.tickets.values() if t.projet == projet["key"]
        )
        cle = f"{projet['key']}-{numero}"
        workflow = self._workflow_du_type(projet, type_id)
        initial = next(v for _, de, v in self._transitions(workflow) if de is None)
        identifiant_ticket = self._id()
        self.tickets[cle] = Ticket(identifiant_ticket, cle, projet["key"], type_id, champs, initial)
        return httpx.Response(201, json={"id": identifiant_ticket, "key": cle})

    def _transitions_du_ticket(self, cle: str) -> list[tuple[str, str | None, str]]:
        ticket = self.tickets[cle]
        workflow = self._workflow_du_type(self.projet(ticket.projet), ticket.type_id)
        return [t for t in self._transitions(workflow) if t[1] == ticket.statut]

    def _get_transitions(self, requete: Requete, cle: str) -> httpx.Response:
        transitions = [
            {"id": i, "name": vers, "to": {"id": "0", "name": vers}}
            for i, _, vers in self._transitions_du_ticket(cle)
        ]
        return httpx.Response(200, json={"transitions": transitions})

    def _post_transition(self, requete: Requete, cle: str) -> httpx.Response:
        identifiant = requete.corps["transition"]["id"]
        for i, _, vers in self._transitions_du_ticket(cle):
            if i == identifiant:
                self.tickets[cle].statut = vers
                return httpx.Response(204)
        return self._refus(f"transition {identifiant} indisponible pour {cle}")

    # --- Aides ---

    def ecritures(self) -> list[Requete]:
        """Requêtes d'écriture reçues (tout sauf GET et lectures POST)."""
        return [
            r for r in self.requetes if r.methode != "GET" and not r.chemin.endswith("/search/jql")
        ]

    def ecritures_tickets(self) -> list[Requete]:
        """Créations de tickets et transitions reçues."""
        return [
            r
            for r in self.ecritures()
            if r.chemin == f"{API}/issue" or r.chemin.endswith("/transitions")
        ]

    def ajouter_ticket(self, cle: str, type_id: str, resume: str, statut: str) -> None:
        """Ticket posé directement dans le projet de `cle` (ticket étranger, aide des tests)."""
        projet = cle.rpartition("-")[0]
        self.tickets[cle] = Ticket(self._id(), cle, projet, type_id, {"summary": resume}, statut)
