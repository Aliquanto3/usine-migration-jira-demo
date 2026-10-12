"""Générateur déterministe du Journal (Stories 0.3, 1.1, 1.2 et 1.3)."""

import json
import re
from collections import Counter
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from usine.config import charger_yaml, cles_sans_commentaire
from usine.contrats.calendrier import (
    FUSEAU,
    jour_local,
    jour_ouvre_de,
    jours_ouvres,
    semaine_programme,
)
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import EnteteJournal, Evenement, NatureEvenement, SourceEvenement
from usine.contrats.tickets import (
    CHAMPS_PAR_TYPE,
    CauseRacine,
    Champ,
    StatutAnomalie,
    StatutTest,
    TypeTicket,
)
from usine.generateur.corpus import Corpus, TextesDomaine, TexteTicket
from usine.generateur.journal import (
    TRANSITIONS_MAX,
    Generation,
    ecrire_journal,
    fenetre_generation,
    generer,
    serialiser_journal,
    serialiser_verite,
)
from usine.generateur.textes import corpus_provisoire

RACINE = Path(__file__).resolve().parents[3]
PROGRAMME_LIVRE = RACINE / "config" / "programme.yaml"
PROGRAMME_REDUIT = Path(__file__).with_name("programme_reduit.yaml")
"""Configuration réduite figée (2 Entités, 25 à 35 Anomalies) des tests paramétrés."""
DATE_GENERATION = date(2026, 10, 12)
GRAINES = (42, 86, 153, 162, 234)

TRANSITIONS_PERMISES = {
    ("nouvelle", "en_analyse"),
    ("en_analyse", "en_correction"),
    ("en_analyse", "rejetee"),
    ("en_correction", "a_retester"),
    ("a_retester", "fermee"),
    ("a_retester", "en_correction"),
    ("fermee", "en_analyse"),
    ("rejetee", "en_analyse"),
}
"""Workflow H-17 strict : pas de raccourci Nouvelle → En correction ; réouverture depuis
Fermée ou Rejetée."""

STATUTS_FERMES_JOURNAL = {"fermee", "rejetee"}


@pytest.fixture(scope="module")
def config() -> ConfigProgramme:
    return charger_yaml(PROGRAMME_REDUIT, ConfigProgramme)


@pytest.fixture(scope="module", params=GRAINES, ids=lambda g: f"graine-{g}")
def graine(request: pytest.FixtureRequest) -> int:
    valeur: int = request.param
    return valeur


@pytest.fixture(scope="module")
def generation(config: ConfigProgramme, graine: int) -> Generation:
    return generer(config, graine, DATE_GENERATION)


def _numero(cle: str) -> int:
    return int(cle.split("-")[1])


def test_entete(generation: Generation, graine: int) -> None:
    entete = generation.entete
    assert entete.graine == graine
    assert entete.date_generation == DATE_GENERATION
    assert entete.date_injection == date(2026, 10, 9)
    assert entete.ancrage_semaines == date(2026, 8, 17)
    assert entete.version_corpus == "provisoire-1"
    assert entete.modele_corpus == "gabarits-provisoires"


@pytest.mark.parametrize(
    ("generation_le", "ancrage", "injection"),
    [
        (date(2026, 10, 12), date(2026, 8, 17), date(2026, 10, 9)),  # lundi → vendredi
        (date(2026, 10, 10), date(2026, 8, 17), date(2026, 10, 9)),  # samedi
        (date(2026, 10, 14), date(2026, 8, 24), date(2026, 10, 13)),  # mercredi
    ],
)
def test_fenetre_generation(generation_le: date, ancrage: date, injection: date) -> None:
    assert fenetre_generation(generation_le, 8) == (ancrage, injection)


def test_reproductible_octet_pour_octet(
    config: ConfigProgramme, generation: Generation, graine: int
) -> None:
    autre = generer(config, graine, DATE_GENERATION)
    assert serialiser_journal(autre) == serialiser_journal(generation)
    assert serialiser_verite(autre) == serialiser_verite(generation)


def test_graine_differente(config: ConfigProgramme, generation: Generation, graine: int) -> None:
    assert serialiser_journal(generer(config, graine + 1, DATE_GENERATION)) != serialiser_journal(
        generation
    )


def test_journal_relu_par_les_contrats(generation: Generation) -> None:
    lignes = serialiser_journal(generation).decode("utf-8").split("\n")
    assert lignes[-1] == ""
    assert "\r" not in "".join(lignes)
    assert EnteteJournal.model_validate_json(lignes[0]) == generation.entete
    relus = [Evenement.model_validate_json(ligne) for ligne in lignes[1:-1]]
    assert tuple(relus) == generation.evenements
    assert [e.id_evenement for e in relus] == [f"J-{rang}" for rang in range(1, len(relus) + 1)]
    assert all(e.source is SourceEvenement.journal for e in relus)


