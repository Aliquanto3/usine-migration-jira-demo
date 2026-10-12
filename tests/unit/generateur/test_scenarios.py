"""Scénarios de démo scriptés (Story 1.5, FR-3) : paramètres, Journal et Météo de fin de semaine.

Seule la forme des trajectoires est vérifiée, sur la Météo du dernier Jour ouvré de chaque
semaine avec la Grille livrée (seuils inchangés, SM-C3) ; le calage au jour près relève de la
Story 1.8.
"""

from collections import Counter, defaultdict
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from usine.config import charger_yaml
from usine.contrats.calendrier import jour_local, jours_ouvres, semaine_programme
from usine.contrats.config import ConfigProgramme, GrilleMeteo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import NatureEvenement
from usine.contrats.meteo import Couleur
from usine.contrats.tickets import (
    CauseRacine,
    Champ,
    Gravite,
    StatutCertification,
    StatutTest,
    TypeTicket,
)
from usine.domaine.instantanes import tickets_etats
from usine.domaine.meteo import meteo
from usine.generateur.journal import CAS_DE_TEST_PAR_ENTITE, Generation, generer, serialiser_journal
from usine.generateur.scenarios import (
    AUCUN_SCENARIO,
    SCENARIOS_PAR_DEFAUT,
    ScenarioEnlisement,
    ScenarioMenace,
    Scenarios,
    ScenarioSortie,
)

RACINE = Path(__file__).resolve().parents[3]
PROGRAMME_LIVRE = RACINE / "config" / "programme.yaml"
PROGRAMME_REDUIT = Path(__file__).with_name("programme_reduit.yaml")
GRILLE_LIVREE = RACINE / "config" / "grille_meteo.yaml"
DATE_GENERATION = date(2026, 10, 12)
GRAINE = 42
SEMAINES = range(1, 9)
SCENARISEES = ("ENT-A", "ENT-B", "ENT-C")
FERMES = {"fermee", "rejetee"}
VERT_OU_JAUNE = {Couleur.vert, Couleur.jaune}


# --- Paramètres ---


@pytest.mark.parametrize(
    ("fabrique", "parametre"),
    [
        (lambda: ScenarioSortie(semaine_vague=0), "semaine_vague"),
        (lambda: ScenarioSortie(semaine_certification=-1), "semaine_certification"),
        (lambda: ScenarioSortie(poids_vague=0), "poids_vague"),
        (lambda: ScenarioSortie(poids_decrue=-0.5), "poids_decrue"),
        (lambda: ScenarioSortie(part_bloquantes_vague=1.2), "part_bloquantes_vague"),
        (lambda: ScenarioSortie(entite=""), "entite"),
        (lambda: ScenarioEnlisement(semaine_debut=0), "semaine_debut"),
        (lambda: ScenarioEnlisement(poids=float("inf")), "poids"),
        (lambda: ScenarioEnlisement(part_majeures=-0.1), "part_majeures"),
        (lambda: ScenarioEnlisement(part_bloquantes=float("nan")), "part_bloquantes"),
        (
            lambda: ScenarioEnlisement(part_bloquantes=0.6, part_majeures=0.5),
            "part_bloquantes + part_majeures",
        ),
        (lambda: ScenarioMenace(taux_ko_initial=1.5), "taux_ko_initial"),
        (lambda: ScenarioMenace(taux_ko_hausse=(0.1, -0.1)), "taux_ko_hausse[1]"),
        (lambda: ScenarioMenace(taux_ko_hausse=()), "taux_ko_hausse"),
        (lambda: ScenarioMenace(semaine_hausse=0), "semaine_hausse"),
        (lambda: ScenarioMenace(cas_de_test_par_semaine=0), "cas_de_test_par_semaine"),
        (lambda: ScenarioMenace(semaine_certification=0), "semaine_certification"),
        (
            lambda: Scenarios(sortie=ScenarioSortie(), menace=ScenarioMenace(entite="ENT-A")),
            "ENT-A",
        ),
    ],
)
def test_parametre_invalide_refuse(fabrique: Any, parametre: str) -> None:
    with pytest.raises(UsineErreur) as erreur:
        fabrique()
    assert parametre in str(erreur.value)


def test_scenarios_par_defaut() -> None:
    assert SCENARIOS_PAR_DEFAUT.sortie is not None
    assert SCENARIOS_PAR_DEFAUT.enlisement is not None
    assert SCENARIOS_PAR_DEFAUT.menace is not None
    entites = (
        SCENARIOS_PAR_DEFAUT.sortie.entite,
        SCENARIOS_PAR_DEFAUT.enlisement.entite,
        SCENARIOS_PAR_DEFAUT.menace.entite,
    )
    assert entites == SCENARISEES


