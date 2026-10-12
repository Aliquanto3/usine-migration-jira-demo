"""Calage des Scénarios de démo au jour près (Story 1.8, FR-3).

La Météo de chaque Entité est calculée pour chaque Jour ouvré de l'historique comme dans la
Chaîne (`EtapeMeteo`) : état des tickets de J-5 au jour (`tickets_etats`), puis `meteo` avec la
Grille et le Programme livrés (seuils inchangés, SM-C3).
"""

from collections import Counter, defaultdict
from datetime import date, timedelta
from functools import cache
from pathlib import Path
from typing import Any

import polars as pl
import pytest
import yaml

from usine.config import charger_yaml
from usine.contrats.calendrier import (
    TAILLE_FENETRE_GLISSANTE,
    jour_local,
    jour_ouvre_precedent,
    jours_ouvres,
    semaine_programme,
)
from usine.contrats.config import ConfigProgramme, GrilleMeteo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import NatureEvenement
from usine.contrats.meteo import Couleur
from usine.contrats.tickets import CauseRacine, Champ, Gravite, TypeTicket
from usine.domaine.instantanes import tickets_etats
from usine.domaine.meteo import DECALAGE_IND8, meteo
from usine.generateur.corpus import CHEMIN_CORPUS, Corpus, charger_corpus
from usine.generateur.journal import Generation, _cas_du_jour, generer
from usine.generateur.scenarios import (
    AUCUN_SCENARIO,
    SCENARIOS_PAR_DEFAUT,
    ScenarioEnlisement,
    ScenarioMenace,
    Scenarios,
    ScenarioSortie,
    scenarios_applicables,
)

RACINE = Path(__file__).resolve().parents[3]
PROGRAMME_LIVRE = RACINE / "config" / "programme.yaml"
PROGRAMME_REDUIT = Path(__file__).with_name("programme_reduit.yaml")
GRILLE_LIVREE = RACINE / "config" / "grille_meteo.yaml"
GRAINE = 42
DATE_GENERATION = date(2026, 10, 12)
SCENARISEES = ("ENT-A", "ENT-B", "ENT-C")
VERT_OU_JAUNE = {Couleur.vert, Couleur.jaune}
ROUGES_CONSECUTIFS_MAX = 3
ROUGES_FIN_MAX = 2
PART_VERT_OU_JAUNE_MIN = 0.8
GRAINES_LENTES = (1, 7, 123)
"""Autres graines vérifiées par le test `lent`."""


@pytest.fixture(scope="module")
def config_livree() -> ConfigProgramme:
    return charger_yaml(PROGRAMME_LIVRE, ConfigProgramme)


@pytest.fixture(scope="module")
def grille_livree() -> GrilleMeteo:
    return charger_yaml(GRILLE_LIVREE, GrilleMeteo)


def _meteo_quotidienne(
    config: ConfigProgramme, grille: GrilleMeteo, generation: Generation
) -> dict[str, dict[date, Couleur]]:
    """Couleur de chaque Entité à chaque Jour ouvré, calculée comme dans la Chaîne.

    Chaque jour reçoit l'état des tickets de J-5 au jour (dès l'ancrage), comme `EtapeMeteo`.
    """
    ancrage = generation.entete.ancrage_semaines
    jours = jours_ouvres(ancrage, generation.entete.date_injection)
    etats = tickets_etats(generation.evenements, jours)
    codes = [e.code for e in config.entites]
    profondeur = max(DECALAGE_IND8, TAILLE_FENETRE_GLISSANTE)
    couleurs: dict[str, dict[date, Couleur]] = defaultdict(dict)
    for jour in jours:
        debut = max(ancrage, jour_ouvre_precedent(jour, profondeur))
        historique = etats.filter(pl.col("date").is_between(debut, jour))
        for m in meteo(historique, jour, codes, grille, "v", programme=config, ancrage=ancrage):
            couleurs[m.entite][jour] = m.couleur
    return couleurs


def _par_semaine(couleurs: dict[date, Couleur], ancrage: date) -> dict[int, list[Couleur]]:
    semaines: dict[int, list[Couleur]] = defaultdict(list)
    for jour, couleur in sorted(couleurs.items()):
        semaines[semaine_programme(jour, ancrage)].append(couleur)
    return semaines


