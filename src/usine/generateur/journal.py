"""Mini-générateur déterministe du Journal d'événements (Story 0.3, amorce de FR-2).

Cœur pur : ni horloge, ni `random` global, ni I/O. La sortie ne dépend que de
`(config, graine, date_generation)` ; tout le hasard vient d'une seule instance de
`Random` initialisée par la graine, tirée dans un ordre fixe. Seule `ecrire_journal` écrit
sur disque : le Journal et la vérité terrain d'une `Generation`.
"""

import json
import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from types import MappingProxyType

from usine.contrats.calendrier import (
    FUSEAU,
    dernier_jour_ouvre_ecoule,
    est_jour_ouvre,
    jours_ouvres,
    verifier_lundi,
)
from usine.contrats.config import ConfigProgramme, EntiteProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import EnteteJournal, Evenement, NatureEvenement, SourceEvenement
from usine.contrats.passage import CHEMIN_JOURNAL, CHEMIN_VERITE_TERRAIN
from usine.contrats.tickets import (
    CHAMPS_PAR_TYPE,
    CauseRacine,
    Champ,
    Gravite,
    Phase,
    StatutAnomalie,
    StatutCertification,
    StatutTest,
    TypeTicket,
)
from usine.generateur.textes import DESCRIPTIONS, MODELE_CORPUS, TITRES, VERSION_CORPUS

PREFIXE_CLE = "DEMO"
"""Préfixe des clés de ticket générées (`DEMO-<n>`)."""

HEURE_DEBUT = 8
"""Première heure ouvrée (heure de Paris)."""

HEURE_FIN = 18
"""Fin de journée ouvrée (exclue) : les horodatages tombent entre 8 h et 17 h 59."""

TRANSITIONS_MAX = 4
"""Nombre maximal de transitions de statut par Anomalie."""

CAS_DE_TEST_PAR_ENTITE = (2, 3)
"""Bornes du nombre de Cas de test par Entité."""

PROBA_EXECUTION_TEST = 0.7
"""Probabilité qu'un Cas de test soit exécuté (passage à `ok` ou `ko`)."""

PROBA_TEST_OK = 0.6
"""Probabilité qu'un Cas de test exécuté soit `ok`."""

PROBA_CORRECTION_DIRECTE = 0.3
"""Probabilité qu'une Anomalie nouvelle passe directement en correction."""

PROBA_REJET = 0.15
"""Probabilité qu'une Anomalie en analyse soit rejetée."""

PROBA_RETOUR_CORRECTION = 0.2
"""Probabilité qu'un nouveau test renvoie l'Anomalie en correction."""

PROBA_REOUVERTURE = 0.2
"""Probabilité qu'une Anomalie fermée soit rouverte (rare : il faut d'abord la fermer)."""


@dataclass(frozen=True)
class Generation:
    """Résultat d'une génération : en-tête, événements du Journal et vérité terrain."""

    entete: EnteteJournal
    evenements: tuple[Evenement, ...]
    verite_terrain: Mapping[str, CauseRacine]
    """Cause racine de chaque Anomalie, par clé de ticket ; jamais dans le Journal."""


@dataclass(frozen=True)
class _Changement:
    """Changement d'un ticket postérieur à sa création."""

    horodatage: datetime
    nature: NatureEvenement
    champ: Champ
    de: str
    vers: str


@dataclass
class _Ticket:
    """Ticket en cours de génération, avant attribution de sa clé."""

    type_ticket: TypeTicket
    creation: datetime
    attributs: dict[Champ, str]
    changements: list[_Changement] = field(default_factory=list)
    cause: CauseRacine | None = None


def _horodatage(jour: date, rng: random.Random) -> datetime:
    """Instant tiré en heures ouvrées de Paris le jour `jour`, rendu en UTC."""
    heure = rng.randrange(HEURE_DEBUT, HEURE_FIN)
    minute = rng.randrange(60)
    return datetime.combine(jour, time(heure, minute), tzinfo=FUSEAU).astimezone(UTC)


