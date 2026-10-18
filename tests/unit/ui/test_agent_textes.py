"""Textes de l'écran Agent : badge « hors périmètre » robuste, date de la mention de repli."""

import unicodedata
from datetime import UTC, datetime

import pytest

from usine.contrats.llm import ReponseAgent, ReponseAgentEnregistree
from usine.ia.agent.session import SANS_REPONSE
from usine.ui.agent import est_hors_perimetre, mention_repli
from usine.ui.ecrans import vue_reponse_agent

NBSP = " "
NNBSP = " "


@pytest.mark.parametrize(
    "texte",
    [
        SANS_REPONSE,
        f"  {SANS_REPONSE}\n",
        "Les données ne permettent pas de répondre",
        "les données ne permettent pas de répondre.",
        "LES DONNÉES NE PERMETTENT PAS DE RÉPONDRE !",
        "« Les données ne permettent pas de répondre. »",
        f"«{NBSP}Les données ne permettent pas de répondre{NNBSP}!{NBSP}»",
        '"Les données ne permettent pas de répondre."',
        "“Les données ne permettent pas de répondre.”",
        "'Les données ne permettent pas de répondre.'",
        "Les  données\tne permettent pas\nde répondre...",
        f"Les{NBSP}données ne{NNBSP}permettent pas de répondre…",
        unicodedata.normalize("NFD", SANS_REPONSE),  # « é » décomposé
        "﻿Les données ne permettent pas de ré­pondre.​",
        "Les​ données ne permettent⁠ pas de répondre.",
    ],
)
def test_variantes_de_la_phrase_acceptees(texte: str) -> None:
    assert est_hors_perimetre(texte, SANS_REPONSE)


@pytest.mark.parametrize(
    "texte",
    [
        "Les données permettent de répondre.",
        "Les données ne permettent pas de répondre : ENT-A est Rouge.",
        "ENT-A est Rouge. Les données ne permettent pas de répondre.",
        "Les données ne permettent pas de conclure.",
        "",
        "Les données ne permettent pas de répondre :",
        "Les données ne permettent pas de répondre ;",
        "Les données ne permettent pas de répondre,",
    ],
)
def test_autre_phrase_refusee(texte: str) -> None:
    assert not est_hors_perimetre(texte, SANS_REPONSE)


def test_phrase_de_reference_vide_jamais_hors_perimetre() -> None:
    assert not est_hors_perimetre("", "")
    assert not est_hors_perimetre(" . ", "")


def test_badge_hors_perimetre_sur_une_variante() -> None:
    reponse = ReponseAgent(question="?", texte="« les données ne permettent pas de répondre »")
    vue = vue_reponse_agent(reponse, SANS_REPONSE)
    assert vue.badge_code == "hors_perimetre"
    autre = vue_reponse_agent(ReponseAgent(question="?", texte="ENT-A."), SANS_REPONSE)
    assert autre.badge_code != "hors_perimetre"


@pytest.mark.parametrize(
    ("instant", "jour"),
    [
        (datetime(2026, 10, 12, 22, 12, tzinfo=UTC), "13/10/2026"),  # été, jour suivant
        (datetime(2026, 1, 15, 22, 12, tzinfo=UTC), "15/01/2026"),  # hiver, même jour
    ],
)
def test_mention_repli_date_de_paris(instant: datetime, jour: str) -> None:
    enregistree = ReponseAgentEnregistree(
        passage_id="20261012T221200Z-abcdef",
        horodatage=instant,
        reponse=ReponseAgent(question="?", texte="ENT-A."),
    )
    assert mention_repli(enregistree).startswith(f"Mode repli : réponse enregistrée le {jour} ")
