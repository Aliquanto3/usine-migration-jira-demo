"""Fixture paramétrée par adaptateur de `SourceTickets`."""

from collections.abc import Callable

import pytest

from tests.contrat.source_tickets.fabriques import FABRIQUES, CasSourceTickets


@pytest.fixture(params=[f for _, f in FABRIQUES], ids=[i for i, _ in FABRIQUES])
def cas(request: pytest.FixtureRequest) -> CasSourceTickets:
    """Un cas neuf par test et par adaptateur."""
    fabrique: Callable[[], CasSourceTickets] = request.param
    return fabrique()
