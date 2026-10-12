"""Indicateurs IND-1 à IND-8, Météo par Entité, Règles déclenchantes et Grille livrée.

Stories 0.4, 3.4, 3.5 et 3.6 ; FR-11, FR-15, FR-16, FR-17, FR-18. Story 3.6 : pire couleur
des indicateurs évalués, sans état d'un jour à l'autre ; toutes les Règles de la couleur
retenue ; tickets en cause par type de règle (FR-17). Story 3.7 (FR-19) : évolution de la
Météo à J-1 et J-5 en Jours ouvrés, lue par `ConsultationPassage.evolution_meteo` sur la Météo
de chaque Jour ouvré calculée par le domaine (D8 : dérivation de lecture, pas de calcul).
"""

import hashlib
import re
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import polars as pl
import pytest
import yaml

from tests.unit.chaine.environnement import DATE_ARRETE, horloge_figee, preparer_racine
from tests.unit.domaine.constructeur import Flux
from usine.adaptateurs.journal import SourceJournal
from usine.composition import lancer_rapport
from usine.config import charger_yaml
from usine.consultation.passage import ConsultationPassage
from usine.contrats.calcul import SCHEMA_INDICATEUR, StatutIndicateur
from usine.contrats.calendrier import (
    fenetre_glissante,
    jour_ouvre_de,
    jour_ouvre_precedent,
    jours_ouvres,
)
from usine.contrats.config import ConfigProgramme, GrilleMeteo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement
from usine.contrats.meteo import CodeIndicateur, Couleur, EvolutionMeteo, MeteoEntite, Operateur
from usine.contrats.passage import (
    CHEMIN_JOURNAL,
    FICHIERS_PASSAGE,
    EnveloppeFichier,
    former_passage_id,
)
from usine.contrats.schemas import valider
from usine.contrats.tickets import (
    SCHEMA_TICKET_ETAT,
    STATUTS_FERMES,
    Champ,
    Phase,
    TypeTicket,
)
from usine.contrats.versions import version_grille
from usine.domaine.instantanes import tickets_etats
from usine.domaine.meteo import indicateurs, meteo, phase_en_cours, verifier_grille
from usine.generateur.journal import generer, serialiser_journal

RACINE = Path(__file__).resolve().parents[3]
CHEMIN_GRILLE = RACINE / "config" / "grille_meteo.yaml"
CHEMIN_PROGRAMME = RACINE / "tests/unit/generateur/programme_reduit.yaml"

VENDREDI = date(2026, 10, 2)
LUNDI = date(2026, 10, 5)
VERSION = "abcdef012345"
ANCRAGE = date(2026, 9, 14)
"""Ancrage des semaines : LUNDI est en semaine 4 (recette), VENDREDI en semaine 3 (chevauchement
migration à blanc / recette, la recette l'emporte)."""
J5 = jour_ouvre_precedent(LUNDI, 5)
"""J-5 de LUNDI : lundi 2026-09-28, semaine 3 (recette)."""

PROGRAMME = charger_yaml(CHEMIN_PROGRAMME, ConfigProgramme)
"""Programme réduit : ENT-A et ENT-B en Vague V1 ; recette en semaines 3 à 6."""


def _donnees_grille() -> dict[str, Any]:
    donnees: dict[str, Any] = yaml.safe_load(CHEMIN_GRILLE.read_text(encoding="utf-8"))
    return donnees


def _grille(**indicateurs_yaml: Any) -> GrilleMeteo:
    """Grille livrée, règles remplacées par `indicateurs_yaml`."""
    donnees = _donnees_grille()
    donnees["indicateurs"].update(indicateurs_yaml)
    return GrilleMeteo.model_validate(donnees)


def _grille_seule(*codes: str, **indicateurs_yaml: Any) -> GrilleMeteo:
    """Grille livrée où seuls `codes` (et les règles de `indicateurs_yaml`) sont actifs."""
    donnees = _donnees_grille()
    for code, regle in donnees["indicateurs"].items():
        regle["active"] = code in codes
    donnees["indicateurs"].update(indicateurs_yaml)
    return GrilleMeteo.model_validate(donnees)


@pytest.fixture(scope="module")
def grille() -> GrilleMeteo:
    """Grille livrée réduite à IND-1 (tests du walking skeleton)."""
    return _grille_seule("IND-1")


@pytest.fixture(scope="module")
def grille_livree() -> GrilleMeteo:
    return charger_yaml(CHEMIN_GRILLE, GrilleMeteo)


def _ts(jour: int, heure: int) -> datetime:
    return datetime(2026, 10, jour, heure, tzinfo=UTC)


def _a(d: date, heure: int = 9) -> datetime:
    return datetime(d.year, d.month, d.day, heure, tzinfo=UTC)


def _calculer_meteo(
    etats: pl.DataFrame,
    d: date,
    entites: list[str],
    grille: GrilleMeteo,
    ancrage: date = ANCRAGE,
) -> tuple[MeteoEntite, ...]:
    return meteo(etats, d, entites, grille, VERSION, programme=PROGRAMME, ancrage=ancrage)


def _calculer_indicateurs(
    etats: pl.DataFrame,
    d: date,
    entites: list[str],
    grille: GrilleMeteo,
    ancrage: date = ANCRAGE,
) -> pl.DataFrame:
    return indicateurs(etats, d, entites, grille, programme=PROGRAMME, ancrage=ancrage)


def _meteo(flux: Flux, grille: GrilleMeteo, d: date = LUNDI) -> dict[str, MeteoEntite]:
    etats = tickets_etats(flux.evenements, [d])
    return {m.entite: m for m in _calculer_meteo(etats, d, ["ENT-A", "ENT-B"], grille)}


SEUILS_LIVRES: dict[CodeIndicateur, dict[Couleur, tuple[Operateur, Fraction]]] = {
    CodeIndicateur.ind_1: {
        Couleur.rouge: (Operateur.superieur_ou_egal, Fraction(3)),
        Couleur.orange: (Operateur.superieur_ou_egal, Fraction(1)),
    },
    CodeIndicateur.ind_2: {
        Couleur.rouge: (Operateur.superieur, Fraction(10)),
        Couleur.orange: (Operateur.superieur, Fraction(5)),
    },
    CodeIndicateur.ind_3: {
        Couleur.rouge: (Operateur.superieur_ou_egal, Fraction(20)),
        Couleur.orange: (Operateur.superieur_ou_egal, Fraction(10)),
        Couleur.jaune: (Operateur.superieur_ou_egal, Fraction(5)),
    },
    CodeIndicateur.ind_4: {
        Couleur.rouge: (Operateur.superieur_ou_egal, Fraction(1, 5)),
        Couleur.orange: (Operateur.superieur_ou_egal, Fraction(1, 10)),
        Couleur.jaune: (Operateur.superieur_ou_egal, Fraction(1, 20)),
    },
    CodeIndicateur.ind_5: {Couleur.rouge: (Operateur.superieur_ou_egal, Fraction(1))},
    CodeIndicateur.ind_6: {
        Couleur.orange: (Operateur.superieur_ou_egal, Fraction(2)),
        Couleur.jaune: (Operateur.superieur_ou_egal, Fraction(1)),
    },
    CodeIndicateur.ind_7: {
        Couleur.orange: (Operateur.superieur, Fraction(3, 2)),
        Couleur.jaune: (Operateur.superieur, Fraction(1)),
    },
    CodeIndicateur.ind_8: {
        Couleur.orange: (Operateur.superieur_ou_egal, Fraction(1, 20)),
        Couleur.jaune: (Operateur.superieur_ou_egal, Fraction(3, 100)),
    },
}


