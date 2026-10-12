"""Commande `usine donnees generer` (Stories 0.3, 1.1, 1.2 et 1.4)."""

import ast
import json
import shutil
from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
import time_machine
import yaml
from pydantic import BaseModel
from typer.testing import CliRunner

from usine import cli, composition
from usine.cli import app
from usine.config import charger_yaml
from usine.contrats.calendrier import FUSEAU, jour_local, semaine_programme
from usine.contrats.config import ConfigJira, ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import EnteteJournal, Evenement, NatureEvenement
from usine.contrats.llm import (
    MessageAgent,
    OutilAgent,
    ParametresAppel,
    ReponseAgentBrute,
    ReponseStructuree,
)
from usine.contrats.tickets import Champ, TypeTicket
from usine.generateur import corpus as corpus_module
from usine.generateur.corpus import Corpus, charger_corpus
from usine.generateur.journal import generer as generer_journal
from usine.generateur.journal import serialiser_journal
from usine.generateur.scenarios import AUCUN_SCENARIO

RACINE = Path(__file__).resolve().parents[3]
CONFIG = Path(__file__).with_name("programme_reduit.yaml")
"""Programme réduit figé : génération rapide."""
CONFIG_JIRA = RACINE / "config" / "jira.yaml"
CORPUS = RACINE / "donnees" / "corpus" / "textes.json"


def _generer(sortie: Path, *options: str) -> None:
    resultat = CliRunner().invoke(
        app,
        [
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--config-jira",
            str(CONFIG_JIRA),
            "--sortie",
            str(sortie),
            "--corpus",
            str(CORPUS),
            *options,
        ],
    )
    assert resultat.exit_code == 0, resultat.output
    assert resultat.exception is None


def test_generation(tmp_path: Path) -> None:
    sortie = tmp_path / "donnees"
    _generer(sortie, "--graine", "42", "--date-generation", "2026-10-12")
    lignes = (sortie / "journal.jsonl").read_bytes().decode("utf-8").splitlines()
    entete = EnteteJournal.model_validate_json(lignes[0])
    assert entete.graine == 42
    assert entete.date_injection.isoformat() == "2026-10-09"
    assert entete.ancrage_semaines.isoformat() == "2026-08-17"
    assert all(Evenement.model_validate_json(ligne) for ligne in lignes[1:])
    assert json.loads((sortie / "verite_terrain.json").read_text(encoding="utf-8"))


def test_generation_ecrit_les_identifiants_injectes(tmp_path: Path) -> None:
    """Story 1.4 : la liste est écrite à côté du Journal et annoncée par la commande."""
    sortie = tmp_path / "donnees"
    resultat = CliRunner().invoke(
        app,
        [
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--config-jira",
            str(CONFIG_JIRA),
            "--sortie",
            str(sortie),
            "--corpus",
            str(CORPUS),
            "--graine",
            "42",
            "--date-generation",
            "2026-10-12",
        ],
    )
    assert resultat.exit_code == 0, resultat.output
    liste = json.loads((sortie / "identifiants_injectes.json").read_text(encoding="utf-8"))
    assert liste
    assert {tuple(sorted(i)) for i in liste} == {("cle_ticket", "type", "valeur")}
    journal = (sortie / "journal.jsonl").read_text(encoding="utf-8")
    assert all(i["valeur"] in journal for i in liste)
    assert str(sortie / "identifiants_injectes.json") in resultat.output
    assert f"{len(liste)} identifiants fictifs" in resultat.output


def _invoquer(sortie: Path, *options: str) -> str:
    """Lance `usine donnees generer` sur le Programme réduit (graine 42, 2026-10-12) ; renvoie
    la sortie."""
    resultat = CliRunner().invoke(
        app,
        [
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--config-jira",
            str(CONFIG_JIRA),
            "--sortie",
            str(sortie),
            "--corpus",
            str(CORPUS),
            "--graine",
            "42",
            "--date-generation",
            "2026-10-12",
            *options,
        ],
    )
    assert resultat.exit_code == 0, resultat.output
    return resultat.output


def test_scenarios_appliques_annonces(tmp_path: Path) -> None:
    """Story 1.8 : Programme réduit (ENT-A, ENT-B) : Scénarios A et B appliqués, C ignoré."""
    sortie = _invoquer(tmp_path)
    assert "Scénarios appliqués : A (ENT-A), B (ENT-B)" in sortie