def test_creation_suivie_des_champs_du_type(generation: Generation) -> None:
    evenements = generation.evenements
    creations = [i for i, e in enumerate(evenements) if e.nature is NatureEvenement.creation]
    assert creations
    for indice in creations:
        creation = evenements[indice]
        attendus = [c for c in Champ if c in CHAMPS_PAR_TYPE[creation.type_ticket]]
        assert Champ.titre in attendus
        assert Champ.description in attendus
        initiaux = [
            e
            for e in evenements
            if e.cle_ticket == creation.cle_ticket
            and e.horodatage == creation.horodatage
            and e is not creation
        ]
        assert [e.champ for e in initiaux] == attendus
        assert all(e.nature is NatureEvenement.modification_champ for e in initiaux)
        assert all(e.de is None and e.vers for e in initiaux)
        assert all(evenements.index(e) > indice for e in initiaux)


def test_tri_et_cles(generation: Generation) -> None:
    evenements = generation.evenements
    cles = [(e.horodatage, _numero(e.cle_ticket)) for e in evenements]
    assert cles == sorted(cles)
    ordre_creation = [
        _numero(e.cle_ticket) for e in evenements if e.nature is NatureEvenement.creation
    ]
    assert ordre_creation == list(range(1, len(ordre_creation) + 1))
    for e in evenements:
        premier = next(x for x in evenements if x.cle_ticket == e.cle_ticket)
        assert premier.nature is NatureEvenement.creation


def test_horodatages_ouvres_dans_la_fenetre(generation: Generation) -> None:
    entete = generation.entete
    jours = set(jours_ouvres(entete.ancrage_semaines, entete.date_injection))
    for e in generation.evenements:
        assert e.horodatage.utcoffset() is not None
        assert e.horodatage.utcoffset().total_seconds() == 0  # type: ignore[union-attr]
        local = e.horodatage.astimezone(FUSEAU)
        assert local.date() in jours
        assert jour_ouvre_de(e.horodatage) == local.date()
        assert 8 <= local.hour < 18


def _rejouer_workflow(generation: Generation) -> dict[str, str]:
    """Rejoue les transitions des Anomalies et vérifie le workflow H-17 ; renvoie le dernier
    statut de chaque Anomalie.

    Chaque transition part du statut courant, suit `TRANSITIONS_PERMISES` et tombe sur un
    Jour ouvré distinct, strictement après la création et au plus tard à la Date d'injection.
    """
    statuts: dict[str, str] = {}
    jours: dict[str, list[date]] = {}
    date_injection = generation.entete.date_injection
    for e in generation.evenements:
        if e.champ is Champ.statut and e.nature is NatureEvenement.modification_champ:
            assert e.vers == "nouvelle"
            statuts[e.cle_ticket] = e.vers
            jours[e.cle_ticket] = [jour_local(e.horodatage)]
        elif e.nature is NatureEvenement.transition:
            assert e.type_ticket is TypeTicket.anomalie
            assert e.de == statuts[e.cle_ticket]
            assert (e.de, e.vers) in TRANSITIONS_PERMISES
            assert e.vers is not None
            statuts[e.cle_ticket] = e.vers
            jour = jour_local(e.horodatage)
            assert jours[e.cle_ticket][-1] < jour <= date_injection, e.cle_ticket
            jours[e.cle_ticket].append(jour)
    assert max((len(j) - 1 for j in jours.values()), default=0) <= TRANSITIONS_MAX
    return statuts


def test_cycle_de_vie(generation: Generation) -> None:
    _rejouer_workflow(generation)
    for e in generation.evenements:
        if e.champ is Champ.statut_test and e.de is not None:
            assert e.de == StatutTest.non_execute
            assert e.vers in {StatutTest.ok, StatutTest.ko}
    transitions = [e for e in generation.evenements if e.nature is NatureEvenement.transition]
    assert transitions
    initiaux_tests = [
        e.vers for e in generation.evenements if e.champ is Champ.statut_test and e.de is None
    ]
    assert set(initiaux_tests) == {StatutTest.non_execute}