def test_grille_livree() -> None:
    grille = charger_yaml(CHEMIN_GRILLE, GrilleMeteo)
    assert grille.version == 3
    assert set(grille.indicateurs) == set(CodeIndicateur)
    for code, seuils in SEUILS_LIVRES.items():
        regle = grille.indicateurs[code]
        assert dict(regle.seuils) == seuils, code
        assert regle.active is True, code
        assert regle.libelle
    assert grille.garde_fous.ind4_min_tests_executes == 20
    assert grille.garde_fous.ind7_min_entrees_fenetre_glissante == 5
    octets = CHEMIN_GRILLE.read_bytes()
    empreinte = version_grille(octets)
    assert re.fullmatch(r"[0-9a-f]{12}", empreinte)
    assert empreinte == hashlib.sha256(octets).hexdigest()[:12]
    assert verifier_grille(grille, str(CHEMIN_GRILLE)) is grille


def _regle(seuils: dict[str, str], active: bool = True) -> dict[str, Any]:
    return {"libelle": "Règle d'essai", "active": active, "seuils": seuils}


@pytest.mark.parametrize(
    ("code", "seuils", "attendus"),
    [
        (
            "IND-1",
            {"rouge": ">= 3", "orange": ">= 4"},
            ["grille.yaml", "IND-1", "orange « >= 4 »", "rouge « >= 3 »"],
        ),
        (
            "IND-3",
            {"rouge": ">= 20", "orange": ">= 10", "jaune": ">= 12"},
            ["IND-3", "jaune « >= 12 »", "orange « >= 10 »"],
        ),
        ("IND-3", {"rouge": ">= 3", "jaune": ">= 5"}, ["IND-3", "jaune « >= 5 »", "rouge"]),
        ("IND-1", {"rouge": ">= 3", "orange": "> 3"}, ["IND-1", "orange « > 3 »"]),
        (
            "IND-4",
            {"rouge": ">= 0.20", "orange": ">= 0.25"},
            ["IND-4", "orange « >= 0.25 »", "rouge « >= 0.2 »"],
        ),
    ],
    ids=["orange-rouge", "jaune-orange", "non-adjacente", "operateur-strict", "decimal"],
)
def test_grille_incoherente_refusee(code: str, seuils: dict[str, str], attendus: list[str]) -> None:
    grille = _grille(**{code: _regle(seuils)})
    with pytest.raises(UsineErreur) as erreur:
        verifier_grille(grille, "grille.yaml")
    message = str(erreur.value)
    assert message.startswith("grille.yaml : règle ")
    for attendu in attendus:
        assert attendu in message


def test_regle_inactive_incoherente_refusee() -> None:
    grille = _grille(**{"IND-2": _regle({"rouge": "> 5", "orange": "> 10"}, active=False)})
    with pytest.raises(UsineErreur, match=r"IND-2 : seuil orange « > 10 »"):
        verifier_grille(grille, "grille.yaml")


@pytest.mark.parametrize(
    "seuils",
    [{"rouge": "> 3", "orange": ">= 3"}, {"rouge": ">= 3", "orange": ">= 3"}],
    ids=["operateur-strict-inverse", "seuils-egaux"],
)
def test_grille_coherente_acceptee(seuils: dict[str, str]) -> None:
    grille = _grille(**{"IND-1": _regle(seuils)})
    assert verifier_grille(grille, "grille.yaml") is grille


def _ecrire_grille(tmp_path: Path, modifier: Callable[[dict[str, Any]], None]) -> Path:
    donnees = _donnees_grille()
    modifier(donnees)
    chemin = tmp_path / "grille_meteo.yaml"
    chemin.write_text(yaml.safe_dump(donnees, allow_unicode=True), encoding="utf-8")
    return chemin


def test_indicateur_inconnu_refuse(tmp_path: Path) -> None:
    chemin = _ecrire_grille(
        tmp_path, lambda d: d["indicateurs"].update({"IND-9": _regle({"rouge": ">= 1"})})
    )
    with pytest.raises(UsineErreur) as erreur:
        charger_yaml(chemin, GrilleMeteo)
    assert str(chemin) in str(erreur.value)
    assert "IND-9" in str(erreur.value)


def test_couleur_inconnue_refusee(tmp_path: Path) -> None:
    chemin = _ecrire_grille(
        tmp_path, lambda d: d["indicateurs"]["IND-1"]["seuils"].update({"violet": ">= 2"})
    )
    with pytest.raises(UsineErreur) as erreur:
        charger_yaml(chemin, GrilleMeteo)
    assert str(chemin) in str(erreur.value)
    assert "violet" in str(erreur.value)


def test_seuil_decimal_exact() -> None:
    grille = _grille(**{"IND-4": _regle({"rouge": ">= 0.20"}, active=False)})
    seuil = grille.indicateurs[CodeIndicateur.ind_4].seuils[Couleur.rouge]
    assert seuil == (Operateur.superieur_ou_egal, Fraction(1, 5))


# --- IND-1 (Grille réduite à IND-1) ---


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
    etats = tickets_etats(flux.evenements, [LUNDI])
    table = _calculer_indicateurs(etats, LUNDI, ["ENT-A", "ENT-B"], grille)
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
    resultats = _calculer_meteo(etats, LUNDI, ["ENT-B", "ENT-A"], grille)
    assert [m.entite for m in resultats] == ["ENT-B", "ENT-A"]
    assert all(m.version_grille == VERSION and m.date_arrete == LUNDI for m in resultats)


def test_indicateur_inactif() -> None:
    grille = _grille_seule(
        **{"IND-1": {"libelle": "x", "active": False, "seuils": {"rouge": ">= 1"}}}
    )
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    assert _meteo(flux, grille)["ENT-A"].couleur is Couleur.vert
    etats = tickets_etats(flux.evenements, [LUNDI])
    assert _calculer_indicateurs(etats, LUNDI, ["ENT-A"], grille).is_empty()


def test_entites_en_double(grille: GrilleMeteo) -> None:
    with pytest.raises(UsineErreur, match="ENT-A"):
        _calculer_meteo(tickets_etats([], [LUNDI]), LUNDI, ["ENT-A", "ENT-A"], grille)


def test_table_des_indicateurs(grille: GrilleMeteo) -> None:
    flux = Flux()
    for numero in range(1, 4):
        flux.anomalie(f"DEMO-{numero}", _ts(1, 8 + numero))
    flux.anomalie("DEMO-4", _ts(1, 9), entite="ENT-B")
    etats = tickets_etats(flux.evenements, [LUNDI])
    table = _calculer_indicateurs(etats, LUNDI, ["ENT-A", "ENT-B"], grille)
    valider(table, SCHEMA_INDICATEUR)
    assert table.select("entite", "code", "statut", "motif", "numerateur", "couleur").rows() == [
        ("ENT-A", "IND-1", "evalue", "", 3, "rouge"),
        ("ENT-B", "IND-1", "evalue", "", 1, "orange"),
    ]
    assert table.select(pl.col("couleur").max()).item() == "rouge"
    meteos = _calculer_meteo(etats, LUNDI, ["ENT-A", "ENT-B"], grille)
    assert table["couleur"].to_list() == [m.couleur.value for m in meteos]


def test_date_d_arrete_posterieure_a_l_etat(grille: GrilleMeteo) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(1, 9))
    etats = tickets_etats(flux.evenements, [VENDREDI])
    with pytest.raises(UsineErreur, match="2026-10-05"):
        _calculer_meteo(etats, LUNDI, ["ENT-A"], grille)
    with pytest.raises(UsineErreur, match="2026-10-05"):
        _calculer_indicateurs(etats, LUNDI, ["ENT-A"], grille)


