"""Exécution d'un Passage : étapes dans l'ordre d'AD-8, publication atomique ou échec propre.

Séquence : `passage_id` → `.en-cours-<id>/` → pour chaque étape, progression `en_cours`,
exécution, écriture des sorties et traces, progression finale → manifeste → renommage. En cas
d'exception : progression `echouee`, déplacement sous `echecs/`, `UsineErreur` nommant l'étape.
L'horloge et l'aléa sont injectés.
"""

import logging
from collections.abc import Callable, Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from usine.chaine.ecrivain import EcrivainPassage
from usine.contrats.config import ConfigUsine
from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import (
    ContextePassage,
    DonneesPassage,
    Etape,
    ExecutionEtape,
    ManifestePassage,
    ResultatEtape,
    StatutEtape,
    former_passage_id,
)
from usine.ports.consultation import Consultation
from usine.ports.etape import Etape as PortEtape

journal = logging.getLogger(__name__)


def _message(exc: BaseException) -> str:
    """Message d'origine d'une `UsineErreur`, type et message de toute autre exception."""
    if isinstance(exc, UsineErreur):
        return str(exc)
    return f"{type(exc).__name__} : {exc}"


def executer_passage(
    registre: Mapping[Etape, PortEtape],
    configuration: ConfigUsine,
    date_arrete: date,
    ecrivain: EcrivainPassage,
    fabrique_consultation: Callable[[Path], Consultation],
    horloge: Callable[[], datetime],
    alea: Callable[[], str],
    donnees: DonneesPassage,
    horodatage_extraction: datetime | None = None,
    nb_alignements: Callable[[], int] | None = None,
) -> ManifestePassage:
    """Exécute toutes les étapes du registre et publie le Passage ; lève une `UsineErreur`.

    `horodatage_extraction` (instant d'extraction Jira ; `None` hors source composite, les
    données du Passage ne dépendant alors d'aucune extraction) est recopié au manifeste ;
    `nb_alignements`, lu après les étapes, y donne le nombre d'alignements persistés par ce
    Passage (0 sans lui).
    """
    manquantes = [etape.value for etape in Etape if etape not in registre]
    if manquantes:
        raise UsineErreur(f"étape(s) absente(s) du registre : {', '.join(manquantes)}")
    debut = horloge()
    passage_id = former_passage_id(debut, alea())
    ecrivain.commencer(passage_id, date_arrete)
    etape_courante: Etape | None = None
    try:
        consultation = fabrique_consultation(ecrivain.repertoire)
        ctx = ContextePassage(date_arrete, passage_id, configuration, consultation)
        executions: list[ExecutionEtape] = []
        for etape in Etape:
            etape_courante = etape
            debut_etape = horloge()
            ecrivain.progression(etape, StatutEtape.en_cours)
            resultat = registre[etape].executer(ctx)
            if not isinstance(resultat, ResultatEtape):
                raise UsineErreur(f"ResultatEtape attendu, pas {type(resultat).__name__}")
            ecrivain.ecrire(resultat.sorties)
            ecrivain.ajouter_traces(resultat.traces)
            executions.append(
                ExecutionEtape(
                    etape=etape,
                    statut=resultat.statut,
                    horodatage_debut=debut_etape,
                    horodatage_fin=horloge(),
                )
            )
            ecrivain.progression(etape, resultat.statut)
        etape_courante = None
        nb_tickets = (
            ctx.consultation.tickets_etats(date_arrete).height
            if "tickets_etats" in ecrivain.ecrits
            else 0
        )
        manifeste = ManifestePassage(
            passage_id=passage_id,
            date_arrete=date_arrete,
            palier=ctx.palier,
            source=donnees.source,
            horodatage_debut=debut,
            horodatage_fin=horloge(),
            horodatage_extraction=horodatage_extraction,
            version_grille=donnees.version_grille,
            version_donnees=donnees.version_donnees,
            cout_llm_eur=Decimal(0),
            nb_alignements=0 if nb_alignements is None else nb_alignements(),
            nb_tickets=nb_tickets,
            etapes=tuple(executions),
        )
        ecrivain.publier(manifeste)
    except BaseException as exc:
        quoi = (
            f"étape « {etape_courante.value} »"
            if etape_courante is not None
            else "publication du Passage"
        )
        message = _message(exc)
        if etape_courante is not None:
            try:
                ecrivain.progression(etape_courante, StatutEtape.echouee, message)
            except Exception:
                journal.exception("progression « echouee » impossible à écrire")
        try:
            ecrivain.abandonner()
        except Exception:
            journal.exception("Passage %s impossible à déplacer sous echecs/", passage_id)
        if not isinstance(exc, Exception):
            raise  # KeyboardInterrupt, SystemExit : interruption propagée telle quelle.
        raise UsineErreur(f"Passage {passage_id} en échec, {quoi} : {message}") from exc
    return manifeste
