"""Page Streamlit (`AppTest`) : bandeau Mode repli, carte météo, lancement et progression."""

import shutil
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import IO, Any, cast

import pytest
import streamlit
from streamlit.testing.v1 import AppTest

from usine.contrats.meteo import LIBELLES_COULEURS
from usine.contrats.passage import Etape, EvenementProgression, StatutEtape
from usine.ui import lancement
from usine.ui.cli import consultation_dernier_passage, mode_repli

REPERTOIRE_UI = Path(lancement.__file__).parent
APP = REPERTOIRE_UI / "app.py"


def _page() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=60).run()


def _textes(page: AppTest) -> str:
    return "\n".join(str(m.value) for m in page.markdown)


def test_carte_meteo(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    page = _page()
    assert not page.exception
    assert not page.warning
    consultation = consultation_dernier_passage(racine_publiee)
    assert consultation is not None
    table = page.table[0].value
    assert list(table["Entité"]) == [m.entite for m in consultation.meteo()]
    for libelle, meteo in zip(table["Météo"], consultation.meteo(), strict=True):
        assert libelle.endswith(LIBELLES_COULEURS[meteo.couleur])
    assert "09/10/2026" in page.caption[0].value


def test_racine_introuvable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    absente = tmp_path / "absente"
    monkeypatch.setenv("USINE_RACINE", str(absente))
    page = _page()
    assert not page.exception
    assert any(str(absente) in erreur.value for erreur in page.error)
    assert not page.info
    assert page.button[0].disabled


def test_sans_passage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    page = _page()
    assert not page.exception
    assert "Aucun Passage publié" in page.info[0].value
    assert not page.table


def test_mode_repli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    assert mode_repli(tmp_path)
    page = _page()
    assert "Mode repli" in page.warning[0].value
    premier = page.main.children[0]
    assert getattr(premier, "type", None) == "warning"


def test_racine_par_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("USINE_MODE_REPLI=1\n", encoding="utf-8")
    monkeypatch.setenv("USINE_RACINE", str(tmp_path))
    page = _page()
    assert "Mode repli" in page.warning[0].value


def test_mode_repli_illisible(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    monkeypatch.setenv("USINE_MODE_REPLI", "peut-etre")
    page = _page()
    assert not page.exception
    assert not page.warning
    assert any("USINE_MODE_REPLI" in erreur.value for erreur in page.error)
    assert page.subheader[-1].value == "Chaîne de reporting"  # le lancement reste affiché
    assert not page.button[0].disabled


def test_passage_illisible(
    racine_publiee: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copytree(racine_publiee / "sorties" / "passages", tmp_path / "sorties" / "passages")
    for meteo in (tmp_path / "sorties" / "passages").glob("*/*/meteo.json"):
        meteo.write_text("{illisible", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    page = _page()
    assert not page.exception
    assert "Lecture du dernier Passage impossible" in page.error[0].value
    assert not page.table


class _ProcessusFactice:
    def __init__(self) -> None:
        self.code: int | None = None

    def poll(self) -> int | None:
        return self.code


class _Lanceur:
    """`Popen` factice : note chaque appel et écrit `message` dans l'erreur standard reçue."""

    def __init__(self, message: str = "") -> None:
        self.processus = _ProcessusFactice()
        self.appels: list[tuple[list[str], dict[str, Any]]] = []
        self.message = message

    def __call__(self, commande: list[str], **options: Any) -> _ProcessusFactice:
        self.appels.append((commande, options))
        erreurs: IO[bytes] = options["stderr"]
        erreurs.write(self.message.encode("utf-8"))
        return self.processus

    @property
    def erreurs(self) -> IO[bytes]:
        fichier: IO[bytes] = self.appels[-1][1]["stderr"]
        return fichier


def _installer(monkeypatch: pytest.MonkeyPatch, lanceur: Any) -> None:
    monkeypatch.setattr(
        lancement,
        "lancer_chaine",
        partial(lancement.lancer_chaine, popen=cast(lancement.Lanceur, lanceur)),
    )


def _ligne(etape: Etape, statut: StatutEtape) -> str:
    instant = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)
    evenement = EvenementProgression(
        passage_id="20261012T073000Z-aaaaaa", etape=etape, statut=statut, horodatage=instant
    )
    return evenement.model_dump_json() + "\n"


def test_lancement_et_progression(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur("Erreur : étape kpi en échec")
    _installer(monkeypatch, lanceur)
    ancien = tmp_path / "sorties" / "progression" / "20261008T070000Z-111111.jsonl"
    ancien.parent.mkdir(parents=True)
    ancien.write_text(_ligne(Etape.extraction, StatutEtape.echouee), encoding="utf-8")

    page = _page()
    page.button[0].click().run()
    assert not page.exception
    ((commande, options),) = lanceur.appels
    assert commande[1:] == ["-m", "usine", "rapport"]
    assert options["cwd"] == tmp_path
    assert page.button[0].disabled
    assert "**extraction** : En attente" in _textes(page)

    nouveau = ancien.with_name("20261012T073000Z-aaaaaa.jsonl")
    nouveau.write_text(
        _ligne(Etape.extraction, StatutEtape.en_cours)
        + _ligne(Etape.extraction, StatutEtape.reussie)
        + _ligne(Etape.instantanes, StatutEtape.en_cours)
        + '{"partielle',
        encoding="utf-8",
    )
    page.run()
    textes = _textes(page)
    assert "**extraction** : Réussie" in textes
    assert "**instantanes** : En cours" in textes
    assert "**kpi** : En attente" in textes

    lanceur.processus.code = 1
    page.run()
    assert not page.exception
    assert "étape kpi en échec" in page.error[0].value
    assert not page.button[0].disabled
    assert lanceur.erreurs.closed


def test_lancement_succes(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)
    lanceur = _Lanceur()
    lanceur.processus.code = 0
    _installer(monkeypatch, lanceur)
    page = _page()
    page.button[0].click().run()
    assert not page.exception
    assert "Chaîne terminée" in page.success[0].value
    assert list(page.table[0].value["Entité"]) == ["ENT-A", "ENT-B"]
    assert lanceur.erreurs.closed
    page.run()
    assert not page.exception
    assert len(lanceur.appels) == 1


def test_rerun_unique_en_fin_de_chaine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur()
    _installer(monkeypatch, lanceur)
    page = _page()
    page.button[0].click().run()
    assert "Chaîne en cours" in page.info[-1].value
    relances: list[object] = []
    monkeypatch.setattr(streamlit, "rerun", lambda *args, **kwargs: relances.append(args))
    lanceur.processus.code = 0
    page.run()
    assert len(relances) == 1
    page.run()
    assert len(relances) == 1


def test_erreur_tronquee(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur("".join(f"trace {n:02d}\n" for n in range(30)))
    lanceur.processus.code = 1
    _installer(monkeypatch, lanceur)
    page = _page()
    page.button[0].click().run()
    message = page.error[0].value
    assert "trace 29" in message
    assert "trace 10" in message
    assert "trace 09" not in message


def test_progression_invalide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur()
    _installer(monkeypatch, lanceur)
    page = _page()
    page.button[0].click().run()
    fichier = tmp_path / "sorties" / "progression" / "20261012T073000Z-aaaaaa.jsonl"
    fichier.parent.mkdir(parents=True)
    fichier.write_text('{"etape": "inconnue"}\n', encoding="utf-8")
    page.run()
    assert not page.exception
    assert any(fichier.name in erreur.value and "ligne 1" in erreur.value for erreur in page.error)


def test_pas_de_second_lancement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    lanceur = _Lanceur()
    _installer(monkeypatch, lanceur)
    page = _page()  # bouton encore actif dans cet onglet périmé
    page.session_state["processus"] = _ProcessusFactice()  # Chaîne déjà en cours
    page.session_state["racine_lancement"] = tmp_path
    page.session_state["fichiers_avant"] = frozenset()
    page.button[0].click().run()
    assert not page.exception
    assert lanceur.appels == []


def test_lancement_impossible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    def popen(commande: list[str], **_options: Any) -> Any:
        raise FileNotFoundError(2, "répertoire introuvable", str(tmp_path / "absent"))

    _installer(monkeypatch, popen)
    page = _page()
    page.button[0].click().run()
    assert not page.exception
    assert "Lancement de la Chaîne impossible" in page.error[0].value
    assert not page.button[0].disabled


def test_ui_sans_acces_interdit() -> None:
    interdits = ("entrepot.duckdb", ".en-cours", "duckdb")
    for chemin in sorted(REPERTOIRE_UI.glob("*.py")):
        texte = chemin.read_text(encoding="utf-8")
        assert [m for m in interdits if m in texte] == [], chemin.name
