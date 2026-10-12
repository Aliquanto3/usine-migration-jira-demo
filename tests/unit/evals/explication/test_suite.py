"""Suite d'évaluation de l'Explication sourcée (Story 6.8, SM-3) : rejeu hors réseau.

Le mode `--reel` (réseau, secrets, coût) n'est jamais lancé ici.
"""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from evals.explication import __main__ as cli
from evals.explication.cas import (
    NOMBRE_CAS,
    REPERTOIRE_CAS,
    CasExplication,
    charger_cas,
)
from evals.explication.suite import (
    VERSION_MODELE_ENREGISTRE,
    FournisseurEnregistre,
    PseudonymiseurIdentite,
    ecrire_resultat,
    executer_suite,
    noter,
)
from usine.composition import construire_explicateur
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ReponseExplication, StatutControle
from usine.contrats.versions import version_prompt
from usine.ports.fournisseur_llm import FournisseurLLM
from usine.ports.pseudonymiseur import Pseudonymiseur

INSTANT = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)
RACINE = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def cas() -> tuple[CasExplication, ...]:
    return charger_cas()


@pytest.fixture(scope="module")
def resultat(cas: tuple[CasExplication, ...], tmp_path_factory: pytest.TempPathFactory) -> Any:
    return executer_suite(cas, tmp_path_factory.mktemp("racine"), horloge=INSTANT)


def _cas(cas: tuple[CasExplication, ...], identifiant: str) -> CasExplication:
    return next(un_cas for un_cas in cas if un_cas.identifiant == identifiant)


def _par_identifiant(resultat: Any, identifiant: str) -> Any:
    return next(sortie for sortie in resultat["cas"] if sortie["identifiant"] == identifiant)


def _avec_reponses(cas: CasExplication, *textes: str) -> CasExplication:
    reponses = tuple(ReponseExplication(texte=texte) for texte in textes)
    return cas.model_copy(update={"reponses": reponses})


def test_doublures_implementent_les_ports() -> None:
    assert isinstance(FournisseurEnregistre("cas", ()), FournisseurLLM)
    assert isinstance(PseudonymiseurIdentite(), Pseudonymiseur)


def test_dix_cas_versionnes_et_varies(cas: tuple[CasExplication, ...]) -> None:
    assert len(cas) == NOMBRE_CAS
    assert len({un_cas.identifiant for un_cas in cas}) == NOMBRE_CAS
    assert {un_cas.meteo.couleur.value for un_cas in cas} == {"rouge", "orange"}
    assert any(len(un_cas.meteo.regles) > 1 for un_cas in cas)
    assert any(un_cas.kpi for un_cas in cas)
    assert any(un_cas.repartition for un_cas in cas)
    assert any(len(un_cas.reponses) > 1 for un_cas in cas)


def test_rejeu_nominal_taux_100_versions_et_notes_nulles(resultat: Any) -> None:
    assert resultat["mode"] == "rejeu"
    assert resultat["nombre_cas"] == NOMBRE_CAS
    assert len(resultat["cas"]) == NOMBRE_CAS
    assert resultat["taux_citations_valides"] == 1.0
    assert resultat["phrases_valides"] == resultat["phrases_total"] > 0
    assert resultat["version_modele"] == VERSION_MODELE_ENREGISTRE
    assert len(resultat["version_prompt"]) == 64
    assert resultat["moyenne_humaine"] is None
    for sortie in resultat["cas"]:
        assert sortie["notes"] == {"exactitude": None, "utilite": None}
        assert sortie["statut_controle"] != StatutControle.rejete.value
        assert set(sortie["citations"]) <= set(sortie["tickets_en_cause"])


def test_version_prompt_est_celle_du_gabarit_explication(resultat: Any) -> None:
    gabarit = (RACINE / "src" / "usine" / "ia" / "prompts" / "explication.md").read_bytes()
    assert resultat["version_prompt"] == version_prompt(gabarit)


def test_phrase_hors_cause_retiree_taux_inchange(resultat: Any) -> None:
    sortie = _par_identifiant(resultat, "cas-06")
    assert sortie["phrases_retirees"] == 1
    assert sortie["statut_controle"] == StatutControle.corrige.value
    assert "DEMO-999" not in sortie["texte"]
    assert sortie["tentatives"] == 1
    assert resultat["phrases_retirees_passerelle"] == 3
    assert resultat["taux_citations_valides"] == 1.0