def test_date_d_arrete_sans_ticket_est_verte(grille: GrilleMeteo) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _ts(5, 9))  # créée le lundi : aucun ticket le vendredi
    etats = tickets_etats(flux.evenements, [VENDREDI, LUNDI])
    assert etats.filter(pl.col("date") == VENDREDI).is_empty()
    (resultat,) = _calculer_meteo(etats, VENDREDI, ["ENT-A"], grille)
    assert resultat.couleur is Couleur.vert
    table = _calculer_indicateurs(etats, VENDREDI, ["ENT-A"], grille)
    assert table["numerateur"].to_list() == [0]
    # Date antérieure à toute ligne de la table : aucun ticket non plus.
    assert _calculer_meteo(etats, date(2026, 9, 30), ["ENT-A"], grille)[0].couleur is Couleur.vert
    assert _calculer_meteo(etats, LUNDI, ["ENT-A"], grille)[0].couleur is Couleur.orange


@pytest.mark.parametrize(
    ("date_arrete", "dates_calculees"),
    [
        (date(2026, 10, 3), [VENDREDI, LUNDI]),  # samedi entre deux dates calculées
        (date(2026, 10, 1), [date(2026, 9, 30), VENDREDI]),  # trou : jeudi non calculé
    ],
    ids=["week-end", "trou"],
)
def test_date_d_arrete_non_calculee_refusee(
    grille: GrilleMeteo, date_arrete: date, dates_calculees: list[date]
) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", datetime(2026, 9, 29, 9, tzinfo=UTC))
    etats = tickets_etats(flux.evenements, dates_calculees)
    with pytest.raises(UsineErreur, match=date_arrete.isoformat()):
        _calculer_meteo(etats, date_arrete, ["ENT-A"], grille)
    with pytest.raises(UsineErreur, match=date_arrete.isoformat()):
        _calculer_indicateurs(etats, date_arrete, ["ENT-A"], grille)


@pytest.mark.parametrize(
    ("nombre", "couleur"),
    [(0, Couleur.vert), (2, Couleur.orange), (3, Couleur.rouge)],
)
def test_operateur_strict(nombre: int, couleur: Couleur) -> None:
    grille = _grille_seule(
        **{"IND-1": {"libelle": "x", "seuils": {"rouge": "> 2", "orange": "> 0"}}}
    )
    flux = Flux()
    for numero in range(1, nombre + 1):
        flux.anomalie(f"DEMO-{numero}", _ts(1, 8 + numero))
    resultat = _meteo(flux, grille)["ENT-A"]
    assert resultat.couleur is couleur
    if couleur is Couleur.vert:
        assert resultat.regles == ()
    else:
        (regle,) = resultat.regles
        assert regle.operateur is Operateur.superieur
        assert regle.numerateur == nombre


# --- IND-2 à IND-8 (Story 3.5) ---


def _cas(
    flux: Flux,
    cle: str,
    d: date,
    statut: str,
    phase: str = "recette",
    entite: str = "ENT-A",
) -> None:
    flux.creer(
        cle,
        TypeTicket.cas_de_test,
        _a(d),
        {
            Champ.statut_test: statut,
            Champ.entite: entite,
            Champ.vague: "V1",
            Champ.domaine: "paie",
            Champ.phase: phase,
        },
    )


def _certification(flux: Flux, cle: str, statut: str, vague: str = "V1") -> None:
    flux.creer(
        cle,
        TypeTicket.certification,
        _a(date(2026, 9, 21)),
        {Champ.statut_certification: statut, Champ.entite: "ENT-A", Champ.vague: vague},
    )


def _campagne(flux: Flux, ko: int, executes: int, d: date = J5, debut: int = 100) -> None:
    """`executes` Cas de test de recette créés en `d`, dont `ko` KO (les premiers numéros)."""
    for rang in range(executes):
        _cas(flux, f"DEMO-{debut + rang}", d, "ko" if rang < ko else "ok")


def _etats(flux: Flux, d: date = LUNDI) -> pl.DataFrame:
    """État des tickets sur chaque Jour ouvré de J-5 à `d`."""
    return tickets_etats(flux.evenements, jours_ouvres(jour_ouvre_precedent(d, 5), d))


def _ligne(
    flux: Flux,
    code: str,
    grille: GrilleMeteo | None = None,
    d: date = LUNDI,
    ancrage: date = ANCRAGE,
) -> dict[str, Any]:
    """Ligne de `code` pour ENT-A dans la table des indicateurs."""
    grille = grille or _grille_seule(code)
    table = _calculer_indicateurs(_etats(flux, d), d, ["ENT-A"], grille, ancrage)
    (ligne,) = table.filter(pl.col("code") == code).to_dicts()
    return ligne


def _regle_unique(
    flux: Flux, code: str, d: date = LUNDI, ancrage: date = ANCRAGE
) -> tuple[Couleur, tuple[int, int], tuple[str, ...]]:
    """Couleur, valeur et tickets en cause de la seule Règle déclenchante d'ENT-A."""
    (resultat,) = _calculer_meteo(_etats(flux, d), d, ["ENT-A"], _grille_seule(code), ancrage)
    (regle,) = resultat.regles
    assert regle.code is CodeIndicateur(code)
    assert regle.couleur is resultat.couleur
    return resultat.couleur, (regle.numerateur, regle.denominateur), regle.tickets_en_cause


def _assert_non_evaluable(ligne: dict[str, Any], *fragments: str) -> None:
    assert ligne["statut"] == StatutIndicateur.non_evaluable.value
    assert (ligne["numerateur"], ligne["denominateur"]) == (0, 0)
    assert ligne["couleur"] == Couleur.vert.value
    assert ligne["motif"]
    for fragment in fragments:
        assert fragment in ligne["motif"], ligne["motif"]


def test_ind2_age_de_la_plus_ancienne_bloquante() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _a(jour_ouvre_precedent(LUNDI, 3)))
    flux.anomalie("DEMO-2", _a(jour_ouvre_precedent(LUNDI, 7)))
    flux.anomalie("DEMO-3", _a(jour_ouvre_precedent(LUNDI, 9)), gravite="majeure")
    # Réouverture : l'âge repart de la dernière Entrée.
    flux.anomalie("DEMO-4", _a(jour_ouvre_precedent(LUNDI, 12)))
    flux.transition("DEMO-4", _a(jour_ouvre_precedent(LUNDI, 11)), "nouvelle", "fermee")
    flux.transition("DEMO-4", _a(jour_ouvre_precedent(LUNDI, 1)), "fermee", "en_analyse")
    assert _regle_unique(flux, "IND-2") == (Couleur.orange, (7, 1), ("DEMO-2",))
    ligne = _ligne(flux, "IND-2")
    assert (ligne["statut"], ligne["motif"]) == ("evalue", "")


def test_ind2_ex_aequo() -> None:
    flux = Flux()
    for numero in (12, 3):
        flux.anomalie(f"DEMO-{numero}", _a(jour_ouvre_precedent(LUNDI, 11)))
    assert _regle_unique(flux, "IND-2") == (Couleur.rouge, (11, 1), ("DEMO-3", "DEMO-12"))


def test_ind2_sans_bloquante() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _a(J5), gravite="majeure")
    flux.anomalie("DEMO-2", _a(J5))
    flux.transition("DEMO-2", _a(J5, 10), "nouvelle", "fermee")
    _assert_non_evaluable(_ligne(flux, "IND-2"), "aucune Anomalie bloquante ouverte")
    (resultat,) = _calculer_meteo(_etats(flux), LUNDI, ["ENT-A"], _grille_seule("IND-2"))
    assert resultat.couleur is Couleur.vert


