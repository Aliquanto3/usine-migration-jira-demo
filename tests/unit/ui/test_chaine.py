"""Lancement de la Chaîne et bouton de mode de l'UI web (Story 7.15, AD-8, AD-19, AD-25).

Aucune vraie Chaîne ni Jira : le sous-processus est une doublure injectée (`popen`) et la
progression un fichier synthétique de `sorties/progression/`.
"""

import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from tests.unit.ui.test_avant_apres import manifeste
from usine.contrats.passage import Etape, EvenementProgression, ManifestePassage, StatutEtape
from usine.ui import app, textes
from usine.ui.chaine import (
    MOTIF_LANCEMENT_EN_COURS,
    MOTIF_MODE_EN_COURS,
    MOTIF_RACINE,
    GestionChaine,
)
from usine.ui.cli import lecture_manifeste
from usine.ui.progression import AUCUN_RAPPORT
from usine.ui.serveur import HOTE, REPERTOIRE_STATIQUE, creer_application
from usine.ui.textes import LIGNES_ERREUR_MAX, REPLI_ABSENT

PASSAGE = "20261012T073000Z-aaaaaa"
INSTANT = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)


class Processus:
    """Doublure de `subprocess.Popen` : tourne tant que `code` est `None`."""

    def __init__(self, stderr: Any, sortie_erreur: bytes) -> None:
        self.code: int | None = None
        stderr.write(sortie_erreur)
        stderr.flush()

    def poll(self) -> int | None:
        return self.code


class Lanceur:
    """Doublure de `subprocess.Popen` injectée dans `GestionChaine`."""

    def __init__(self) -> None:
        self.appels: list[tuple[list[str], dict[str, Any]]] = []
        self.processus: Processus | None = None
        self.sortie_erreur = b""

    def __call__(self, commande: list[str], **options: Any) -> Processus:
        self.appels.append((commande, options))
        self.processus = Processus(options["stderr"], self.sortie_erreur)
        return self.processus

    def finir(self, code: int) -> None:
        assert self.processus is not None
        self.processus.code = code


def _evenement(etape: Etape, statut: StatutEtape, secondes: float = 0.0) -> str:
    instant = INSTANT + timedelta(seconds=secondes)
    return EvenementProgression(
        passage_id=PASSAGE, etape=etape, statut=statut, horodatage=instant
    ).model_dump_json()


def ecrire_progression(racine: Path, *lignes: str, partielle: str = "") -> Path:
    repertoire = racine / "sorties" / "progression"
    repertoire.mkdir(parents=True, exist_ok=True)
    chemin = repertoire / f"{PASSAGE}.jsonl"
    chemin.write_text("".join(f"{ligne}\n" for ligne in lignes) + partielle, encoding="utf-8")
    return chemin


class Banc:
    """Application, doublure de lanceur et racine d'essai."""

    def __init__(
        self,
        racine: Path | None,
        *,
        repli: bool = False,
        passage: ManifestePassage | None = None,
        lecteur: Any = None,
    ) -> None:
        self.lanceur = Lanceur()
        self.lectures: list[bool] = []

        def lire_manifeste(mode_repli: bool) -> ManifestePassage | None:
            self.lectures.append(mode_repli)
            return lecteur(mode_repli) if lecteur is not None else passage

        self.application = creer_application(
            repli=repli,
            lire_manifeste=lire_manifeste,
            lire_consultation=lambda _repli: None,
            chaine=GestionChaine(racine, popen=cast(Any, self.lanceur)),
        )
        self.http = TestClient(self.application, base_url=f"http://{HOTE}")

    def etat(self) -> dict[str, Any]:
        reponse = self.http.get("/api/chaine")
        assert reponse.status_code == 200
        donnees: dict[str, Any] = reponse.json()
        return donnees

    def lancer(self) -> Any:
        return self.http.post("/api/chaine")

    def mode(self, mode: str) -> Any:
        return self.http.post("/api/mode", json={"mode": mode})


