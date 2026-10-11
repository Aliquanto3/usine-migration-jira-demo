"""Indicateur IND-1 et Météo par Entité (Story 0.4, FR-15, FR-16)."""

from collections.abc import Iterable
from datetime import UTC, date, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import polars as pl
import pytest
import yaml

from tests.unit.domaine.constructeur import Flux
from usine.adaptateurs.journal import SourceJournal
from usine.config import charger_yaml
from usine.contrats.calcul import SCHEMA_INDICATEUR
from usine.contrats.calendrier import jour_ouvre_de
from usine.contrats.config import ConfigProgramme, GrilleMeteo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement
from usine.contrats.meteo import CodeIndicateur, Couleur, MeteoEntite, Operateur
from usine.contrats.schemas import valider
from usine.contrats.tickets import STATUTS_FERMES, Champ
from usine.contrats.versions import version_grille
from usine.domaine.instantanes import tickets_etats
from usine.domaine.meteo import indicateurs, meteo
from usine.generateur.journal import generer, serialiser_journal

RACINE = Path(__file__).resolve().parents[3]
CHEMIN_GRILLE = RACINE / "config" / "grille_meteo.yaml"

VENDREDI = date(2026, 10, 2)
LUNDI = date(2026, 10, 5)
VERSION = "abcdef012345"


@pytest.fixture(scope="module")
def grille() -> GrilleMeteo:
    return charger_yaml(CHEMIN_GRILLE, GrilleMeteo)


def _grille(**indicateurs_yaml: Any) -> GrilleMeteo:
    donnees = yaml.safe_load(CHEMIN_GRILLE.read_text(encoding="utf-8"))
    donnees["indicateurs"].update(indicateurs_yaml)
    return GrilleMeteo.model_validate(donnees)


def _ts(jour: int, heure: int) -> datetime:
    return datetime(2026, 10, jour, heure, tzinfo=UTC)


def _meteo(flux: Flux, grille: GrilleMeteo, d: date = LUNDI) -> dict[str, MeteoEntite]:
    etats = tickets_etats(flux.evenements, [d])
    return {m.entite: m for m in meteo(etats, d, ["ENT-A", "ENT-B"], grille, VERSION)}


def test_grille_livree() -> None:
    grille = charger_yaml(CHEMIN_GRILLE, GrilleMeteo)
    ind1 = grille.indicateurs[CodeIndicateur.ind_1]
    assert set(grille.indicateurs) == {CodeIndicateur.ind_1}
    assert ind1.active
    assert ind1.seuils[Couleur.rouge] == (Operateur.superieur_ou_egal, Fraction(3))
    assert ind1.seuils[Couleur.orange] == (Operateur.superieur_ou_egal, Fraction(1))
    assert grille.garde_fous.ind4_min_tests_executes == 20
    assert grille.garde_fous.ind7_min_entrees_fenetre_glissante == 5


def test_rouge(grille: GrilleMeteo) -> None:
    flux = Flux()
    for numero in (10, 2, 7):
        flux.anomalie(f"DEMO-{numero}", _ts(1, numero))
    resultat = _meteo(flux, grille)["ENT-A"]
    assert resultat.couleur is Couleur.rouge
    (regle,) = resultat.regles
    assert regle.code is CodeIndicateur.ind_1
    assert (regle.numerateur, regle.denominateur) == (3, 1)
    assert regle.operateur is Operateur.superieur_ou_egal
    assert (regle.seuil_numerateur, regle.seuil_denominateur) == (3, 1)
    assert regle.tickets_en_cause == ("DEMO-2", "DEMO-7", "DEMO-10")


def test_orange(grille: GrilleMeteo) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    resultat = _meteo(flux, grille)["ENT-A"]
    assert resultat.couleur is Couleur.orange
    (regle,) = resultat.regles
    assert regle.couleur is Couleur.orange
    assert (regle.numerateur, regle.seuil_numerateur) == (1, 1)
    assert regle.tickets_en_cause == ("DEMO-1",)


