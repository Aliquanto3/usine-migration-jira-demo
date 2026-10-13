"""Composition : `FournisseurLLM` choisi par `config/llm.yaml`, sans modification de code (H-23)."""

from decimal import Decimal
from pathlib import Path

import pytest

from tests.doublures.fournisseur_factice import FournisseurFactice
from usine.composition import (
    construire_fournisseur,
    construire_fournisseurs_par_tache,
    estimer_corpus,
    generer_corpus_llm,
    verifier_modele_corpus_candidat,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import Tache
from usine.generateur.corpus import ReponseCorpus, TexteTicket, charger_corpus
from usine.ports import FournisseurLLM


def _racine(tmp_path: Path, fournisseur: str, modele: str) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "llm.yaml").write_text(
        f"fournisseur: {fournisseur}\nmodele: {modele}\nplafond_cout_passage_eur: 1\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize(
    ("fournisseur", "modele", "variable"),
    [
        ("anthropic", "claude-sonnet-5-5", "ANTHROPIC_API_KEY"),
        ("mistral", "mistral-large-latest", "MISTRAL_API_KEY"),
    ],
)
def test_fournisseur_choisi_par_la_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fournisseur: str, modele: str, variable: str
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    racine = _racine(tmp_path, fournisseur, modele)
    with pytest.raises(UsineErreur, match=variable):
        construire_fournisseur(racine)
    monkeypatch.setenv(variable, "cle-de-test")
    adaptateur = construire_fournisseur(racine)
    assert isinstance(adaptateur, FournisseurLLM)
    assert adaptateur.version_modele == f"{fournisseur}:{modele}"


def test_sans_llm_yaml(tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match=r"llm\.yaml"):
        construire_fournisseur(tmp_path)


def test_configuration_du_depot_valide(monkeypatch: pytest.MonkeyPatch) -> None:
    """`config/llm.yaml` du dépôt : Anthropic, `claude-sonnet-5-5`, présent au registre."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    racine = Path(__file__).resolve().parents[2]
    assert construire_fournisseur(racine).version_modele == "anthropic:claude-sonnet-5-5"


def test_configuration_du_depot_modele_par_tache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 6.5 : la classification sur Haiku 5.5, l'explication sur le modèle par défaut."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    racine = Path(__file__).resolve().parents[2]
    par_tache = construire_fournisseurs_par_tache(racine)
    assert set(par_tache) == {Tache.classification}
    assert par_tache[Tache.classification].version_modele == "anthropic:claude-haiku-5-5"
    for fournisseur in par_tache.values():
        getattr(fournisseur, "fermer", lambda: None)()


def _avec_modeles_par_tache(racine: Path, lignes: str) -> Path:
    chemin = racine / "config" / "llm.yaml"
    chemin.write_text(
        chemin.read_text(encoding="utf-8") + "modeles_par_tache:\n" + lignes, encoding="utf-8"
    )
    return racine


def test_modele_par_tache_identique_sans_fournisseur_dedie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    racine = _avec_modeles_par_tache(
        _racine(tmp_path, "anthropic", "claude-sonnet-5-5"),
        "  explication: claude-sonnet-5-5\n",
    )
    assert construire_fournisseurs_par_tache(racine) == {}


def test_modele_par_tache_hors_registre(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    racine = _avec_modeles_par_tache(
        _racine(tmp_path, "anthropic", "claude-sonnet-5-5"),
        "  classification: claude-haiku-5-5\n  narration: claude-inconnu\n",
    )
    with pytest.raises(UsineErreur, match="claude-inconnu"):
        construire_fournisseurs_par_tache(racine)


def test_sans_modele_par_tache(tmp_path: Path) -> None:
    racine = _racine(tmp_path, "anthropic", "claude-sonnet-5-5")
    assert construire_fournisseurs_par_tache(racine) == {}
    assert construire_fournisseurs_par_tache(tmp_path / "absente") == {}


# --- Story 1.9 : Corpus définitif par LLM ---


def test_surcharge_sans_llm_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "cle-de-test")
    adaptateur = construire_fournisseur(
        tmp_path, fournisseur="mistral", modele="mistral-medium-latest"
    )
    assert adaptateur.version_modele == "mistral:mistral-medium-latest"
    getattr(adaptateur, "fermer", lambda: None)()


def test_surcharge_remplace_la_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "cle-de-test")
    racine = _avec_modeles_par_tache(
        _racine(tmp_path, "anthropic", "claude-sonnet-5-5"), "  classification: claude-haiku-5-5\n"
    )
    adaptateur = construire_fournisseur(
        racine, fournisseur="mistral", modele="mistral-medium-latest"
    )
    assert adaptateur.version_modele == "mistral:mistral-medium-latest"
    getattr(adaptateur, "fermer", lambda: None)()


def test_surcharge_incomplete(tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match="vont ensemble"):
        construire_fournisseur(tmp_path, fournisseur="mistral")


def _corpus(racine: Path, modele_corpus: str) -> Path:
    chemin = racine / "donnees" / "corpus" / "textes.json"
    chemin.parent.mkdir(parents=True)
    chemin.write_text(f'{{"modele_corpus": "{modele_corpus}"}}', encoding="utf-8")
    return chemin


@pytest.mark.parametrize(
    ("par_tache", "modele_corpus"),
    [
        ("  classification: claude-haiku-5-5\n", "anthropic:claude-haiku-5-5"),
        ("  explication: claude-haiku-5-5\n", "anthropic:claude-sonnet-5-5"),
    ],
)
def test_garde_fou_classification_egale_modele_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, par_tache: str, modele_corpus: str
) -> None:
    """AD-19 : `modeles_par_tache.classification`, sinon `modele`, ≠ `modele_corpus`."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    racine = _avec_modeles_par_tache(_racine(tmp_path, "anthropic", "claude-sonnet-5-5"), par_tache)
    corpus = _corpus(racine, modele_corpus)
    with pytest.raises(UsineErreur) as erreur:
        construire_fournisseur(racine)
    message = str(erreur.value)
    assert message.count(repr(modele_corpus)) == 2
    assert str(racine / "config" / "llm.yaml") in message
    assert str(corpus) in message
    with pytest.raises(UsineErreur, match="AD-19"):
        construire_fournisseurs_par_tache(racine)


