"""Contrats de configuration 1.1.0 : Scénarios de démo, Prévisions et décalage J-5 (AD-2).

Ajouts optionnels : un YAML v1.0 se valide toujours, avec les défauts H-7, H-8 et H-19.
"""

import copy
import math
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from usine.config import charger_yaml
from usine.contrats.config import (
    ConfigBaseline,
    ConfigChaine,
    ConfigProgramme,
    ConfigRisque,
    ConfigScenarios,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.tickets import StatutCertification
from usine.domaine.meteo import DECALAGE_IND8
from usine.domaine.prevision.baseline import ParametresBaseline
from usine.domaine.prevision.risque import ParametresRisque

RACINE = Path(__file__).resolve().parents[3]
PROGRAMME_LIVRE = RACINE / "config" / "programme.yaml"
PROGRAMME_REDUIT = RACINE / "tests" / "unit" / "generateur" / "programme_reduit.yaml"
CHAINE_LIVREE = RACINE / "config" / "chaine.yaml"


def _programme_livre() -> dict[str, Any]:
    donnees: dict[str, Any] = yaml.safe_load(PROGRAMME_LIVRE.read_text(encoding="utf-8"))
    return donnees


# --- Programme : Scénarios de démo ---


def test_programme_livre_porte_les_scenarios() -> None:
    scenarios = charger_yaml(PROGRAMME_LIVRE, ConfigProgramme).scenarios
    assert scenarios is not None
    assert scenarios.sortie is not None
    assert scenarios.enlisement is not None
    assert scenarios.menace is not None
    assert [s.entite for _, s in scenarios.actifs()] == ["ENT-A", "ENT-B", "ENT-C"]
    assert scenarios.sortie.statut_certification is StatutCertification.accordee
    assert scenarios.enlisement.statut_certification is StatutCertification.reservee
    assert scenarios.menace.taux_ko_hausse == (0.045, 0.065, 0.07, 0.14, 0.18)


def test_programme_livre_flux_scripte_v1_2() -> None:
    """Contrats 1.2.0 : bloquantes scriptées de A et B (flux par semaine, durée fixe)."""
    scenarios = charger_yaml(PROGRAMME_LIVRE, ConfigProgramme).scenarios
    assert scenarios is not None
    assert scenarios.sortie is not None
    assert scenarios.enlisement is not None
    assert scenarios.menace is not None
    sortie, enlisement = scenarios.sortie, scenarios.enlisement
    assert (sortie.bloquantes_bascule, sortie.bloquantes_par_semaine) == (4, (9, 2, 4))
    assert sortie.duree_bloquantes == 7
    assert enlisement.bloquantes_par_semaine == (3, 3, 4, 4, 5, 5, 6)
    assert (enlisement.duree_bloquantes, enlisement.part_majeures) == (8, 0.03)
    assert scenarios.menace.cas_de_test_par_semaine == 50


def test_programme_livre_volumetrie_h2() -> None:
    volumetrie = charger_yaml(PROGRAMME_LIVRE, ConfigProgramme).volumetrie
    assert (volumetrie.anomalies_min, volumetrie.anomalies_max) == (3000, 4000)


def test_programme_v1_0_sans_scenarios() -> None:
    assert charger_yaml(PROGRAMME_REDUIT, ConfigProgramme).scenarios is None
    donnees = _programme_livre()
    del donnees["scenarios"]
    assert ConfigProgramme.model_validate(donnees).scenarios is None


def test_scenario_desactive() -> None:
    donnees = _programme_livre()
    donnees["scenarios"] = {"sortie": donnees["scenarios"]["sortie"], "menace": None}
    scenarios = ConfigProgramme.model_validate(donnees).scenarios
    assert scenarios is not None
    assert (scenarios.enlisement, scenarios.menace) == (None, None)
    assert [nom for nom, _ in scenarios.actifs()] == ["sortie"]
    assert ConfigScenarios().actifs() == ()


def test_semaine_au_dela_du_programme_acceptee() -> None:
    """Une semaine au-delà de `nb_semaines` n'est pas refusée : le générateur ignore ce
    Scénario, ce qui garde valide une copie raccourcie du Programme livré (`test_calage`)."""
    donnees = _programme_livre()
    donnees["scenarios"]["sortie"]["semaine_vague"] = donnees["nb_semaines"] + 1
    scenarios = ConfigProgramme.model_validate(donnees).scenarios
    assert scenarios is not None
    assert scenarios.sortie is not None
    assert scenarios.sortie.semaine_vague == 9


def _scenario(nom: str, cle: str, valeur: object) -> Callable[[dict[str, Any]], None]:
    def modifier(scenarios: dict[str, Any]) -> None:
        scenarios[nom][cle] = valeur

    return modifier


def _sans(nom: str, cle: str) -> Callable[[dict[str, Any]], None]:
    def modifier(scenarios: dict[str, Any]) -> None:
        del scenarios[nom][cle]

    return modifier


INCOHERENTS: dict[str, Callable[[dict[str, Any]], None]] = {
    "entite_inconnue": _scenario("sortie", "entite", "ENT-Z"),
    "entite_mal_formee": _scenario("sortie", "entite", "A"),
    "entite_partagee": _scenario("enlisement", "entite", "ENT-A"),
    "semaine_zero": _scenario("menace", "semaine_hausse", 0),
    "semaine_decimale": _scenario("enlisement", "semaine_debut", 2.5),
    "semaine_texte": _scenario("sortie", "semaine_vague", "6"),
    "bloquantes_negatives": _scenario("sortie", "bloquantes_bascule", -1),
    "bloquantes_booleen": _scenario("enlisement", "bloquantes_bascule", True),
    "cas_de_test_nuls": _scenario("menace", "cas_de_test_par_semaine", 0),
    "taux_superieur_a_1": _scenario("enlisement", "part_majeures", 1.5),
    "taux_negatif": _scenario("menace", "taux_ko_initial", -0.1),
    "taux_nan": _scenario("menace", "taux_ko_initial", math.nan),
    "taux_ko_hausse_superieur_a_1": _scenario("menace", "taux_ko_hausse", [0.1, 1.2]),
    "taux_ko_hausse_vide": _scenario("menace", "taux_ko_hausse", []),
    "poids_nul": _scenario("enlisement", "poids", 0),
    "poids_negatif": _scenario("sortie", "poids_decrue", -0.5),
    "poids_infini": _scenario("sortie", "poids_vague", math.inf),
    "flux_vide": _scenario("sortie", "bloquantes_par_semaine", []),
    "flux_negatif": _scenario("enlisement", "bloquantes_par_semaine", [3, -1]),
    "flux_decimal": _scenario("sortie", "bloquantes_par_semaine", [9, 2.5]),
    "duree_trop_courte": _scenario("sortie", "duree_bloquantes", 3),
    "duree_trop_longue": _scenario("enlisement", "duree_bloquantes", 11),
    "duree_manquante": _sans("enlisement", "duree_bloquantes"),
    "part_bloquantes_retiree_v1_2": _scenario("enlisement", "part_bloquantes", 0.06),
    "part_bloquantes_vague_retiree_v1_2": _scenario("sortie", "part_bloquantes_vague", 0.4),
    "statut_inconnu": _scenario("enlisement", "statut_certification", "perdue"),
    "champ_manquant": _sans("sortie", "poids_vague"),
    "cle_inconnue": _scenario("menace", "taux", 0.1),
}


@pytest.mark.parametrize("modifier", INCOHERENTS.values(), ids=INCOHERENTS.keys())
def test_scenario_incoherent_refuse(modifier: Callable[[dict[str, Any]], None]) -> None:
    donnees = _programme_livre()
    modifier(donnees["scenarios"])
    with pytest.raises(ValidationError):
        ConfigProgramme.model_validate(donnees)


def test_scenarios_cle_inconnue_refusee() -> None:
    donnees = _programme_livre()
    donnees["scenarios"]["crise"] = copy.deepcopy(donnees["scenarios"]["sortie"])
    with pytest.raises(ValidationError):
        ConfigProgramme.model_validate(donnees)


def test_scenario_incoherent_nomme_au_chargement(tmp_path: Path) -> None:
    fautive = tmp_path / "programme.yaml"
    fautive.write_text(
        PROGRAMME_LIVRE.read_text(encoding="utf-8").replace("entite: ENT-C", "entite: ENT-Z"),
        encoding="utf-8",
    )
    with pytest.raises(UsineErreur) as erreur:
        charger_yaml(fautive, ConfigProgramme)
    message = str(erreur.value)
    assert str(fautive) in message
    assert "scenarios.menace" in message
    assert "ENT-Z" in message


# --- Chaîne : Prévisions et décalage de comparaison ---


def test_chaine_v1_0_aux_defauts() -> None:
    chaine = ConfigChaine.model_validate({"palier": 1})
    baseline, risque = chaine.prevision.baseline, chaine.prevision.risque
    assert (
        baseline.fenetre_velocite,
        baseline.horizon,
        baseline.fenetre_fourchette,
        baseline.profondeur_fourchette,
    ) == (10, 10, 5, 20)
    assert (risque.fenetre, risque.horizon) == (10, 5)
    assert chaine.decalage_comparaison == 5


def test_chaine_livree_aux_valeurs_par_defaut() -> None:
    chaine = charger_yaml(CHAINE_LIVREE, ConfigChaine)
    assert chaine == ConfigChaine(palier=1)
    donnees = yaml.safe_load(CHAINE_LIVREE.read_text(encoding="utf-8"))
    assert set(donnees) == {"palier", "prevision", "decalage_comparaison"}
    assert set(donnees["prevision"]) == {"baseline", "risque"}
    assert set(donnees["prevision"]["baseline"]) == {
        "fenetre_velocite",
        "horizon",
        "fenetre_fourchette",
        "profondeur_fourchette",
    }
    assert set(donnees["prevision"]["risque"]) == {"fenetre", "horizon"}


def test_defauts_alignes_sur_le_domaine() -> None:
    """Les défauts reproduisent ceux du domaine, que la composition construira (L5)."""
    assert ConfigBaseline().model_dump() == asdict(ParametresBaseline())
    assert ConfigRisque().model_dump() == asdict(ParametresRisque())
    assert ConfigChaine(palier=1).decalage_comparaison == DECALAGE_IND8


def test_chaine_partielle() -> None:
    chaine = ConfigChaine.model_validate(
        {"palier": 2, "prevision": {"risque": {"horizon": 3}}, "decalage_comparaison": 4}
    )
    assert chaine.prevision.baseline == ConfigBaseline()
    assert chaine.prevision.risque == ConfigRisque(fenetre=10, horizon=3)
    assert chaine.decalage_comparaison == 4


@pytest.mark.parametrize(
    "donnees",
    [
        {"prevision": {"baseline": {"horizon": 0}}},
        {"prevision": {"baseline": {"fenetre_velocite": True}}},
        {"prevision": {"baseline": {"profondeur_fourchette": 2.5}}},
        {"prevision": {"baseline": {"fenetre_fourchette": 5.0}}},
        {"prevision": {"risque": {"fenetre": 0}}},
        {"prevision": {"risque": {"horizon": "5"}}},
        {"decalage_comparaison": 0},
        {"decalage_comparaison": True},
        {"decalage_comparaison": 2.5},
        {"prevision": {"baseline": {"inconnue": 1}}},
        {"prevision": {"tendance": {}}},
        {"decalage": 5},
    ],
    ids=str,
)
def test_parametre_chaine_invalide(donnees: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ConfigChaine.model_validate({"palier": 1, **donnees})


def test_parametre_chaine_invalide_nomme(tmp_path: Path) -> None:
    chemin = tmp_path / "chaine.yaml"
    chemin.write_text(
        "# Palier.\npalier: 1\n# Prévision.\nprevision:\n  # Baseline.\n  baseline:\n"
        "    # Horizon.\n    horizon: 0\n",
        encoding="utf-8",
    )
    with pytest.raises(UsineErreur) as erreur:
        charger_yaml(chemin, ConfigChaine)
    assert "« prevision.baseline.horizon »" in str(erreur.value)