def test_ind3_majeures_ouvertes() -> None:
    flux = Flux()
    for numero in range(1, 6):
        flux.anomalie(f"DEMO-{numero}", _a(J5), gravite="majeure")
    flux.anomalie("DEMO-6", _a(J5))  # bloquante : non comptée
    flux.anomalie("DEMO-7", _a(J5), gravite="majeure", entite="ENT-B")
    attendus = tuple(f"DEMO-{n}" for n in range(1, 6))
    assert _regle_unique(flux, "IND-3") == (Couleur.jaune, (5, 1), attendus)


def test_ind4_taux_de_ko_phase_en_cours() -> None:
    flux = Flux()
    _campagne(flux, ko=4, executes=20)
    for rang in range(3):  # KO de TNR : hors Phase en cours
        _cas(flux, f"DEMO-{200 + rang}", J5, "ko", phase="tnr")
    _cas(flux, "DEMO-300", J5, "non_execute")
    _cas(flux, "DEMO-301", J5, "ko", entite="ENT-B")
    attendus = ("DEMO-100", "DEMO-101", "DEMO-102", "DEMO-103")
    assert _regle_unique(flux, "IND-4") == (Couleur.rouge, (4, 20), attendus)


def test_ind4_garde_fou() -> None:
    flux = Flux()
    _campagne(flux, ko=10, executes=19)
    _cas(flux, "DEMO-300", J5, "non_execute")
    _assert_non_evaluable(_ligne(flux, "IND-4"), "19", "20")


def test_ind4_hors_calendrier() -> None:
    flux = Flux()
    _campagne(flux, ko=10, executes=20)
    ancrage = date(2026, 8, 10)  # LUNDI en semaine 9 : au-delà du calendrier de V1
    _assert_non_evaluable(_ligne(flux, "IND-4", ancrage=ancrage), "aucune Phase en cours")


def test_phase_en_cours() -> None:
    assert phase_en_cours(PROGRAMME, "ENT-A", LUNDI, ANCRAGE) is Phase.recette
    # Semaine 3 : migration à blanc (3) et recette (3-6) se chevauchent ; début le plus tardif.
    assert phase_en_cours(PROGRAMME, "ENT-A", VENDREDI, ANCRAGE) is Phase.recette
    assert phase_en_cours(PROGRAMME, "ENT-A", date(2026, 9, 14), ANCRAGE) is (
        Phase.migration_a_blanc
    )
    assert phase_en_cours(PROGRAMME, "ENT-A", date(2026, 9, 11), ANCRAGE) is None
    assert phase_en_cours(PROGRAMME, "ENT-A", LUNDI, date(2026, 8, 10)) is None
    # Même début : le rang le plus élevé dans la configuration l'emporte.
    donnees = PROGRAMME.model_dump(mode="json")
    donnees["vagues"][0]["phases"][2] = {"phase": "tnr", "semaine_debut": 3, "semaine_fin": 4}
    chevauchant = ConfigProgramme.model_validate(donnees)
    assert phase_en_cours(chevauchant, "ENT-A", VENDREDI, ANCRAGE) is Phase.tnr
    with pytest.raises(UsineErreur, match="ENT-Z"):
        phase_en_cours(PROGRAMME, "ENT-Z", LUNDI, ANCRAGE)


def test_ind5_ind6_certifications_vague_en_cours() -> None:
    flux = Flux()
    _certification(flux, "DEMO-1", "refusee")
    _certification(flux, "DEMO-2", "reservee")
    _certification(flux, "DEMO-3", "reservee")
    _certification(flux, "DEMO-4", "reservee", vague="V2")
    _certification(flux, "DEMO-5", "accordee")
    assert _regle_unique(flux, "IND-5") == (Couleur.rouge, (1, 1), ("DEMO-1",))
    assert _regle_unique(flux, "IND-6") == (Couleur.orange, (2, 1), ("DEMO-2", "DEMO-3"))
    (resultat,) = _calculer_meteo(_etats(flux), LUNDI, ["ENT-A"], _grille_seule("IND-5", "IND-6"))
    assert [r.code for r in resultat.regles] == [CodeIndicateur.ind_5]


def _entrees_fenetre(flux: Flux, nombre: int, gravite: str = "bloquante", debut: int = 1) -> None:
    """`nombre` Anomalies entrées sur la Fenêtre glissante de LUNDI (une par jour, en boucle)."""
    jours = jours_ouvres(jour_ouvre_precedent(LUNDI, 4), LUNDI)
    for rang in range(nombre):
        flux.anomalie(f"DEMO-{debut + rang}", _a(jours[rang % len(jours)]), gravite=gravite)


def test_ind7_ratio_infini() -> None:
    flux = Flux()
    _entrees_fenetre(flux, 3)
    _entrees_fenetre(flux, 3, gravite="majeure", debut=4)
    _entrees_fenetre(flux, 4, gravite="mineure", debut=20)  # mineures : non comptées
    flux.anomalie("DEMO-30", _a(J5))  # entrée la veille de la Fenêtre
    flux.anomalie("DEMO-31", _a(LUNDI), entite="ENT-B")
    attendus = tuple(f"DEMO-{n}" for n in range(1, 7))
    assert _regle_unique(flux, "IND-7") == (Couleur.orange, (6, 0), attendus)


def test_ind7_entrees_et_sorties() -> None:
    flux = Flux()
    _entrees_fenetre(flux, 6)
    for numero in range(40, 44):  # entrées avant la Fenêtre, sorties dedans
        flux.anomalie(f"DEMO-{numero}", _a(date(2026, 9, 21)), gravite="majeure")
        flux.transition(f"DEMO-{numero}", _a(date(2026, 9, 29)), "nouvelle", "fermee")
    flux.anomalie("DEMO-50", _a(date(2026, 9, 21)), gravite="mineure")
    flux.transition("DEMO-50", _a(date(2026, 9, 29)), "nouvelle", "fermee")
    couleur, valeur, tickets = _regle_unique(flux, "IND-7")
    assert (couleur, valeur) == (Couleur.jaune, (6, 4))  # 1,5 : pas strictement > 1,5
    assert tickets == tuple(f"DEMO-{n}" for n in [*range(1, 7), *range(40, 44)])


def test_ind7_entree_et_sortie_le_meme_jour() -> None:
    flux = Flux()
    _entrees_fenetre(flux, 5)
    flux.transition("DEMO-1", _a(jour_ouvre_precedent(LUNDI, 4), 10), "nouvelle", "rejetee")
    assert _regle_unique(flux, "IND-7") == (
        Couleur.orange,
        (5, 1),
        tuple(f"DEMO-{n}" for n in range(1, 6)),
    )


def test_ind7_garde_fou() -> None:
    flux = Flux()
    _entrees_fenetre(flux, 4)
    _entrees_fenetre(flux, 3, gravite="mineure", debut=20)
    _assert_non_evaluable(_ligne(flux, "IND-7"), "4", "5")


def _hausse(flux: Flux, ko_j5: int, ko_d: int) -> None:
    """20 Cas de recette créés à J-5 avec `ko_j5` KO ; `ko_d - ko_j5` passent en KO ensuite."""
    _campagne(flux, ko=ko_j5, executes=20)
    for rang in range(ko_j5, ko_d):
        flux.modifier(
            f"DEMO-{100 + rang}",
            TypeTicket.cas_de_test,
            _a(date(2026, 10, 1)),
            Champ.statut_test,
            "ok",
            "ko",
        )


def test_ind8_hausse_du_taux_de_ko() -> None:
    flux = Flux()
    _hausse(flux, ko_j5=1, ko_d=6)
    attendus = tuple(f"DEMO-{n}" for n in range(100, 106))
    assert _regle_unique(flux, "IND-8") == (Couleur.orange, (1, 4), attendus)


