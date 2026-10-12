"""Tickets du Public Jira Dataset → `SerieStock` par projet, en Jours ouvrés (FR-51).

Fonction pure et déterministe, sans I/O. Les tickets ont la forme brute de l'API Jira v2 du
dump (`key`, `fields`, `changelog.histories`). Chaque ticket est rejoué depuis sa création :
il est « en stock » tant qu'il est ouvert et de priorité maximale ; chaque passage hors
stock → en stock est une Entrée, l'inverse une Sortie, au Jour ouvré `jour_ouvre_de(instant)`.

- état initial à `fields.created` : résolu si le premier item `resolution` du changelog part
  d'une valeur (`fromString`/`from` non vide ; ticket créé résolu), sinon ouvert ; priorité =
  `fromString` du premier changement de priorité du changelog (sinon `fields.priority.name`) ;
- items `resolution` : vide → valeur = résolu, valeur → vide = rouvert ; items `priority` :
  nouvelle priorité ; rejoués dans l'ordre de `histories[].created` ;
- sans item `resolution` mais avec `fields.resolutiondate` : résolu à cette date ;
- sans item `resolution` ni `resolutiondate`, mais statut courant de catégorie « done »
  (`fields.status.statusCategory.key`, ticket fermé par le seul statut) : résolu à l'instant
  du dernier item `status` du changelog, sinon à `created`.

Un horodatage antérieur à la création est rabattu sur `fields.created`.

La série d'un projet (`"{depot}/{clé projet}"`) est dense, du premier Jour ouvré d'événement à
`fin` (défaut : dernier Jour ouvré d'événement du projet) ; stock(j) = stock(j−1) + Entrées(j)
− Sorties(j). C'est la forme attendue par `domaine.prevision.baseline.prevoir_sortie`.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import polars as pl

from usine.contrats.calendrier import est_jour_ouvre, jour_ouvre_de, jours_ouvres
from usine.contrats.erreurs import UsineErreur
from usine.contrats.prevision import SCHEMA_SERIE_STOCK
from usine.contrats.schemas import valider

PRIORITES_MAXIMALES = frozenset({"Blocker", "Highest"})
"""Nom du niveau de priorité le plus haut : `Blocker` (Apache, …), `Highest` (schéma par défaut)."""

_FORMAT_JIRA = "%Y-%m-%dT%H:%M:%S.%f%z"
_RESOLUTION = "resolution"
_PRIORITE = "priority"
_STATUT = "status"


@dataclass(frozen=True)
class _Etape:
    instant: datetime
    items: tuple[Mapping[str, Any], ...]


def convertir_en_series(
    tickets: Iterable[Mapping[str, Any]],
    *,
    depot: str,
    priorites: frozenset[str] = PRIORITES_MAXIMALES,
    fin: date | None = None,
) -> pl.DataFrame:
    """`SerieStock` des projets de `depot` dont un ticket a été ouvert en priorité maximale.

    Les événements postérieurs à `fin` (un Jour ouvré) sont ignorés. Lève une `UsineErreur`
    nommant le ticket si sa clé, sa date de création ou un horodatage du changelog manque ou
    est sans fuseau.
    """
    if fin is not None and not est_jour_ouvre(fin):
        raise UsineErreur(f"Zenodo {depot} : fin {fin.isoformat()} n'est pas un Jour ouvré")
    mouvements: dict[str, dict[date, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for ticket in tickets:
        projet, evenements = _evenements(ticket, priorites)
        for jour, sens in evenements:
            if fin is not None and jour > fin:
                break
            mouvements[f"{depot}/{projet}"][jour][0 if sens > 0 else 1] += 1

    colonnes: dict[str, list[Any]] = {nom: [] for nom in SCHEMA_SERIE_STOCK.colonnes}
    for serie in sorted(mouvements):
        par_jour = mouvements[serie]
        stock = 0
        for jour in jours_ouvres(min(par_jour), fin if fin is not None else max(par_jour)):
            entrees, sorties = par_jour.get(jour, (0, 0))
            stock += entrees - sorties
            colonnes["serie"].append(serie)
            colonnes["date"].append(jour)
            colonnes["stock"].append(stock)
            colonnes["entrees"].append(entrees)
            colonnes["sorties"].append(sorties)
    return valider(
        pl.DataFrame(colonnes, schema=dict(SCHEMA_SERIE_STOCK.colonnes)), SCHEMA_SERIE_STOCK
    )


def _evenements(
    ticket: Mapping[str, Any], priorites: frozenset[str]
) -> tuple[str, list[tuple[date, int]]]:
    """Clé projet et Entrées (+1) / Sorties (−1) du ticket, par Jour ouvré, dans l'ordre."""
    cle = ticket.get("key")
    if not isinstance(cle, str) or not cle:
        raise UsineErreur(f"Zenodo : ticket sans clé ({ticket.get('_id')!r})")
    champs: Mapping[str, Any] = ticket.get("fields") or {}
    projet_jira = champs.get("project") or {}
    projet = projet_jira.get("key") or cle.rsplit("-", 1)[0]
    cree = _instant(champs.get("created"), cle, "fields.created")

    historiques = (ticket.get("changelog") or {}).get("histories") or []
    etapes = [
        _Etape(
            max(_instant(h.get("created"), cle, "changelog.histories.created"), cree),
            tuple(h.get("items") or ()),
        )
        for h in historiques
    ]
    etapes.sort(key=lambda e: e.instant)
    items = [item for etape in etapes for item in etape.items]
    premiere_resolution = next((i for i in items if _champ(i) == _RESOLUTION), None)
    if premiere_resolution is not None:
        ouvert = not (premiere_resolution.get("fromString") or premiere_resolution.get("from"))
    else:
        ouvert = True
        resolu = champs.get("resolutiondate")
        fermeture: datetime | None = None
        if resolu is not None:
            fermeture = max(_instant(resolu, cle, "fields.resolutiondate"), cree)
        elif _statut_termine(champs):
            statuts = [e.instant for e in etapes if any(_champ(i) == _STATUT for i in e.items)]
            fermeture = statuts[-1] if statuts else cree
        if fermeture is not None:
            etapes.append(_Etape(fermeture, ({"field": _RESOLUTION, "toString": "résolu"},)))
            etapes.sort(key=lambda e: e.instant)

    premier_changement = next((i for i in items if _champ(i) == _PRIORITE), None)
    if premier_changement is not None:
        priorite = premier_changement.get("fromString")
    else:
        priorite = (champs.get("priority") or {}).get("name")
    en_stock = ouvert and priorite in priorites
    evenements: list[tuple[date, int]] = [(jour_ouvre_de(cree), 1)] if en_stock else []
    for etape in etapes:
        for item in etape.items:
            champ = _champ(item)
            if champ == _RESOLUTION:
                ouvert = not (item.get("toString") or item.get("to"))
            elif champ == _PRIORITE:
                priorite = item.get("toString")
        apres = ouvert and priorite in priorites
        if apres != en_stock:
            evenements.append((jour_ouvre_de(etape.instant), 1 if apres else -1))
            en_stock = apres
    return projet, evenements