def test_vert(grille: GrilleMeteo) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9), gravite="majeure")
    flux.anomalie("DEMO-2", _ts(1, 9), entite="ENT-A", gravite="majeure", statut="en_analyse")
    flux.anomalie("DEMO-3", _ts(1, 10))
    flux.transition("DEMO-3", _ts(2, 9), "nouvelle", "rejetee")
    resultats = _meteo(flux, grille)
    for entite in ("ENT-A", "ENT-B"):  # ENT-B : aucun ticket
        assert resultats[entite].couleur is Couleur.vert
        assert resultats[entite].regles == ()
    table = indicateurs(tickets_etats(flux.evenements, [LUNDI]), LUNDI, ["ENT-A", "ENT-B"], grille)
    assert table["numerateur"].to_list() == [0, 0]
    assert table["denominateur"].to_list() == [1, 1]


def test_coupure(grille: GrilleMeteo) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(3, 23))  # samedi 23 h UTC : compté le lundi
    flux.anomalie("DEMO-2", _ts(6, 9))  # mardi : après D
    resultat = _meteo(flux, grille)["ENT-A"]
    assert resultat.couleur is Couleur.orange
    assert resultat.regles[0].tickets_en_cause == ("DEMO-1",)
    assert _meteo(flux, grille, VENDREDI)["ENT-A"].couleur is Couleur.vert


def test_fermeture(grille: GrilleMeteo) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    flux.transition("DEMO-1", _ts(1, 10), "nouvelle", "en_correction")
    flux.transition("DEMO-1", _ts(1, 11), "en_correction", "a_retester")
    flux.transition("DEMO-1", _ts(5, 9), "a_retester", "fermee")
    assert _meteo(flux, grille, LUNDI)["ENT-A"].couleur is Couleur.vert
    assert _meteo(flux, grille, VENDREDI)["ENT-A"].couleur is Couleur.orange


def test_version_et_ordre_des_entites(grille: GrilleMeteo) -> None:
    etats = tickets_etats([], [LUNDI])
    resultats = meteo(etats, LUNDI, ["ENT-B", "ENT-A"], grille, VERSION)
    assert [m.entite for m in resultats] == ["ENT-B", "ENT-A"]
    assert all(m.version_grille == VERSION and m.date_arrete == LUNDI for m in resultats)


def test_indicateur_inactif() -> None:
    grille = _grille(**{"IND-1": {"libelle": "x", "active": False, "seuils": {"rouge": ">= 1"}}})
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    assert _meteo(flux, grille)["ENT-A"].couleur is Couleur.vert
    etats = tickets_etats(flux.evenements, [LUNDI])
    assert indicateurs(etats, LUNDI, ["ENT-A"], grille).is_empty()


def test_indicateur_non_implemente() -> None:
    grille = _grille(**{"IND-2": {"libelle": "Âge", "seuils": {"rouge": "> 10"}}})
    etats = tickets_etats([], [LUNDI])
    with pytest.raises(UsineErreur, match="IND-2"):
        meteo(etats, LUNDI, ["ENT-A"], grille, VERSION)
    with pytest.raises(UsineErreur, match="IND-2"):
        indicateurs(etats, LUNDI, ["ENT-A"], grille)


def test_indicateur_non_implemente_inactif_ignore() -> None:
    grille = _grille(**{"IND-2": {"libelle": "Âge", "active": False, "seuils": {"rouge": "> 1"}}})
    assert meteo(tickets_etats([], [LUNDI]), LUNDI, ["ENT-A"], grille, VERSION)[0].couleur is (
        Couleur.vert
    )


def test_entites_en_double(grille: GrilleMeteo) -> None:
    with pytest.raises(UsineErreur, match="ENT-A"):
        meteo(tickets_etats([], [LUNDI]), LUNDI, ["ENT-A", "ENT-A"], grille, VERSION)


def test_table_des_indicateurs(grille: GrilleMeteo) -> None:
    flux = Flux()
    for numero in range(1, 4):
        flux.anomalie(f"DEMO-{numero}", _ts(1, 8 + numero))
    flux.anomalie("DEMO-4", _ts(1, 9), entite="ENT-B")
    etats = tickets_etats(flux.evenements, [LUNDI])
    table = indicateurs(etats, LUNDI, ["ENT-A", "ENT-B"], grille)
    valider(table, SCHEMA_INDICATEUR)
    assert table.select("entite", "code", "statut", "motif", "numerateur", "couleur").rows() == [
        ("ENT-A", "IND-1", "evalue", "", 3, "rouge"),
        ("ENT-B", "IND-1", "evalue", "", 1, "orange"),
    ]
    assert table.select(pl.col("couleur").max()).item() == "rouge"
    meteos = meteo(etats, LUNDI, ["ENT-A", "ENT-B"], grille, VERSION)
    assert table["couleur"].to_list() == [m.couleur.value for m in meteos]