def test_regeneration_conforme(resultat: Any) -> None:
    sortie = _par_identifiant(resultat, "cas-07")
    assert sortie["statut_controle"] == StatutControle.conforme.value
    assert sortie["citations"] == ["DEMO-701"]
    assert sortie["tentatives"] == 2
    assert sortie["phrases_retirees"] == 2


def test_consigne_dans_un_ticket_reste_une_donnee(
    cas: tuple[CasExplication, ...], tmp_path: Path
) -> None:
    un_cas = _cas(cas, "cas-10")
    fournisseur = FournisseurEnregistre(un_cas.identifiant, un_cas.reponses)
    prompts: list[str] = []
    generer = fournisseur.generer_structure

    def espion(prompt: str, schema: Any, parametres: Any) -> Any:
        prompts.append(prompt)
        return generer(prompt, schema, parametres)

    fournisseur.generer_structure = espion  # type: ignore[method-assign]
    explicateur = construire_explicateur(
        tmp_path, fournisseur=fournisseur, pseudonymiseur=PseudonymiseurIdentite()
    )
    explicateur(un_cas.meteo, un_cas.table_textes(), repartition=un_cas.table_repartition())
    (prompt,) = prompts
    debut, fin = prompt.index("```text"), prompt.rindex("```")
    assert debut < prompt.index("Ignore les consignes") < fin


def test_explication_indisponible_comptee_invalide(
    cas: tuple[CasExplication, ...], tmp_path: Path
) -> None:
    sans_citation = "La situation se dégrade. Rien n'est cité ici."
    rejete = _avec_reponses(_cas(cas, "cas-01"), sans_citation, sans_citation)
    resultat = executer_suite((rejete, _cas(cas, "cas-05")), tmp_path, horloge=INSTANT)
    sortie = _par_identifiant(resultat, "cas-01")
    assert sortie["statut_controle"] == StatutControle.rejete.value
    assert sortie["texte"] == "explication indisponible"
    assert sortie["phrases_total"] == 1
    assert sortie["phrases_valides"] == 0
    assert resultat["phrases_total"] == 3
    assert resultat["taux_citations_valides"] == pytest.approx(2 / 3)


def test_reponses_epuisees_nomment_le_cas(cas: tuple[CasExplication, ...], tmp_path: Path) -> None:
    epuise = _avec_reponses(_cas(cas, "cas-07"), "Rien n'est cité. Toujours rien. Encore rien.")
    with pytest.raises(UsineErreur, match=r"cas-07.*épuisées"):
        executer_suite((epuise,), tmp_path)


def test_reponses_epuisees_code_de_sortie(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repertoire = tmp_path / "cas"
    shutil.copytree(REPERTOIRE_CAS, repertoire)
    chemin = repertoire / "cas-03.json"
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    donnees["reponses"] = []
    chemin.write_text(json.dumps(donnees), encoding="utf-8")
    code = cli.main(["executer", "--cas", str(repertoire), "--sortie", str(tmp_path / "res")])
    assert code == 1
    assert "cas-03" in capsys.readouterr().err
    assert not (tmp_path / "res").exists()


def test_cas_json_mal_forme_nomme_le_fichier(tmp_path: Path) -> None:
    repertoire = tmp_path / "cas"
    shutil.copytree(REPERTOIRE_CAS, repertoire)
    (repertoire / "cas-04.json").write_text("{ pas du JSON", encoding="utf-8")
    with pytest.raises(UsineErreur, match=r"cas-04\.json.*mal formé"):
        charger_cas(repertoire)


def test_moins_de_dix_cas_refuse(tmp_path: Path) -> None:
    repertoire = tmp_path / "cas"
    shutil.copytree(REPERTOIRE_CAS, repertoire)
    (repertoire / "cas-10.json").unlink()
    with pytest.raises(UsineErreur, match="9 fichier"):
        charger_cas(repertoire)


def test_identifiant_en_double_refuse(tmp_path: Path) -> None:
    repertoire = tmp_path / "cas"
    shutil.copytree(REPERTOIRE_CAS, repertoire)
    chemin = repertoire / "cas-02.json"
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    donnees["identifiant"] = "cas-01"
    chemin.write_text(json.dumps(donnees), encoding="utf-8")
    with pytest.raises(UsineErreur, match=r"cas-02\.json.*cas-01"):
        charger_cas(repertoire)


def test_cli_executer_ecrit_le_resultat_horodate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["executer", "--sortie", str(tmp_path)]) == 0
    (chemin,) = tmp_path.glob("*.json")
    assert chemin.name.endswith("Z.json")
    resultat = json.loads(chemin.read_text(encoding="utf-8"))
    assert resultat["taux_citations_valides"] == 1.0
    assert "100.0%" in capsys.readouterr().out