def test_ind8_baisse() -> None:
    flux = Flux()
    _campagne(flux, ko=6, executes=20)
    flux.modifier("DEMO-100", TypeTicket.cas_de_test, _a(LUNDI), Champ.statut_test, "ko", "ok")
    ligne = _ligne(flux, "IND-8")
    assert (ligne["statut"], ligne["numerateur"], ligne["denominateur"]) == ("evalue", -1, 20)
    assert ligne["couleur"] == "vert"


def test_ind8_ind4_non_evaluable_a_d() -> None:
    flux = Flux()
    _hausse(flux, ko_j5=1, ko_d=6)
    flux.modifier(
        "DEMO-119", TypeTicket.cas_de_test, _a(LUNDI), Champ.statut_test, "ok", "non_execute"
    )
    _assert_non_evaluable(_ligne(flux, "IND-8"), LUNDI.isoformat())


def test_ind8_ind4_non_evaluable_a_j5() -> None:
    flux = Flux()
    _campagne(flux, ko=6, executes=20, d=jour_ouvre_precedent(LUNDI, 2))
    _assert_non_evaluable(_ligne(flux, "IND-8"), J5.isoformat())


def test_ind8_j5_anterieur_a_l_ancrage() -> None:
    flux = Flux()
    _campagne(flux, ko=6, executes=20, d=date(2026, 9, 28))
    ancrage = date(2026, 9, 28)
    j5 = jour_ouvre_precedent(VENDREDI, 5)
    _assert_non_evaluable(_ligne(flux, "IND-8", d=VENDREDI, ancrage=ancrage), j5.isoformat())


def test_meteo_pire_couleur(grille_livree: GrilleMeteo) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _a(J5))  # IND-1 orange
    _campagne(flux, ko=4, executes=20)  # IND-4 rouge, IND-8 : hausse nulle
    (resultat,) = _calculer_meteo(_etats(flux), LUNDI, ["ENT-A"], grille_livree)
    assert resultat.couleur is Couleur.rouge
    (regle,) = resultat.regles
    assert regle.code is CodeIndicateur.ind_4
    table = _calculer_indicateurs(_etats(flux), LUNDI, ["ENT-A"], grille_livree)
    assert table["code"].to_list() == [code.value for code in CodeIndicateur]
    couleurs = dict(zip(table["code"].to_list(), table["couleur"].to_list(), strict=True))
    assert (couleurs["IND-1"], couleurs["IND-4"], couleurs["IND-8"]) == ("orange", "rouge", "vert")
    assert table.filter(pl.col("code") == "IND-7")["statut"].item() == "non_evaluable"


def test_entite_inconnue(grille_livree: GrilleMeteo) -> None:
    etats = tickets_etats([], [LUNDI])
    with pytest.raises(UsineErreur, match="ENT-Z"):
        _calculer_meteo(etats, LUNDI, ["ENT-A", "ENT-Z"], grille_livree)
    with pytest.raises(UsineErreur, match="ENT-Z"):
        _calculer_indicateurs(etats, LUNDI, ["ENT-Z"], grille_livree)


def test_ind2_bloquante_ouverte_sans_date_de_derniere_entree() -> None:
    ligne = {colonne: None for colonne in SCHEMA_TICKET_ETAT.colonnes} | {
        "date": LUNDI,
        "cle_ticket": "DEMO-7",
        "type_ticket": "anomalie",
        "entite": "ENT-A",
        "vague": "V1",
        "gravite": "bloquante",
        "phase": "recette",
        "statut": "nouvelle",
    }
    etats = pl.DataFrame([ligne], schema=dict(SCHEMA_TICKET_ETAT.colonnes))
    with pytest.raises(UsineErreur, match="DEMO-7"):
        _calculer_indicateurs(etats, LUNDI, ["ENT-A"], _grille_seule("IND-2"))


def test_date_d_arrete_avant_l_ancrage_toujours_controlee(grille: GrilleMeteo) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", datetime(2026, 9, 7, 9, tzinfo=UTC))
    etats = tickets_etats(flux.evenements, [date(2026, 9, 7), date(2026, 9, 9)])
    with pytest.raises(UsineErreur, match="2026-09-08"):
        _calculer_meteo(etats, date(2026, 9, 8), ["ENT-A"], grille)  # avant ANCRAGE


def test_trou_entre_j5_et_d(grille_livree: GrilleMeteo) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _a(date(2026, 9, 24)))
    dates = [d for d in jours_ouvres(J5, LUNDI) if d != date(2026, 9, 30)]
    etats = tickets_etats(flux.evenements, dates)
    with pytest.raises(UsineErreur, match="2026-09-30"):
        _calculer_meteo(etats, LUNDI, ["ENT-A"], grille_livree)
    with pytest.raises(UsineErreur, match="2026-09-30"):
        _calculer_indicateurs(etats, LUNDI, ["ENT-A"], grille_livree)
    # Avant l'ancrage, une date absente n'est pas exigée.
    ancrage = date(2026, 9, 28)
    etats = tickets_etats(flux.evenements, [date(2026, 9, 24), *jours_ouvres(ancrage, VENDREDI)])
    (resultat,) = _calculer_meteo(etats, VENDREDI, ["ENT-A"], grille_livree, ancrage)
    assert resultat.couleur is Couleur.orange


def test_lignes_posterieures_ignorees(grille_livree: GrilleMeteo) -> None:
    flux = Flux()
    _entrees_fenetre(flux, 6)
    flux.anomalie("DEMO-9", _a(date(2026, 10, 6)))
    avec_lendemain = tickets_etats(flux.evenements, jours_ouvres(J5, date(2026, 10, 6)))
    sans_lendemain = _etats(flux)
    assert _calculer_indicateurs(avec_lendemain, LUNDI, ["ENT-A"], grille_livree).equals(
        _calculer_indicateurs(sans_lendemain, LUNDI, ["ENT-A"], grille_livree)
    )
    assert _calculer_meteo(avec_lendemain, LUNDI, ["ENT-A"], grille_livree) == _calculer_meteo(
        sans_lendemain, LUNDI, ["ENT-A"], grille_livree
    )


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
    chemin = tmp_path / "journal.jsonl"
    chemin.write_bytes(serialiser_journal(generer(PROGRAMME, 42, date(2026, 10, 12))))
    source = SourceJournal(chemin)
    evenements = list(source.evenements())
    d = source.entete.date_injection
    ancrage = source.entete.ancrage_semaines
    entites = [e.code for e in PROGRAMME.entites]
    assert entites == ["ENT-A", "ENT-B"]
    grille = charger_yaml(CHEMIN_GRILLE, GrilleMeteo)
    version = version_grille(CHEMIN_GRILLE.read_bytes())
    etats = tickets_etats(evenements, jours_ouvres(jour_ouvre_precedent(d, 5), d))

    def calculer() -> tuple[pl.DataFrame, tuple[MeteoEntite, ...]]:
        return (
            indicateurs(etats, d, entites, grille, programme=PROGRAMME, ancrage=ancrage),
            meteo(etats, d, entites, grille, version, programme=PROGRAMME, ancrage=ancrage),
        )

    table, resultats = calculer()
    assert any(r.couleur is not Couleur.vert for r in resultats)
    attendus = _bloquantes_ouvertes(evenements, d)
    for resultat in resultats:
        MeteoEntite.model_validate(resultat.model_dump())
        assert resultat.version_grille == version
        lignes = table.filter(pl.col("entite") == resultat.entite)
        assert lignes["code"].to_list() == [code.value for code in CodeIndicateur]
        evaluees = lignes.filter(pl.col("statut") == "evalue")
        pire = max((Couleur(c) for c in evaluees["couleur"].to_list()), default=Couleur.vert)
        assert resultat.couleur is pire, resultat.entite
        declenchees = evaluees.filter(pl.col("couleur") == pire.value)["code"].to_list()
        assert [r.code.value for r in resultat.regles] == (
            declenchees if pire is not Couleur.vert else []
        )
        for ligne in lignes.filter(pl.col("statut") == "non_evaluable").to_dicts():
            assert (ligne["numerateur"], ligne["denominateur"], ligne["couleur"]) == (0, 0, "vert")
            assert ligne["motif"]
        ind1 = lignes.filter(pl.col("code") == "IND-1").row(0, named=True)
        assert ind1["numerateur"] == len(attendus.get(resultat.entite, []))
    # Déterminisme : deux calculs identiques, ordre des lignes compris.
    table_bis, resultats_bis = calculer()
    assert table.equals(table_bis)
    assert resultats == resultats_bis


