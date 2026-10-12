"""Correspondance des clés générées → clés Jira à la lecture du Journal (Story 2.5, AD-4)."""

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from tests.unit.adaptateurs.journal.outils import cle_jira, manifeste_pour
from usine.adaptateurs.journal import (
    CHEMIN_MANIFESTE_INJECTION,
    SourceJournal,
    charger_manifeste,
)
from usine.config import charger_yaml
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import ManifesteInjection
from usine.generateur.journal import Generation, generer, serialiser_journal
from usine.ports import SourceTickets

RACINE = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def generation() -> Generation:
    config = charger_yaml(RACINE / "tests/unit/generateur/programme_reduit.yaml", ConfigProgramme)
    return generer(config, 42, date(2026, 10, 12))


@pytest.fixture
def chemin_journal(tmp_path: Path, generation: Generation) -> Path:
    chemin = tmp_path / "journal.jsonl"
    chemin.write_bytes(serialiser_journal(generation))
    return chemin


@pytest.fixture(scope="module")
def manifeste(generation: Generation) -> ManifesteInjection:
    return manifeste_pour(generation.entete, generation.evenements)


def test_chemin_du_manifeste() -> None:
    assert Path("donnees/injection/manifeste_injection.json") == CHEMIN_MANIFESTE_INJECTION


def test_sans_manifeste_flux_inchange(chemin_journal: Path, generation: Generation) -> None:
    source = SourceJournal(chemin_journal)
    assert source.manifeste is None
    assert tuple(source.evenements()) == generation.evenements


def test_cles_remplacees_par_les_cles_jira(
    chemin_journal: Path, generation: Generation, manifeste: ManifesteInjection
) -> None:
    source = SourceJournal(chemin_journal, manifeste)
    assert isinstance(source, SourceTickets)
    assert source.manifeste is manifeste
    assert source.entete == generation.entete
    rendus = tuple(source.evenements())
    assert len(rendus) == len(generation.evenements)
    for rendu, origine in zip(rendus, generation.evenements, strict=True):
        assert rendu.cle_ticket == cle_jira(origine.cle_ticket)
        assert rendu == origine.model_copy(update={"cle_ticket": rendu.cle_ticket})
    assert {e.cle_ticket for e in rendus} == set(manifeste.correspondance_cles.values())


def test_cle_absente_de_la_correspondance(chemin_journal: Path, generation: Generation) -> None:
    cles = {e.cle_ticket for e in generation.evenements}
    assert "DEMO-3" in cles
    incomplet = manifeste_pour(generation.entete, generation.evenements, sans=frozenset({"DEMO-3"}))
    rang = next(i for i, e in enumerate(generation.evenements) if e.cle_ticket == "DEMO-3")
    ligne = rang + 2  # ligne 1 = en-tête
    with pytest.raises(UsineErreur) as erreur:
        SourceJournal(chemin_journal, incomplet)
    message = str(erreur.value)
    assert str(chemin_journal) in message
    assert f"ligne {ligne} :" in message
    assert "'DEMO-3'" in message


def test_cle_du_manifeste_absente_du_journal(
    chemin_journal: Path, manifeste: ManifesteInjection
) -> None:
    donnees = manifeste.model_dump()
    donnees["correspondance_cles"] = dict(manifeste.correspondance_cles) | {
        "DEMO-99999": "DEMO-199999"
    }
    perime = ManifesteInjection.model_validate(donnees)
    with pytest.raises(UsineErreur) as erreur:
        SourceJournal(chemin_journal, perime)
    message = str(erreur.value)
    assert str(chemin_journal) in message
    assert "DEMO-99999" in message
    assert "1 clé(s)" in message


def test_date_d_injection_incoherente(
    chemin_journal: Path, generation: Generation, manifeste: ManifesteInjection
) -> None:
    autre = generation.entete.date_injection - timedelta(days=1)
    decale = manifeste.model_copy(update={"date_injection": autre})
    with pytest.raises(UsineErreur) as erreur:
        SourceJournal(chemin_journal, decale)
    message = str(erreur.value)
    assert str(chemin_journal) in message
    assert autre.isoformat() in message
    assert generation.entete.date_injection.isoformat() in message


def test_depuis_avec_manifeste(
    chemin_journal: Path, generation: Generation, manifeste: ManifesteInjection
) -> None:
    source = SourceJournal(chemin_journal, manifeste)
    depuis = generation.evenements[10].horodatage
    attendus = [
        e.model_copy(update={"cle_ticket": cle_jira(e.cle_ticket)})
        for e in generation.evenements
        if e.horodatage >= depuis
    ]
    assert list(source.evenements(depuis)) == attendus
    with pytest.raises(UsineErreur, match="sans fuseau"):
        list(source.evenements(datetime(2026, 10, 5)))  # noqa: DTZ001


def test_charger_manifeste_relit_le_fichier(tmp_path: Path, manifeste: ManifesteInjection) -> None:
    chemin = tmp_path / "manifeste_injection.json"
    chemin.write_text(manifeste.model_dump_json(indent=2), encoding="utf-8")
    assert charger_manifeste(chemin) == manifeste


def test_manifeste_introuvable(tmp_path: Path) -> None:
    chemin = tmp_path / "absent.json"
    with pytest.raises(UsineErreur, match=rf"{re.escape(str(chemin))} : .*introuvable"):
        charger_manifeste(chemin)


@pytest.mark.parametrize(
    ("contenu", "motif"),
    [
        (b"{pas du json", "JSON illisible"),
        (b"\xff\xfe{}", "UTF-8"),
        (b"[]", "objet JSON attendu"),
    ],
)
def test_manifeste_illisible(tmp_path: Path, contenu: bytes, motif: str) -> None:
    chemin = tmp_path / "manifeste_injection.json"
    chemin.write_bytes(contenu)
    with pytest.raises(UsineErreur, match=re.escape(str(chemin))) as erreur:
        charger_manifeste(chemin)
    assert motif in str(erreur.value)


def test_manifeste_invalide(tmp_path: Path, manifeste: ManifesteInjection) -> None:
    donnees = json.loads(manifeste.model_dump_json())
    del donnees["correspondance_cles"]
    chemin = tmp_path / "manifeste_injection.json"
    chemin.write_text(json.dumps(donnees), encoding="utf-8")
    with pytest.raises(UsineErreur, match=re.escape(str(chemin))) as erreur:
        charger_manifeste(chemin)
    assert "invalide" in str(erreur.value)
    assert "correspondance_cles" in str(erreur.value)
