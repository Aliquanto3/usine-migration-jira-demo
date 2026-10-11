"""Fixture paramétrée par adaptateur de `Consultation` (liste vide : tests ignorés)."""

from collections.abc import Callable

import pytest

from tests.contrat.consultation.fabriques import FABRIQUES, CasConsultation


@pytest.fixture(params=[f for _, f in FABRIQUES], ids=[i for i, _ in FABRIQUES])
def cas(request: pytest.FixtureRequest) -> CasConsultation:
    """Un cas neuf par test et par adaptateur."""
    fabrique: Callable[[], CasConsultation] = request.param
    return fabrique()
