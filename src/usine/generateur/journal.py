"""Générateur déterministe du Journal d'événements (Stories 0.3, 1.1 et 1.2, amorce de FR-2).

Cœur pur : ni horloge, ni `random` global, ni I/O. La sortie ne dépend que de
`(config, graine, date_generation, cle_projet, corpus)` (la clé de projet ne fixe que le préfixe
des clés de tickets) ; tout le hasard vient d'une seule instance de
`Random` initialisée par la graine, tirée dans un ordre fixe. Seule `ecrire_journal` écrit
sur disque : le Journal et la vérité terrain d'une `Generation`.
"""

import json
import random
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from types import MappingProxyType

from usine.contrats.calendrier import (
    FUSEAU,
    dernier_jour_ouvre_ecoule,
    jour_ouvre_precedent,
    jours_ouvres,
    semaine_programme,
    verifier_lundi,
)
from usine.contrats.config import ConfigProgramme, EntiteProgramme, VagueProgramme
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
from usine.generateur.corpus import Corpus, TexteTicket
from usine.generateur.textes import corpus_provisoire

CLE_PROJET_ESSAI = "DEMO"
"""Clé de projet par défaut, pour les appelants sans configuration Jira (tests, composition).

La CLI passe `ConfigJira.cle_projet` : les clés générées sont `<cle_projet>-<n>`.
"""

_MOTIF_CLE_PROJET = re.compile(r"[A-Z][A-Z0-9]+")
"""Forme d'une clé de projet Jira (même motif que `ConfigJira.cle_projet`)."""

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
    case: tuple[TexteTicket, ...], entite: str, domaine: str, rng: random.Random
) -> tuple[str, str]:
    """Titre et description d'une paire tirée d'un seul coup dans une case du Corpus."""
    return rng.choice(case).remplir(entite, domaine)


def _verifier_phases(vague: VagueProgramme) -> None:
    if not vague.phases:
        raise UsineErreur(f"Vague {vague.code} : aucune Phase dans son calendrier")


def _phase_du_calendrier(vague: VagueProgramme, semaine: int) -> Phase:
    """Phase de la Vague en semaine `semaine`.

    Parmi les Phases dont [début, fin] contient la semaine, la dernière ; si aucune ne la
    contient (trou du calendrier), la dernière Phase commencée ; sinon la première Phase.
    « Dernière » : début le plus tardif, puis rang le plus élevé dans la configuration.
    """
    _verifier_phases(vague)
    en_cours = [
        (periode.semaine_debut, rang)
        for rang, periode in enumerate(vague.phases)
        if periode.semaine_debut <= semaine <= periode.semaine_fin
    ]
    commencees = en_cours or [
        (periode.semaine_debut, rang)
        for rang, periode in enumerate(vague.phases)
        if periode.semaine_debut <= semaine
    ]
    if not commencees:
        return vague.phases[0].phase
    return vague.phases[max(commencees)[1]].phase


@dataclass
class _Calendrier:
    """Semaines du Programme, Phases des Vagues et Entrées d'Anomalies comptées par semaine."""

    ancrage: date
    jours: tuple[date, ...]
    vagues: Mapping[str, VagueProgramme]
    entrees_max: int
    entrees: dict[int, int] = field(default_factory=dict)
    """Entrées (créations et réouvertures) par semaine du Programme."""

    def semaine(self, jour: date) -> int:
        return semaine_programme(jour, self.ancrage)

    def phase(self, entite: EntiteProgramme, jour: date) -> Phase:
        return _phase_du_calendrier(self.vagues[entite.vague], self.semaine(jour))

    def accepter_reouverture(self, jour: date) -> bool:
        """Compte une réouverture le jour `jour` si sa semaine reste sous le maximum d'Entrées."""
        semaine = self.semaine(jour)
        if self.entrees.get(semaine, 0) >= self.entrees_max:
            return False
        self.entrees[semaine] = self.entrees.get(semaine, 0) + 1
        return True


