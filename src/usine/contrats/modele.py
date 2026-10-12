"""Base commune des enregistrements unitaires : modèles Pydantic gelés (AD-2)."""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Annotated, Any, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, WrapSerializer

from usine.contrats.erreurs import UsineErreur
from usine.contrats.versions import verifier_version

MOTIF_PASSAGE_ID_TEXTE = r"\d{8}T\d{6}Z-[0-9a-f]{6}"
"""Forme d'un `passage_id` : `AAAAMMJJTHHMMSSZ-<6 hex>` (AD-7)."""

PassageId = Annotated[str, Field(pattern=f"^{MOTIF_PASSAGE_ID_TEXTE}$")]
"""Identifiant de Passage validé."""


def _version_compatible(version: str) -> str:
    try:
        verifier_version(version)
    except UsineErreur as exc:
        raise ValueError(str(exc)) from exc
    return version


VersionContrats = Annotated[str, AfterValidator(_version_compatible)]
"""`contrats_version` d'un fichier ; une version majeure différente est refusée (AD-2)."""


_K = TypeVar("_K")
_V = TypeVar("_V")


def _figer(valeur: Mapping[Any, Any]) -> Mapping[Any, Any]:
    return MappingProxyType(dict(valeur))


def _en_dict(valeur: Mapping[Any, Any], suite: Callable[[Any], Any]) -> Any:
    return suite(dict(valeur))


MappingFige = Annotated[Mapping[_K, _V], AfterValidator(_figer), WrapSerializer(_en_dict)]
"""`Mapping` figé en `MappingProxyType` après validation, pour un modèle gelé (AD-2).

La forme JSON ou YAML est celle d'un objet, inchangée ; toute affectation d'élément lève
`TypeError`. S'emploie comme `MappingFige[str, JsonValue]`.
"""


class Enregistrement(BaseModel):
    """Enregistrement gelé : toute affectation et tout champ inconnu sont refusés."""

    model_config = ConfigDict(frozen=True, extra="forbid")