def _jours_ulterieurs(
    jours: tuple[date, ...], jour: date, nombre: int, rng: random.Random
) -> list[date]:
    """Jusqu'à `nombre` Jours ouvrés distincts strictement après `jour`, triés."""
    candidats = [j for j in jours if j > jour]
    return sorted(rng.sample(candidats, min(nombre, len(candidats))))


def _statut_suivant(statut: StatutAnomalie, rng: random.Random) -> StatutAnomalie | None:
    """Statut suivant le long du workflow H-17 ; `None` si le statut est terminal."""
    match statut:
        case StatutAnomalie.nouvelle:
            if rng.random() < PROBA_CORRECTION_DIRECTE:
                return StatutAnomalie.en_correction
            return StatutAnomalie.en_analyse
        case StatutAnomalie.en_analyse:
            if rng.random() < PROBA_REJET:
                return StatutAnomalie.rejetee
            return StatutAnomalie.en_correction
        case StatutAnomalie.en_correction:
            return StatutAnomalie.a_retester
        case StatutAnomalie.a_retester:
            if rng.random() < PROBA_RETOUR_CORRECTION:
                return StatutAnomalie.en_correction
            return StatutAnomalie.fermee
        case StatutAnomalie.fermee:
            if rng.random() < PROBA_REOUVERTURE:
                return StatutAnomalie.en_analyse
            return None
        case StatutAnomalie.rejetee:
            return None


def _textes(
    type_ticket: TypeTicket, entite: str, domaine: str, rng: random.Random
) -> tuple[str, str]:
    """Titre et description tirés dans le mini-corpus."""
    titre = rng.choice(TITRES[type_ticket]).format(entite=entite, domaine=domaine)
    description = rng.choice(DESCRIPTIONS[type_ticket]).format(entite=entite, domaine=domaine)
    return titre, description


def _anomalie(
    entite: EntiteProgramme,
    domaines: tuple[str, ...],
    jours: tuple[date, ...],
    rng: random.Random,
) -> _Ticket:
    jour = rng.choice(jours)
    creation = _horodatage(jour, rng)
    gravite = rng.choice(tuple(Gravite))
    phase = rng.choice(tuple(Phase))
    domaine = rng.choice(domaines)
    cause = rng.choice(tuple(CauseRacine))
    titre, description = _textes(TypeTicket.anomalie, entite.code, domaine, rng)
    ticket = _Ticket(
        TypeTicket.anomalie,
        creation,
        {
            Champ.statut: StatutAnomalie.nouvelle.value,
            Champ.entite: entite.code,
            Champ.vague: entite.vague,
            Champ.domaine: domaine,
            Champ.gravite: gravite.value,
            Champ.phase: phase.value,
            Champ.titre: titre,
            Champ.description: description,
        },
        cause=cause,
    )
    statut = StatutAnomalie.nouvelle
    for jour_transition in _jours_ulterieurs(jours, jour, rng.randint(0, TRANSITIONS_MAX), rng):
        suivant = _statut_suivant(statut, rng)
        if suivant is None:
            break
        ticket.changements.append(
            _Changement(
                _horodatage(jour_transition, rng),
                NatureEvenement.transition,
                Champ.statut,
                statut.value,
                suivant.value,
            )
        )
        statut = suivant
    return ticket


