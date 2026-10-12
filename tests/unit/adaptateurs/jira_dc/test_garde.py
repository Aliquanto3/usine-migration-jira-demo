"""Garde structurelle de l'adaptateur Data Center (AD-5) : mêmes interdits que Cloud.

`adaptateurs/jira_dc` ne lit Jira que par `ClientJiraLecture` : ni `httpx`, ni transport, ni
authentification, ni pagination directe, ni `usine.config`, ni `yaml`.
"""

from tests.unit.adaptateurs.jira_cloud.test_garde import SRC, acces_interdits

PAQUET = SRC / "adaptateurs" / "jira_dc"


def test_adaptateur_dc_sans_acces_direct_au_transport() -> None:
    fichiers = sorted(PAQUET.rglob("*.py"))
    assert len(fichiers) >= 2
    fautifs = {
        f.relative_to(SRC).as_posix(): trouves
        for f in fichiers
        if (trouves := acces_interdits(f.read_text(encoding="utf-8")))
    }
    assert fautifs == {}


def test_garde_laisse_passer_le_client_de_lecture_dc() -> None:
    source = (
        "from usine.adaptateurs.jira_http import ClientJiraLecture\n"
        "def f(client: ClientJiraLecture):\n"
        "    client.requete_liste('GET', '/rest/api/2/field')\n"
        "    return client.paginer_par_position('/rest/api/2/search', 'issues')\n"
    )
    assert acces_interdits(source) == []
