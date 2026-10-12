"""`PseudonymiseurPresidio` : reconnaisseurs maison, entités spaCy, balayage FR-4 (Story 6.2)."""

import re
import tempfile
from datetime import date
from functools import cache
from pathlib import Path

import pytest
from presidio_analyzer import RecognizerResult

from usine.adaptateurs.presidio import PseudonymiseurPresidio
from usine.adaptateurs.pseudonymisation import PseudonymiseurHmac
from usine.adaptateurs.stockage_sqlite import TablePseudonymesSqlite
from usine.composition import _motifs_pseudonymisation
from usine.config import charger_yaml
from usine.contrats.config import ConfigProgramme, ConfigPseudonymisation, Reconnaisseur
from usine.contrats.erreurs import UsineErreur
from usine.contrats.tickets import Champ
from usine.generateur.journal import Generation, generer
from usine.ports import Pseudonymiseur

RACINE = Path(__file__).resolve().parents[4]
REPERTOIRE_CONFIG = RACINE / "config"
PROGRAMME_REDUIT = RACINE / "tests" / "unit" / "generateur" / "programme_reduit.yaml"
GRAINES = (42, 86, 153, 162, 234)
"""Graines du programme réduit, comme `tests/unit/generateur/test_journal.py`."""
DATE_GENERATION = date(2026, 10, 12)
CLE = b"cle-de-test-fictive"

PHRASE = (
    "Cas cité par l'Entité ENT-B : client Mme Simulie MAQUETTEAU, compte"
    " FR42 9999 9123 4567 8901 2345 678, identifiant client 9912345670 (voir DEMO-204518)."
)
VALEURS = {
    "CLIENT": "Mme Simulie MAQUETTEAU",
    "COMPTE": "FR42 9999 9123 4567 8901 2345 678",
    "ID_CLIENT": "9912345670",
}
JETON = re.compile(r"\b[A-Z][A-Z_]*_[0-9a-f]{6}\b")


@cache
def _config_livree() -> ConfigPseudonymisation:
    return charger_yaml(REPERTOIRE_CONFIG / "pseudonymisation.yaml", ConfigPseudonymisation)


@cache
def _presidio_partage() -> PseudonymiseurPresidio:
    """Moteur construit une fois par session ; chaque test lui donne sa propre table."""
    table = TablePseudonymesSqlite(Path(tempfile.mkdtemp(prefix="pseudo-")) / "p.sqlite")
    return PseudonymiseurPresidio(CLE, _config_livree(), table)


@pytest.fixture
def presidio(tmp_path: Path) -> PseudonymiseurPresidio:
    return _presidio_partage().avec_table(TablePseudonymesSqlite(tmp_path / "presidio.sqlite"))


@pytest.fixture
def regex(tmp_path: Path) -> PseudonymiseurHmac:
    motifs = _motifs_pseudonymisation(REPERTOIRE_CONFIG)
    return PseudonymiseurHmac(CLE, motifs, TablePseudonymesSqlite(tmp_path / "regex.sqlite"))


def test_implemente_le_port(presidio: PseudonymiseurPresidio) -> None:
    assert isinstance(presidio, Pseudonymiseur)


def test_phrase_generee_memes_jetons_que_le_moteur_regex(
    presidio: PseudonymiseurPresidio, regex: PseudonymiseurHmac
) -> None:
    sortie = presidio.pseudonymiser(PHRASE)
    assert sortie == regex.pseudonymiser(PHRASE)
    for type_jeton, valeur in VALEURS.items():
        assert valeur not in sortie
        assert presidio.jeton(type_jeton, valeur) in sortie
    assert "DEMO-204518" in sortie
    assert "ENT-B" in sortie


def test_cle_de_ticket_inchangee(presidio: PseudonymiseurPresidio) -> None:
    assert presidio.pseudonymiser("voir DEMO-204518") == "voir DEMO-204518"


def test_entite_spacy_seule(presidio: PseudonymiseurPresidio) -> None:
    sortie = presidio.pseudonymiser("Jean Dupont a validé.")
    assert sortie == f"{presidio.jeton('PERSON', 'Jean Dupont')} a validé."


def test_reconnaisseur_maison_prime_sur_entite_spacy(presidio: PseudonymiseurPresidio) -> None:
    texte = "Relance de Mme Simulie MAQUETTEAU hier."
    sortie = presidio.pseudonymiser(texte)
    assert sortie == f"Relance de {presidio.jeton('CLIENT', VALEURS['CLIENT'])} hier."
    assert "PERSON_" not in sortie


