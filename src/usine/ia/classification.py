"""Tâche `classification` : Cause racine proposée pour chaque Anomalie (FR-35).

Un appel par Anomalie des `TicketTexte`, par la passerelle (ordre AD-12) ; les Cas de test et
les Certifications sont ignorés. Le prompt `prompts/classification.md` reçoit la clé, le titre
et la description de l'Anomalie, placés entre délimiteurs (données, pas instructions) ; il ne
porte pas la Date d'arrêté, que la clé de cache d'une classification ignore aussi.

Incrémentalité par le cache : une Anomalie inchangée est servie sans appel, une Anomalie
nouvelle ou dont le texte a changé part au fournisseur. Le contrôle déterministe retire de la
justification toute phrase citant une autre clé de ticket (`corrige`) ; sinon `conforme`.
Plafond de coût du Passage atteint (`PlafondCoutAtteint`) : l'Anomalie reste sans suggestion
(absente de la sortie), sans faire échouer le Passage. Un échec isolé du fournisseur (réponse
inexploitable, `UnexpectedModelBehavior` par exemple, déjà converti en `UsineErreur` par
l'adaptateur) laisse de même l'Anomalie sans suggestion, consignée au journal ; seuls
`MAX_ECHECS_CONSECUTIFS` échecs d'affilée (fournisseur injoignable) font échouer l'étape. La
Cause racine proposée n'est qu'une suggestion : elle n'est jamais écrite dans Jira.
"""

import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import resources
from typing import Any

import polars as pl

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    ParametresAppel,
    ReponseClassification,
    SortieClassification,
    StatutControle,
    Tache,
)
from usine.contrats.passage import ContextePassage, ResultatEtape, StatutEtape
from usine.contrats.tickets import TypeTicket, rang_cle
from usine.contrats.trace import EntreeTrace
from usine.contrats.versions import version_prompt
from usine.ia.controles import decouper_phrases, retirer_citations_hors
from usine.ia.passerelle import ContexteAppel, Controle, Passerelle, PlafondCoutAtteint
from usine.ports.consultation import Consultation

PART_PLAFOND_CLASSIFICATION = Decimal("0.5")
"""Part du plafond de coût du Passage que la classification peut dépenser (NFR-9) ; le reste
garde le budget des explications et de la narration, et le stock se complète aux Passages
suivants."""

MAX_ECHECS_CONSECUTIFS = 3
"""Échecs du fournisseur d'affilée au-delà desquels la classification échoue (panne franche,
fournisseur injoignable) ; en deçà, chaque Anomalie en échec reste sans suggestion."""

MAX_ECHECS_PASSAGE = 20
"""Échecs du fournisseur au total au-delà desquels la classification échoue, même non
consécutifs (une alternance échec/succès ne doit pas répéter des appels facturés sans fin)."""

MAX_JETONS_SORTIE = 512
"""Plafond de jetons de sortie d'une classification."""

DELIMITEUR = "```"
"""Délimiteur du bloc de données du ticket ; neutralisé dans le titre et la description."""

journal = logging.getLogger(__name__)

_VARIABLE = re.compile(r"\{\{(\w+)\}\}")


def lire_prompt() -> bytes:
    """Octets de `ia/prompts/classification.md` (source de `version_prompt`)."""
    return (resources.files("usine.ia") / "prompts" / "classification.md").read_bytes()


def rendre_prompt(gabarit: str, variables: Mapping[str, str]) -> str:
    """Remplace chaque `{{nom}}` ; une variable inconnue ou inutilisée lève une `UsineErreur`."""
    attendues = set(_VARIABLE.findall(gabarit))
    manquantes = sorted(attendues - set(variables))
    en_trop = sorted(set(variables) - attendues)
    if manquantes or en_trop:
        raise UsineErreur(
            f"prompt « classification » : variables manquantes {manquantes}, en trop {en_trop}"
        )
    return _VARIABLE.sub(lambda m: variables[m.group(1)], gabarit)


