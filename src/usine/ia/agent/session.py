"""Session de l'Agent : une question, des outils, des chiffres contrôlés (FR-39, FR-40).

Chaque question est indépendante, sans historique : la session envoie les consignes
(`ia/prompts/agent.md`) et la question à `Passerelle.executer_agent`, avec les cinq outils de
consultation en lecture seule sérialisés en JSON. `get_tendance` est borné à la sérialisation
(`LIMITE_POINTS_TENDANCE` points les plus récents, plus `points_omis`).

Contrôle (AD-12, AD-14) : les valeurs autorisées sont celles des messages `outil` de la
conversation (nombres JSON, `float` lu via `Decimal(repr)`, nombres écrits dans les chaînes et
dates ISO) ; un nombre du texte absent de ces valeurs (`controler_nombres`) ou un ticket cité
absent des clés retournées rejette la réponse, remplacée par `MESSAGE_REJET`. Un ticket cité est
une clé `MOTIF_CLE_TICKET` dont le projet n'est ni `IND`, ni `ENT`, ni `J`. Les refus de la
dernière réponse restent lisibles dans `SessionAgent.derniers_refus` (suite d'évaluation).

Traces : une ligne `EntreeTrace` par outil exécuté et par réponse, ajoutée dès sa production à
`sorties/agent/<AAAA-MM-JJ>/<session>.jsonl` ; aucun répertoire de Passage n'est écrit.
"""

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from importlib import resources
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from usine.contrats.agent import ResultatGetTendance
from usine.contrats.llm import (
    CANDIDAT_JETON,
    MessageAgent,
    ParametresAppel,
    ReponseAgent,
    ReponseAgentBrute,
    StatutControle,
    Tache,
)
from usine.contrats.modele import Enregistrement
from usine.contrats.tickets import MOTIF_CLE_TICKET
from usine.contrats.trace import EntreeTrace
from usine.contrats.versions import version_prompt
from usine.ia.agent.outils import DefinitionOutil, outils_consultation
from usine.ia.controles import ValeurAutorisee, controler_nombres, projet
from usine.ia.passerelle import ContexteAppel, Controle, OutilSource, Passerelle, ResultatAgent
from usine.ports.consultation import Consultation

LIMITE_POINTS_TENDANCE = 60
"""Points de Tendance envoyés au fournisseur au plus : les plus récents."""

MAX_JETONS_SORTIE = 1024
"""Plafond de jetons de sortie d'une réponse de l'Agent."""

REPERTOIRE_AGENT = Path("sorties/agent")
"""Traces des sessions de l'Agent, hors des Passages (relatif à la racine)."""

PROJETS_IGNORES = frozenset({"IND", "ENT", "J"})
"""Projets d'une clé qui ne sont pas des tickets : indicateurs, Entités, jalons."""

SANS_REPONSE = "Les données ne permettent pas de répondre."
"""Réponse attendue quand les outils ne permettent pas de répondre."""

MESSAGE_REJET = (
    "Réponse rejetée par le contrôle : {motifs}. Seuls les chiffres et les tickets retournés"
    " par les outils peuvent être cités."
)
"""Texte d'une réponse rejetée ; `{motifs}` nomme les chiffres et tickets refusés."""

_CLE_TICKET = re.compile(rf"\b{MOTIF_CLE_TICKET}\b")
_NOMBRE = re.compile(r"\d+(?:[.,]\d+)?")
_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def lire_prompt() -> bytes:
    """Octets de `ia/prompts/agent.md` (source de `version_prompt`)."""
    return (resources.files("usine.ia") / "prompts" / "agent.md").read_bytes()


def serialiser_resultat(resultat: Enregistrement) -> str:
    """Résultat d'outil en JSON ; une Tendance trop longue garde ses points les plus récents."""
    donnees: dict[str, Any] = resultat.model_dump(mode="json")
    if isinstance(resultat, ResultatGetTendance) and len(resultat.points) > LIMITE_POINTS_TENDANCE:
        points = sorted(resultat.points, key=lambda p: p.date)
        donnees = {
            "points": [p.model_dump(mode="json") for p in points[-LIMITE_POINTS_TENDANCE:]],
            "points_omis": len(points) - LIMITE_POINTS_TENDANCE,
        }
    return json.dumps(donnees, ensure_ascii=False)


