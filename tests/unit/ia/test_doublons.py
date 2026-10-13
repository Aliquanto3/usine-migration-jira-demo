"""Tâche `doublons` : paires d'Anomalies ouvertes confirmées par le modèle, sans écriture."""

import logging
from datetime import date
from decimal import Decimal
from typing import cast

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
from usine.contrats.agent import AnomalieResume, ResultatListAnomalies
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ReponseDoublons, StatutControle, Tache
from usine.contrats.tickets import Gravite, Phase, StatutAnomalie
from usine.contrats.versions import version_prompt
from usine.ia.doublons import (
    MAX_ECHECS_CONSECUTIFS,
    SEUIL_CANDIDAT,
    ContexteDoublons,
    detecter,
    detecter_doublons,
    lire_prompt,
    paires_candidates,
    similarite,
)
from usine.ia.passerelle import Passerelle
from usine.ports.consultation import Consultation

TEXTES_PAR_CLE = {
    "DEMO-10": ("Solde faux après reprise", "Le solde repris diffère de l'ancien système."),
    "DEMO-2": ("Écart de solde après reprise", "Le solde repris diffère de l'ancien système."),
    "DEMO-3": ("Flux en retard", "Le fichier du flux comptable arrive en retard."),
    "DEMO-4": ("Solde faux après reprise", "Le solde repris diffère de l'ancien système."),
}
TEXTES = textes(TEXTES_PAR_CLE)
OUVERTES = ("DEMO-10", "DEMO-2", "DEMO-3")
"""DEMO-4 est fermée : jamais comparée."""


def _contexte() -> ContexteDoublons:
    return ContexteDoublons(
        passage_id=PASSAGE_ID,
        version_donnees="d" * 64,
        version_grille="grille123456",
        gabarit=lire_prompt(),
    )


def _passerelle(
    factice: FournisseurFactice,
    cache: CacheMemoire | None = None,
    plafond: Decimal | None = None,
) -> Passerelle:
    return Passerelle(
        factice,
        pseudonymiseur(),
        cache if cache is not None else CacheMemoire(),
        horloge_espion([]),
        tarif=lambda *_: Decimal(1),
        plafond_cout_passage_eur=plafond,
    )


def _oui(justification: str = "Même écart de solde.") -> ReponseDoublons:
    return ReponseDoublons(doublon=True, justification=justification)


def test_similarite_de_jaccard() -> None:
    assert similarite({"a", "b"}, {"a", "b"}) == 1.0
    assert similarite({"a", "b", "c"}, {"a", "d"}) == 0.25
    assert similarite(set(), set()) == 0.0


def test_paires_candidates_ouvertes_triees_et_bornees() -> None:
    paires = paires_candidates(TEXTES, OUVERTES)
    assert [(p.a.cle, p.b.cle) for p in paires] == [("DEMO-2", "DEMO-10")]
    assert paires[0].score >= SEUIL_CANDIDAT
    assert paires_candidates(TEXTES, OUVERTES, seuil=0.99) == ()
    plus = paires_candidates(TEXTES, ("DEMO-10", "DEMO-2", "DEMO-4"), maximum=1)
    assert len(plus) == 1
    assert plus[0].score == 1.0


def test_paires_candidates_ecarte_les_tickets_qui_ne_sont_pas_des_anomalies() -> None:
    table = TEXTES.with_columns(
        pl.when(pl.col("cle_ticket") == "DEMO-2")
        .then(pl.lit("cas_de_test"))
        .otherwise(pl.col("type_ticket"))
        .alias("type_ticket")
    )
    assert paires_candidates(table, OUVERTES) == ()


def test_paire_confirmee_publiee_avec_score_local_et_trace() -> None:
    factice = FournisseurFactice([_oui()])
    sorties, traces = detecter(_passerelle(factice), TEXTES, OUVERTES, DATE_ARRETE, _contexte())
    (sortie,) = sorties
    assert (sortie.cle_a, sortie.cle_b) == ("DEMO-2", "DEMO-10")
    assert sortie.score == paires_candidates(TEXTES, OUVERTES)[0].score
    assert sortie.justification == "Même écart de solde."
    assert sortie.statut_controle is StatutControle.conforme
    (appel,) = factice.appels
    assert appel.parametres.tache is Tache.doublons
    assert "DEMO-2 : Écart de solde après reprise" in str(appel.entree)
    assert "DEMO-10 : Solde faux après reprise" in str(appel.entree)
    assert "DEMO-3" not in str(appel.entree)
    (trace,) = traces
    assert trace.tache is Tache.doublons
    assert trace.cible == "DEMO-2|DEMO-10"
    assert trace.entite == "ENT-A"
    assert trace.version_prompt == version_prompt(lire_prompt())


def test_paire_refusee_par_le_modele_n_est_pas_publiee_mais_tracee() -> None:
    factice = FournisseurFactice([ReponseDoublons(doublon=False, justification="Distincts.")])
    sorties, traces = detecter(_passerelle(factice), TEXTES, OUVERTES, DATE_ARRETE, _contexte())
    assert sorties == ()
    assert len(traces) == 1