@pytest.fixture
def racine(tmp_path: Path) -> Path:
    return tmp_path


def test_etat_initial(racine: Path) -> None:
    vue = Banc(racine, passage=manifeste()).etat()
    assert vue["statut"] == "attente"
    assert vue["en_cours"] is False
    assert [etape["nom"] for etape in vue["etapes"]] == [etape.value for etape in Etape]
    assert {etape["etat"] for etape in vue["etapes"]} == {"en_attente"}
    assert vue["compteur"] == "0 / 10"
    assert vue["terminees"] == 0
    assert vue["annonce"] == ""
    assert vue["intervalle_ms"] == round(textes.INTERVALLE_SONDAGE * 1000)
    assert vue["bouton_lancement"] == {
        "libelle": "Lancer la Chaîne",
        "bloque": False,
        "motif": None,
    }
    assert vue["bouton_mode"]["libelle"] == "Passer en Mode repli"
    assert vue["bouton_mode"]["bloque"] is False
    assert vue["mode_cible"] == "repli"
    assert vue["journal"] == []
    assert vue["bandeau"] is None
    assert vue["dernier_passage"]["lignes"][-1] == f"Passage {manifeste().passage_id}"


def test_dernier_passage_absent(racine: Path) -> None:
    vue = Banc(racine).etat()
    assert vue["dernier_passage"] is None
    assert vue["message_dernier_passage"]


def test_lancement_demarre_usine_rapport_en_sous_processus(racine: Path) -> None:
    banc = Banc(racine)
    reponse = banc.lancer()
    assert reponse.status_code == 202
    ((commande, options),) = banc.lanceur.appels
    assert commande == [sys.executable, "-m", "usine", "rapport"]
    assert options["cwd"] == racine
    vue = reponse.json()
    assert vue["statut"] == "en_cours"
    assert vue["en_cours"] is True
    assert vue["bouton_lancement"] == {
        "libelle": "Chaîne en cours…",
        "bloque": True,
        "motif": MOTIF_LANCEMENT_EN_COURS,
    }
    assert vue["bouton_mode"]["bloque"] is True
    assert vue["bouton_mode"]["motif"] == MOTIF_MODE_EN_COURS
    assert vue["annonce"] == "Chaîne en cours…"


def test_une_chaine_a_la_fois(racine: Path) -> None:
    banc = Banc(racine)
    assert banc.lancer().status_code == 202
    second = banc.lancer()
    assert second.status_code == 409
    assert second.json()["detail"] == MOTIF_LANCEMENT_EN_COURS
    assert len(banc.lanceur.appels) == 1
    assert banc.etat()["en_cours"] is True


def test_reprise_du_suivi_en_revenant_sur_la_page(racine: Path) -> None:
    banc = Banc(racine)
    banc.lancer()
    ecrire_progression(racine, _evenement(Etape.extraction, StatutEtape.en_cours))
    # « Quitter puis rouvrir /chaine » : un nouvel appel retrouve l'état, boutons bloqués.
    vue = banc.etat()
    assert vue["statut"] == "en_cours"
    assert vue["bouton_lancement"]["bloque"] is True
    assert vue["bouton_mode"]["bloque"] is True
    assert vue["etapes"][0]["etat"] == "en_cours"


