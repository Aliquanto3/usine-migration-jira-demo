"""Serveur FastAPI de l'UI web (Story 7.13) : sept pages, cadre commun, mode, ressources locales."""

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.unit.ui.test_avant_apres import manifeste
from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import ManifestePassage
from usine.ui import serveur
from usine.ui.cli import lecture_manifeste
from usine.ui.serveur import HOTE, PAGES, REPERTOIRE_STATIQUE, creer_application
from usine.ui.textes import BANDEAU_REPLI, REPLI_ABSENT

TITRES = {
    "/": "Carte météo",
    "/entites/ENT-B": "Détail d'une Entité",
    "/chaine": "Lancement de la Chaîne",
    "/agent": "Agent",
    "/avant-apres": "Avant / après",
    "/pseudonymisation": "Pseudonymisation",
    "/outillage": "Ce qu'il faut pour le faire en vrai",
}
URLS = list(TITRES)
FIN = datetime(2026, 10, 16, 19, 5, 40, tzinfo=UTC)
LIEN_NAV = r'<a class="nav-lien" href="([^"]+)"( aria-current="page")?>([^<]+)</a>'


def client(*, repli: bool = False, passage: ManifestePassage | None = None) -> TestClient:
    return TestClient(
        creer_application(repli=repli, lire_manifeste=lambda _repli: passage),
        base_url=f"http://{HOTE}",
    )


def test_hote_local() -> None:
    assert HOTE == "127.0.0.1"


def test_une_page_par_ecran() -> None:
    attendues = ["/", "/entites/{entite}", "/chaine", "/agent", "/avant-apres"]
    attendues += ["/pseudonymisation", "/outillage"]
    assert sorted(PAGES) == sorted(attendues)
    for fichier in PAGES.values():
        assert (REPERTOIRE_STATIQUE / fichier).is_file()


@pytest.mark.parametrize("url", URLS)
def test_page_cadre_commun(url: str) -> None:
    reponse = client().get(url)
    assert reponse.status_code == 200
    assert reponse.headers["content-type"].startswith("text/html")
    html = reponse.text
    assert '<html lang="fr">' in html
    assert f"<title>{TITRES[url]} · Usine de migration</title>" in html
    assert html.count("<h1") == 1
    assert f'<h1 id="titre-ecran" tabindex="-1">{TITRES[url]}</h1>' in html
    assert 'class="lien-evitement" href="#titre-ecran"' in html
    assert html.count('aria-current="page"') == 1
    assert 'id="pastille-mode"' in html
    assert 'id="pastille-passage"' in html
    assert 'id="bandeaux"' in html
    assert "Chargement" not in html


@pytest.mark.parametrize("url", URLS)
def test_navigation_active_et_sept_liens(url: str) -> None:
    liens = re.findall(LIEN_NAV, client().get(url).text)
    assert [libelle for _, _, libelle in liens] == list(TITRES.values())
    assert [libelle for _, courant, libelle in liens if courant] == [TITRES[url]]


def test_bouton_lancer_la_chaine_absent_de_chaine() -> None:
    bouton = 'class="bouton-entete" href="/chaine">Lancer la Chaîne</a>'
    assert bouton not in client().get("/chaine").text
    for url in URLS:
        if url != "/chaine":
            assert bouton in client().get(url).text


def test_mention_de_donnees_sur_la_carte_seulement() -> None:
    mention = "Données fictives ou publiques."
    assert mention in client().get("/").text
    assert mention not in client().get("/agent").text


@pytest.mark.parametrize("url", URLS)
def test_ressources_locales_seulement(url: str) -> None:
    html = client().get(url).text
    assert re.findall(r"(?:src|href|action)=\"(?:https?:)?//", html) == []
    assert "http://" not in html
    assert "https://" not in html
    chemins = re.findall(r'(?:src|href)="(/statique/[^"]+)"', html)
    assert chemins
    for chemin in chemins:
        assert client().get(chemin).status_code == 200


def test_feuille_et_script_sans_requete_externe() -> None:
    for nom in ("cadre.css", "cadre.js"):
        texte = client().get(f"/statique/{nom}").text
        assert "http://" not in texte
        assert "https://" not in texte
        assert "@import" not in texte
    css = client().get("/statique/cadre.css").text
    polices = re.findall(r'url\("(polices/[^"]+)"\)', css)
    assert len(polices) == 5
    for police in polices:
        reponse = client().get(f"/statique/{police}")
        assert reponse.status_code == 200
        assert reponse.content[:4] == b"wOF2"