def test_verite_terrain(generation: Generation) -> None:
    anomalies = {
        e.cle_ticket
        for e in generation.evenements
        if e.nature is NatureEvenement.creation and e.type_ticket is TypeTicket.anomalie
    }
    assert set(generation.verite_terrain) == anomalies
    contenu = json.loads(serialiser_verite(generation))
    assert contenu == {cle: cause.value for cle, cause in generation.verite_terrain.items()}
    assert list(contenu) == sorted(contenu)
    journal = serialiser_journal(generation).decode("utf-8")
    assert "cause_racine" not in journal
    for cause in CauseRacine:
        assert f'"{cause.value}"' not in journal


def test_volumetrie(config: ConfigProgramme, generation: Generation) -> None:
    creations = [e for e in generation.evenements if e.nature is NatureEvenement.creation]
    entites = {e.cle_ticket: e.vers for e in generation.evenements if e.champ is Champ.entite}
    assert set(entites.values()) == {"ENT-A", "ENT-B"}
    nb_anomalies = sum(1 for e in creations if e.type_ticket is TypeTicket.anomalie)
    assert config.volumetrie.anomalies_min <= nb_anomalies <= config.volumetrie.anomalies_max
    for code in ("ENT-A", "ENT-B"):
        types = {e.type_ticket for e in creations if entites[e.cle_ticket] == code}
        assert TypeTicket.cas_de_test in types
        assert TypeTicket.certification in types


@pytest.mark.parametrize("graine_negative", [-1, -42])
def test_graine_negative_refusee(config: ConfigProgramme, graine_negative: int) -> None:
    with pytest.raises(UsineErreur, match=str(graine_negative)):
        generer(config, graine_negative, DATE_GENERATION)


def test_sortie_utf8_sans_retour_chariot(generation: Generation) -> None:
    for contenu in (serialiser_journal(generation), serialiser_verite(generation)):
        assert b"\r" not in contenu
        assert contenu.endswith(b"\n")
        contenu.decode("utf-8")


def test_coeur_pur_sans_horloge_ni_hasard_global() -> None:
    """Le générateur (hors `cli.py`) ne lit ni l'horloge ni le `random` global."""
    sources = sorted((RACINE / "src" / "usine" / "generateur").glob("*.py"))
    sources = [s for s in sources if s.name != "cli.py"]
    assert any(s.name == "journal.py" for s in sources)
    for source in sources:
        texte = source.read_text(encoding="utf-8")
        assert "datetime.now" not in texte, source.name
        assert "date.today" not in texte, source.name
        assert "from random import" not in texte, source.name
        assert not re.search(r"\brandom\.(?!Random\b)", texte), source.name
        assert texte.count("random.Random(") <= 1, source.name


def test_ecrire_journal(config: ConfigProgramme, tmp_path: Path) -> None:
    generation = generer(config, 42, DATE_GENERATION)
    repertoire = tmp_path / "sortie" / "donnees"
    chemin = ecrire_journal(generation, repertoire)
    assert chemin == repertoire / "journal.jsonl"
    assert chemin.read_bytes() == serialiser_journal(generation)
    assert (repertoire / "verite_terrain.json").read_bytes() == serialiser_verite(generation)


def test_ecrire_journal_impossible(config: ConfigProgramme, tmp_path: Path) -> None:
    fichier = tmp_path / "fichier"
    fichier.write_text("x", encoding="utf-8")
    with pytest.raises(UsineErreur, match="écriture impossible"):
        ecrire_journal(generer(config, 42, DATE_GENERATION), fichier / "donnees")


# --- Story 1.1 : configuration complète et fidélité du générateur ---


def _variante(
    modifier: Callable[[dict[str, Any]], None], chemin: Path = PROGRAMME_REDUIT
) -> ConfigProgramme:
    """Configuration `chemin` modifiée par `modifier`, validée par `ConfigProgramme`."""
    donnees = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    modifier(donnees)
    return ConfigProgramme.model_validate(donnees)


def _volumetrie(anomalies: tuple[int, int], entrees: tuple[int, int]) -> Callable[..., None]:
    def modifier(donnees: dict[str, Any]) -> None:
        donnees["volumetrie"] = {
            "anomalies_min": anomalies[0],
            "anomalies_max": anomalies[1],
            "entrees_semaine_min": entrees[0],
            "entrees_semaine_max": entrees[1],
        }

    return modifier


def _attributs(generation: Generation) -> dict[str, dict[Champ, str]]:
    """Attributs initiaux de chaque ticket, par clé."""
    attributs: dict[str, dict[Champ, str]] = {}
    for e in generation.evenements:
        if e.nature is NatureEvenement.modification_champ and e.de is None and e.champ:
            attributs.setdefault(e.cle_ticket, {})[e.champ] = str(e.vers)
    return attributs


