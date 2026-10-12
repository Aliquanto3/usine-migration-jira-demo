"""Bout en bout (constat 23 de la rétro E0) : un vrai `usine rapport` lancé depuis la page.

Le sous-processus est réel (`subprocess.Popen`) ; seule la Date d'arrêté est fixée au
09/10/2026 pour retrouver le Passage d'essai. La page sonde la progression jusqu'à la fin.
"""

import time
from functools import partial
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.unit.chaine.environnement import DATE_ARRETE, preparer_racine
from usine.contrats.passage import REPERTOIRE_PASSAGES, Etape
from usine.ui import lancement
from usine.ui.navigation import Ecran

APP = Path(lancement.__file__).with_name("app.py")
DELAI_MAX = 60.0  # secondes
PAUSE = 0.5  # secondes entre deux sondages


def _fini(page: AppTest) -> bool:
    return bool(page.success) or any("Échec de la Chaîne" in e.value for e in page.error)


def test_vrai_rapport_depuis_la_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    racine = preparer_racine(tmp_path)
    monkeypatch.chdir(racine)
    monkeypatch.setattr(
        lancement, "lancer_chaine", partial(lancement.lancer_chaine, date_arrete=DATE_ARRETE)
    )
    page = AppTest.from_file(str(APP), default_timeout=60).run()
    assert "Aucun Passage publié" in page.info[0].value
    page.sidebar.radio[0].set_value(Ecran.lancement.value).run()
    page.button[0].click().run()
    assert not page.exception

    limite = time.monotonic() + DELAI_MAX
    while not _fini(page):
        assert time.monotonic() < limite, "usine rapport non terminé en 60 s"
        time.sleep(PAUSE)
        page.run()

    assert not page.exception
    assert not page.error, [e.value for e in page.error]
    assert "Chaîne terminée" in page.success[0].value
    # `Etape` n'a pas d'étape `publication` : la publication suit la dernière étape (`rendu`)
    # et se constate par le répertoire publié du Passage, puis par la carte.
    etapes = "\n".join(str(m.value) for m in page.markdown)
    for etape in Etape:
        assert f"**{etape.value}** : " in etapes
    assert "En attente" not in etapes
    assert "Échec" not in etapes
    assert f"**{list(Etape)[-1].value}** : Réussie" in etapes
    publies = list((racine / REPERTOIRE_PASSAGES / DATE_ARRETE.isoformat()).iterdir())
    assert len(publies) == 1
    assert (publies[0] / "manifeste.json").is_file()

    page.sidebar.radio[0].set_value(Ecran.carte.value).run()
    assert not page.exception
    assert "09/10/2026" in page.caption[0].value
    assert any(str(m.value).startswith("| Entité |") for m in page.markdown)