def _anomalie(
    entite: EntiteProgramme,
    jour: date,
    domaines: tuple[str, ...],
    corpus: Corpus,
    calendrier: _Calendrier,
    rng: random.Random,
) -> _Ticket:
    creation = _horodatage(jour, rng)
    gravite = rng.choice(tuple(Gravite))
    phase = calendrier.phase(entite, jour)
    domaine = rng.choice(domaines)
    cause = rng.choice(tuple(CauseRacine))
    case = corpus.textes_domaine(domaine).anomalies[cause]
    titre, description = _textes(case, entite.code, domaine, rng)
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
    nb_transitions = rng.randint(0, TRANSITIONS_MAX)
    for jour_transition in _jours_ulterieurs(calendrier.jours, jour, nb_transitions, rng):
        suivant = _statut_suivant(statut, rng)
        if suivant is None:
            break
        # Une réouverture est une Entrée : refusée si sa semaine a atteint son maximum.
        if statut is StatutAnomalie.fermee and not calendrier.accepter_reouverture(jour_transition):
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
    corpus: Corpus,
    calendrier: _Calendrier,
    rng: random.Random,
) -> _Ticket:
    jours = calendrier.jours
    jour = rng.choice(jours)
    creation = _horodatage(jour, rng)
    phase = calendrier.phase(entite, jour)
    domaine = rng.choice(domaines)
    case = corpus.textes_domaine(domaine).cas_de_test
    titre, description = _textes(case, entite.code, domaine, rng)
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


def _certification(
    entite: EntiteProgramme, corpus: Corpus, jours: tuple[date, ...], rng: random.Random
) -> _Ticket:
    creation = _horodatage(rng.choice(jours), rng)
    statut = rng.choice(tuple(StatutCertification))
    titre, description = _textes(corpus.certifications, entite.code, "", rng)
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
    # Lundi de la semaine : premier Jour ouvré dont la veille ouvrée n'est pas la veille
    # calendaire (`contrats.calendrier` reste seul juge des Jours ouvrés, AD-17).
    lundi = date_injection
    while jour_ouvre_precedent(lundi) == lundi - timedelta(days=1):
        lundi = jour_ouvre_precedent(lundi)
    verifier_lundi(lundi)
    return lundi - timedelta(weeks=nb_semaines - 1), date_injection


def _verifier_cle_projet(cle_projet: str) -> None:
    if _MOTIF_CLE_PROJET.fullmatch(cle_projet) is None:
        raise UsineErreur(
            f"clé de projet invalide : {cle_projet!r} (attendu : une majuscule puis des"
            " majuscules ou des chiffres, ex. DEMO)"
        )


def _bornes_anomalies(config: ConfigProgramme) -> tuple[int, int]:
    """Bornes du nombre d'Anomalies : bornes configurées ∩ `nb_semaines` × bornes d'Entrées."""
    volumetrie = config.volumetrie
    semaines = config.nb_semaines
    entrees_min = semaines * volumetrie.entrees_semaine_min
    entrees_max = semaines * volumetrie.entrees_semaine_max
    minimum = max(volumetrie.anomalies_min, entrees_min)
    maximum = min(volumetrie.anomalies_max, entrees_max)
    if minimum > maximum:
        raise UsineErreur(
            "volumétrie infaisable : Anomalies dans"
            f" [{volumetrie.anomalies_min}, {volumetrie.anomalies_max}], hors de"
            f" [{entrees_min}, {entrees_max}] ({semaines} semaines × Entrées par semaine dans"
            f" [{volumetrie.entrees_semaine_min}, {volumetrie.entrees_semaine_max}])"
        )
    return minimum, maximum


def _repartition_par_semaine(
    nombre: int, semaines: int, minimum: int, maximum: int, rng: random.Random
) -> list[int]:
    """`nombre` créations sur `semaines` : `minimum` par semaine, puis le complément tiré
    unité par unité parmi les semaines encore sous `maximum`."""
    repartition = [minimum] * semaines
    ouvertes = [s for s in range(semaines) if repartition[s] < maximum]
    for _ in range(nombre - minimum * semaines):
        indice = rng.randrange(len(ouvertes))
        semaine = ouvertes[indice]
        repartition[semaine] += 1
        if repartition[semaine] >= maximum:
            ouvertes.pop(indice)
    return repartition


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