def test_justification_citant_un_autre_ticket_est_corrigee() -> None:
    reponse = _oui("Même écart de solde. Voir aussi DEMO-3. Même reprise.")
    sorties, _ = detecter(
        _passerelle(FournisseurFactice([reponse])), TEXTES, OUVERTES, DATE_ARRETE, _contexte()
    )
    assert sorties[0].statut_controle is StatutControle.corrige
    assert "DEMO-3" not in sorties[0].justification
    assert sorties[0].justification == "Même écart de solde. Même reprise."


def test_textes_pseudonymises_avant_le_fournisseur_puis_restitues() -> None:
    table = textes(
        {
            "DEMO-1": ("Compte rejeté", f"Le compte {NUMERO_COMPTE} est rejeté au chargement."),
            "DEMO-2": ("Compte rejeté", f"Le compte {NUMERO_COMPTE} est rejeté au chargement."),
        }
    )
    jeton = jeton_compte()
    factice = FournisseurFactice([_oui(f"Même compte {jeton}.")])
    sorties, traces = detecter(
        _passerelle(factice), table, ("DEMO-1", "DEMO-2"), DATE_ARRETE, _contexte()
    )
    assert NUMERO_COMPTE not in str(factice.appels[0].entree)
    assert jeton in str(factice.appels[0].entree)
    assert NUMERO_COMPTE not in traces[0].entree_pseudonymisee
    assert NUMERO_COMPTE not in traces[0].sortie
    assert sorties[0].justification == f"Même compte {NUMERO_COMPTE}."


def test_rejeu_servi_par_le_cache_sans_nouvel_appel() -> None:
    cache = CacheMemoire()
    premier = FournisseurFactice([_oui()])
    detecter(_passerelle(premier, cache), TEXTES, OUVERTES, DATE_ARRETE, _contexte())
    second = FournisseurFactice()
    sorties, traces = detecter(
        _passerelle(second, cache), TEXTES, OUVERTES, DATE_ARRETE, _contexte()
    )
    assert second.appels == []
    assert len(sorties) == 1
    assert traces[0].depuis_cache


def test_plafond_de_cout_arrete_les_paires_restantes(caplog: pytest.LogCaptureFixture) -> None:
    table = textes({f"DEMO-{n}": ("Solde faux", "Le solde diffère.") for n in range(1, 4)})
    ouvertes = ("DEMO-1", "DEMO-2", "DEMO-3")
    factice = FournisseurFactice([_oui(), _oui(), _oui()])
    with caplog.at_level(logging.WARNING):
        sorties, _ = detecter(
            _passerelle(factice, plafond=Decimal(1)), table, ouvertes, DATE_ARRETE, _contexte()
        )
    assert len(factice.appels) == 1
    assert len(sorties) == 1
    assert "plafond" in caplog.text


def test_echec_isole_ecarte_la_paire_et_echecs_consecutifs_font_echouer() -> None:
    table = textes({f"DEMO-{n}": ("Solde faux", "Le solde diffère.") for n in range(1, 5)})
    ouvertes = tuple(f"DEMO-{n}" for n in range(1, 5))
    # aucune réponse scriptée : chaque appel échoue
    factice = FournisseurFactice([])
    with pytest.raises(UsineErreur, match=f"{MAX_ECHECS_CONSECUTIFS} échecs consécutifs"):
        detecter(_passerelle(factice), table, ouvertes, DATE_ARRETE, _contexte())
    assert len(factice.appels) == MAX_ECHECS_CONSECUTIFS

    mixte = FournisseurFactice([])
    sorties, traces = detecter(_passerelle(mixte), table, ouvertes[:2], DATE_ARRETE, _contexte())
    assert sorties == ()
    assert len(traces) == 1
    assert traces[0].en_echec


class _ConsultationAnomalies:
    """Consultation réduite aux Anomalies ouvertes et à leurs textes."""

    def textes_tickets(self) -> pl.DataFrame:
        return TEXTES

    def anomalies(self, date_arrete: date | None = None) -> ResultatListAnomalies:
        resumes = tuple(
            AnomalieResume(
                cle_ticket=cle,
                entite="ENT-A",
                gravite=Gravite.majeure,
                phase=Phase.recette,
                domaine="Comptes",
                statut=StatutAnomalie.nouvelle,
                age_jours_ouvres=1,
            )
            for cle in OUVERTES
        )
        return ResultatListAnomalies(
            date_arrete=date_arrete or DATE_ARRETE, anomalies=resumes, total=len(resumes)
        )


def test_detecter_doublons_lit_les_anomalies_ouvertes_via_la_consultation() -> None:
    factice = FournisseurFactice([_oui()])
    sorties, _ = detecter_doublons(
        _passerelle(factice),
        cast(Consultation, _ConsultationAnomalies()),
        DATE_ARRETE,
        _contexte(),
    )
    assert [(s.cle_a, s.cle_b) for s in sorties] == [("DEMO-2", "DEMO-10")]