def _ecarts(
    couleurs: dict[str, dict[date, Couleur]], ancrage: date, derniere_semaine: int
) -> list[str]:
    """Écarts aux trajectoires de FR-3 et aux règles hors A, B et C, jour par jour."""
    ecarts: list[str] = []

    def attendre(entite: str, semaines: range, permises: set[Couleur]) -> None:
        for semaine, du_jour in _par_semaine(couleurs[entite], ancrage).items():
            if semaine in semaines and not set(du_jour) <= permises:
                noms = sorted(c.value for c in permises)
                vues = [c.value for c in du_jour]
                ecarts.append(f"{entite} semaine {semaine} : {vues} hors de {noms}")

    fin = derniere_semaine + 1
    attendre("ENT-A", range(1, 6), VERT_OU_JAUNE)
    attendre("ENT-A", range(6, fin), {Couleur.rouge})
    attendre("ENT-B", range(2, fin), {Couleur.rouge})
    attendre("ENT-C", range(1, 4), {Couleur.vert})
    attendre("ENT-C", range(4, 7), {Couleur.jaune})
    attendre("ENT-C", range(7, fin), {Couleur.orange})

    autres = {e: c for e, c in couleurs.items() if e not in SCENARISEES}
    for entite, du_jour in autres.items():
        serie = plus_longue = 0
        for _, couleur in sorted(du_jour.items()):
            serie = serie + 1 if couleur is Couleur.rouge else 0
            plus_longue = max(plus_longue, serie)
        if plus_longue > ROUGES_CONSECUTIFS_MAX:
            ecarts.append(f"{entite} : {plus_longue} Jours ouvrés rouges consécutifs")
    couples = [c for du_jour in autres.values() for c in du_jour.values()]
    part = sum(c in VERT_OU_JAUNE for c in couples) / len(couples)
    if part < PART_VERT_OU_JAUNE_MIN:
        ecarts.append(f"hors A, B, C : {part:.0%} de couples verts ou jaunes")
    dernier = max(next(iter(autres.values())))
    rouges = sorted(e for e, du_jour in autres.items() if du_jour[dernier] is Couleur.rouge)
    if len(rouges) > ROUGES_FIN_MAX:
        ecarts.append(f"{len(rouges)} Entités rouges le {dernier.isoformat()} : {rouges}")
    return ecarts


@cache
def _corpus_versionne() -> Corpus:
    """Corpus versionné, celui de la démo (`usine donnees generer`)."""
    return charger_corpus(RACINE / CHEMIN_CORPUS)


def _verifier_calage(
    config: ConfigProgramme, grille: GrilleMeteo, date_generation: date, graine: int = GRAINE
) -> tuple[Generation, dict[str, dict[date, Couleur]]]:
    """Génère avec le Corpus versionné de la démo et vérifie le calage au jour près."""
    generation = generer(config, graine, date_generation, corpus=_corpus_versionne())
    couleurs = _meteo_quotidienne(config, grille, generation)
    ancrage = generation.entete.ancrage_semaines
    derniere = semaine_programme(generation.entete.date_injection, ancrage)
    assert derniere == config.nb_semaines
    assert set(couleurs) == {e.code for e in config.entites}
    jours = set(jours_ouvres(ancrage, generation.entete.date_injection))
    assert all(set(du_jour) == jours for du_jour in couleurs.values())
    assert _ecarts(couleurs, ancrage, derniere) == []
    return generation, couleurs


# --- Configuration livrée : calage au jour près ---


def test_calage_config_livree(config_livree: ConfigProgramme, grille_livree: GrilleMeteo) -> None:
    """Graine 42, génération le 2026-10-12 (8 semaines pleines) : trajectoires de FR-3 tenues
    chaque Jour ouvré, règles hors A, B et C tenues sur tous les couples Entité × Jour ouvré."""
    generation, couleurs = _verifier_calage(config_livree, grille_livree, DATE_GENERATION)
    assert len(couleurs["ENT-A"]) == 40
    assert generation.scenarios == SCENARIOS_PAR_DEFAUT