def _entrees_par_semaine(generation: Generation) -> Counter[int]:
    """Entrées d'Anomalies (créations et réouvertures) par semaine du Programme."""
    ancrage = generation.entete.ancrage_semaines
    return Counter(
        semaine_programme(jour_local(e.horodatage), ancrage)
        for e in generation.evenements
        if e.type_ticket is TypeTicket.anomalie
        and (
            e.nature is NatureEvenement.creation
            or (e.nature is NatureEvenement.transition and e.de in STATUTS_FERMES_JOURNAL)
        )
    )


def _reouvertures(generation: Generation) -> list[Evenement]:
    return [
        e
        for e in generation.evenements
        if e.nature is NatureEvenement.transition and e.de in STATUTS_FERMES_JOURNAL
    ]


def _nb_anomalies(generation: Generation) -> int:
    return sum(
        1
        for e in generation.evenements
        if e.nature is NatureEvenement.creation and e.type_ticket is TypeTicket.anomalie
    )


def _phase_attendue(config: ConfigProgramme, vague: str, semaine: int) -> str:
    """Oracle : dernière Phase en cours, sinon dernière commencée, sinon la première.

    « Dernière » : début le plus tardif, puis rang le plus élevé.
    """
    (periodes,) = [v.phases for v in config.vagues if v.code == vague]
    en_cours = [p for p in periodes if p.semaine_debut <= semaine <= p.semaine_fin]
    commencees = en_cours or [p for p in periodes if p.semaine_debut <= semaine]
    if not commencees:
        return periodes[0].phase.value
    debut = max(p.semaine_debut for p in commencees)
    return [p for p in commencees if p.semaine_debut == debut][-1].phase.value


def _verifier_phases(config: ConfigProgramme, generation: Generation) -> None:
    ancrage = generation.entete.ancrage_semaines
    creations = {
        e.cle_ticket: e.horodatage
        for e in generation.evenements
        if e.nature is NatureEvenement.creation
    }
    vagues = {e.code: e.vague for e in config.entites}
    verifies = 0
    for cle, valeurs in _attributs(generation).items():
        if Champ.phase not in valeurs:
            continue
        semaine = semaine_programme(jour_local(creations[cle]), ancrage)
        assert valeurs[Champ.vague] == vagues[valeurs[Champ.entite]]
        assert valeurs[Champ.phase] == _phase_attendue(config, valeurs[Champ.vague], semaine), cle
        verifies += 1
    assert verifies


@pytest.fixture(scope="module")
def config_livree() -> ConfigProgramme:
    return charger_yaml(PROGRAMME_LIVRE, ConfigProgramme)


@pytest.fixture(scope="module")
def generation_livree(config_livree: ConfigProgramme) -> Generation:
    return generer(config_livree, 42, DATE_GENERATION)


def test_config_livree(config_livree: ConfigProgramme) -> None:
    assert config_livree.nom == "Banque Exemple — migration SI cœur"
    assert (config_livree.graine, config_livree.nb_semaines) == (42, 8)
    assert [e.code for e in config_livree.entites] == [f"ENT-{c}" for c in "ABCDEFGHIJ"]
    assert {e.code: e.vague for e in config_livree.entites} == {
        **{f"ENT-{c}": "V1" for c in "ABCD"},
        **{f"ENT-{c}": "V2" for c in "EFG"},
        **{f"ENT-{c}": "V3" for c in "HIJ"},
    }
    calendriers = {
        v.code: [(p.phase.value, p.semaine_debut, p.semaine_fin) for p in v.phases]
        for v in config_livree.vagues
    }
    assert calendriers == {
        "V1": [("migration_a_blanc", 1, 2), ("recette", 3, 5), ("tnr", 6, 8)],
        "V2": [("migration_a_blanc", 1, 3), ("recette", 4, 6), ("tnr", 7, 8)],
        "V3": [("migration_a_blanc", 1, 4), ("recette", 5, 7), ("tnr", 8, 8)],
    }
    assert config_livree.domaines == (
        "credits",
        "depots",
        "paiements",
        "referentiel_clients",
        "comptabilite",
        "epargne",
    )
    volumetrie = config_livree.volumetrie
    assert (volumetrie.anomalies_min, volumetrie.anomalies_max) == (3000, 5000)
    assert (volumetrie.entrees_semaine_min, volumetrie.entrees_semaine_max) == (200, 500)


@pytest.mark.parametrize("chemin", [PROGRAMME_LIVRE, PROGRAMME_REDUIT], ids=lambda c: c.name)
def test_chaque_cle_commentee(chemin: Path) -> None:
    assert cles_sans_commentaire(chemin.read_text(encoding="utf-8")) == []


