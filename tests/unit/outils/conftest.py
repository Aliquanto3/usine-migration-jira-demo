"""Marqueur `lent` pour les tests des outils : mêmes règles que les tests du générateur."""

from tests.unit.generateur.conftest import pytest_configure, pytest_runtest_setup

__all__ = ["pytest_configure", "pytest_runtest_setup"]