def test_polices_et_licences_ofl() -> None:
    dossier = REPERTOIRE_STATIQUE / "polices"
    for nom in ("Fredoka", "AtkinsonHyperlegible", "JetBrainsMono"):
        licence = (dossier / f"OFL-{nom}.txt").read_text(encoding="utf-8")
        assert "SIL OPEN FONT LICENSE" in licence


def test_script_message_serveur_injoignable() -> None:
    script = client().get("/statique/cadre.js").text
    assert "L'interface ne joint plus le serveur. Relancer usine ui." in script


def test_documentation_automatique_absente() -> None:
    assert client().get("/inconnue").status_code == 404
    assert client().get("/docs").status_code == 404
    assert client().get("/openapi.json").status_code == 404


def test_cadre_mode_reel_avec_passage() -> None:
    passage = manifeste(secondes=0, debut=FIN)
    assert client(passage=passage).get("/api/cadre").json() == {
        "mode": "reel",
        "libelle_mode": "Mode réel",
        "bandeau_repli_html": None,
        "passage_publie": "Passage publié · 16/10/2026 19:05 UTC",
        "erreur": None,
    }


def test_cadre_sans_passage() -> None:
    vue = client().get("/api/cadre").json()
    assert vue["passage_publie"] is None
    assert vue["erreur"] is None


def test_cadre_mode_repli() -> None:
    vue = client(repli=True).get("/api/cadre").json()
    assert vue["mode"] == "repli"
    assert vue["libelle_mode"] == "Mode repli"
    html = vue["bandeau_repli_html"]
    assert html.startswith("<strong>Mode repli</strong>")
    assert "<code>demo/repli/passage/</code>" in html
    assert BANDEAU_REPLI.startswith("**Mode repli**")


def test_cadre_lecture_impossible() -> None:
    def lire(_repli: bool) -> ManifestePassage | None:
        raise UsineErreur("manifeste illisible")

    vue = TestClient(creer_application(repli=False, lire_manifeste=lire)).get("/api/cadre").json()
    assert vue["erreur"] == "manifeste illisible"
    assert vue["passage_publie"] is None
    assert vue["mode"] == "reel"


def test_le_mode_ne_change_jamais_seul() -> None:
    appels: list[bool] = []

    def lire(repli: bool) -> ManifestePassage | None:
        appels.append(repli)
        raise UsineErreur("illisible")

    http = TestClient(creer_application(repli=False, lire_manifeste=lire))
    assert http.get("/api/cadre").json()["mode"] == "reel"
    assert http.get("/api/cadre").json()["mode"] == "reel"
    assert appels == [False, False]


def test_serveur_seul_module_qui_cree_l_application() -> None:
    racine = Path(serveur.__file__).parent
    createurs = [
        chemin.name
        for chemin in racine.glob("*.py")
        if re.search(r"\bFastAPI\(", chemin.read_text(encoding="utf-8"))
    ]
    assert createurs == ["serveur.py"]


# Lecture réelle par les services de `ui/cli.py`.


def test_lecture_dernier_passage(racine_publiee: Path) -> None:
    lu = lecture_manifeste(racine_publiee)(False)
    assert lu is not None
    assert lu.date_arrete.isoformat() == "2026-10-09"


def test_lecture_sans_passage(tmp_path: Path) -> None:
    assert lecture_manifeste(tmp_path)(False) is None


def test_lecture_repli(racine_publiee: Path) -> None:
    lu = lecture_manifeste(racine_publiee)(True)
    assert lu is not None
    assert lu.passage_id == "20261012T221158Z-96c621"


def test_lecture_repli_absent(tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match="introuvable"):
        lecture_manifeste(tmp_path)(True)
    application = creer_application(repli=True, lire_manifeste=lecture_manifeste(tmp_path))
    vue = TestClient(application).get("/api/cadre").json()
    assert vue["erreur"] == REPLI_ABSENT
    assert vue["mode"] == "repli"


def test_cadre_repertoire_illisible() -> None:
    def lire(_repli: bool) -> ManifestePassage | None:
        raise PermissionError(13, "accès refusé", "sorties/passages")

    reponse = TestClient(creer_application(repli=False, lire_manifeste=lire)).get("/api/cadre")
    assert reponse.status_code == 200
    assert reponse.json()["erreur"].startswith("Lecture du Passage impossible")


def test_cadre_heure_convertie_en_utc() -> None:
    from datetime import timedelta, timezone

    paris = datetime(2026, 10, 16, 21, 5, tzinfo=timezone(timedelta(hours=2)))
    passage = manifeste(secondes=0, debut=paris)
    vue = client(passage=passage).get("/api/cadre").json()
    assert vue["passage_publie"] == "Passage publié · 16/10/2026 19:05 UTC"