def test_sans_scenarios(tmp_path: Path) -> None:
    """`--sans-scenarios` : Journal identique à `scenarios=AUCUN_SCENARIO`, sortie « aucun »."""
    sortie = _invoquer(tmp_path / "sans", "--sans-scenarios")
    assert "Scénarios appliqués : aucun" in sortie
    attendu = generer_journal(
        charger_yaml(CONFIG, ConfigProgramme),
        42,
        date(2026, 10, 12),
        cle_projet=charger_yaml(CONFIG_JIRA, ConfigJira).cle_projet,
        corpus=charger_corpus(CORPUS),
        scenarios=AUCUN_SCENARIO,
    )
    journal = (tmp_path / "sans" / "journal.jsonl").read_bytes()
    assert journal == serialiser_journal(attendu)
    _invoquer(tmp_path / "avec")
    assert (tmp_path / "avec" / "journal.jsonl").read_bytes() != journal


def test_identifiants_injectes_ignores_par_git() -> None:
    """Le fichier par défaut, `donnees/identifiants_injectes.json`, est hors git."""
    lignes = (RACINE / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "donnees/*" in lignes
    assert not any(ligne.startswith("!donnees/identifiants") for ligne in lignes)


def test_reproductible_et_graine_differente(tmp_path: Path) -> None:
    options = ("--date-generation", "2026-10-12")
    _generer(tmp_path / "a", "--graine", "42", *options)
    _generer(tmp_path / "b", "--graine", "42", *options)
    _generer(tmp_path / "c", "--graine", "43", *options)
    for nom in ("journal.jsonl", "verite_terrain.json", "identifiants_injectes.json"):
        assert (tmp_path / "a" / nom).read_bytes() == (tmp_path / "b" / nom).read_bytes()
    journal = (tmp_path / "a" / "journal.jsonl").read_bytes()
    assert (tmp_path / "c" / "journal.jsonl").read_bytes() != journal


@pytest.mark.parametrize(
    "instant",
    [
        datetime(2026, 10, 12, 10, 0, tzinfo=FUSEAU),
        # Juste après minuit à Paris : la date UTC est encore le 2026-10-11.
        datetime(2026, 10, 12, 0, 30, tzinfo=FUSEAU),
    ],
    ids=["10h-paris", "00h30-paris"],
)
def test_graine_et_date_par_defaut(tmp_path: Path, instant: datetime) -> None:
    with time_machine.travel(instant, tick=False):
        _generer(tmp_path)
    entete = EnteteJournal.model_validate_json(
        (tmp_path / "journal.jsonl").read_bytes().splitlines()[0]
    )
    assert entete.graine == 42
    assert entete.date_generation.isoformat() == "2026-10-12"


@pytest.mark.parametrize("valeur", ["2026-13-01", "12/10/2026", "20261012", "2026-1-5"])
def test_date_invalide(tmp_path: Path, valeur: str) -> None:
    resultat = CliRunner().invoke(
        app,
        [
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--sortie",
            str(tmp_path),
            "--date-generation",
            valeur,
        ],
    )
    assert resultat.exit_code != 0
    assert isinstance(resultat.exception, UsineErreur)
    assert valeur in str(resultat.exception)
    assert not (tmp_path / "journal.jsonl").exists()


@pytest.mark.parametrize("valeur", ["2026-13-01", "20261012"])
def test_date_invalide_code_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    valeur: str,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "usine",
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--sortie",
            str(tmp_path),
            "--date-generation",
            valeur,
        ],
    )
    with pytest.raises(SystemExit) as sortie:
        cli.main()
    assert sortie.value.code == 1
    assert valeur in capsys.readouterr().err


def test_graine_negative(tmp_path: Path) -> None:
    resultat = CliRunner().invoke(
        app,
        [
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--config-jira",
            str(CONFIG_JIRA),
            "--sortie",
            str(tmp_path),
            "--date-generation",
            "2026-10-12",
            "--graine",
            "-42",
        ],
    )
    assert isinstance(resultat.exception, UsineErreur)
    assert "-42" in str(resultat.exception)
    assert not (tmp_path / "journal.jsonl").exists()


def test_chemins_par_defaut(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "config").mkdir()
    shutil.copyfile(CONFIG, tmp_path / "config" / "programme.yaml")
    shutil.copyfile(CONFIG_JIRA, tmp_path / "config" / "jira.yaml")
    (tmp_path / "donnees" / "corpus").mkdir(parents=True)
    shutil.copyfile(CORPUS, tmp_path / "donnees" / "corpus" / "textes.json")
    monkeypatch.chdir(tmp_path)
    resultat = CliRunner().invoke(app, ["donnees", "generer", "--date-generation", "2026-10-12"])
    assert resultat.exit_code == 0, resultat.output
    assert (tmp_path / "donnees" / "journal.jsonl").is_file()
    assert (tmp_path / "donnees" / "verite_terrain.json").is_file()
    assert (tmp_path / "donnees" / "identifiants_injectes.json").is_file()


