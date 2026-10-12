"""Scénarios de démo scriptés du générateur (Stories 1.5 et 1.8, FR-3).

Trois Scénarios, chacun porté par une Entité, impriment au Journal une trajectoire visible
avec la Grille par défaut ; les autres Entités suivent le profil « normal » du générateur
(vert ou jaune). Les paramètres sont typés et validés ici, puis passés à `generer`.

Depuis les contrats 1.1.0, ils se lisent dans la clé `scenarios` de `config/programme.yaml`
(`ConfigScenarios`, validée au chargement, convertie par `scenarios_de_config`) ; la
configuration livrée reprend `SCENARIOS_PAR_DEFAUT`, qui reste le repli d'une configuration
sans cette clé.

Les Scénarios ne changent pas la volumétrie : ils répartissent autrement, entre Entités, les
créations d'Anomalies d'une semaine (tirage de l'Entité par poids, bloquantes de bascule
prises sur les créations de la semaine). Un Scénario dont l'Entité est absente de la
configuration est ignoré.

Calage au jour près (Story 1.8) : avec la Grille par défaut et la configuration livrée, la
Météo de chaque Jour ouvré suit la trajectoire du Scénario. Les bascules tombent le premier
Jour ouvré d'une semaine (bloquantes de bascule de A et B, Certifications des Scénarios), et
les KO de C sont décidés jour par jour sur un taux cumulé visé dans la Phase en cours.
"""

import math
from collections.abc import Collection
from dataclasses import dataclass
from fractions import Fraction
from typing import ClassVar, Protocol

