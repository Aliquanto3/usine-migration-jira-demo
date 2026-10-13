"""Tâche `doublons` : paires d'Anomalies ouvertes probablement en doublon (FR-36, Story 6.11)."""

from datetime import date
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
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ReponseDoublon, SortieDoublon, StatutControle, Tache
from usine.contrats.versions import version_prompt
from usine.ia.doublons import (
    MAX_ECHECS_CONSECUTIFS,
    MAX_PAIRES,
    ContexteDoublons,
    cles_ouvertes,
    detecter,
    lire_prompt,
    paires_candidates,
)
from usine.ia.passerelle import Passerelle

TEXTES_PAR_CLE = {
    "DEMO-10": ("Solde faux après reprise", "Le solde repris diffère de l'ancien système."),
    "DEMO-2": ("Solde faux après la reprise", "Le solde repris diffère de l'ancien système."),
    "DEMO-3": ("Flux en retard", "Le fichier du flux comptable arrive en retard."),
    "DEMO-4": ("Paramètre devise absent", "Le code devise n'est pas paramétré."),
    "DEMO-5": ("Solde faux après reprise", "Le solde repris diffère de l'ancien système."),
}
TEXTES = textes(TEXTES_PAR_CLE)
OUVERTES = frozenset(TEXTES_PAR_CLE)


def _contexte() -> ContexteDoublons:
    return ContexteDoublons(
        passage_id=PASSAGE_ID,
        version_donnees="d" * 64,
        version_grille="grille123456",
        gabarit=lire_prompt(),
    )


def _passerelle(factice: FournisseurFactice, plafond: Decimal | None = None) -> Passerelle:
    return Passerelle(
        factice,
        pseudonymiseur(),
        CacheMemoire(),
        horloge_espion([]),
        tarif=lambda *_: Decimal(1),
        plafond_cout_passage_eur=plafond,
    )


def _detecter(
    factice: FournisseurFactice,
    table: pl.DataFrame = TEXTES,
    ouvertes: frozenset[str] = OUVERTES,
    plafond: Decimal | None = None,
) -> tuple[tuple[SortieDoublon, ...], int]:
    sorties, traces = detecter(
        _passerelle(factice, plafond), table, ouvertes, DATE_ARRETE, _contexte()
    )
    return sorties, len(traces)


def test_paires_candidates_meme_entite_et_recouvrement() -> None:
    cles = [(a["cle_ticket"], b["cle_ticket"]) for _, a, b in paires_candidates(TEXTES, OUVERTES)]
    # Les trois Anomalies « Solde faux » forment trois paires ; ni flux ni devise n'y figurent.
    assert set(cles) == {("DEMO-2", "DEMO-5"), ("DEMO-2", "DEMO-10"), ("DEMO-5", "DEMO-10")}
    assert all(a != b for a, b in cles)


def test_paires_candidates_ignore_les_fermees_et_les_autres_entites() -> None:
    sans_deux = paires_candidates(TEXTES, OUVERTES - {"DEMO-2"})
    assert [(a["cle_ticket"], b["cle_ticket"]) for _, a, b in sans_deux] == [("DEMO-5", "DEMO-10")]
    autre = pl.concat(
        [
            textes({"DEMO-1": TEXTES_PAR_CLE["DEMO-5"]}),
            textes({"DEMO-2": TEXTES_PAR_CLE["DEMO-5"]}, "ENT-B"),
        ]
    )
    assert paires_candidates(autre, {"DEMO-1", "DEMO-2"}) == []


def test_paires_candidates_bornees() -> None:
    nombre = 20
    table = textes(
        {f"DEMO-{n}": ("Solde faux", "Le solde repris est faux.") for n in range(nombre)}
    )
    assert nombre * (nombre - 1) // 2 > MAX_PAIRES
    assert len(paires_candidates(table, {f"DEMO-{n}" for n in range(nombre)})) == MAX_PAIRES


def test_detection_scores_filtre_et_tri() -> None:
    factice = FournisseurFactice(
        [
            ReponseDoublon(score=0.9, justification="Même solde faux."),
            ReponseDoublon(score=0.3, justification="Peu probable."),
            ReponseDoublon(score=0.7),
        ]
    )
    sorties, nb_traces = _detecter(factice)
    assert nb_traces == 3
    assert len(factice.appels) == 3
    assert {a.parametres.tache for a in factice.appels} == {Tache.doublons}
    assert [s.score for s in sorties] == [0.9, 0.7]
    assert all(s.statut_controle is StatutControle.conforme for s in sorties)
    assert all(s.cle_a != s.cle_b for s in sorties)


