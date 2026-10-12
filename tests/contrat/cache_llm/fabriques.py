"""Fabriques des adaptateurs de `CacheLLM` soumis à la suite de contrat.

Chaque appel d'une fabrique rend un cache vide, sans stockage partagé avec les autres
(répertoire temporaire neuf pour l'adaptateur SQLite). `rouvrir` rend un second accès au même
stockage quand l'adaptateur est persistant, sinon `None`.
"""

import atexit
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tests.doublures import CacheMemoire
from usine.adaptateurs.stockage_sqlite import CacheLLMSqlite
from usine.ports import CacheLLM


@dataclass(frozen=True)
class CasCache:
    """Adaptateur à éprouver et, s'il est persistant, un moyen de rouvrir son stockage."""

    cache: CacheLLM
    rouvrir: Callable[[], CacheLLM] | None = None


def fabrique_memoire() -> CasCache:
    """Doublure en mémoire."""
    return CasCache(CacheMemoire())


def fabrique_sqlite() -> CasCache:
    """`CacheLLMSqlite` dans un répertoire temporaire neuf, supprimé en fin de session."""
    repertoire = Path(tempfile.mkdtemp(prefix="cache-llm-"))
    atexit.register(shutil.rmtree, repertoire, True)
    chemin = repertoire / "donnees" / "cache_llm.sqlite"
    return CasCache(CacheLLMSqlite(chemin), lambda: CacheLLMSqlite(chemin))


FABRIQUES: list[tuple[str, Callable[[], CasCache]]] = [
    ("memoire", fabrique_memoire),
    ("sqlite", fabrique_sqlite),
]