def test_entite_spacy_partiellement_chevauchante_garde_sa_partie_hors_plage(
    presidio: PseudonymiseurPresidio, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Une entité spaCy qui déborde d'une plage maison : la partie qui déborde est remplacée."""
    texte = "Relance de Mme Simulie MAQUETTEAU Dupont hier."
    client = texte.index("Mme")
    personne = texte.index("Simulie")
    fin_personne = texte.index(" hier")
    nom = RecognizerResult.RECOGNIZER_NAME_KEY
    resultats = [
        RecognizerResult(
            "CLIENT",
            client,
            personne + len("Simulie MAQUETTEAU"),
            0.85,
            recognition_metadata={nom: "maison:CLIENT"},
        ),
        RecognizerResult(
            "PERSON", personne, fin_personne, 0.85, recognition_metadata={nom: "SpacyRecognizer"}
        ),
    ]
    monkeypatch.setattr(presidio._analyseur, "analyze", lambda *_a, **_k: resultats)
    sortie = presidio.pseudonymiser(texte)
    assert "Dupont" not in sortie
    assert sortie == (
        f"Relance de {presidio.jeton('CLIENT', VALEURS['CLIENT'])}"
        f" {presidio.jeton('PERSON', 'Dupont')} hier."
    )


def test_reidentifier_et_apercu(presidio: PseudonymiseurPresidio, tmp_path: Path) -> None:
    vu = presidio.avec_table(TablePseudonymesSqlite(tmp_path / "apercu.sqlite"))
    apercu = vu.apercu(PHRASE)
    assert vu.reidentifier(apercu) == apercu  # `apercu` n'écrit pas la table
    sortie = presidio.pseudonymiser(PHRASE)
    assert sortie == apercu
    assert presidio.reidentifier(sortie) == PHRASE


def test_modele_absent_sans_telechargement(tmp_path: Path) -> None:
    config = ConfigPseudonymisation(modele_spacy="inexistant_xx", entites_presidio=("PERSON",))
    with pytest.raises(UsineErreur, match="inexistant_xx"):
        PseudonymiseurPresidio(CLE, config, TablePseudonymesSqlite(tmp_path / "p.sqlite"))


def test_entite_invalide(tmp_path: Path) -> None:
    config = ConfigPseudonymisation(entites_presidio=("person",))
    with pytest.raises(UsineErreur, match="type de jeton invalide"):
        PseudonymiseurPresidio(CLE, config, TablePseudonymesSqlite(tmp_path / "p.sqlite"))


def test_entite_que_le_modele_ne_produit_pas(tmp_path: Path) -> None:
    config = ConfigPseudonymisation(entites_presidio=("EMAIL_ADDRESS",))
    with pytest.raises(UsineErreur, match="EMAIL_ADDRESS"):
        PseudonymiseurPresidio(CLE, config, TablePseudonymesSqlite(tmp_path / "p.sqlite"))


def test_type_maison_egal_a_une_entite_presidio(tmp_path: Path) -> None:
    config = ConfigPseudonymisation(
        entites_presidio=("PERSON",),
        reconnaisseurs=(Reconnaisseur(type_jeton="PERSON", motif=r"M. [A-Z][a-z]+"),),
    )
    with pytest.raises(UsineErreur, match="PERSON"):
        PseudonymiseurPresidio(CLE, config, TablePseudonymesSqlite(tmp_path / "p.sqlite"))


def test_cle_trop_courte(tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match="USINE_CLE_PSEUDO"):
        PseudonymiseurPresidio(b"court", _config_livree(), TablePseudonymesSqlite(tmp_path / "p"))


# --- Balayage SM-7 : aucun identifiant injecté ne subsiste ---


@cache
def _generation(graine: int) -> Generation:
    return generer(charger_yaml(PROGRAMME_REDUIT, ConfigProgramme), graine, DATE_GENERATION)


def _descriptions(generation: Generation) -> list[str]:
    return [str(e.vers) for e in generation.evenements if e.champ is Champ.description and e.vers]


@pytest.mark.parametrize("graine", GRAINES, ids=lambda g: f"graine-{g}")
def test_balayage_aucun_identifiant_injecte_ne_subsiste(
    graine: int, presidio: PseudonymiseurPresidio, regex: PseudonymiseurHmac
) -> None:
    generation = _generation(graine)
    assert generation.identifiants
    for description in _descriptions(generation):
        sortie_presidio = presidio.apercu(description)
        sortie_regex = regex.apercu(description)
        for identifiant in generation.identifiants:
            assert identifiant.valeur not in sortie_presidio, identifiant
            assert identifiant.valeur not in sortie_regex, identifiant
            if identifiant.valeur in description:
                attendu = presidio.jeton(identifiant.type.value, identifiant.valeur)
                assert attendu in sortie_presidio
                assert attendu in sortie_regex
        for cle in re.findall(r"\bDEMO-\d+\b", description):
            assert re.search(rf"\b{cle}\b", sortie_presidio), cle
            assert re.search(rf"\b{cle}\b", sortie_regex), cle
    assert any(JETON.search(presidio.apercu(d)) for d in _descriptions(generation))