def _cas_de_test(
    entite: EntiteProgramme,
    domaines: tuple[str, ...],
    jours: tuple[date, ...],
    rng: random.Random,
) -> _Ticket:
    jour = rng.choice(jours)
    creation = _horodatage(jour, rng)
    phase = rng.choice(tuple(Phase))
    domaine = rng.choice(domaines)
    titre, description = _textes(TypeTicket.cas_de_test, entite.code, domaine, rng)
    ticket = _Ticket(
        TypeTicket.cas_de_test,
        creation,
        {
            Champ.statut_test: StatutTest.non_execute.value,
            Champ.entite: entite.code,
            Champ.vague: entite.vague,
            Champ.domaine: domaine,
            Champ.phase: phase.value,
            Champ.titre: titre,
            Champ.description: description,
        },
    )
    if rng.random() < PROBA_EXECUTION_TEST:
        resultat = StatutTest.ok if rng.random() < PROBA_TEST_OK else StatutTest.ko
        for jour_execution in _jours_ulterieurs(jours, jour, 1, rng):
            ticket.changements.append(
                _Changement(
                    _horodatage(jour_execution, rng),
                    NatureEvenement.modification_champ,
                    Champ.statut_test,
                    StatutTest.non_execute.value,
                    resultat.value,
                )
            )
    return ticket


def _certification(entite: EntiteProgramme, jours: tuple[date, ...], rng: random.Random) -> _Ticket:
    creation = _horodatage(rng.choice(jours), rng)
    statut = rng.choice(tuple(StatutCertification))
    titre, description = _textes(TypeTicket.certification, entite.code, "", rng)
    return _Ticket(
        TypeTicket.certification,
        creation,
        {
            Champ.statut_certification: statut.value,
            Champ.entite: entite.code,
            Champ.vague: entite.vague,
            Champ.titre: titre,
            Champ.description: description,
        },
    )


def fenetre_generation(date_generation: date, nb_semaines: int) -> tuple[date, date]:
    """`(ancrage des semaines, Date d'injection)` pour une date de génération.

    Date d'injection = dernier Jour ouvré écoulé ; ancrage = lundi de sa semaine, moins
    `nb_semaines - 1` semaines.
    """
    date_injection = dernier_jour_ouvre_ecoule(date_generation)
    # Lundi de la semaine : on recule tant que la veille est un Jour ouvré.
    lundi = date_injection
    while est_jour_ouvre(lundi - timedelta(days=1)):
        lundi -= timedelta(days=1)
    verifier_lundi(lundi)
    return lundi - timedelta(weeks=nb_semaines - 1), date_injection


def _evenements_du_ticket(cle: str, ticket: _Ticket) -> list[Evenement]:
    """Création, un `modification_champ` par Champ du type (ordre de `Champ`), puis changements.

    L'identifiant est provisoire : il est attribué après le tri du Journal.
    """

    def evenement(
        horodatage: datetime,
        nature: NatureEvenement,
        champ: Champ | None = None,
        de: str | None = None,
        vers: str | None = None,
    ) -> Evenement:
        return Evenement(
            id_evenement="J-0",
            cle_ticket=cle,
            type_ticket=ticket.type_ticket,
            horodatage=horodatage,
            nature=nature,
            champ=champ,
            de=de,
            vers=vers,
            source=SourceEvenement.journal,
        )

    champs = CHAMPS_PAR_TYPE[ticket.type_ticket]
    evenements = [evenement(ticket.creation, NatureEvenement.creation)]
    evenements.extend(
        evenement(
            ticket.creation,
            NatureEvenement.modification_champ,
            champ,
            None,
            ticket.attributs[champ],
        )
        for champ in Champ
        if champ in champs
    )
    evenements.extend(
        evenement(c.horodatage, c.nature, c.champ, c.de, c.vers) for c in ticket.changements
    )
    return evenements


