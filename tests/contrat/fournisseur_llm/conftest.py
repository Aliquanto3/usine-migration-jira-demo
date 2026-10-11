"""Fixture paramétrée par adaptateur de `FournisseurLLM`."""

from collections.abc import Callable

import pytest

from tests.contrat.fournisseur_llm.fabriques import FABRIQUES, CasFournisseurLLM


@pytest.fixture(params=[f for _, f in FABRIQUES], ids=[i for i, _ in FABRIQUES])
def cas(request: pytest.FixtureRequest) -> CasFournisseurLLM:
    """Un cas neuf par test et par adaptateur."""
    fabrique: Callable[[], CasFournisseurLLM] = request.param
    return fabrique()
