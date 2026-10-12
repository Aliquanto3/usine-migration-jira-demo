"""Préparation du site Jira Cloud : types, champs, workflow H-17, schémas, écran, projet (FR-5).

Cœur sans réseau propre : le client arrive par le `Protocol` `ClientJira`. Chaque objet est
d'abord cherché par nom (par clé pour le projet) ; un objet trouvé n'est ni modifié ni recréé,
rien n'est supprimé, aucun autre projet n'est touché. Seules les options manquantes des listes
de sélection sont ajoutées. Le contrôle final par `createmeta` vérifie que chaque type et
chaque champ est créable dans le projet : un projet existant mal configuré est refusé avant
tout ticket. Requêtes et noms reprennent le spike de la Story 1.6 (site réel, 2026-10-12).
"""

import uuid
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol

from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.tickets import (
    CHAMPS_PAR_TYPE,
    DOMAINES_CANONIQUES,
    Champ,
    StatutAnomalie,
    TypeTicket,
)
from usine.generateur.injecteur.plan import (
    CHAMPS_SELECTION,
    CHAMPS_STANDARD,
    STATUT_INITIAL,
    TRANSITIONS_H17,
    noms_jira,
)

API = "/rest/api/3"
"""Préfixe des chemins de l'API REST Jira Cloud."""

DESCRIPTION = "Programme fictif de la démo (usine de migration, données entièrement fictives)."
"""Description de chaque objet créé."""

NOM_WORKFLOW = "DEMO : workflow des Anomalies"
NOM_SCHEMA_WORKFLOW = "DEMO : schéma de workflow"
NOM_SCHEMA_TYPES = "DEMO : types de tickets"
NOM_ECRAN = "DEMO : écran des tickets"
NOM_ONGLET = "Général"
NOM_SCHEMA_ECRANS = "DEMO : schéma d'écrans"
NOM_ECRANS_PAR_TYPE = "DEMO : écrans par type"
NOM_PROJET = "DEMO - Banque Exemple, migration SI cœur"

TYPE_CHAMP = "com.atlassian.jira.plugin.system.customfieldtypes:select"
CHERCHEUR_CHAMP = "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher"

DESCRIPTIONS_TYPES: Mapping[TypeTicket, str] = MappingProxyType(
    {
        TypeTicket.anomalie: "Anomalie de migration (Programme fictif de la démo).",
        TypeTicket.cas_de_test: "Cas de test d'une Entité (Programme fictif de la démo).",
        TypeTicket.certification: "Certification d'une Entité (Programme fictif de la démo).",
    }
)

TAILLE_PAGE = 50
"""Taille de page demandée aux recherches paginées par position."""