def test_sortie_non_inscriptible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fichier = tmp_path / "pas_un_repertoire"
    fichier.write_text("occupé", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "usine",
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--config-jira",
            str(CONFIG_JIRA),
            "--sortie",
            str(fichier),
            "--date-generation",
            "2026-10-12",
        ],
    )
    with pytest.raises(SystemExit) as sortie:
        cli.main()
    assert sortie.value.code == 1
    assert str(fichier) in capsys.readouterr().err


def test_config_fautive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fautive = tmp_path / "programme.yaml"
    fautive.write_text(
        CONFIG.read_text(encoding="utf-8").replace("vague: V1", "vague: V9", 1),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["usine", "donnees", "generer", "--config", str(fautive), "--sortie", str(tmp_path)],
    )
    with pytest.raises(SystemExit) as sortie:
        cli.main()
    assert sortie.value.code == 1
    erreur = capsys.readouterr().err
    assert str(fautive) in erreur
    assert "Vague inconnue" in erreur
    assert "V9" in erreur
    assert not (tmp_path / "journal.jsonl").exists()


def _lire_journal(sortie: Path) -> tuple[EnteteJournal, list[Evenement]]:
    lignes = (sortie / "journal.jsonl").read_bytes().decode("utf-8").splitlines()
    entete = EnteteJournal.model_validate_json(lignes[0])
    return entete, [Evenement.model_validate_json(ligne) for ligne in lignes[1:]]


def test_cle_projet_de_la_config_jira(tmp_path: Path) -> None:
    jira = tmp_path / "jira.yaml"
    jira.write_text(
        CONFIG_JIRA.read_text(encoding="utf-8").replace("cle_projet: DEMO", "cle_projet: PILOTE"),
        encoding="utf-8",
    )
    sortie = tmp_path / "donnees"
    _generer(
        sortie, "--graine", "42", "--date-generation", "2026-10-12", "--config-jira", str(jira)
    )
    _, evenements = _lire_journal(sortie)
    assert evenements
    assert all(e.cle_ticket.startswith("PILOTE-") for e in evenements)
    verite = json.loads((sortie / "verite_terrain.json").read_text(encoding="utf-8"))
    assert verite
    assert all(cle.startswith("PILOTE-") for cle in verite)


def test_cle_projet_par_defaut_demo(tmp_path: Path) -> None:
    _generer(tmp_path, "--graine", "42", "--date-generation", "2026-10-12")
    _, evenements = _lire_journal(tmp_path)
    assert all(e.cle_ticket.startswith("DEMO-") for e in evenements)


def test_config_jira_fautive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    jira = tmp_path / "jira.yaml"
    jira.write_text(
        CONFIG_JIRA.read_text(encoding="utf-8").replace("cle_projet: DEMO", "cle_projet: demo"),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "usine",
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--config-jira",
            str(jira),
            "--sortie",
            str(tmp_path),
            "--date-generation",
            "2026-10-12",
        ],
    )
    with pytest.raises(SystemExit) as sortie:
        cli.main()
    assert sortie.value.code == 1
    erreur = capsys.readouterr().err
    assert str(jira) in erreur
    assert "cle_projet" in erreur
    assert "demo" in erreur
    assert not (tmp_path / "journal.jsonl").exists()