def test_calage_derniere_semaine_partielle_rapide(
    config_livree: ConfigProgramme, grille_livree: GrilleMeteo
) -> None:
    """Génération un mercredi (défaut de la CLI : le jour même), dernière semaine de 2 Jours
    ouvrés : mêmes trajectoires."""
    generation, _ = _verifier_calage(
        config_livree, grille_livree, DATE_GENERATION + timedelta(days=2)
    )
    ancrage = generation.entete.ancrage_semaines
    jours = jours_ouvres(ancrage, generation.entete.date_injection)
    assert sum(semaine_programme(j, ancrage) == 8 for j in jours) == 2


@pytest.mark.lent
@pytest.mark.parametrize(
    "date_generation",
    [DATE_GENERATION + timedelta(days=n) for n in (1, 3, 4, 5)],
    ids=["mardi", "jeudi", "vendredi", "samedi"],
)
def test_calage_derniere_semaine_partielle(
    config_livree: ConfigProgramme, grille_livree: GrilleMeteo, date_generation: date
) -> None:
    """Dernière semaine partielle (génération du mardi au samedi) : mêmes trajectoires."""
    _verifier_calage(config_livree, grille_livree, date_generation)


@pytest.mark.lent
@pytest.mark.parametrize("graine", GRAINES_LENTES)
def test_calage_autres_graines(
    config_livree: ConfigProgramme, grille_livree: GrilleMeteo, graine: int
) -> None:
    """Autres graines, génération le 2026-10-12 : mêmes trajectoires, mêmes règles."""
    _verifier_calage(config_livree, grille_livree, DATE_GENERATION, graine)


@pytest.mark.parametrize(
    ("par_semaine", "attendu"),
    [
        (50, [10, 10, 10, 10, 10]),
        (30, [6, 6, 6, 6, 6]),
        (32, [7, 7, 6, 6, 6]),
        (4, [1, 1, 1, 1, 0]),
        (1, [1, 0, 0, 0, 0]),
    ],
)
def test_cas_du_jour(par_semaine: int, attendu: list[int]) -> None:
    """Répartition des Cas de test de C : le reste aux premiers jours, total d'une semaine
    pleine égal à `cas_de_test_par_semaine`."""
    du_jour = [_cas_du_jour(par_semaine, rang) for rang in range(5)]
    assert du_jour == attendu
    assert sum(du_jour) == par_semaine


# --- Bloquantes de bascule ---


def _creations(generation: Generation) -> dict[str, dict[Any, Any]]:
    """Attributs initiaux et jour de création de chaque ticket."""
    tickets: dict[str, dict[Any, Any]] = defaultdict(dict)
    for e in generation.evenements:
        if e.nature is NatureEvenement.creation:
            tickets[e.cle_ticket]["type"] = e.type_ticket
            tickets[e.cle_ticket]["jour"] = jour_local(e.horodatage)
        elif e.nature is NatureEvenement.modification_champ and e.de is None and e.champ:
            tickets[e.cle_ticket][e.champ] = e.vers
    return tickets


def _bloquantes_du_jour(generation: Generation, entite: str, jour: date) -> list[str]:
    return [
        cle
        for cle, t in _creations(generation).items()
        if t["type"] is TypeTicket.anomalie
        and t[Champ.entite] == entite
        and t[Champ.gravite] == Gravite.bloquante
        and t["jour"] == jour
    ]


def _lundi(generation: Generation, semaine: int) -> date:
    return generation.entete.ancrage_semaines + timedelta(weeks=semaine - 1)


@pytest.fixture(scope="module")
def generation_livree(config_livree: ConfigProgramme) -> Generation:
    return generer(config_livree, GRAINE, DATE_GENERATION, corpus=_corpus_versionne())


def test_bascule_au_premier_jour_ouvre(generation_livree: Generation) -> None:
    """A : au moins 3 bloquantes de reprise de données le lundi de la semaine 6 ; B : au moins
    3 bloquantes le lundi de la semaine 2, sa première semaine d'enlisement."""
    a = _bloquantes_du_jour(generation_livree, "ENT-A", _lundi(generation_livree, 6))
    assert len(a) >= 3, a
    assert {generation_livree.verite_terrain[cle] for cle in a} == {CauseRacine.reprise_donnees}
    b = _bloquantes_du_jour(generation_livree, "ENT-B", _lundi(generation_livree, 2))
    assert len(b) >= 3, b


# --- Bloquantes scriptées de A et B (Story 4.5) ---


