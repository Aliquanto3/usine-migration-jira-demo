"""Contrat de `CacheLLM` : lecture, écriture, remplacement, valeur `EnveloppeCache` (AD-12)."""

import json
from collections.abc import Callable

from tests.contrat.cache_llm.fabriques import CasCache
from usine.contrats.llm import EnveloppeCache
from usine.ports import CacheLLM

CLE = json.dumps(
    {"tache": "explication", "cible": "ENT-A", "tentative": 0}, sort_keys=True, ensure_ascii=False
)


def test_implemente_le_port(cas: CasCache) -> None:
    assert isinstance(cas.cache, CacheLLM)


def test_cle_inconnue(cas: CasCache) -> None:
    assert cas.cache.lire(CLE) is None
    assert cas.cache.lire("") is None


def test_ecriture_puis_lecture(cas: CasCache) -> None:
    valeur = EnveloppeCache(brut='{"texte": "DEMO-3 bloque."}', version_modele="factice:v1")
    cas.cache.ecrire(CLE, valeur.model_dump_json())
    relue = cas.cache.lire(CLE)
    assert relue is not None
    assert EnveloppeCache.model_validate_json(relue) == valeur


def test_ecriture_remplace(cas: CasCache) -> None:
    cas.cache.ecrire(CLE, "a")
    cas.cache.ecrire(CLE, "b")
    assert cas.cache.lire(CLE) == "b"


def test_cles_distinctes(cas: CasCache) -> None:
    cas.cache.ecrire(CLE, "a")
    cas.cache.ecrire(CLE + " ", "b")
    assert cas.cache.lire(CLE) == "a"
    assert cas.cache.lire(CLE + " ") == "b"


def test_texte_unicode_intact(cas: CasCache) -> None:
    valeur = "Écart « sévère » sur DEMO-7 : 1 234,5 € — ✓\n\x00fin"
    cas.cache.ecrire("clé é", valeur)
    assert cas.cache.lire("clé é") == valeur


def test_instances_independantes(fabrique: Callable[[], CasCache]) -> None:
    premier, second = fabrique(), fabrique()
    premier.cache.ecrire(CLE, "a")
    assert second.cache.lire(CLE) is None


def test_persistance(cas: CasCache) -> None:
    """Un adaptateur persistant relit ce qu'une autre instance a écrit sur le même stockage."""
    if cas.rouvrir is None:
        return
    cas.cache.ecrire(CLE, "a")
    assert cas.rouvrir().lire(CLE) == "a"
