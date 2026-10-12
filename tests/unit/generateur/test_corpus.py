"""Corpus de textes : format, Corpus provisoire versionné et production par LLM (Story 1.2)."""

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.doublures.fournisseur_factice import FournisseurFactice
from usine.config import charger_yaml
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import Tache
from usine.contrats.tickets import CauseRacine
from usine.generateur.corpus import (
    CHEMIN_CORPUS,
    MODELE_GABARITS,
    Corpus,
    ReponseCorpus,
    TexteTicket,
    charger_corpus,
    ecrire_corpus,
    produire_corpus,
    serialiser_corpus,
)
from usine.generateur.textes import VOCABULAIRES, corpus_provisoire

RACINE = Path(__file__).resolve().parents[3]
CORPUS_VERSIONNE = RACINE / CHEMIN_CORPUS
PROGRAMME_LIVRE = RACINE / "config" / "programme.yaml"

SDK_FOURNISSEURS = (
    "anthropic",
    "mistralai",
    "pydantic_ai",
    "openai",
    "google",
    "cohere",
    "langchain",
    "litellm",
    "ollama",
)


@pytest.fixture(scope="module")
def domaines_livres() -> tuple[str, ...]:
    return charger_yaml(PROGRAMME_LIVRE, ConfigProgramme).domaines


def test_corpus_versionne_identique_au_provisoire(domaines_livres: tuple[str, ...]) -> None:
    corpus = charger_corpus(CORPUS_VERSIONNE)
    assert corpus.modele_corpus == MODELE_GABARITS == "gabarits-provisoires"
    attendu = corpus_provisoire(domaines_livres)
    assert corpus == attendu
    assert CORPUS_VERSIONNE.read_bytes() == serialiser_corpus(attendu)


def test_corpus_provisoire_complet(domaines_livres: tuple[str, ...]) -> None:
    corpus = corpus_provisoire(domaines_livres)
    assert tuple(corpus.domaines) == domaines_livres
    assert set(VOCABULAIRES) == set(domaines_livres)
    for section in (*corpus.domaines.values(), corpus.generique):
        assert set(section.anomalies) == set(CauseRacine)
        assert all(section.anomalies.values())
        assert section.cas_de_test
    assert corpus.certifications
    textes = " ".join(f"{t.titre} {t.description}" for t in _tous(corpus))
    # La Cause racine n'est jamais nommée par son identifiant dans un texte.
    for cause in CauseRacine:
        if "_" in cause.value:
            assert cause.value not in textes
    assert "{domaine}" in json.dumps(corpus.generique.model_dump(mode="json"))
    assert "{entite}" in textes
    assert " de les " not in textes
    assert " de le " not in textes


def _tous(corpus: Corpus) -> list[TexteTicket]:
    textes = list(corpus.certifications)
    for section in (*corpus.domaines.values(), corpus.generique):
        textes.extend(section.cas_de_test)
        for case in section.anomalies.values():
            textes.extend(case)
    return textes


def test_textes_differents_par_cause(domaines_livres: tuple[str, ...]) -> None:
    corpus = corpus_provisoire(domaines_livres)
    for section in (*corpus.domaines.values(), corpus.generique):
        titres = [t.titre for case in section.anomalies.values() for t in case]
        assert len(titres) == len(set(titres))


def test_corpus_provisoire_deterministe() -> None:
    domaines = ("credits", "achats")
    premier = serialiser_corpus(corpus_provisoire(domaines))
    assert premier == serialiser_corpus(corpus_provisoire(domaines))
    corpus = corpus_provisoire(domaines)
    # Un Domaine sans vocabulaire n'a pas de section : il tirera dans `generique`.
    assert tuple(corpus.domaines) == ("credits",)
    assert corpus.textes_domaine("achats") is corpus.generique


def test_aller_retour(tmp_path: Path) -> None:
    corpus = corpus_provisoire(("depots", "epargne"))
    chemin = ecrire_corpus(corpus, tmp_path / "a" / "b" / "textes.json")
    assert charger_corpus(chemin) == corpus
    contenu = chemin.read_bytes()
    assert contenu.endswith(b"\n")
    assert b"\r" not in contenu


