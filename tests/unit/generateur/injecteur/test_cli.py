"""Composition de l'injecteur et commande `usine donnees injecter` (Stories 1.6, 1.7)."""

import json
from datetime import UTC, date, datetime
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
from usine.contrats.tickets import TypeTicket
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
    # Le faux Jira attribue d'autres identifiants que ceux de config/jira.yaml : avertissement.
    assert any(ecart.startswith("gravite : customfield_10046") for ecart in resultat.avertissements)
    assert list((tmp_path / "injection").glob(".*.tmp")) == []
    assert len(faux.tickets) == len(manifeste.correspondance_cles)


@pytest.mark.usefixtures("secrets_injection")
def test_reinjection_complete_laisse_les_fichiers_intacts(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    faux = FauxJira()
    premier = _executer(tmp_path, config_fichier, chemin_journal, faux)
    repertoire = tmp_path / "injection"
    fichiers = [repertoire / "manifeste_injection.json", repertoire / NOM_SITE]
    avant = {f: (f.read_bytes(), f.stat().st_mtime_ns) for f in fichiers}
    statuts = {cle: t.statut for cle, t in faux.tickets.items()}
    faux.requetes.clear()
    second = _executer(tmp_path, config_fichier, chemin_journal, faux)
    assert faux.ecritures() == []  # ni préparation, ni ticket, ni transition.
    assert {cle: t.statut for cle, t in faux.tickets.items()} == statuts
    assert {f: (f.read_bytes(), f.stat().st_mtime_ns) for f in fichiers} == avant
    assert not second.manifeste_ecrit
    assert second.manifeste == premier.manifeste
    assert second.bilan.crees == () and second.bilan.transitions == 0
    assert len(second.bilan.repris) == len(faux.tickets)


@pytest.mark.usefixtures("secrets_injection")
def test_second_site_vierge_memes_cles(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    premier = _executer(tmp_path, config_fichier, chemin_journal, FauxJira())
    autre = FauxJira(premier_id=50000)  # site recréé : autre identifiant de projet.
    second = _executer(tmp_path, config_fichier, chemin_journal, autre)
    assert second.site.id_projet != premier.site.id_projet
    assert second.manifeste.correspondance_cles == premier.manifeste.correspondance_cles
    assert second.bilan.repris == ()
    assert len(second.bilan.crees) == len(autre.tickets)
    assert second.manifeste_ecrit
    repertoire = tmp_path / "injection"
    site = json.loads((repertoire / NOM_SITE).read_text(encoding="utf-8"))
    assert site["id_projet"] == second.site.id_projet
    assert charger_manifeste(repertoire / "manifeste_injection.json") == second.manifeste


@pytest.mark.usefixtures("secrets_injection")
def test_numerotation_decalee_relue_par_source_journal(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    faux = FauxJira(premier_numero=11)
    _executer(tmp_path, config_fichier, chemin_journal, faux)
    manifeste = charger_manifeste(tmp_path / "injection" / "manifeste_injection.json")
    assert manifeste.correspondance_cles["DEMO-1"] == "DEMO-11"
    assert set(manifeste.correspondance_cles.values()) == set(faux.tickets)
    relu = SourceJournal(chemin_journal, manifeste)
    assert {e.cle_ticket for e in relu.evenements()} == set(faux.tickets)


@pytest.mark.usefixtures("secrets_injection")
def test_journal_different_rien_n_est_envoye(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    faux = FauxJira()
    _executer(tmp_path, config_fichier, chemin_journal, faux)
    chemin = tmp_path / "injection" / "manifeste_injection.json"
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    contenu["date_injection"] = "2026-01-02"
    chemin.write_text(json.dumps(contenu), encoding="utf-8")
    faux.requetes.clear()
    with pytest.raises(UsineErreur, match=r"2026-01-02.*2026-10-09"):
        _executer(tmp_path, config_fichier, chemin_journal, faux)
    assert faux.requetes == []


def _ecrire_partiel(tmp_path: Path, resultat: ResultatInjection, **modifs: Any) -> None:
    contenu = {
        "url_site": resultat.site.url_site,
        "cle_projet": "DEMO",
        "id_projet": resultat.site.id_projet,
        "date_injection": resultat.manifeste.date_injection.isoformat(),
        "debut_injection": resultat.manifeste.debut_injection.isoformat(),
        "tickets_crees": [],
        "tickets_repris": [],
        "correspondance_cles": dict(resultat.manifeste.correspondance_cles),
        "derniere_erreur": "panne",
        **modifs,
    }
    chemin = tmp_path / "injection" / NOM_ETAT_PARTIEL
    chemin.write_text(json.dumps(contenu), encoding="utf-8")


@pytest.mark.usefixtures("secrets_injection")
def test_manifeste_et_etat_partiel_ulterieur_fin_relue(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    faux = FauxJira()
    premier = _executer(tmp_path, config_fichier, chemin_journal, faux)
    _ecrire_partiel(tmp_path, premier)
    tardive = datetime(2100, 1, 1, tzinfo=UTC)
    second = executer_injection(
        racine=tmp_path,
        config_jira=config_fichier,
        journal=chemin_journal,
        manifeste=tmp_path / "injection" / "manifeste_injection.json",
        attendre=Attentes(),
        horloge=lambda: tardive,
        horloge_monotone=lambda: 0.0,
        transport_http=faux.transport,
    )
    assert second.bilan.crees == () and second.bilan.transitions == 0
    assert second.manifeste.horodatage_fin_injection == tardive  # relue, pas recopiée.
    assert second.manifeste.debut_injection == premier.manifeste.debut_injection
    assert second.manifeste_ecrit
    assert not (tmp_path / "injection" / NOM_ETAT_PARTIEL).exists()


@pytest.mark.usefixtures("secrets_injection")
def test_manifeste_et_etat_partiel_en_conflit(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    faux = FauxJira()
    premier = _executer(tmp_path, config_fichier, chemin_journal, faux)
    correspondance = dict(premier.manifeste.correspondance_cles)
    correspondance["DEMO-1"] = "DEMO-2"
    _ecrire_partiel(tmp_path, premier, correspondance_cles=correspondance)
    faux.requetes.clear()
    with pytest.raises(UsineErreur, match=r"DEMO-1 → DEMO-2, le manifeste porte DEMO-1"):
        _executer(tmp_path, config_fichier, chemin_journal, faux)
    assert faux.ecritures_tickets() == []


@pytest.mark.usefixtures("secrets_injection")
def test_journal_different_par_etat_partiel_seul(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    faux = FauxJira()
    premier = _executer(tmp_path, config_fichier, chemin_journal, faux)
    (tmp_path / "injection" / "manifeste_injection.json").unlink()
    _ecrire_partiel(tmp_path, premier, date_injection="2026-01-02")
    faux.requetes.clear()
    with pytest.raises(UsineErreur, match=r"2026-01-02.*2026-10-09"):
        _executer(tmp_path, config_fichier, chemin_journal, faux)
    assert faux.requetes == []


@pytest.mark.usefixtures("secrets_injection")
def test_projet_vide_meme_identifiant_injection_complete(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    faux = FauxJira()
    premier = _executer(tmp_path, config_fichier, chemin_journal, faux)
    faux.tickets.clear()  # site recréé à la même URL, même identifiant de projet.
    second = _executer(tmp_path, config_fichier, chemin_journal, faux)
    assert second.site.id_projet == premier.site.id_projet
    assert second.bilan.repris == ()
    assert len(second.bilan.crees) == len(faux.tickets)
    assert second.manifeste.correspondance_cles == premier.manifeste.correspondance_cles


@pytest.mark.usefixtures("secrets_injection")
def test_ticket_etranger_rien_n_est_ecrit(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    faux = FauxJira()
    premier = _executer(tmp_path, config_fichier, chemin_journal, faux)
    faux.ajouter_ticket("DEMO-500", premier.site.types[TypeTicket.cas_de_test], "Intrus", "x")
    faux.requetes.clear()
    with pytest.raises(UsineErreur, match="DEMO-500"):
        _executer(tmp_path, config_fichier, chemin_journal, faux)
    assert faux.ecritures() == []
    assert not (tmp_path / "injection" / NOM_ETAT_PARTIEL).exists()


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
    assert etat["url_site"] == "https://jira.example.invalid"
    assert etat["id_projet"] == faux.projet("DEMO")["id"]
    assert etat["tickets_repris"] == []
    # Reprise : les deux tickets créés sont repris, le début d'origine conservé.
    faux.avant = None
    resultat = _executer(tmp_path, config_fichier, chemin_journal, faux)
    assert resultat.bilan.repris == ("DEMO-1", "DEMO-2")
    assert len(faux.tickets) == len(resultat.manifeste.correspondance_cles)
    assert resultat.manifeste.debut_injection.isoformat() == etat["debut_injection"]
    assert not (repertoire / NOM_ETAT_PARTIEL).exists()


@pytest.mark.usefixtures("secrets_injection")
def test_interruption_sur_un_nouveau_site_puis_reprise(
    tmp_path: Path, config_fichier: Path, chemin_journal: Path
) -> None:
    premier = _executer(tmp_path, config_fichier, chemin_journal, FauxJira())
    repertoire = tmp_path / "injection"
    site_initial = (repertoire / NOM_SITE).read_bytes()
    autre = FauxJira(premier_id=50000)
    autre.avant = lambda r: (
        httpx.Response(503) if r.chemin == f"{API}/issue" and len(autre.tickets) == 3 else None
    )
    with pytest.raises(InjectionInterrompue):
        _executer(tmp_path, config_fichier, chemin_journal, autre)
    # Nouveau site : site_jira.json et manifeste de l'ancien site laissés jusqu'au succès.
    assert (repertoire / NOM_SITE).read_bytes() == site_initial
    assert charger_manifeste(repertoire / "manifeste_injection.json") == premier.manifeste
    autre.avant = None
    second = _executer(tmp_path, config_fichier, chemin_journal, autre)
    assert second.bilan.repris == ("DEMO-1", "DEMO-2", "DEMO-3")
    assert len(autre.tickets) == len(second.manifeste.correspondance_cles)
    site = json.loads((repertoire / NOM_SITE).read_text(encoding="utf-8"))
    assert site["id_projet"] == second.site.id_projet


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
            avertissements=("gravite : customfield_10046 (config) ≠ customfield_20046 (site)",),
            bilan=SimpleNamespace(crees=("DEMO-1",), repris=(), transitions=3),
            manifeste_ecrit=True,
        )

    monkeypatch.setattr(cli_injecteur, "executer_injection", executer)
    resultat = CliRunner().invoke(app, ["donnees", "injecter", "--debit", "2.5"])
    assert resultat.exit_code == 0, resultat.output
    assert recus["debit"] == 2.5
    assert "Site préparé" in resultat.stdout and "2 objet(s) créé(s)" in resultat.stdout
    assert "Tickets : 1 créé(s), 0 repris, 3 transition(s)" in resultat.stdout
    assert "Manifeste écrit" in resultat.stdout
    assert "1 tickets, projet DEMO, Date d'injection 2026-10-01" in resultat.stdout
    assert "Avertissement" in resultat.stderr
    assert "customfield_20046 (site)" in resultat.stderr
    assert "Avertissement" not in resultat.stdout
