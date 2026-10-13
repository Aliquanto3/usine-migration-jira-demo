"""Exécution et notation automatique de la suite d'évaluation de l'Agent (SM-4, FR-42).

`executer_suite` pose chaque question à la vraie `SessionAgent`, celle de l'UI (façade
`usine.composition.construire_session_agent`) : outils réels sur le Passage, passerelle
(Pseudonymisation, cache en mémoire, traces) et contrôle des chiffres et des tickets. Les
traces vont dans `racine/sorties/agent/<AAAA-MM-JJ>/<session>.jsonl` ; le Passage n'est que lu.

Par défaut, le fournisseur est `FournisseurAgentEnregistre` (tour enregistré de chaque
question : ses appels d'outils sont réellement exécutés, puis son texte est rendu) et le
pseudonymiseur `PseudonymiseurIdentite` : ni réseau ni secret. `reel=True` lit
`config/llm.yaml` (tâche `agent`), la clé du fournisseur et `USINE_CLE_PSEUDO`.

Notation : une question répondable réussit si la réponse est conforme au contrôle, n'est pas
un refus et contient chaque élément attendu (Entité et ticket : mot entier ; chiffre : nombre
isolé écrit à la française) ; une question sans réponse possible réussit si la réponse
conforme contient « ne permettent pas de répondre ». Sont comptés les chiffres inventés
(nombres refusés par le contrôle dans le texte brut), les tickets inventés et les refus sur
les questions répondables. SM-4 : score ≥ 13 sur 15, aucun chiffre inventé, au plus 1 refus.
"""

import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from evals.agent.questions import FichierQuestions, QuestionAgent, TourEnregistre
from evals.explication.suite import VERSION_MODELE_ENREGISTRE, PseudonymiseurIdentite
from usine.composition import SessionAgent, construire_session_agent, consultation_repertoire
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    AppelOutil,
    MessageAgent,
    OutilAgent,
    ParametresAppel,
    ReponseAgentBrute,
    ReponseStructuree,
    StatutControle,
)

SCORE_SM4 = 13
"""Score minimal sur 15 de SM-4."""

MAX_REFUS_SM4 = 1
"""Refus tolérés sur les questions répondables (H-22)."""

PHRASE_SANS_REPONSE = "ne permettent pas de répondre"
"""Marque d'une réponse « Les données ne permettent pas de répondre. »"""

REPERTOIRE_PASSAGE = Path("demo/repli/passage")
"""Passage interrogé, relatif à la racine du dépôt."""

REPERTOIRE_RESULTATS = Path(__file__).parent / "resultats"
CHEMIN_HISTORIQUE = Path(__file__).parent / "historique.jsonl"


def _jetons(texte: str) -> int:
    return len(texte.split())


class FournisseurAgentEnregistre:
    """Fournisseur LLM sans réseau : joue le tour enregistré de la question posée.

    Les appels d'outils du tour sont exécutés par les vrais outils (enveloppés par la
    passerelle), puis le texte enregistré est rendu, comme le ferait le modèle.
    """

    def __init__(self, tours: Mapping[str, tuple[str, TourEnregistre]]) -> None:
        """`tours` : texte de la question -> (identifiant, tour enregistré)."""
        self._tours = dict(tours)

    @property
    def version_modele(self) -> str:
        """Version de modèle annoncée (`enregistre:rejeu`)."""
        return VERSION_MODELE_ENREGISTRE

    def generer_structure[T: BaseModel](
        self, prompt: str, schema: type[T], parametres: ParametresAppel
    ) -> ReponseStructuree[T]:
        """Sans objet pour l'Agent."""
        raise UsineErreur("suite de l'Agent : aucune réponse structurée enregistrée")

    def executer_agent(
        self,
        messages: Sequence[MessageAgent],
        outils: Sequence[OutilAgent],
        parametres: ParametresAppel,
    ) -> ReponseAgentBrute:
        """Conversation du tour enregistré de la dernière question de `messages`."""
        question = next((m.contenu for m in reversed(messages) if m.role == "utilisateur"), "")
        if question not in self._tours:
            raise UsineErreur(f"suite de l'Agent : aucun tour enregistré pour « {question} »")
        identifiant, tour = self._tours[question]
        par_nom = {outil.nom: outil for outil in outils}
        appels = tuple(
            AppelOutil(
                id_appel=f"{identifiant}-{rang}", nom_outil=a.nom_outil, arguments=a.arguments
            )
            for rang, a in enumerate(tour.appels, start=1)
        )
        conversation = list(messages)
        if appels:
            conversation.append(MessageAgent(role="assistant", contenu="", appels_outils=appels))
        for appel in appels:
            outil = par_nom.get(appel.nom_outil)
            if outil is None:
                raise UsineErreur(
                    f"question « {identifiant} » : outil inconnu « {appel.nom_outil} »"
                    f" (outils : {', '.join(par_nom)})"
                )
            conversation.append(
                MessageAgent(
                    role="outil", contenu=outil.executer(appel.arguments), id_appel=appel.id_appel
                )
            )
        conversation.append(MessageAgent(role="assistant", contenu=tour.texte))
        return ReponseAgentBrute(
            texte=tour.texte,
            messages=tuple(conversation),
            jetons_entree=sum(_jetons(m.contenu) for m in messages),
            jetons_sortie=_jetons(tour.texte),
            version_modele=VERSION_MODELE_ENREGISTRE,
        )


