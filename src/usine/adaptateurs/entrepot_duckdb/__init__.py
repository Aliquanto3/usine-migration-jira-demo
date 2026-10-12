"""Entrepôt d'extraction DuckDB et extraction incrémentale (AD-6, AD-9, FR-6).

- `entrepot` : `EntrepotDuckDB` (port `EntrepotExtraction`, `donnees/entrepot.duckdb`), qui
  stocke événements et repère dans une seule transaction, dédoublonnés par `id_evenement` ;
- `extraction` : `extraire` et `EtapeExtraction` (port `Etape`), qui demandent à la source les
  événements depuis `repère − marge`. Seule `EtapeExtraction` (et la composition) ouvre
  l'entrepôt ; `duckdb` n'est importé que dans ce paquet.
"""

from usine.adaptateurs.entrepot_duckdb.entrepot import CHEMIN_ENTREPOT, EntrepotDuckDB
from usine.adaptateurs.entrepot_duckdb.extraction import (
    EtapeExtraction,
    ResultatExtraction,
    extraire,
)

__all__ = [
    "CHEMIN_ENTREPOT",
    "EntrepotDuckDB",
    "EtapeExtraction",
    "ResultatExtraction",
    "extraire",
]
