"""Conversion d'un ticket Jira et de son changelog en `Evenement` canoniques (AD-3, AD-23).

Fonctions pures, sans réseau : elles reçoivent les objets JSON de Jira et la table de
correspondance `ConfigJira` (`config/jira.yaml`), seule source des noms propres au site
(identifiants de champs, types et statuts). Le paramètre `source` les rend réutilisables par
l'adaptateur Data Center (Story 2.4).

Identifiants : `C-<id ticket>` (création), `C-<id ticket>-<champ>` (attribut initial),
`<id historique>-<rang item>` (rang 1 = premier item de l'historique, items ignorés compris).
"""

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, NatureEvenement, SourceEvenement
from usine.contrats.tickets import (
    CHAMPS_PAR_TYPE,
    DOMAINES_CANONIQUES,
    Champ,
    TypeTicket,
    rang_cle,
)

FICHIER_CONFIG = "config/jira.yaml"
"""Fichier de la table de correspondance, nommé dans les erreurs."""


def lire_horodatage(texte: object, contexte: str) -> datetime:
    """Instant Jira (`2026-09-01T09:00:00.000+0000`) ramené en UTC ; sans fuseau : erreur."""
    if not isinstance(texte, str):
        raise UsineErreur(f"{contexte} : horodatage absent ou illisible ({texte!r})")
    try:
        instant = datetime.fromisoformat(texte)
    except ValueError as exc:
        raise UsineErreur(f"{contexte} : horodatage illisible {texte!r}") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise UsineErreur(f"{contexte} : horodatage sans fuseau {texte!r}")
    return instant.astimezone(UTC)


def texte_adf(document: Mapping[str, Any], contexte: str) -> str:
    """Texte d'un document ADF : nœuds `text` concaténés, un paragraphe par ligne.

    Les blocs conteneurs (listes, citations, tableaux…) sont parcourus ; `hardBreak` devient
    un saut de ligne ; les autres feuilles sans texte (mention, emoji…) sont ignorées.
    """
    if document.get("type") != "doc" or not isinstance(document.get("content"), list):
        raise UsineErreur(f"{contexte} : document ADF de forme inconnue")
    lignes: list[str] = []
    for bloc in document["content"]:
        _blocs_adf(bloc, lignes, contexte)
    return "\n".join(lignes)


def _noeud_adf(noeud: object, contexte: str) -> Mapping[str, Any]:
    if not isinstance(noeud, Mapping) or not isinstance(noeud.get("type"), str):
        raise UsineErreur(f"{contexte} : nœud ADF de forme inconnue ({noeud!r})")
    contenu = noeud.get("content")
    if contenu is not None and not isinstance(contenu, list):
        raise UsineErreur(f"{contexte} : nœud ADF « {noeud['type']} » au contenu illisible")
    return noeud


def _blocs_adf(noeud: object, lignes: list[str], contexte: str) -> None:
    bloc = _noeud_adf(noeud, contexte)
    if bloc["type"] in {"paragraph", "heading", "codeBlock"}:
        lignes.append("".join(_texte_en_ligne(e, contexte) for e in bloc.get("content") or []))
        return
    if bloc["type"] == "text":
        raise UsineErreur(f"{contexte} : nœud ADF « text » hors d'un paragraphe")
    for enfant in bloc.get("content") or []:
        _blocs_adf(enfant, lignes, contexte)


def _texte_en_ligne(noeud: object, contexte: str) -> str:
    element = _noeud_adf(noeud, contexte)
    if element["type"] == "text":
        texte = element.get("text")
        if not isinstance(texte, str):
            raise UsineErreur(f"{contexte} : nœud ADF « text » sans texte")
        return texte
    if element["type"] == "hardBreak":
        return "\n"
    return "".join(_texte_en_ligne(e, contexte) for e in element.get("content") or [])


def valeur_courante(brute: object, contexte: str) -> str | None:
    """Valeur Jira d'un champ en texte : texte, `{value}`, `{name}` ou ADF ; vide → `None`."""
    if brute is None:
        return None
    if isinstance(brute, str):
        valeur = brute
    elif isinstance(brute, Mapping) and brute.get("type") == "doc":
        valeur = texte_adf(brute, contexte)
    elif isinstance(brute, Mapping) and isinstance(brute.get("value"), str):
        valeur = brute["value"]
    elif isinstance(brute, Mapping) and isinstance(brute.get("name"), str):
        valeur = brute["name"]
    else:
        raise UsineErreur(f"{contexte} : valeur de forme inconnue ({brute!r})")
    return valeur if valeur.strip() else None