_ESPACES = re.compile(r"[  ]")


def contient_mot(texte: str, element: str) -> bool:
    """Vrai si `element` (Entité, indicateur, ticket) figure en mot entier dans `texte`."""
    return re.search(rf"(?<![\w-]){re.escape(element)}(?![\w]|-\w)", texte) is not None


def contient_chiffre(texte: str, chiffre: str) -> bool:
    """Vrai si `chiffre` figure isolé dans `texte` : ni collé à un mot, une clé ou une date, ni
    fragment d'un nombre plus long (`100` n'est pas dans `1 100`, ni `4` dans `IND-4`)."""
    normalise = _ESPACES.sub(" ", texte)
    motif = re.escape(_ESPACES.sub(" ", chiffre))
    return (
        re.search(rf"(?<![\w.,/-])(?<!\d ){motif}(?![\w/-]|[.,]\d| \d{{3}})", normalise) is not None
    )


def _manquants(question: QuestionAgent, texte: str) -> dict[str, list[str]]:
    attendus = question.attendus
    return {
        "entites": [e for e in attendus.entites if not contient_mot(texte, e)],
        "tickets": [t for t in attendus.tickets if not contient_mot(texte, t)],
        "chiffres": [c for c in attendus.chiffres if not contient_chiffre(texte, c)],
    }


def _poser(session: SessionAgent, question: QuestionAgent) -> dict[str, Any]:
    reponse = session.repondre(question.question)
    refus_controle = session.derniers_refus
    resultat = session.dernier_resultat
    conforme = reponse.statut_controle is StatutControle.conforme
    sans_reponse = conforme and PHRASE_SANS_REPONSE in reponse.texte
    manquants = _manquants(question, reponse.texte)
    if question.repondable:
        reussie = conforme and not sans_reponse and not any(manquants.values())
    else:
        reussie = sans_reponse
    trace = resultat.traces[-1] if resultat is not None else None
    return {
        "identifiant": question.identifiant,
        "question": question.question,
        "repondable": question.repondable,
        "demo": question.demo,
        "texte": reponse.texte,
        "statut_controle": reponse.statut_controle.value,
        "outils_appeles": list(reponse.outils_appeles),
        "tickets_cites": list(reponse.tickets_cites),
        "reussie": reussie,
        "refus": question.repondable and sans_reponse,
        "chiffres_inventes": len(refus_controle.nombres),
        "chiffres_refuses": list(refus_controle.nombres),
        "tickets_inventes": len(refus_controle.tickets),
        "tickets_refuses": list(refus_controle.tickets),
        "manquants": manquants,
        "version_prompt": trace.version_prompt if trace else None,
        "version_modele": trace.version_modele if trace else None,
        "cout_estime_eur": str(trace.cout_estime_eur if trace else Decimal(0)),
    }


