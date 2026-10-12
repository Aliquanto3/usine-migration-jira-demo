"""`PseudonymiseurHmac` : jetons HMAC stables entre instances, table persistante (AD-15)."""

import re
from pathlib import Path

import pytest

from usine.adaptateurs.pseudonymisation import MOTIFS_PAR_DEFAUT, PseudonymiseurHmac
from usine.adaptateurs.stockage_sqlite import TablePseudonymesSqlite
from usine.contrats.erreurs import UsineErreur
from usine.ports import Pseudonymiseur

CLE = b"cle-de-test-fictive"
NUMERO_COMPTE = "FR76 3000 6000 0112 3456 7890 189"
"""Numéro de compte fictif (IBAN de démonstration)."""
TEXTE = f"DEMO-3 : virement refusé sur le compte {NUMERO_COMPTE}."


def _pseudonymiseur(chemin: Path, cle: bytes = CLE) -> PseudonymiseurHmac:
    return PseudonymiseurHmac(cle, MOTIFS_PAR_DEFAUT, TablePseudonymesSqlite(chemin))


def test_implemente_le_port(tmp_path: Path) -> None:
    assert isinstance(_pseudonymiseur(tmp_path / "pseudonymes.sqlite"), Pseudonymiseur)


def test_jeton_stable_entre_deux_processus(tmp_path: Path) -> None:
    # Deux instances sur la même clé et deux tables distinctes : comme deux processus.
    premier = _pseudonymiseur(tmp_path / "a" / "pseudonymes.sqlite")
    second = _pseudonymiseur(tmp_path / "b" / "pseudonymes.sqlite")
    sortie = premier.pseudonymiser(TEXTE)
    assert second.pseudonymiser(TEXTE) == sortie
    assert NUMERO_COMPTE not in sortie
    assert re.search(r"\bCOMPTE_[0-9a-f]{6}\b", sortie)
    assert "DEMO-3" in sortie


def test_jeton_depend_de_la_cle(tmp_path: Path) -> None:
    premier = _pseudonymiseur(tmp_path / "a.sqlite")
    autre = _pseudonymiseur(tmp_path / "b.sqlite", b"autre-cle-fictive")
    assert premier.apercu(TEXTE) != autre.apercu(TEXTE)


def test_reidentification_apres_reouverture(tmp_path: Path) -> None:
    chemin = tmp_path / "pseudonymes.sqlite"
    sortie = _pseudonymiseur(chemin).pseudonymiser(TEXTE)
    assert _pseudonymiseur(chemin).reidentifier(sortie) == TEXTE


def test_apercu_n_ecrit_pas_la_table(tmp_path: Path) -> None:
    chemin = tmp_path / "pseudonymes.sqlite"
    pseudo = _pseudonymiseur(chemin)
    vu = pseudo.apercu(TEXTE)
    assert vu == _pseudonymiseur(tmp_path / "autre.sqlite").pseudonymiser(TEXTE)
    assert pseudo.reidentifier(vu) == vu
    (jeton,) = re.findall(r"\bCOMPTE_[0-9a-f]{6}\b", vu)
    assert TablePseudonymesSqlite(chemin).lire([jeton]) == {}


def test_jeton_inconnu_garde(tmp_path: Path) -> None:
    pseudo = _pseudonymiseur(tmp_path / "pseudonymes.sqlite")
    assert pseudo.reidentifier("COMPTE_abcdef et DEMO-1") == "COMPTE_abcdef et DEMO-1"


@pytest.mark.parametrize("cle", [b"", b"cle-courte", b"   " + b"x" * 15])
def test_cle_vide_ou_courte_refusee(tmp_path: Path, cle: bytes) -> None:
    with pytest.raises(UsineErreur, match="USINE_CLE_PSEUDO"):
        _pseudonymiseur(tmp_path / "pseudonymes.sqlite", cle)


def test_type_du_plus_long_dans_un_groupe(tmp_path: Path) -> None:
    motifs = {"PREFIXE": r"compte FR\d{2}", "COMPTE": MOTIFS_PAR_DEFAUT["COMPTE"]}
    pseudo = PseudonymiseurHmac(CLE, motifs, TablePseudonymesSqlite(tmp_path / "p.sqlite"))
    texte = f"Virement sur le compte {NUMERO_COMPTE}."
    sortie = pseudo.pseudonymiser(texte)
    assert re.fullmatch(r"Virement sur le COMPTE_[0-9a-f]{6}\.", sortie)
    assert pseudo.reidentifier(sortie) == texte


def test_motif_court_ne_masque_pas_un_motif_long(tmp_path: Path) -> None:
    motifs = {"PAYS": r"FR\d{2}", "COMPTE": MOTIFS_PAR_DEFAUT["COMPTE"]}
    pseudo = PseudonymiseurHmac(CLE, motifs, TablePseudonymesSqlite(tmp_path / "p.sqlite"))
    sortie = pseudo.pseudonymiser(TEXTE)
    assert re.fullmatch(r"DEMO-3 : virement refusé sur le compte COMPTE_[0-9a-f]{6}\.", sortie)
    assert "3000" not in sortie
    assert pseudo.reidentifier(sortie) == TEXTE


def test_correspondance_a_cheval_sur_une_cle_de_ticket(tmp_path: Path) -> None:
    motifs = {"IDENTIFIANT": r"\d{4}-\d{4}-\d{4}"}
    pseudo = PseudonymiseurHmac(CLE, motifs, TablePseudonymesSqlite(tmp_path / "p.sqlite"))
    texte = "Dossier ABC-2024-5678-9012 ; voir DEMO-3."
    sortie = pseudo.pseudonymiser(texte)
    assert "5678" not in sortie
    assert "9012" not in sortie
    assert re.search(r"\bIDENTIFIANT_[0-9a-f]{6}\b", sortie)
    assert re.search(r"\bABC-2024\b", sortie)  # la clé chevauchée reste intacte
    assert "DEMO-3" in sortie
    assert pseudo.reidentifier(sortie) == texte


def test_correspondance_interne_a_une_cle_de_ticket_ignoree(tmp_path: Path) -> None:
    pseudo = PseudonymiseurHmac(
        CLE, {"IDENTIFIANT": r"\d{6}"}, TablePseudonymesSqlite(tmp_path / "p.sqlite")
    )
    assert pseudo.pseudonymiser("Voir DEMO-204518.") == "Voir DEMO-204518."


@pytest.mark.parametrize("type_jeton", ["compte", "COMPTE1", "_COMPTE", "COMPTE_"])
def test_type_de_jeton_invalide(tmp_path: Path, type_jeton: str) -> None:
    with pytest.raises(UsineErreur, match="type de jeton invalide"):
        PseudonymiseurHmac(CLE, {type_jeton: r"\d+"}, TablePseudonymesSqlite(tmp_path / "p.db"))
