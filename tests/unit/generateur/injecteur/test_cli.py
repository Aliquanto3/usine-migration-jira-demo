"""Composition de l'injecteur et commande `usine donnees injecter` (Story 1.6)."""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import yaml
from typer.testing import CliRunner

from tests.unit.adaptateurs.jira_http.outils import Attentes
from tests.unit.generateur.injecteur.faux_jira import API, FauxJira, Requete
from usine.adaptateurs.journal import SourceJournal, charger_manifeste
from usine.cli import app
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.generateur.injecteur import cli as cli_injecteur
from usine.generateur.injecteur.cli import (
    NOM_ETAT_PARTIEL,
    NOM_SITE,
    Limiteur,
    ResultatInjection,
    executer_injection,
)
from usine.generateur.injecteur.injection import InjectionInterrompue

RACINE = Path(__file__).resolve().parents[4]


@pytest.fixture
def config_fichier(tmp_path: Path, config: ConfigJira) -> Path:
    """`config/jira.yaml` du dépôt, URL fictive, écrit dans `tmp_path`."""
    contenu = yaml.safe_load((RACINE / "config" / "jira.yaml").read_text(encoding="utf-8"))
    contenu["url_site"] = config.url_site
    chemin = tmp_path / "jira.yaml"
    chemin.write_text(yaml.safe_dump(contenu, allow_unicode=True), encoding="utf-8")
    return chemin


@pytest.fixture
def secrets_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    """E-mail et jeton d'injection dans l'environnement du test."""
    monkeypatch.setenv("JIRA_EMAIL", "injecteur@example.invalid")
    monkeypatch.setenv("JIRA_TOKEN_INJECTION", "jeton-injection")


def _executer(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path, faux: FauxJira
) -> ResultatInjection:
    return executer_injection(
        racine=tmp_path,
        config_jira=config_fichier,
        journal=chemin_journal,
        manifeste=tmp_path / "injection" / "manifeste_injection.json",
        attendre=Attentes(),
        horloge_monotone=lambda: 0.0,
        transport_http=faux.transport,
    )


