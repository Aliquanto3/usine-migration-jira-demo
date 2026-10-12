"""Scénarios de démo scriptés du générateur (Story 1.5, FR-3).

Trois Scénarios, chacun porté par une Entité, impriment au Journal une trajectoire visible
avec la Grille par défaut ; les autres Entités suivent le profil « normal » du générateur
(vert ou jaune). Les paramètres sont typés et validés ici, puis passés à `generer` :
`ConfigProgramme` (contrats gelés, `extra="forbid"`) n'accepte pas encore de clé
`scenarios` dans `config/programme.yaml` (report : prochaine version des contrats).

Les Scénarios ne changent pas la volumétrie : ils répartissent autrement, entre Entités, les
créations d'Anomalies d'une semaine (tirage de l'Entité par poids). Un Scénario dont l'Entité
est absente de la configuration est ignoré. Le calage au jour près relève de la Story 1.8 ;
ici, seule la forme des trajectoires est visée (Météo du dernier Jour ouvré de chaque
semaine).
"""

import math
from dataclasses import dataclass

from usine.contrats.erreurs import UsineErreur
from usine.contrats.tickets import StatutCertification


def _verifier_semaine(scenario: str, nom: str, valeur: int) -> None:
    if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < 1:
        raise UsineErreur(f"Scénario {scenario} : {nom} = {valeur!r} (semaine ≥ 1 attendue)")


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


@dataclass(frozen=True)
class ScenarioSortie:
    """Scénario A, « sortie de crise » : vague de bloquantes de reprise de données, puis décrue.

    Profil calme du générateur (sans bloquante, peu de majeures : vert ou jaune) avant
    `semaine_vague` et pendant la décrue. Pendant
    `semaine_vague`, l'Entité reçoit `poids_vague` fois la part de créations d'une Entité
    normale, dont `part_bloquantes_vague` de bloquantes de Cause racine « reprise de
    données », lentes à corriger : rouge par IND-1 (≥ 3 bloquantes ouvertes) dès la fin de
    cette semaine et jusqu'à la fin de l'historique. Les semaines suivantes (décrue), la part
    de créations tombe à `poids_decrue` : les Sorties dépassent les Entrées. Sa Certification
    (`statut_certification`) est créée en `semaine_certification`.
    """

    entite: str = "ENT-A"
    """Code de l'Entité du Scénario."""
    semaine_vague: int = 6
    """Semaine du Programme de la vague de bloquantes."""
    poids_vague: float = 1.5
    """Poids de l'Entité dans le tirage des créations pendant la vague (Entité normale : 1)."""
    part_bloquantes_vague: float = 0.4
    """Part des créations de la vague qui sont des bloquantes de reprise de données."""
    poids_decrue: float = 0.25
    """Poids de l'Entité dans le tirage des créations après la vague."""
    statut_certification: StatutCertification = StatutCertification.accordee
    """Statut de la Certification de l'Entité."""
    semaine_certification: int = 3
    """Semaine de création de la Certification."""

    def __post_init__(self) -> None:
        _verifier_entite("A", self.entite)
        _verifier_semaine("A", "semaine_vague", self.semaine_vague)
        _verifier_poids("A", "poids_vague", self.poids_vague)
        _verifier_taux("A", "part_bloquantes_vague", self.part_bloquantes_vague)
        _verifier_poids("A", "poids_decrue", self.poids_decrue)
        _verifier_semaine("A", "semaine_certification", self.semaine_certification)


@dataclass(frozen=True)
class ScenarioEnlisement:
    """Scénario B, « enlisement » : à partir de `semaine_debut`, plus de créations que les
    autres Entités (`poids`), beaucoup de majeures (`part_majeures`) et de bloquantes
    (`part_bloquantes`), toutes corrigées très lentement : les Entrées dépassent les Sorties
    chaque semaine, les bloquantes et les majeures s'accumulent (rouge par IND-1, IND-2 et
    IND-3) jusqu'à la fin de l'historique, sans sortie projetée. Sa Certification
    (`statut_certification`) est créée en `semaine_certification`.
    """

    entite: str = "ENT-B"
    """Code de l'Entité du Scénario."""
    semaine_debut: int = 2
    """Première semaine de l'enlisement."""
    poids: float = 3.0
    """Poids de l'Entité dans le tirage des créations dès `semaine_debut` (Entité normale : 1)."""
    part_bloquantes: float = 0.06
    """Part des créations enlisées qui sont bloquantes."""
    part_majeures: float = 0.3
    """Part des créations enlisées qui sont majeures (le reste : mineures)."""
    statut_certification: StatutCertification = StatutCertification.refusee
    """Statut de la Certification de l'Entité."""
    semaine_certification: int = 4
    """Semaine de création de la Certification."""

    def __post_init__(self) -> None:
        _verifier_entite("B", self.entite)
        _verifier_semaine("B", "semaine_debut", self.semaine_debut)
        _verifier_poids("B", "poids", self.poids)
        _verifier_taux("B", "part_bloquantes", self.part_bloquantes)
        _verifier_taux("B", "part_majeures", self.part_majeures)
        if self.part_bloquantes + self.part_majeures > 1:
            raise UsineErreur(
                f"Scénario B : part_bloquantes + part_majeures = {self.part_bloquantes}"
                f" + {self.part_majeures} > 1"
            )
        _verifier_semaine("B", "semaine_certification", self.semaine_certification)


