"""Copie versionnée du Mode repli (`demo/repli/passage/`) et `consultation_repli`."""

import json
from datetime import date
from pathlib import Path

from tests.unit.chaine.environnement import RACINE_DEPOT
from usine.contrats.meteo import Couleur
from usine.ui.cli import REPERTOIRE_REPLI, consultation_repli

PASSAGE_ID = "20261012T152755Z-5de91e"
"""`passage_id` de la copie, repris par les réponses enregistrées de l'Agent (Story 7.11)."""


def test_copie_lisible_et_conforme() -> None:
    consultation = consultation_repli(RACINE_DEPOT)
    assert consultation is not None
    manifeste = consultation.manifeste()
    assert manifeste.passage_id == PASSAGE_ID
    assert manifeste.date_arrete == date(2026, 10, 9)
    assert manifeste.palier == 1
    assert not manifeste.classification_initiale
    assert manifeste.horodatage_fin > manifeste.horodatage_debut  # durée réellement mesurée


def test_scenarios_au_09_10_2026() -> None:
    consultation = consultation_repli(RACINE_DEPOT)
    assert consultation is not None
    couleurs = {meteo.entite: meteo.couleur for meteo in consultation.meteo()}
    assert list(couleurs) == [f"ENT-{lettre}" for lettre in "ABCDEFGHIJ"]
    assert couleurs["ENT-A"] is Couleur.rouge
    assert couleurs["ENT-B"] is Couleur.rouge
    assert couleurs["ENT-C"] is Couleur.orange


def test_previsions_non_vides() -> None:
    consultation = consultation_repli(RACINE_DEPOT)
    assert consultation is not None
    assert consultation.previsions()
    assert consultation.previsions(entite="ENT-A")


def test_liens_jira_inactifs() -> None:
    consultation = consultation_repli(RACINE_DEPOT)
    assert consultation is not None
    (meteo_a,) = consultation.meteo(entite="ENT-A")
    cles = [cle for regle in meteo_a.regles for cle in regle.tickets_en_cause]
    assert cles
    assert all(cle.startswith("DEMO-") for cle in cles)  # données fictives
    assert [consultation.url_ticket(cle) for cle in cles] == [None] * len(cles)


def test_passage_id_coherent_avec_les_fichiers() -> None:
    repertoire = RACINE_DEPOT / REPERTOIRE_REPLI
    for nom in ("meteo.json", "previsions.json"):
        enveloppe = json.loads((repertoire / nom).read_text(encoding="utf-8"))
        assert enveloppe["passage_id"] == PASSAGE_ID, nom
    traces = sorted((repertoire / "trace").glob("*.jsonl"))
    assert traces
    for trace in traces:
        lignes = trace.read_text(encoding="utf-8").splitlines()
        assert lignes, trace.name
        assert {json.loads(ligne)["passage_id"] for ligne in lignes} == {PASSAGE_ID}


def test_consultation_repli_sans_copie(tmp_path: Path) -> None:
    assert consultation_repli(tmp_path) is None
    (tmp_path / REPERTOIRE_REPLI).mkdir(parents=True)
    assert consultation_repli(tmp_path) is None  # répertoire sans manifeste
