"""Client d'écriture de l'injecteur : distinct, `JIRA_TOKEN_INJECTION`, Cloud seulement (AD-5)."""

import ast
import base64
import re
from pathlib import Path

import grimp
import httpx
import pytest
from pydantic import SecretStr

from tests.unit.adaptateurs.jira_http.outils import RACINE, Attentes, ServeurSimule, config_jira
from usine.adaptateurs.jira_http import (
    ClientJiraEcriture,
    ClientJiraLecture,
    construire_client_ecriture,
    construire_client_lecture,
)
from usine.contrats.erreurs import UsineErreur


def _client(serveur: ServeurSimule) -> ClientJiraEcriture:
    return construire_client_ecriture(
        config_jira("cloud"),
        email="injecteur@example.invalid",
        jeton_injection=SecretStr("jeton-injection"),
        attendre=Attentes(),
        transport_http=serveur.transport,
    )


def test_client_ecriture_authentifie_par_jeton_injection() -> None:
    serveur = ServeurSimule(
        httpx.Response(201, json={"id": "10001", "key": "DEMO-1"}),
        httpx.Response(204),
    )
    with _client(serveur) as client:
        assert not isinstance(client, ClientJiraLecture)
        cree = client.requete("POST", "/rest/api/3/issue", corps={"fields": {}})
        client.requete("POST", "/rest/api/3/issue/DEMO-1/transitions", corps={})
    assert cree == {"id": "10001", "key": "DEMO-1"}
    attendu = base64.b64encode(b"injecteur@example.invalid:jeton-injection").decode()
    assert [r.headers["Authorization"] for r in serveur.requetes] == [f"Basic {attendu}"] * 2


def test_client_ecriture_sans_jeton_nomme_jira_token_injection() -> None:
    with pytest.raises(UsineErreur, match="JIRA_TOKEN_INJECTION"):
        construire_client_ecriture(
            config_jira("cloud"), email="a@example.invalid", jeton_injection=None
        )


def test_client_ecriture_refuse_le_mode_dc() -> None:
    with pytest.raises(UsineErreur, match="Jira Cloud"):
        construire_client_ecriture(
            config_jira("dc"), email="a@example.invalid", jeton_injection=SecretStr("x")
        )


@pytest.mark.parametrize(
    ("mode", "variable", "email", "jeton", "pat"),
    [
        ("cloud", "JIRA_TOKEN_LECTURE", "a@example.invalid", None, SecretStr("p")),
        ("cloud", "JIRA_EMAIL", None, SecretStr("j"), None),
        ("dc", "JIRA_DC_PAT", "a@example.invalid", SecretStr("j"), None),
    ],
)
def test_client_lecture_identifiants_absents(
    mode: str, variable: str, email: str | None, jeton: SecretStr | None, pat: SecretStr | None
) -> None:
    with pytest.raises(UsineErreur, match=variable):
        construire_client_lecture(config_jira(mode), email=email, jeton_lecture=jeton, pat=pat)


@pytest.mark.parametrize("mode", ["cloud", "dc"])
def test_client_lecture_respecte_tentatives_max(mode: str) -> None:
    serveur = ServeurSimule(*(httpx.Response(429) for _ in range(5)))
    client = construire_client_lecture(
        config_jira(mode, tentatives_max=2),
        email="a@example.invalid",
        jeton_lecture=SecretStr("j"),
        pat=SecretStr("p"),
        attendre=Attentes(),
        transport_http=serveur.transport,
    )
    chemin = "/rest/api/3/field" if mode == "cloud" else "/rest/api/2/field"
    with pytest.raises(UsineErreur, match="429 après 2 tentatives"):
        client.requete("GET", chemin)
    assert len(serveur.requetes) == 2