def generer(
    config: ConfigProgramme,
    graine: int,
    date_generation: date,
    *,
    cle_projet: str = CLE_PROJET_ESSAI,
    corpus: Corpus | None = None,
) -> Generation:
    """Génère le Journal du Programme fictif pour `graine` et `date_generation`.

    Tirages dans un ordre fixe : nombre d'Anomalies (bornes d'Anomalies ∩ `nb_semaines` ×
    bornes d'Entrées), répartition par semaine, puis, semaine par semaine, le jour, l'Entité
    et le cycle de vie de chaque Anomalie ; enfin, Entité par Entité (ordre de la
    configuration), ses Cas de test et sa Certification. La Phase d'un ticket est celle du
    calendrier de la Vague de son Entité la semaine de sa création. Une réouverture n'est
    gardée que si sa semaine reste sous le maximum d'Entrées. Les clés `<cle_projet>-<n>`
    sont ensuite attribuées dans l'ordre chronologique de création.

    Titre et description forment une paire tirée d'un seul coup dans la case du `corpus`
    (défaut : Corpus provisoire des Domaines de `config`) : (Domaine, Cause racine) pour une
    Anomalie, Cas de test du Domaine, Certifications ; un Domaine absent du Corpus tire dans
    `generique`. L'en-tête reprend `version_corpus` et `modele_corpus`. Aucun appel LLM.
    """
    if corpus is None:
        corpus = corpus_provisoire(config.domaines)
    if graine < 0:
        # `Random(-n)` tire comme `Random(n)` : deux graines, un même Journal.
        raise UsineErreur(f"graine invalide : {graine} (entier ≥ 0 attendu)")
    _verifier_cle_projet(cle_projet)
    for vague in config.vagues:
        _verifier_phases(vague)
    anomalies_min, anomalies_max = _bornes_anomalies(config)
    ancrage, date_injection = fenetre_generation(date_generation, config.nb_semaines)
    volumetrie = config.volumetrie
    calendrier = _Calendrier(
        ancrage,
        jours_ouvres(ancrage, date_injection),
        {vague.code: vague for vague in config.vagues},
        volumetrie.entrees_semaine_max,
    )
    jours_par_semaine: dict[int, list[date]] = {}
    for jour in calendrier.jours:
        jours_par_semaine.setdefault(calendrier.semaine(jour), []).append(jour)
    rng = random.Random(graine)

    nb_anomalies = rng.randint(anomalies_min, anomalies_max)
    repartition = _repartition_par_semaine(
        nb_anomalies,
        config.nb_semaines,
        volumetrie.entrees_semaine_min,
        volumetrie.entrees_semaine_max,
        rng,
    )
    calendrier.entrees.update(enumerate(repartition, start=1))
    tickets: list[_Ticket] = []
    for semaine, nombre in enumerate(repartition, start=1):
        jours_semaine = jours_par_semaine[semaine]
        for _ in range(nombre):
            jour = rng.choice(jours_semaine)
            entite = rng.choice(config.entites)
            tickets.append(_anomalie(entite, jour, config.domaines, corpus, calendrier, rng))
    for entite in config.entites:
        nb_tests = rng.randint(*CAS_DE_TEST_PAR_ENTITE)
        tickets.extend(
            _cas_de_test(entite, config.domaines, corpus, calendrier, rng) for _ in range(nb_tests)
        )
        tickets.append(_certification(entite, corpus, calendrier.jours, rng))

    ordre = sorted(range(len(tickets)), key=lambda i: (tickets[i].creation, i))
    a_trier: list[tuple[datetime, int, int, Evenement]] = []
    verite: dict[str, CauseRacine] = {}
    for numero, indice in enumerate(ordre, start=1):
        ticket = tickets[indice]
        cle = f"{cle_projet}-{numero}"
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
        version_corpus=corpus.version_corpus,
        modele_corpus=corpus.modele_corpus,
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
