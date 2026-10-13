"""Réponses enregistrées de l'Agent, rejouées en Mode repli (FR-45, NFR-12, AD-24).

`usine agent --enregistrer` pose les questions de la démo (`QUESTIONS_DEMO`) à une session sur
la copie `demo/repli/passage/` et écrit une `ReponseAgentEnregistree` par question dans
`demo/repli/agent/<rang>.json`, versionnés. En Mode repli, l'UI les relit par
`charger_reponses` : une réponse dont le `passage_id` n'est pas celui de la copie est refusée
avec un message explicite, jamais rejouée.
"""

from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ReponseAgent, ReponseAgentEnregistree, StatutControle

REPERTOIRE_REPONSES = Path("demo/repli/agent")
"""Réponses enregistrées versionnées, relatives à la racine du dépôt."""

QUESTIONS_DEMO: tuple[str, ...] = (
    "Quelles entités risquent de passer au rouge la semaine prochaine, et pourquoi ?",
    "Quelles entités sont rouges à la Date d'arrêté ?",
    "Pourquoi ENT-B est-elle rouge ?",
    "Combien d'Anomalies sont ouvertes chez ENT-C ?",
    "Quel est le budget restant du programme de migration ?",
)
"""Questions de la démo proposées en choix fermés en Mode repli (dont un refus attendu)."""


class SessionEnregistrable(Protocol):
    """Ce que l'enregistrement utilise d'une `SessionAgent`."""

    @property
    def passage_id(self) -> str:
        """Passage consulté."""
        ...

    def repondre(self, question: str) -> ReponseAgent:
        """Réponse contrôlée à `question`."""
        ...


def enregistrer_reponses(
    session: SessionEnregistrable,
    repertoire: Path,
    horloge: Callable[[], datetime],
    questions: Sequence[str] = QUESTIONS_DEMO,
) -> list[Path]:
    """Pose `questions` à `session` et écrit leurs réponses dans `repertoire/<rang>.json`.

    Rien n'est écrit si une réponse est rejetée par le contrôle (`UsineErreur` nommant la
    question) ; sinon les anciens `*.json` de `repertoire` sont remplacés.
    """
    if not questions:
        raise UsineErreur("enregistrement de l'Agent : aucune question à poser")
    enregistrees: list[ReponseAgentEnregistree] = []
    for question in questions:
        reponse = session.repondre(question)
        if reponse.statut_controle is StatutControle.rejete:
            raise UsineErreur(
                f"question « {question} » : réponse rejetée par le contrôle, rien n'est"
                f" enregistré ({reponse.texte})"
            )
        enregistrees.append(
            ReponseAgentEnregistree(
                passage_id=session.passage_id, horodatage=horloge(), reponse=reponse
            )
        )
    repertoire.mkdir(parents=True, exist_ok=True)
    for ancien in repertoire.glob("*.json"):
        ancien.unlink()
    chemins: list[Path] = []
    for rang, enregistree in enumerate(enregistrees, start=1):
        chemin = repertoire / f"{rang:02d}.json"
        chemin.write_text(enregistree.model_dump_json(indent=2) + "\n", encoding="utf-8")
        chemins.append(chemin)
    return chemins


def charger_reponses(repertoire: Path, passage_id: str) -> tuple[ReponseAgentEnregistree, ...]:
    """Réponses de `repertoire/*.json`, dans l'ordre des fichiers, toutes sur `passage_id`.

    Répertoire vide, fichier invalide ou `passage_id` différent : `UsineErreur` explicite.
    """
    chemins = sorted(repertoire.glob("*.json")) if repertoire.is_dir() else []
    if not chemins:
        raise UsineErreur(
            f"{repertoire} : aucune réponse enregistrée de l'Agent ; lancer"
            " `usine agent --enregistrer`"
        )
    reponses: list[ReponseAgentEnregistree] = []
    for chemin in chemins:
        try:
            enregistree = ReponseAgentEnregistree.model_validate_json(chemin.read_bytes())
        except (OSError, ValidationError) as exc:
            raise UsineErreur(f"{chemin} : réponse enregistrée illisible ({exc})") from exc
        if enregistree.passage_id != passage_id:
            raise UsineErreur(
                f"{chemin} : réponse enregistrée sur le Passage {enregistree.passage_id}, alors"
                f" que la copie du Mode repli est le Passage {passage_id} ; réponses refusées,"
                " relancer `usine agent --enregistrer`"
            )
        reponses.append(enregistree)
    return tuple(reponses)
