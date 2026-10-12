"""Gardes structurelles de l'adaptateur Cloud (AD-5, AD-23).

- `adaptateurs/jira_cloud` ne lit Jira que par `ClientJiraLecture` : ni `httpx`, ni
  transport, ni authentification, ni pagination directe, ni `usine.config`, ni `yaml` ;
- la table de correspondance n'est appliquée que dans les adaptateurs Jira : `types_tickets`
  et `customfield_` n'apparaissent dans `src/usine` qu'aux adaptateurs Jira et dans
  `contrats/config.py`.
"""

import ast
import re

import pytest

from tests.unit.adaptateurs.jira_http.outils import RACINE

SRC = RACINE / "src" / "usine"
PAQUET = SRC / "adaptateurs" / "jira_cloud"

_MODULES_INTERDITS = (
    "httpx",
    "usine.adaptateurs.jira_http.transport",
    "usine.adaptateurs.jira_http.pagination",
    "usine.config",
    "yaml",
)
_NOMS_INTERDITS = frozenset(
    {
        "httpx",
        "TransportJira",
        "Authentification",
        "pagination",
        "transport",
        "_transport",
        "ClientJiraEcriture",
        "construire_client_ecriture",
        "construire_client_lecture",
    }
)


def _interdit(module: str) -> bool:
    return any(module == m or module.startswith(f"{m}.") for m in _MODULES_INTERDITS)


def acces_interdits(source: str) -> list[str]:
    """Imports et noms interdits à l'adaptateur Cloud trouvés dans `source`."""
    trouves: list[str] = []
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Import):
            trouves += [f"import {a.name}" for a in noeud.names if _interdit(a.name)]
        elif isinstance(noeud, ast.ImportFrom):
            module = noeud.module or ""
            if noeud.level == 0 and _interdit(module):
                trouves.append(f"from {module} import …")
            for alias in noeud.names:
                if alias.name in _NOMS_INTERDITS or alias.name == "*":
                    trouves.append(f"from {'.' * noeud.level}{module} import {alias.name}")
                if noeud.level == 0 and _interdit(f"{module}.{alias.name}"):
                    trouves.append(f"from {module} import {alias.name}")
        elif isinstance(noeud, ast.Name) and noeud.id in _NOMS_INTERDITS:
            trouves.append(f"nom {noeud.id}")
        elif isinstance(noeud, ast.Attribute) and noeud.attr in _NOMS_INTERDITS:
            trouves.append(f"attribut .{noeud.attr}")
        elif isinstance(noeud, ast.Call):
            trouves += [
                f"argument {arg.value!r} (accès dynamique)"
                for arg in noeud.args
                if isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and (_interdit(arg.value) or arg.value in _NOMS_INTERDITS)
            ]
    return trouves


def test_adaptateur_cloud_sans_acces_direct_au_transport() -> None:
    fichiers = sorted(PAQUET.rglob("*.py"))
    assert fichiers
    fautifs = {
        f.relative_to(SRC).as_posix(): trouves
        for f in fichiers
        if (trouves := acces_interdits(f.read_text(encoding="utf-8")))
    }
    assert fautifs == {}


@pytest.mark.parametrize(
    "source",
    [
        "import httpx",
        "from httpx import Client",
        "from usine.adaptateurs.jira_http import TransportJira",
        "from usine.adaptateurs.jira_http import Authentification",
        "from usine.adaptateurs.jira_http import pagination",
        "from usine.adaptateurs.jira_http.pagination import paginer_par_jeton",
        "import usine.adaptateurs.jira_http.transport",
        "from usine.config import charger_yaml",
        "import yaml",
        "from ..jira_http import transport",
        "from usine.adaptateurs.jira_http import *",
        "def f(client):\n    return client._transport",
        "import importlib\nimportlib.import_module('httpx')",
    ],
)
def test_garde_detecte_les_acces_interdits(source: str) -> None:
    assert acces_interdits(source)


def test_garde_laisse_passer_le_client_de_lecture() -> None:
    source = (
        "from usine.adaptateurs.jira_http import ClientJiraLecture\n"
        "def f(client: ClientJiraLecture):\n"
        "    return client.paginer_par_jeton('POST', '/rest/api/3/search/jql', 'issues')\n"
    )
    assert acces_interdits(source) == []


_AUTORISES = (
    re.compile(r"^adaptateurs/jira_[a-z_]+/.+\.py$"),
    re.compile(r"^contrats/config\.py$"),
    # L'injecteur, seul écrivain Jira (AD-5), applique la correspondance à rebours (Story 1.6).
    re.compile(r"^generateur/injecteur/(plan|site|injection)\.py$"),
)
_NOMS_JIRA = re.compile(r"types_tickets|customfield_")


def test_correspondance_jira_appliquee_dans_les_adaptateurs_seulement() -> None:
    fautifs: list[str] = []
    for fichier in sorted(SRC.rglob("*.py")):
        relatif = fichier.relative_to(SRC).as_posix()
        if any(motif.match(relatif) for motif in _AUTORISES):
            continue
        if _NOMS_JIRA.search(fichier.read_text(encoding="utf-8")):
            fautifs.append(relatif)
    assert fautifs == []
