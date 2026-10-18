"""Contrôle avant répétition de la démo (Story 7.12) : les sept écrans et les livrables, en vrai.

Complète `outils/verifier_demo.py` (qui lit les données de la copie du Mode repli sans serveur) :
ici on démarre `usine ui` en Mode repli (sous-processus, 127.0.0.1, port libre), puis on charge
chacun des sept écrans dans Edge sans fenêtre (`msedge --headless --dump-dom`, temps virtuel de
5 s pour laisser le script de la page appeler l'API) et on vérifie sur le DOM rendu :

- aucun texte « Chargement… » ;
- aucun bandeau d'erreur visible (`bandeau--erreur` sans attribut `hidden`) ;
- le contenu de l'écran est affiché (bloc principal visible, pas de message d'absence).

Enfin il télécharge chaque livrable annoncé par `/api/carte` pour le Passage de repli (HTTP 200,
en-tête `Content-Disposition: attachment`, corps non vide). Le serveur est arrêté dans un
`finally`, même en cas d'erreur.

`outils` n'importe ni `usine.ui` ni `usine.ia` (contrat « hors produit ») : les routes sont
recopiées ici et le produit n'est lancé que comme processus.

Usage : `uv run python outils/controle_repetition.py [--racine .] [--port N] [--msedge CHEMIN]`.
La racine porte `demo/repli/` et le `.env` (`USINE_CLE_PSEUDO`, sinon l'écran Pseudonymisation
affiche un bandeau d'erreur et le contrôle l'indique). Code de sortie : 0 tout est bon, 1 au moins
un écran ou un livrable en échec, 2 contrôle impossible (Edge introuvable, serveur muet).
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

HOTE = "127.0.0.1"
DELAI_VIRTUEL_MS = 5000
"""Temps virtuel laissé à Edge pour que les scripts de la page chargent leurs données."""
DELAI_DEMARRAGE_S = 40.0
"""Attente maximale de la réponse du serveur au démarrage."""
DELAI_EDGE_S = 90.0
"""Durée maximale d'un chargement de page par Edge."""

ECRANS: tuple[tuple[str, str], ...] = (
    ("Carte météo", "/"),
    ("Détail d'une Entité", "/entites/ENT-A"),
    ("Lancement de la Chaîne", "/chaine"),
    ("Avant / après", "/avant-apres"),
    ("Pseudonymisation", "/pseudonymisation"),
    ("Agent", "/agent"),
    ("Ce qu'il faut pour le faire en vrai", "/outillage"),
)
"""Les sept écrans dans l'ordre de la navigation (même routes que `ui/serveur.PAGES`)."""

BLOCS_CONTENU: Mapping[str, tuple[str, ...]] = {
    "/": ("bloc-carte",),
    "/entites/ENT-A": ("bloc-detail",),
    "/avant-apres": ("bloc-avant-apres",),
    "/pseudonymisation": ("bloc-pseudo",),
    "/agent": ("bloc-agent",),
}
"""Bloc principal rempli par le script de chaque écran (masqué par `hidden` tant qu'il est vide)."""

TEXTE_CHARGEMENT = "chargement…"
BLOC_MESSAGE = "bloc-message"
ID_FICHE = "fiche"

MSEDGE_EMPLACEMENTS: tuple[str, ...] = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


class ControleImpossible(Exception):
    """Le contrôle ne peut pas être mené (Edge absent, serveur muet) : code de sortie 2."""


@dataclass(frozen=True)
class Resultat:
    """Bilan d'un écran ou d'un livrable."""

    nom: str
    ok: bool
    detail: str