def test_client_ecriture_respecte_tentatives_max() -> None:
    serveur = ServeurSimule(*(httpx.Response(429) for _ in range(5)))
    client = construire_client_ecriture(
        config_jira("cloud", tentatives_max=2),
        email="a@example.invalid",
        jeton_injection=SecretStr("j"),
        attendre=Attentes(),
        transport_http=serveur.transport,
    )
    with pytest.raises(UsineErreur, match="429 après 2 tentatives"):
        client.requete("POST", "/rest/api/3/issue", corps={})
    assert len(serveur.requetes) == 2


_AUTORISES = (
    re.compile(r"^adaptateurs/jira_http/.+\.py$"),
    re.compile(r"^generateur/(.+/)?cli\.py$"),
)
_REFERENCES = re.compile(
    r"\b(ClientJiraEcriture|construire_client_ecriture|TransportJira|Authentification)\b"
)


def test_seule_la_composition_du_generateur_reference_le_client_ecriture() -> None:
    racine_src = RACINE / "src" / "usine"
    fautifs: list[Path] = []
    for fichier in sorted(racine_src.rglob("*.py")):
        relatif = fichier.relative_to(racine_src).as_posix()
        if any(motif.match(relatif) for motif in _AUTORISES):
            continue
        if _REFERENCES.search(fichier.read_text(encoding="utf-8")):
            fautifs.append(fichier)
    assert fautifs == []


# --- Garde structurelle : seule la composition du générateur construit le client d'écriture ---
#
# Spine AD-5 : « seul `generateur/injecteur` construit un client d'écriture ». Le contrat de
# couches interdit à `usine.generateur.*` d'importer `usine.adaptateurs`, sauf ses modules `cli`
# (racines de composition) : ce sont donc les seuls autorisés, avec le paquet lui-même. La garde
# lit l'arbre syntaxique (imports, y compris relatifs et `import *`, noms, attributs, imports
# dynamiques) et le graphe d'imports de grimp, pas le texte brut.

_PAQUET = "usine.adaptateurs.jira_http"
_SENSIBLES = frozenset(
    {"ClientJiraEcriture", "construire_client_ecriture", "TransportJira", "Authentification"}
)
"""Noms qui donnent un accès en écriture : client d'écriture et transport sans liste blanche."""
_ATTRIBUTS_SENSIBLES = _SENSIBLES | {"_transport"}
_MODULES_SENSIBLES = frozenset({f"{_PAQUET}.transport"})


def _autorise(module: str) -> bool:
    return (
        module == _PAQUET
        or module.startswith(f"{_PAQUET}.")
        or (module.startswith("usine.generateur.") and module.endswith(".cli"))
    )


def _module_importe(noeud: ast.ImportFrom, module: str, est_paquet: bool) -> str:
    """Module visé par `from … import`, l'import relatif étant résolu depuis `module`."""
    if noeud.level == 0:
        return noeud.module or ""
    parties = module.split(".")
    base = parties if est_paquet else parties[:-1]
    base = base[: len(base) - (noeud.level - 1)]
    return ".".join([*base, *([noeud.module] if noeud.module else [])])


def acces_sensibles(source: str, module: str, *, est_paquet: bool = False) -> list[str]:
    """Accès au client d'écriture ou au transport nu trouvés dans `source` (module `module`)."""
    trouves: list[str] = []
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.ImportFrom):
            cible = _module_importe(noeud, module, est_paquet)
            if cible in _MODULES_SENSIBLES:
                trouves.append(f"import de {cible}")
            if cible == _PAQUET or cible.startswith(f"{_PAQUET}."):
                for alias in noeud.names:
                    if alias.name == "*" or alias.name in _SENSIBLES:
                        trouves.append(f"from {cible} import {alias.name}")
                    if f"{cible}.{alias.name}" in _MODULES_SENSIBLES:
                        trouves.append(f"import de {cible}.{alias.name}")
        elif isinstance(noeud, ast.Import):
            trouves += [f"import de {a.name}" for a in noeud.names if a.name in _MODULES_SENSIBLES]
        elif isinstance(noeud, ast.Name) and noeud.id in _SENSIBLES:
            trouves.append(f"nom {noeud.id}")
        elif isinstance(noeud, ast.Attribute) and noeud.attr in _ATTRIBUTS_SENSIBLES:
            trouves.append(f"attribut .{noeud.attr}")
        elif isinstance(noeud, ast.Call):
            # `import_module("…jira_http…")`, `getattr(m, "ClientJiraEcriture")` : les chaînes
            # passées en argument, pas les docstrings, qui peuvent citer le paquet.
            trouves += [
                f"argument {arg.value!r} (accès dynamique)"
                for arg in noeud.args
                if isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and (_PAQUET in arg.value or arg.value in _ATTRIBUTS_SENSIBLES)
            ]
    return trouves


