"""Fixtures paramétrées par adaptateur de `Pseudonymiseur`."""

from collections.abc import Callable

import pytest

from tests.contrat.pseudonymiseur.fabriques import FABRIQUES, CasPseudonymiseur


@pytest.fixture(params=[f for _, f in FABRIQUES], ids=[i for i, _ in FABRIQUES])
def fabrique(request: pytest.FixtureRequest) -> Callable[[], CasPseudonymiseur]:
    """Fabrique de l'adaptateur, pour en obtenir plusieurs instances."""
    resultat: Callable[[], CasPseudonymiseur] = request.param
    return resultat


@pytest.fixture
def cas(fabrique: Callable[[], CasPseudonymiseur]) -> CasPseudonymiseur:
    """Un cas neuf par test et par adaptateur."""
    return fabrique()
