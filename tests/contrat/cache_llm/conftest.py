"""Fixtures paramétrées par adaptateur de `CacheLLM`."""

from collections.abc import Callable

import pytest

from tests.contrat.cache_llm.fabriques import FABRIQUES, CasCache


@pytest.fixture(params=[f for _, f in FABRIQUES], ids=[i for i, _ in FABRIQUES])
def fabrique(request: pytest.FixtureRequest) -> Callable[[], CasCache]:
    """Fabrique de l'adaptateur, pour en obtenir plusieurs instances."""
    resultat: Callable[[], CasCache] = request.param
    return resultat


@pytest.fixture
def cas(fabrique: Callable[[], CasCache]) -> CasCache:
    """Un cache neuf par test et par adaptateur."""
    return fabrique()
