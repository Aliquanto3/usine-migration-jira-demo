"""Scénarios de démo lus dans `config/programme.yaml` (contrats 1.1.0, FR-3).

La clé `scenarios` remplace `SCENARIOS_PAR_DEFAUT` quand `generer` reçoit `scenarios=None` ;
la configuration livrée en reprend les valeurs, donc le Journal ne change pas.
"""

from datetime import date
from pathlib import Path
from typing import Any

import yaml
from typer.testing import CliRunner

from usine.cli import app
from usine.config import charger_yaml
from usine.contrats.config import ConfigJira, ConfigProgramme, ConfigScenarios
from usine.contrats.tickets import StatutCertification
from usine.generateur.corpus import charger_corpus
from usine.generateur.journal import generer, serialiser_journal
from usine.generateur.scenarios import (
    AUCUN_SCENARIO,
    SCENARIOS_PAR_DEFAUT,
    ScenarioEnlisement,
    ScenarioMenace,
    Scenarios,
    ScenarioSortie,
    scenarios_de_config,
)

RACINE = Path(__file__).resolve().parents[3]
PROGRAMME_LIVRE = RACINE / "config" / "programme.yaml"
PROGRAMME_REDUIT = Path(__file__).with_name("programme_reduit.yaml")
CONFIG_JIRA = RACINE / "config" / "jira.yaml"
CORPUS = RACINE / "donnees" / "corpus" / "textes.json"
GRAINE = 42
DATE_GENERATION = date(2026, 10, 12)


def _scenarios_livres() -> dict[str, Any]:
    donnees: dict[str, Any] = yaml.safe_load(PROGRAMME_LIVRE.read_text(encoding="utf-8"))
    scenarios: dict[str, Any] = donnees["scenarios"]
    return scenarios


def _reduit(scenarios: dict[str, Any] | None) -> dict[str, Any]:
    """Programme réduit (ENT-A, ENT-B), avec la clé `scenarios` si elle est fournie."""
    donnees: dict[str, Any] = yaml.safe_load(PROGRAMME_REDUIT.read_text(encoding="utf-8"))
    if scenarios is not None:
        donnees["scenarios"] = scenarios
    return donnees


def _config_reduite(scenarios: dict[str, Any] | None) -> ConfigProgramme:
    return ConfigProgramme.model_validate(_reduit(scenarios))


def _a_et_b() -> dict[str, Any]:
    livres = _scenarios_livres()
    return {"sortie": livres["sortie"], "enlisement": livres["enlisement"]}


def test_configuration_livree_egale_aux_defauts() -> None:
    config = charger_yaml(PROGRAMME_LIVRE, ConfigProgramme)
    assert config.scenarios is not None
    assert scenarios_de_config(config.scenarios) == SCENARIOS_PAR_DEFAUT


def test_journal_livre_identique_avec_et_sans_cle() -> None:
    config = charger_yaml(PROGRAMME_LIVRE, ConfigProgramme)
    avec = generer(config, GRAINE, DATE_GENERATION)
    sans = generer(config.model_copy(update={"scenarios": None}), GRAINE, DATE_GENERATION)
    assert avec.scenarios == sans.scenarios == SCENARIOS_PAR_DEFAUT
    assert avec.evenements == sans.evenements


def test_journal_identique_avec_et_sans_cle() -> None:
    avec = generer(_config_reduite(_a_et_b()), GRAINE, DATE_GENERATION)
    sans = generer(_config_reduite(None), GRAINE, DATE_GENERATION)
    assert avec.scenarios == sans.scenarios
    assert avec.scenarios.resume() == "A (ENT-A), B (ENT-B)"
    assert avec.evenements == sans.evenements


def test_scenario_desactive() -> None:
    config = _config_reduite({"sortie": _scenarios_livres()["sortie"]})
    generation = generer(config, GRAINE, DATE_GENERATION)
    assert generation.scenarios == Scenarios(sortie=ScenarioSortie())
    assert generation.scenarios.resume() == "A (ENT-A)"


def test_cle_vide_desactive_tout() -> None:
    """`scenarios: {}` désactive les trois Scénarios (clé absente ou `null` : défauts)."""
    generation = generer(_config_reduite({}), GRAINE, DATE_GENERATION)
    assert generation.scenarios == AUCUN_SCENARIO
    assert generation.scenarios.resume() == "aucun"


