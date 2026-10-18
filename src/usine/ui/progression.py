"""Suivi de la progression d'un Passage lancé depuis l'UI (fonctions pures).

Le fichier `sorties/progression/<passage_id>.jsonl` est lu en ouvrir-lire-fermer à chaque
sondage ; une dernière ligne incomplète (sans saut de ligne) attend le sondage suivant.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import MappingProxyType

from pydantic import ValidationError

from usine.contrats.erreurs import UsineErreur
from usine.contrats.format import formater_nombre
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

AUCUN_RAPPORT = (
    "Aucun rapport publié par ce lancement : la carte météo reste celle du dernier Passage publié."
)
"""Message de l'écran Lancement après un échec : aucun rapport partiel n'est affiché."""


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


_FINAUX = frozenset({StatutEtape.reussie, StatutEtape.sautee, StatutEtape.echouee})


@dataclass(frozen=True)
class SuiviEtape:
    """État affiché d'une étape et sa durée (seulement pour une étape terminée)."""

    etape: Etape
    etat: str
    duree: timedelta | None


def suivi_des_etapes(evenements: Iterable[EvenementProgression]) -> list[SuiviEtape]:
    """Pour chaque `Etape` dans l'ordre d'AD-8 : dernier statut et durée.

    La durée vaut l'horodatage du dernier événement final moins celui du dernier `en_cours` ;
    une étape en cours, en attente, sans `en_cours` ou aux horodatages incohérents n'en a pas.
    """
    etats: dict[Etape, str] = {}
    debuts: dict[Etape, datetime] = {}
    fins: dict[Etape, datetime] = {}
    for evenement in evenements:
        etats[evenement.etape] = evenement.statut.value
        if evenement.statut in _FINAUX:
            fins[evenement.etape] = evenement.horodatage
        else:
            debuts[evenement.etape] = evenement.horodatage
    suivis: list[SuiviEtape] = []
    for etape in Etape:
        etat = etats.get(etape, EN_ATTENTE)
        duree: timedelta | None = None
        if etat in _FINAUX and etape in debuts and etape in fins:
            ecart = fins[etape] - debuts[etape]
            duree = ecart if ecart >= timedelta(0) else None
        suivis.append(SuiviEtape(etape, etat, duree))
    return suivis


def etape_en_echec(evenements: Iterable[EvenementProgression]) -> Etape | None:
    """Dernière étape signalée `echouee` dans la progression, ou `None`."""
    fautive: Etape | None = None
    for evenement in evenements:
        if evenement.statut is StatutEtape.echouee:
            fautive = evenement.etape
    return fautive


def texte_duree(duree: timedelta) -> str:
    """Durée en secondes au format français : `0,3 s`."""
    return f"{formater_nombre(duree.total_seconds(), 1)} s"