def test_progression_etapes_barre_annonce_et_journal(racine: Path) -> None:
    banc = Banc(racine)
    banc.lancer()
    ecrire_progression(
        racine,
        _evenement(Etape.extraction, StatutEtape.en_cours, 0),
        _evenement(Etape.extraction, StatutEtape.reussie, 0.5),
        _evenement(Etape.instantanes, StatutEtape.en_cours, 0.6),
        partielle='{"passage_id": "tronqu',  # ligne en cours d'écriture : ignorée
    )
    vue = banc.etat()
    assert [etape["etat"] for etape in vue["etapes"][:3]] == ["reussie", "en_cours", "en_attente"]
    assert vue["etapes"][0]["libelle_etat"] == "Réussie"
    assert vue["etapes"][0]["duree"] == "0,5 s"
    assert vue["etapes"][1]["duree"] is None
    assert vue["terminees"] == 1
    assert vue["compteur"] == "1 / 10"
    assert vue["total"] == 10
    assert vue["annonce"] == "Étape 2 sur 10 : instantanes"
    assert [ligne["texte"] for ligne in vue["journal"]] == [
        "instantanes : En cours",
        "extraction : Réussie",
        "extraction : En cours",
    ]
    assert vue["journal"][0]["horodatage"] == "07:30:00"
    # Même progression au sondage suivant : même annonce (le script ne la répète pas).
    assert banc.etat()["annonce"] == vue["annonce"]


def test_entre_deux_etapes_rien_a_annoncer(racine: Path) -> None:
    banc = Banc(racine)
    banc.lancer()
    ecrire_progression(
        racine,
        _evenement(Etape.extraction, StatutEtape.en_cours),
        _evenement(Etape.extraction, StatutEtape.reussie, 1),
    )
    assert banc.etat()["annonce"] == ""


def test_fin_de_chaine_reussie(racine: Path) -> None:
    banc = Banc(racine)
    banc.lancer()
    ecrire_progression(
        racine,
        *[
            ligne
            for rang, etape in enumerate(Etape)
            for ligne in (
                _evenement(etape, StatutEtape.en_cours, rang),
                _evenement(etape, StatutEtape.reussie, rang + 0.5),
            )
        ],
    )
    banc.lanceur.finir(0)
    vue = banc.etat()
    assert vue["statut"] == "terminee"
    assert vue["en_cours"] is False
    assert vue["terminees"] == 10
    assert vue["annonce"] == "Chaîne terminée : Passage publié."
    assert vue["bandeau"]["variante"] == "succes"
    assert vue["bandeau"]["texte"] == "Chaîne terminée : Passage publié."
    assert vue["bandeau"]["lien"] == {"libelle": "Voir la carte météo", "url": "/"}
    assert vue["bouton_lancement"] == {
        "libelle": "Relancer la Chaîne",
        "bloque": False,
        "motif": None,
    }
    assert vue["bouton_mode"]["bloque"] is False


def test_echec_etape_code_et_vingt_lignes(racine: Path) -> None:
    banc = Banc(racine, passage=manifeste())
    banc.lanceur.sortie_erreur = "\n".join(f"ligne {n}" for n in range(1, 31)).encode()
    banc.lancer()
    ecrire_progression(
        racine,
        _evenement(Etape.extraction, StatutEtape.en_cours),
        _evenement(Etape.extraction, StatutEtape.echouee, 1),
    )
    cadre_avant = banc.http.get("/api/cadre").json()
    banc.lanceur.finir(3)
    vue = banc.etat()
    assert vue["statut"] == "echec"
    assert vue["etapes"][0]["etat"] == "echouee"
    assert vue["etapes"][0]["libelle_etat"] == "Échec"
    bandeau = vue["bandeau"]
    assert bandeau["variante"] == "erreur"
    assert bandeau["texte"] == "Échec de la Chaîne à l'étape « extraction » (code 3)."
    assert len(bandeau["lignes"]) == LIGNES_ERREUR_MAX == 20
    assert bandeau["lignes"][0] == "ligne 11"
    assert bandeau["lignes"][-1] == "ligne 30"
    assert bandeau["complement"] == AUCUN_RAPPORT
    assert vue["annonce"] == "Échec de la Chaîne à l'étape « extraction »."
    assert vue["bouton_lancement"]["libelle"] == "Relancer la Chaîne"
    # Le Passage affiché ailleurs ne change pas.
    assert banc.http.get("/api/cadre").json() == cadre_avant
    # La lecture est unique : un second sondage donne le même bandeau.
    assert banc.etat()["bandeau"] == bandeau