@pytest.mark.usefixtures("secrets_injection")
def test_injection_ecrit_manifeste_et_site(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    faux = FauxJira()
    resultat = _executer(tmp_path, config_fichier, chemin_journal, faux)
    manifeste = charger_manifeste(tmp_path / "injection" / "manifeste_injection.json")
    assert manifeste == resultat.manifeste
    assert SourceJournal(chemin_journal, manifeste).entete.date_injection == (
        manifeste.date_injection
    )
    site = json.loads((tmp_path / "injection" / NOM_SITE).read_text(encoding="utf-8"))
    assert site == resultat.site.vers_json()
    assert not (tmp_path / "injection" / NOM_ETAT_PARTIEL).exists()
    # Les identifiants fictifs de config/jira.yaml diffèrent de ceux du site : avertissement.
    assert any(ecart.startswith("gravite : customfield_10004") for ecart in resultat.avertissements)
    assert list((tmp_path / "injection").glob(".*.tmp")) == []
    assert len(faux.tickets) == len(manifeste.correspondance_cles)


@pytest.mark.usefixtures("secrets_injection")
def test_manifeste_existant_rien_n_est_envoye(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    manifeste = tmp_path / "injection" / "manifeste_injection.json"
    manifeste.parent.mkdir()
    manifeste.write_text("{}", encoding="utf-8")
    faux = FauxJira()
    with pytest.raises(UsineErreur, match=r"manifeste_injection.json"):
        _executer(tmp_path, config_fichier, chemin_journal, faux)
    assert faux.requetes == []


def test_secret_absent_rien_n_est_envoye(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    faux = FauxJira()
    with pytest.raises(UsineErreur, match="JIRA_TOKEN_INJECTION"):
        _executer(tmp_path, config_fichier, chemin_journal, faux)
    assert faux.requetes == []


@pytest.mark.usefixtures("secrets_injection")
def test_interruption_ecrit_l_etat_partiel(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    faux = FauxJira()
    creations = 0

    def echouer(requete: Requete) -> httpx.Response | None:
        nonlocal creations
        if requete.methode == "POST" and requete.chemin == f"{API}/issue":
            creations += 1
            if creations == 3:
                return httpx.Response(503)
        return None

    faux.avant = echouer
    with pytest.raises(InjectionInterrompue):
        _executer(tmp_path, config_fichier, chemin_journal, faux)
    repertoire = tmp_path / "injection"
    assert not (repertoire / "manifeste_injection.json").exists()
    assert (repertoire / NOM_SITE).exists()
    etat = json.loads((repertoire / NOM_ETAT_PARTIEL).read_text(encoding="utf-8"))
    assert etat["tickets_crees"] == ["DEMO-1", "DEMO-2"]
    assert etat["correspondance_cles"] == {"DEMO-1": "DEMO-1", "DEMO-2": "DEMO-2"}
    assert "503" in etat["derniere_erreur"]


def test_limiteur_plafonne_le_debit() -> None:
    instants = iter([0.0, 0.05, 0.5, 0.55])
    attentes = Attentes()
    limiteur = Limiteur(5.0, horloge_monotone=lambda: next(instants), attendre=attentes)
    for _ in range(4):
        limiteur()
    assert attentes.durees == pytest.approx([0.15, 0.15])
    with pytest.raises(UsineErreur, match="débit"):
        Limiteur(0)


def test_commande_injecter_sans_secret(
    tmp_path: Path,
    config_fichier: Path,
    chemin_journal: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)  # aucun `.env` : jamais celui du dépôt
    resultat = CliRunner().invoke(
        app,
        [
            "donnees",
            "injecter",
            "--journal",
            str(chemin_journal),
            "--config-jira",
            str(config_fichier),
            "--manifeste",
            str(tmp_path / "injection" / "manifeste_injection.json"),
        ],
    )
    assert isinstance(resultat.exception, UsineErreur)
    assert "JIRA_TOKEN_INJECTION" in str(resultat.exception)


def test_commande_injecter_dans_l_aide() -> None:
    resultat = CliRunner().invoke(app, ["donnees", "--help"])
    assert resultat.exit_code == 0
    assert "injecter" in resultat.output


@pytest.mark.usefixtures("secrets_injection")
def test_limiteur_couvre_preparation_et_injection(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    # Horloge monotone figée : le k-ième appel du limiteur après le premier attend k/débit.
    faux = FauxJira()
    attentes = Attentes()
    executer_injection(
        racine=tmp_path,
        config_jira=config_fichier,
        journal=chemin_journal,
        manifeste=tmp_path / "injection" / "manifeste_injection.json",
        debit=4.0,
        attendre=attentes,
        horloge_monotone=lambda: 0.0,
        transport_http=faux.transport,
    )
    assert any(r.chemin == f"{API}/issuetype" for r in faux.requetes)  # préparation
    assert any(r.chemin == f"{API}/issue" for r in faux.requetes)  # injection
    attendues = [0.25 * k for k in range(1, len(faux.requetes))]
    assert attentes.durees == pytest.approx(attendues)


def test_commande_injecter_transmet_le_debit_et_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recus: dict[str, Any] = {}

    def executer(**kwargs: Any) -> Any:
        recus.update(kwargs)
        return SimpleNamespace(
            site=SimpleNamespace(crees=("type Anomalie", "projet DEMO")),
            chemin_site=tmp_path / NOM_SITE,
            chemin_manifeste=tmp_path / "manifeste_injection.json",
            manifeste=SimpleNamespace(
                correspondance_cles={"DEMO-1": "DEMO-1"},
                cle_projet="DEMO",
                date_injection=date(2026, 10, 1),
            ),
            avertissements=("gravite : customfield_10004 (config) ≠ customfield_10046 (site)",),
        )

    monkeypatch.setattr(cli_injecteur, "executer_injection", executer)
    resultat = CliRunner().invoke(app, ["donnees", "injecter", "--debit", "2.5"])
    assert resultat.exit_code == 0, resultat.output
    assert recus["debit"] == 2.5
    assert "Site préparé" in resultat.stdout and "2 objet(s) créé(s)" in resultat.stdout
    assert "1 tickets, projet DEMO, Date d'injection 2026-10-01" in resultat.stdout
    assert "Avertissement" in resultat.stderr
    assert "customfield_10046 (site)" in resultat.stderr
    assert "Avertissement" not in resultat.stdout
