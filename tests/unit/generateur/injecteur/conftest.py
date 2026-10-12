"""Fixtures de l'injecteur : Journal réduit, configuration Jira et client sur le faux Jira."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from pydantic import SecretStr

from tests.unit.adaptateurs.jira_http.outils import Attentes, config_jira
from tests.unit.generateur.injecteur.faux_jira import FauxJira
from usine.adaptateurs.jira_http import construire_client_ecriture
from usine.config import charger_yaml
from usine.contrats.config import ConfigJira, ConfigProgramme
from usine.generateur.corpus import charger_corpus
from usine.generateur.injecteur.plan import PlanInjection, planifier
from usine.generateur.injecteur.site import ClientJira
from usine.generateur.journal import Generation, ecrire_journal, generer

RACINE = Path(__file__).resolve().parents[4]
PROGRAMME_REDUIT = RACINE / "tests" / "unit" / "generateur" / "programme_reduit.yaml"
CORPUS = RACINE / "donnees" / "corpus" / "textes.json"

type FabriqueClient = Callable[[FauxJira], ClientJira]


@pytest.fixture(scope="session")
def generation() -> Generation:
    """Journal réduit (Programme réduit, graine 42, généré le 2026-10-12)."""
    return generer(
        charger_yaml(PROGRAMME_REDUIT, ConfigProgramme),
        42,
        date(2026, 10, 12),
        corpus=charger_corpus(CORPUS),
    )


@pytest.fixture(scope="session")
def plan(generation: Generation) -> PlanInjection:
    """Plan d'injection du Journal réduit."""
    return planifier(generation.entete, generation.evenements)


@pytest.fixture
def chemin_journal(generation: Generation, tmp_path: Path) -> Path:
    """Journal réduit écrit sur disque."""
    return ecrire_journal(generation, tmp_path / "donnees")


@pytest.fixture
def config() -> ConfigJira:
    """`config/jira.yaml` du dépôt, URL fictive."""
    return config_jira("cloud")


@pytest.fixture
def attentes() -> Attentes:
    """Attentes enregistrées du transport (reprise sur 429)."""
    return Attentes()


@pytest.fixture
def fabrique_client(config: ConfigJira, attentes: Attentes) -> FabriqueClient:
    """Client d'écriture branché sur un faux Jira."""

    def fabriquer(faux: FauxJira) -> ClientJira:
        return construire_client_ecriture(
            config,
            email="injecteur@example.invalid",
            jeton_injection=SecretStr("jeton-injection"),
            attendre=attentes,
            transport_http=faux.transport,
        )

    return fabriquer
