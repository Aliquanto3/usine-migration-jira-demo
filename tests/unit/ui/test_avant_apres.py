"""Avant / après : durée mesurée, tableau (par Rapport et cumulé) et légende."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from usine.contrats.passage import ManifestePassage
from usine.ui.avant_apres import (
    AUCUN_PASSAGE,
    CONFIG_ABSENTE,
    MENTION_CUMUL,
    MENTION_FICTIVE,
    duree_mesuree,
    legende,
)

DEBUT = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)


def manifeste(
    secondes: float = 3.4,
    classification_initiale: bool = False,
    passage_id: str = "20261012T073000Z-aaaaaa",
    date_arrete: date = date(2026, 10, 9),
    debut: datetime = DEBUT,
) -> ManifestePassage:
    """Manifeste minimal d'un Passage de `secondes` secondes."""
    return ManifestePassage(
        passage_id=passage_id,
        date_arrete=date_arrete,
        palier=1,
        source="journal",
        horodatage_debut=debut,
        horodatage_fin=debut + timedelta(seconds=secondes),
        version_grille="abc",
        version_donnees="def",
        classification_initiale=classification_initiale,
        cout_llm_eur=Decimal(0),
        nb_alignements=0,
        nb_tickets=0,
        etapes=(),
    )


def publier(racine: Path, manifeste: ManifestePassage) -> None:
    """Écrit à la main le manifeste d'un Passage publié sous `racine/sorties/passages/`."""
    repertoire = (
        racine / "sorties" / "passages" / manifeste.date_arrete.isoformat() / manifeste.passage_id
    )
    repertoire.mkdir(parents=True)
    (repertoire / "manifeste.json").write_text(manifeste.model_dump_json(), encoding="utf-8")


def test_duree_mesuree() -> None:
    assert duree_mesuree(manifeste(3.4)) == timedelta(seconds=3.4)
    assert duree_mesuree(manifeste(0)) == timedelta(0)


def test_legende() -> None:
    texte = legende(manifeste())
    assert "09/10/2026" in texte
    assert "`20261012T073000Z-aaaaaa`" in texte
    assert texte.endswith(f"{MENTION_FICTIVE} {MENTION_CUMUL}")
    assert MENTION_CUMUL == "Cumul : 5 × le temps d'un Rapport."
    assert MENTION_FICTIVE == (
        "Temps manuel : valeur déclarative fictive (`config/demo.yaml`, Q-5)."
    )


def test_messages() -> None:
    assert AUCUN_PASSAGE == "Aucun Passage publié : lancer la Chaîne pour mesurer son temps."
    assert "config/demo.yaml" in CONFIG_ABSENTE
    assert "temps_manuel_minutes_par_rapport" in CONFIG_ABSENTE