@dataclass(frozen=True)
class ContexteClassification:
    """Contexte du Passage commun aux classifications."""

    passage_id: str
    version_donnees: str
    version_grille: str
    """Tracée seulement (AD-16) : la Grille n'entre ni dans le prompt ni dans le cache."""
    gabarit: bytes
    """Octets du gabarit envoyé (source de `version_prompt`)."""

    @property
    def version_prompt(self) -> str:
        """`version_prompt` du gabarit envoyé."""
        return version_prompt(self.gabarit)

    @property
    def texte_gabarit(self) -> str:
        """Gabarit décodé en UTF-8."""
        return self.gabarit.decode("utf-8")


def _donnee(texte: str) -> str:
    """Texte de ticket sans délimiteur : il ne peut pas fermer le bloc de données."""
    return texte.replace(DELIMITEUR, "'''")


def _ticket(cle: str, titre: str | None, description: str | None) -> str:
    return (
        f"{cle} : {_donnee(titre or '(sans titre)')}\n"
        f"{_donnee(description or '(sans description)')}"
    )


@dataclass(frozen=True)
class _Controleur:
    """Contrôle d'une `ReponseClassification` : justification sans clé d'un autre ticket."""

    cle_ticket: str

    def __call__(self, reponse: ReponseClassification) -> Controle[SortieClassification]:
        justification = retirer_citations_hors(reponse.justification, (self.cle_ticket,))
        retirees = len(decouper_phrases(reponse.justification)) - len(
            decouper_phrases(justification)
        )
        if retirees:
            statut = StatutControle.corrige
        else:
            statut = StatutControle.conforme
            justification = reponse.justification
        sortie = SortieClassification(
            cle_ticket=self.cle_ticket,
            cause_racine=reponse.cause_racine,
            justification=justification,
            statut_controle=statut,
        )
        return Controle(sortie, statut, retirees)


def anomalies(textes: pl.DataFrame) -> list[dict[str, Any]]:
    """Lignes des Anomalies de `textes`, triées par `rang_cle` ; Cas de test et Certifications
    écartés."""
    lignes = textes.filter(pl.col("type_ticket") == TypeTicket.anomalie.value)
    return sorted(lignes.iter_rows(named=True), key=lambda ligne: rang_cle(ligne["cle_ticket"]))


def classer(
    passerelle: Passerelle,
    textes: pl.DataFrame,
    date_arrete: date,
    contexte: ContexteClassification,
    plafond_eur: Decimal | None = None,
    *,
    tolerer_echecs: bool = True,
    arreter: Callable[[], bool] | None = None,
) -> tuple[tuple[SortieClassification, ...], tuple[EntreeTrace, ...]]:
    """Cause racine proposée de chaque Anomalie de `textes` et trace de chaque appel.

    Une Anomalie refusée par le plafond de coût du Passage, ou par la part `plafond_eur` qui
    revient à la classification, est absente de la sortie, comme une Anomalie dont l'appel
    échoue (`UsineErreur`, consignée au journal). `MAX_ECHECS_CONSECUTIFS` échecs d'affilée,
    ou `MAX_ECHECS_PASSAGE` au total, lèvent une `UsineErreur` qui nomme la tâche et le
    dernier échec ; le coût majoré de chaque échec est imputé au plafond par la passerelle.
    `tolerer_echecs=False` (suite d'évaluation) : le premier échec est propagé tel quel.
    `arreter`, consulté avant chaque Anomalie, interrompt la boucle (préchauffage du cache
    borné dans le temps) : les Anomalies restantes sont absentes de la sortie.
    """
    sorties: list[SortieClassification] = []
    traces: list[EntreeTrace] = []
    echecs: list[str] = []
    consecutifs = 0
    parametres = ParametresAppel(tache=Tache.classification, max_jetons_sortie=MAX_JETONS_SORTIE)
    lignes = anomalies(textes)
    for rang, ligne in enumerate(lignes):
        if arreter is not None and arreter():
            journal.info(
                "classification interrompue : %d Anomalie(s) restante(s)", len(lignes) - rang
            )
            break
        cle = ligne["cle_ticket"]
        prompt = rendre_prompt(
            contexte.texte_gabarit,
            {"cle_ticket": cle, "ticket": _ticket(cle, ligne["titre"], ligne["description"])},
        )
        appel = ContexteAppel(
            passage_id=contexte.passage_id,
            date_arrete=date_arrete,
            cible=cle,
            version_prompt=contexte.version_prompt,
            version_grille=contexte.version_grille,
            version_donnees=contexte.version_donnees,
            entite=ligne["entite"],
        )
        try:
            resultat = passerelle.executer_structure(
                prompt,
                ReponseClassification,
                parametres,
                appel,
                _Controleur(cle),
                plafond_eur=plafond_eur,
            )
        except PlafondCoutAtteint:
            journal.warning("classification de %s non demandée : plafond de coût", cle)
            continue
        except UsineErreur as exc:
            if not tolerer_echecs:
                raise
            consecutifs += 1
            echecs.append(cle)
            if consecutifs >= MAX_ECHECS_CONSECUTIFS or len(echecs) >= MAX_ECHECS_PASSAGE:
                raise UsineErreur(
                    f"classification : {consecutifs} échecs consécutifs et {len(echecs)} au"
                    f" total du fournisseur LLM (dernier sur {cle} : {exc})"
                ) from exc
            journal.warning("classification de %s en échec, sans suggestion : %s", cle, exc)
            continue
        consecutifs = 0
        sorties.append(resultat.sortie)
        traces.append(resultat.trace)
    if echecs:
        journal.warning(
            "%d Anomalie(s) sans suggestion après un échec du fournisseur : %s",
            len(echecs),
            ", ".join(echecs),
        )
    return tuple(sorties), tuple(traces)