def test_copie_a_six_entites_et_volumetrie_divisee(tmp_path: Path) -> None:
    """Changer le nombre d'Entités ou la volumétrie ne demande aucun code."""
    donnees = yaml.safe_load((RACINE / "config" / "programme.yaml").read_text(encoding="utf-8"))
    donnees["entites"] = donnees["entites"][:6]
    donnees["volumetrie"] = {cle: n // 2 for cle, n in donnees["volumetrie"].items()}
    copie = tmp_path / "programme.yaml"
    copie.write_text(yaml.safe_dump(donnees, allow_unicode=True), encoding="utf-8")
    sortie = tmp_path / "donnees"
    resultat = CliRunner().invoke(
        app,
        [
            "donnees",
            "generer",
            "--config",
            str(copie),
            "--config-jira",
            str(CONFIG_JIRA),
            "--sortie",
            str(sortie),
            "--date-generation",
            "2026-10-12",
        ],
    )
    assert resultat.exit_code == 0, resultat.output
    entete, evenements = _lire_journal(sortie)
    entites = {e.vers for e in evenements if e.champ is Champ.entite}
    assert entites == {f"ENT-{c}" for c in "ABCDEF"}
    creations = [
        e
        for e in evenements
        if e.nature is NatureEvenement.creation and e.type_ticket is TypeTicket.anomalie
    ]
    # Bornes divisées par deux ∩ 8 semaines × [100, 250] Entrées par semaine = [1 500, 2 000].
    assert 1500 <= len(creations) <= 2000
    reouvertures = [
        e for e in evenements if e.nature is NatureEvenement.transition and e.de == "fermee"
    ]
    entrees = Counter(
        semaine_programme(jour_local(e.horodatage), entete.ancrage_semaines)
        for e in creations + reouvertures
    )
    assert sorted(entrees) == list(range(1, 9))
    assert all(100 <= n <= 250 for n in entrees.values()), entrees


# --- Story 1.2 : Corpus de textes ---


class FournisseurEnEchec:
    """Fournisseur LLM qui compte ses appels et échoue à chacun."""

    def __init__(self) -> None:
        self.appels = 0

    @property
    def version_modele(self) -> str:
        return "echec:modele"

    def generer_structure[T: BaseModel](
        self, prompt: str, schema: type[T], parametres: ParametresAppel
    ) -> ReponseStructuree[T]:
        self.appels += 1
        raise AssertionError("appel LLM pendant la régénération des données")

    def executer_agent(
        self,
        messages: Sequence[MessageAgent],
        outils: Sequence[OutilAgent],
        parametres: ParametresAppel,
    ) -> ReponseAgentBrute:
        self.appels += 1
        raise AssertionError("appel LLM pendant la régénération des données")


def test_corpus_versionne_dans_l_entete(tmp_path: Path) -> None:
    _generer(tmp_path, "--graine", "42", "--date-generation", "2026-10-12")
    entete, evenements = _lire_journal(tmp_path)
    corpus = charger_corpus(CORPUS)
    assert (entete.version_corpus, entete.modele_corpus) == (
        corpus.version_corpus,
        "gabarits-provisoires",
    )
    titres = {e.vers for e in evenements if e.champ is Champ.titre}
    assert titres
    assert not any("{" in str(t) for t in titres)


def test_regeneration_sans_appel_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un fournisseur en échec branché sur `produire_corpus` : le Journal s'écrit sans appel.

    La génération est sans LLM par construction : `cli.py` et `journal.py` n'importent ni le
    port `FournisseurLLM`, ni `composition`, ni `ia`, ni `produire_corpus` (vérifié par AST).
    """
    interdits = {"usine.ports.fournisseur_llm", "usine.composition", "usine.ia"}
    for source in ("cli.py", "journal.py"):
        arbre = ast.parse((RACINE / "src" / "usine" / "generateur" / source).read_text("utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                modules = {alias.name for alias in noeud.names}
                noms: set[str] = set()
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                modules = {noeud.module}
                noms = {alias.name for alias in noeud.names}
            else:
                continue
            for module in modules:
                assert not any(module == i or module.startswith(f"{i}.") for i in interdits), (
                    source,
                    module,
                )
            assert "produire_corpus" not in noms, source
    fournisseur = FournisseurEnEchec()
    produire = corpus_module.produire_corpus

    def produire_en_echec(*_: object, **options: Any) -> Corpus:
        return produire(fournisseur, ("credits",), **options)

    monkeypatch.setattr(corpus_module, "produire_corpus", produire_en_echec)
    monkeypatch.setattr(composition, "produire_corpus", produire_en_echec)
    _generer(tmp_path, "--graine", "42", "--date-generation", "2026-10-12")
    assert (tmp_path / "journal.jsonl").is_file()
    assert fournisseur.appels == 0


def test_corpus_autre_chemin(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.json"
    contenu = json.loads(CORPUS.read_text(encoding="utf-8"))
    contenu.update(version_corpus="essai-2", modele_corpus="factice:modele")
    corpus.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
    sortie = tmp_path / "donnees"
    _generer(sortie, "--graine", "42", "--date-generation", "2026-10-12", "--corpus", str(corpus))
    entete, _ = _lire_journal(sortie)
    assert (entete.version_corpus, entete.modele_corpus) == ("essai-2", "factice:modele")


@pytest.mark.parametrize("contenu", ["{pas du json", "", '{"version_corpus": "x"}'])
def test_corpus_invalide(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    contenu: str,
) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(contenu, encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "usine",
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--config-jira",
            str(CONFIG_JIRA),
            "--sortie",
            str(tmp_path),
            "--date-generation",
            "2026-10-12",
            "--corpus",
            str(corpus),
        ],
    )
    with pytest.raises(SystemExit) as sortie:
        cli.main()
    assert sortie.value.code == 1
    assert str(corpus) in capsys.readouterr().err
    assert not (tmp_path / "journal.jsonl").exists()
