"""Balayage SM-7 des traces et du cache LLM (Story 6.10)."""

import json
import sqlite3
from pathlib import Path

import pytest

from outils.balayer_sm7 import (
    CHEMIN_TRACES_LLM,
    FichierIllisible,
    balayer,
    charger_identifiants,
    main,
    variantes,
)

IBAN = "FR46 9999 9143 2694 4104 2320 086"
IDENTIFIANTS = [
    {"cle_ticket": "DEMO-4", "type": "CLIENT", "valeur": "M. Fictivia EXEMPLON"},
    {"cle_ticket": "DEMO-4", "type": "COMPTE", "valeur": IBAN},
]
JETON = "CLIENT_0a1b2c"


def _depot(
    tmp_path: Path, traces: list[str], cache: dict[str, str] | None = None
) -> tuple[Path, Path, Path]:
    passage = tmp_path / "passage"
    (passage / CHEMIN_TRACES_LLM).parent.mkdir(parents=True)
    (passage / CHEMIN_TRACES_LLM).write_text("\n".join(traces) + "\n", encoding="utf-8")
    identifiants = tmp_path / "identifiants_injectes.json"
    identifiants.write_text(json.dumps(IDENTIFIANTS), encoding="utf-8")
    chemin_cache = tmp_path / "cache_llm.sqlite"
    with sqlite3.connect(chemin_cache) as connexion:
        connexion.execute("CREATE TABLE cache_llm (cle TEXT PRIMARY KEY, brut TEXT NOT NULL)")
        connexion.executemany("INSERT INTO cache_llm VALUES (?, ?)", (cache or {}).items())
    return passage, identifiants, chemin_cache


def _arguments(passage: Path, identifiants: Path, cache: Path | None = None) -> list[str]:
    args = ["--passage", str(passage), "--identifiants", str(identifiants)]
    return args + (["--cache", str(cache)] if cache is not None else [])


def test_variantes_iban_sans_espaces() -> None:
    assert variantes(IBAN) == {IBAN, IBAN.replace(" ", "")}
    assert variantes("9986233488") == {"9986233488"}


def test_traces_et_cache_pseudonymises_conformes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    passage, identifiants, cache = _depot(
        tmp_path, [json.dumps({"entree_pseudonymisee": f"Client {JETON} mécontent"})], {"k": JETON}
    )
    assert main(_arguments(passage, identifiants, cache)) == 0
    sortie = capsys.readouterr().out
    assert "2 textes balayés, 2 identifiants injectés, 2 jetons" in sortie
    assert "0 fuite(s)" in sortie


def test_fuite_dans_une_trace_signalee(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    trace = json.dumps({"entree_pseudonymisee": "Client M. Fictivia EXEMPLON mécontent"})
    passage, identifiants, _ = _depot(tmp_path, [trace])
    assert main(_arguments(passage, identifiants)) == 1
    sortie = capsys.readouterr().out
    assert "1 fuite(s)" in sortie
    assert "FUITE CLIENT" in sortie and "llm.jsonl:1" in sortie


def test_fuite_iban_compacte_dans_le_cache(tmp_path: Path) -> None:
    passage, identifiants, cache = _depot(tmp_path, ["{}"], {"cle": IBAN.replace(" ", "")})
    bilan = balayer(
        [("cache", IBAN.replace(" ", ""))],
        [(i["type"], i["valeur"]) for i in IDENTIFIANTS],
    )
    assert [(f.source, f.type) for f in bilan.fuites] == [("cache", "COMPTE")]
    assert main(_arguments(passage, identifiants, cache)) == 1


def test_fichiers_illisibles(tmp_path: Path) -> None:
    passage, identifiants, _ = _depot(tmp_path, ["{}"])
    assert main(_arguments(tmp_path / "absent", identifiants)) == 2
    assert main(_arguments(passage, identifiants, tmp_path / "absent.sqlite")) == 2
    vide = tmp_path / "vide.json"
    vide.write_text("[]", encoding="utf-8")
    with pytest.raises(FichierIllisible, match="aucun identifiant"):
        charger_identifiants(vide)
    mal_forme = tmp_path / "mal_forme.json"
    mal_forme.write_text('[{"type": "CLIENT"}]', encoding="utf-8")
    with pytest.raises(FichierIllisible, match="illisible"):
        charger_identifiants(mal_forme)