def test_generation_config_livree(
    config_livree: ConfigProgramme, generation_livree: Generation
) -> None:
    entites = {v[Champ.entite] for v in _attributs(generation_livree).values()}
    assert entites == {e.code for e in config_livree.entites}
    # Bornes livrées ∩ 8 semaines × [200, 500] Entrées par semaine = [3 000, 4 000], moins la
    # marge de réouvertures (500 − 50 créations au plus par semaine) : [3 000, 3 600].
    assert 3000 <= _nb_anomalies(generation_livree) <= 3600
    entrees = _entrees_par_semaine(generation_livree)
    assert sorted(entrees) == list(range(1, 9))
    assert all(200 <= n <= 500 for n in entrees.values()), entrees
    assert all(cle.startswith("DEMO-") for cle in generation_livree.verite_terrain)


def test_workflow_et_reouvertures_config_livree(generation_livree: Generation) -> None:
    """Workflow H-17 rejoué ; réouvertures depuis Fermée et Rejetée ; derniers statuts variés,
    Anomalies récentes encore ouvertes à la Date d'injection."""
    statuts = _rejouer_workflow(generation_livree)
    assert set(statuts) == set(generation_livree.verite_terrain)
    reouvertures = _reouvertures(generation_livree)
    assert {e.de for e in reouvertures} == STATUTS_FERMES_JOURNAL
    assert {e.vers for e in reouvertures} == {"en_analyse"}
    derniers = Counter(statuts.values())
    assert set(derniers) == {s.value for s in StatutAnomalie}
    # La majorité des Anomalies est fermée ou rejetée ; celles du dernier jour sont nouvelles.
    assert derniers["fermee"] + derniers["rejetee"] > len(statuts) // 2
    date_injection = generation_livree.entete.date_injection
    du_dernier_jour = {
        e.cle_ticket
        for e in generation_livree.evenements
        if e.nature is NatureEvenement.creation
        and e.type_ticket is TypeTicket.anomalie
        and jour_local(e.horodatage) == date_injection
    }
    assert du_dernier_jour
    assert {statuts[cle] for cle in du_dernier_jour} == {"nouvelle"}


def test_semaine_partielle_bornes_proratisees() -> None:
    """Date d'injection un lundi : la semaine 8 n'a qu'un Jour ouvré, ses bornes d'Entrées
    sont ⌊20 / 5⌋ = 4 et ⌈50 / 5⌉ = 10 ; les semaines pleines gardent [20, 50]."""
    config = _variante(_volumetrie((150, 300), (20, 50)))
    mardi = date(2026, 10, 13)
    for graine in GRAINES:
        generation = generer(config, graine, mardi)
        assert generation.entete.date_injection == date(2026, 10, 12)
        entrees = _entrees_par_semaine(generation)
        assert sorted(entrees) == list(range(1, 9))
        assert 4 <= entrees[8] <= 10, entrees
        assert all(20 <= entrees[s] <= 50 for s in range(1, 8)), entrees
        _rejouer_workflow(generation)


def test_semaine_partielle_reouvertures_sous_le_maximum_proratise() -> None:
    """Anomalies = Σ plafonds (7 × 45 + 9) : la semaine 8 d'un seul jour est pleine de
    créations ; ses réouvertures restent sous ⌈50 / 5⌉ = 10, pas sous le maximum plein 50."""
    config = _variante(_volumetrie((324, 324), (20, 50)))
    reouvertures_semaine_8 = 0
    for graine in GRAINES:
        generation = generer(config, graine, date(2026, 10, 13))
        assert _nb_anomalies(generation) == 324
        entrees = _entrees_par_semaine(generation)
        assert 9 <= entrees[8] <= 10, entrees
        reouvertures_semaine_8 += entrees[8] - 9
    assert reouvertures_semaine_8 > 0


def test_semaine_partielle_volumetrie_infaisable() -> None:
    """Bornes proratisées : 7 × [20, 50] + [4, 10] = [144, 360] Entrées."""
    config = _variante(_volumetrie((361, 400), (20, 50)))
    with pytest.raises(UsineErreur, match=re.escape("[144, 360]")):
        generer(config, 42, date(2026, 10, 13))
    assert _nb_anomalies(generer(config, 42, DATE_GENERATION)) >= 361


def test_phases_du_calendrier_livre(
    config_livree: ConfigProgramme, generation_livree: Generation
) -> None:
    _verifier_phases(config_livree, generation_livree)
    phases = {v[Champ.phase] for v in _attributs(generation_livree).values() if Champ.phase in v}
    assert phases == {"migration_a_blanc", "recette", "tnr"}