def _date(annee: str, mois: str, jour: str) -> date | None:
    try:
        return date(int(annee), int(mois), int(jour))
    except ValueError:
        return None


def _collecter(valeur: object, valeurs: list[ValeurAutorisee], tickets: set[str]) -> None:
    """Nombres, dates et clés de ticket d'une valeur JSON décodée."""
    if isinstance(valeur, bool) or valeur is None:
        return
    if isinstance(valeur, int):
        valeurs.append(valeur)
    elif isinstance(valeur, float):
        valeurs.append(Decimal(repr(valeur)))
    elif isinstance(valeur, str):
        tickets.update(_CLE_TICKET.findall(valeur))
        valeurs.extend(d for m in _DATE_ISO.finditer(valeur) if (d := _date(*m.groups())))
        # Les chiffres d'une clé de ticket ou d'un jeton ne sont pas des nombres du résultat.
        reste = CANDIDAT_JETON.sub(" ", _CLE_TICKET.sub(" ", valeur))
        valeurs.extend(Decimal(m.group(0).replace(",", ".")) for m in _NOMBRE.finditer(reste))
    elif isinstance(valeur, dict):
        for element in valeur.values():
            _collecter(element, valeurs, tickets)
    elif isinstance(valeur, list):
        for element in valeur:
            _collecter(element, valeurs, tickets)


def valeurs_outils(
    messages: tuple[MessageAgent, ...],
) -> tuple[tuple[ValeurAutorisee, ...], frozenset[str]]:
    """Valeurs autorisées et clés de ticket retournées par les messages `outil`."""
    valeurs: list[ValeurAutorisee] = []
    tickets: set[str] = set()
    for message in messages:
        if message.role != "outil":
            continue
        try:
            decode: object = json.loads(message.contenu)
        except json.JSONDecodeError:
            decode = message.contenu
        _collecter(decode, valeurs, tickets)
    return tuple(valeurs), frozenset(tickets)


def tickets_cites(texte: str) -> tuple[str, ...]:
    """Clés de ticket citées par `texte`, dans l'ordre, hors `IND-n`, `ENT-x` et `J-n`."""
    cles = (m.group(0) for m in _CLE_TICKET.finditer(texte))
    return tuple(dict.fromkeys(c for c in cles if projet(c) not in PROJETS_IGNORES))


@dataclass(frozen=True)
class RefusControle:
    """Ce que le contrôle refuse dans le texte brut d'une réponse (encore pseudonymisé)."""

    nombres: tuple[str, ...] = ()
    """Nombres et dates absents des résultats des outils, sans doublon, dans l'ordre."""
    tickets: tuple[str, ...] = ()
    """Tickets cités mais non retournés par les outils, dans l'ordre."""


def refus_reponse(reponse: ReponseAgentBrute) -> RefusControle:
    """Nombres et tickets du texte brut de `reponse` que le contrôle refuse."""
    valeurs, retournes = valeurs_outils(reponse.messages)
    nombres = controler_nombres(reponse.texte, valeurs)
    hors = tuple(c for c in tickets_cites(reponse.texte) if c not in retournes)
    return RefusControle(tuple(dict.fromkeys(nombres.refuses)), hors)