def _transitions_statut(generation: Generation) -> dict[str, list[tuple[date, str, str]]]:
    transitions: dict[str, list[tuple[date, str, str]]] = defaultdict(list)
    for e in generation.evenements:
        if e.nature is NatureEvenement.transition and e.champ is Champ.statut:
            assert e.de is not None and e.vers is not None
            transitions[e.cle_ticket].append((jour_local(e.horodatage), e.de, e.vers))
    return transitions


@pytest.mark.parametrize("date_generation", [DATE_GENERATION, DATE_GENERATION + timedelta(days=2)])
def test_bloquantes_scriptees(config_livree: ConfigProgramme, date_generation: date) -> None:
    """Chaque bloquante de A et B est scriptée : créée au nombre du flux du jour, En analyse à
    J+1, En correction à J+2, À retester à J+durée−1 et Fermée à J+durée (Jours ouvrés), sans
    rejet ni retour ; une transition postérieure à la Date d'injection n'est pas émise (la
    bloquante reste ouverte). A : Cause racine « reprise de données »."""
    generation = generer(config_livree, GRAINE, date_generation, corpus=_corpus_versionne())
    ancrage = generation.entete.ancrage_semaines
    jours = jours_ouvres(ancrage, generation.entete.date_injection)
    rangs = {jour: rang for rang, jour in enumerate(jours)}
    creations, transitions = _creations(generation), _transitions_statut(generation)
    sortie, enlisement = SCENARIOS_PAR_DEFAUT.sortie, SCENARIOS_PAR_DEFAUT.enlisement
    assert sortie is not None and enlisement is not None
    ouvertes_fin = fermees = 0
    for scenario in (sortie, enlisement):
        bloquantes = {
            cle: t
            for cle, t in creations.items()
            if t["type"] is TypeTicket.anomalie
            and t[Champ.entite] == scenario.entite
            and t[Champ.gravite] == Gravite.bloquante
        }
        par_jour = Counter(t["jour"] for t in bloquantes.values())
        for jour in jours:
            semaine = semaine_programme(jour, ancrage)
            rang_semaine = (jour - _lundi(generation, semaine)).days
            attendu = scenario.bloquantes(semaine, rang_semaine)
            assert par_jour[jour] == attendu, (scenario.entite, jour)
        duree = scenario.duree_bloquantes
        for cle, t in bloquantes.items():
            rang = rangs[t["jour"]]
            attendues = [
                (jours[rang + decalage], de, vers)
                for decalage, de, vers in (
                    (1, "nouvelle", "en_analyse"),
                    (2, "en_analyse", "en_correction"),
                    (duree - 1, "en_correction", "a_retester"),
                    (duree, "a_retester", "fermee"),
                )
                if rang + decalage < len(jours)
            ]
            assert transitions[cle] == attendues, cle
            if rang + duree < len(jours):
                fermees += 1
            else:
                ouvertes_fin += 1
            if scenario is sortie:
                assert generation.verite_terrain[cle] is CauseRacine.reprise_donnees
    assert fermees and ouvertes_fin


@pytest.fixture(scope="module")
def config_reduite() -> ConfigProgramme:
    return charger_yaml(PROGRAMME_REDUIT, ConfigProgramme)


def _creations_par_semaine(generation: Generation) -> Counter[int]:
    ancrage = generation.entete.ancrage_semaines
    return Counter(
        semaine_programme(t["jour"], ancrage)
        for t in _creations(generation).values()
        if t["type"] is TypeTicket.anomalie
    )


@pytest.mark.parametrize("bascule", [5, 50])
def test_bloquantes_bascule_prises_sur_la_semaine(
    config_reduite: ConfigProgramme, bascule: int
) -> None:
    """Les bloquantes de bascule comptent dans les créations de la semaine (volumétrie de la
    1.3 tenue) ; au-delà des créations de la semaine, elles les prennent toutes."""

    def generation(n: int) -> Generation:
        scenarios = Scenarios(sortie=ScenarioSortie(bloquantes_bascule=n))
        return generer(config_reduite, GRAINE, DATE_GENERATION, scenarios=scenarios)

    sans, avec = generation(0), generation(bascule)
    assert _creations_par_semaine(avec) == _creations_par_semaine(sans)
    lundi = _lundi(avec, 6)
    creations_semaine = _creations_par_semaine(avec)[6]
    assert len(_bloquantes_du_jour(avec, "ENT-A", lundi)) >= min(bascule, creations_semaine)
    if bascule >= creations_semaine:
        ancrage = avec.entete.ancrage_semaines
        semaine_6 = [
            t
            for t in _creations(avec).values()
            if t["type"] is TypeTicket.anomalie and semaine_programme(t["jour"], ancrage) == 6
        ]
        assert {(t[Champ.entite], t[Champ.gravite], t["jour"]) for t in semaine_6} == {
            ("ENT-A", Gravite.bloquante, lundi)
        }