def test_phases_du_calendrier_reduit(config: ConfigProgramme, generation: Generation) -> None:
    _verifier_phases(config, generation)


def test_entrees_par_semaine_reduit(config: ConfigProgramme, generation: Generation) -> None:
    volumetrie = config.volumetrie
    entrees = _entrees_par_semaine(generation)
    assert sorted(entrees) == list(range(1, config.nb_semaines + 1))
    assert all(
        volumetrie.entrees_semaine_min <= n <= volumetrie.entrees_semaine_max
        for n in entrees.values()
    )


def test_phase_avant_toute_phase_commencee() -> None:
    """Semaine antérieure à la première Phase : la première Phase de la Vague."""

    def decaler(donnees: dict[str, Any]) -> None:
        donnees["vagues"][0]["phases"] = [
            {"phase": "recette", "semaine_debut": 3, "semaine_fin": 5},
            {"phase": "tnr", "semaine_debut": 6, "semaine_fin": 8},
        ]

    config = _variante(decaler)
    generation = generer(config, 42, DATE_GENERATION)
    _verifier_phases(config, generation)
    phases = {v.get(Champ.phase) for v in _attributs(generation).values()}
    assert "migration_a_blanc" not in phases
    assert "recette" in phases


def _phases_par_semaine(generation: Generation) -> dict[int, set[str]]:
    """Phases des tickets créés chaque semaine du Programme."""
    ancrage = generation.entete.ancrage_semaines
    creations = {
        e.cle_ticket: e.horodatage
        for e in generation.evenements
        if e.nature is NatureEvenement.creation
    }
    phases: dict[int, set[str]] = {}
    for cle, valeurs in _attributs(generation).items():
        if Champ.phase in valeurs:
            semaine = semaine_programme(jour_local(creations[cle]), ancrage)
            phases.setdefault(semaine, set()).add(valeurs[Champ.phase])
    return phases


def _calendrier_v1(periodes: list[tuple[str, int, int]]) -> ConfigProgramme:
    def remplacer(donnees: dict[str, Any]) -> None:
        donnees["vagues"][0]["phases"] = [
            {"phase": phase, "semaine_debut": debut, "semaine_fin": fin}
            for phase, debut, fin in periodes
        ]

    return _variante(remplacer)


def test_phase_meme_debut_rang_le_plus_eleve() -> None:
    """Deux Phases commencent la même semaine : la Phase de rang le plus élevé l'emporte."""
    config = _calendrier_v1([("migration_a_blanc", 1, 2), ("recette", 3, 5), ("tnr", 3, 8)])
    generation = generer(config, 42, DATE_GENERATION)
    _verifier_phases(config, generation)
    phases = _phases_par_semaine(generation)
    assert phases[1] == phases[2] == {"migration_a_blanc"}
    for semaine in range(3, 9):
        assert phases[semaine] == {"tnr"}, semaine


def test_phase_terminee_et_trou_du_calendrier() -> None:
    """Une Phase terminée cède la place à une Phase en cours ; dans un trou, la dernière
    Phase commencée s'applique."""
    config = _calendrier_v1([("migration_a_blanc", 1, 5), ("recette", 2, 3), ("tnr", 7, 8)])
    generation = generer(config, 42, DATE_GENERATION)
    _verifier_phases(config, generation)
    phases = _phases_par_semaine(generation)
    attendues = {
        1: "migration_a_blanc",
        2: "recette",
        3: "recette",
        4: "migration_a_blanc",  # recette terminée, migration à blanc encore en cours
        5: "migration_a_blanc",
        6: "recette",  # trou : dernière Phase commencée (début 2)
        7: "tnr",
        8: "tnr",
    }
    assert phases == {semaine: {phase} for semaine, phase in attendues.items()}


def test_reouvertures_bornees_par_le_maximum_d_entrees() -> None:
    """Semaines pleines dès les créations : aucune réouverture n'est gardée."""
    config = _variante(_volumetrie((160, 160), (1, 20)))
    for graine in GRAINES:
        generation = generer(config, graine, DATE_GENERATION)
        assert _nb_anomalies(generation) == 160
        assert set(_entrees_par_semaine(generation).values()) == {20}


def test_reouvertures_gardees_sous_le_maximum() -> None:
    generation = generer(_variante(_volumetrie((2000, 2000), (1, 1000))), 42, DATE_GENERATION)
    assert sum(_entrees_par_semaine(generation).values()) > 2000