def _ecrire(tmp_path: Path, contenu: Any) -> Path:
    chemin = tmp_path / "textes.json"
    texte = contenu if isinstance(contenu, str) else json.dumps(contenu, ensure_ascii=False)
    chemin.write_text(texte, encoding="utf-8")
    return chemin


def _valide() -> dict[str, Any]:
    donnees: dict[str, Any] = json.loads(serialiser_corpus(corpus_provisoire(("credits",))))
    return donnees


def _sans_cause(donnees: dict[str, Any]) -> None:
    del donnees["domaines"]["credits"]["anomalies"]["parametrage"]


def _liste_vide(donnees: dict[str, Any]) -> None:
    donnees["generique"]["anomalies"]["environnement"] = []


def _cas_de_test_vide(donnees: dict[str, Any]) -> None:
    donnees["domaines"]["credits"]["cas_de_test"] = []


def _certifications_vides(donnees: dict[str, Any]) -> None:
    donnees["certifications"] = []


def _cause_inconnue(donnees: dict[str, Any]) -> None:
    donnees["generique"]["anomalies"]["meteo"] = donnees["generique"]["anomalies"]["parametrage"]


def _champ_inconnu(donnees: dict[str, Any]) -> None:
    donnees["certifications"][0]["titre"] = "Avis de {personne}"


def _accolade_orpheline(donnees: dict[str, Any]) -> None:
    donnees["generique"]["cas_de_test"][0]["description"] = "Test {entite"


def _domaine_en_certification(donnees: dict[str, Any]) -> None:
    donnees["certifications"][0]["description"] = "Avis sur {domaine}"


def _titre_vide(donnees: dict[str, Any]) -> None:
    donnees["domaines"]["credits"]["anomalies"]["environnement"][0]["titre"] = ""


def _champ_en_trop(donnees: dict[str, Any]) -> None:
    donnees["auteur"] = "x"


def _sans_modele(donnees: dict[str, Any]) -> None:
    del donnees["modele_corpus"]


@pytest.mark.parametrize(
    "alterer",
    [
        _sans_cause,
        _liste_vide,
        _cas_de_test_vide,
        _certifications_vides,
        _cause_inconnue,
        _champ_inconnu,
        _accolade_orpheline,
        _domaine_en_certification,
        _titre_vide,
        _champ_en_trop,
        _sans_modele,
    ],
)
def test_corpus_invalide(tmp_path: Path, alterer: Any) -> None:
    donnees = _valide()
    alterer(donnees)
    chemin = _ecrire(tmp_path, donnees)
    with pytest.raises(UsineErreur) as erreur:
        charger_corpus(chemin)
    assert str(chemin) in str(erreur.value)


def test_cause_manquante_nommee(tmp_path: Path) -> None:
    donnees = _valide()
    _sans_cause(donnees)
    with pytest.raises(UsineErreur, match="parametrage"):
        charger_corpus(_ecrire(tmp_path, donnees))


@pytest.mark.parametrize("contenu", ["{pas du json", "", "[]", "null"])
def test_json_mal_forme(tmp_path: Path, contenu: str) -> None:
    chemin = _ecrire(tmp_path, contenu)
    with pytest.raises(UsineErreur, match="Corpus invalide") as erreur:
        charger_corpus(chemin)
    assert str(chemin) in str(erreur.value)


def test_corpus_introuvable(tmp_path: Path) -> None:
    chemin = tmp_path / "absent.json"
    with pytest.raises(UsineErreur, match="introuvable") as erreur:
        charger_corpus(chemin)
    assert str(chemin) in str(erreur.value)


def test_ecriture_impossible(tmp_path: Path) -> None:
    fichier = tmp_path / "fichier"
    fichier.write_text("x", encoding="utf-8")
    with pytest.raises(UsineErreur, match="écriture impossible"):
        ecrire_corpus(corpus_provisoire(()), fichier / "textes.json")


# --- Production par LLM ---