def type_canonique(config: ConfigJira, nom_jira: object, cle: str) -> TypeTicket:
    """Type canonique du type Jira `nom_jira`, selon `types_tickets`."""
    if not isinstance(nom_jira, str) or nom_jira not in config.types_tickets:
        raise UsineErreur(
            f"{FICHIER_CONFIG} : types_tickets : type Jira {nom_jira!r} sans correspondance"
            f" (ticket {cle})"
        )
    return config.types_tickets[nom_jira]


def valeur_canonique(config: ConfigJira, champ: Champ, valeur_jira: str, cle: str) -> str:
    """Valeur canonique de `valeur_jira` pour `champ` ; valeur libre : inchangée."""
    if DOMAINES_CANONIQUES[champ] is None:
        return valeur_jira
    table = config.valeurs.get(champ, {})
    if valeur_jira not in table:
        raise UsineErreur(
            f"{FICHIER_CONFIG} : valeurs.{champ.value} : valeur Jira {valeur_jira!r} sans"
            f" correspondance (ticket {cle})"
        )
    return table[valeur_jira]


def _canonique_ou_rien(
    config: ConfigJira, champ: Champ, valeur_jira: object, cle: str, contexte: str
) -> str | None:
    if valeur_jira is not None and not isinstance(valeur_jira, str):
        raise UsineErreur(f"{contexte} : valeur de forme inconnue ({valeur_jira!r})")
    if valeur_jira is None or not valeur_jira.strip():
        return None
    return valeur_canonique(config, champ, valeur_jira, cle)


def _champs_par_identifiant(config: ConfigJira) -> dict[str, Champ]:
    return {identifiant: champ for champ, identifiant in config.champs.items()}


def _identifiant_item(item: Mapping[str, Any], contexte: str) -> str | None:
    """Identifiant Jira du champ modifié : `fieldId`, à défaut `field` hors champ personnalisé.

    Pour un champ personnalisé, `field` porte le nom d'affichage, pas l'identifiant : sans
    `fieldId` exploitable, l'item est illisible.
    """
    identifiant = item.get("fieldId")
    if isinstance(identifiant, str) and identifiant:
        return identifiant
    if item.get("fieldtype") == "custom":
        raise UsineErreur(f"{contexte} : champ personnalisé sans fieldId ({item.get('field')!r})")
    nom = item.get("field")
    return nom if isinstance(nom, str) and nom else None


def _items(historique: Mapping[str, Any], contexte: str) -> list[Mapping[str, Any]]:
    items = historique.get("items")
    if not isinstance(items, list) or not all(isinstance(i, Mapping) for i in items):
        raise UsineErreur(f"{contexte} : historique sans liste d'items")
    return items


def _id_historique(historique: Mapping[str, Any], contexte: str) -> str:
    identifiant = historique.get("id")
    if isinstance(identifiant, int) and not isinstance(identifiant, bool):
        identifiant = str(identifiant)
    if not isinstance(identifiant, str) or not identifiant:
        raise UsineErreur(f"{contexte} : historique sans identifiant")
    return identifiant


def _rang_id(identifiant: str) -> tuple[int, str]:
    return (
        int(identifiant) if identifiant.isascii() and identifiant.isdigit() else -1,
        identifiant,
    )


def ordonner_historiques(
    historiques: Iterable[Mapping[str, Any]], contexte: str
) -> list[tuple[str, datetime, Mapping[str, Any]]]:
    """Historiques dédoublonnés par id, triés par (horodatage, id) : `(id, instant, objet)`."""
    vus: dict[str, tuple[str, datetime, Mapping[str, Any]]] = {}
    for historique in historiques:
        if not isinstance(historique, Mapping):
            raise UsineErreur(f"{contexte} : historique de forme inconnue ({historique!r})")
        identifiant = _id_historique(historique, contexte)
        if identifiant in vus:
            continue
        instant = lire_horodatage(
            historique.get("created"), f"{contexte} : historique {identifiant}"
        )
        vus[identifiant] = (identifiant, instant, historique)
    return sorted(vus.values(), key=lambda h: (h[1], _rang_id(h[0])))


def _evenement(contexte: str, **attributs: Any) -> Evenement:
    try:
        return Evenement(**attributs)
    except ValidationError as exc:
        motifs = " ; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '(événement)'} : {err['msg']}"
            for err in exc.errors()
        )
        raise UsineErreur(f"{contexte} : événement invalide ({motifs})") from exc