def test_nombre_ko_par_semaine() -> None:
    menace = ScenarioMenace(taux_ko_initial=0.03, semaine_hausse=4, taux_ko_hausse=(0.07, 0.5))
    assert [menace.nombre_ko(s, 30) for s in SEMAINES] == [1, 1, 1, 2, 15, 15, 15, 15]
    assert ScenarioMenace(taux_ko_initial=1).nombre_ko(1, 7) == 7


# --- Entité absente : Scénario ignoré ---


@pytest.fixture(scope="module")
def config_reduite() -> ConfigProgramme:
    return charger_yaml(PROGRAMME_REDUIT, ConfigProgramme)


def test_scenario_sans_son_entite_ignore(config_reduite: ConfigProgramme) -> None:
    """Configuration réduite (ENT-A, ENT-B) : le Scénario C n'a aucun effet."""
    sans_c = Scenarios(sortie=ScenarioSortie(), enlisement=ScenarioEnlisement())

    def journal(scenarios: Scenarios) -> bytes:
        return serialiser_journal(
            generer(config_reduite, GRAINE, DATE_GENERATION, scenarios=scenarios)
        )

    assert journal(SCENARIOS_PAR_DEFAUT) == journal(sans_c)
    assert journal(Scenarios(menace=ScenarioMenace())) == journal(AUCUN_SCENARIO)
    autre = Scenarios(menace=ScenarioMenace(entite="ENT-Z"), sortie=ScenarioSortie(entite="ENT-Y"))
    assert journal(autre) == journal(AUCUN_SCENARIO)


@pytest.mark.parametrize(
    ("scenarios", "attendu"),
    [
        (Scenarios(sortie=ScenarioSortie(semaine_vague=9)), "Scénario A : semaine_vague = 9"),
        (
            Scenarios(sortie=ScenarioSortie(semaine_certification=12)),
            "Scénario A : semaine_certification = 12",
        ),
        (
            Scenarios(enlisement=ScenarioEnlisement(semaine_debut=9)),
            "Scénario B : semaine_debut = 9",
        ),
        (
            Scenarios(enlisement=ScenarioEnlisement(semaine_certification=10)),
            "Scénario B : semaine_certification = 10",
        ),
    ],
)
def test_semaine_au_dela_de_l_historique_refusee(
    config_reduite: ConfigProgramme, scenarios: Scenarios, attendu: str
) -> None:
    with pytest.raises(UsineErreur) as erreur:
        generer(config_reduite, GRAINE, DATE_GENERATION, scenarios=scenarios)
    assert attendu in str(erreur.value)
    assert "dernière semaine générée (8)" in str(erreur.value)


def test_semaine_au_dela_ignoree_sans_l_entite(config_reduite: ConfigProgramme) -> None:
    """Scénario C sans ENT-C dans la configuration : semaines non contrôlées, ignoré."""
    scenarios = Scenarios(menace=ScenarioMenace(semaine_hausse=20, semaine_certification=20))
    generer(config_reduite, GRAINE, DATE_GENERATION, scenarios=scenarios)


def test_entite_absente_generation_normale(config_reduite: ConfigProgramme) -> None:
    generation = generer(
        config_reduite, GRAINE, DATE_GENERATION, scenarios=Scenarios(menace=ScenarioMenace())
    )
    attributs = _attributs(generation)
    tests = Counter(
        a[Champ.entite] for a in attributs.values() if a["type"] is TypeTicket.cas_de_test
    )
    assert set(tests) == {"ENT-A", "ENT-B"}
    assert all(CAS_DE_TEST_PAR_ENTITE[0] <= n <= CAS_DE_TEST_PAR_ENTITE[1] for n in tests.values())


# --- Outils de lecture du Journal ---


def _attributs(generation: Generation) -> dict[str, dict[Any, Any]]:
    """Attributs initiaux de chaque ticket, avec son type et sa semaine de création."""
    ancrage = generation.entete.ancrage_semaines
    attributs: dict[str, dict[Any, Any]] = defaultdict(dict)
    for e in generation.evenements:
        if e.nature is NatureEvenement.creation:
            attributs[e.cle_ticket]["type"] = e.type_ticket
            attributs[e.cle_ticket]["semaine"] = semaine_programme(
                jour_local(e.horodatage), ancrage
            )
        elif e.nature is NatureEvenement.modification_champ and e.de is None and e.champ:
            attributs[e.cle_ticket][e.champ] = e.vers
    return attributs