def _reponse(rang: int) -> ReponseCorpus:
    return ReponseCorpus(
        textes=(
            TexteTicket(titre=f"Titre {rang} pour {{entite}}", description=f"Description {rang}"),
            TexteTicket(titre=f"Autre titre {rang}", description="Constaté sur {entite}"),
        )
    )


def _nb_appels(nb_domaines: int) -> int:
    """7 Causes + Cas de test par Domaine et pour `generique`, puis les Certifications."""
    return (nb_domaines + 1) * (len(CauseRacine) + 1) + 1


def test_produire_corpus_faux_llm() -> None:
    domaines = ("credits", "achats")
    nombre = _nb_appels(len(domaines))
    fournisseur = FournisseurFactice(
        reponses_structurees=[_reponse(r) for r in range(nombre)],
        version_modele="factice:redacteur",
    )
    corpus = produire_corpus(fournisseur, domaines, version_corpus="llm-essai")
    assert corpus.modele_corpus == "factice:redacteur"
    assert corpus.version_corpus == "llm-essai"
    assert tuple(corpus.domaines) == domaines
    assert len(fournisseur.appels) == nombre
    assert {a.methode for a in fournisseur.appels} == {"generer_structure"}
    assert {a.parametres.tache for a in fournisseur.appels} == {Tache.narration}
    # Ordre des cases : Domaines, puis générique, puis Certifications.
    assert corpus.domaines["credits"].anomalies[CauseRacine.reprise_donnees] == _reponse(0).textes
    assert corpus.domaines["credits"].cas_de_test == _reponse(7).textes
    assert corpus.generique.anomalies[CauseRacine.reprise_donnees] == _reponse(16).textes
    assert corpus.certifications == _reponse(nombre - 1).textes
    prompts = [str(a.entree) for a in fournisseur.appels]
    assert "credits" in prompts[0]
    assert "fictif" in prompts[0].lower()
    assert "{domaine}" in prompts[16]
    assert "{domaine}" not in prompts[0]


def test_produire_corpus_texte_fautif() -> None:
    """Une Certification produite avec `{domaine}` est refusée par le format."""
    nombre = _nb_appels(0)
    reponses = [_reponse(r) for r in range(nombre - 1)]
    reponses.append(
        ReponseCorpus(textes=(TexteTicket(titre="Avis {domaine}", description="{entite}"),))
    )
    fournisseur = FournisseurFactice(reponses_structurees=reponses)
    with pytest.raises(UsineErreur, match="factice:modele"):
        produire_corpus(fournisseur, ())


def test_production_ecrite_et_relue(tmp_path: Path) -> None:
    fournisseur = FournisseurFactice(
        reponses_structurees=[_reponse(r) for r in range(_nb_appels(1))]
    )
    corpus = produire_corpus(fournisseur, ("paie",))
    assert charger_corpus(ecrire_corpus(corpus, tmp_path / "textes.json")) == corpus


def _modules_importes(chemin: Path) -> set[str]:
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            modules.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            modules.add(noeud.module)
    return modules


@pytest.mark.parametrize(
    "chemin",
    [
        RACINE / "outils" / "generer_corpus.py",
        RACINE / "src" / "usine" / "generateur" / "corpus.py",
        RACINE / "src" / "usine" / "generateur" / "textes.py",
    ],
    ids=lambda c: c.name,
)
def test_aucun_sdk_de_fournisseur(chemin: Path) -> None:
    modules = _modules_importes(chemin)
    assert modules
    fautifs = {m for m in modules if m.split(".")[0] in SDK_FOURNISSEURS}
    assert not fautifs, fautifs


def test_outil_sans_sdk_transitif() -> None:
    """`import outils.generer_corpus` ne charge aucun SDK de fournisseur, même indirectement."""
    script = "import sys, outils.generer_corpus; print('\\n'.join(sorted(sys.modules)))"
    resultat = subprocess.run(
        [sys.executable, "-c", script], cwd=RACINE, capture_output=True, text=True, check=True
    )
    charges = {nom.split(".")[0] for nom in resultat.stdout.split()}
    assert "outils" in charges
    assert not charges & {"anthropic", "mistralai", "pydantic_ai", "openai"}
