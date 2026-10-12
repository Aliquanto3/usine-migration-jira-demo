"""Suivi de la progression d'un Passage lancé depuis l'UI, sans Streamlit (fonctions pures).

Le fichier `sorties/progression/<passage_id>.jsonl` est lu en ouvrir-lire-fermer à chaque
sondage ; une dernière ligne incomplète (sans saut de ligne) attend le sondage suivant.
"""

from collections.abc import Iterable, Mapping
from pathlib import Path
from types import MappingProxyType

from pydantic import ValidationError

from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import (
    REPERTOIRE_PROGRESSION,
    Etape,
    EvenementProgression,
    StatutEtape,
)

EN_ATTENTE = "en_attente"
"""État d'une étape sans événement de progression."""

LIBELLES_ETATS: Mapping[str, str] = MappingProxyType(
    {
        EN_ATTENTE: "En attente",
        StatutEtape.en_cours: "En cours",
        StatutEtape.reussie: "Réussie",
        StatutEtape.sautee: "Sautée",
        StatutEtape.echouee: "Échec",
    }
)
"""Libellé français de chaque état d'étape affiché."""


def fichiers_progression(racine: Path) -> frozenset[Path]:
    """Fichiers `*.jsonl` présents dans `racine/sorties/progression/` (vide sans répertoire)."""
    repertoire = racine / REPERTOIRE_PROGRESSION
    if not repertoire.is_dir():
        return frozenset()
    return frozenset(chemin for chemin in repertoire.glob("*.jsonl") if chemin.is_file())


def fichier_nouveau(avant: Iterable[Path], racine: Path) -> Path | None:
    """Premier fichier de progression apparu depuis `avant`, ou `None`.

    Le nom commence par l'horodatage UTC du Passage : le plus petit nom est le premier lancé.
    """
    nouveaux = fichiers_progression(racine) - frozenset(avant)
    return min(nouveaux, key=lambda chemin: chemin.name) if nouveaux else None


def lire_progression(chemin: Path) -> tuple[EvenementProgression, ...]:
    """Événements des lignes complètes de `chemin`, validés ; dernière ligne partielle ignorée."""
    try:
        octets = chemin.read_bytes()
    except FileNotFoundError:
        return ()
    except OSError as exc:
        raise UsineErreur(f"{chemin} : progression illisible ({exc.strerror or exc})") from exc
    lignes = octets.split(b"\n")[:-1]  # le dernier segment n'est pas terminé par un saut de ligne
    evenements: list[EvenementProgression] = []
    for numero, ligne in enumerate(lignes, start=1):
        if not ligne.strip():
            continue
        try:
            evenements.append(EvenementProgression.model_validate_json(ligne))
        except ValidationError as exc:
            raise UsineErreur(f"{chemin}, ligne {numero} : progression invalide ({exc})") from exc
    return tuple(evenements)


def etat_des_etapes(evenements: Iterable[EvenementProgression]) -> list[tuple[Etape, str]]:
    """Pour chaque `Etape` dans l'ordre d'AD-8, son dernier statut ou `en_attente`."""
    derniers: dict[Etape, str] = {}
    for evenement in evenements:
        derniers[evenement.etape] = evenement.statut.value
    return [(etape, derniers.get(etape, EN_ATTENTE)) for etape in Etape]
