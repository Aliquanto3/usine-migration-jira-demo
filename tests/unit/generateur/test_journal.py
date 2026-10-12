"""Mini-générateur déterministe du Journal (Story 0.3)."""

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from usine.config import charger_yaml
from usine.contrats.calendrier import FUSEAU, jour_ouvre_de, jours_ouvres
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import EnteteJournal, Evenement, NatureEvenement, SourceEvenement
from usine.contrats.tickets import CHAMPS_PAR_TYPE, CauseRacine, Champ, StatutTest, TypeTicket
from usine.generateur.journal import (
    Generation,
    ecrire_journal,
    fenetre_generation,
    generer,
    serialiser_journal,
    serialiser_verite,
)

RACINE = Path(__file__).resolve().parents[3]
DATE_GENERATION = date(2026, 10, 12)
GRAINES = (42, 86, 153, 162, 234)

TRANSITIONS_PERMISES = {
    ("nouvelle", "en_analyse"),
    ("nouvelle", "en_correction"),
    ("en_analyse", "en_correction"),
    ("en_analyse", "rejetee"),
    ("en_correction", "a_retester"),
    ("a_retester", "fermee"),
    ("a_retester", "en_correction"),
    ("fermee", "en_analyse"),
}


@pytest.fixture(scope="module")
def config() -> ConfigProgramme:
    return charger_yaml(RACINE / "config" / "programme.yaml", ConfigProgramme)


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
    assert entete.version_corpus == "mini-e0"
    assert entete.modele_corpus == "aucun"


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


def test_cycle_de_vie(generation: Generation) -> None:
    statuts: dict[str, str] = {}
    for e in generation.evenements:
        if e.champ is Champ.statut and e.nature is NatureEvenement.modification_champ:
            assert e.vers == "nouvelle"
            statuts[e.cle_ticket] = e.vers
        elif e.nature is NatureEvenement.transition:
            assert e.de == statuts[e.cle_ticket]
            assert (e.de, e.vers) in TRANSITIONS_PERMISES
            assert e.vers is not None
            statuts[e.cle_ticket] = e.vers
        elif e.champ is Champ.statut_test and e.de is not None:
            assert e.de == StatutTest.non_execute
            assert e.vers in {StatutTest.ok, StatutTest.ko}
    transitions = [e for e in generation.evenements if e.nature is NatureEvenement.transition]
    assert transitions
    par_ticket = Counter(e.cle_ticket for e in transitions)
    assert max(par_ticket.values()) <= 4
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
