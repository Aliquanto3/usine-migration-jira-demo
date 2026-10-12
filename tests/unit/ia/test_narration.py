"""Tâche `narration` : phrase contrôlée par `controler_nombres`, repli sur la Prévision brute."""

import logging
from datetime import date
from decimal import Decimal
from fractions import Fraction

import pytest

from tests.doublures.fournisseur_factice import FournisseurFactice
from tests.unit.ia.espions import (
    DATE_ARRETE,
    PASSAGE_ID,
    CacheMemoire,
    horloge_espion,
    prevision_rouge,
    pseudonymiseur,
    risque_entree_rouge,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ReponseNarration, StatutControle, Tache
from usine.contrats.meteo import CodeIndicateur
from usine.contrats.prevision import FacteurExplicatif
from usine.contrats.versions import version_prompt
from usine.ia.controles import controler_nombres
from usine.ia.explication import rendre_prompt
from usine.ia.narration import ContexteNarration, lire_prompt, narrer, prevision_brute
from usine.ia.passerelle import Passerelle

GRILLE = "grille123456"


def _contexte() -> ContexteNarration:
    return ContexteNarration(passage_id=PASSAGE_ID, version_donnees="d" * 64, gabarit=lire_prompt())


def _passerelle(factice: FournisseurFactice, plafond: Decimal | None = None) -> Passerelle:
    return Passerelle(
        factice,
        pseudonymiseur(),
        CacheMemoire(),
        horloge_espion([]),
        plafond_cout_passage_eur=plafond,
    )


def test_narration_conforme_et_prompt_des_seules_valeurs() -> None:
    phrase = "ENT-A sortirait du rouge le 15/10/2026, avec 60 % de chances sous 10 jours ouvrés."
    factice = FournisseurFactice([ReponseNarration(texte=phrase)])
    sortie, traces = narrer(
        _passerelle(factice), "ENT-A", DATE_ARRETE, GRILLE, prevision_rouge(), (), _contexte()
    )
    assert sortie.texte == phrase
    assert sortie.statut_controle is StatutControle.conforme
    assert (sortie.entite, sortie.date_arrete) == ("ENT-A", DATE_ARRETE)
    (trace,) = traces
    assert trace.tache is Tache.narration
    assert trace.entite == trace.cible == "ENT-A"
    assert trace.version_grille == GRILLE
    assert trace.version_prompt == version_prompt(lire_prompt())
    (appel,) = factice.appels
    assert appel.parametres.max_jetons_sortie == 256
    prompt = str(appel.entree)
    for attendu in ("15/10/2026", "14/10/2026", "20/10/2026", "60 %", "1 234", "7/2"):
        assert attendu in prompt
    assert "```text\n### Entité ENT-A" in prompt


@pytest.mark.parametrize(
    "phrase",
    [
        "ENT-A sortirait du rouge dans 12 jours.",
        "ENT-A sortirait du rouge le 21/10/2026.",
        "   ",
    ],
)
def test_narration_rejetee_prevision_brute(phrase: str, caplog: pytest.LogCaptureFixture) -> None:
    factice = FournisseurFactice([ReponseNarration(texte=phrase)])
    with caplog.at_level(logging.WARNING):
        sortie, traces = narrer(
            _passerelle(factice), "ENT-A", DATE_ARRETE, GRILLE, prevision_rouge(), (), _contexte()
        )
    assert sortie.statut_controle is StatutControle.rejete
    assert sortie.texte == prevision_brute("ENT-A", DATE_ARRETE, prevision_rouge())
    assert len(traces) == 1
    assert len(factice.appels) == 1  # pas de régénération
    assert "rejetée" in caplog.text


def test_prevision_brute_passe_son_propre_controle() -> None:
    brute = prevision_brute("ENT-A", DATE_ARRETE, prevision_rouge(), (risque_entree_rouge(),))
    assert brute.startswith("Prévision brute.")
    assert "15/10/2026" in brute and "60 %" in brute
    valeurs = (
        DATE_ARRETE,
        date(2026, 10, 14),
        date(2026, 10, 15),
        date(2026, 10, 16),
        date(2026, 10, 20),
        Decimal("0.6"),
        10,
        1234,
        Fraction(7, 2),
        -3,
        4,
        6,
    )
    assert controler_nombres(brute, valeurs).conforme


def test_plafond_de_cout_prevision_brute(caplog: pytest.LogCaptureFixture) -> None:
    factice = FournisseurFactice()
    with caplog.at_level(logging.WARNING):
        sortie, traces = narrer(
            _passerelle(factice, Decimal(0)),
            "ENT-A",
            DATE_ARRETE,
            GRILLE,
            prevision_rouge(),
            (),
            _contexte(),
        )
    assert factice.appels == []
    assert traces == ()
    assert sortie.statut_controle is StatutControle.rejete
    assert sortie.texte == prevision_brute("ENT-A", DATE_ARRETE, prevision_rouge())
    assert "plafond" in caplog.text


def test_narration_de_l_ensemble_des_risques() -> None:
    risques = (risque_entree_rouge(CodeIndicateur.ind_1), risque_entree_rouge(CodeIndicateur.ind_3))
    phrase = "ENT-B risque d'entrer en rouge sur IND-1 et IND-3 vers le 16/10/2026."
    factice = FournisseurFactice([ReponseNarration(texte=phrase)])
    sortie, _ = narrer(
        _passerelle(factice), "ENT-B", DATE_ARRETE, GRILLE, None, risques, _contexte()
    )
    assert sortie.statut_controle is StatutControle.conforme
    prompt = str(factice.appels[0].entree)
    assert "Risque d'entrée en rouge sur IND-1" in prompt
    assert "Risque d'entrée en rouge sur IND-3" in prompt
    assert "Prévision de sortie du rouge" not in prompt


def test_rendre_prompt_nomme_la_tache() -> None:
    with pytest.raises(UsineErreur, match="« narration »"):
        rendre_prompt("{{entite}}", {}, Tache.narration)


def test_nombre_d_un_libelle_de_facteur_est_autorise() -> None:
    """Revue : « les 5 derniers Jours ouvrés » vient du libellé déterministe du facteur."""
    prevision = prevision_rouge().model_copy(
        update={
            "facteurs": (
                FacteurExplicatif(
                    nom="entrees",
                    libelle="Entrées sur les 5 derniers Jours ouvrés",
                    numerateur=8,
                    denominateur=1,
                ),
            )
        }
    )
    phrase = "ENT-A a reçu 8 Anomalies sur les 5 derniers Jours ouvrés."
    factice = FournisseurFactice([ReponseNarration(texte=phrase)])
    sortie, _ = narrer(
        _passerelle(factice), "ENT-A", DATE_ARRETE, GRILLE, prevision, (), _contexte()
    )
    assert sortie.statut_controle is StatutControle.conforme