class EtapeClassification:
    """Propose une Cause racine pour chaque Anomalie ; n'écrit rien elle-même.

    `version_prompt` est calculée à partir des octets du gabarit qu'elle envoie (par défaut
    `ia/prompts/classification.md`).
    """

    def __init__(
        self,
        passerelle: Passerelle,
        version_donnees: str,
        version_grille: str,
        gabarit: bytes | None = None,
        plafond_eur: Decimal | None = None,
    ) -> None:
        """`plafond_eur` : part du plafond de coût du Passage réservée à la classification
        (`None` : aucune part propre)."""
        self._passerelle = passerelle
        self._version_donnees = version_donnees
        self._version_grille = version_grille
        self._gabarit = gabarit if gabarit is not None else lire_prompt()
        self._plafond_eur = plafond_eur

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sortie `classification` et une trace par appel, lues via `ctx.consultation`."""
        contexte = ContexteClassification(
            passage_id=ctx.passage_id,
            version_donnees=self._version_donnees,
            version_grille=self._version_grille,
            gabarit=self._gabarit,
        )
        sorties, traces = classer(
            self._passerelle,
            ctx.consultation.textes_tickets(),
            ctx.date_arrete,
            contexte,
            self._plafond_eur,
        )
        return ResultatEtape(StatutEtape.reussie, {"classification": sorties}, traces)

    def prechauffer(
        self,
        textes: pl.DataFrame,
        date_arrete: date,
        passage_id: str,
        arreter: Callable[[], bool],
    ) -> tuple[tuple[SortieClassification, ...], tuple[EntreeTrace, ...]]:
        """Classe les Anomalies de `textes` hors Passage, jusqu'à ce qu'`arreter` le demande.

        Même passerelle, même gabarit et même part de plafond qu'`executer` : les réponses
        remplissent le cache de production, servi ensuite aux Passages ("cache de
        classification initialisé", Story 6.10). `passage_id` porte le cumul de coût.
        """
        contexte = ContexteClassification(
            passage_id=passage_id,
            version_donnees=self._version_donnees,
            version_grille=self._version_grille,
            gabarit=self._gabarit,
        )
        return classer(
            self._passerelle, textes, date_arrete, contexte, self._plafond_eur, arreter=arreter
        )