def _statut_termine(champs: Mapping[str, Any]) -> bool:
    """Vrai si le statut courant du ticket est de catégorie « done »."""
    categorie = ((champs.get("status") or {}).get("statusCategory") or {}).get("key")
    return categorie == "done"


def _champ(item: Mapping[str, Any]) -> str:
    return str(item.get("field") or "").lower()


def _instant(valeur: object, cle: str, nom: str) -> datetime:
    """Horodatage avec fuseau d'un champ du ticket `cle` (chaîne Jira ou `datetime`)."""
    if isinstance(valeur, str):
        texte = valeur
        try:
            # `%z` présent : le résultat a un fuseau dès que l'analyse réussit.
            valeur = datetime.strptime(texte, _FORMAT_JIRA)  # noqa: DTZ007
        except ValueError:
            try:
                valeur = datetime.fromisoformat(texte)
            except ValueError:
                raise UsineErreur(f"Zenodo {cle} : {nom} illisible {texte!r}") from None
    if not isinstance(valeur, datetime):
        raise UsineErreur(f"Zenodo {cle} : {nom} absent ou invalide ({valeur!r})")
    if valeur.tzinfo is None or valeur.utcoffset() is None:
        raise UsineErreur(f"Zenodo {cle} : {nom} sans fuseau ({valeur.isoformat()})")
    return valeur