def test_volumetrie_infaisable() -> None:
    config = _variante(_volumetrie((10, 20), (5, 10)))
    with pytest.raises(UsineErreur) as erreur:
        generer(config, 42, DATE_GENERATION)
    message = str(erreur.value)
    assert "volumétrie infaisable" in message
    assert "[10, 20]" in message
    assert "[40, 80]" in message
    assert "[5, 10]" in message


def test_vague_sans_phase() -> None:
    def vider(donnees: dict[str, Any]) -> None:
        donnees["vagues"][0]["phases"] = []

    with pytest.raises(UsineErreur, match="Vague V1"):
        generer(_variante(vider), 42, DATE_GENERATION)


def test_vague_inconnue_refusee_au_chargement(tmp_path: Path) -> None:
    fautive = tmp_path / "programme.yaml"
    fautive.write_text(
        PROGRAMME_LIVRE.read_text(encoding="utf-8").replace("vague: V2", "vague: V9", 1),
        encoding="utf-8",
    )
    with pytest.raises(UsineErreur) as erreur:
        charger_yaml(fautive, ConfigProgramme)
    message = str(erreur.value)
    assert str(fautive) in message
    assert "ENT-E" in message
    assert "Vague" in message
    assert "V9" in message


def test_cle_projet(config: ConfigProgramme) -> None:
    generation = generer(config, 42, DATE_GENERATION, cle_projet="PILOTE")
    assert all(e.cle_ticket.startswith("PILOTE-") for e in generation.evenements)
    assert all(cle.startswith("PILOTE-") for cle in generation.verite_terrain)
    reference = serialiser_journal(generer(config, 42, DATE_GENERATION))
    assert serialiser_journal(generation).replace(b'"PILOTE-', b'"DEMO-') == reference


@pytest.mark.parametrize("cle", ["", "D", "demo", "1DEMO", "DE-MO", "DEMO\n"])
def test_cle_projet_invalide(config: ConfigProgramme, cle: str) -> None:
    with pytest.raises(UsineErreur, match="clé de projet invalide"):
        generer(config, 42, DATE_GENERATION, cle_projet=cle)


# --- Story 1.2 : textes tirés du Corpus ---


def _titres_attendus(corpus: Corpus, domaine: str, cause: CauseRacine, entite: str) -> set[str]:
    case = corpus.textes_domaine(domaine).anomalies[cause]
    return {texte.remplir(entite, domaine)[0] for texte in case}


def _verifier_titres_des_anomalies(corpus: Corpus, generation: Generation) -> int:
    """Le titre de chaque Anomalie appartient à la case (Domaine, Cause racine) du Corpus."""
    attributs = _attributs(generation)
    for cle, cause in generation.verite_terrain.items():
        valeurs = attributs[cle]
        attendus = _titres_attendus(corpus, valeurs[Champ.domaine], cause, valeurs[Champ.entite])
        assert valeurs[Champ.titre] in attendus, (cle, cause, valeurs[Champ.titre])
    return len(generation.verite_terrain)


def test_titres_dans_la_case_domaine_cause(config: ConfigProgramme, generation: Generation) -> None:
    """Config réduite : `comptabilite` livré, `achats` et `paie` tirés dans `generique`."""
    assert _verifier_titres_des_anomalies(corpus_provisoire(config.domaines), generation)


def test_titres_dans_la_case_config_livree(
    config_livree: ConfigProgramme, generation_livree: Generation
) -> None:
    corpus = corpus_provisoire(config_livree.domaines)
    assert set(corpus.domaines) == set(config_livree.domaines)
    assert _verifier_titres_des_anomalies(corpus, generation_livree) >= 3000


def test_domaine_absent_tire_dans_generique(config: ConfigProgramme) -> None:
    generation = generer(config, 42, DATE_GENERATION)
    attributs = _attributs(generation).values()
    for domaine in ("achats", "paie"):
        textes = [v for v in attributs if v.get(Champ.domaine) == domaine]
        assert textes, domaine
        for valeurs in textes:
            assert f"domaine {domaine}" in valeurs[Champ.titre] + valeurs[Champ.description]
    contenu = serialiser_journal(generation).decode("utf-8")
    assert "{domaine}" not in contenu
    assert "{entite}" not in contenu


