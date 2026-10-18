"""Écran Agent : libellés et mise en forme d'une réponse contrôlée (FR-39, FR-40)."""

import unicodedata
from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol

from usine.contrats.format import formater_date, heure_de_paris
from usine.contrats.llm import ReponseAgent, ReponseAgentEnregistree, StatutControle


class Session(Protocol):
    """Ce que l'écran utilise d'une `SessionAgent` (`ui/cli.session_agent`)."""

    @property
    def passage_id(self) -> str:
        """Passage consulté."""
        ...

    def repondre(self, question: str) -> ReponseAgent:
        """Réponse contrôlée à `question`."""
        ...

    def fermer(self) -> None:
        """Ferme les fournisseurs de la session."""
        ...


AUCUN_PASSAGE = "Aucun Passage publié : lancer la Chaîne pour que l'Agent puisse le consulter."

QUESTION_DEMO = "Quelle Entité risque de passer au rouge, et pourquoi ?"
"""Question de la démo, proposée dans le champ de saisie."""

LIBELLE_QUESTION = "Question à l'Agent"

LEGENDE = (
    "L'Agent ne lit que le dernier Passage publié, par des outils en lecture seule ; chaque"
    " chiffre et chaque ticket de sa réponse est contrôlé contre les résultats de ces outils."
)

MESSAGE_REPLI = (
    "En Mode repli, l'Agent ne s'adresse à aucun LLM : choisir une question enregistrée lors"
    " d'une répétition, sa réponse contrôlée est rejouée telle quelle."
)

LIBELLE_CHOIX = "Question enregistrée"
REFUS_REPLI = "Mode repli : réponses enregistrées de l'Agent refusées"


def mention_repli(enregistree: ReponseAgentEnregistree) -> str:
    """Mention « Mode repli » d'une réponse rejouée : date d'enregistrement et Passage."""
    jour = heure_de_paris(enregistree.horodatage).date()
    return (
        f"Mode repli : réponse enregistrée le {formater_date(jour)}"
        f" sur le Passage {enregistree.passage_id}, rejouée sans LLM"
    )


LIBELLES_STATUT: Mapping[StatutControle, str] = MappingProxyType(
    {
        StatutControle.non_controle: "non contrôlée",
        StatutControle.conforme: "conforme : chiffres et tickets vérifiés",
        StatutControle.corrige: "corrigée",
        StatutControle.rejete: "rejetée par le contrôle",
    }
)
"""Libellé du statut de contrôle d'une réponse."""


def texte_statut(reponse: ReponseAgent) -> str:
    """Statut de contrôle de la réponse, en français."""
    return f"Contrôle : {LIBELLES_STATUT[reponse.statut_controle]}"


_GUILLEMETS = "«»\"'“”‘’„‚‹›`"
_PONCTUATION_FINALE = ".!…"
_INVISIBLES = dict.fromkeys(map(ord, "​­﻿⁠"))
"""Espace sans chasse, trait d'union conditionnel, BOM et gluon de mots : retirés."""


def _normaliser(texte: str) -> str:
    """Casse, guillemets, ponctuation finale, espaces et caractères invisibles neutralisés.

    Forme NFC d'abord (un « é » décomposé égale un « é » composé) ; seuls `.`, `!` et `…`
    finaux sont retirés : un « : » ou un « ; » annonce une suite, la phrase diffère.
    """
    texte = unicodedata.normalize("NFC", texte).translate(_INVISIBLES)
    sans_guillemets = "".join(" " if c in _GUILLEMETS else c for c in texte)
    mots = sans_guillemets.split()  # tout espace Unicode : insécable, fine, tabulation…
    return " ".join(mots).rstrip(_PONCTUATION_FINALE + " ").casefold()


def est_hors_perimetre(texte: str, phrase_hors_perimetre: str) -> bool:
    """Réponse recopiant la phrase « hors périmètre » de l'Agent, aux variantes de forme près.

    Le LLM recopie `SANS_REPONSE` : casse, ponctuation finale, guillemets droits, typographiques
    ou français et espaces multiples ou insécables ne changent pas le verdict ; une autre phrase,
    ou la phrase suivie d'un autre texte, n'est pas hors périmètre.
    """
    attendu = _normaliser(phrase_hors_perimetre)
    return bool(attendu) and _normaliser(texte) == attendu