def test_date_d_arrete_posterieure_a_l_etat(grille: GrilleMeteo) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    etats = tickets_etats(flux.evenements, [VENDREDI])
    with pytest.raises(UsineErreur, match="2026-10-05"):
        meteo(etats, LUNDI, ["ENT-A"], grille, VERSION)
    with pytest.raises(UsineErreur, match="2026-10-05"):
        indicateurs(etats, LUNDI, ["ENT-A"], grille)


def test_date_d_arrete_sans_ticket_est_verte(grille: GrilleMeteo) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(5, 9))  # créée le lundi : aucun ticket le vendredi
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI])
    assert etats.filter(pl.col("date") == VENDREDI).is_empty()
    (resultat,) = meteo(etats, VENDREDI, ["ENT-A"], grille, VERSION)
    assert resultat.couleur is Couleur.vert
    table = indicateurs(etats, VENDREDI, ["ENT-A"], grille)
    assert table["numerateur"].to_list() == [0]
    # Date antérieure à toute ligne de la table : aucun ticket non plus.
    assert meteo(etats, date(2026, 9, 30), ["ENT-A"], grille, VERSION)[0].couleur is Couleur.vert
    assert meteo(etats, LUNDI, ["ENT-A"], grille, VERSION)[0].couleur is Couleur.orange


def _bloquantes_ouvertes(evenements: Iterable[Evenement], d: date) -> dict[str, list[str]]:
    """Clés des bloquantes ouvertes par Entité, rejouées directement sur les événements."""
    etat: dict[str, dict[Champ, str | None]] = {}
    for evenement in evenements:
        if jour_ouvre_de(evenement.horodatage) > d:
            continue
        attributs = etat.setdefault(evenement.cle_ticket, {})
        if evenement.champ is not None:
            attributs[evenement.champ] = evenement.vers
    fermes = {s.value for s in STATUTS_FERMES}
    cles: dict[str, list[str]] = {}
    for cle, a in etat.items():
        statut = a.get(Champ.statut)
        if a.get(Champ.gravite) == "bloquante" and statut is not None and statut not in fermes:
            cles.setdefault(str(a[Champ.entite]), []).append(cle)
    return {
        entite: sorted(liste, key=lambda c: int(c.split("-")[1])) for entite, liste in cles.items()
    }


def test_journal_genere(tmp_path: Path) -> None:
    config = charger_yaml(RACINE / "config" / "programme.yaml", ConfigProgramme)
    chemin = tmp_path / "journal.jsonl"
    chemin.write_bytes(serialiser_journal(generer(config, 42, date(2026, 10, 12))))
    source = SourceJournal(chemin)
    evenements = list(source.evenements())
    d = source.entete.date_injection
    entites = [e.code for e in config.entites]
    assert entites == ["ENT-A", "ENT-B"]
    grille = charger_yaml(CHEMIN_GRILLE, GrilleMeteo)
    version = version_grille(CHEMIN_GRILLE.read_bytes())
    resultats = meteo(tickets_etats(evenements, [d]), d, entites, grille, version)
    attendus = _bloquantes_ouvertes(evenements, d)
    assert any(r.couleur is not Couleur.vert for r in resultats)
    for resultat in resultats:
        MeteoEntite.model_validate(resultat.model_dump())
        cles = attendus.get(resultat.entite, [])
        nombre = len(cles)
        couleur = Couleur.rouge if nombre >= 3 else Couleur.orange if nombre >= 1 else Couleur.vert
        assert resultat.couleur is couleur, resultat.entite
        assert resultat.version_grille == version
        if couleur is Couleur.vert:
            assert resultat.regles == ()
        else:
            (regle,) = resultat.regles
            assert regle.numerateur == nombre
            assert list(regle.tickets_en_cause) == cles
