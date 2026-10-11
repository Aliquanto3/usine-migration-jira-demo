"""Lecture et validation des fichiers YAML de configuration."""

from collections.abc import Hashable, Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from usine.contrats.config import ConfigChaine
from usine.contrats.erreurs import UsineErreur

MODELES: dict[str, type[BaseModel]] = {
    "chaine": ConfigChaine,
}

# Clés spéciales traitées par `flatten_mapping` : fusion `<<` et valeur `=`.
_ETIQUETTES_SPECIALES = ("tag:yaml.org,2002:merge", "tag:yaml.org,2002:value")


class _CleDupliquee(yaml.YAMLError):
    """Clé présente deux fois dans un même mapping YAML."""

    def __init__(self, cle: object, ligne: int) -> None:
        super().__init__(f"clé {cle!r} dupliquée (ligne {ligne})")
        self.cle = cle
        self.ligne = ligne


class _ChargeurSansDoublon(yaml.SafeLoader):
    """`SafeLoader` qui refuse une clé dupliquée au lieu de garder la dernière valeur."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        vues: set[Hashable] = set()
        for noeud_cle, _ in node.value:
            if noeud_cle.tag in _ETIQUETTES_SPECIALES:
                continue
            cle = self.construct_object(noeud_cle, deep=deep)
            if not isinstance(cle, Hashable):
                continue  # Refusée ensuite par PyYAML (clé non hachable).
            if cle in vues:
                raise _CleDupliquee(cle, noeud_cle.start_mark.line + 1)
            vues.add(cle)
        return super().construct_mapping(node, deep=deep)


def _chemin_cle(loc: Sequence[int | str]) -> str:
    """Rend un emplacement Pydantic sous la forme `a.b[2].c`."""
    chemin = ""
    for partie in loc:
        if isinstance(partie, int):
            chemin += f"[{partie}]"
        else:
            chemin += f".{partie}" if chemin else partie
    return chemin or "(racine)"


def _lire(chemin: Path) -> str:
    """Lit `chemin` en UTF-8 ; toute erreur de lecture devient une `UsineErreur`."""
    try:
        return chemin.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise UsineErreur(f"{chemin} : fichier de configuration introuvable") from exc
    except UnicodeDecodeError as exc:
        raise UsineErreur(
            f"{chemin} : fichier de configuration non encodé en UTF-8"
            f" (octet {exc.start} : {exc.object[exc.start : exc.start + 1]!r})"
        ) from exc
    except OSError as exc:
        raise UsineErreur(
            f"{chemin} : fichier de configuration illisible ({exc.strerror or exc})"
        ) from exc


def charger_yaml[M: BaseModel](chemin: Path, modele: type[M]) -> M:
    """Lit `chemin` et le valide par `modele`.

    Lève une `UsineErreur` qui nomme le fichier, la clé et la valeur fautive.
    """
    texte = _lire(chemin)
    try:
        donnees = yaml.load(texte, Loader=_ChargeurSansDoublon)
    except _CleDupliquee as exc:
        raise UsineErreur(f"{chemin} : clé « {exc.cle} » dupliquée (ligne {exc.ligne})") from exc
    except yaml.YAMLError as exc:
        raise UsineErreur(f"{chemin} : YAML illisible ({exc})") from exc
    try:
        return modele.model_validate({} if donnees is None else donnees)
    except ValidationError as exc:
        lignes = [
            f"{chemin} : clé « {_chemin_cle(err['loc'])} », valeur {err['input']!r} refusée"
            f" ({err['msg']})"
            for err in exc.errors()
        ]
        raise UsineErreur("\n".join(lignes)) from exc


def charger(nom: str, repertoire: Path) -> BaseModel:
    """Charge `repertoire/<nom>.yaml` avec le modèle enregistré pour `nom`."""
    if nom not in MODELES:
        attendus = ", ".join(MODELES)
        raise UsineErreur(f"configuration inconnue : {nom!r} (attendu : {attendus})")
    return charger_yaml(repertoire / f"{nom}.yaml", MODELES[nom])