@dataclass(frozen=True)
class ScenarioMenace:
    """Scénario C, « menace » : Cas de test nombreux dont le taux de KO monte.

    Chaque semaine, `cas_de_test_par_semaine` Cas de test sont créés et exécutés dans la
    semaine, avec un nombre exact de KO : `taux_ko_initial` avant `semaine_hausse`, puis
    `taux_ko_hausse` semaine après semaine (le dernier taux se répète), arrondi à l'unité la
    plus proche. Avec le calendrier livré, IND-4 reste sous 10 % jusqu'à la fin de la
    semaine 6 (vert puis jaune), puis le franchit en TNR (orange, sous 20 % : une menace, pas
    encore une crise). Une Certification réservée en `semaine_certification` donne le jaune
    par IND-6. Les Anomalies de l'Entité suivent le profil calme du générateur (sans
    bloquante, peu de majeures).
    """

    entite: str = "ENT-C"
    """Code de l'Entité du Scénario."""
    cas_de_test_par_semaine: int = 30
    """Cas de test créés et exécutés chaque semaine (au-dessus du garde-fou d'IND-4)."""
    taux_ko_initial: float = 0.03
    """Taux de KO des Cas de test exécutés avant `semaine_hausse`."""
    semaine_hausse: int = 4
    """Première semaine de la hausse du taux de KO."""
    taux_ko_hausse: tuple[float, ...] = (0.07, 0.10, 0.07, 0.17, 0.23)
    """Taux de KO hebdomadaires à partir de `semaine_hausse` ; le dernier se répète."""
    semaine_certification: int = 4
    """Semaine de création de la Certification, réservée."""

    def __post_init__(self) -> None:
        _verifier_entite("C", self.entite)
        nombre = self.cas_de_test_par_semaine
        if isinstance(nombre, bool) or not isinstance(nombre, int) or nombre < 1:
            raise UsineErreur(
                f"Scénario C : cas_de_test_par_semaine = {nombre!r} (entier ≥ 1 attendu)"
            )
        _verifier_taux("C", "taux_ko_initial", self.taux_ko_initial)
        _verifier_semaine("C", "semaine_hausse", self.semaine_hausse)
        if not isinstance(self.taux_ko_hausse, tuple) or not self.taux_ko_hausse:
            raise UsineErreur(
                f"Scénario C : taux_ko_hausse = {self.taux_ko_hausse!r} (tuple non vide attendu)"
            )
        for rang, taux in enumerate(self.taux_ko_hausse):
            _verifier_taux("C", f"taux_ko_hausse[{rang}]", taux)
        _verifier_semaine("C", "semaine_certification", self.semaine_certification)

    def taux_ko(self, semaine: int) -> float:
        """Taux de KO visé pour les Cas de test de la semaine `semaine`."""
        if semaine < self.semaine_hausse:
            return self.taux_ko_initial
        rang = min(semaine - self.semaine_hausse, len(self.taux_ko_hausse) - 1)
        return self.taux_ko_hausse[rang]

    def nombre_ko(self, semaine: int, executes: int) -> int:
        """Nombre exact de KO parmi `executes` Cas de test de la semaine (arrondi au plus
        proche, demi vers le haut)."""
        return min(executes, math.floor(self.taux_ko(semaine) * executes + 0.5))


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
        entites = [s.entite for s in (self.sortie, self.enlisement, self.menace) if s is not None]
        doublons = sorted({e for e in entites if entites.count(e) > 1})
        if doublons:
            raise UsineErreur(
                f"Scénarios : Entité portée par plusieurs Scénarios : {', '.join(doublons)}"
            )


AUCUN_SCENARIO = Scenarios()
"""Aucun Scénario : toutes les Entités suivent le profil normal."""

SCENARIOS_PAR_DEFAUT = Scenarios(
    sortie=ScenarioSortie(),
    enlisement=ScenarioEnlisement(),
    menace=ScenarioMenace(),
)
"""Scénarios A (`ENT-A`), B (`ENT-B`) et C (`ENT-C`) de la démo, calés sur le calendrier de la
Vague V1 livré (migration à blanc 1-2, recette 3-5, TNR 6-8)."""
