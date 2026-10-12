"""Journal à la volumétrie de `config/programme.yaml`, lu aux clés Jira (Story 2.5, FR-8).

Test `lent` : sauté par défaut, lancé par `uv run pytest -m lent tests/unit/adaptateurs/journal`.
Le réseau est coupé par la fixture `sans_reseau` du répertoire.
"""

from datetime import date
from pathlib import Path

import pytest

from tests.unit.adaptateurs.journal.outils import cle_jira, manifeste_pour
from usine.adaptateurs.journal import SourceJournal
from usine.chaine.etapes import jours_du_passage
from usine.config import charger_yaml
from usine.contrats.config import ConfigProgramme
from usine.contrats.tickets import SCHEMA_TICKET_ETAT
from usine.domaine.instantanes import instantane, tickets_etats
from usine.generateur.journal import generer, serialiser_journal

RACINE = Path(__file__).resolve().parents[4]


@pytest.mark.lent
def test_journal_a_l_echelle_aux_cles_jira(tmp_path: Path) -> None:
    programme = charger_yaml(RACINE / "config" / "programme.yaml", ConfigProgramme)
    generation = generer(programme, 42, date(2026, 10, 12))
    assert len(generation.evenements) > 30_000
    chemin = tmp_path / "journal.jsonl"
    chemin.write_bytes(serialiser_journal(generation))
    manifeste = manifeste_pour(generation.entete, generation.evenements)

    source = SourceJournal(chemin, manifeste)
    evenements = list(source.evenements())

    assert len(evenements) == len(generation.evenements)
    for rendu, origine in zip(evenements, generation.evenements, strict=True):
        assert rendu == origine.model_copy(update={"cle_ticket": cle_jira(origine.cle_ticket)})
    cles_jira = set(manifeste.correspondance_cles.values())
    assert {e.cle_ticket for e in evenements} == cles_jira

    entete = generation.entete
    jours = jours_du_passage(entete.ancrage_semaines, entete.date_injection)
    dates = sorted({jours[0], jours[len(jours) // 2], jours[-1]})
    assert jours[-1] == entete.date_injection
    etats = tickets_etats(evenements, dates)
    assert dict(etats.schema) == dict(SCHEMA_TICKET_ETAT.colonnes)
    assert set(etats["date"].unique().to_list()) == set(dates)
    assert set(etats["cle_ticket"].unique().to_list()) <= cles_jira
    assert etats.filter(etats["date"] == entete.date_injection).height > 0
    instantanes = instantane(etats)
    assert instantanes.height > 0