def _entrees_sorties(generation: Generation) -> tuple[Counter[Any], Counter[Any]]:
    """Entrées et Sorties d'Anomalies, par (Entité, semaine du Programme)."""
    ancrage = generation.entete.ancrage_semaines
    entites = {
        e.cle_ticket: e.vers
        for e in generation.evenements
        if e.champ is Champ.entite and e.de is None
    }
    entrees: Counter[Any] = Counter()
    sorties: Counter[Any] = Counter()
    for e in generation.evenements:
        if e.type_ticket is not TypeTicket.anomalie:
            continue
        cle = (entites[e.cle_ticket], semaine_programme(jour_local(e.horodatage), ancrage))
        if e.nature is NatureEvenement.creation or (
            e.nature is NatureEvenement.transition and e.de in FERMES
        ):
            entrees[cle] += 1
        if e.nature is NatureEvenement.transition and e.vers in FERMES:
            sorties[cle] += 1
    return entrees, sorties


def _ko_par_semaine(generation: Generation, entite: str) -> dict[int, Fraction]:
    """Taux de KO des Cas de test de l'Entité exécutés chaque semaine."""
    ancrage = generation.entete.ancrage_semaines
    entites = {
        e.cle_ticket: e.vers
        for e in generation.evenements
        if e.champ is Champ.entite and e.de is None
    }
    executes: Counter[int] = Counter()
    ko: Counter[int] = Counter()
    for e in generation.evenements:
        if e.champ is Champ.statut_test and e.de is not None and entites[e.cle_ticket] == entite:
            semaine = semaine_programme(jour_local(e.horodatage), ancrage)
            executes[semaine] += 1
            ko[semaine] += e.vers == StatutTest.ko
    return {s: Fraction(ko[s], executes[s]) for s in sorted(executes)}


# --- Configuration livrée : Journal ---


@pytest.fixture(scope="module")
def config_livree() -> ConfigProgramme:
    return charger_yaml(PROGRAMME_LIVRE, ConfigProgramme)


@pytest.fixture(scope="module")
def generation_livree(config_livree: ConfigProgramme) -> Generation:
    return generer(config_livree, GRAINE, DATE_GENERATION)


def test_volumetrie_tenue(config_livree: ConfigProgramme, generation_livree: Generation) -> None:
    """Les Scénarios répartissent les créations d'une semaine, ils n'en ajoutent pas."""
    volumetrie = config_livree.volumetrie
    entrees, _ = _entrees_sorties(generation_livree)
    par_semaine = Counter[int]()
    for (_, semaine), nombre in entrees.items():
        par_semaine[semaine] += nombre
    assert sorted(par_semaine) == list(SEMAINES)
    assert all(
        volumetrie.entrees_semaine_min <= n <= volumetrie.entrees_semaine_max
        for n in par_semaine.values()
    ), par_semaine
    assert 3000 <= len(generation_livree.verite_terrain) <= 3600


def test_scenario_a_journal(generation_livree: Generation) -> None:
    """A : bloquantes « reprise de données » à partir de la semaine 6, Sorties > Entrées en
    semaines 7 et 8."""
    attributs = _attributs(generation_livree)
    bloquantes_a = {
        cle: a["semaine"]
        for cle, a in attributs.items()
        if a[Champ.entite] == "ENT-A"
        and a["type"] is TypeTicket.anomalie
        and a[Champ.gravite] == Gravite.bloquante
    }
    reprise = Counter(
        semaine
        for cle, semaine in bloquantes_a.items()
        if generation_livree.verite_terrain[cle] is CauseRacine.reprise_donnees
    )
    assert reprise, "aucune bloquante « reprise de données » pour ENT-A"
    assert min(reprise) == 6, reprise
    assert reprise[6] >= 3, reprise
    # Toutes les bloquantes de la vague sont de reprise de données (Cause racine imposée).
    assert reprise[6] == Counter(bloquantes_a.values())[6], bloquantes_a
    entrees, sorties = _entrees_sorties(generation_livree)
    for semaine in (7, 8):
        assert sorties["ENT-A", semaine] > entrees["ENT-A", semaine], semaine


def test_scenario_b_journal(generation_livree: Generation) -> None:
    """B : Entrées > Sorties de la semaine 2 à la fin."""
    entrees, sorties = _entrees_sorties(generation_livree)
    for semaine in range(2, 9):
        assert entrees["ENT-B", semaine] > sorties["ENT-B", semaine], semaine


def test_scenario_c_journal(generation_livree: Generation) -> None:
    """C : taux de KO hebdomadaire plus haut dès la semaine 4 qu'en semaines 1 à 3, croissant
    en TNR (semaines 6 à 8) et au-dessus de 10 % sur la TNR."""
    taux = _ko_par_semaine(generation_livree, "ENT-C")
    assert sorted(taux) == list(SEMAINES)
    assert min(taux[s] for s in range(4, 9)) > max(taux[s] for s in range(1, 4)), taux
    assert taux[6] < taux[7] < taux[8], taux
    attributs = _attributs(generation_livree)
    tnr = [
        a
        for a in attributs.values()
        if a[Champ.entite] == "ENT-C" and a["type"] is TypeTicket.cas_de_test and a["semaine"] >= 6
    ]
    assert {a[Champ.phase] for a in tnr} == {"tnr"}
    assert taux[6] < Fraction(1, 10) <= taux[7], taux


