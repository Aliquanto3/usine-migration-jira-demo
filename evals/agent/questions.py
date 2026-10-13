"""Questions versionnées de la suite d'évaluation de l'Agent (SM-4, FR-42).

Le fichier `questions.json` porte en tête le `passage_id` du Passage interrogé
(`demo/repli/passage/`), puis 15 questions types du Pilote. Chacune a un identifiant, son
texte, `repondable` (faux : la seule réponse juste est « Les données ne permettent pas de
répondre. »), `demo` (vrai pour la seule question de la démo), ses éléments attendus
(`entites` : codes d'Entité ou d'indicateur ; `tickets` ; `chiffres` : nombres ou dates ISO
écrits à la française) et le tour enregistré (`tour` : appels d'outils, puis texte final),
rejoué hors réseau.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from usine.contrats.erreurs import UsineErreur

NOMBRE_QUESTIONS = 15
"""Nombre de questions exigé par FR-42."""

MIN_SANS_REPONSE = 2
"""Nombre minimal de questions sans réponse possible (FR-42)."""

QUESTION_DEMO = "Quelles entités risquent de passer au rouge la semaine prochaine, et pourquoi ?"
"""Question de la démo, mot pour mot celle de l'epic 7 (Story 7.9)."""

CHEMIN_QUESTIONS = Path(__file__).parent / "questions.json"
"""Fichier des questions versionnées."""


class _Modele(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Attendus(_Modele):
    """Éléments qu'une réponse juste doit contenir."""

    entites: tuple[str, ...] = ()
    """Codes d'Entité (`ENT-C`) ou d'indicateur (`IND-4`), cherchés en mot entier."""
    tickets: tuple[str, ...] = ()
    """Clés de ticket, cherchées en mot entier."""
    chiffres: tuple[str, ...] = ()
    """Nombres isolés écrits à la française (`1 100`, `0,5`) ou dates ISO (`2026-10-14`)."""


class AppelEnregistre(_Modele):
    """Appel d'outil du tour enregistré."""

    nom_outil: str = Field(min_length=1)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class TourEnregistre(_Modele):
    """Tour d'Agent enregistré : appels d'outils exécutés dans l'ordre, puis texte final."""

    appels: tuple[AppelEnregistre, ...] = ()
    texte: str


class QuestionAgent(_Modele):
    """Question de la suite, ses attendus et son tour enregistré."""

    identifiant: str = Field(min_length=1)
    question: str = Field(min_length=1)
    repondable: bool
    demo: bool = False
    attendus: Attendus = Attendus()
    tour: TourEnregistre | None = None
    """Absent : la question ne peut être jouée qu'en mode réel."""


class FichierQuestions(_Modele):
    """Contenu de `questions.json`."""

    passage_id: str = Field(min_length=1)
    """Passage dont les questions et leurs attendus décrivent les données."""
    questions: tuple[QuestionAgent, ...]


def charger_questions(chemin: Path = CHEMIN_QUESTIONS) -> FichierQuestions:
    """Questions de `chemin`, validées : 15 questions aux identifiants et textes uniques, une
    seule `demo` (la question de l'epic, répondable), au moins 2 sans réponse possible.

    Un fichier illisible, mal formé ou hors de ces règles lève une `UsineErreur`.
    """
    try:
        fichier = FichierQuestions.model_validate_json(chemin.read_bytes())
    except OSError as exc:
        raise UsineErreur(f"{chemin} : questions illisibles ({exc.strerror or exc})") from exc
    except ValidationError as exc:
        premiere = exc.errors()[0]
        lieu = ".".join(str(partie) for partie in premiere["loc"]) or "racine"
        raise UsineErreur(
            f"{chemin} : questions mal formées ({exc.error_count()} erreur(s), {lieu} :"
            f" {premiere['msg']})"
        ) from exc
    questions = fichier.questions
    if len(questions) != NOMBRE_QUESTIONS:
        raise UsineErreur(
            f"{chemin} : {len(questions)} question(s), {NOMBRE_QUESTIONS} attendues (FR-42)"
        )
    for attribut in ("identifiant", "question"):
        valeurs = [getattr(q, attribut) for q in questions]
        doublons = sorted({v for v in valeurs if valeurs.count(v) > 1})
        if doublons:
            raise UsineErreur(f"{chemin} : {attribut}(s) en double {doublons}")
    demos = [q for q in questions if q.demo]
    if len(demos) != 1:
        raise UsineErreur(f"{chemin} : {len(demos)} question(s) de la démo, une seule attendue")
    (demo,) = demos
    if demo.question != QUESTION_DEMO or not demo.repondable:
        raise UsineErreur(
            f"{chemin}, question « {demo.identifiant} » : la question de la démo doit être"
            f" répondable et exactement « {QUESTION_DEMO} »"
        )
    sans_reponse = sum(not q.repondable for q in questions)
    if sans_reponse < MIN_SANS_REPONSE:
        raise UsineErreur(
            f"{chemin} : {sans_reponse} question(s) sans réponse possible,"
            f" au moins {MIN_SANS_REPONSE} attendues (FR-42)"
        )
    return fichier