def _modules_source() -> list[tuple[str, Path, bool]]:
    racine_src = RACINE / "src"
    modules = []
    for fichier in sorted((racine_src / "usine").rglob("*.py")):
        parties = list(fichier.relative_to(racine_src).with_suffix("").parts)
        est_paquet = parties[-1] == "__init__"
        if est_paquet:
            parties.pop()
        modules.append((".".join(parties), fichier, est_paquet))
    return modules


def test_seule_la_composition_du_generateur_accede_au_client_ecriture() -> None:
    fautifs: dict[str, list[str]] = {}
    for module, fichier, est_paquet in _modules_source():
        if _autorise(module):
            continue
        source = fichier.read_text(encoding="utf-8")
        if trouves := acces_sensibles(source, module, est_paquet=est_paquet):
            fautifs[module] = trouves
    assert fautifs == {}


def test_graphe_imports_transport_nu_reserve_au_paquet() -> None:
    graphe = grimp.build_graph("usine")
    for sensible in _MODULES_SENSIBLES:
        importeurs = graphe.find_modules_that_directly_import(sensible)
        assert {m for m in importeurs if not m.startswith(f"{_PAQUET}.") and m != _PAQUET} == set()


@pytest.mark.parametrize(
    ("source", "module"),
    [
        ("from usine.adaptateurs.jira_http import ClientJiraEcriture", "usine.chaine.x"),
        ("from usine.adaptateurs.jira_http.clients import construire_client_ecriture", "usine.x"),
        ("import usine.adaptateurs.jira_http as j\nj.construire_client_ecriture()", "usine.x"),
        ("from usine.adaptateurs.jira_http import transport", "usine.adaptateurs.jira_cloud"),
        ("import usine.adaptateurs.jira_http.transport", "usine.adaptateurs.jira_dc.a"),
        ("from usine.adaptateurs.jira_http import *", "usine.x"),
        ("from ..jira_http import TransportJira", "usine.adaptateurs.jira_cloud.a"),
        ("from .jira_http import transport", "usine.adaptateurs.a"),
        ("def f(client):\n    return client._transport.requete('POST', '/x')", "usine.x"),
        (
            "import importlib\nimportlib.import_module('usine.adaptateurs.jira_http.clients')",
            "usine.x",
        ),
        ("getattr(module, 'ClientJiraEcriture')", "usine.x"),
    ],
)
def test_garde_detecte_les_contournements(source: str, module: str) -> None:
    assert acces_sensibles(source, module)


def test_garde_laisse_passer_le_client_de_lecture() -> None:
    source = (
        '"""Adaptateur Cloud : lit Jira par `usine.adaptateurs.jira_http`."""\n'
        "from usine.adaptateurs.jira_http import ClientJiraLecture, construire_client_lecture\n"
        "def f(client: ClientJiraLecture):\n"
        "    return client.requete('GET', '/rest/api/3/field')\n"
    )
    assert acces_sensibles(source, "usine.adaptateurs.jira_cloud.extraction") == []


def test_seuls_les_modules_cli_du_generateur_sont_autorises() -> None:
    assert _autorise("usine.generateur.cli")
    assert _autorise("usine.generateur.injecteur.cli")
    assert not _autorise("usine.generateur.injecteur")
    assert not _autorise("usine.composition")
    assert not _autorise("usine.adaptateurs.jira_cloud")