class _AnalyseurDom(HTMLParser):
    """Relève textes, blocs visibles et bandeaux d'erreur d'un DOM rendu."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.texte: list[str] = []
        self.visibles: set[str] = set()
        self.messages: dict[str, str] = {}
        self.bandeaux: list[str] = []
        self.fiche: list[str] = []
        self._pile: list[tuple[str, str]] = []  # (balise, rôle) des éléments suivis
        self._profondeur_ignoree = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        masque = "hidden" in a
        identifiant = a.get("id") or ""
        if tag in ("script", "style"):
            self._profondeur_ignoree += 1
        if identifiant and not masque:
            self.visibles.add(identifiant)
        if "bandeau--erreur" in (a.get("class") or "").split() and not masque:
            self._pile.append((tag, "bandeau"))
            self.bandeaux.append("")
        elif identifiant == BLOC_MESSAGE and not masque:
            self._pile.append((tag, "message"))
            self.messages[identifiant] = ""
        elif identifiant == ID_FICHE:
            self._pile.append((tag, "fiche"))
        elif self._pile and tag == self._pile[-1][0]:
            self._pile.append((tag, "imbrique"))

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._profondeur_ignoree:
            self._profondeur_ignoree -= 1
        if self._pile and self._pile[-1][0] == tag:
            self._pile.pop()

    def handle_data(self, data: str) -> None:
        if self._profondeur_ignoree:
            return
        self.texte.append(data)
        for _, role in self._pile:
            if role == "bandeau" and self.bandeaux:
                self.bandeaux[-1] += data
            elif role == "message":
                self.messages[BLOC_MESSAGE] += data
            elif role == "fiche":
                self.fiche.append(data)


def analyser_dom(route: str, dom: str) -> list[str]:
    """Anomalies d'un DOM rendu ; liste vide si l'écran est complet."""
    analyseur = _AnalyseurDom()
    analyseur.feed(dom)
    analyseur.close()
    anomalies: list[str] = []
    if TEXTE_CHARGEMENT in " ".join(analyseur.texte).lower().replace("...", "…"):
        anomalies.append("texte « Chargement… » encore affiché")
    for bandeau in analyseur.bandeaux:
        anomalies.append(f"bandeau d'erreur : {' '.join(bandeau.split())[:160] or '(vide)'}")
    message = " ".join(analyseur.messages.get(BLOC_MESSAGE, "").split())
    if BLOC_MESSAGE in analyseur.visibles:
        anomalies.append(f"message à la place du contenu : {message[:160] or '(vide)'}")
    blocs = BLOCS_CONTENU.get(route)
    if blocs and not any(bloc in analyseur.visibles for bloc in blocs):
        anomalies.append("contenu non affiché (bloc principal masqué)")
    if route == "/outillage" and not "".join(analyseur.fiche).strip():
        anomalies.append("fiche vide")
    if not "".join(analyseur.texte).strip():
        anomalies.append("page vide")
    return anomalies


def trouver_msedge(
    chemin: str | None = None,
    *,
    chercher_path: Callable[[str], str | None] = shutil.which,
    existe: Callable[[str], bool] = os.path.isfile,
) -> str:
    """Chemin de `msedge` : option, puis PATH, puis emplacements Windows usuels.

    Lève `ControleImpossible` avec un message clair s'il est introuvable.
    """
    if chemin:
        if existe(chemin):
            return chemin
        raise ControleImpossible(f"Edge introuvable à l'emplacement demandé : {chemin}")
    trouve = chercher_path("msedge")
    if trouve:
        return trouve
    for emplacement in MSEDGE_EMPLACEMENTS:
        if existe(emplacement):
            return emplacement
    raise ControleImpossible(
        "Microsoft Edge (msedge) introuvable dans le PATH et aux emplacements usuels : "
        "installer Edge ou passer --msedge <chemin>."
    )


def port_libre() -> int:
    """Un port TCP libre sur 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as prise:
        prise.bind((HOTE, 0))
        return int(prise.getsockname()[1])


def commande_edge(msedge: str, url: str, profil: Path) -> list[str]:
    """Ligne de commande d'Edge sans fenêtre, profil jetable, DOM rendu sur la sortie."""
    return [
        msedge,
        "--headless",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profil}",
        f"--virtual-time-budget={DELAI_VIRTUEL_MS}",
        "--dump-dom",
        url,
    ]