def test_correspondance_de_chaque_champ() -> None:
    """Chaque champ configuré arrive dans le champ homonyme de la dataclass (valeurs
    distinctes, hors défauts : un mot-clé oublié ou permuté se verrait)."""
    config = ConfigScenarios.model_validate(
        {
            "sortie": {
                "entite": "ENT-D",
                "semaine_vague": 5,
                "bloquantes_bascule": 7,
                "poids_vague": 2.5,
                "part_bloquantes_vague": 0.35,
                "poids_decrue": 0.5,
                "statut_certification": "reservee",
                "semaine_certification": 2,
            },
            "enlisement": {
                "entite": "ENT-E",
                "semaine_debut": 3,
                "bloquantes_bascule": 4,
                "poids": 2.0,
                "part_bloquantes": 0.1,
                "part_majeures": 0.45,
                "statut_certification": "accordee",
                "semaine_certification": 6,
            },
            "menace": {
                "entite": "ENT-F",
                "cas_de_test_par_semaine": 25,
                "taux_ko_initial": 0.02,
                "semaine_hausse": 5,
                "taux_ko_hausse": [0.08, 0.12],
                "semaine_certification": 7,
            },
        }
    )
    assert scenarios_de_config(config) == Scenarios(
        sortie=ScenarioSortie(
            entite="ENT-D",
            semaine_vague=5,
            bloquantes_bascule=7,
            poids_vague=2.5,
            part_bloquantes_vague=0.35,
            poids_decrue=0.5,
            statut_certification=StatutCertification.reservee,
            semaine_certification=2,
        ),
        enlisement=ScenarioEnlisement(
            entite="ENT-E",
            semaine_debut=3,
            bloquantes_bascule=4,
            poids=2.0,
            part_bloquantes=0.1,
            part_majeures=0.45,
            statut_certification=StatutCertification.accordee,
            semaine_certification=6,
        ),
        menace=ScenarioMenace(
            entite="ENT-F",
            cas_de_test_par_semaine=25,
            taux_ko_initial=0.02,
            semaine_hausse=5,
            taux_ko_hausse=(0.08, 0.12),
            semaine_certification=7,
        ),
    )


def test_parametres_configures_appliques() -> None:
    scenarios = _a_et_b()
    scenarios["enlisement"]["semaine_debut"] = 3
    generation = generer(_config_reduite(scenarios), GRAINE, DATE_GENERATION)
    assert generation.scenarios.enlisement == ScenarioEnlisement(semaine_debut=3)
    defaut = generer(_config_reduite(None), GRAINE, DATE_GENERATION)
    assert generation.evenements != defaut.evenements


def test_semaine_hors_historique_ignoree() -> None:
    """Comme un Scénario par défaut, un Scénario configuré qui ne tient pas dans
    l'historique est ignoré."""
    scenarios = _a_et_b()
    scenarios["sortie"]["semaine_vague"] = 9
    generation = generer(_config_reduite(scenarios), GRAINE, DATE_GENERATION)
    assert generation.scenarios == Scenarios(enlisement=ScenarioEnlisement())


def test_scenarios_explicites_prioritaires() -> None:
    config = _config_reduite(_a_et_b())
    generation = generer(config, GRAINE, DATE_GENERATION, scenarios=AUCUN_SCENARIO)
    assert generation.scenarios == AUCUN_SCENARIO


def _invoquer(config: Path, sortie: Path, *options: str) -> str:
    resultat = CliRunner().invoke(
        app,
        [
            "donnees",
            "generer",
            "--config",
            str(config),
            "--config-jira",
            str(CONFIG_JIRA),
            "--sortie",
            str(sortie),
            "--corpus",
            str(CORPUS),
            "--graine",
            str(GRAINE),
            "--date-generation",
            DATE_GENERATION.isoformat(),
            *options,
        ],
    )
    assert resultat.exit_code == 0, resultat.output
    return resultat.output


def test_cli_lit_la_cle_et_sans_scenarios_l_ignore(tmp_path: Path) -> None:
    config = tmp_path / "programme.yaml"
    donnees = _reduit({"sortie": _scenarios_livres()["sortie"]})
    config.write_text(yaml.safe_dump(donnees, allow_unicode=True), encoding="utf-8")

    assert "Scénarios appliqués : A (ENT-A)\n" in _invoquer(config, tmp_path / "avec")

    sortie = _invoquer(config, tmp_path / "sans", "--sans-scenarios")
    assert "Scénarios appliqués : aucun" in sortie
    attendu = generer(
        charger_yaml(config, ConfigProgramme),
        GRAINE,
        DATE_GENERATION,
        cle_projet=charger_yaml(CONFIG_JIRA, ConfigJira).cle_projet,
        corpus=charger_corpus(CORPUS),
        scenarios=AUCUN_SCENARIO,
    )
    assert (tmp_path / "sans" / "journal.jsonl").read_bytes() == serialiser_journal(attendu)