def test_echec_hors_etape_sans_message(racine: Path) -> None:
    banc = Banc(racine)
    banc.lancer()
    banc.lanceur.finir(1)
    bandeau = banc.etat()["bandeau"]
    assert bandeau["texte"] == "Échec de la Chaîne hors d'une étape (code 1)."
    assert bandeau["lignes"] == ["aucun message"]


def test_relancer_apres_la_fin(racine: Path) -> None:
    banc = Banc(racine)
    banc.lancer()
    banc.lanceur.finir(1)
    assert banc.etat()["statut"] == "echec"
    assert banc.lancer().status_code == 202
    assert len(banc.lanceur.appels) == 2
    vue = banc.etat()
    assert vue["statut"] == "en_cours"
    assert vue["bandeau"] is None


def test_progression_illisible_signalee_sans_arret(racine: Path) -> None:
    banc = Banc(racine)
    banc.lancer()
    ecrire_progression(racine, "pas du json")
    vue = banc.etat()
    assert vue["en_cours"] is True
    assert "progression invalide" in vue["erreur"]
    assert {etape["etat"] for etape in vue["etapes"]} == {"en_attente"}


def test_demarrage_impossible(racine: Path) -> None:

    def echec(*_args: Any, **_options: Any) -> Processus:
        raise OSError("introuvable")

    gestion = GestionChaine(racine, popen=cast(Any, echec))
    gestion.lancer(False)
    vue = gestion.vue(False, None)
    assert vue.statut == "attente"
    assert vue.erreur == "Lancement de la Chaîne impossible : introuvable"
    assert vue.bouton_lancement.bloque is False


def test_racine_absente_bloque_le_lancement(tmp_path: Path) -> None:
    for racine_absente in (None, tmp_path / "absente"):
        banc = Banc(racine_absente)
        vue = banc.etat()
        assert vue["bouton_lancement"]["bloque"] is True
        assert vue["bouton_lancement"]["motif"] == MOTIF_RACINE
        assert banc.lancer().status_code == 409
        assert banc.lanceur.appels == []


def test_lancement_refuse_en_mode_repli(racine: Path) -> None:
    banc = Banc(racine, repli=True)
    vue = banc.etat()
    assert vue["bouton_lancement"]["bloque"] is True
    assert vue["bouton_lancement"]["motif"] == textes.LANCEMENT_REPLI.replace("`", "")
    assert vue["bouton_mode"] == {"libelle": "Revenir au Mode réel", "bloque": False, "motif": None}
    assert vue["mode_cible"] == "reel"
    assert banc.lancer().status_code == 409
    assert banc.lanceur.appels == []


# --- bouton de mode ---


def test_bascule_repli_reel_repli(racine: Path) -> None:
    banc = Banc(racine, passage=manifeste())
    assert banc.http.get("/api/cadre").json()["mode"] == "reel"
    repli = banc.mode("repli")
    assert repli.status_code == 200
    assert repli.json()["mode"] == "repli"
    assert repli.json()["bandeau_repli_html"]
    assert banc.http.get("/api/cadre").json()["mode"] == "repli"
    assert banc.lectures[-1] is True  # tous les écrans lisent maintenant le Passage enregistré
    assert banc.etat()["bouton_mode"]["libelle"] == "Revenir au Mode réel"
    reel = banc.mode("reel")
    assert reel.json()["mode"] == "reel"
    assert reel.json()["bandeau_repli_html"] is None
    assert banc.lectures[-1] is False
    assert banc.mode("repli").json()["mode"] == "repli"


def test_bascule_est_idempotente_et_jamais_automatique(racine: Path) -> None:
    banc = Banc(racine)
    banc.http.get("/api/chaine")
    banc.http.get("/api/cadre")
    assert set(banc.lectures) == {False}
    assert banc.mode("reel").json()["mode"] == "reel"
    assert banc.mode("reel").json()["mode"] == "reel"


