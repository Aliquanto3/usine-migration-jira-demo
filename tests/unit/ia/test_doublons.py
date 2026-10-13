"""Tâche `doublons` : paires d'Anomalies probablement en doublon, sans écriture (FR-36)."""

import logging
from decimal import Decimal

import polars as pl
import pytest

from tests.doublures.fournisseur_factice import FournisseurFactice
from tests.unit.ia.espions import (
    DATE_ARRETE,
    PASSAGE_ID,
    CacheMemoire,
    horloge_espion,
    pseudonymiseur,
    textes,
)
from usine.contrats.llm import PaireDoublonBrute, ReponseDoublons, StatutControle, Tache
from usine.contrats.versions import version_prompt
from usine.ia.doublons import (
    MAX_PAIRES_PAR_ENTITE,
    ContexteDoublons,
    detecter_doublons,
    lire_prompt,
    paires_candidates,
)
from usine.ia.passerelle import Passerelle

GRILLE = "grille123456"
LIGNES = {
    "DEMO-10": ("Flux comptable en retard", "Le fichier du flux comptable arrive en retard."),
    "DEMO-2": ("Retard du flux comptable", "Le fichier du flux comptable est livré en retard."),
    "DEMO-3": ("Code devise absent", "Le paramètre du code devise n'est pas renseigné."),
}


def _contexte() -> ContexteDoublons:
    return ContexteDoublons(passage_id=PASSAGE_ID, version_donnees="d" * 64, gabarit=lire_prompt())


def _passerelle(factice: FournisseurFactice, plafond: Decimal | None = None) -> Passerelle:
    return Passerelle(
        factice,
        pseudonymiseur(),
        CacheMemoire(),
        horloge_espion([]),
        plafond_cout_passage_eur=plafond,
    )


def _paire(a: str, b: str, score: float, justification: str = "") -> PaireDoublonBrute:
    return PaireDoublonBrute(cle_a=a, cle_b=b, score=score, justification=justification)


def _lignes(table: pl.DataFrame) -> list[dict[str, object]]:
    return list(table.iter_rows(named=True))


def test_paires_candidates_seulement_les_textes_proches() -> None:
    assert paires_candidates(_lignes(textes(LIGNES))) == [("DEMO-2", "DEMO-10")]


def test_paires_candidates_bornees_et_deterministes() -> None:
    nombreuses = {
        f"DEMO-{n}": ("Flux comptable en retard", "Fichier du flux") for n in range(1, 12)
    }
    candidates = paires_candidates(_lignes(textes(nombreuses)))
    assert len(candidates) == MAX_PAIRES_PAR_ENTITE
    assert candidates == paires_candidates(_lignes(textes(nombreuses)))
    assert candidates[0] == ("DEMO-1", "DEMO-2")


def test_paire_scoree_publiee_et_prompt_des_seuls_candidats() -> None:
    reponse = ReponseDoublons(paires=(_paire("DEMO-10", "DEMO-2", 0.9, "Même flux en retard."),))
    factice = FournisseurFactice([reponse])
    sorties, traces = detecter_doublons(
        _passerelle(factice), textes(LIGNES), DATE_ARRETE, _contexte(), GRILLE
    )
    (sortie,) = sorties
    assert (sortie.cle_a, sortie.cle_b, sortie.score) == ("DEMO-2", "DEMO-10", 0.9)
    assert (sortie.entite, sortie.date_arrete) == ("ENT-A", DATE_ARRETE)
    assert sortie.justification == "Même flux en retard."
    assert sortie.statut_controle is StatutControle.conforme
    (trace,) = traces
    assert trace.tache is Tache.doublons
    assert trace.cible == trace.entite == "ENT-A"
    assert trace.version_prompt == version_prompt(lire_prompt())
    (appel,) = factice.appels
    prompt = str(appel.entree)
    assert "DEMO-2 / DEMO-10" in prompt
    assert "DEMO-3" not in prompt