# --- Météo et Règles déclenchantes (Story 3.6) ---


def _resume(resultat: MeteoEntite) -> list[tuple[str, str, tuple[int, int], str, tuple[str, ...]]]:
    """Code, couleur, valeur, seuil écrit et tickets en cause de chaque Règle déclenchante."""
    return [
        (
            regle.code.value,
            regle.couleur.value,
            (regle.numerateur, regle.denominateur),
            f"{regle.operateur.value} {regle.seuil_numerateur}/{regle.seuil_denominateur}",
            regle.tickets_en_cause,
        )
        for regle in resultat.regles
    ]


def test_rouge_par_ind1_et_ind5(grille_livree: GrilleMeteo) -> None:
    flux = Flux()
    for numero in (7, 2, 11):  # créées à J-5 : âge 5, hors Fenêtre glissante
        flux.anomalie(f"DEMO-{numero}", _a(J5))
    _certification(flux, "DEMO-20", "refusee")
    (resultat,) = _calculer_meteo(_etats(flux), LUNDI, ["ENT-A"], grille_livree)
    assert resultat.couleur is Couleur.rouge
    assert resultat.version_grille == VERSION
    assert resultat.date_arrete == LUNDI
    assert _resume(resultat) == [
        ("IND-1", "rouge", (3, 1), ">= 3/1", ("DEMO-2", "DEMO-7", "DEMO-11")),
        ("IND-5", "rouge", (1, 1), ">= 1/1", ("DEMO-20",)),
    ]


def _grille_tout_rouge() -> GrilleMeteo:
    """Grille livrée (garde-fous compris) où chaque indicateur n'a qu'un seuil rouge bas."""
    seuils = {
        "IND-1": ">= 1",
        "IND-2": "> 0",
        "IND-3": ">= 1",
        "IND-4": ">= 0.05",
        "IND-5": ">= 1",
        "IND-6": ">= 1",
        "IND-7": "> 1",
        "IND-8": ">= 0.03",
    }
    return _grille(**{code: _regle({"rouge": seuil}) for code, seuil in seuils.items()})


def _ouverte(ligne: dict[str, Any]) -> bool:
    return ligne["statut"] is not None and ligne["statut"] not in {s.value for s in STATUTS_FERMES}


def test_toutes_les_regles_et_tickets_en_cause_fr17() -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _a(J5))  # bloquante entrée avant la Fenêtre glissante
    flux.anomalie("DEMO-2", _a(J5), gravite="majeure")
    _entrees_fenetre(flux, 5, debut=3)  # DEMO-3 à DEMO-7 : bloquantes entrées dans la Fenêtre
    flux.anomalie("DEMO-8", _a(date(2026, 9, 21)))  # entrée avant la Fenêtre…
    flux.transition("DEMO-8", _a(date(2026, 9, 30)), "nouvelle", "fermee")  # …sortie dedans
    _hausse(flux, ko_j5=1, ko_d=6)  # DEMO-100 à DEMO-119 en recette, KO : DEMO-100 à DEMO-105
    _cas(flux, "DEMO-200", J5, "ko", phase="tnr")  # KO hors Phase en cours
    _certification(flux, "DEMO-300", "refusee")
    _certification(flux, "DEMO-301", "reservee")
    _certification(flux, "DEMO-302", "reservee", vague="V2")  # autre Vague
    flux.anomalie("DEMO-400", _a(LUNDI), gravite="mineure")
    # Leurres d'une autre Entité : bloquante ouverte et Cas de test KO de recette d'ENT-B.
    flux.anomalie("DEMO-500", _a(LUNDI), entite="ENT-B")
    _cas(flux, "DEMO-501", J5, "ko", entite="ENT-B")
    etats = _etats(flux)
    resultat, _ = _calculer_meteo(etats, LUNDI, ["ENT-A", "ENT-B"], _grille_tout_rouge())

    assert resultat.entite == "ENT-A"
    assert resultat.couleur is Couleur.rouge
    assert [r.code for r in resultat.regles] == list(CodeIndicateur)
    ko_recette = tuple(f"DEMO-{n}" for n in range(100, 106))
    fenetre = tuple(f"DEMO-{n}" for n in range(3, 8))
    assert _resume(resultat) == [
        ("IND-1", "rouge", (6, 1), ">= 1/1", ("DEMO-1", *fenetre)),
        ("IND-2", "rouge", (5, 1), "> 0/1", ("DEMO-1",)),
        ("IND-3", "rouge", (1, 1), ">= 1/1", ("DEMO-2",)),
        ("IND-4", "rouge", (6, 20), ">= 1/20", ko_recette),
        ("IND-5", "rouge", (1, 1), ">= 1/1", ("DEMO-300",)),
        ("IND-6", "rouge", (1, 1), ">= 1/1", ("DEMO-301",)),
        ("IND-7", "rouge", (5, 1), "> 1/1", (*fenetre, "DEMO-8")),
        ("IND-8", "rouge", (1, 4), ">= 3/100", ko_recette),
    ]

    # Chaque ticket en cause est retrouvé dans l'état des tickets avec le type FR-17 attendu.
    par_jour = {(ligne["cle_ticket"], ligne["date"]): ligne for ligne in etats.to_dicts()}
    lignes = {cle: ligne for (cle, jour), ligne in par_jour.items() if jour == LUNDI}
    phase = phase_en_cours(PROGRAMME, "ENT-A", LUNDI, ANCRAGE)
    assert phase is Phase.recette
    vague = next(e.vague for e in PROGRAMME.entites if e.code == "ENT-A")

    def anomalie_ouverte(gravite: str) -> Callable[[dict[str, Any]], bool]:
        return lambda t: t["type_ticket"] == "anomalie" and t["gravite"] == gravite and _ouverte(t)

    def ko_phase_en_cours(t: dict[str, Any]) -> bool:
        return t["type_ticket"] == "cas_de_test" and (t["statut_test"], t["phase"]) == (
            "ko",
            phase.value,
        )

    def certification(statut: str) -> Callable[[dict[str, Any]], bool]:
        attendu = ("certification", vague, statut)
        return lambda t: (t["type_ticket"], t["vague"], t["statut_certification"]) == attendu

    def mouvement_fenetre(t: dict[str, Any]) -> bool:
        """Entrée un jour de la Fenêtre, ou ouverte la veille d'un jour de la Fenêtre et
        fermée ce jour-là (lignes J-5 à D de l'état des tickets)."""
        for jour in fenetre_glissante(LUNDI):
            du_jour = par_jour.get((t["cle_ticket"], jour))
            veille = par_jour.get((t["cle_ticket"], jour_ouvre_precedent(jour)))
            if du_jour is None or du_jour["type_ticket"] != "anomalie":
                continue
            if du_jour["gravite"] not in ("bloquante", "majeure"):
                continue
            entree = du_jour["date_derniere_entree"] == jour
            sortie = veille is not None and _ouverte(veille) and not _ouverte(du_jour)
            if entree or sortie:
                return True
        return False

    types_fr17: dict[CodeIndicateur, Callable[[dict[str, Any]], bool]] = {
        CodeIndicateur.ind_1: anomalie_ouverte("bloquante"),
        CodeIndicateur.ind_2: anomalie_ouverte("bloquante"),
        CodeIndicateur.ind_3: anomalie_ouverte("majeure"),
        CodeIndicateur.ind_4: ko_phase_en_cours,
        CodeIndicateur.ind_5: certification("refusee"),
        CodeIndicateur.ind_6: certification("reservee"),
        CodeIndicateur.ind_7: mouvement_fenetre,
        CodeIndicateur.ind_8: ko_phase_en_cours,
    }
    for regle in resultat.regles:
        assert regle.tickets_en_cause, regle.code
        for cle in regle.tickets_en_cause:
            ticket = lignes[cle]
            assert ticket["entite"] == "ENT-A", (regle.code, cle)
            assert types_fr17[regle.code](ticket), (regle.code, cle, ticket)
    en_cause = {cle for regle in resultat.regles for cle in regle.tickets_en_cause}
    assert en_cause.isdisjoint({"DEMO-200", "DEMO-302", "DEMO-400"})
    cles_ent_b = set(etats.filter(pl.col("entite") == "ENT-B")["cle_ticket"].to_list())
    assert cles_ent_b == {"DEMO-500", "DEMO-501"}
    assert en_cause.isdisjoint(cles_ent_b)