def generer(config: ConfigProgramme, graine: int, date_generation: date) -> Generation:
    """Génère le Journal du Programme fictif réduit pour `graine` et `date_generation`.

    Tirages dans un ordre fixe : nombre d'Anomalies, répartition par Entité, puis, Entité par
    Entité (ordre de la configuration), ses Anomalies, ses Cas de test et sa Certification.
    Les clés `DEMO-<n>` sont ensuite attribuées dans l'ordre chronologique de création.
    """
    if graine < 0:
        # `Random(-n)` tire comme `Random(n)` : deux graines, un même Journal.
        raise UsineErreur(f"graine invalide : {graine} (entier ≥ 0 attendu)")
    ancrage, date_injection = fenetre_generation(date_generation, config.nb_semaines)
    jours = jours_ouvres(ancrage, date_injection)
    rng = random.Random(graine)

    volumetrie = config.volumetrie
    nb_anomalies = rng.randint(volumetrie.anomalies_min, volumetrie.anomalies_max)
    repartition = [0] * len(config.entites)
    for _ in range(nb_anomalies):
        repartition[rng.randrange(len(config.entites))] += 1

    tickets: list[_Ticket] = []
    for entite, nombre in zip(config.entites, repartition, strict=True):
        tickets.extend(_anomalie(entite, config.domaines, jours, rng) for _ in range(nombre))
        nb_tests = rng.randint(*CAS_DE_TEST_PAR_ENTITE)
        tickets.extend(_cas_de_test(entite, config.domaines, jours, rng) for _ in range(nb_tests))
        tickets.append(_certification(entite, jours, rng))

    ordre = sorted(range(len(tickets)), key=lambda i: (tickets[i].creation, i))
    a_trier: list[tuple[datetime, int, int, Evenement]] = []
    verite: dict[str, CauseRacine] = {}
    for numero, indice in enumerate(ordre, start=1):
        ticket = tickets[indice]
        cle = f"{PREFIXE_CLE}-{numero}"
        if ticket.cause is not None:
            verite[cle] = ticket.cause
        a_trier.extend(
            (e.horodatage, numero, rang, e)
            for rang, e in enumerate(_evenements_du_ticket(cle, ticket))
        )

    # Tri par (horodatage, clé de ticket, rang de création) : la création passe en tête.
    a_trier.sort(key=lambda t: t[:3])
    evenements = tuple(
        e.model_copy(update={"id_evenement": f"J-{rang}"})
        for rang, (_, _, _, e) in enumerate(a_trier, start=1)
    )
    entete = EnteteJournal(
        graine=graine,
        date_generation=date_generation,
        date_injection=date_injection,
        ancrage_semaines=ancrage,
        version_corpus=VERSION_CORPUS,
        modele_corpus=MODELE_CORPUS,
    )
    return Generation(entete, evenements, MappingProxyType(verite))


def serialiser_journal(generation: Generation) -> bytes:
    """Journal JSONL : l'en-tête puis un `Evenement` par ligne, UTF-8, fins de ligne `\\n`."""
    lignes = [generation.entete.model_dump_json()]
    lignes.extend(e.model_dump_json() for e in generation.evenements)
    return ("\n".join(lignes) + "\n").encode("utf-8")


def serialiser_verite(generation: Generation) -> bytes:
    """Vérité terrain : `{clé: cause racine}` en JSON trié par clé, UTF-8, fin de ligne `\\n`."""
    contenu = {cle: cause.value for cle, cause in generation.verite_terrain.items()}
    texte = json.dumps(contenu, ensure_ascii=False, indent=2, sort_keys=True)
    return (texte + "\n").encode("utf-8")


def ecrire_journal(generation: Generation, repertoire: Path) -> Path:
    """Écrit le Journal et la vérité terrain dans `repertoire` ; renvoie le chemin du Journal.

    Les noms sont ceux de `contrats.passage` (`journal.jsonl`, `verite_terrain.json`). Une
    erreur d'écriture lève une `UsineErreur` qui nomme le répertoire.
    """
    journal = repertoire / CHEMIN_JOURNAL.name
    try:
        repertoire.mkdir(parents=True, exist_ok=True)
        journal.write_bytes(serialiser_journal(generation))
        (repertoire / CHEMIN_VERITE_TERRAIN.name).write_bytes(serialiser_verite(generation))
    except OSError as exc:
        raise UsineErreur(f"{repertoire} : écriture impossible ({exc.strerror or exc})") from exc
    return journal
