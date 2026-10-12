"""Transport Jira : authentification, reprise sur 429, erreurs (Story 2.1, AD-5)."""

import base64

import httpx
import pytest
from pydantic import SecretStr

from tests.unit.adaptateurs.jira_http.outils import URL_SITE, Attentes, ServeurSimule, corps_json
from usine.adaptateurs.jira_http import Authentification, TransportJira
from usine.contrats.erreurs import UsineErreur

JETON = "jeton-tres-secret-123"
PAT = "pat-tres-secret-456"


def _cloud() -> Authentification:
    return Authentification.cloud("pilote@example.invalid", SecretStr(JETON))


def _transport(
    serveur: ServeurSimule, *, tentatives: int = 5, attentes: Attentes | None = None
) -> TransportJira:
    return TransportJira(
        URL_SITE,
        _cloud(),
        tentatives,
        attendre=attentes if attentes is not None else Attentes(),
        transport_http=serveur.transport,
    )


def test_authentification_cloud_basic() -> None:
    serveur = ServeurSimule(httpx.Response(200, json={"ok": True}))
    with _transport(serveur) as transport:
        assert transport.requete("get", "/rest/api/3/myself") == {"ok": True}
    attendu = base64.b64encode(f"pilote@example.invalid:{JETON}".encode()).decode()
    (requete,) = serveur.requetes
    assert requete.method == "GET"
    assert requete.headers["Authorization"] == f"Basic {attendu}"
    assert str(requete.url) == f"{URL_SITE}/rest/api/3/myself"


def test_authentification_dc_bearer() -> None:
    serveur = ServeurSimule(httpx.Response(200, json={}))
    transport = TransportJira(
        URL_SITE, Authentification.dc(SecretStr(PAT)), 3, transport_http=serveur.transport
    )
    transport.requete("GET", "/rest/api/2/myself")
    assert serveur.requetes[0].headers["Authorization"] == f"Bearer {PAT}"


def test_url_site_avec_chemin_de_contexte() -> None:
    serveur = ServeurSimule(httpx.Response(200, json={}))
    transport = TransportJira(
        "https://dc.example.invalid/jira/",
        Authentification.dc(SecretStr(PAT)),
        3,
        transport_http=serveur.transport,
    )
    transport.requete("GET", "/rest/api/2/field")
    assert str(serveur.requetes[0].url) == "https://dc.example.invalid/jira/rest/api/2/field"


@pytest.mark.parametrize(
    ("email", "jeton", "variable"),
    [
        (None, SecretStr(JETON), "JIRA_EMAIL"),
        ("  ", SecretStr(JETON), "JIRA_EMAIL"),
        ("pilote@example.invalid", None, "JIRA_TOKEN_LECTURE"),
        ("pilote@example.invalid", SecretStr(""), "JIRA_TOKEN_LECTURE"),
    ],
)
def test_identifiant_cloud_absent(
    email: str | None, jeton: SecretStr | None, variable: str
) -> None:
    with pytest.raises(UsineErreur, match=variable):
        Authentification.cloud(email, jeton)


def test_jeton_injection_absent_nomme_sa_variable() -> None:
    with pytest.raises(UsineErreur, match="JIRA_TOKEN_INJECTION"):
        Authentification.cloud("a@example.invalid", None, variable_jeton="JIRA_TOKEN_INJECTION")


@pytest.mark.parametrize("pat", [None, SecretStr(" ")])
def test_pat_absent(pat: SecretStr | None) -> None:
    with pytest.raises(UsineErreur, match="JIRA_DC_PAT"):
        Authentification.dc(pat)


def test_aucun_secret_dans_les_repr() -> None:
    serveur = ServeurSimule()
    authentification = _cloud()
    transport = _transport(serveur)
    encode = base64.b64encode(f"pilote@example.invalid:{JETON}".encode()).decode()
    for texte in (repr(authentification), str(authentification), repr(transport)):
        assert JETON not in texte
        assert encode not in texte
    assert PAT not in repr(Authentification.dc(SecretStr(PAT)))


