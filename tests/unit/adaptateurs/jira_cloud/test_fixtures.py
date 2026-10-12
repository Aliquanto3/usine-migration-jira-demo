"""Rafraîchissement anonymisé des fixtures Cloud (Story 2.7) : sans réseau, client doublé."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from tests.unit.adaptateurs.jira_http.outils import (
    FIXTURES,
    RACINE,
    Attentes,
    ServeurSimule,
    config_jira,
    corps_json,
    fixture,
)
from usine.adaptateurs import cli
from usine.adaptateurs.jira_cloud import (
    anonymiser,
    convertir_ticket,
    rafraichir_fixtures,
    verifier_sans_secret,
)
from usine.adaptateurs.jira_cloud.fixtures import COMPTE_FICTIF, FICHIER_RECHERCHE
from usine.adaptateurs.jira_http import ClientJiraLecture, construire_client_lecture
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import NatureEvenement, SourceEvenement

URL_REELLE = "https://site-reel.atlassian.net"


def _utilisateur() -> dict[str, Any]:
    return {
        "self": f"{URL_REELLE}/rest/api/3/user?accountId=712020:abc",
        "accountId": "712020:abc",
        "emailAddress": "personne.reelle@entreprise.fr",
        "displayName": "Personne Réelle",
        "avatarUrls": {"48x48": "https://avatar-management.atlassian.com/abc.png"},
    }


def _page_reelle() -> dict[str, Any]:
    return {
        "issues": [
            {
                "id": "10001",
                "key": "DEMO-1",
                "self": f"{URL_REELLE}/rest/api/3/issue/10001",
                "fields": {
                    "summary": "Écart de solde",
                    "reporter": _utilisateur(),
                    "status": {"name": "Nouvelle", "iconUrl": f"{URL_REELLE}/images/statut.png"},
                },
                "changelog": {
                    "total": 1,
                    "histories": [
                        {
                            "id": "20001",
                            "author": _utilisateur(),
                            "created": "2026-09-02T08:00:00.000+0000",
                            "items": [
                                {
                                    "field": "assignee",
                                    "fieldtype": "jira",
                                    "from": None,
                                    "fromString": None,
                                    "to": "712020:abc",
                                    "toString": "Personne Réelle",
                                    "tmpToAccountId": "712020:abc",
                                },
                                {
                                    "field": "status",
                                    "fieldtype": "jira",
                                    "from": "1",
                                    "fromString": "Nouvelle",
                                    "to": "2",
                                    "toString": "En analyse",
                                },
                            ],
                        }
                    ],
                },
            }
        ],
        "nextPageToken": "jeton-de-page",
        "isLast": False,
    }


def _config(**modifications: Any) -> ConfigJira:
    return config_jira("cloud", url_site=URL_REELLE, **modifications)


def _client(serveur: ServeurSimule, config: ConfigJira) -> ClientJiraLecture:
    return construire_client_lecture(
        config,
        email="lecteur@example.invalid",
        jeton_lecture=SecretStr("jeton-lecture"),
        pat=None,
        attendre=Attentes(),
        transport_http=serveur.transport,
    )


# --- Anonymisation -----------------------------------------------------------------------


def test_anonymisation_remplace_hote_utilisateurs_et_retire_email_et_jeton() -> None:
    page = _page_reelle()
    resultat = anonymiser(page, URL_REELLE)
    ticket = resultat["issues"][0]
    assert ticket["self"] == "https://jira.example.invalid/rest/api/3/issue/10001"
    assert ticket["fields"]["reporter"] == dict(COMPTE_FICTIF)
    assert ticket["fields"]["status"]["iconUrl"].startswith("https://jira.example.invalid/")
    historique = ticket["changelog"]["histories"][0]
    assert historique["author"] == dict(COMPTE_FICTIF)
    assignation, statut = historique["items"]
    assert assignation["to"] == assignation["tmpToAccountId"] == "compte-fictif"
    assert assignation["toString"] == "Compte fictif"
    assert assignation["from"] is None and assignation["fromString"] is None
    assert statut == page["issues"][0]["changelog"]["histories"][0]["items"][1]
    assert "nextPageToken" not in resultat and resultat["isLast"] is True
    texte = json.dumps(resultat, ensure_ascii=False)
    assert "emailAddress" not in texte and "Personne Réelle" not in texte
    verifier_sans_secret(texte, URL_REELLE)
    assert page["nextPageToken"] == "jeton-de-page", "l'objet d'origine n'est pas modifié"


def test_anonymisation_hote_sans_schema_et_casse() -> None:
    texte = anonymiser("voir SITE-REEL.atlassian.net/browse/DEMO-1", URL_REELLE)
    assert texte == "voir jira.example.invalid/browse/DEMO-1"


# --- Résidu sensible ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texte", "motif"),
    [
        ('{"self": "https://site-reel.atlassian.net/x"}', "hôte du site Jira réel"),
        ('{"note": "écrire à quelqu.un@exemple.fr"}', "adresse e-mail"),
        ('{"note": "ATATT3xFfGF0-valeur-secrete"}', "préfixe de jeton Atlassian"),
    ],
)
def test_residu_sensible_refuse_sans_citer_la_valeur(texte: str, motif: str) -> None:
    with pytest.raises(UsineErreur, match=motif) as erreur:
        verifier_sans_secret(texte, URL_REELLE)
    message = str(erreur.value)
    for valeur in ("site-reel", "quelqu.un", "valeur-secrete"):
        assert valeur not in message


def test_residu_sensible_aucun_fichier_ecrit(tmp_path: Path) -> None:
    page = _page_reelle()
    page["issues"][0]["fields"]["summary"] = "jeton ATATTabc colle par erreur"
    serveur = ServeurSimule(httpx.Response(200, json=page))
    sortie = tmp_path / "fixtures"
    with pytest.raises(UsineErreur, match="ATATT"):
        rafraichir_fixtures(_client(serveur, _config()), _config(), sortie, 3)
    assert not sortie.exists()


# --- Rafraîchissement ---------------------------------------------------------------------


def test_rafraichissement_une_requete_et_fichier_ecrit(tmp_path: Path) -> None:
    serveur = ServeurSimule(httpx.Response(200, json=_page_reelle()))
    config = _config()
    sortie = tmp_path / "absente" / "jira_cloud"
    chemin = rafraichir_fixtures(_client(serveur, config), config, sortie, 3)
    assert chemin == sortie / FICHIER_RECHERCHE == sortie / "direct_recherche_page_1.json"
    [requete] = serveur.requetes
    assert requete.method == "POST" and requete.url.path == "/rest/api/3/search/jql"
    corps = corps_json(requete)
    assert corps["maxResults"] == 3 and corps["expand"] == "changelog"
    assert "nextPageToken" not in corps
    assert corps["jql"].startswith('project = "DEMO"')
    texte = chemin.read_text(encoding="utf-8")
    verifier_sans_secret(texte, URL_REELLE)
    assert json.loads(texte)["issues"][0]["key"] == "DEMO-1"


def test_rafraichissement_nb_tickets_invalide(tmp_path: Path) -> None:
    serveur = ServeurSimule()
    with pytest.raises(UsineErreur, match="--nb-tickets"):
        rafraichir_fixtures(_client(serveur, _config()), _config(), tmp_path, 0)
    assert serveur.requetes == []


# --- Commande CLI -------------------------------------------------------------------------


def _racine(tmp_path: Path) -> Path:
    racine = tmp_path / "racine"
    (racine / "config").mkdir(parents=True)
    texte = (RACINE / "config" / "jira.yaml").read_text(encoding="utf-8")
    lignes = [
        f"url_site: {URL_REELLE}" if ligne.startswith("url_site:") else ligne
        for ligne in texte.splitlines()
    ]
    (racine / "config" / "jira.yaml").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return racine


def test_commande_rafraichir_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    serveur = ServeurSimule(httpx.Response(200, json=_page_reelle()))
    construire = construire_client_lecture

    def client_double(config: ConfigJira, **options: Any) -> ClientJiraLecture:
        assert options["pat"] is None
        return construire(config, **options, transport_http=serveur.transport)

    monkeypatch.setattr(cli, "construire_client_lecture", client_double)
    monkeypatch.setenv("JIRA_EMAIL", "lecteur@example.invalid")
    monkeypatch.setenv("JIRA_TOKEN_LECTURE", "jeton-lecture")
    sortie = tmp_path / "sortie"
    resultat = CliRunner().invoke(
        cli.app,
        ["rafraichir-fixtures", "--racine", str(_racine(tmp_path)), "--sortie", str(sortie)],
    )
    assert resultat.exit_code == 0, resultat.output
    assert (sortie / FICHIER_RECHERCHE).exists()
    assert corps_json(serveur.requetes[0])["maxResults"] == 3


def test_commande_sans_secret_code_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("JIRA_TOKEN_LECTURE", raising=False)
    sortie = tmp_path / "sortie"
    resultat = CliRunner().invoke(
        cli.app,
        ["rafraichir-fixtures", "--racine", str(_racine(tmp_path)), "--sortie", str(sortie)],
    )
    assert resultat.exit_code == 1
    assert "JIRA_TOKEN_LECTURE" in resultat.output
    assert not sortie.exists()


def test_commande_refuse_mode_dc(tmp_path: Path) -> None:
    racine = _racine(tmp_path)
    chemin = racine / "config" / "jira.yaml"
    texte = chemin.read_text(encoding="utf-8")
    lignes = ["mode: dc" if ligne.startswith("mode:") else ligne for ligne in texte.splitlines()]
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    resultat = CliRunner().invoke(cli.app, ["rafraichir-fixtures", "--racine", str(racine)])
    assert resultat.exit_code == 1
    assert "mode" in resultat.output


# --- Fixture versionnée --------------------------------------------------------------------


def test_fixture_directe_se_convertit() -> None:
    """La fixture enregistrée sur `DEMO` (commande `rafraichir-fixtures`) est lue telle quelle."""
    chemin = FIXTURES / "jira_cloud" / FICHIER_RECHERCHE
    texte = chemin.read_text(encoding="utf-8")
    verifier_sans_secret(texte, _url_depot())
    page = fixture(f"jira_cloud/{FICHIER_RECHERCHE}")
    assert "nextPageToken" not in page
    config = config_jira("cloud")
    tickets = page["issues"]
    assert tickets, "fixture directe sans ticket"
    for ticket in tickets:
        assert ticket["self"].startswith("https://jira.example.invalid/")
        historiques = ticket.get("changelog", {}).get("histories", [])
        evenements = convertir_ticket(ticket, historiques, config, SourceEvenement.jira_cloud)
        creation, *suite = evenements
        assert creation.nature is NatureEvenement.creation
        assert creation.cle_ticket == ticket["key"]
        initiaux = [e for e in suite if e.horodatage == creation.horodatage]
        assert initiaux, f"{ticket['key']} : aucun champ initial"
        assert all(e.nature is NatureEvenement.modification_champ for e in initiaux)


def _url_depot() -> str:
    """`url_site` réel de `config/jira.yaml` du dépôt : il ne doit pas figurer dans la fixture."""
    for ligne in (RACINE / "config" / "jira.yaml").read_text(encoding="utf-8").splitlines():
        if ligne.startswith("url_site:"):
            return ligne.split(":", 1)[1].strip()
    raise AssertionError("config/jira.yaml sans url_site")
