"""Adaptateur `SourceJournal` : lecture et validation du Journal JSONL (Story 0.4, FR-8)."""

import json
import re
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from usine.adaptateurs.journal import SourceJournal
from usine.config import charger_yaml
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.tickets import Champ
from usine.generateur.journal import Generation, generer, serialiser_journal
from usine.ports import SourceTickets

RACINE = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def generation() -> Generation:
    config = charger_yaml(RACINE / "config" / "programme.yaml", ConfigProgramme)
    return generer(config, 42, date(2026, 10, 12))


def _ecrire(repertoire: Path, lignes: list[str]) -> Path:
    chemin = repertoire / "journal.jsonl"
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return chemin


def _lignes(generation: Generation) -> list[str]:
    return serialiser_journal(generation).decode("utf-8").splitlines()


def test_relit_le_journal_genere(tmp_path: Path, generation: Generation) -> None:
    chemin = tmp_path / "journal.jsonl"
    chemin.write_bytes(serialiser_journal(generation))
    source = SourceJournal(chemin)
    assert isinstance(source, SourceTickets)
    assert source.entete == generation.entete
    assert tuple(source.evenements()) == generation.evenements


def test_depuis_inclusif(tmp_path: Path, generation: Generation) -> None:
    chemin = tmp_path / "journal.jsonl"
    chemin.write_bytes(serialiser_journal(generation))
    depuis = generation.evenements[10].horodatage
    rendus = list(SourceJournal(chemin).evenements(depuis))
    assert rendus == [e for e in generation.evenements if e.horodatage >= depuis]
    assert rendus[0].horodatage == depuis


def test_depuis_sans_fuseau(tmp_path: Path, generation: Generation) -> None:
    chemin = _ecrire(tmp_path, _lignes(generation))
    with pytest.raises(UsineErreur, match="sans fuseau"):
        list(SourceJournal(chemin).evenements(datetime(2026, 10, 5)))  # noqa: DTZ001


def test_journal_absent(tmp_path: Path) -> None:
    chemin = tmp_path / "absent.jsonl"
    with pytest.raises(UsineErreur, match=r"absent\.jsonl : Journal introuvable"):
        SourceJournal(chemin)


def test_journal_non_utf8(tmp_path: Path) -> None:
    chemin = tmp_path / "journal.jsonl"
    chemin.write_bytes(b"\xff\xfe{}\n")
    with pytest.raises(UsineErreur, match="UTF-8"):
        SourceJournal(chemin)


def test_journal_vide(tmp_path: Path) -> None:
    chemin = tmp_path / "journal.jsonl"
    chemin.write_bytes(b"")
    with pytest.raises(UsineErreur, match="en-tête du Journal manquant"):
        SourceJournal(chemin)


def test_entete_invalide(tmp_path: Path, generation: Generation) -> None:
    lignes = _lignes(generation)
    chemin = _ecrire(tmp_path, lignes[1:])  # première ligne = un événement
    with pytest.raises(UsineErreur, match=r"journal\.jsonl : ligne 1 : en-tête invalide"):
        SourceJournal(chemin)


def test_autre_version_majeure(tmp_path: Path, generation: Generation) -> None:
    lignes = _lignes(generation)
    entete = json.loads(lignes[0])
    entete["contrats_version"] = "1.0.0"
    chemin = _ecrire(tmp_path, [json.dumps(entete), *lignes[1:]])
    with pytest.raises(UsineErreur, match=r"1\.0\.0.*0\.1\.0") as erreur:
        SourceJournal(chemin)
    assert "journal.jsonl" in str(erreur.value)


def test_ligne_invalide_nommee(tmp_path: Path, generation: Generation) -> None:
    lignes = _lignes(generation)
    evenement = json.loads(lignes[4])
    evenement["nature"] = "inconnue"
    lignes[4] = json.dumps(evenement)
    chemin = _ecrire(tmp_path, lignes)
    with pytest.raises(UsineErreur, match=r"journal\.jsonl : ligne 5 : événement invalide"):
        SourceJournal(chemin)


def test_ligne_json_illisible(tmp_path: Path, generation: Generation) -> None:
    lignes = _lignes(generation)
    lignes[2] = "{pas du json"
    with pytest.raises(UsineErreur, match=r"ligne 3 : .*JSON illisible"):
        SourceJournal(_ecrire(tmp_path, lignes))


def test_ligne_non_objet(tmp_path: Path, generation: Generation) -> None:
    lignes = _lignes(generation)
    lignes[2] = "[1, 2]"
    with pytest.raises(UsineErreur, match=r"ligne 3 : .*objet JSON attendu"):
        SourceJournal(_ecrire(tmp_path, lignes))


def test_ligne_vide(tmp_path: Path, generation: Generation) -> None:
    lignes = _lignes(generation)
    lignes.insert(3, "")
    with pytest.raises(UsineErreur, match="ligne 4 vide"):
        SourceJournal(_ecrire(tmp_path, lignes))


def test_identifiant_en_double(tmp_path: Path, generation: Generation) -> None:
    lignes = _lignes(generation)
    evenement = json.loads(lignes[3])
    evenement["id_evenement"] = json.loads(lignes[2])["id_evenement"]
    lignes[3] = json.dumps(evenement)
    with pytest.raises(UsineErreur, match=r"ligne 4 : id_evenement .* en double"):
        SourceJournal(_ecrire(tmp_path, lignes))


def test_horodatage_decroissant(tmp_path: Path, generation: Generation) -> None:
    lignes = _lignes(generation)
    dernier = json.loads(lignes[-1])
    dernier["horodatage"] = datetime(2000, 1, 3, tzinfo=UTC).isoformat()
    lignes[-1] = json.dumps(dernier)
    with pytest.raises(UsineErreur, match=f"ligne {len(lignes)} : horodatage"):
        SourceJournal(_ecrire(tmp_path, lignes))


def test_separateurs_unicode_dans_une_valeur(tmp_path: Path, generation: Generation) -> None:
    rang, evenement = next(
        (rang, e) for rang, e in enumerate(generation.evenements) if e.champ is Champ.description
    )
    modifie = evenement.model_copy(update={"vers": "avant\u2028après\u0085\x0bfin"})
    evenements = (*generation.evenements[:rang], modifie, *generation.evenements[rang + 1 :])
    chemin = tmp_path / "journal.jsonl"
    chemin.write_bytes(serialiser_journal(replace(generation, evenements=evenements)))
    assert "\u2028" in chemin.read_text(encoding="utf-8")
    assert tuple(SourceJournal(chemin).evenements()) == evenements


def test_journal_illisible(tmp_path: Path) -> None:
    # Un répertoire : ni introuvable ni décodable, l'ouverture lève une autre `OSError`.
    with pytest.raises(UsineErreur, match=re.escape(f"{tmp_path} : Journal illisible")):
        SourceJournal(tmp_path)