class ClientJira(Protocol):
    """Client REST Jira reçu de la composition : rend l'objet ou le tableau JSON."""

    def requete(
        self,
        methode: str,
        chemin: str,
        *,
        params: Mapping[str, Any] | None = None,
        corps: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def requete_liste(
        self,
        methode: str,
        chemin: str,
        *,
        params: Mapping[str, Any] | None = None,
        corps: Mapping[str, Any] | None = None,
    ) -> list[Any]: ...


@dataclass(frozen=True)
class SiteDemo:
    """Identifiants Jira du site préparé, et objets créés par cette préparation."""

    url_site: str
    cle_projet: str
    id_projet: str
    types: Mapping[TypeTicket, str]
    """Identifiant Jira de chaque type canonique."""
    noms_types: Mapping[TypeTicket, str]
    """Nom Jira de chaque type canonique."""
    champs: Mapping[Champ, str]
    """Identifiant Jira de chaque liste de sélection (`customfield_…`)."""
    crees: tuple[str, ...] = field(default=())
    """Objets créés par la préparation (« type Anomalie », « option Entité=ENT-A »…)."""

    def vers_json(self) -> dict[str, Any]:
        """Contenu de `site_jira.json` : identifiants réels, `champs` prêts pour la config."""
        champs = {c.value: i for c, i in (*CHAMPS_STANDARD.items(), *self.champs.items())}
        return {
            "url_site": self.url_site,
            "cle_projet": self.cle_projet,
            "id_projet": self.id_projet,
            "types_tickets": {self.noms_types[t]: self.types[t] for t in TypeTicket},
            "champs": {c.value: champs[c.value] for c in Champ},
            "workflow_anomalies": NOM_WORKFLOW,
        }


def _identifiant(valeur: object, contexte: str) -> str:
    """Identifiant Jira (entier ou texte) en texte ; absent : `UsineErreur`."""
    if isinstance(valeur, int) and not isinstance(valeur, bool):
        return str(valeur)
    if isinstance(valeur, str) and valeur:
        return valeur
    raise UsineErreur(f"{contexte} : réponse Jira sans identifiant")


def _pages(
    client: ClientJira,
    chemin: str,
    cle: str,
    params: Mapping[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Éléments de `cle` sur toutes les pages `startAt`/`maxResults` d'un GET.

    Arrêt sur `isLast: true`, sur `startAt ≥ total`, sur une page vide, ou sur une réponse
    qui n'annonce ni `isLast` ni `total` (non paginée).
    """
    debut = 0
    while True:
        page = client.requete(
            "GET", chemin, params={**(params or {}), "startAt": debut, "maxResults": TAILLE_PAGE}
        )
        elements = page.get(cle)
        if not isinstance(elements, list):
            raise UsineErreur(f"Jira GET {chemin} : réponse sans liste {cle!r}")
        yield from (e for e in elements if isinstance(e, dict))
        if not elements or page.get("isLast") is True:
            return
        debut += len(elements)
        total = page.get("total")
        if isinstance(total, int) and not isinstance(total, bool):
            if debut >= total:
                return
        elif page.get("isLast") is not False:
            return


def _entier(identifiant: str, contexte: str) -> int:
    """Identifiant numérique attendu par Jira dans un corps (`issueTypeScheme`…)."""
    if not (identifiant.isascii() and identifiant.isdigit()):
        raise UsineErreur(f"{contexte} : identifiant Jira non numérique {identifiant!r}")
    return int(identifiant)


def _par_nom(elements: Iterator[dict[str, Any]], nom: str, quoi: str) -> dict[str, Any] | None:
    """Unique élément de nom exact `nom` ; plusieurs : `UsineErreur` (ambiguïté)."""
    trouves = [e for e in elements if e.get("name") == nom]
    if len(trouves) > 1:
        raise UsineErreur(f"Jira : {len(trouves)} {quoi} nommés « {nom} » : ambiguïté")
    return trouves[0] if trouves else None


class _Preparation:
    """État d'une préparation : client, configuration et journal des créations."""

    def __init__(self, client: ClientJira, config: ConfigJira) -> None:
        self.client = client
        self.config = config
        self.crees: list[str] = []
        self.noms = noms_jira(config)

    def creer(self, quoi: str, chemin: str, corps: Mapping[str, Any]) -> dict[str, Any]:
        reponse = self.client.requete("POST", chemin, corps=corps)
        self.crees.append(quoi)
        return reponse

    # --- Types de tickets ---

    def types(self) -> tuple[dict[TypeTicket, str], dict[TypeTicket, str]]:
        noms: dict[TypeTicket, str] = {}
        for nom, canonique in self.config.types_tickets.items():
            noms.setdefault(canonique, nom)
        existants: dict[str, list[str]] = {}
        for element in self.client.requete_liste("GET", f"{API}/issuetype"):
            if isinstance(element, dict) and "scope" not in element:
                existants.setdefault(str(element.get("name")), []).append(
                    _identifiant(element.get("id"), "Jira GET /issuetype")
                )
        identifiants: dict[TypeTicket, str] = {}
        for type_ticket in TypeTicket:
            nom = noms[type_ticket]
            trouves = existants.get(nom, [])
            if len(trouves) > 1:
                raise UsineErreur(f"Jira : {len(trouves)} types de tickets nommés « {nom} »")
            if trouves:
                identifiants[type_ticket] = trouves[0]
                continue
            cree = self.creer(
                f"type {nom}",
                f"{API}/issuetype",
                {"name": nom, "description": DESCRIPTIONS_TYPES[type_ticket], "type": "standard"},
            )
            identifiants[type_ticket] = _identifiant(cree.get("id"), f"type {nom}")
        return identifiants, noms

    # --- Champs et options ---

    def champ(self, champ: Champ, valeurs_libres: Mapping[Champ, Sequence[str]]) -> str:
        nom = CHAMPS_SELECTION[champ]
        trouve = _par_nom(
            _pages(self.client, f"{API}/field/search", "values", {"type": "custom", "query": nom}),
            nom,
            "champs",
        )
        if trouve is not None:
            identifiant = _identifiant(trouve.get("id"), f"champ {nom}")
        else:
            cree = self.creer(
                f"champ {nom}",
                f"{API}/field",
                {
                    "name": nom,
                    "description": DESCRIPTION,
                    "type": TYPE_CHAMP,
                    "searcherKey": CHERCHEUR_CHAMP,
                },
            )
            identifiant = _identifiant(cree.get("id"), f"champ {nom}")
        if DOMAINES_CANONIQUES[champ] is None:
            voulues = list(valeurs_libres.get(champ, ()))
        else:
            voulues = list(self.config.valeurs[champ])
        self.options(nom, identifiant, voulues)
        return identifiant

    def options(self, nom: str, identifiant: str, voulues: Sequence[str]) -> None:
        contextes = list(_pages(self.client, f"{API}/field/{identifiant}/context", "values"))
        if not contextes:
            raise UsineErreur(f"Jira : champ « {nom} » ({identifiant}) sans contexte")
        globaux = [c for c in contextes if c.get("isGlobalContext") is True]
        contexte = _identifiant((globaux or contextes)[0].get("id"), f"contexte du champ {nom}")
        chemin = f"{API}/field/{identifiant}/context/{contexte}/option"
        existantes = {o.get("value") for o in _pages(self.client, chemin, "values")}
        manquantes = list(dict.fromkeys(v for v in voulues if v not in existantes))
        if manquantes:
            self.client.requete(
                "POST",
                chemin,
                corps={"options": [{"value": v, "disabled": False} for v in manquantes]},
            )
            self.crees.extend(f"option {nom}={v}" for v in manquantes)

    # --- Workflow H-17 ---

    def workflow(self) -> None:
        trouve = _par_nom(
            _pages(self.client, f"{API}/workflows/search", "values", {"queryString": NOM_WORKFLOW}),
            NOM_WORKFLOW,
            "workflows",
        )
        if trouve is not None:
            return
        statuts_existants: dict[str, str] = {}
        for statut in _pages(self.client, f"{API}/statuses/search", "values"):
            statuts_existants.setdefault(
                str(statut.get("name")), _identifiant(statut.get("id"), "statut Jira")
            )
        noms = self.noms[Champ.statut]
        reference = {
            s: str(uuid.uuid5(uuid.NAMESPACE_URL, f"usine-demo:statut:{noms[s]}"))
            for s in StatutAnomalie
        }
        statuts: list[dict[str, Any]] = []
        for s in StatutAnomalie:
            description: dict[str, Any] = {
                "statusReference": reference[s],
                "name": noms[s],
                "statusCategory": _categorie(s),
            }
            if noms[s] in statuts_existants:
                description["id"] = statuts_existants[noms[s]]
            statuts.append(description)
        transitions: list[dict[str, Any]] = [
            {
                "id": "1",
                "name": "Créer",
                "type": "INITIAL",
                "toStatusReference": reference[STATUT_INITIAL],
                "links": [],
            }
        ]
        for rang, (de, vers) in enumerate(TRANSITIONS_H17, start=1):
            transitions.append(
                {
                    "id": str(10 * rang + 1),
                    "name": noms[vers],
                    "type": "DIRECTED",
                    "toStatusReference": reference[vers],
                    "links": [{"fromStatusReference": reference[de]}],
                }
            )
        self.creer(
            f"workflow {NOM_WORKFLOW}",
            f"{API}/workflows/create",
            {
                "scope": {"type": "GLOBAL"},
                "statuses": statuts,
                "workflows": [
                    {
                        "name": NOM_WORKFLOW,
                        "description": "Workflow fictif des Anomalies (hypothèse H-17).",
                        "statuses": [
                            {"statusReference": reference[s], "properties": {}}
                            for s in StatutAnomalie
                        ],
                        "transitions": transitions,
                    }
                ],
            },
        )

    # --- Schémas, écran, projet ---

    def schema(
        self,
        chemin: str,
        nom: str,
        quoi: str,
        corps: Mapping[str, Any],
        cle_id: str = "id",
        params: Mapping[str, Any] | None = None,
    ) -> str:
        trouve = _par_nom(_pages(self.client, f"{API}{chemin}", "values", params), nom, quoi)
        if trouve is not None:
            return _identifiant(trouve.get("id"), f"{quoi} {nom}")
        cree = self.creer(f"{quoi} {nom}", f"{API}{chemin}", {"name": nom, **corps})
        return _identifiant(cree.get(cle_id), f"{quoi} {nom}")

    def ecran(self, champs: Mapping[Champ, str]) -> str:
        trouve = _par_nom(
            _pages(self.client, f"{API}/screens", "values", {"queryString": NOM_ECRAN}),
            NOM_ECRAN,
            "écrans",
        )
        if trouve is not None:
            # Écran existant : jamais modifié ; `createmeta` dira s'il lui manque un champ.
            return _identifiant(trouve.get("id"), f"écran {NOM_ECRAN}")
        cree = self.creer(
            f"écran {NOM_ECRAN}",
            f"{API}/screens",
            {"name": NOM_ECRAN, "description": DESCRIPTION},
        )
        ecran = _identifiant(cree.get("id"), f"écran {NOM_ECRAN}")
        onglets = self.client.requete_liste("GET", f"{API}/screens/{ecran}/tabs")
        if onglets and isinstance(onglets[0], dict):
            onglet = _identifiant(onglets[0].get("id"), f"onglet de l'écran {NOM_ECRAN}")
        else:
            reponse = self.creer(
                f"onglet {NOM_ONGLET}", f"{API}/screens/{ecran}/tabs", {"name": NOM_ONGLET}
            )
            onglet = _identifiant(reponse.get("id"), f"onglet {NOM_ONGLET}")
        chemin = f"{API}/screens/{ecran}/tabs/{onglet}/fields"
        presents = {
            f.get("id") for f in self.client.requete_liste("GET", chemin) if isinstance(f, dict)
        }
        for identifiant in ("summary", "description", "issuetype", *champs.values()):
            if identifiant not in presents:
                self.client.requete("POST", chemin, corps={"fieldId": identifiant})
        return ecran

    def projet(self, schemas: Mapping[str, str]) -> str:
        cle = self.config.cle_projet
        page = self.client.requete("GET", f"{API}/project/search", params={"keys": cle})
        valeurs = page.get("values")
        if not isinstance(valeurs, list):
            raise UsineErreur(f"Jira GET {API}/project/search : réponse sans liste 'values'")
        for projet in valeurs:
            if isinstance(projet, dict) and projet.get("key") == cle:
                return _identifiant(projet.get("id"), f"projet {cle}")
        moi = self.client.requete("GET", f"{API}/myself").get("accountId")
        if not isinstance(moi, str) or not moi:
            raise UsineErreur(f"Jira GET {API}/myself : réponse sans accountId")
        cree = self.creer(
            f"projet {cle}",
            f"{API}/project",
            {
                "key": cle,
                "name": NOM_PROJET,
                "description": DESCRIPTION,
                "projectTypeKey": "software",
                "leadAccountId": moi,
                "assigneeType": "UNASSIGNED",
                "issueTypeScheme": _entier(schemas["types"], "schéma de types"),
                "issueTypeScreenScheme": _entier(
                    schemas["ecrans_par_type"], "schéma d'écrans par type"
                ),
                "workflowScheme": _entier(schemas["workflow"], "schéma de workflow"),
            },
        )
        return _identifiant(cree.get("id"), f"projet {cle}")

    # --- Contrôle ---

    def controler(
        self,
        types: Mapping[TypeTicket, str],
        noms: Mapping[TypeTicket, str],
        champs: Mapping[Champ, str],
    ) -> None:
        cle = self.config.cle_projet
        chemin = f"{API}/issue/createmeta/{cle}/issuetypes"
        creables = {
            _identifiant(t.get("id"), f"Jira GET {chemin}")
            for t in _pages(self.client, chemin, "issueTypes")
        }
        for type_ticket in TypeTicket:
            if types[type_ticket] not in creables:
                raise UsineErreur(
                    f"Jira : projet {cle} : type « {noms[type_ticket]} » non créable (absent du"
                    " schéma de types du projet) ; aucun ticket créé"
                )
        for type_ticket in TypeTicket:
            chemin_type = f"{chemin}/{types[type_ticket]}"
            presents = {f.get("fieldId") for f in _pages(self.client, chemin_type, "fields")}
            attendus = {"summary": "Résumé", "description": "Description"}
            attendus.update(
                {
                    champs[c]: n
                    for c, n in CHAMPS_SELECTION.items()
                    if c in CHAMPS_PAR_TYPE[type_ticket]
                }
            )
            absents = [nom for identifiant, nom in attendus.items() if identifiant not in presents]
            if absents:
                raise UsineErreur(
                    f"Jira : projet {cle} : type « {noms[type_ticket]} » : champ(s) absent(s) de"
                    f" l'écran de création : {', '.join(absents)} ; aucun ticket créé"
                )


def _categorie(statut: StatutAnomalie) -> str:
    if statut is STATUT_INITIAL:
        return "TODO"
    if statut in (StatutAnomalie.fermee, StatutAnomalie.rejetee):
        return "DONE"
    return "IN_PROGRESS"


def preparer_site(
    client: ClientJira, config: ConfigJira, valeurs_libres: Mapping[Champ, Sequence[str]]
) -> SiteDemo:
    """Prépare le site de `config` et rend ses identifiants ; idempotent par nom.

    `valeurs_libres` donne les options voulues des listes à valeur libre (Entité, Vague,
    Domaine) ; celles des domaines fermés sont les noms Jira de `config.valeurs`.
    """
    preparation = _Preparation(client, config)
    types, noms = preparation.types()
    champs = {champ: preparation.champ(champ, valeurs_libres) for champ in CHAMPS_SELECTION}
    preparation.workflow()
    schemas = {
        "workflow": preparation.schema(
            "/workflowscheme",
            NOM_SCHEMA_WORKFLOW,
            "schéma de workflow",
            {
                "description": DESCRIPTION,
                "defaultWorkflow": "jira",
                "issueTypeMappings": {types[TypeTicket.anomalie]: NOM_WORKFLOW},
            },
        ),
        "types": preparation.schema(
            "/issuetypescheme",
            NOM_SCHEMA_TYPES,
            "schéma de types",
            {
                "description": DESCRIPTION,
                "defaultIssueTypeId": types[TypeTicket.anomalie],
                "issueTypeIds": [types[t] for t in TypeTicket],
            },
            cle_id="issueTypeSchemeId",
        ),
    }
    ecran = preparation.ecran(champs)
    schema_ecrans = preparation.schema(
        "/screenscheme",
        NOM_SCHEMA_ECRANS,
        "schéma d'écrans",
        {"description": DESCRIPTION, "screens": {"default": _entier(ecran, NOM_ECRAN)}},
    )
    schemas["ecrans_par_type"] = preparation.schema(
        "/issuetypescreenscheme",
        NOM_ECRANS_PAR_TYPE,
        "schéma d'écrans par type",
        {
            "description": DESCRIPTION,
            "issueTypeMappings": [{"issueTypeId": "default", "screenSchemeId": schema_ecrans}],
        },
    )
    id_projet = preparation.projet(schemas)
    preparation.controler(types, noms, champs)
    return SiteDemo(
        url_site=config.url_site,
        cle_projet=config.cle_projet,
        id_projet=id_projet,
        types=MappingProxyType(types),
        noms_types=MappingProxyType(noms),
        champs=MappingProxyType(champs),
        crees=tuple(preparation.crees),
    )