def test_429_repris_apres_retry_after() -> None:
    serveur = ServeurSimule(
        httpx.Response(429, headers={"Retry-After": "7"}),
        httpx.Response(200, json={"issues": []}),
    )
    attentes = Attentes()
    resultat = _transport(serveur, attentes=attentes).requete("GET", "/rest/api/3/search/jql")
    assert resultat == {"issues": []}
    assert attentes.durees == [7.0]
    assert len(serveur.requetes) == 2


def test_429_sans_en_tete_attente_exponentielle_plafonnee() -> None:
    serveur = ServeurSimule(*(httpx.Response(429) for _ in range(9)), httpx.Response(200, json={}))
    attentes = Attentes()
    _transport(serveur, tentatives=10, attentes=attentes).requete("GET", "/rest/api/3/field")
    assert attentes.durees == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 120.0, 120.0]


def test_429_retry_after_plafonne() -> None:
    serveur = ServeurSimule(
        httpx.Response(429, headers={"Retry-After": "3600"}), httpx.Response(200, json={})
    )
    attentes = Attentes()
    _transport(serveur, attentes=attentes).requete("GET", "/rest/api/3/field")
    assert attentes.durees == [120.0]


@pytest.mark.parametrize(
    ("date_http", "attendu"),
    [("Wed, 21 Oct 2015 07:28:00 GMT", 0.0), ("Fri, 31 Dec 2100 23:59:59 GMT", 120.0)],
)
def test_429_retry_after_en_date_http(date_http: str, attendu: float) -> None:
    serveur = ServeurSimule(
        httpx.Response(429, headers={"Retry-After": date_http}), httpx.Response(200, json={})
    )
    attentes = Attentes()
    _transport(serveur, attentes=attentes).requete("GET", "/rest/api/3/field")
    assert attentes.durees == [attendu]


@pytest.mark.parametrize("valeur", [b"plus tard", "²".encode()])
def test_429_retry_after_illisible_attente_exponentielle(valeur: bytes) -> None:
    serveur = ServeurSimule(
        httpx.Response(429, headers={b"Retry-After": valeur}), httpx.Response(200, json={})
    )
    attentes = Attentes()
    _transport(serveur, attentes=attentes).requete("GET", "/rest/api/3/field")
    assert attentes.durees == [1.0]


def test_429_persistant_echoue_apres_tentatives_max() -> None:
    serveur = ServeurSimule(*(httpx.Response(429) for _ in range(3)))
    attentes = Attentes()
    with pytest.raises(UsineErreur, match=r"429 après 3 tentatives") as exc:
        _transport(serveur, tentatives=3, attentes=attentes).requete(
            "POST", "/rest/api/3/search/jql", corps={"jql": "project = DEMO"}
        )
    assert "POST /rest/api/3/search/jql" in str(exc.value)
    assert len(serveur.requetes) == 3
    assert len(attentes.durees) == 2


@pytest.mark.parametrize("statut", [401, 403, 404, 500])
def test_erreur_http_nomme_methode_chemin_statut_sans_corps(statut: int) -> None:
    serveur = ServeurSimule(
        httpx.Response(statut, json={"errorMessages": [f"détail serveur {JETON}"]})
    )
    with pytest.raises(UsineErreur) as exc:
        _transport(serveur).requete("GET", "/rest/api/3/issue/DEMO-1")
    message = str(exc.value)
    assert f"GET /rest/api/3/issue/DEMO-1 : statut HTTP {statut}" in message
    assert JETON not in message
    assert "détail serveur" not in message
    assert len(serveur.requetes) == 1


def test_redirection_non_suivie() -> None:
    serveur = ServeurSimule(
        httpx.Response(302, headers={"Location": "https://ailleurs.example.invalid/vol"})
    )
    with pytest.raises(UsineErreur, match=r"GET /rest/api/3/myself : statut HTTP 302"):
        _transport(serveur).requete("GET", "/rest/api/3/myself")
    assert len(serveur.requetes) == 1