def test_sans_etat_d_un_jour_a_l_autre(grille_livree: GrilleMeteo) -> None:
    flux = Flux()
    for numero in (1, 2, 3):
        flux.anomalie(f"DEMO-{numero}", _a(J5))
    for numero in (1, 2):
        flux.transition(f"DEMO-{numero}", _a(LUNDI), "nouvelle", "fermee")
    etats = tickets_etats(flux.evenements, jours_ouvres(jour_ouvre_precedent(VENDREDI, 5), LUNDI))
    (vendredi,) = _calculer_meteo(etats, VENDREDI, ["ENT-A"], grille_livree)
    (lundi,) = _calculer_meteo(etats, LUNDI, ["ENT-A"], grille_livree)
    assert vendredi.couleur is Couleur.rouge
    assert _resume(vendredi) == [
        ("IND-1", "rouge", (3, 1), ">= 3/1", ("DEMO-1", "DEMO-2", "DEMO-3")),
    ]
    assert lundi.couleur is Couleur.orange  # pas de maintien du rouge (pas d'hystérésis)
    assert _resume(lundi) == [("IND-1", "orange", (1, 1), ">= 1/1", ("DEMO-3",))]
    # Le lundi ne dépend pas de la Météo du vendredi : un flux qui atteint le même état des
    # tickets au lundi sans avoir jamais été rouge (DEMO-1 et DEMO-2 fermées dès J-5) donne
    # la même Météo.
    jamais_rouge = Flux()
    for numero in (1, 2, 3):
        jamais_rouge.anomalie(f"DEMO-{numero}", _a(J5))
    for numero in (1, 2):
        jamais_rouge.transition(f"DEMO-{numero}", _a(J5, 10), "nouvelle", "fermee")
    etats_bis = tickets_etats(
        jamais_rouge.evenements, jours_ouvres(jour_ouvre_precedent(VENDREDI, 5), LUNDI)
    )
    (vendredi_bis,) = _calculer_meteo(etats_bis, VENDREDI, ["ENT-A"], grille_livree)
    assert vendredi_bis.couleur is Couleur.orange
    (lundi_bis,) = _calculer_meteo(etats_bis, LUNDI, ["ENT-A"], grille_livree)
    assert lundi_bis == lundi


def test_non_evaluable_sans_effet(grille_livree: GrilleMeteo) -> None:
    flux = Flux()
    _entrees_fenetre(flux, 4)  # 4 Entrées bloquantes : sous le garde-fou d'IND-7
    for numero in (2, 3, 4):
        jour = jour_ouvre_precedent(LUNDI, 4 - (numero - 1))
        flux.transition(f"DEMO-{numero}", _a(jour, 10), "nouvelle", "rejetee")
    # 19 Cas exécutés tous KO : sous le garde-fou d'IND-4. Évalué, IND-4 vaudrait 19/19,
    # au-delà du seuil rouge (>= 0,20) : il ferait passer la Météo au rouge.
    _campagne(flux, ko=19, executes=19)
    (resultat,) = _calculer_meteo(_etats(flux), LUNDI, ["ENT-A"], grille_livree)
    assert resultat.couleur is Couleur.orange
    assert _resume(resultat) == [("IND-1", "orange", (1, 1), ">= 1/1", ("DEMO-1",))]
    table = _calculer_indicateurs(_etats(flux), LUNDI, ["ENT-A"], grille_livree)
    non_evaluables = table.filter(pl.col("statut") == "non_evaluable")
    assert non_evaluables["code"].to_list() == ["IND-4", "IND-7", "IND-8"]
    motifs = dict(zip(non_evaluables["code"], non_evaluables["motif"], strict=True))
    assert "19 Cas de test" in motifs["IND-4"] and "garde-fou de 20" in motifs["IND-4"]
    assert "4 Entrée(s)" in motifs["IND-7"] and "garde-fou de 5" in motifs["IND-7"]
    assert "IND-4 non évaluable" in motifs["IND-8"]


def test_tout_non_evaluable_ou_vert(grille_livree: GrilleMeteo) -> None:
    flux = Flux()
    _entrees_fenetre(flux, 4, gravite="majeure")  # IND-3 sous le jaune, IND-7 non évaluable
    _campagne(flux, ko=19, executes=19)  # IND-4 et IND-8 non évaluables
    (resultat,) = _calculer_meteo(_etats(flux), LUNDI, ["ENT-A"], grille_livree)
    assert resultat.couleur is Couleur.vert
    assert resultat.regles == ()
    table = _calculer_indicateurs(_etats(flux), LUNDI, ["ENT-A"], grille_livree)
    assert set(table["couleur"].to_list()) == {"vert"}
    non_evaluables = table.filter(pl.col("statut") == "non_evaluable")["code"].to_list()
    assert non_evaluables == ["IND-2", "IND-4", "IND-7", "IND-8"]
    # Seuls des indicateurs non évaluables actifs (IND-4 à 19/19 franchirait le rouge s'il
    # était évalué) : vert, sans règle.
    seuls = _grille_seule("IND-2", "IND-4", "IND-7", "IND-8")
    (resultat,) = _calculer_meteo(_etats(flux), LUNDI, ["ENT-A"], seuls)
    assert resultat.couleur is Couleur.vert
    assert resultat.regles == ()
    table = _calculer_indicateurs(_etats(flux), LUNDI, ["ENT-A"], seuls)
    assert table["code"].to_list() == ["IND-2", "IND-4", "IND-7", "IND-8"]
    assert set(table["statut"].to_list()) == {"non_evaluable"}


def test_egalite_de_couleurs(grille_livree: GrilleMeteo) -> None:
    flux = Flux()
    flux.anomalie("DEMO-1", _a(J5))  # IND-1 orange
    for numero in range(10, 15):  # IND-3 jaune
        flux.anomalie(f"DEMO-{numero}", _a(J5), gravite="majeure")
    _certification(flux, "DEMO-21", "reservee")  # IND-6 orange
    _certification(flux, "DEMO-20", "reservee")
    (resultat,) = _calculer_meteo(_etats(flux), LUNDI, ["ENT-A"], grille_livree)
    assert resultat.couleur is Couleur.orange
    assert _resume(resultat) == [
        ("IND-1", "orange", (1, 1), ">= 1/1", ("DEMO-1",)),
        ("IND-6", "orange", (2, 1), ">= 2/1", ("DEMO-20", "DEMO-21")),
    ]
    table = _calculer_indicateurs(_etats(flux), LUNDI, ["ENT-A"], grille_livree)
    assert table.filter(pl.col("code") == "IND-3")["couleur"].item() == "jaune"