def charger_dom(msedge: str, url: str) -> str:
    """DOM de `url` après exécution des scripts, par Edge sans fenêtre."""
    with tempfile.TemporaryDirectory(prefix="controle-edge-") as profil:
        try:
            termine = subprocess.run(
                commande_edge(msedge, url, Path(profil)),
                capture_output=True,
                timeout=DELAI_EDGE_S,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ControleImpossible(f"Edge n'a pas rendu {url} en {DELAI_EDGE_S:.0f} s") from exc
    sortie = termine.stdout.decode("utf-8", errors="replace")
    if not sortie.strip():
        raise ControleImpossible(f"Edge n'a rien rendu pour {url} (code {termine.returncode})")
    return sortie


def verifier_ecrans(base: str, charger: Callable[[str], str]) -> list[Resultat]:
    """Un résultat par écran, d'après le DOM rendu par `charger(url)`."""
    resultats: list[Resultat] = []
    for nom, route in ECRANS:
        anomalies = analyser_dom(route, charger(base + route))
        resultats.append(
            Resultat(f"écran {nom} ({route})", not anomalies, "; ".join(anomalies) or "affiché")
        )
    return resultats


def verifier_livrables(
    base: str, ouvrir: Callable[[str], tuple[int, Mapping[str, str], bytes]]
) -> list[Resultat]:
    """Télécharge chaque livrable annoncé par `/api/carte` : 200, attachment, corps non vide."""
    statut, _, corps = ouvrir(base + "/api/carte")
    if statut != 200:
        return [Resultat("livrables", False, f"/api/carte a répondu {statut}")]
    try:
        vue = json.loads(corps)
        livrables = [element for element in vue.get("livrables", []) if element.get("url")]
    except (ValueError, AttributeError, TypeError):
        return [Resultat("livrables", False, "/api/carte illisible")]
    if not livrables:
        return [Resultat("livrables", False, "aucun livrable disponible pour ce Passage")]
    resultats: list[Resultat] = []
    for livrable in livrables:
        nom = f"livrable {livrable.get('fichier', livrable['url'])}"
        statut, entetes, contenu = ouvrir(base + str(livrable["url"]))
        disposition = entetes.get("content-disposition", "")
        problemes = []
        if statut != 200:
            problemes.append(f"HTTP {statut}")
        if not disposition.lower().startswith("attachment"):
            problemes.append("en-tête attachment absent")
        if not contenu:
            problemes.append("corps vide")
        detail = "; ".join(problemes) or f"HTTP 200, attachment, {len(contenu)} octets"
        resultats.append(Resultat(nom, not problemes, detail))
    return resultats


def ouvrir_http(url: str) -> tuple[int, Mapping[str, str], bytes]:
    """GET simple ; un statut d'erreur est rendu tel quel, pas levé."""
    try:
        with urllib.request.urlopen(url, timeout=30) as reponse:
            entetes = {cle.lower(): valeur for cle, valeur in reponse.headers.items()}
            return int(reponse.status), entetes, reponse.read()
    except urllib.error.HTTPError as exc:
        return exc.code, {cle.lower(): v for cle, v in exc.headers.items()}, exc.read()


def attendre_serveur(base: str, processus: subprocess.Popen[bytes]) -> None:
    """Attend que `/api/cadre` réponde ; `ControleImpossible` si le serveur meurt ou se tait."""
    limite = time.monotonic() + DELAI_DEMARRAGE_S
    while time.monotonic() < limite:
        if processus.poll() is not None:
            raise ControleImpossible(f"`usine ui` s'est arrêté (code {processus.returncode})")
        try:
            if ouvrir_http(base + "/api/cadre")[0] == 200:
                return
        except OSError:
            pass
        time.sleep(0.5)
    raise ControleImpossible(f"`usine ui` ne répond pas après {DELAI_DEMARRAGE_S:.0f} s")


def demarrer_serveur(racine: Path, port: int) -> subprocess.Popen[bytes]:
    """`usine ui` en Mode repli, dans la racine donnée."""
    environnement = dict(os.environ)
    environnement["USINE_MODE_REPLI"] = "1"
    environnement["USINE_RACINE"] = str(racine)
    return subprocess.Popen(
        [sys.executable, "-m", "usine", "ui", "--port", str(port)],
        cwd=racine,
        env=environnement,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def arreter_serveur(processus: subprocess.Popen[bytes]) -> None:
    """Arrêt propre, puis forcé si le serveur ne rend pas la main."""
    if processus.poll() is not None:
        return
    processus.terminate()
    try:
        processus.wait(timeout=10)
    except subprocess.TimeoutExpired:
        processus.kill()
        processus.wait(timeout=10)


def compte_rendu(resultats: Sequence[Resultat]) -> str:
    """Rapport court : une ligne par écran et par livrable, puis le bilan."""
    lignes = ["Contrôle avant répétition (Mode repli, Edge sans fenêtre)"]
    lignes += [f"  [{'OK' if r.ok else 'KO'}] {r.nom} : {r.detail}" for r in resultats]
    ko = sum(1 for r in resultats if not r.ok)
    lignes.append(
        "Bilan : prêt pour la répétition." if not ko else f"Bilan : {ko} point(s) en échec."
    )
    return "\n".join(lignes)


def controler(racine: Path, port: int | None, msedge: str | None) -> list[Resultat]:
    """Démarre le serveur, contrôle écrans et livrables, arrête le serveur (toujours)."""
    edge = trouver_msedge(msedge)
    numero = port or port_libre()
    base = f"http://{HOTE}:{numero}"
    processus = demarrer_serveur(racine, numero)
    try:
        attendre_serveur(base, processus)
        resultats = verifier_ecrans(base, lambda url: charger_dom(edge, url))
        resultats += verifier_livrables(base, ouvrir_http)
        return resultats
    finally:
        arreter_serveur(processus)


def main(arguments: Sequence[str] | None = None) -> int:
    """Point d'entrée ; 0 prêt, 1 écran ou livrable en échec, 2 contrôle impossible."""
    reconfigurer = getattr(sys.stdout, "reconfigure", None)
    if reconfigurer is not None:  # console Windows : libellés accentués
        reconfigurer(encoding="utf-8", errors="replace")
    analyseur = argparse.ArgumentParser(
        prog="controle_repetition", description=(__doc__ or "").splitlines()[0]
    )
    analyseur.add_argument("--racine", type=Path, default=Path("."))
    analyseur.add_argument("--port", type=int, default=None, help="port local (défaut : libre)")
    analyseur.add_argument("--msedge", default=None, help="chemin de msedge.exe")
    args = analyseur.parse_args(arguments)
    try:
        resultats = controler(args.racine.resolve(), args.port, args.msedge)
    except ControleImpossible as exc:
        print(f"Contrôle impossible : {exc}", file=sys.stderr)
        return 2
    print(compte_rendu(resultats))
    return 0 if all(r.ok for r in resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
