"""`CacheLLMSqlite` : cache LLM en SQLite, mode WAL, erreurs nommant le fichier (AD-12)."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from usine.adaptateurs.stockage_sqlite import CacheLLMSqlite, TablePseudonymesSqlite
from usine.contrats.erreurs import UsineErreur
from usine.ports.cache_llm import CacheLLM


def test_mode_wal_et_relecture(tmp_path: Path) -> None:
    chemin = tmp_path / "cache_llm.sqlite"
    cache = CacheLLMSqlite(chemin)
    assert isinstance(cache, CacheLLM)
    assert cache.lire("cle") is None
    cache.ecrire("cle", '{"texte": "DEMO-1 bloque."}')
    with closing(sqlite3.connect(chemin)) as connexion:
        (mode,) = connexion.execute("PRAGMA journal_mode").fetchone()
    assert mode == "wal"
    relu = CacheLLMSqlite(chemin)
    assert relu.lire("cle") == '{"texte": "DEMO-1 bloque."}'


def test_ecriture_remplace(tmp_path: Path) -> None:
    cache = CacheLLMSqlite(tmp_path / "donnees" / "cache_llm.sqlite")
    cache.ecrire("cle", "a")
    cache.ecrire("cle", "b")
    assert cache.lire("cle") == "b"
    assert cache.lire("autre") is None


def test_fichier_invalide_nomme(tmp_path: Path) -> None:
    chemin = tmp_path / "cache_llm.sqlite"
    chemin.write_bytes(b"ceci n'est pas une base SQLite" * 100)
    with pytest.raises(UsineErreur, match=r"cache_llm.sqlite"):
        CacheLLMSqlite(chemin)


def test_table_pseudonymes_wal_et_relecture(tmp_path: Path) -> None:
    chemin = tmp_path / "donnees" / "pseudonymes.sqlite"
    table = TablePseudonymesSqlite(chemin)
    table.enregistrer({"COMPTE_abc123": "valeur fictive"})
    table.enregistrer({"COMPTE_abc123": "valeur fictive"})  # idempotent
    with closing(sqlite3.connect(chemin)) as connexion:
        (mode,) = connexion.execute("PRAGMA journal_mode").fetchone()
    assert mode == "wal"
    relue = TablePseudonymesSqlite(chemin)
    assert relue.lire(["COMPTE_abc123", "COMPTE_000000"]) == {"COMPTE_abc123": "valeur fictive"}
    assert relue.lire([]) == {}


def test_table_pseudonymes_collision_refusee(tmp_path: Path) -> None:
    table = TablePseudonymesSqlite(tmp_path / "pseudonymes.sqlite")
    table.enregistrer({"COMPTE_abc123": "valeur fictive"})
    with pytest.raises(UsineErreur, match="COMPTE_abc123") as erreur:
        table.enregistrer({"COMPTE_def456": "autre", "COMPTE_abc123": "valeur différente"})
    assert "valeur différente" not in str(erreur.value)
    assert table.lire(["COMPTE_def456"]) == {}  # rien n'est écrit en cas d'échec


def test_table_pseudonymes_fichier_invalide_nomme(tmp_path: Path) -> None:
    chemin = tmp_path / "pseudonymes.sqlite"
    chemin.write_bytes(b"ceci n'est pas une base SQLite" * 100)
    with pytest.raises(UsineErreur, match=r"pseudonymes.sqlite"):
        TablePseudonymesSqlite(chemin)