def convertir_ticket(
    ticket: Mapping[str, Any],
    historiques: Iterable[Mapping[str, Any]],
    config: ConfigJira,
    source: SourceEvenement,
) -> list[Evenement]:
    """`Evenement` d'un ticket : création, attributs initiaux, puis changelog dans l'ordre.

    `ticket` est l'objet Jira (`id`, `key`, `fields`) ; `historiques` est son changelog
    complet (doublons tolérés, dédoublonnés par id). Seuls les `Champ` du type sont émis.
    """
    cle = ticket.get("key")
    contexte = f"Jira : ticket {cle}"
    if not isinstance(cle, str) or not cle:
        raise UsineErreur(f"Jira : ticket sans clé ({ticket.get('id')!r})")
    id_ticket = ticket.get("id")
    if isinstance(id_ticket, int) and not isinstance(id_ticket, bool):
        id_ticket = str(id_ticket)
    if not isinstance(id_ticket, str) or not id_ticket:
        raise UsineErreur(f"{contexte} : identifiant (id) absent")
    champs_jira = ticket.get("fields")
    if not isinstance(champs_jira, Mapping):
        raise UsineErreur(f"{contexte} : objet « fields » absent")
    type_jira = champs_jira.get("issuetype")
    nom_type = type_jira.get("name") if isinstance(type_jira, Mapping) else None
    type_ticket = type_canonique(config, nom_type, cle)
    creation = lire_horodatage(champs_jira.get("created"), f"{contexte} : created")
    retenus = CHAMPS_PAR_TYPE[type_ticket]
    par_identifiant = _champs_par_identifiant(config)
    ordonnes = ordonner_historiques(historiques, contexte)

    communs: dict[str, Any] = {"cle_ticket": cle, "type_ticket": type_ticket, "source": source}
    evenements = [
        _evenement(
            contexte,
            id_evenement=f"C-{id_ticket}",
            horodatage=creation,
            nature=NatureEvenement.creation,
            **communs,
        )
    ]

    premiers: dict[Champ, Mapping[str, Any]] = {}
    for identifiant, _, historique in ordonnes:
        for rang, item in enumerate(_items(historique, contexte), start=1):
            contexte_item = f"{contexte} : historique {identifiant}, item {rang}"
            champ = par_identifiant.get(_identifiant_item(item, contexte_item) or "")
            if champ is not None and champ not in premiers:
                premiers[champ] = item

    for champ in Champ:
        if champ not in retenus:
            continue
        contexte_champ = f"{contexte} : champ {champ.value}"
        if champ in premiers:
            vers = _canonique_ou_rien(
                config, champ, premiers[champ].get("fromString"), cle, contexte_champ
            )
        else:
            brute = valeur_courante(champs_jira.get(config.champs[champ]), contexte_champ)
            vers = None if brute is None else valeur_canonique(config, champ, brute, cle)
        if vers is None:
            continue
        evenements.append(
            _evenement(
                contexte,
                id_evenement=f"C-{id_ticket}-{champ.value}",
                horodatage=creation,
                nature=NatureEvenement.modification_champ,
                champ=champ,
                vers=vers,
                **communs,
            )
        )

    for identifiant, instant, historique in ordonnes:
        for rang, item in enumerate(_items(historique, contexte), start=1):
            evenement = _convertir_item(
                item, identifiant, rang, instant, retenus, par_identifiant, config, communs
            )
            if evenement is not None:
                evenements.append(evenement)
    return evenements


def _convertir_item(
    item: Mapping[str, Any],
    id_historique: str,
    rang: int,
    instant: datetime,
    retenus: frozenset[Champ],
    par_identifiant: Mapping[str, Champ],
    config: ConfigJira,
    communs: Mapping[str, Any],
) -> Evenement | None:
    cle = communs["cle_ticket"]
    contexte = f"Jira : ticket {cle} : historique {id_historique}, item {rang}"
    champ = par_identifiant.get(_identifiant_item(item, contexte) or "")
    if champ is None or champ not in retenus:
        return None
    id_evenement = f"{id_historique}-{rang}"
    de = _canonique_ou_rien(config, champ, item.get("fromString"), cle, contexte)
    vers = _canonique_ou_rien(config, champ, item.get("toString"), cle, contexte)
    if de == vers:
        return None
    if champ is Champ.statut:
        if vers is None:
            raise UsineErreur(f"{contexte} : changement de statut sans statut d'arrivée")
        nature = NatureEvenement.transition
    else:
        nature = NatureEvenement.modification_champ
    return _evenement(
        contexte,
        id_evenement=id_evenement,
        horodatage=instant,
        nature=nature,
        champ=champ,
        de=de,
        vers=vers,
        **communs,
    )


def trier_evenements(par_ticket: Iterable[Sequence[Evenement]]) -> list[Evenement]:
    """Fusionne les flux de chaque ticket, triés par (horodatage, `rang_cle`, ordre interne).

    L'ordre interne est celui de `convertir_ticket` : création puis attributs initiaux en tête.
    """
    indexes = [
        (evenement.horodatage, rang_cle(evenement.cle_ticket), ordre, evenement)
        for evenements in par_ticket
        for ordre, evenement in enumerate(evenements)
    ]
    indexes.sort(key=lambda t: (t[0], t[1], t[2]))
    return [evenement for *_, evenement in indexes]