def controler_reponse(reponse: ReponseAgentBrute) -> Controle[ReponseAgent]:
    """Contrôle déterministe d'une réponse de l'Agent, encore pseudonymisée.

    Conforme si chaque nombre et chaque date du texte figure dans les résultats des outils et
    si chaque ticket cité a été retourné ; rejetée sinon, avec un message qui nomme les refus.
    """
    question = next((m.contenu for m in reversed(reponse.messages) if m.role == "utilisateur"), "")
    outils = tuple(a.nom_outil for m in reponse.messages for a in m.appels_outils)
    refus = refus_reponse(reponse)
    cites = tickets_cites(reponse.texte)
    hors = refus.tickets
    vide = not reponse.texte.strip()
    if not refus.nombres and not hors and not vide:
        sortie = ReponseAgent(
            question=question,
            texte=reponse.texte,
            outils_appeles=outils,
            tickets_cites=cites,
            statut_controle=StatutControle.conforme,
        )
        return Controle(sortie, StatutControle.conforme)
    motifs: list[str] = ["réponse vide"] if vide else []
    if refus.nombres:
        refuses = ", ".join(f"« {n} »" for n in refus.nombres)
        motifs.append(f"chiffres absents des résultats des outils : {refuses}")
    if hors:
        motifs.append(f"tickets non retournés par les outils : {', '.join(hors)}")
    sortie = ReponseAgent(
        question=question,
        texte=MESSAGE_REJET.format(motifs=" ; ".join(motifs)),
        outils_appeles=outils,
        statut_controle=StatutControle.rejete,
    )
    return Controle(sortie, StatutControle.rejete)


def _source(definition: DefinitionOutil) -> OutilSource:
    def executer(arguments: Mapping[str, JsonValue]) -> str:
        return serialiser_resultat(definition.executer(arguments))

    return OutilSource(definition.nom, definition.description, definition.arguments, executer)


class SessionAgent:
    """Session de l'Agent sur un Passage consulté ; traces dans `sorties/agent/`."""

    def __init__(
        self,
        passerelle: Passerelle,
        consultation: Consultation,
        racine: Path,
        horloge: Callable[[], datetime],
        identifiant: str,
        fermeture: Callable[[], None] | None = None,
    ) -> None:
        """`identifiant` nomme le fichier de traces ; `fermeture` ferme les fournisseurs."""
        manifeste = consultation.manifeste()
        octets = lire_prompt()
        self._consignes = octets.decode("utf-8")
        self._contexte = ContexteAppel(
            passage_id=manifeste.passage_id,
            date_arrete=manifeste.date_arrete,
            cible=manifeste.passage_id,
            version_prompt=version_prompt(octets),
            version_grille=manifeste.version_grille,
            version_donnees=manifeste.version_donnees,
        )
        self._parametres = ParametresAppel(tache=Tache.agent, max_jetons_sortie=MAX_JETONS_SORTIE)
        self._passerelle = passerelle
        self._sources = tuple(_source(d) for d in outils_consultation(consultation))
        self._fermeture = fermeture
        self.identifiant = identifiant
        self.chemin_traces = (
            racine / REPERTOIRE_AGENT / horloge().date().isoformat() / f"{identifiant}.jsonl"
        )
        self.dernier_resultat: ResultatAgent | None = None
        self.derniers_refus = RefusControle()
        """Nombres et tickets refusés dans le texte brut de la dernière réponse contrôlée."""

    @property
    def passage_id(self) -> str:
        """Passage consulté."""
        return self._contexte.passage_id

    def repondre(self, question: str) -> ReponseAgent:
        """Réponse contrôlée et ré-identifiée à `question`.

        Chaque trace est écrite dès sa production : une exception en cours de conversation
        laisse dans le fichier celles des outils déjà exécutés.
        """
        messages = (
            MessageAgent(role="systeme", contenu=self._consignes),
            MessageAgent(role="utilisateur", contenu=question),
        )
        self.derniers_refus = RefusControle()

        def controler(reponse: ReponseAgentBrute) -> Controle[ReponseAgent]:
            self.derniers_refus = refus_reponse(reponse)
            return controler_reponse(reponse)

        resultat = self._passerelle.executer_agent(
            messages,
            self._sources,
            self._parametres,
            self._contexte,
            controler,
            sur_trace=self._ecrire,
        )
        self.dernier_resultat = resultat
        return resultat.sortie

    def _ecrire(self, trace: EntreeTrace) -> None:
        """Ajoute `trace` au fichier de traces de la session."""
        self.chemin_traces.parent.mkdir(parents=True, exist_ok=True)
        with self.chemin_traces.open("a", encoding="utf-8", newline="\n") as fichier:
            fichier.write(trace.model_dump_json() + "\n")

    def fermer(self) -> None:
        """Ferme les fournisseurs construits depuis `config/llm.yaml` (aucun effet sinon)."""
        if self._fermeture is not None:
            self._fermeture()