def test_justification_citant_une_autre_cle_est_corrigee() -> None:
    table = textes({"DEMO-1": TEXTES_PAR_CLE["DEMO-5"], "DEMO-2": TEXTES_PAR_CLE["DEMO-5"]})
    factice = FournisseurFactice(
        [ReponseDoublon(score=0.8, justification="Même texte. Voir aussi DEMO-9.")]
    )
    sorties, _ = _detecter(factice, table, frozenset({"DEMO-1", "DEMO-2"}))
    assert len(sorties) == 1
    assert sorties[0].statut_controle is StatutControle.corrige
    assert "DEMO-9" not in sorties[0].justification
    assert sorties[0].justification == "Même texte."


def test_aucune_paire_aucun_appel() -> None:
    factice = FournisseurFactice()
    sorties, nb_traces = _detecter(factice, ouvertes=frozenset())
    assert (sorties, nb_traces, factice.appels) == ((), 0, [])


def test_plafond_de_cout_arrete_sans_echec() -> None:
    factice = FournisseurFactice([ReponseDoublon(score=0.9)] * 3)
    sorties, nb_traces = _detecter(factice, plafond=Decimal(0))
    assert (sorties, nb_traces, factice.appels) == ((), 0, [])


def test_echec_isole_laisse_la_paire_sans_score() -> None:
    factice = FournisseurFactice([ReponseDoublon(score=0.6), ReponseDoublon(score=0.9)])
    table = textes(
        {
            "DEMO-1": TEXTES_PAR_CLE["DEMO-5"],
            "DEMO-2": TEXTES_PAR_CLE["DEMO-5"],
            "DEMO-3": TEXTES_PAR_CLE["DEMO-5"],
        }
    )
    # Trois paires pour deux réponses scriptées : la troisième échoue sans faire échouer la tâche.
    sorties, _ = _detecter(factice, table, frozenset({"DEMO-1", "DEMO-2", "DEMO-3"}))
    assert [s.score for s in sorties] == [0.9, 0.6]


def test_echecs_consecutifs_font_echouer() -> None:
    factice = FournisseurFactice()
    table = textes({f"DEMO-{n}": TEXTES_PAR_CLE["DEMO-5"] for n in range(1, 5)})
    with pytest.raises(UsineErreur, match=f"doublons : {MAX_ECHECS_CONSECUTIFS} échecs"):
        _detecter(factice, table, frozenset(table["cle_ticket"].to_list()))


def test_rejeu_sans_appel() -> None:
    cache = CacheMemoire()
    reponses = [ReponseDoublon(score=0.9)] * 3
    passerelle = Passerelle(
        FournisseurFactice(reponses),
        pseudonymiseur(),
        cache,
        horloge_espion([]),
        tarif=lambda *_: Decimal(1),
    )
    premier, _ = detecter(passerelle, TEXTES, OUVERTES, DATE_ARRETE, _contexte())
    vide = FournisseurFactice()
    rejeu = Passerelle(
        vide, pseudonymiseur(), cache, horloge_espion([]), tarif=lambda *_: Decimal(1)
    )
    second, traces = detecter(rejeu, TEXTES, OUVERTES, DATE_ARRETE, _contexte())
    assert vide.appels == []
    assert second == premier
    assert {t.depuis_cache for t in traces} == {True}


def test_trace_et_prompt() -> None:
    factice = FournisseurFactice([ReponseDoublon(score=0.9)])
    table = textes({"DEMO-1": TEXTES_PAR_CLE["DEMO-5"], "DEMO-2": TEXTES_PAR_CLE["DEMO-5"]})
    _, traces = detecter(
        _passerelle(factice), table, {"DEMO-1", "DEMO-2"}, date(2026, 10, 9), _contexte()
    )
    (trace,) = traces
    assert trace.tache is Tache.doublons
    assert trace.cible == "DEMO-1+DEMO-2"
    assert trace.version_prompt == version_prompt(lire_prompt())
    prompt = factice.appels[0].entree
    assert isinstance(prompt, str)
    assert "DEMO-1 : Solde faux après reprise" in prompt
    assert "DEMO-2 : Solde faux après reprise" in prompt


def test_cles_ouvertes() -> None:
    etats = pl.DataFrame(
        {
            "date": [DATE_ARRETE] * 4,
            "cle_ticket": ["DEMO-1", "DEMO-2", "DEMO-3", "TEST-1"],
            "type_ticket": ["anomalie", "anomalie", "anomalie", "cas_de_test"],
            "statut": ["nouvelle", "fermee", "rejetee", None],
        },
        schema_overrides={"statut": pl.Utf8, "type_ticket": pl.Utf8},
    )
    assert cles_ouvertes(etats) == frozenset({"DEMO-1"})
