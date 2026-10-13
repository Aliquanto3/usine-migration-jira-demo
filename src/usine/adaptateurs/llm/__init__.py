"""Adaptateurs `FournisseurLLM` (Anthropic, Mistral, local) et registre des quotas et des prix.

Seul paquet autorisé à importer `pydantic_ai`, `anthropic`, `mistralai`, `openai` (AD-12).
"""

import os

# Pydantic AI affiche une bannière d'accueil à la première exécution ; jamais dans l'usine.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from usine.adaptateurs.llm.fournisseur import (
    FOURNISSEURS,
    URL_LOCALE_DEFAUT,
    VARIABLES_CLE,
    FournisseurPydanticAI,
    construire_fournisseur_llm,
)
from usine.adaptateurs.llm.registre import (
    REGISTRE,
    TarifModele,
    cout_estime_eur,
    tarif,
)

__all__ = [
    "FOURNISSEURS",
    "REGISTRE",
    "URL_LOCALE_DEFAUT",
    "VARIABLES_CLE",
    "FournisseurPydanticAI",
    "TarifModele",
    "construire_fournisseur_llm",
    "cout_estime_eur",
    "tarif",
]
