"""Tâche `doublons` (Story 6.11, FR-36) : paires scorées, locales, sans écriture."""

from datetime import date
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from usine import composition
from usine.cli import app
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import SortieDoublons
from usine.contrats.tickets import SCHEMA_TICKET_TEXTE
from usine.ia.doublons import detecter_doublons, score_similarite

JOUR = date(2026, 10, 12)


def _textes(*lignes: tuple[str, str, str, str]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {"cle_ticket": c, "type_ticket": t, "entite": "E1", "titre": ti, "description": d}
            for c, t, ti, d in lignes
        ],
        schema=dict(SCHEMA_TICKET_TEXTE.colonnes),
    )


TEXTES = _textes(
    ("DEMO-2", "anomalie", "Écart de solde après reprise", "Solde client différent du legacy"),
    ("DEMO-10", "anomalie", "Écart de solde après reprise", "Le solde client diffère du legacy"),
    ("DEMO-3", "anomalie", "Batch de nuit en timeout", "Le job de nuit dépasse le délai"),
    ("DEMO-4", "cas_de_test", "Écart de solde après reprise", "Solde client différent du legacy"),
    ("DEMO-5", "anomalie", "Écart de solde après reprise", "Solde client différent du legacy"),
)
OUVERTES = ("DEMO-2", "DEMO-10", "DEMO-3", "DEMO-4")


def _identite(texte: str) -> str:
    return texte


def test_paire_scoree_et_classement() -> None:
    sortie = detecter_doublons(TEXTES, OUVERTES, JOUR, _identite, seuil=0.5)
    assert [(p.cle_a, p.cle_b) for p in sortie.paires] == [("DEMO-2", "DEMO-10")]
    assert 0.5 <= sortie.paires[0].score <= 1


def test_ignore_non_anomalies_et_fermees() -> None:
    sortie = detecter_doublons(TEXTES, OUVERTES, JOUR, _identite, seuil=0.1)
    cles = {c for p in sortie.paires for c in (p.cle_a, p.cle_b)}
    assert "DEMO-4" not in cles  # Cas de test
    assert "DEMO-5" not in cles  # non ouverte


def test_seuil_limite_et_ordre() -> None:
    plus = _textes(
        ("DEMO-1", "anomalie", "alpha beta gamma", "delta"),
        ("DEMO-2", "anomalie", "alpha beta gamma", "delta"),
        ("DEMO-3", "anomalie", "alpha beta gamma", "epsilon"),
    )
    cles = ("DEMO-1", "DEMO-2", "DEMO-3")
    sortie = detecter_doublons(plus, cles, JOUR, _identite, seuil=0.5)
    assert [(p.cle_a, p.cle_b, p.score) for p in sortie.paires] == [
        ("DEMO-1", "DEMO-2", 1.0),
        ("DEMO-1", "DEMO-3", 0.6),
        ("DEMO-2", "DEMO-3", 0.6),
    ]
    assert len(detecter_doublons(plus, cles, JOUR, _identite, seuil=0.5, limite=1).paires) == 1
    assert detecter_doublons(plus, cles, JOUR, _identite, seuil=0.9).paires[0].score == 1.0
    assert len(detecter_doublons(plus, cles, JOUR, _identite, seuil=0.9).paires) == 1


def test_texte_pseudonymise_avant_comparaison() -> None:
    vus: list[str] = []

    def pseudo(texte: str) -> str:
        vus.append(texte)
        return texte.replace("Dupont", "PERSONNE_aaaaaa")

    textes = _textes(
        ("DEMO-1", "anomalie", "Client Dupont bloqué", ""),
        ("DEMO-2", "anomalie", "Client Dupont bloqué", ""),
    )
    sortie = detecter_doublons(textes, ("DEMO-1", "DEMO-2"), JOUR, pseudo)
    assert len(vus) == 2 and sortie.paires
    assert "Dupont" not in sortie.model_dump_json()


def test_sans_texte_ni_stock() -> None:
    vides = _textes(("DEMO-1", "anomalie", "", ""), ("DEMO-2", "anomalie", "", ""))
    assert detecter_doublons(vides, ("DEMO-1", "DEMO-2"), JOUR, _identite, seuil=0).paires == ()
    assert detecter_doublons(TEXTES, (), JOUR, _identite).paires == ()
    assert score_similarite(frozenset(), frozenset({"abc"})) == 0.0


@pytest.mark.parametrize(("seuil", "limite"), [(-0.1, 5), (1.1, 5), (0.5, 0)])
def test_parametres_invalides(seuil: float, limite: int) -> None:
    with pytest.raises(UsineErreur):
        detecter_doublons(TEXTES, OUVERTES, JOUR, _identite, seuil=seuil, limite=limite)


def test_composition_sans_ecriture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Consultation:
        def anomalies(self, **kw: object):  # type: ignore[no-untyped-def]
            from usine.contrats.agent import ResultatListAnomalies

            assert kw == {"limite": None}
            return ResultatListAnomalies(date_arrete=JOUR, anomalies=(), total=0)

        def textes_tickets(self) -> pl.DataFrame:
            return TEXTES

    monkeypatch.setattr(composition, "consultation_repertoire", lambda _r: Consultation())
    monkeypatch.setattr(composition, "apercu_pseudonymisation", lambda _r: _identite)
    sortie = composition.doublons_passage(tmp_path, tmp_path)
    assert sortie == SortieDoublons(date_arrete=JOUR, seuil=0.6, statut_controle="conforme")
    assert list(tmp_path.iterdir()) == []


def test_cli_affiche_les_paires(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sortie = detecter_doublons(TEXTES, OUVERTES, JOUR, _identite, seuil=0.5)
    appels: list[tuple[float, int]] = []

    def faux(_racine: Path, _rep: Path, seuil: float, limite: int) -> SortieDoublons:
        appels.append((seuil, limite))
        return sortie

    monkeypatch.setattr(composition, "doublons_passage", faux)
    resultat = CliRunner().invoke(app, ["ia", "doublons", str(tmp_path), "--seuil", "0.5"])
    assert resultat.exit_code == 0, resultat.output
    assert "DEMO-2  DEMO-10" in resultat.output
    assert "1 paire(s) à revoir" in resultat.output
    assert appels == [(0.5, 50)]
