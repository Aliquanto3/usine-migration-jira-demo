"""Tâche `doublons` : paires d'Anomalies probablement en doublon, avec un score (FR-36, bonus)."""

import logging
from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from tests.doublures.fournisseur_factice import FournisseurFactice
from tests.unit.ia.espions import (
    DATE_ARRETE,
    NUMERO_COMPTE,
    PASSAGE_ID,
    CacheMemoire,
    horloge_espion,
    jeton_compte,
    pseudonymiseur,
    textes,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ReponseDoublons, SortieDoublons, StatutControle, Tache
from usine.contrats.trace import EntreeTrace, TypeTrace
from usine.contrats.versions import version_prompt
from usine.ia.doublons import (
    MAX_ECHECS_CONSECUTIFS,
    SEUIL_SCORE,
    ContexteDoublons,
    detecter_doublons,
    lire_prompt,
    mots,
    preselectionner,
    similarite,
)
from usine.ia.passerelle import Passerelle

AUTRE_DATE = date(2026, 10, 13)
TEXTES = textes(
    {
        "DEMO-10": ("Flux comptable en retard", "Le fichier du flux comptable arrive en retard."),
        "DEMO-2": ("Retard du flux comptable", "Le fichier du flux comptable est livré en retard."),
        "DEMO-1": ("Solde faux", "Le solde repris diffère de l'ancien système."),
        "DEMO-3": ("Devise absente", "Le code devise n'est pas paramétré."),
    }
)
"""Un seul couple proche : DEMO-2 et DEMO-10 (flux comptable en retard)."""
OUVERTES = ("DEMO-1", "DEMO-2", "DEMO-3", "DEMO-10")


def _contexte() -> ContexteDoublons:
    return ContexteDoublons(passage_id=PASSAGE_ID, version_donnees="d" * 64, gabarit=lire_prompt())


def _passerelle(
    factice: FournisseurFactice, cache: CacheMemoire | None = None, plafond: Decimal | None = None
) -> Passerelle:
    return Passerelle(
        factice,
        pseudonymiseur(),
        cache if cache is not None else CacheMemoire(),
        horloge_espion([]),
        tarif=lambda *_: Decimal(1),
        plafond_cout_passage_eur=plafond,
    )


def _detecter(
    factice: FournisseurFactice,
    table: pl.DataFrame = TEXTES,
    ouvertes: tuple[str, ...] = OUVERTES,
    cache: CacheMemoire | None = None,
    date_arrete: date = DATE_ARRETE,
    plafond: Decimal | None = None,
) -> tuple[tuple[SortieDoublons, ...], tuple[EntreeTrace, ...]]:
    return detecter_doublons(
        _passerelle(factice, cache, plafond),
        table,
        ouvertes,
        date_arrete,
        "grille123456",
        _contexte(),
    )


def _reponse(score: int = 90, justification: str = "Même flux en retard.") -> ReponseDoublons:
    return ReponseDoublons(score=score, justification=justification)


def test_mots_sans_accent_ni_mot_vide() -> None:
    assert mots("Écart du Solde", "Le solde est faux (2 cas)") == {"ecart", "solde", "faux", "cas"}
    assert mots(None, None) == frozenset()


def test_similarite_de_jaccard() -> None:
    assert similarite(frozenset({"a", "b"}), frozenset({"b", "c"})) == pytest.approx(1 / 3)
    assert similarite(frozenset(), frozenset()) == 0.0


def test_preselection_garde_la_paire_proche_seulement() -> None:
    candidates = preselectionner(TEXTES, OUVERTES)
    assert [(c.ligne_a["cle_ticket"], c.ligne_b["cle_ticket"]) for c in candidates] == [
        ("DEMO-2", "DEMO-10")
    ]


def test_preselection_ignore_les_anomalies_fermees() -> None:
    assert preselectionner(TEXTES, ("DEMO-1", "DEMO-3", "DEMO-10")) == ()


def test_preselection_ignore_les_cas_de_test() -> None:
    table = TEXTES.with_columns(
        pl.when(pl.col("cle_ticket") == "DEMO-10")
        .then(pl.lit("cas_de_test"))
        .otherwise(pl.col("type_ticket"))
        .alias("type_ticket")
    )
    assert preselectionner(table, OUVERTES) == ()


def test_preselection_bornee_aux_plus_proches() -> None:
    table = textes(
        {
            "DEMO-1": ("Flux comptable en retard", "Fichier du flux comptable en retard."),
            "DEMO-2": ("Flux comptable en retard", "Fichier du flux comptable en retard."),
            "DEMO-3": ("Flux comptable en retard", "Fichier du flux comptable livré."),
        }
    )
    candidates = preselectionner(table, ("DEMO-1", "DEMO-2", "DEMO-3"), max_paires=2)
    paires = [(c.ligne_a["cle_ticket"], c.ligne_b["cle_ticket"]) for c in candidates]
    assert paires[0] == ("DEMO-1", "DEMO-2")
    assert len(paires) == 2


def test_paire_au_dessus_du_seuil_publiee_avec_son_score() -> None:
    factice = FournisseurFactice([_reponse(90)])
    sorties, traces = _detecter(factice)
    assert len(sorties) == 1
    paire = sorties[0]
    assert (paire.cle_a, paire.cle_b, paire.score) == ("DEMO-2", "DEMO-10", 90)
    assert paire.statut_controle is StatutControle.conforme
    assert paire.justification == "Même flux en retard."
    assert len(factice.appels) == 1
    assert factice.appels[0].parametres.tache is Tache.doublons
    (trace,) = traces
    assert trace.type_trace is TypeTrace.llm
    assert trace.tache is Tache.doublons
    assert trace.cible == "DEMO-2|DEMO-10"
    assert trace.entite == "ENT-A"
    assert trace.version_prompt == version_prompt(lire_prompt())
    assert trace.version_grille == "grille123456"
    assert not trace.depuis_cache


def test_paire_sous_le_seuil_non_publiee_mais_tracee() -> None:
    sorties, traces = _detecter(FournisseurFactice([_reponse(SEUIL_SCORE - 1)]))
    assert sorties == ()
    assert len(traces) == 1


def test_aucune_paire_proche_aucun_appel() -> None:
    factice = FournisseurFactice()
    sorties, traces = _detecter(factice, ouvertes=("DEMO-1", "DEMO-3"))
    assert (sorties, traces) == ((), ())
    assert factice.appels == []


def test_paires_triees_par_score_decroissant() -> None:
    table = textes(
        {
            "DEMO-1": ("Flux comptable en retard", "Fichier du flux comptable en retard."),
            "DEMO-2": ("Flux comptable en retard", "Fichier du flux comptable en retard."),
            "DEMO-3": ("Flux comptable en retard", "Fichier du flux comptable livré."),
        }
    )
    reponses = [_reponse(75), _reponse(95), _reponse(85)]
    sorties, _ = _detecter(FournisseurFactice(reponses), table, ("DEMO-1", "DEMO-2", "DEMO-3"))
    assert [s.score for s in sorties] == [95, 85, 75]
    assert all(rang_a_avant_b(s) for s in sorties)


def rang_a_avant_b(sortie: SortieDoublons) -> bool:
    return int(sortie.cle_a.split("-")[1]) < int(sortie.cle_b.split("-")[1])


def test_justification_citant_une_autre_cle_corrigee() -> None:
    reponse = _reponse(88, "Même flux que DEMO-2. Voir aussi DEMO-99.")
    sorties, traces = _detecter(FournisseurFactice([reponse]))
    assert sorties[0].justification == "Même flux que DEMO-2."
    assert sorties[0].statut_controle is StatutControle.corrige
    assert traces[0].phrases_retirees == 1


def test_rejeu_sans_appel_depuis_le_cache() -> None:
    cache = CacheMemoire()
    premier, _ = _detecter(FournisseurFactice([_reponse()]), cache=cache)
    factice = FournisseurFactice()
    sorties, traces = _detecter(factice, cache=cache)
    assert factice.appels == []
    assert sorties == premier
    assert {t.depuis_cache for t in traces} == {True}


def test_texte_modifie_relance_l_appel() -> None:
    cache = CacheMemoire()
    _detecter(FournisseurFactice([_reponse()]), cache=cache)
    modifie = TEXTES.with_columns(
        pl.when(pl.col("cle_ticket") == "DEMO-10")
        .then(pl.lit("Le fichier du flux comptable arrive en retard, toujours."))
        .otherwise(pl.col("description"))
        .alias("description")
    )
    factice = FournisseurFactice([_reponse()])
    _detecter(factice, modifie, cache=cache)
    assert len(factice.appels) == 1


def test_entree_pseudonymisee_avant_le_fournisseur() -> None:
    table = textes(
        {
            "DEMO-1": ("Virement refusé", f"Le compte {NUMERO_COMPTE} est refusé en virement."),
            "DEMO-2": ("Virement refusé", f"Compte {NUMERO_COMPTE} : virement refusé."),
        }
    )
    factice = FournisseurFactice([_reponse(80, f"Même compte {jeton_compte()}.")])
    sorties, traces = _detecter(factice, table, ("DEMO-1", "DEMO-2"))
    envoye = str(factice.appels[0].entree)
    assert NUMERO_COMPTE not in envoye
    assert jeton_compte() in envoye
    assert NUMERO_COMPTE not in traces[0].entree_pseudonymisee
    assert NUMERO_COMPTE in sorties[0].justification  # ré-identifiée localement


def test_plafond_atteint_paires_restantes_non_demandees(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tarif de 1 € par appel, plafond de 0,5 € : le premier appel passe, l'autre non."""
    table = textes(
        {
            "DEMO-1": ("Flux comptable en retard", "Fichier du flux comptable en retard."),
            "DEMO-2": ("Flux comptable en retard", "Fichier du flux comptable en retard."),
            "DEMO-3": ("Flux comptable en retard", "Fichier du flux comptable livré."),
        }
    )
    factice = FournisseurFactice([_reponse()] * 3)
    with caplog.at_level(logging.WARNING):
        sorties, traces = _detecter(
            factice, table, ("DEMO-1", "DEMO-2", "DEMO-3"), plafond=Decimal("0.5")
        )
    assert len(factice.appels) == 1
    assert len(sorties) == 1 and len(traces) == 1
    assert any("plafond" in m for m in caplog.messages)


def test_echec_isole_paire_sans_score(caplog: pytest.LogCaptureFixture) -> None:
    table = textes(
        {
            "DEMO-1": ("Flux comptable en retard", "Fichier du flux comptable en retard."),
            "DEMO-2": ("Flux comptable en retard", "Fichier du flux comptable en retard."),
            "DEMO-3": ("Flux comptable en retard", "Fichier du flux comptable livré."),
        }
    )
    factice = FournisseurFactice([_reponse(90)])  # la deuxième paire n'a pas de réponse
    with caplog.at_level(logging.WARNING):
        sorties, traces = _detecter(factice, table, ("DEMO-1", "DEMO-2", "DEMO-3"))
    assert [(s.cle_a, s.cle_b) for s in sorties] == [("DEMO-1", "DEMO-2")]
    assert len(traces) >= 1
    assert any("en échec" in m for m in caplog.messages)


def test_echecs_consecutifs_font_echouer_la_tache() -> None:
    lignes = {
        f"DEMO-{n}": ("Flux comptable en retard", "Fichier du flux en retard.") for n in range(1, 6)
    }
    with pytest.raises(UsineErreur, match="doublons"):
        _detecter(FournisseurFactice(), textes(lignes), tuple(lignes))
    assert MAX_ECHECS_CONSECUTIFS == 3