def test_certifications(generation_livree: Generation) -> None:
    """A accordée, B refusée, C réservée en semaine 4 ; aucune autre Entité refusée."""
    certifications = {
        a[Champ.entite]: (a[Champ.statut_certification], a["semaine"])
        for a in _attributs(generation_livree).values()
        if a["type"] is TypeTicket.certification
    }
    assert certifications["ENT-A"] == (StatutCertification.accordee, 3)
    assert certifications["ENT-B"] == (StatutCertification.refusee, 4)
    assert certifications["ENT-C"] == (StatutCertification.reservee, 4)
    autres = {e: s for e, (s, _) in certifications.items() if e not in SCENARISEES}
    assert len(autres) == 7
    assert StatutCertification.refusee not in autres.values()


# --- Météo du dernier Jour ouvré de chaque semaine, Grille livrée ---


def _meteo_fin_de_semaine(
    config: ConfigProgramme, generation: Generation
) -> dict[str, list[Couleur]]:
    """Couleur de chaque Entité au dernier Jour ouvré de chaque semaine."""
    grille = charger_yaml(GRILLE_LIVREE, GrilleMeteo)
    ancrage = generation.entete.ancrage_semaines
    jours = jours_ouvres(ancrage, generation.entete.date_injection)
    derniers: dict[int, date] = {}
    for jour in jours:
        derniers[semaine_programme(jour, ancrage)] = jour
    etats = tickets_etats(generation.evenements, jours)
    codes = [e.code for e in config.entites]
    couleurs: dict[str, list[Couleur]] = defaultdict(list)
    for semaine in sorted(derniers):
        for m in meteo(
            etats, derniers[semaine], codes, grille, "v", programme=config, ancrage=ancrage
        ):
            couleurs[m.entite].append(m.couleur)
    return couleurs


@pytest.fixture(scope="module")
def meteo_livree(
    config_livree: ConfigProgramme, generation_livree: Generation
) -> dict[str, list[Couleur]]:
    return _meteo_fin_de_semaine(config_livree, generation_livree)


def test_meteo_scenario_a(meteo_livree: dict[str, list[Couleur]]) -> None:
    a = meteo_livree["ENT-A"]
    assert set(a[:5]) <= VERT_OU_JAUNE, a
    assert set(a[5:]) == {Couleur.rouge}, a


def test_meteo_scenario_b(meteo_livree: dict[str, list[Couleur]]) -> None:
    b = meteo_livree["ENT-B"]
    assert set(b[1:]) == {Couleur.rouge}, b


def test_meteo_scenario_c(meteo_livree: dict[str, list[Couleur]]) -> None:
    c = meteo_livree["ENT-C"]
    assert set(c[:6]) <= VERT_OU_JAUNE, c
    assert Couleur.jaune in c[3:6], c
    assert set(c[6:]) == {Couleur.orange}, c


def test_meteo_hors_scenarios(meteo_livree: dict[str, list[Couleur]]) -> None:
    """Hors A, B, C : au moins 80 % des couples verts ou jaunes, aucune rouge en fin
    d'historique."""
    autres = {e: c for e, c in meteo_livree.items() if e not in SCENARISEES}
    assert len(autres) == 7
    couples = [couleur for couleurs in autres.values() for couleur in couleurs]
    assert sum(c in VERT_OU_JAUNE for c in couples) >= 0.8 * len(couples), autres
    assert all(couleurs[-1] is not Couleur.rouge for couleurs in autres.values()), autres


# --- Programme réduit ---


def test_programme_reduit_une_entite_rouge(config_reduite: ConfigProgramme) -> None:
    """Graine 42, Programme réduit : au moins une Entité rouge en fin d'historique (précondition
    du rendu, Story 1.3), bornes d'Entrées tenues."""
    generation = generer(config_reduite, GRAINE, DATE_GENERATION)
    couleurs = _meteo_fin_de_semaine(config_reduite, generation)
    assert any(c[-1] is Couleur.rouge for c in couleurs.values()), couleurs
    entrees, _ = _entrees_sorties(generation)
    par_semaine = Counter[int]()
    for (_, semaine), nombre in entrees.items():
        par_semaine[semaine] += nombre
    volumetrie = config_reduite.volumetrie
    assert all(
        volumetrie.entrees_semaine_min <= par_semaine[s] <= volumetrie.entrees_semaine_max
        for s in SEMAINES
    ), par_semaine
