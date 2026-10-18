"""Outil `outils/controle_repetition.py` (Story 7.12) : DOM, Edge, rapport, sans serveur."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from outils import controle_repetition as controle
from outils.controle_repetition import (
    ControleImpossible,
    Resultat,
    analyser_dom,
    compte_rendu,
    trouver_msedge,
    verifier_livrables,
)

DEPOT = Path(__file__).resolve().parents[3]


CARTE = "<div id='bloc-carte'><table><tr data-meteo='vert'><th>ENT-A</th></tr></table></div>"


def _page(corps: str) -> str:
    return f"<html><body><h1>Titre</h1><div id='bandeaux'>{corps}</div></body></html>"


def test_dom_complet() -> None:
    dom = _page(
        "<div id='bloc-carte'><table><tbody><tr data-meteo='vert'><th>ENT-A</th></tr></tbody>"
        "</table></div><section id='bloc-message' hidden>x</section>"
    )
    assert analyser_dom("/", dom) == []


def test_dom_chargement_encore_affiche() -> None:
    dom = _page("<div id='bloc-carte'>Chargement…</div>")
    assert any("Chargement" in a for a in analyser_dom("/", dom))


def test_dom_bandeau_erreur_visible_nomme_le_texte() -> None:
    dom = _page(
        "<p class='bandeau bandeau--erreur' id='bandeau-erreur'>Lecture <b>impossible</b></p>"
        + CARTE
    )
    anomalies = analyser_dom("/", dom)
    assert anomalies == ["bandeau d'erreur : Lecture impossible"]


def test_dom_bandeau_erreur_masque_ignore() -> None:
    dom = _page("<p class='bandeau bandeau--erreur' hidden>x</p>" + CARTE)
    assert analyser_dom("/", dom) == []


def test_dom_bandeau_repli_n_est_pas_une_erreur() -> None:
    dom = _page("<p class='bandeau bandeau--repli'>Mode repli</p>" + CARTE)
    assert analyser_dom("/", dom) == []


def test_dom_message_d_absence_et_bloc_masque() -> None:
    dom = _page("<section id='bloc-message'><p id='message'>Aucun Passage</p></section>")
    anomalies = analyser_dom("/", dom)
    assert any("Aucun Passage" in a for a in anomalies)
    assert any("bloc principal masqué" in a for a in anomalies)


def test_dom_carte_sans_ligne_d_entite() -> None:
    dom = _page("<div id='bloc-carte'><table><tbody></tbody></table></div>")
    assert analyser_dom("/", dom) == ["carte sans aucune ligne d'Entité"]


def test_dom_avant_apres_exige_la_duree_de_chaine() -> None:
    sans = _page("<div id='bloc-avant-apres'><section id='carte-chaine'><p id='valeur-chaine'>")
    avec = _page(
        "<div id='bloc-avant-apres'><section id='carte-chaine'>"
        "<p id='valeur-chaine'>4 min</p></section></div>"
    )
    assert analyser_dom("/avant-apres", sans) == ["Avant / après sans durée de la Chaîne"]
    assert analyser_dom("/avant-apres", avec) == []


def test_dom_pseudonymisation_exige_les_panneaux() -> None:
    sans = _page("<div id='bloc-pseudo'><div id='panneaux' hidden>x</div></div>")
    avec = _page("<div id='bloc-pseudo'><div id='panneaux'>x</div></div>")
    assert any("masqué" in a for a in analyser_dom("/pseudonymisation", sans))
    assert analyser_dom("/pseudonymisation", avec) == []


def test_fin_journal() -> None:
    import io

    assert controle.fin_journal(io.BytesIO(b"")) == ""
    texte = controle.fin_journal(io.BytesIO(b"un\ndeux\ntrois\n"), lignes=2)
    assert "deux" in texte
    assert "trois" in texte
    assert "un" not in texte.split("deux")[0].replace("usine", "")


def test_dom_script_ignore() -> None:
    dom = _page("<script>var t='Chargement…'</script>" + CARTE)
    assert analyser_dom("/", dom) == []


def test_dom_outillage_fiche_vide_et_remplie() -> None:
    assert "fiche vide" in analyser_dom("/outillage", _page("<div id='fiche'></div>"))
    assert analyser_dom("/outillage", _page("<div id='fiche'><p>Cartes</p></div>")) == []


def test_msedge_option_path_puis_emplacements() -> None:
    assert trouver_msedge("X.exe", existe=lambda c: True) == "X.exe"
    with pytest.raises(ControleImpossible):
        trouver_msedge("X.exe", existe=lambda c: False)
    assert trouver_msedge(chercher_path=lambda n: "C:/p/msedge.exe") == "C:/p/msedge.exe"
    emplacement = controle.MSEDGE_EMPLACEMENTS[1]
    assert trouver_msedge(chercher_path=lambda n: None, existe=lambda c: c == emplacement) == (
        emplacement
    )


def test_msedge_absent_message_clair() -> None:
    with pytest.raises(ControleImpossible, match="Edge"):
        trouver_msedge(chercher_path=lambda n: None, existe=lambda c: False)


def test_main_edge_absent_code_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:

    def absent(chemin: str | None = None) -> str:
        raise ControleImpossible("Edge introuvable")

    monkeypatch.setattr(controle, "trouver_msedge", absent)
    assert controle.main(["--racine", "."]) == 2
    assert "Edge introuvable" in capsys.readouterr().err


def test_commande_edge() -> None:
    commande = controle.commande_edge("msedge", "http://127.0.0.1:1/", Path("p"))
    assert commande[0] == "msedge"
    assert "--headless" in commande
    assert "--virtual-time-budget=5000" in commande
    assert commande[-2:] == ["--dump-dom", "http://127.0.0.1:1/"]


def test_ecrans_sont_les_sept_routes_du_serveur() -> None:
    from usine.ui.serveur import PAGES

    routes = {route.replace("{entite}", "ENT-A") for route in PAGES}
    assert {route for _, route in controle.ECRANS} == routes


def _ouvrir(reponses: dict[str, tuple[int, dict[str, str], bytes]]):  # type: ignore[no-untyped-def]
    return lambda url: reponses[url.removeprefix("http://h")]


def test_livrables_ok_et_ko() -> None:
    carte = (
        b'{"livrables": [{"fichier": "a.xlsx", "url": "/livrables/rapport_xlsx"},'
        b' {"fichier": "b.pptx", "url": "/livrables/rapport_pptx"},'
        b' {"fichier": "c", "url": null}]}'
    )
    ouvrir = _ouvrir(
        {
            "/api/carte": (200, {}, carte),
            "/livrables/rapport_xlsx": (
                200,
                {"content-disposition": 'attachment; filename="a"'},
                b"x",
            ),
            "/livrables/rapport_pptx": (200, {}, b""),
        }
    )
    ok, ko = verifier_livrables("http://h", ouvrir)
    assert ok.ok
    assert not ko.ok
    assert "attachment" in ko.detail
    assert "corps vide" in ko.detail


def test_livrables_aucun_disponible() -> None:
    ouvrir = _ouvrir({"/api/carte": (200, {}, b'{"livrables": []}')})
    (resultat,) = verifier_livrables("http://h", ouvrir)
    assert not resultat.ok


def test_compte_rendu() -> None:
    texte = compte_rendu([Resultat("a", True, "bien"), Resultat("b", False, "mal")])
    assert "[OK] a : bien" in texte
    assert "[KO] b : mal" in texte
    assert "1 point(s) en échec" in texte
    assert "prêt pour la répétition" in compte_rendu([Resultat("a", True, "bien")])


def test_serveur_arrete_meme_en_cas_d_erreur(monkeypatch: pytest.MonkeyPatch) -> None:
    arretes: list[object] = []
    processus = object()
    monkeypatch.setattr(controle, "trouver_msedge", lambda chemin=None: "msedge")
    monkeypatch.setattr(controle, "demarrer_serveur", lambda racine, port, journal: processus)

    def echec(base: str, proc: object) -> None:
        raise ControleImpossible("muet")

    monkeypatch.setattr(controle, "attendre_serveur", echec)
    monkeypatch.setattr(controle, "arreter_serveur", arretes.append)
    with pytest.raises(ControleImpossible):
        controle.controler(Path("."), 1234, None)
    assert arretes == [processus]


@pytest.mark.lent
@pytest.mark.skipif(
    shutil.which("msedge") is None and not Path(controle.MSEDGE_EMPLACEMENTS[0]).is_file(),
    reason="Edge absent",
)
def test_controle_reel_en_mode_repli() -> None:  # pragma: no cover - lancé par `-m lent`
    termine = subprocess.run(
        [sys.executable, "outils/controle_repetition.py", "--racine", str(DEPOT)],
        capture_output=True,
        text=True,
        check=False,
        cwd=DEPOT,
    )
    # Sans `.env` (CI), seul l'écran Pseudonymisation peut être en échec.
    assert termine.returncode in (0, 1), termine.stderr