def executer_suite(
    fichier: FichierQuestions,
    racine: Path,
    passage: Path | None = None,
    *,
    reel: bool = False,
    horloge: datetime | None = None,
) -> dict[str, Any]:
    """Résultat JSON de la suite : réponse et notation par question, score, verdict SM-4.

    `passage` (défaut : `racine/demo/repli/passage`) doit être le Passage des questions
    (`passage_id`), sinon `UsineErreur`. Rejeu (défaut) : chaque question doit porter son tour
    enregistré, sinon `UsineErreur` nommant la question. Une seule session pour les 15
    questions, donc un seul fichier de traces.
    """
    instant = horloge or datetime.now(UTC)
    repertoire = passage if passage is not None else racine / REPERTOIRE_PASSAGE
    consultation = consultation_repertoire(repertoire)
    passage_id = consultation.manifeste().passage_id
    if passage_id != fichier.passage_id:
        raise UsineErreur(
            f"{repertoire} : Passage {passage_id}, alors que les questions décrivent le Passage"
            f" {fichier.passage_id}"
        )
    if reel:
        session = construire_session_agent(racine, consultation)
    else:
        tours: dict[str, tuple[str, TourEnregistre]] = {}
        for question in fichier.questions:
            if question.tour is None:
                raise UsineErreur(
                    f"question « {question.identifiant} » : aucun tour enregistré (rejeu)"
                )
            tours[question.question] = (question.identifiant, question.tour)
        session = construire_session_agent(
            racine, consultation, FournisseurAgentEnregistre(tours), PseudonymiseurIdentite()
        )
    try:
        sorties = [_poser(session, question) for question in fichier.questions]
    finally:
        session.fermer()
    repondables = [s for s in sorties if s["repondable"]]
    score = sum(s["reussie"] for s in sorties)
    chiffres = sum(s["chiffres_inventes"] for s in sorties)
    refus = sum(s["refus"] for s in sorties)
    return {
        "horodatage": instant.isoformat(),
        "mode": "reel" if reel else "rejeu",
        "passage_id": passage_id,
        "version_prompt": ", ".join(sorted({str(s["version_prompt"]) for s in sorties})),
        "version_modele": ", ".join(sorted({str(s["version_modele"]) for s in sorties})),
        "traces": str(session.chemin_traces),
        "nombre_questions": len(sorties),
        "nombre_repondables": len(repondables),
        "score": score,
        "chiffres_inventes": chiffres,
        "tickets_inventes": sum(s["tickets_inventes"] for s in sorties),
        "refus_repondables": refus,
        "sm4_atteint": score >= SCORE_SM4 and chiffres == 0 and refus <= MAX_REFUS_SM4,
        "cout_estime_eur": str(sum((Decimal(s["cout_estime_eur"]) for s in sorties), Decimal(0))),
        "questions": sorties,
    }


def ajouter_historique(
    resultat: dict[str, Any], chemin_resultat: Path, chemin_historique: Path = CHEMIN_HISTORIQUE
) -> dict[str, Any]:
    """Ajoute à `chemin_historique` la synthèse de `resultat` (une ligne JSON) et la renvoie."""
    entree = {
        "horodatage": resultat["horodatage"],
        "resultat": chemin_resultat.name,
        "mode": resultat["mode"],
        "passage_id": resultat["passage_id"],
        "version_prompt": resultat["version_prompt"],
        "version_modele": resultat["version_modele"],
        "nombre_questions": resultat["nombre_questions"],
        "score": resultat["score"],
        "chiffres_inventes": resultat["chiffres_inventes"],
        "tickets_inventes": resultat["tickets_inventes"],
        "refus_repondables": resultat["refus_repondables"],
        "sm4_atteint": resultat["sm4_atteint"],
        "cout_estime_eur": resultat["cout_estime_eur"],
    }
    chemin_historique.parent.mkdir(parents=True, exist_ok=True)
    with chemin_historique.open("a", encoding="utf-8", newline="\n") as fichier:
        fichier.write(json.dumps(entree, ensure_ascii=False) + "\n")
    return entree