def test_bascule_refusee_pendant_une_chaine(racine: Path) -> None:
    banc = Banc(racine)
    banc.lancer()
    reponse = banc.mode("repli")
    assert reponse.status_code == 409
    assert reponse.json()["detail"] == MOTIF_MODE_EN_COURS
    assert banc.http.get("/api/cadre").json()["mode"] == "reel"
    banc.lanceur.finir(0)
    assert banc.mode("repli").status_code == 200


@pytest.mark.parametrize("corps", [{"mode": "autre"}, {}, {"mode": "repli", "x": 1}])
def test_bascule_corps_invalide(racine: Path, corps: dict[str, Any]) -> None:
    banc = Banc(racine)
    assert banc.http.post("/api/mode", json=corps).status_code == 422
    assert banc.http.post("/api/mode").status_code == 422
    assert banc.http.get("/api/cadre").json()["mode"] == "reel"


def test_repli_absent_affiche_la_cause(tmp_path: Path) -> None:
    http = TestClient(
        creer_application(
            repli=False,
            lire_manifeste=lecture_manifeste(tmp_path),
            lire_consultation=lambda _repli: None,
            chaine=GestionChaine(tmp_path),
        ),
        base_url=f"http://{HOTE}",
    )
    cadre = http.post("/api/mode", json={"mode": "repli"}).json()
    assert cadre["mode"] == "repli"
    assert cadre["erreur"] == REPLI_ABSENT
    assert cadre["passage_publie"] is None
    # Le bouton de mode reste accessible pour revenir au Mode réel.
    vue = http.get("/api/chaine").json()
    assert vue["bouton_mode"]["bloque"] is False
    assert http.post("/api/mode", json={"mode": "reel"}).json()["erreur"] is None


def test_ecritures_refusees_depuis_une_autre_origine(racine: Path) -> None:
    banc = Banc(racine)
    etranger = {"Origin": "http://exemple.invalid"}
    assert banc.http.post("/api/chaine", headers=etranger).status_code == 403
    assert banc.http.post("/api/mode", json={"mode": "repli"}, headers=etranger).status_code == 403
    local = {"Origin": f"http://{HOTE}"}
    assert banc.http.post("/api/mode", json={"mode": "repli"}, headers=local).status_code == 200
    assert banc.lanceur.appels == []


def test_seules_deux_routes_post_changent_un_etat(racine: Path) -> None:
    application = Banc(racine).application
    ecritures = {
        (getattr(route, "path", ""), methode)
        for route in application.routes
        for methode in getattr(route, "methods", None) or ()
        if methode not in ("GET", "HEAD")
    }
    assert ecritures == {("/api/chaine", "POST"), ("/api/mode", "POST")}


# --- page, constantes ---


def test_page_chaine_boutons_barre_et_region_status() -> None:
    page = (REPERTOIRE_STATIQUE / "chaine.html").read_text(encoding="utf-8")
    assert re.search(r'<button[^>]*id="bouton-lancement"', page)
    assert re.search(r'<button[^>]*id="bouton-mode"', page)
    assert 'role="progressbar"' in page
    assert 'aria-valuemax="10"' in page
    assert 'id="annonce" role="status"' in page
    assert "/statique/chaine.js" in page
    assert "http://" not in page and "https://" not in page


def test_script_sans_innerhtml_ni_ressource_externe() -> None:
    script = (REPERTOIRE_STATIQUE / "chaine.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script
    assert "http://" not in script and "https://" not in script
    assert "aria-describedby" in script and "aria-disabled" in script


def test_constantes_communes_avec_streamlit() -> None:
    assert app.INTERVALLE_SONDAGE is textes.INTERVALLE_SONDAGE
    assert app.LIGNES_ERREUR_MAX is textes.LIGNES_ERREUR_MAX
    assert app.LANCEMENT_REPLI is textes.LANCEMENT_REPLI
    assert app.REPLI_ABSENT is textes.REPLI_ABSENT
