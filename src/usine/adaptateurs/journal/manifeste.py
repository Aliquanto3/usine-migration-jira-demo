"""Lecture du manifeste d'injection (`donnees/injection/manifeste_injection.json`, AD-4).

Le manifeste est écrit par l'injecteur (L1) ; cette lane ne fait que le lire, pour appliquer
`correspondance_cles` (clé générée → clé Jira) à la lecture du Journal. Toute anomalie de
lecture devient une `UsineErreur` qui nomme le fichier.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import ManifesteInjection
from usine.contrats.passage import REPERTOIRE_DONNEES

CHEMIN_MANIFESTE_INJECTION = REPERTOIRE_DONNEES / "injection" / "manifeste_injection.json"
"""Manifeste d'injection, relatif à la racine du dépôt (AD-4)."""


def _motifs(exc: ValidationError) -> str:
    """Résumé des erreurs Pydantic : `champ : message`, séparés par « ; »."""
    return " ; ".join(
        f"{'.'.join(str(partie) for partie in err['loc']) or '(manifeste)'} : {err['msg']}"
        for err in exc.errors()
    )


def charger_manifeste(chemin: Path) -> ManifesteInjection:
    """Lit et valide le manifeste d'injection `chemin`."""
    try:
        texte = chemin.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise UsineErreur(f"{chemin} : manifeste d'injection introuvable") from exc
    except UnicodeDecodeError as exc:
        raise UsineErreur(
            f"{chemin} : manifeste d'injection non encodé en UTF-8 (octet {exc.start})"
        ) from exc
    except OSError as exc:
        raise UsineErreur(
            f"{chemin} : manifeste d'injection illisible ({exc.strerror or exc})"
        ) from exc
    try:
        donnees = json.loads(texte)
    except json.JSONDecodeError as exc:
        raise UsineErreur(
            f"{chemin} : manifeste d'injection, JSON illisible ({exc.msg}, ligne {exc.lineno})"
        ) from exc
    if not isinstance(donnees, dict):
        raise UsineErreur(
            f"{chemin} : manifeste d'injection, objet JSON attendu ({type(donnees).__name__} reçu)"
        )
    try:
        return ManifesteInjection.model_validate(donnees)
    except ValidationError as exc:
        raise UsineErreur(f"{chemin} : manifeste d'injection invalide ({_motifs(exc)})") from exc