from usine.contrats.config import (
    ConfigScenarioEnlisement,
    ConfigScenarioMenace,
    ConfigScenarios,
    ConfigScenarioSortie,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.tickets import StatutCertification


def _verifier_semaine(scenario: str, nom: str, valeur: int) -> None:
    if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < 1:
        raise UsineErreur(f"Scénario {scenario} : {nom} = {valeur!r} (semaine ≥ 1 attendue)")


def _verifier_nombre(scenario: str, nom: str, valeur: int, minimum: int) -> None:
    if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < minimum:
        raise UsineErreur(f"Scénario {scenario} : {nom} = {valeur!r} (entier ≥ {minimum} attendu)")


def _verifier_taux(scenario: str, nom: str, valeur: float) -> None:
    if (
        isinstance(valeur, bool)
        or not isinstance(valeur, int | float)
        or math.isnan(valeur)
        or not 0 <= valeur <= 1
    ):
        raise UsineErreur(f"Scénario {scenario} : {nom} = {valeur!r} hors de [0, 1]")


def _verifier_poids(scenario: str, nom: str, valeur: float) -> None:
    if (
        isinstance(valeur, bool)
        or not isinstance(valeur, int | float)
        or not math.isfinite(valeur)
        or valeur <= 0
    ):
        raise UsineErreur(f"Scénario {scenario} : {nom} = {valeur!r} (poids > 0 attendu)")


def _verifier_entite(scenario: str, valeur: str) -> None:
    if not isinstance(valeur, str) or not valeur:
        raise UsineErreur(f"Scénario {scenario} : entite = {valeur!r} (code d'Entité attendu)")


JOURS_OUVRES_SEMAINE = 5
"""Jours ouvrés d'une semaine pleine (lundi à vendredi), base de la proratisation."""

DUREE_BLOQUANTE_MIN = 4
"""Durée minimale, en Jours ouvrés, d'une bloquante scriptée : ses quatre transitions
(En analyse, En correction, À retester, Fermée) tombent sur des Jours ouvrés distincts."""

DUREE_BLOQUANTE_MAX = 10
"""Durée maximale, en Jours ouvrés, d'une bloquante scriptée : la plus vieille bloquante
ouverte reste sous le seuil rouge d'IND-2 (10 Jours ouvrés), condition de SM-6."""


def part_du_jour(par_semaine: int, rang: int) -> int:
    """Part du `rang`-ième Jour ouvré d'une semaine (0 : lundi) dans `par_semaine` éléments
    répartis sur `JOURS_OUVRES_SEMAINE` Jours ouvrés, le reste aux premiers jours : une
    semaine pleine en compte exactement `par_semaine`, une semaine partielle ceux de ses
    jours."""
    base, reste = divmod(par_semaine, JOURS_OUVRES_SEMAINE)
    return base + (1 if rang < reste else 0)


def _verifier_flux(scenario: str, flux: tuple[int, ...], duree: int) -> None:
    if not isinstance(flux, tuple) or not flux:
        raise UsineErreur(
            f"Scénario {scenario} : bloquantes_par_semaine = {flux!r} (tuple non vide attendu)"
        )
    for rang, nombre in enumerate(flux):
        _verifier_nombre(scenario, f"bloquantes_par_semaine[{rang}]", nombre, 0)
    _verifier_nombre(scenario, "duree_bloquantes", duree, DUREE_BLOQUANTE_MIN)
    if duree > DUREE_BLOQUANTE_MAX:
        raise UsineErreur(
            f"Scénario {scenario} : duree_bloquantes = {duree!r}"
            f" (entier ≤ {DUREE_BLOQUANTE_MAX} attendu)"
        )


def _bloquantes_du_flux(
    debut: int, bascule: int, flux: tuple[int, ...], semaine: int, rang: int
) -> int:
    """Bloquantes scriptées du `rang`-ième Jour ouvré de `semaine` : `bascule` le premier Jour
    ouvré de `debut`, plus la part du jour de `flux[semaine − debut]` (dernier répété)."""
    if semaine < debut:
        return 0
    nombre = part_du_jour(flux[min(semaine - debut, len(flux) - 1)], rang)
    return nombre + (bascule if semaine == debut and rang == 0 else 0)


@dataclass(frozen=True)
class ScenarioSortie:
    """Scénario A, « sortie de crise » : vague de bloquantes de reprise de données, puis décrue.

    Profil calme du générateur (sans bloquante tirée, peu de majeures : vert ou jaune). Les
    bloquantes de A sont scriptées (Cause racine « reprise de données ») : le premier Jour
    ouvré de `semaine_vague`, `bloquantes_bascule` d'un coup (rouge par IND-1, ≥ 3 bloquantes
    ouvertes, dès ce jour-là), puis chaque semaine sa part de `bloquantes_par_semaine`
    répartie sur ses Jours ouvrés ; chacune est corrigée et fermée `duree_bloquantes` Jours
    ouvrés après sa création. La vague retombe dès la semaine suivante : les Sorties dépassent
    les Entrées, le stock baisse sans repasser sous 3 (rouge jusqu'à la fin) et, en fin
    d'historique, la plus ancienne bloquante ouverte a moins de 10 Jours ouvrés : la Baseline
    projette une sortie dans l'horizon (SM-6). Pendant la vague, l'Entité reçoit `poids_vague`
    fois la part de créations d'une Entité normale, puis `poids_decrue` fois. Sa Certification
    (`statut_certification`) est créée le premier Jour ouvré de `semaine_certification`.
    """

    LETTRE: ClassVar[str] = "A"

    entite: str = "ENT-A"
    """Code de l'Entité du Scénario."""
    semaine_vague: int = 6
    """Semaine du Programme de la vague de bloquantes."""
    bloquantes_bascule: int = 4
    """Bloquantes de reprise de données créées le premier Jour ouvré de la vague (entier ≥ 0),
    prises sur les créations de la semaine : elles fixent le jour de la bascule au rouge."""
    bloquantes_par_semaine: tuple[int, ...] = (9, 2, 4)
    """Bloquantes scriptées de la semaine de vague (hors bascule), puis de chaque semaine
    suivante (la dernière valeur se répète), réparties sur les Jours ouvrés (`part_du_jour`)."""
    duree_bloquantes: int = 7
    """Jours ouvrés entre la création et la fermeture d'une bloquante scriptée (4 à 10)."""
    poids_vague: float = 1.5
    """Poids de l'Entité dans le tirage des créations pendant la vague (Entité normale : 1)."""
    poids_decrue: float = 0.25
    """Poids de l'Entité dans le tirage des créations après la vague."""
    statut_certification: StatutCertification = StatutCertification.accordee
    """Statut de la Certification de l'Entité."""
    semaine_certification: int = 3
    """Semaine de création de la Certification (premier Jour ouvré)."""

    def __post_init__(self) -> None:
        _verifier_entite("A", self.entite)
        _verifier_semaine("A", "semaine_vague", self.semaine_vague)
        _verifier_nombre("A", "bloquantes_bascule", self.bloquantes_bascule, 0)
        _verifier_flux("A", self.bloquantes_par_semaine, self.duree_bloquantes)
        _verifier_poids("A", "poids_vague", self.poids_vague)
        _verifier_poids("A", "poids_decrue", self.poids_decrue)
        _verifier_semaine("A", "semaine_certification", self.semaine_certification)

    def semaines(self) -> tuple[tuple[str, int], ...]:
        """Semaines du Programme du Scénario, nommées par leur paramètre."""
        return (
            ("semaine_vague", self.semaine_vague),
            ("semaine_certification", self.semaine_certification),
        )

    def bloquantes(self, semaine: int, rang: int) -> int:
        """Bloquantes scriptées créées le `rang`-ième Jour ouvré de `semaine`."""
        return _bloquantes_du_flux(
            self.semaine_vague,
            self.bloquantes_bascule,
            self.bloquantes_par_semaine,
            semaine,
            rang,
        )


@dataclass(frozen=True)
class ScenarioEnlisement:
    """Scénario B, « enlisement » : les bloquantes arrivent plus vite qu'elles ne sortent.

    Les bloquantes de B sont scriptées : le premier Jour ouvré de `semaine_debut`,
    `bloquantes_bascule` d'un coup (rouge par IND-1 dès ce jour-là), puis chaque semaine sa
    part de `bloquantes_par_semaine`, en hausse ; chacune est fermée `duree_bloquantes` Jours
    ouvrés après sa création. Les Entrées de bloquantes dépassent leurs Sorties, le stock
    monte jusqu'à la fin de l'historique : vélocité nette défavorable, « pas de sortie
    projetée » (SM-6), la plus ancienne bloquante ouverte ayant moins de 10 Jours ouvrés.
    Dès `semaine_debut`, l'Entité reçoit plus de créations que les autres (`poids`), dont
    `part_majeures` de majeures aux délais du profil normal (le stock de majeures reste sous
    le seuil rouge d'IND-3) et des mineures corrigées lentement (`DELAIS_LENTS`) : les
    Entrées d'Anomalies dépassent les Sorties chaque semaine ; aucune bloquante tirée. Sa
    Certification (`statut_certification`) est créée le premier Jour ouvré de
    `semaine_certification`.
    """

    LETTRE: ClassVar[str] = "B"

    entite: str = "ENT-B"
    """Code de l'Entité du Scénario."""
    semaine_debut: int = 2
    """Première semaine de l'enlisement."""
    bloquantes_bascule: int = 3
    """Bloquantes créées le premier Jour ouvré de `semaine_debut` (entier ≥ 0), prises sur les
    créations de la semaine : elles fixent le jour de la bascule au rouge."""
    bloquantes_par_semaine: tuple[int, ...] = (3, 3, 4, 4, 5, 5, 6)
    """Bloquantes scriptées de `semaine_debut` (hors bascule), puis de chaque semaine suivante
    (la dernière valeur se répète), réparties sur les Jours ouvrés (`part_du_jour`)."""
    duree_bloquantes: int = 8
    """Jours ouvrés entre la création et la fermeture d'une bloquante scriptée (4 à 10)."""
    poids: float = 3.0
    """Poids de l'Entité dans le tirage des créations dès `semaine_debut` (Entité normale : 1)."""
    part_majeures: float = 0.03
    """Part des créations enlisées tirées qui sont majeures (le reste : mineures)."""
    statut_certification: StatutCertification = StatutCertification.reservee
    """Statut de la Certification de l'Entité (refusée, IND-5 rendrait la règle non
    projetable et masquerait « pas de sortie projetée »)."""
    semaine_certification: int = 4
    """Semaine de création de la Certification (premier Jour ouvré)."""

    def __post_init__(self) -> None:
        _verifier_entite("B", self.entite)
        _verifier_semaine("B", "semaine_debut", self.semaine_debut)
        _verifier_nombre("B", "bloquantes_bascule", self.bloquantes_bascule, 0)
        _verifier_flux("B", self.bloquantes_par_semaine, self.duree_bloquantes)
        _verifier_poids("B", "poids", self.poids)
        _verifier_taux("B", "part_majeures", self.part_majeures)
        _verifier_semaine("B", "semaine_certification", self.semaine_certification)

    def semaines(self) -> tuple[tuple[str, int], ...]:
        """Semaines du Programme du Scénario, nommées par leur paramètre."""
        return (
            ("semaine_debut", self.semaine_debut),
            ("semaine_certification", self.semaine_certification),
        )

    def bloquantes(self, semaine: int, rang: int) -> int:
        """Bloquantes scriptées créées le `rang`-ième Jour ouvré de `semaine`."""
        return _bloquantes_du_flux(
            self.semaine_debut,
            self.bloquantes_bascule,
            self.bloquantes_par_semaine,
            semaine,
            rang,
        )


@dataclass(frozen=True)
class ScenarioMenace:
    """Scénario C, « menace » : Cas de test nombreux dont le taux de KO monte.

    Chaque semaine, `cas_de_test_par_semaine` Cas de test sont répartis sur les Jours ouvrés
    (même nombre chaque jour d'une semaine pleine, le reste aux premiers jours) ; chacun est
    créé le matin et exécuté l'après-midi du même jour. Le taux visé de la semaine
    (`taux_ko`) est un plancher du taux de KO cumulé de la Phase en cours : chaque jour, le
    cumul des KO de la Phase est porté à `ko_cumules(semaine, exécutés de la Phase)`, sans
    jamais retirer un KO déjà compté. IND-4, cumulé par Phase et évalué en fin de journée,
    reste ainsi sous le taux visé, à moins d'un exécuté près, quel que soit le jour.

    Avec le calendrier livré (migration à blanc 1-2, recette 3-5, TNR 6-8) : vert jusqu'à la
    semaine 3 (IND-4 sous 5 %, IND-8 sous 3 points), jaune en semaines 4 à 6 par la
    Certification réservée (IND-6) créée le premier Jour ouvré de `semaine_certification`
    (IND-4 sous 10 %, IND-8 sous 5 points), puis orange dès le lundi de la semaine 7 (IND-4
    au-dessus de 10 % et sous 20 % : une menace, pas encore une crise). En fin d'historique,
    la régression d'IND-4 sur 10 Jours ouvrés franchit 20 % dans les 5 Jours ouvrés : Risque
    d'entrée en rouge (SM-6), quel que soit le jour de la semaine 8. Les Anomalies de
    l'Entité suivent le profil calme du générateur (sans bloquante, peu de majeures).
    """

    LETTRE: ClassVar[str] = "C"

    entite: str = "ENT-C"
    """Code de l'Entité du Scénario."""
    cas_de_test_par_semaine: int = 50
    """Cas de test d'une semaine pleine, créés et exécutés chaque Jour ouvré (10 par jour : le
    garde-fou d'IND-4, 20 exécutés, est franchi le deuxième Jour ouvré d'une Phase ; la
    fenêtre de 10 Jours ouvrés du Risque d'entrée en rouge reste évaluable dès le lundi de la
    semaine 8, Story 4.5)."""
    taux_ko_initial: float = 0.03
    """Taux de KO cumulé visé avant `semaine_hausse`."""
    semaine_hausse: int = 4
    """Première semaine de la hausse du taux de KO visé."""
    taux_ko_hausse: tuple[float, ...] = (0.045, 0.065, 0.07, 0.14, 0.18)
    """Taux de KO cumulés visés semaine après semaine à partir de `semaine_hausse` ; le dernier
    se répète. 0,045 et 0,065 (et non 0,05) gardent IND-8 sous 5 points en recette (Story
    1.8). 0,18 en semaine 8 (et non 0,17) donne au Risque d'entrée en rouge une marge nette
    le vendredi : projection à 5 Jours ouvrés de 22 % au lieu de 19,8 % (Story 4.5)."""
    semaine_certification: int = 4
    """Semaine de création de la Certification, réservée (premier Jour ouvré)."""

    def __post_init__(self) -> None:
        _verifier_entite("C", self.entite)
        _verifier_nombre("C", "cas_de_test_par_semaine", self.cas_de_test_par_semaine, 1)
        _verifier_taux("C", "taux_ko_initial", self.taux_ko_initial)
        _verifier_semaine("C", "semaine_hausse", self.semaine_hausse)
        if not isinstance(self.taux_ko_hausse, tuple) or not self.taux_ko_hausse:
            raise UsineErreur(
                f"Scénario C : taux_ko_hausse = {self.taux_ko_hausse!r} (tuple non vide attendu)"
            )
        for rang, taux in enumerate(self.taux_ko_hausse):
            _verifier_taux("C", f"taux_ko_hausse[{rang}]", taux)
        _verifier_semaine("C", "semaine_certification", self.semaine_certification)

    def semaines(self) -> tuple[tuple[str, int], ...]:
        """Semaines du Programme du Scénario, nommées par leur paramètre."""
        return (
            ("semaine_hausse", self.semaine_hausse),
            ("semaine_certification", self.semaine_certification),
        )

    def taux_ko(self, semaine: int) -> float:
        """Taux de KO cumulé visé dans la Phase en cours pendant la semaine `semaine`."""
        if semaine < self.semaine_hausse:
            return self.taux_ko_initial
        rang = min(semaine - self.semaine_hausse, len(self.taux_ko_hausse) - 1)
        return self.taux_ko_hausse[rang]

    def ko_cumules(self, semaine: int, executes: int) -> int:
        """KO cumulés visés de la Phase en cours pour `executes` Cas de test exécutés dans la
        Phase, en semaine `semaine` : ⌊taux visé × exécutés⌋, calculé en décimal exact."""
        return min(executes, math.floor(Fraction(str(self.taux_ko(semaine))) * executes))


class _Scenario(Protocol):
    """Ce que `scenarios_applicables` lit d'un Scénario."""

    @property
    def entite(self) -> str: ...

    def semaines(self) -> tuple[tuple[str, int], ...]: ...


@dataclass(frozen=True)
class Scenarios:
    """Les trois Scénarios de démo ; `None` désactive un Scénario. Entités distinctes."""

    sortie: ScenarioSortie | None = None
    """Scénario A."""
    enlisement: ScenarioEnlisement | None = None
    """Scénario B."""
    menace: ScenarioMenace | None = None
    """Scénario C."""

    def __post_init__(self) -> None:
        entites = [s.entite for s in self.actifs()]
        doublons = sorted({e for e in entites if entites.count(e) > 1})
        if doublons:
            raise UsineErreur(
                f"Scénarios : Entité portée par plusieurs Scénarios : {', '.join(doublons)}"
            )

    def actifs(self) -> tuple[ScenarioSortie | ScenarioEnlisement | ScenarioMenace, ...]:
        """Scénarios non désactivés, dans l'ordre A, B, C."""
        return tuple(s for s in (self.sortie, self.enlisement, self.menace) if s is not None)

    def resume(self) -> str:
        """« A (ENT-A), B (ENT-B), C (ENT-C) », ou « aucun »."""
        return ", ".join(f"{s.LETTRE} ({s.entite})" for s in self.actifs()) or "aucun"


def _tient(scenario: _Scenario | None, codes: Collection[str], derniere_semaine: int) -> bool:
    return (
        scenario is not None
        and scenario.entite in codes
        and all(semaine <= derniere_semaine for _, semaine in scenario.semaines())
    )


def scenarios_applicables(
    scenarios: Scenarios, codes: Collection[str], derniere_semaine: int
) -> Scenarios:
    """Scénarios de `scenarios` dont l'Entité est parmi `codes` et dont toutes les semaines
    tiennent dans l'historique (≤ `derniere_semaine`) ; les autres sont désactivés.

    `generer` réduit ainsi les Scénarios par défaut d'un programme court ; des Scénarios
    fournis explicitement sont d'abord contrôlés strictement (une semaine hors de
    l'historique est refusée).
    """
    return Scenarios(
        sortie=scenarios.sortie if _tient(scenarios.sortie, codes, derniere_semaine) else None,
        enlisement=(
            scenarios.enlisement if _tient(scenarios.enlisement, codes, derniere_semaine) else None
        ),
        menace=scenarios.menace if _tient(scenarios.menace, codes, derniere_semaine) else None,
    )


AUCUN_SCENARIO = Scenarios()
"""Aucun Scénario : toutes les Entités suivent le profil normal."""

SCENARIOS_PAR_DEFAUT = Scenarios(
    sortie=ScenarioSortie(),
    enlisement=ScenarioEnlisement(),
    menace=ScenarioMenace(),
)
"""Scénarios A (`ENT-A`), B (`ENT-B`) et C (`ENT-C`) de la démo, calés au jour près sur le
calendrier de la Vague V1 livré (migration à blanc 1-2, recette 3-5, TNR 6-8) ; `generer` les
applique par défaut quand la configuration ne porte pas de clé `scenarios`, réduits à ceux qui
tiennent dans l'historique (`scenarios_applicables`). `config/programme.yaml` en reprend les
valeurs."""


def _sortie(config: ConfigScenarioSortie) -> ScenarioSortie:
    return ScenarioSortie(
        entite=config.entite,
        semaine_vague=config.semaine_vague,
        bloquantes_bascule=config.bloquantes_bascule,
        bloquantes_par_semaine=tuple(config.bloquantes_par_semaine),
        duree_bloquantes=config.duree_bloquantes,
        poids_vague=config.poids_vague,
        poids_decrue=config.poids_decrue,
        statut_certification=config.statut_certification,
        semaine_certification=config.semaine_certification,
    )


def _enlisement(config: ConfigScenarioEnlisement) -> ScenarioEnlisement:
    return ScenarioEnlisement(
        entite=config.entite,
        semaine_debut=config.semaine_debut,
        bloquantes_bascule=config.bloquantes_bascule,
        bloquantes_par_semaine=tuple(config.bloquantes_par_semaine),
        duree_bloquantes=config.duree_bloquantes,
        poids=config.poids,
        part_majeures=config.part_majeures,
        statut_certification=config.statut_certification,
        semaine_certification=config.semaine_certification,
    )


def _menace(config: ConfigScenarioMenace) -> ScenarioMenace:
    return ScenarioMenace(
        entite=config.entite,
        cas_de_test_par_semaine=config.cas_de_test_par_semaine,
        taux_ko_initial=config.taux_ko_initial,
        semaine_hausse=config.semaine_hausse,
        taux_ko_hausse=tuple(config.taux_ko_hausse),
        semaine_certification=config.semaine_certification,
    )


def scenarios_de_config(config: ConfigScenarios) -> Scenarios:
    """Scénarios du générateur à partir de la clé `scenarios` de `config/programme.yaml`.

    Un Scénario absent de la configuration est désactivé. Les contrôles de `ConfigScenarios`
    (au chargement) et ceux des dataclasses portent sur les mêmes règles.
    """
    return Scenarios(
        sortie=None if config.sortie is None else _sortie(config.sortie),
        enlisement=None if config.enlisement is None else _enlisement(config.enlisement),
        menace=None if config.menace is None else _menace(config.menace),
    )
