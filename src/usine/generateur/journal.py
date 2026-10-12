"""Générateur déterministe du Journal d'événements (Stories 0.3, 1.1 à 1.5 et 1.8, FR-2 à FR-4).

Cœur pur : ni horloge, ni `random` global, ni I/O. La sortie ne dépend que de
`(config, graine, date_generation, cle_projet, corpus, scenarios)` (la clé de projet ne fixe
que le préfixe des clés de tickets) ; tout le hasard vient d'une seule instance de
`Random` initialisée par la graine, tirée dans un ordre fixe. Seule `ecrire_journal` écrit
sur disque : le Journal, la vérité terrain et la liste des identifiants injectés d'une
`Generation`.
"""

import json
import logging
import random
import re
from collections.abc import Collection, Mapping, Sequence
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
from usine.contrats.config import (
    ConfigProgramme,
    EntiteProgramme,
    VagueProgramme,
    VolumetrieProgramme,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import EnteteJournal, Evenement, NatureEvenement, SourceEvenement
from usine.contrats.passage import CHEMIN_JOURNAL, CHEMIN_VERITE_TERRAIN
from usine.contrats.tickets import (
    CHAMPS_PAR_TYPE,
    STATUTS_FERMES,
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
from usine.generateur.identifiants import IdentifiantInjecte, TypeIdentifiant, phrase_identifiants
from usine.generateur.scenarios import (
    AUCUN_SCENARIO,
    JOURS_OUVRES_SEMAINE,
    SCENARIOS_PAR_DEFAUT,
    ScenarioEnlisement,
    ScenarioMenace,
    Scenarios,
    ScenarioSortie,
    part_du_jour,
    scenarios_applicables,
    scenarios_de_config,
)
from usine.generateur.textes import corpus_provisoire

_log = logging.getLogger(__name__)

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

HEURE_MIDI = 13
"""Début de l'après-midi : les Cas de test du Scénario C sont créés le matin (8 h à 12 h 59)
et exécutés l'après-midi (13 h à 17 h 59) du même Jour ouvré."""

TRANSITIONS_MAX = 12
"""Garde : nombre maximal de transitions de statut par Anomalie (boucles de retest et
réouvertures comprises)."""

DELAIS_PAR_STATUT: Mapping[StatutAnomalie, tuple[int, int]] = MappingProxyType(
    {
        StatutAnomalie.nouvelle: (1, 2),
        StatutAnomalie.en_analyse: (1, 3),
        StatutAnomalie.en_correction: (2, 5),
        StatutAnomalie.a_retester: (1, 3),
        StatutAnomalie.fermee: (2, 10),
        StatutAnomalie.rejetee: (2, 10),
    }
)
"""Bornes, en Jours ouvrés (≥ 1), du séjour d'une Anomalie mineure du profil normal dans un
statut avant l'étape suivante : un cycle complet Nouvelle → Fermée dure environ deux semaines."""

DELAIS_BLOQUANTE_NORMALE: Mapping[StatutAnomalie, tuple[int, int]] = MappingProxyType(
    {
        **DELAIS_PAR_STATUT,
        StatutAnomalie.nouvelle: (1, 1),
        StatutAnomalie.en_analyse: (1, 1),
        StatutAnomalie.en_correction: (1, 2),
        StatutAnomalie.a_retester: (1, 1),
    }
)
"""Délais prioritaires d'une bloquante du profil normal : traitée en une semaine environ."""

DELAIS_MAJEURE_NORMALE: Mapping[StatutAnomalie, tuple[int, int]] = MappingProxyType(
    {
        **DELAIS_PAR_STATUT,
        StatutAnomalie.nouvelle: (1, 2),
        StatutAnomalie.en_analyse: (1, 2),
        StatutAnomalie.en_correction: (1, 3),
        StatutAnomalie.a_retester: (1, 2),
    }
)
"""Délais d'une majeure du profil normal, plus courts que ceux d'une mineure."""

DELAIS_LENTS: Mapping[StatutAnomalie, tuple[int, int]] = MappingProxyType(
    {
        **DELAIS_PAR_STATUT,
        StatutAnomalie.nouvelle: (1, 3),
        StatutAnomalie.en_analyse: (3, 6),
        StatutAnomalie.en_correction: (15, 30),
        StatutAnomalie.a_retester: (2, 4),
    }
)
"""Délais d'une mineure tirée enlisée du Scénario B (ses majeures gardent les délais du profil
normal, `_DELAIS_ENLISES`) : la correction dure de trois à six semaines."""

POIDS_GRAVITE_NORMAL: tuple[int, int, int] = (2, 40, 958)
"""Poids (pour mille) des gravités bloquante, majeure et mineure du profil normal : bloquantes
rares, majeures peu nombreuses ; les mineures, invisibles pour la Grille, portent l'essentiel
de la volumétrie."""

STATUTS_CERTIFICATION_NORMAUX: tuple[StatutCertification, ...] = (
    StatutCertification.accordee,
    StatutCertification.reservee,
)
"""Statuts tirés pour la Certification d'une Entité normale : jamais refusée."""

MARGE_REOUVERTURES_POURCENT = 10
"""Part (en %) du maximum d'Entrées d'une semaine laissée libre par les créations, pour les
réouvertures."""


CAS_DE_TEST_PAR_ENTITE = (2, 3)
"""Bornes du nombre de Cas de test d'une Entité hors Scénario C."""

PROBA_EXECUTION_TEST = 0.7
"""Probabilité qu'un Cas de test soit exécuté (passage à `ok` ou `ko`)."""

PROBA_TEST_OK = 0.6
"""Probabilité qu'un Cas de test exécuté soit `ok`."""

PROBA_REJET = 0.15
"""Probabilité qu'une Anomalie en analyse soit rejetée."""

PROBA_RETOUR_CORRECTION = 0.2
"""Probabilité qu'un nouveau test renvoie l'Anomalie en correction."""

PROBA_REOUVERTURE = 0.1
"""Probabilité qu'une Anomalie fermée ou rejetée soit rouverte (retour en analyse)."""

PROPORTION_IDENTIFIANTS_POURCENT = 15
"""Part (en %, arrondie au-dessus) des Anomalies dont la description porte des identifiants
sensibles fictifs (FR-4 : au moins 10 %)."""

NOM_IDENTIFIANTS = "identifiants_injectes.json"
"""Nom du fichier des identifiants injectés, écrit à côté du Journal (sous `donnees/`, hors
git) et lu par le test de balayage de la Pseudonymisation. Constante du générateur :
`contrats.passage` est gelé."""


@dataclass(frozen=True)
class Generation:
    """Résultat d'une génération : en-tête, événements du Journal, vérité terrain et
    identifiants injectés."""

    entete: EnteteJournal
    evenements: tuple[Evenement, ...]
    verite_terrain: Mapping[str, CauseRacine]
    """Cause racine de chaque Anomalie, par clé de ticket ; jamais dans le Journal."""
    identifiants: tuple[IdentifiantInjecte, ...] = ()
    """Identifiants sensibles fictifs insérés dans les descriptions, triés par numéro de clé."""
    scenarios: Scenarios = AUCUN_SCENARIO
    """Scénarios de démo appliqués : ceux dont l'Entité est dans la configuration et dont les
    semaines tiennent dans l'historique."""


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
    identifiants: tuple[tuple[TypeIdentifiant, str], ...] = ()
    """Identifiants fictifs ajoutés à la description, avant attribution de la clé."""


_GRAVITES: tuple[Gravite, ...] = (Gravite.bloquante, Gravite.majeure, Gravite.mineure)
"""Ordre des gravités des poids d'un `_Profil`."""


@dataclass(frozen=True)
class _Profil:
    """Tirage d'une Anomalie : poids des gravités et délais par gravité."""

    poids_gravite: tuple[float, float, float]
    delais: Mapping[Gravite, Mapping[StatutAnomalie, tuple[int, int]]]


_DELAIS_NORMAUX: Mapping[Gravite, Mapping[StatutAnomalie, tuple[int, int]]] = MappingProxyType(
    {
        Gravite.bloquante: DELAIS_BLOQUANTE_NORMALE,
        Gravite.majeure: DELAIS_MAJEURE_NORMALE,
        Gravite.mineure: DELAIS_PAR_STATUT,
    }
)

_DELAIS_ENLISES: Mapping[Gravite, Mapping[StatutAnomalie, tuple[int, int]]] = MappingProxyType(
    {**_DELAIS_NORMAUX, Gravite.mineure: DELAIS_LENTS}
)
"""Délais des Anomalies tirées de B pendant l'enlisement : mineures lentes."""

PROFIL_NORMAL = _Profil(POIDS_GRAVITE_NORMAL, _DELAIS_NORMAUX)
"""Profil des Entités hors Scénario : vise le vert ou le jaune avec la Grille par défaut."""

POIDS_GRAVITE_CALME: tuple[int, int, int] = (0, 20, 980)
"""Poids (pour mille) des gravités du profil calme : aucune bloquante, deux fois moins de
majeures qu'au profil normal."""

PROFIL_CALME = _Profil(POIDS_GRAVITE_CALME, _DELAIS_NORMAUX)
"""Profil d'une Entité scénarisée hors des semaines de son Scénario : pour que sa trajectoire
ne dépende pas d'une bloquante tirée au hasard (IND-1 est orange dès une bloquante ouverte)
ni d'une rafale de majeures (IND-7 au-delà de son garde-fou), pas de bloquante et peu de
majeures."""


def _profil(code: str, semaine: int, scenarios: Scenarios) -> _Profil:
    """Profil de tirage d'une Anomalie de l'Entité `code` créée en semaine `semaine`.

    B : dès sa semaine de début, part de majeures du Scénario aux délais du profil normal (le
    stock de majeures reste sous le seuil rouge d'IND-3), mineures lentes, aucune bloquante
    tirée. A (ses bloquantes sont scriptées, `_bloquantes_scriptees`), B avant l'enlisement
    et C : `PROFIL_CALME` ; Entité sans Scénario : `PROFIL_NORMAL`.
    """
    sortie, enlisement, menace = scenarios.sortie, scenarios.enlisement, scenarios.menace
    if enlisement is not None and code == enlisement.entite and semaine >= enlisement.semaine_debut:
        majeures = enlisement.part_majeures
        return _Profil((0.0, majeures, 1 - majeures), _DELAIS_ENLISES)
    if code in {s.entite for s in (sortie, enlisement, menace) if s is not None}:
        return PROFIL_CALME
    return PROFIL_NORMAL


def _verifier_semaines_scenarios(
    scenarios: Scenarios, codes: Collection[str], derniere: int
) -> None:
    """Refuse une semaine de Scénario au-delà de la dernière semaine générée `derniere`,
    pour un Scénario dont l'Entité est parmi `codes` (sinon il est ignoré)."""
    for scenario in scenarios.actifs():
        if scenario.entite not in codes:
            continue
        for nom, semaine in scenario.semaines():
            if semaine > derniere:
                raise UsineErreur(
                    f"Scénario {scenario.LETTRE} : {nom} = {semaine} au-delà de la dernière"
                    f" semaine générée ({derniere})"
                )


@dataclass(frozen=True)
class _Scriptees:
    """Bloquantes scriptées d'une Entité un Jour ouvré donné."""

    entite: EntiteProgramme
    jour: date
    nombre: int
    duree: int
    """Jours ouvrés entre la création et la fermeture."""
    cause: CauseRacine | None
    """Cause racine imposée (`None` : tirée)."""


def _bloquantes_scriptees(
    entites: tuple[EntiteProgramme, ...],
    semaine: int,
    jours_semaine: Sequence[date],
    scenarios: Scenarios,
) -> list[_Scriptees]:
    """Bloquantes scriptées de la semaine `semaine`, jour par jour, B puis A.

    B : Cause racine tirée ; A : Cause racine « reprise de données » imposée. Prises sur les
    créations de la semaine dans cet ordre : quand elles ne suffisent pas (programme réduit),
    l'enlisement de B, rouge jusqu'à la fin, est servi d'abord.
    """
    par_code = {entite.code: entite for entite in entites}
    lots: list[_Scriptees] = []
    sources: tuple[tuple[ScenarioSortie | ScenarioEnlisement | None, CauseRacine | None], ...] = (
        (scenarios.enlisement, None),
        (scenarios.sortie, CauseRacine.reprise_donnees),
    )
    for scenario, cause in sources:
        if scenario is None or scenario.entite not in par_code:
            continue
        for rang, jour in enumerate(jours_semaine):
            nombre = scenario.bloquantes(semaine, rang)
            if nombre > 0:
                entite = par_code[scenario.entite]
                lots.append(_Scriptees(entite, jour, nombre, scenario.duree_bloquantes, cause))
    return lots


def _poids_entites(
    entites: tuple[EntiteProgramme, ...], semaine: int, scenarios: Scenarios
) -> list[float]:
    """Poids de chaque Entité dans le tirage des créations de la semaine `semaine`.

    1 pour une Entité normale ; A : `poids_vague` pendant sa vague, `poids_decrue` après ;
    B : `poids` dès sa semaine de début.
    """
    sortie, enlisement = scenarios.sortie, scenarios.enlisement
    poids: list[float] = []
    for entite in entites:
        valeur = 1.0
        if sortie is not None and entite.code == sortie.entite:
            if semaine == sortie.semaine_vague:
                valeur = sortie.poids_vague
            elif semaine > sortie.semaine_vague:
                valeur = sortie.poids_decrue
        if (
            enlisement is not None
            and entite.code == enlisement.entite
            and semaine >= enlisement.semaine_debut
        ):
            valeur = enlisement.poids
        poids.append(valeur)
    return poids


def _horodatage(
    jour: date, rng: random.Random, heures: tuple[int, int] = (HEURE_DEBUT, HEURE_FIN)
) -> datetime:
    """Instant tiré le jour `jour`, heure de Paris dans `[heures[0], heures[1])` (défaut :
    heures ouvrées), rendu en UTC."""
    heure = rng.randrange(*heures)
    minute = rng.randrange(60)
    return datetime.combine(jour, time(heure, minute), tzinfo=FUSEAU).astimezone(UTC)


def _jours_ulterieurs(
    jours: tuple[date, ...], jour: date, nombre: int, rng: random.Random
) -> list[date]:
    """Jusqu'à `nombre` Jours ouvrés distincts strictement après `jour`, triés."""
    candidats = [j for j in jours if j > jour]
    return sorted(rng.sample(candidats, min(nombre, len(candidats))))


def _statut_suivant(statut: StatutAnomalie, rng: random.Random) -> StatutAnomalie | None:
    """Statut suivant le long du workflow H-17 ; `None` si le statut terminal n'est pas rouvert.

    Nouvelle → En analyse → En correction ou Rejetée ; En correction → À retester → Fermée
    ou retour En correction ; Fermée ou Rejetée → En analyse (réouverture).
    """
    match statut:
        case StatutAnomalie.nouvelle:
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
        case StatutAnomalie.fermee | StatutAnomalie.rejetee:
            if rng.random() < PROBA_REOUVERTURE:
                return StatutAnomalie.en_analyse
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
    entrees_max: Mapping[int, int]
    """Maximum d'Entrées de chaque semaine, proratisé à ses Jours ouvrés."""
    entrees: dict[int, int] = field(default_factory=dict)
    """Entrées (créations et réouvertures) par semaine du Programme."""

    def semaine(self, jour: date) -> int:
        return semaine_programme(jour, self.ancrage)

    def phase(self, entite: EntiteProgramme, jour: date) -> Phase:
        return _phase_du_calendrier(self.vagues[entite.vague], self.semaine(jour))

    _rangs: dict[date, int] = field(init=False, repr=False)
    """Rang de chaque Jour ouvré dans `jours`."""

    def __post_init__(self) -> None:
        self._rangs = {jour: rang for rang, jour in enumerate(self.jours)}

    def jour_apres(self, jour: date, delai: int) -> date | None:
        """Jour ouvré `delai` Jours ouvrés après `jour` ; `None` au-delà de la Date d'injection."""
        if jour not in self._rangs:
            raise UsineErreur(f"{jour.isoformat()} : hors des Jours ouvrés de l'historique")
        rang = self._rangs[jour] + delai
        return self.jours[rang] if rang < len(self.jours) else None

    def accepter_reouverture(self, jour: date) -> bool:
        """Compte une réouverture le jour `jour` si sa semaine reste sous le maximum d'Entrées."""
        semaine = self.semaine(jour)
        if self.entrees.get(semaine, 0) >= self.entrees_max[semaine]:
            return False
        self.entrees[semaine] = self.entrees.get(semaine, 0) + 1
        return True


def _nouvelle_anomalie(
    entite: EntiteProgramme,
    jour: date,
    creation: datetime,
    gravite: Gravite,
    cause: CauseRacine | None,
    domaines: tuple[str, ...],
    corpus: Corpus,
    calendrier: _Calendrier,
    rng: random.Random,
) -> _Ticket:
    """Anomalie créée à `creation` (jour `jour`), statut Nouvelle, sans transition : Domaine
    tiré, Cause racine `cause` ou tirée, titre et description tirés dans la case du Corpus."""
    phase = calendrier.phase(entite, jour)
    domaine = rng.choice(domaines)
    if cause is None:
        cause = rng.choice(tuple(CauseRacine))
    case = corpus.textes_domaine(domaine).anomalies[cause]
    titre, description = _textes(case, entite.code, domaine, rng)
    return _Ticket(
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


_ETAPES_SCRIPTEES: tuple[tuple[StatutAnomalie, StatutAnomalie], ...] = (
    (StatutAnomalie.nouvelle, StatutAnomalie.en_analyse),
    (StatutAnomalie.en_analyse, StatutAnomalie.en_correction),
    (StatutAnomalie.en_correction, StatutAnomalie.a_retester),
    (StatutAnomalie.a_retester, StatutAnomalie.fermee),
)
"""Transitions d'une bloquante scriptée : le workflow H-17 sans rejet, retour ni réouverture."""


def _bloquante_scriptee(
    lot: _Scriptees,
    domaines: tuple[str, ...],
    corpus: Corpus,
    calendrier: _Calendrier,
    rng: random.Random,
) -> _Ticket:
    """Bloquante scriptée de `lot` : créée le jour `lot.jour`, En analyse à J+1, En correction
    à J+2, À retester à J+duree−1 et Fermée à J+duree (Jours ouvrés) ; les transitions
    au-delà de la Date d'injection ne sont pas émises (bloquante encore ouverte)."""
    ticket = _nouvelle_anomalie(
        lot.entite,
        lot.jour,
        _horodatage(lot.jour, rng),
        Gravite.bloquante,
        lot.cause,
        domaines,
        corpus,
        calendrier,
        rng,
    )
    decalages = (1, 2, lot.duree - 1, lot.duree)
    for decalage, (de, vers) in zip(decalages, _ETAPES_SCRIPTEES, strict=True):
        jour_transition = calendrier.jour_apres(lot.jour, decalage)
        if jour_transition is None:
            break
        ticket.changements.append(
            _Changement(
                _horodatage(jour_transition, rng),
                NatureEvenement.transition,
                Champ.statut,
                de.value,
                vers.value,
            )
        )
    return ticket


def _anomalie(
    entite: EntiteProgramme,
    jour: date,
    domaines: tuple[str, ...],
    corpus: Corpus,
    calendrier: _Calendrier,
    profil: _Profil,
    rng: random.Random,
) -> _Ticket:
    creation = _horodatage(jour, rng)
    gravite = rng.choices(_GRAVITES, weights=profil.poids_gravite)[0]
    ticket = _nouvelle_anomalie(
        entite, jour, creation, gravite, None, domaines, corpus, calendrier, rng
    )
    delais = profil.delais[gravite]
    # Marche le long du workflow : séjour tiré en Jours ouvrés (≥ 1) dans chaque statut, d'où
    # des transitions sur des jours distincts, arrêtée à la Date d'injection.
    statut = StatutAnomalie.nouvelle
    jour_courant = jour
    for _ in range(TRANSITIONS_MAX):
        jour_transition = calendrier.jour_apres(jour_courant, rng.randint(*delais[statut]))
        if jour_transition is None:
            break
        suivant = _statut_suivant(statut, rng)
        if suivant is None:
            break
        # Une réouverture est une Entrée : refusée si sa semaine a atteint son maximum.
        if statut in STATUTS_FERMES and not calendrier.accepter_reouverture(jour_transition):
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
        jour_courant = jour_transition
    return ticket


def _nouveau_cas_de_test(
    entite: EntiteProgramme,
    jour: date,
    domaines: tuple[str, ...],
    corpus: Corpus,
    calendrier: _Calendrier,
    rng: random.Random,
    heures: tuple[int, int] = (HEURE_DEBUT, HEURE_FIN),
) -> _Ticket:
    """Cas de test non exécuté créé le jour `jour` (heure tirée dans `heures`), Phase du
    calendrier ce jour-là."""
    creation = _horodatage(jour, rng, heures)
    phase = calendrier.phase(entite, jour)
    domaine = rng.choice(domaines)
    case = corpus.textes_domaine(domaine).cas_de_test
    titre, description = _textes(case, entite.code, domaine, rng)
    return _Ticket(
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


def _executer(
    ticket: _Ticket,
    jour: date,
    resultat: StatutTest,
    rng: random.Random,
    heures: tuple[int, int] = (HEURE_DEBUT, HEURE_FIN),
) -> None:
    """Exécution du Cas de test le jour `jour` (heure tirée dans `heures`) : passage de non
    exécuté à `resultat`."""
    ticket.changements.append(
        _Changement(
            _horodatage(jour, rng, heures),
            NatureEvenement.modification_champ,
            Champ.statut_test,
            StatutTest.non_execute.value,
            resultat.value,
        )
    )


def _cas_de_test(
    entite: EntiteProgramme,
    domaines: tuple[str, ...],
    corpus: Corpus,
    calendrier: _Calendrier,
    rng: random.Random,
) -> _Ticket:
    """Cas de test du profil normal : créé un jour tiré, exécuté ou non, résultat tiré."""
    jours = calendrier.jours
    jour = rng.choice(jours)
    ticket = _nouveau_cas_de_test(entite, jour, domaines, corpus, calendrier, rng)
    if rng.random() < PROBA_EXECUTION_TEST:
        resultat = StatutTest.ok if rng.random() < PROBA_TEST_OK else StatutTest.ko
        for jour_execution in _jours_ulterieurs(jours, jour, 1, rng):
            _executer(ticket, jour_execution, resultat, rng)
    return ticket


def _cas_du_jour(par_semaine: int, rang: int) -> int:
    """Cas de test du Scénario C du `rang`-ième Jour ouvré d'une semaine (0 : lundi).

    `par_semaine` réparti comme les bloquantes scriptées de A et B (`part_du_jour`) : le reste
    aux premiers jours ; une semaine pleine en compte exactement `par_semaine`.
    """
    return part_du_jour(par_semaine, rang)


def _cas_de_test_menace(
    entite: EntiteProgramme,
    scenario: ScenarioMenace,
    jours_par_semaine: Mapping[int, list[date]],
    domaines: tuple[str, ...],
    corpus: Corpus,
    calendrier: _Calendrier,
    rng: random.Random,
) -> list[_Ticket]:
    """Cas de test du Scénario C, Jour ouvré par Jour ouvré.

    Chaque Jour ouvré reçoit sa part de `cas_de_test_par_semaine` (`_cas_du_jour`) : chaque
    Cas de test est créé le matin et exécuté l'après-midi du même jour, Phase du calendrier
    ce jour-là. Les exécutés et les KO sont cumulés par Phase ; les KO du jour portent le
    cumul de la Phase à `ko_cumules(semaine, exécutés de la Phase)` (jamais moins que les KO
    déjà comptés, au plus les Cas de test du jour), tirés par `rng.sample` ; les autres sont
    OK. IND-4, cumulé par Phase en fin de journée, suit ainsi le taux visé au jour près.
    """
    tickets: list[_Ticket] = []
    cumuls: dict[Phase, tuple[int, int]] = {}  # exécutés et KO cumulés, par Phase
    for semaine, jours in sorted(jours_par_semaine.items()):
        for rang_jour, jour in enumerate(jours):
            nombre = _cas_du_jour(scenario.cas_de_test_par_semaine, rang_jour)
            phase = calendrier.phase(entite, jour)
            executes, ko_comptes = cumuls.get(phase, (0, 0))
            executes += nombre
            ko_du_jour = min(nombre, max(0, scenario.ko_cumules(semaine, executes) - ko_comptes))
            cumuls[phase] = (executes, ko_comptes + ko_du_jour)
            ko = set(rng.sample(range(nombre), ko_du_jour))
            for rang in range(nombre):
                ticket = _nouveau_cas_de_test(
                    entite, jour, domaines, corpus, calendrier, rng, (HEURE_DEBUT, HEURE_MIDI)
                )
                resultat = StatutTest.ko if rang in ko else StatutTest.ok
                _executer(ticket, jour, resultat, rng, (HEURE_MIDI, HEURE_FIN))
                tickets.append(ticket)
    return tickets


def _certification(
    entite: EntiteProgramme,
    corpus: Corpus,
    jours: Sequence[date],
    rng: random.Random,
    statut: StatutCertification | None = None,
) -> _Ticket:
    """Certification créée un jour tiré dans `jours` ; statut imposé par un Scénario, ou tiré
    parmi `STATUTS_CERTIFICATION_NORMAUX`."""
    creation = _horodatage(rng.choice(jours), rng)
    if statut is None:
        statut = rng.choice(STATUTS_CERTIFICATION_NORMAUX)
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


def _injecter_identifiants(tickets: list[_Ticket], rng: random.Random) -> None:
    """Ajoute une phrase d'identifiants fictifs à la description de ⌈15 %⌉ des Anomalies.

    Anomalies tirées par `rng.sample`, puis traitées dans l'ordre de construction de la
    liste des tickets.
    """
    anomalies = [i for i, t in enumerate(tickets) if t.type_ticket is TypeTicket.anomalie]
    nombre = -(-len(anomalies) * PROPORTION_IDENTIFIANTS_POURCENT // 100)
    for indice in sorted(rng.sample(anomalies, nombre)):
        ticket = tickets[indice]
        phrase, identifiants = phrase_identifiants(ticket.attributs[Champ.entite], rng)
        ticket.attributs[Champ.description] = f"{ticket.attributs[Champ.description]} {phrase}"
        ticket.identifiants = identifiants


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


def _bornes_entrees(
    volumetrie: VolumetrieProgramme, jours_par_semaine: Mapping[int, int]
) -> dict[int, tuple[int, int]]:
    """`(minimum, maximum)` d'Entrées de chaque semaine, proratisés à ses Jours ouvrés.

    Une semaine de `n` Jours ouvrés sur 5 a pour bornes ⌊min × n / 5⌋ et ⌈max × n / 5⌉ : une
    semaine pleine garde les bornes configurées.
    """
    return {
        semaine: (
            volumetrie.entrees_semaine_min * nombre // JOURS_OUVRES_SEMAINE,
            -(-volumetrie.entrees_semaine_max * nombre // JOURS_OUVRES_SEMAINE),
        )
        for semaine, nombre in jours_par_semaine.items()
    }


def _bornes_anomalies(
    volumetrie: VolumetrieProgramme, bornes_entrees: Mapping[int, tuple[int, int]]
) -> tuple[int, int, dict[int, int]]:
    """`(minimum, maximum, plafonds)` : bornes du nombre d'Anomalies et plafond de créations
    de chaque semaine.

    Bornes : bornes configurées ∩ [Σ minimums, Σ maximums] d'Entrées des semaines. Plafond
    d'une semaine : son maximum moins `MARGE_REOUVERTURES_POURCENT` % (arrondi bas), au moins
    son minimum, pour laisser place aux réouvertures ; le maximum d'Anomalies est alors
    ramené à Σ plafonds. Si Σ plafonds est sous le minimum d'Anomalies, pas de marge :
    plafond = maximum de la semaine.
    """
    entrees_min = sum(minimum for minimum, _ in bornes_entrees.values())
    entrees_max = sum(maximum for _, maximum in bornes_entrees.values())
    minimum = max(volumetrie.anomalies_min, entrees_min)
    maximum = min(volumetrie.anomalies_max, entrees_max)
    if minimum > maximum:
        raise UsineErreur(
            "volumétrie infaisable : Anomalies dans"
            f" [{volumetrie.anomalies_min}, {volumetrie.anomalies_max}], hors de"
            f" [{entrees_min}, {entrees_max}] ({len(bornes_entrees)} semaines × Entrées par"
            f" semaine dans [{volumetrie.entrees_semaine_min}, {volumetrie.entrees_semaine_max}],"
            " proratisées aux Jours ouvrés d'une semaine partielle)"
        )
    plafonds = {
        semaine: max(mini, maxi - maxi * MARGE_REOUVERTURES_POURCENT // 100)
        for semaine, (mini, maxi) in bornes_entrees.items()
    }
    if minimum <= sum(plafonds.values()):
        return minimum, min(maximum, sum(plafonds.values())), plafonds
    return minimum, maximum, {semaine: maxi for semaine, (_, maxi) in bornes_entrees.items()}


def _repartition_par_semaine(
    nombre: int, minimums: list[int], plafonds: list[int], rng: random.Random
) -> list[int]:
    """`nombre` créations sur les semaines : son minimum à chaque semaine, puis le complément
    tiré unité par unité parmi les semaines encore sous leur plafond."""
    repartition = list(minimums)
    ouvertes = [s for s in range(len(repartition)) if repartition[s] < plafonds[s]]
    for _ in range(nombre - sum(minimums)):
        indice = rng.randrange(len(ouvertes))
        semaine = ouvertes[indice]
        repartition[semaine] += 1
        if repartition[semaine] >= plafonds[semaine]:
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
    scenarios: Scenarios | None = None,
) -> Generation:
    """Génère le Journal du Programme fictif pour `graine` et `date_generation`.

    Les bornes d'Entrées d'une semaine sont proratisées à ses Jours ouvrés (dernière semaine
    partielle). Tirages dans un ordre fixe : nombre d'Anomalies (bornes d'Anomalies ∩ Σ
    bornes d'Entrées, sous Σ plafonds de créations qui réservent une marge aux
    réouvertures), répartition par semaine, puis, semaine par semaine, le jour, l'Entité et
    le cycle de vie de chaque Anomalie ; enfin, Entité par Entité (ordre de la
    configuration), ses Cas de test et sa Certification ; en dernier, les identifiants
    sensibles fictifs (`_injecter_identifiants`) : ce tirage ne change que les descriptions
    des Anomalies choisies, le reste du Journal d'une graine est inchangé.

    Scénarios de démo (Stories 1.5 et 1.8) : `scenarios` omis (`None`), ceux de
    `config.scenarios` (contrats 1.1.0, `scenarios_de_config`) ou, sans cette clé,
    `SCENARIOS_PAR_DEFAUT`, réduits à ceux qui tiennent dans l'historique
    (`scenarios_applicables` : un programme court génère sans erreur) ; des Scénarios
    explicites sont contrôlés strictement (une semaine au-delà de la dernière semaine générée
    est refusée), `AUCUN_SCENARIO` les désactive. Un Scénario dont l'Entité est absente de
    `config` est sans effet ; `Generation.scenarios` porte les Scénarios appliqués. La
    semaine de bascule de A (vague) et de B (début de l'enlisement), les `bloquantes_bascule`
    premières créations de la semaine sont des bloquantes lentes de l'Entité, créées le
    premier Jour ouvré (bascule au rouge ce jour-là) ; les autres créations ont leur Entité
    tirée par poids
    (`_poids_entites` : B renforcé dès sa semaine de début, A renforcé pendant sa vague puis
    réduit pendant sa décrue), sans changer le nombre de créations de la semaine ; la
    gravité, la Cause racine des bloquantes et les délais suivent le profil de l'Entité
    cette semaine-là (`_profil` ; Entité sans Scénario : `PROFIL_NORMAL` ; Entité scénarisée
    hors de ses semaines : `PROFIL_CALME`). L'Entité de C reçoit les Cas de test du Scénario
    (`_cas_de_test_menace`, KO décidés jour par jour) au lieu des Cas de test normaux ; la
    Certification de A, B et C a le statut du Scénario et est créée le premier Jour ouvré de
    sa semaine ; celle d'une autre Entité est accordée ou réservée, un jour tiré.

    Cycle de vie : marche le long du workflow H-17 (`_statut_suivant`), un séjour tiré en
    Jours ouvrés (délais du profil, par gravité) dans chaque statut, arrêtée au-delà de la Date
    d'injection, sur un statut fermé non rouvert ou après `TRANSITIONS_MAX` transitions. Une
    réouverture (depuis Fermée ou Rejetée) n'est gardée que si sa semaine reste sous le
    maximum d'Entrées. La Phase d'un ticket est celle du calendrier de la Vague de son
    Entité la semaine de sa création. Les clés `<cle_projet>-<n>` sont ensuite attribuées
    dans l'ordre chronologique de création.

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
    ancrage, date_injection = fenetre_generation(date_generation, config.nb_semaines)
    jours = jours_ouvres(ancrage, date_injection)
    jours_par_semaine: dict[int, list[date]] = {}
    for jour in jours:
        jours_par_semaine.setdefault(semaine_programme(jour, ancrage), []).append(jour)
    codes = {entite.code for entite in config.entites}
    derniere_semaine = max(jours_par_semaine)
    if scenarios is None:
        scenarios = (
            SCENARIOS_PAR_DEFAUT
            if config.scenarios is None
            else scenarios_de_config(config.scenarios)
        )
    else:
        _verifier_semaines_scenarios(scenarios, codes, derniere_semaine)
    scenarios = scenarios_applicables(scenarios, codes, derniere_semaine)
    bornes_entrees = _bornes_entrees(
        config.volumetrie, {s: len(j) for s, j in sorted(jours_par_semaine.items())}
    )
    anomalies_min, anomalies_max, plafonds = _bornes_anomalies(config.volumetrie, bornes_entrees)
    calendrier = _Calendrier(
        ancrage,
        jours,
        {vague.code: vague for vague in config.vagues},
        {semaine: maximum for semaine, (_, maximum) in bornes_entrees.items()},
    )
    rng = random.Random(graine)

    nb_anomalies = rng.randint(anomalies_min, anomalies_max)
    semaines = sorted(bornes_entrees)
    repartition = _repartition_par_semaine(
        nb_anomalies,
        [bornes_entrees[s][0] for s in semaines],
        [plafonds[s] for s in semaines],
        rng,
    )
    calendrier.entrees.update(zip(semaines, repartition, strict=True))
    tickets: list[_Ticket] = []
    for semaine, nombre in zip(semaines, repartition, strict=True):
        jours_semaine = jours_par_semaine[semaine]
        restantes = nombre
        for lot in _bloquantes_scriptees(config.entites, semaine, jours_semaine, scenarios):
            servies = min(lot.nombre, restantes)
            if servies < lot.nombre:
                _log.warning(
                    "Semaine %d, %s : %d bloquante(s) scriptée(s) sur %d le %s, faute de"
                    " créations dans la semaine (%d tirées)",
                    semaine,
                    lot.entite.code,
                    servies,
                    lot.nombre,
                    lot.jour.isoformat(),
                    nombre,
                )
            for _ in range(servies):
                tickets.append(_bloquante_scriptee(lot, config.domaines, corpus, calendrier, rng))
            restantes -= servies
        poids = _poids_entites(config.entites, semaine, scenarios)
        for _ in range(restantes):
            jour = rng.choice(jours_semaine)
            entite = rng.choices(config.entites, weights=poids)[0]
            profil = _profil(entite.code, semaine, scenarios)
            tickets.append(
                _anomalie(entite, jour, config.domaines, corpus, calendrier, profil, rng)
            )
    certifications = {
        s.entite: (s.statut_certification, s.semaine_certification)
        for s in (scenarios.sortie, scenarios.enlisement)
        if s is not None
    }
    if scenarios.menace is not None:
        certifications[scenarios.menace.entite] = (
            StatutCertification.reservee,
            scenarios.menace.semaine_certification,
        )
    for entite in config.entites:
        menace = scenarios.menace
        if menace is not None and entite.code == menace.entite:
            tickets.extend(
                _cas_de_test_menace(
                    entite, menace, jours_par_semaine, config.domaines, corpus, calendrier, rng
                )
            )
        else:
            nb_tests = rng.randint(*CAS_DE_TEST_PAR_ENTITE)
            tickets.extend(
                _cas_de_test(entite, config.domaines, corpus, calendrier, rng)
                for _ in range(nb_tests)
            )
        if entite.code in certifications:
            statut, semaine_certification = certifications[entite.code]
            # Applicable : sa semaine tient dans l'historique ; créée son premier Jour ouvré.
            premier_jour = jours_par_semaine[semaine_certification][:1]
            tickets.append(_certification(entite, corpus, premier_jour, rng, statut))
        else:
            tickets.append(_certification(entite, corpus, calendrier.jours, rng))
    _injecter_identifiants(tickets, rng)

    ordre = sorted(range(len(tickets)), key=lambda i: (tickets[i].creation, i))
    a_trier: list[tuple[datetime, int, int, Evenement]] = []
    verite: dict[str, CauseRacine] = {}
    identifiants: list[IdentifiantInjecte] = []
    for numero, indice in enumerate(ordre, start=1):
        ticket = tickets[indice]
        cle = f"{cle_projet}-{numero}"
        if ticket.cause is not None:
            verite[cle] = ticket.cause
        identifiants.extend(IdentifiantInjecte(cle, t, valeur) for t, valeur in ticket.identifiants)
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
    return Generation(entete, evenements, MappingProxyType(verite), tuple(identifiants), scenarios)


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


def serialiser_identifiants(generation: Generation) -> bytes:
    """Identifiants injectés : `[{cle_ticket, type, valeur}]` en JSON, triés par numéro de clé
    (ordre de la phrase pour une même clé), UTF-8, fin de ligne `\\n`."""
    contenu = [
        {"cle_ticket": i.cle_ticket, "type": i.type.value, "valeur": i.valeur}
        for i in generation.identifiants
    ]
    texte = json.dumps(contenu, ensure_ascii=False, indent=2)
    return (texte + "\n").encode("utf-8")


def ecrire_journal(generation: Generation, repertoire: Path) -> Path:
    """Écrit le Journal, la vérité terrain et les identifiants injectés dans `repertoire` ;
    renvoie le chemin du Journal.

    Les noms du Journal et de la vérité terrain sont ceux de `contrats.passage`
    (`journal.jsonl`, `verite_terrain.json`), celui de la liste est `NOM_IDENTIFIANTS`. Une
    erreur d'écriture lève une `UsineErreur` qui nomme le répertoire.
    """
    journal = repertoire / CHEMIN_JOURNAL.name
    try:
        repertoire.mkdir(parents=True, exist_ok=True)
        journal.write_bytes(serialiser_journal(generation))
        (repertoire / CHEMIN_VERITE_TERRAIN.name).write_bytes(serialiser_verite(generation))
        (repertoire / NOM_IDENTIFIANTS).write_bytes(serialiser_identifiants(generation))
    except OSError as exc:
        raise UsineErreur(f"{repertoire} : écriture impossible ({exc.strerror or exc})") from exc
    return journal