@pytest.mark.parametrize(
    "chemin", ["https://autre.example.invalid/rest/api/3/myself", "//autre.example.invalid/x"]
)
def test_chemin_hors_site_jamais_envoye(chemin: str) -> None:
    serveur = ServeurSimule()
    with pytest.raises(UsineErreur, match=rf"Jira POST {chemin} : chemin relatif"):
        _transport(serveur).requete("POST", chemin, corps={"fields": {}})
    assert serveur.requetes == []


@pytest.mark.parametrize("chemin", ["/rest/api/3/issue/A\tB", "/rest/api/3/issue/A\nB"])
def test_chemin_invalide_leve_usine_erreur_sans_envoi(chemin: str) -> None:
    serveur = ServeurSimule()
    with pytest.raises(UsineErreur, match="chemin invalide ; aucune requête envoyée") as erreur:
        _transport(serveur).requete("POST", chemin, corps={})
    assert erreur.value.__cause__ is None
    assert JETON not in str(erreur.value)
    assert serveur.requetes == []


def test_attente_exponentielle_sans_debordement_au_dela_de_1024_tentatives() -> None:
    attentes = Attentes()
    serveur = ServeurSimule(*(httpx.Response(429) for _ in range(1030)))
    with pytest.raises(UsineErreur, match="429 après 1030 tentatives"):
        _transport(serveur, tentatives=1030, attentes=attentes).requete("GET", "/rest/api/3/x")
    assert len(attentes.durees) == 1029
    assert max(attentes.durees) == 120.0


def test_identifiants_copies_avec_espaces_nettoyes() -> None:
    serveur = ServeurSimule(httpx.Response(200, json={}), httpx.Response(200, json={}))
    cloud = Authentification.cloud("pilote@example.invalid", SecretStr(f" {JETON}\n"))
    TransportJira(URL_SITE, cloud, 1, transport_http=serveur.transport).requete(
        "GET", "/rest/api/3/myself"
    )
    dc = Authentification.dc(SecretStr(f"{PAT} \r\n"))
    TransportJira(URL_SITE, dc, 1, transport_http=serveur.transport).requete(
        "GET", "/rest/api/2/myself"
    )
    attendu = base64.b64encode(f"pilote@example.invalid:{JETON}".encode()).decode()
    assert [r.headers["Authorization"] for r in serveur.requetes] == [
        f"Basic {attendu}",
        f"Bearer {PAT}",
    ]


def test_erreur_reseau_nomme_methode_et_chemin() -> None:
    def coupure(requete: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connexion refusée", request=requete)

    serveur = ServeurSimule(coupure)
    with pytest.raises(UsineErreur, match=r"Jira GET /rest/api/3/field : erreur réseau") as exc:
        _transport(serveur).requete("GET", "/rest/api/3/field")
    assert exc.value.__cause__ is None
    assert exc.value.__suppress_context__


@pytest.mark.parametrize(
    "reponse",
    [httpx.Response(200, text="<html>"), httpx.Response(200, json=[1, 2])],
)
def test_reponse_non_objet_json(reponse: httpx.Response) -> None:
    with pytest.raises(UsineErreur, match=r"GET /rest/api/3/field : statut HTTP 200"):
        _transport(ServeurSimule(reponse)).requete("GET", "/rest/api/3/field")


def test_reponse_sans_contenu() -> None:
    serveur = ServeurSimule(httpx.Response(204))
    assert _transport(serveur).requete("PUT", "/rest/api/3/issue/DEMO-1") == {}


def test_corps_et_parametres_transmis() -> None:
    serveur = ServeurSimule(httpx.Response(200, json={}))
    _transport(serveur).requete(
        "POST", "/rest/api/3/search/jql", params={"a": "1"}, corps={"jql": "project = DEMO"}
    )
    (requete,) = serveur.requetes
    assert requete.url.params["a"] == "1"
    assert corps_json(requete) == {"jql": "project = DEMO"}


def test_tentatives_max_invalide() -> None:
    with pytest.raises(UsineErreur, match="tentatives_max"):
        TransportJira(URL_SITE, _cloud(), 0)