# --- Programmes courts : Scénarios applicables ---


def _programme_court(config: ConfigProgramme) -> ConfigProgramme:
    """ENT-A à ENT-C sur 5 semaines (Vague V1 : migration à blanc 1, recette 2-3, TNR 4-5)."""
    donnees = yaml.safe_load(PROGRAMME_LIVRE.read_text(encoding="utf-8"))
    donnees["nb_semaines"] = 5
    donnees["entites"] = donnees["entites"][:3]
    donnees["vagues"] = [
        {
            "code": "V1",
            "libelle": "Vague 1",
            "phases": [
                {"phase": "migration_a_blanc", "semaine_debut": 1, "semaine_fin": 1},
                {"phase": "recette", "semaine_debut": 2, "semaine_fin": 3},
                {"phase": "tnr", "semaine_debut": 4, "semaine_fin": 5},
            ],
        }
    ]
    donnees["volumetrie"]["anomalies_min"] = 1000
    return ConfigProgramme.model_validate(donnees)


def test_programme_court_scenarios_par_defaut(config_livree: ConfigProgramme) -> None:
    """5 semaines, `scenarios` omis : A ignoré (vague en semaine 6), B et C appliqués."""
    court = _programme_court(config_livree)
    generation = generer(court, GRAINE, DATE_GENERATION)
    assert generation.scenarios == Scenarios(
        enlisement=ScenarioEnlisement(), menace=ScenarioMenace()
    )
    explicite = generer(court, GRAINE, DATE_GENERATION, scenarios=generation.scenarios)
    assert explicite.evenements == generation.evenements


def test_programme_court_scenarios_explicites_refuses(config_livree: ConfigProgramme) -> None:
    """Des Scénarios fournis explicitement restent contrôlés strictement."""
    court = _programme_court(config_livree)
    with pytest.raises(UsineErreur) as erreur:
        generer(court, GRAINE, DATE_GENERATION, scenarios=SCENARIOS_PAR_DEFAUT)
    message = str(erreur.value)
    assert "Scénario A : semaine_vague = 6" in message
    assert "dernière semaine générée (5)" in message


def test_scenarios_explicites_trop_longs(config_livree: ConfigProgramme) -> None:
    with pytest.raises(UsineErreur) as erreur:
        generer(
            config_livree,
            GRAINE,
            DATE_GENERATION,
            scenarios=Scenarios(sortie=ScenarioSortie(semaine_vague=9)),
        )
    assert "Scénario A : semaine_vague = 9" in str(erreur.value)
    assert "dernière semaine générée (8)" in str(erreur.value)


@pytest.mark.parametrize(
    ("codes", "derniere", "attendu"),
    [
        (("ENT-A", "ENT-B", "ENT-C"), 8, SCENARIOS_PAR_DEFAUT),
        (
            ("ENT-A", "ENT-B", "ENT-C"),
            5,
            Scenarios(enlisement=ScenarioEnlisement(), menace=ScenarioMenace()),
        ),
        (("ENT-A", "ENT-B", "ENT-C"), 3, AUCUN_SCENARIO),
        (("ENT-A", "ENT-C"), 8, Scenarios(sortie=ScenarioSortie(), menace=ScenarioMenace())),
        ((), 8, AUCUN_SCENARIO),
    ],
)
def test_scenarios_applicables(codes: tuple[str, ...], derniere: int, attendu: Scenarios) -> None:
    assert scenarios_applicables(SCENARIOS_PAR_DEFAUT, codes, derniere) == attendu


def test_resume_des_scenarios() -> None:
    assert SCENARIOS_PAR_DEFAUT.resume() == "A (ENT-A), B (ENT-B), C (ENT-C)"
    assert AUCUN_SCENARIO.resume() == "aucun"