# --- Évolution de la Météo à J-1 et J-5 (Story 3.7) ---

PREMIER_JOUR = date(2026, 9, 28)
"""Premier Jour ouvré de l'historique de la trajectoire (lundi)."""
TRAJECTOIRE = jours_ouvres(PREMIER_JOUR, LUNDI)
"""Du lundi 2026-09-28 au lundi 2026-10-05 (6 Jours ouvrés)."""


def _passage_trajectoire(repertoire: Path, grille: GrilleMeteo) -> ConsultationPassage:
    """Météo de chaque Jour ouvré de la trajectoire, publiée dans `meteo.json`.

    ENT-A (IND-1 seul) : 28/09 vert, 29/09 orange (1 bloquante), 30/09 et 01/10 rouge (3),
    02/10 et 05/10 orange (2 fermées le 02/10). ENT-B : aucun ticket, vert tout du long.
    """
    flux = Flux()
    flux.anomalie("DEMO-1", _a(date(2026, 9, 29)))
    for cle in ("DEMO-2", "DEMO-3"):
        flux.anomalie(cle, _a(date(2026, 9, 30)))
        flux.transition(cle, _a(VENDREDI, 10), "nouvelle", "fermee")
    etats = tickets_etats(flux.evenements, TRAJECTOIRE)
    meteos = tuple(
        m for jour in TRAJECTOIRE for m in _calculer_meteo(etats, jour, ["ENT-A", "ENT-B"], grille)
    )
    passage_id = former_passage_id(datetime(2026, 10, 5, 18, tzinfo=UTC), "aaaaaa")
    enveloppe = EnveloppeFichier[tuple[MeteoEntite, ...]](
        passage_id=passage_id, date_arrete=LUNDI, contenu=meteos
    )
    (repertoire / FICHIERS_PASSAGE["meteo"]).write_bytes(
        enveloppe.model_dump_json(indent=2).encode("utf-8")
    )
    return ConsultationPassage(repertoire, date_arrete=LUNDI)


def _evolution(consultation: ConsultationPassage, d: date, entite: str) -> EvolutionMeteo:
    trouvees = [e for e in consultation.evolution_meteo(d) if e.entite == entite]
    assert len(trouvees) == 1, f"{entite} au {d.isoformat()} : {len(trouvees)} évolution(s)"
    return trouvees[0]


def test_trajectoire_publiee(tmp_path: Path, grille: GrilleMeteo) -> None:
    consultation = _passage_trajectoire(tmp_path, grille)
    assert consultation.dates_disponibles() == TRAJECTOIRE
    couleurs = [consultation.meteo(jour, "ENT-A")[0].couleur for jour in TRAJECTOIRE]
    assert couleurs == [
        Couleur.vert,
        Couleur.orange,
        Couleur.rouge,
        Couleur.rouge,
        Couleur.orange,
        Couleur.orange,
    ]


def test_j1_inchange_j5_change(tmp_path: Path, grille: GrilleMeteo) -> None:
    evolution = _evolution(_passage_trajectoire(tmp_path, grille), LUNDI, "ENT-A")
    assert evolution.couleur is Couleur.orange
    assert (evolution.date_j1, evolution.couleur_j1) == (VENDREDI, Couleur.orange)
    assert evolution.change_depuis_j1 is False
    assert (evolution.date_j5, evolution.couleur_j5) == (PREMIER_JOUR, Couleur.vert)
    assert evolution.change_depuis_j5 is True


def test_j1_change_j5_hors_historique(tmp_path: Path, grille: GrilleMeteo) -> None:
    evolution = _evolution(_passage_trajectoire(tmp_path, grille), VENDREDI, "ENT-A")
    assert evolution.couleur is Couleur.orange
    assert (evolution.date_j1, evolution.couleur_j1) == (date(2026, 10, 1), Couleur.rouge)
    assert evolution.change_depuis_j1 is True
    assert evolution.date_j5 == date(2026, 9, 25)
    assert evolution.couleur_j5 is None
    assert evolution.change_depuis_j5 is False


def test_premier_jour_ouvre_j1_absent(tmp_path: Path, grille: GrilleMeteo) -> None:
    consultation = _passage_trajectoire(tmp_path, grille)
    for entite in ("ENT-A", "ENT-B"):
        evolution = _evolution(consultation, PREMIER_JOUR, entite)
        assert evolution.couleur is Couleur.vert
        assert evolution.date_j1 == date(2026, 9, 25)
        assert evolution.couleur_j1 is None  # et non une couleur par défaut (vert)
        assert evolution.change_depuis_j1 is False
        assert evolution.date_j5 == date(2026, 9, 21)
        assert evolution.couleur_j5 is None
        assert evolution.change_depuis_j5 is False


def test_entite_stable(tmp_path: Path, grille: GrilleMeteo) -> None:
    evolution = _evolution(_passage_trajectoire(tmp_path, grille), LUNDI, "ENT-B")
    assert (evolution.couleur, evolution.couleur_j1, evolution.couleur_j5) == (
        Couleur.vert,
        Couleur.vert,
        Couleur.vert,
    )
    assert not evolution.change_depuis_j1
    assert not evolution.change_depuis_j5


def test_evolution_sur_le_passage_du_mini_jeu(tmp_path: Path) -> None:
    racine = preparer_racine(tmp_path / "racine")
    lance = lancer_rapport(racine, DATE_ARRETE, horloge_figee(), lambda: "aaaaaa")
    premier_jour = SourceJournal(racine / CHEMIN_JOURNAL).entete.ancrage_semaines
    consultation = ConsultationPassage(lance.repertoire)
    jours = jours_ouvres(premier_jour, DATE_ARRETE)
    assert consultation.dates_disponibles() == jours
    entites = [e.code for e in PROGRAMME.entites]
    couleurs: dict[tuple[date, str], Couleur] = {}
    for jour in jours:
        meteos = consultation.meteo(jour)
        assert [m.entite for m in meteos] == entites, jour
        couleurs.update({(jour, m.entite): m.couleur for m in meteos})
    changements = 0
    j5_connus = 0
    for jour in jours:
        evolutions = consultation.evolution_meteo(jour)
        assert [e.entite for e in evolutions] == entites, jour
        for evolution in evolutions:
            j1, j5 = jour_ouvre_precedent(jour, 1), jour_ouvre_precedent(jour, 5)
            assert (evolution.date_j1, evolution.date_j5) == (j1, j5)
            assert evolution.couleur is couleurs[(jour, evolution.entite)]
            assert evolution.couleur_j1 is couleurs.get((j1, evolution.entite))
            assert evolution.couleur_j5 is couleurs.get((j5, evolution.entite))
            assert (evolution.couleur_j1 is None) == (j1 < premier_jour)
            assert (evolution.couleur_j5 is None) == (j5 < premier_jour)
            assert evolution.change_depuis_j1 == (
                evolution.couleur_j1 is not None and evolution.couleur_j1 is not evolution.couleur
            )
            assert evolution.change_depuis_j5 == (
                evolution.couleur_j5 is not None and evolution.couleur_j5 is not evolution.couleur
            )
            changements += evolution.change_depuis_j1
            j5_connus += evolution.couleur_j5 is not None
    assert changements > 0  # le mini-jeu fait changer la Météo au moins une fois
    assert j5_connus > 0  # les assertions sur J-5 portent sur au moins une couleur connue
