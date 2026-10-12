"""Client d'écriture de l'injecteur : distinct, `JIRA_TOKEN_INJECTION`, Cloud seulement (AD-5)."""

import base64
import re
from pathlib import Path

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