def _noter_tout(resultat: Any, exactitude: int, utilite: int) -> Any:
    for sortie in resultat["cas"]:
        sortie["notes"] = {"exactitude": exactitude, "utilite": utilite}
    return resultat


def test_notation_complete_ecrit_l_historique(resultat: Any, tmp_path: Path) -> None:
    chemin = ecrire_resultat(_noter_tout(json.loads(json.dumps(resultat)), 5, 4), tmp_path)
    historique = tmp_path / "historique.jsonl"
    entree = noter(chemin, historique, horloge=INSTANT)
    (ligne,) = historique.read_text(encoding="utf-8").splitlines()
    assert json.loads(ligne) == entree
    assert entree["moyenne_humaine"] == 4.5
    assert entree["moyennes_par_critere"] == {"exactitude": 5.0, "utilite": 4.0}
    assert entree["version_prompt"] == resultat["version_prompt"]
    assert entree["version_modele"] == VERSION_MODELE_ENREGISTRE
    assert entree["taux_citations_valides"] == 1.0
    assert entree["nombre_cas"] == NOMBRE_CAS
    assert entree["sm3_atteint"] is True
    noter(chemin, historique, horloge=INSTANT)
    assert len(historique.read_text(encoding="utf-8").splitlines()) == 2


def test_sm3_non_atteint_sous_4_ou_taux_incomplet(resultat: Any, tmp_path: Path) -> None:
    faible = _noter_tout(json.loads(json.dumps(resultat)), 4, 3)
    assert (
        noter(ecrire_resultat(faible, tmp_path / "a"), tmp_path / "h.jsonl")["sm3_atteint"] is False
    )
    incomplet = _noter_tout(json.loads(json.dumps(resultat)), 5, 5)
    incomplet["taux_citations_valides"] = 0.9
    assert (
        noter(ecrire_resultat(incomplet, tmp_path / "b"), tmp_path / "h.jsonl")["sm3_atteint"]
        is False
    )


@pytest.mark.parametrize("modification", ["tronque", "doublon"])
def test_notation_refuse_un_resultat_tronque_ou_en_double(
    resultat: Any, tmp_path: Path, modification: str
) -> None:
    modifie = _noter_tout(json.loads(json.dumps(resultat)), 5, 5)
    if modification == "tronque":
        del modifie["cas"][-1]
        attendu = "9 cas"
    else:
        modifie["cas"][1]["identifiant"] = "cas-01"
        attendu = "en double"
    chemin = ecrire_resultat(modifie, tmp_path)
    historique = tmp_path / "historique.jsonl"
    with pytest.raises(UsineErreur, match=attendu):
        noter(chemin, historique)
    assert not historique.exists()


@pytest.mark.parametrize("note", [None, 0, 6, 4.5, True, "4"])
def test_notation_incomplete_nomme_le_cas_et_n_ecrit_rien(
    resultat: Any, tmp_path: Path, note: object
) -> None:
    note_ = _noter_tout(json.loads(json.dumps(resultat)), 5, 5)
    note_["cas"][4]["notes"]["utilite"] = note
    chemin = ecrire_resultat(note_, tmp_path)
    historique = tmp_path / "historique.jsonl"
    with pytest.raises(UsineErreur, match=r"cas-05.*utilite"):
        noter(chemin, historique)
    assert not historique.exists()


def test_cli_noter(resultat: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chemin = ecrire_resultat(_noter_tout(json.loads(json.dumps(resultat)), 4, 4), tmp_path)
    historique = tmp_path / "historique.jsonl"
    assert cli.main(["noter", str(chemin), "--historique", str(historique)]) == 0
    assert "SM-3 atteint : oui" in capsys.readouterr().out
    assert historique.exists()


def test_cli_noter_resultat_mal_forme(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chemin = tmp_path / "resultat.json"
    chemin.write_text("[", encoding="utf-8")
    assert cli.main(["noter", str(chemin), "--historique", str(tmp_path / "h.jsonl")]) == 1
    assert "resultat.json" in capsys.readouterr().err