def _corpus_unique(version: str, modele: str) -> Corpus:
    """Corpus minimal : une seule paire par case, marquée par sa case."""

    def case(nom: str) -> tuple[TexteTicket, ...]:
        return (TexteTicket(titre=f"{nom} {{domaine}}", description=f"{nom} pour {{entite}}"),)

    def section(prefixe: str) -> TextesDomaine:
        return TextesDomaine(
            anomalies={c: case(f"{prefixe}-{c.name}") for c in CauseRacine},
            cas_de_test=case(f"{prefixe}-test"),
        )

    return Corpus(
        version_corpus=version,
        modele_corpus=modele,
        domaines={"comptabilite": section("compta")},
        generique=section("gen"),
        certifications=(TexteTicket(titre="Certif {entite}", description="Avis {entite}"),),
    )


def test_corpus_passe_en_parametre(config: ConfigProgramme) -> None:
    corpus = _corpus_unique("essai-7", "factice:modele")
    generation = generer(config, 42, DATE_GENERATION, corpus=corpus)
    assert generation.entete.version_corpus == "essai-7"
    assert generation.entete.modele_corpus == "factice:modele"
    attributs = _attributs(generation)
    for cle, cause in generation.verite_terrain.items():
        valeurs = attributs[cle]
        prefixe = "compta" if valeurs[Champ.domaine] == "comptabilite" else "gen"
        assert valeurs[Champ.titre] == f"{prefixe}-{cause.name} {valeurs[Champ.domaine]}"
        assert valeurs[Champ.description] == f"{prefixe}-{cause.name} pour {valeurs[Champ.entite]}"
    certifications = [v for v in attributs.values() if Champ.statut_certification in v]
    assert {v[Champ.titre] for v in certifications} == {"Certif ENT-A", "Certif ENT-B"}
    # Même graine, même Corpus : même Journal ; autre Corpus : autres textes.
    assert serialiser_journal(generer(config, 42, DATE_GENERATION, corpus=corpus)) == (
        serialiser_journal(generation)
    )
    assert serialiser_journal(generer(config, 42, DATE_GENERATION)) != serialiser_journal(
        generation
    )


# --- Story 1.3 : volumétrie cible sur plusieurs graines et dates (test `lent`) ---

DATES_LENT = (
    date(2026, 10, 12),  # lundi : 8 semaines pleines
    date(2026, 10, 13),  # mardi : Date d'injection lundi, semaine 8 d'un seul jour
    date(2026, 10, 15),  # jeudi : semaine 8 de 3 jours
    date(2026, 10, 17),  # samedi : 8 semaines pleines
)


@pytest.mark.lent
@pytest.mark.parametrize("date_generation", DATES_LENT, ids=lambda d: d.isoformat())
@pytest.mark.parametrize("graine_lente", GRAINES, ids=lambda g: f"graine-{g}")
def test_volumetrie_cible_config_livree(
    config_livree: ConfigProgramme, graine_lente: int, date_generation: date
) -> None:
    generation = generer(config_livree, graine_lente, date_generation)
    autre = generer(config_livree, graine_lente, date_generation)
    assert serialiser_journal(autre) == serialiser_journal(generation)
    assert serialiser_verite(autre) == serialiser_verite(generation)

    entete = generation.entete
    ancrage, injection = entete.ancrage_semaines, entete.date_injection
    assert ancrage.weekday() == 0
    assert semaine_programme(injection, ancrage) == config_livree.nb_semaines
    jours = [jour_local(e.horodatage) for e in generation.evenements]
    assert (min(jours), max(jours)) == (ancrage, injection)

    entites = {v[Champ.entite] for v in _attributs(generation).values()}
    assert entites == {e.code for e in config_livree.entites}
    volumetrie = config_livree.volumetrie
    assert volumetrie.anomalies_min <= _nb_anomalies(generation) <= volumetrie.anomalies_max

    # Bornes d'Entrées proratisées aux Jours ouvrés de chaque semaine (sur 5).
    jours_semaine = Counter(semaine_programme(j, ancrage) for j in jours_ouvres(ancrage, injection))
    entrees = _entrees_par_semaine(generation)
    assert sorted(entrees) == sorted(jours_semaine) == list(range(1, 9))
    for semaine, nombre in jours_semaine.items():
        minimum = volumetrie.entrees_semaine_min * nombre // 5
        maximum = -(-volumetrie.entrees_semaine_max * nombre // 5)
        assert minimum <= entrees[semaine] <= maximum, (semaine, nombre, entrees)

    statuts = _rejouer_workflow(generation)
    assert set(statuts) == set(generation.verite_terrain)
    assert _reouvertures(generation)
    assert set(generation.verite_terrain.values()) == set(CauseRacine)
    journal = serialiser_journal(generation).decode("utf-8")
    assert "cause_racine" not in journal
    for cause in CauseRacine:
        assert f'"{cause.value}"' not in journal
