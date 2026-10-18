"""Jira fait foi : rejeu d'état, alignements et conversion de l'état Jira (H-27, FR-49, AD-4).

- `etats_tickets` rejoue un flux d'`Evenement` : pour chaque ticket et chaque champ d'état,
  la dernière valeur `vers` reçue (ordre : horodatage, puis ordre du flux), comme le domaine ;
- `alignements` compare un état rejoué à l'état Jira et rend un `Evenement` `alignement` par
  champ d'état qui diffère (jamais `titre` ni `description`, jamais vers une valeur vide) ;
- `convertir_etat_jira` traduit l'état Jira à un instant en créations + alignements, pour le
  test de cohérence à la Date d'injection (FR-49) ;
- `DetecteurAlignements` compare le flux composite à l'état Jira, pour l'étape `extraction`.

Identifiant d'un alignement : `A-<clé>-<champ>-<sha256(vers)[:8]>` ; il ne dépend pas de
l'instant de détection, si bien qu'un même écart n'est persisté qu'une fois.
"""

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from usine.adaptateurs.composite.source import SourceComposite
from usine.adaptateurs.journal import SourceJournal
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, NatureEvenement, SourceEvenement
from usine.contrats.format import formater_horodatage
from usine.contrats.tickets import CHAMPS_PAR_TYPE, Champ, TypeTicket, rang_cle

CHAMPS_ETAT: tuple[Champ, ...] = (
    Champ.statut,
    Champ.entite,
    Champ.vague,
    Champ.domaine,
    Champ.gravite,
    Champ.phase,
    Champ.statut_test,
    Champ.statut_certification,
)
"""Champs comparés entre état rejoué et état Jira : ceux des Instantanés, sans les textes."""


@dataclass
class EtatTicket:
    """État rejoué d'un ticket : type, source, création vue et valeur de chaque champ d'état."""

    type_ticket: TypeTicket
    source: SourceEvenement
    cree: bool = False
    valeurs: dict[Champ, str | None] = field(default_factory=dict)


def _instant_utc(instant: datetime, quoi: str) -> datetime:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise UsineErreur(f"{quoi} sans fuseau : {instant!r}")
    return instant.astimezone(UTC)


def etats_tickets(evenements: Iterable[Evenement]) -> dict[str, EtatTicket]:
    """État de chaque ticket après rejeu de `evenements`.

    Flux dédoublonné par `id_evenement` (première occurrence gardée), puis trié par
    horodatage sans changer l'ordre à horodatage égal ; chaque champ d'état prend la dernière
    valeur `vers` reçue (`None` compris). Type et source sont ceux du premier événement du
    ticket.
    """
    vus: set[str] = set()
    uniques: list[Evenement] = []
    for evenement in evenements:
        if evenement.id_evenement not in vus:
            vus.add(evenement.id_evenement)
            uniques.append(evenement)
    uniques.sort(key=lambda e: e.horodatage)
    etats: dict[str, EtatTicket] = {}
    for evenement in uniques:
        etat = etats.setdefault(
            evenement.cle_ticket, EtatTicket(evenement.type_ticket, evenement.source)
        )
        if evenement.nature is NatureEvenement.creation:
            etat.cree = True
        elif evenement.champ in CHAMPS_ETAT:
            etat.valeurs[evenement.champ] = evenement.vers
    return etats


def id_alignement(cle_ticket: str, champ: Champ, vers: str) -> str:
    """`A-<clé>-<champ>-<sha256(vers)[:8]>`."""
    empreinte = hashlib.sha256(vers.encode("utf-8")).hexdigest()[:8]
    return f"A-{cle_ticket}-{champ.value}-{empreinte}"


def alignements(
    rejoues: Mapping[str, EtatTicket], jira: Mapping[str, EtatTicket], instant: datetime
) -> list[Evenement]:
    """Un `alignement` par champ d'état où la valeur Jira (non vide) diffère de l'état rejoué.

    `de` = valeur rejouée (`None` si le ticket ou le champ est inconnu du rejeu), `vers` =
    valeur Jira, horodatage = `instant`, type et source = ceux de Jira. Tickets dans l'ordre
    de `rang_cle`, champs dans l'ordre de `CHAMPS_ETAT`.
    """
    instant = _instant_utc(instant, "instant d'alignement")
    rendus: list[Evenement] = []
    for cle in sorted(jira, key=rang_cle):
        etat = jira[cle]
        rejoue = rejoues.get(cle)
        for champ in CHAMPS_ETAT:
            if champ not in CHAMPS_PAR_TYPE[etat.type_ticket]:
                continue
            vers = etat.valeurs.get(champ)
            if vers is None:
                continue
            de = None if rejoue is None else rejoue.valeurs.get(champ)
            if de == vers:
                continue
            rendus.append(
                Evenement(
                    id_evenement=id_alignement(cle, champ, vers),
                    cle_ticket=cle,
                    type_ticket=etat.type_ticket,
                    horodatage=instant,
                    nature=NatureEvenement.alignement,
                    champ=champ,
                    de=de,
                    vers=vers,
                    source=etat.source,
                )
            )
    return rendus


def _hors_alignements(evenements: Iterable[Evenement]) -> list[Evenement]:
    return [e for e in evenements if e.nature is not NatureEvenement.alignement]


def convertir_etat_jira(evenements_jira: Iterable[Evenement], instant: datetime) -> list[Evenement]:
    """État Jira à `instant` en `Evenement` : créations Jira ≤ `instant`, puis un alignement
    par champ d'état renseigné, horodaté à `instant` (test de cohérence FR-49).

    Seuls les événements Jira hors `alignement` d'horodatage ≤ `instant` sont rejoués.
    """
    instant = _instant_utc(instant, "instant de conversion")
    retenus = sorted(
        (e for e in _hors_alignements(evenements_jira) if e.horodatage <= instant),
        key=lambda e: e.horodatage,
    )
    creations = [e for e in retenus if e.nature is NatureEvenement.creation]
    return [*creations, *alignements({}, etats_tickets(retenus), instant)]


class DetecteurAlignements:
    """Détecte les écarts entre le flux composite et l'état Jira (H-27).

    Appelable `(evenements_jira, instant) -> alignements` : `evenements_jira` sont tous les
    événements Jira connus (stockés et nouveaux, alignements déjà persistés compris). L'état
    rejoué est celui de `SourceComposite(journal, evenements_jira)` ; l'état Jira, le rejeu des
    seuls événements Jira hors `alignement`. Un instant de détection antérieur ou égal à la fin
    d'injection lève une `UsineErreur` : l'alignement serait ignoré par la coupure.
    """

    def __init__(self, journal: SourceJournal) -> None:
        # Refuse dès la construction un Journal sans manifeste d'injection.
        self._fin = SourceComposite(journal, lambda: ()).horodatage_fin_injection
        self._journal = journal

    def __call__(self, evenements_jira: Iterable[Evenement], instant: datetime) -> list[Evenement]:
        """Alignements à persister pour les écarts constatés à `instant`."""
        instant = _instant_utc(instant, "instant de détection des alignements")
        if instant <= self._fin:
            raise UsineErreur(
                f"instant de détection des alignements {formater_horodatage(instant)} antérieur ou"
                f" égal à la fin d'injection {formater_horodatage(self._fin)} (heure de Paris) :"
                f" relancer après l'injection"
            )
        jira = tuple(evenements_jira)
        rejoues = etats_tickets(SourceComposite(self._journal, lambda: jira).evenements())
        return alignements(rejoues, etats_tickets(_hors_alignements(jira)), instant)