def test_paire_inconnue_doublon_ou_score_invalide_ecartes() -> None:
    reponse = ReponseDoublons(
        paires=(
            _paire("DEMO-2", "DEMO-10", 0.8),
            _paire("DEMO-10", "DEMO-2", 0.7),  # même paire inversée : doublon
            _paire("DEMO-2", "DEMO-3", 0.9),  # paire non candidate
            _paire("DEMO-2", "DEMO-99", 0.9),  # clé inconnue
        )
    )
    sorties, _ = detecter_doublons(
        _passerelle(FournisseurFactice([reponse])), textes(LIGNES), DATE_ARRETE, _contexte(), GRILLE
    )
    (sortie,) = sorties
    assert (sortie.cle_a, sortie.cle_b, sortie.score) == ("DEMO-2", "DEMO-10", 0.8)
    assert sortie.statut_controle is StatutControle.corrige


@pytest.mark.parametrize("score", [1.5, -0.1, float("nan")])
def test_score_hors_de_0_a_1_ecarte(score: float) -> None:
    reponse = ReponseDoublons(paires=(_paire("DEMO-2", "DEMO-10", score),))
    sorties, _ = detecter_doublons(
        _passerelle(FournisseurFactice([reponse])), textes(LIGNES), DATE_ARRETE, _contexte(), GRILLE
    )
    assert sorties == ()


def test_score_sous_le_seuil_non_publie() -> None:
    reponse = ReponseDoublons(paires=(_paire("DEMO-2", "DEMO-10", 0.3),))
    sorties, traces = detecter_doublons(
        _passerelle(FournisseurFactice([reponse])), textes(LIGNES), DATE_ARRETE, _contexte(), GRILLE
    )
    assert sorties == ()
    assert len(traces) == 1


def test_seules_les_anomalies_ouvertes_sont_comparees() -> None:
    factice = FournisseurFactice([])
    sorties, traces = detecter_doublons(
        _passerelle(factice),
        textes(LIGNES),
        DATE_ARRETE,
        _contexte(),
        GRILLE,
        ouvertes={"DEMO-2", "DEMO-3"},
    )
    assert (sorties, traces, factice.appels) == ((), (), [])


def test_cas_de_test_ignores_et_entites_separees() -> None:
    table = pl.concat(
        [
            textes({"DEMO-1": LIGNES["DEMO-10"], "DEMO-2": LIGNES["DEMO-2"]}, "ENT-B"),
            textes({"DEMO-3": LIGNES["DEMO-10"]}, "ENT-A"),
            textes({"DEMO-4": LIGNES["DEMO-2"]}, "ENT-A").with_columns(
                type_ticket=pl.lit("cas_de_test").cast(
                    pl.Enum(["anomalie", "cas_de_test", "certification"])
                )
            ),
        ]
    )
    reponse = ReponseDoublons(paires=(_paire("DEMO-1", "DEMO-2", 0.7),))
    factice = FournisseurFactice([reponse])
    sorties, traces = detecter_doublons(
        _passerelle(factice), table, DATE_ARRETE, _contexte(), GRILLE
    )
    assert [(s.entite, s.cle_a, s.cle_b) for s in sorties] == [("ENT-B", "DEMO-1", "DEMO-2")]
    assert len(traces) == 1


def test_sans_candidat_aucun_appel() -> None:
    factice = FournisseurFactice([])
    sorties, traces = detecter_doublons(
        _passerelle(factice), textes({"DEMO-3": LIGNES["DEMO-3"]}), DATE_ARRETE, _contexte(), GRILLE
    )
    assert (sorties, traces, factice.appels) == ((), (), [])


def test_plafond_de_cout_atteint_sans_paire_ni_echec(caplog: pytest.LogCaptureFixture) -> None:
    factice = FournisseurFactice([])
    with caplog.at_level(logging.WARNING):
        sorties, traces = detecter_doublons(
            _passerelle(factice, Decimal(0)), textes(LIGNES), DATE_ARRETE, _contexte(), GRILLE
        )
    assert (sorties, traces, factice.appels) == ((), (), [])
    assert "plafond de coût" in caplog.text
