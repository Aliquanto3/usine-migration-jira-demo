"""Version des contrats et empreintes de traçabilité, définies une seule fois (AD-2, AD-16)."""

import hashlib
import re
from datetime import UTC, datetime

from usine.contrats.erreurs import UsineErreur

CONTRATS_VERSION = "0.1.0"
"""Version des contrats ; toute PR de `contrats/` ou `ports/` l'incrémente (AD-2)."""

CLE_VERSION = "contrats_version"
"""Clé portée par chaque fichier d'un Passage (enveloppe JSON, métadonnée Parquet)."""

_MOTIF_VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


def version_majeure(version: str) -> int:
    """Renvoie la version majeure de `version` (`MAJEURE.MINEURE.CORRECTIF`)."""
    correspondance = _MOTIF_VERSION.fullmatch(version) if isinstance(version, str) else None
    if correspondance is None:
        raise UsineErreur(f"version de contrats illisible : {version!r} (attendu : X.Y.Z)")
    return int(correspondance.group(1))


def verifier_version(version: str) -> None:
    """Refuse une version de contrats dont la majeure diffère de `CONTRATS_VERSION`."""
    if version_majeure(version) != version_majeure(CONTRATS_VERSION):
        raise UsineErreur(
            f"version de contrats {version} incompatible avec la version courante"
            f" {CONTRATS_VERSION} (version majeure différente)"
        )


def _sha256(octets: bytes) -> str:
    if not isinstance(octets, bytes):
        raise UsineErreur(f"octets attendus pour une empreinte, pas {type(octets).__name__}")
    return hashlib.sha256(octets).hexdigest()


def version_grille(octets: bytes) -> str:
    """Version de la Grille : 12 premiers caractères hexadécimaux du SHA-256 du YAML."""
    return _sha256(octets)[:12]


def version_prompt(octets: bytes) -> str:
    """Version d'un prompt : SHA-256 (64 hex) du fichier `ia/prompts/<tache>.md`."""
    return _sha256(octets)


def version_modele(fournisseur: str, modele: str) -> str:
    """Version de modèle : `fournisseur:modele`."""
    if not fournisseur or not modele or ":" in fournisseur:
        raise UsineErreur(
            f"fournisseur ou modèle invalide pour une version de modèle :"
            f" {fournisseur!r}, {modele!r}"
        )
    return f"{fournisseur}:{modele}"


def version_donnees(journal: bytes, horodatage_extraction: datetime | None) -> str:
    """Version de données : SHA-256 du Journal, suivi de `\\n` et de l'horodatage d'extraction.

    L'horodatage est écrit en ISO 8601 ramené en UTC ; sans extraction (`None`), seul le
    Journal entre dans l'empreinte.
    """
    if horodatage_extraction is None:
        return _sha256(journal)
    if horodatage_extraction.tzinfo is None or horodatage_extraction.utcoffset() is None:
        raise UsineErreur(f"horodatage d'extraction sans fuseau : {horodatage_extraction!r}")
    if not isinstance(journal, bytes):
        raise UsineErreur(f"octets attendus pour le Journal, pas {type(journal).__name__}")
    suffixe = horodatage_extraction.astimezone(UTC).isoformat().encode("ascii")
    return _sha256(journal + b"\n" + suffixe)