@pytest.mark.parametrize("modele_corpus", ["gabarits-provisoires", "mistral:mistral-medium-latest"])
def test_garde_fou_corpus_provisoire_ou_distinct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, modele_corpus: str
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    racine = _avec_modeles_par_tache(
        _racine(tmp_path, "anthropic", "claude-sonnet-5-5"), "  classification: claude-haiku-5-5\n"
    )
    _corpus(racine, modele_corpus)
    adaptateur = construire_fournisseur(racine)
    assert adaptateur.version_modele == "anthropic:claude-sonnet-5-5"
    getattr(adaptateur, "fermer", lambda: None)()


def test_garde_fou_corpus_illisible(tmp_path: Path) -> None:
    racine = _racine(tmp_path, "anthropic", "claude-sonnet-5-5")
    chemin = racine / "donnees" / "corpus" / "textes.json"
    chemin.parent.mkdir(parents=True)
    chemin.write_text("{pas du json", encoding="utf-8")
    with pytest.raises(UsineErreur, match="illisible"):
        construire_fournisseur(racine)
    chemin.write_text("{}", encoding="utf-8")
    with pytest.raises(UsineErreur, match="modele_corpus"):
        construire_fournisseur(racine)


def test_estimer_corpus() -> None:
    appels, cout = estimer_corpus("mistral:mistral-medium-latest", ["a", "b", "c", "d", "e", "f"])
    assert appels == 57
    assert Decimal(0) < cout <= Decimal(2)
    assert estimer_corpus("mistral:mistral-medium-latest", [])[0] == 9


def test_estimer_corpus_hors_registre() -> None:
    with pytest.raises(UsineErreur, match="modèles connus"):
        estimer_corpus("mistral:inconnu", ["a"])


def test_verifier_modele_corpus_candidat(tmp_path: Path) -> None:
    racine = _avec_modeles_par_tache(
        _racine(tmp_path, "anthropic", "claude-sonnet-5-5"), "  classification: claude-haiku-5-5\n"
    )
    verifier_modele_corpus_candidat(racine, "mistral:mistral-medium-latest")
    verifier_modele_corpus_candidat(tmp_path / "absente", "anthropic:claude-haiku-5-5")
    with pytest.raises(UsineErreur, match="anthropic:claude-haiku-5-5"):
        verifier_modele_corpus_candidat(racine, "anthropic:claude-haiku-5-5")


def test_corpus_fautif_regenerable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un Corpus versionné fautif (AD-19 ou illisible) n'empêche pas de le régénérer."""
    monkeypatch.setenv("MISTRAL_API_KEY", "cle-de-test")
    racine = _avec_modeles_par_tache(
        _racine(tmp_path, "anthropic", "claude-sonnet-5-5"), "  classification: claude-haiku-5-5\n"
    )
    corpus = _corpus(racine, "anthropic:claude-haiku-5-5")
    for contenu in ('{"modele_corpus": "anthropic:claude-haiku-5-5"}', "{pas du json"):
        corpus.write_text(contenu, encoding="utf-8")
        verifier_modele_corpus_candidat(racine, "mistral:mistral-medium-latest")
        adaptateur = construire_fournisseur(
            racine, fournisseur="mistral", modele="mistral-medium-latest"
        )
        assert adaptateur.version_modele == "mistral:mistral-medium-latest"
        getattr(adaptateur, "fermer", lambda: None)()


def test_generer_corpus_llm_bilan(tmp_path: Path) -> None:
    reponses = [
        ReponseCorpus(textes=(TexteTicket(titre=f"T{r}", description=f"Sur {{entite}} {r}"),))
        for r in range(9)
    ]
    fournisseur = FournisseurFactice(reponses, version_modele="factice:redacteur")
    bilan = generer_corpus_llm(fournisseur, [], tmp_path / "textes.json")
    assert bilan.appels == 9
    assert bilan.modele_corpus == "factice:redacteur"
    assert bilan.jetons_entree == sum(len(str(a.entree).split()) for a in fournisseur.appels)
    assert bilan.jetons_sortie > 0
    assert bilan.cout_eur == Decimal(0)
    assert charger_corpus(bilan.chemin).modele_corpus == "factice:redacteur"


# --- Story 6.12 : mode LLM local (llama-server) ---


def test_fournisseur_local_sans_aucune_cle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for nom in ("LLAMA_API_KEY", "USINE_URL_LLM_LOCAL", "ANTHROPIC_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.delenv(nom, raising=False)
    racine = _racine(tmp_path, "local", "ministral-3-8b")
    adaptateur = construire_fournisseur(racine)
    assert adaptateur.version_modele == "local:ministral-3-8b"
    getattr(adaptateur, "fermer", lambda: None)()


def test_fournisseur_local_transmet_l_url_de_l_environnement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("USINE_URL_LLM_LOCAL", "http://hote:9000/v1")
    racine = _racine(tmp_path, "local", "ministral-3-8b")
    adaptateur = construire_fournisseur(racine)
    assert getattr(adaptateur, "_url_base", None) == "http://hote:9000/v1"
    getattr(adaptateur, "fermer", lambda: None)()
