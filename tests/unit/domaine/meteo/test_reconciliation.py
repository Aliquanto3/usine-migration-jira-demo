"""Rapport de référence : réconciliation à 100 % de KPI, Indicateurs et Météo (Story 3.8).

FR-13, SM-1. Le jeu figé de `tests/fixtures/reference/` (2 Entités, 58 tickets, 1 Date
d'arrêté) est lu par le chemin de production : Journal par `SourceJournal`, Programme et Grille
par `charger_yaml` (+ `verifier_grille`), `version_grille` par `contrats.versions`. Le domaine
recalcule KPI, Indicateurs et Météo, comparés à `attendu.yaml` (calculé à la main) en égalité
stricte : mêmes clés dans le même ordre, couples `(numérateur, dénominateur)` entiers comparés
sans réduction ([4, 20] ≠ [1, 5]).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any

import polars as pl
import pytest
import yaml

from usine.adaptateurs.journal import SourceJournal
from usine.config import charger_yaml
from usine.contrats.calcul import PERIMETRE_PROGRAMME
from usine.contrats.calendrier import est_jour_ouvre, jour_local, jour_ouvre_de, jours_ouvres
from usine.contrats.config import ConfigProgramme, GrilleMeteo
from usine.contrats.evenements import NatureEvenement
from usine.contrats.meteo import CodeIndicateur, Couleur, MeteoEntite
from usine.contrats.tickets import Champ, Phase, StatutAnomalie, TypeTicket
from usine.contrats.versions import version_grille
from usine.domaine.instantanes import tickets_etats
from usine.domaine.kpi import CODES_KPI, DIMENSIONS_KPI, kpi
from usine.domaine.meteo import indicateurs, meteo, verifier_grille

REFERENCE = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "reference"
CHEMIN_JOURNAL = REFERENCE / "journal.jsonl"
CHEMIN_PROGRAMME = REFERENCE / "programme.yaml"
CHEMIN_GRILLE = REFERENCE / "grille_meteo.yaml"
CHEMIN_ATTENDU = REFERENCE / "attendu.yaml"

Couple = tuple[int, int]
_Meteo = tuple[str, tuple[tuple[object, ...], ...]]
"""(couleur, règles (code, couleur, opérateur, valeur, seuil, tickets en cause))."""

_INDICATEURS_A_GARDE = (
    CodeIndicateur.ind_2,
    CodeIndicateur.ind_4,
    CodeIndicateur.ind_7,
    CodeIndicateur.ind_8,
)
"""Indicateurs pouvant être non évaluables (donnée absente ou garde-fou de volume)."""

_GARDE_FOU = "en deçà du garde-fou"
_IND8_SANS_IND4 = "IND-4 non évaluable le "


def _couple(valeur: object, ou: str) -> Couple:
    """Couple d'entiers `[n, d]` du YAML ; tout autre forme (flottant, booléen…) est refusée."""
    if not (
        isinstance(valeur, list)
        and len(valeur) == 2
        and all(type(partie) is int for partie in valeur)
    ):
        raise AssertionError(f"{ou} : couple d'entiers [n, d] attendu, pas {valeur!r}")
    return valeur[0], valeur[1]


def _entier(valeur: object) -> int:
    """Entier Python strict (ni `bool`, ni flottant) issu d'une table Polars."""
    assert type(valeur) is int, f"entier attendu, pas {valeur!r}"
    return valeur


def _ecarts[K, V](calcule: dict[K, V], attendu: dict[K, V]) -> str:
    """Écarts lisibles entre deux tables indexées : clés en trop, manquantes, valeurs."""
    lignes = [
        f"calculée seulement : {cle!r} = {calcule[cle]!r}" for cle in calcule.keys() - attendu
    ]
    lignes += [
        f"attendue seulement : {cle!r} = {attendu[cle]!r}" for cle in attendu.keys() - calcule
    ]
    lignes += [
        f"{cle!r} : calculé {calcule[cle]!r}, attendu {attendu[cle]!r}"
        for cle in calcule.keys() & attendu.keys()
        if calcule[cle] != attendu[cle]
    ]
    return "\n".join(sorted(lignes))


@dataclass(frozen=True)
class _Calcul:
    """Entrées lues par le chemin de production et sorties du domaine à la Date d'arrêté."""

    source: SourceJournal
    programme: ConfigProgramme
    grille: GrilleMeteo
    ancrage: date
    etats: pl.DataFrame
    entites: tuple[str, ...]
    date_arrete: date
    version_grille: str
    kpi: pl.DataFrame
    indicateurs: pl.DataFrame
    meteo: tuple[MeteoEntite, ...]

    def meteo_avec(self, grille: GrilleMeteo) -> tuple[MeteoEntite, ...]:
        """Météo à D recalculée avec une autre Grille (même `version_grille`)."""
        return meteo(
            self.etats,
            self.date_arrete,
            self.entites,
            grille,
            self.version_grille,
            programme=self.programme,
            ancrage=self.ancrage,
        )


@pytest.fixture(scope="module")
def attendu() -> dict[str, Any]:
    donnees: dict[str, Any] = yaml.safe_load(CHEMIN_ATTENDU.read_text(encoding="utf-8"))
    return donnees


@pytest.fixture(scope="module")
def calcul(attendu: dict[str, Any]) -> _Calcul:
    source = SourceJournal(CHEMIN_JOURNAL)
    programme = charger_yaml(CHEMIN_PROGRAMME, ConfigProgramme)
    grille = verifier_grille(charger_yaml(CHEMIN_GRILLE, GrilleMeteo), str(CHEMIN_GRILLE))
    empreinte = version_grille(CHEMIN_GRILLE.read_bytes())
    ancrage = source.entete.ancrage_semaines
    date_arrete: date = attendu["date_arrete"]
    entites = tuple(entite.code for entite in programme.entites)

    # Historique complet de l'ancrage à D : Entrées, Sorties, Fenêtre glissante et J-5 en
    # dépendent ; seules les lignes datées de D sont réconciliées.
    etats = tickets_etats(list(source.evenements()), jours_ouvres(ancrage, date_arrete))
    return _Calcul(
        source=source,
        programme=programme,
        grille=grille,
        ancrage=ancrage,
        etats=etats,
        entites=entites,
        date_arrete=date_arrete,
        version_grille=empreinte,
        kpi=kpi(etats, entites),
        indicateurs=indicateurs(
            etats, date_arrete, entites, grille, programme=programme, ancrage=ancrage
        ),
        meteo=meteo(
            etats, date_arrete, entites, grille, empreinte, programme=programme, ancrage=ancrage
        ),
    )


def _grille_sans(grille: GrilleMeteo, inactifs: Sequence[str]) -> GrilleMeteo:
    """Grille dérivée par `model_copy` : les indicateurs de `inactifs` passent `active=False`."""
    codes = {CodeIndicateur(code) for code in inactifs}
    return grille.model_copy(
        update={
            "indicateurs": MappingProxyType(
                {
                    code: regle.model_copy(update={"active": False}) if code in codes else regle
                    for code, regle in grille.indicateurs.items()
                }
            )
        }
    )


def _reconcilier_meteo(
    calculees: tuple[MeteoEntite, ...],
    attendues: dict[str, Any],
    calcul: _Calcul,
    version_attendue: str,
    ou: str,
) -> None:
    """Compare des Météo calculées à un bloc `{entité: {couleur, regles}}` du YAML."""
    attendus: dict[str, _Meteo] = {}
    for entite, bloc in attendues.items():
        regles = tuple(
            (
                regle["code"],
                bloc["couleur"],
                regle["operateur"],
                _couple(regle["valeur"], f"{ou}.{entite}.{regle['code']}.valeur"),
                _couple(regle["seuil"], f"{ou}.{entite}.{regle['code']}.seuil"),
                tuple(regle["tickets_en_cause"]),
            )
            for regle in bloc["regles"]
        )
        attendus[entite] = (bloc["couleur"], regles)

    calcules: dict[str, _Meteo] = {}
    for entite_meteo in calculees:
        assert entite_meteo.date_arrete == calcul.date_arrete
        assert entite_meteo.version_grille == version_attendue
        assert entite_meteo.entite not in calcules
        calcules[entite_meteo.entite] = (
            entite_meteo.couleur.value,
            tuple(
                (
                    regle.code.value,
                    regle.couleur.value,
                    regle.operateur.value,
                    (_entier(regle.numerateur), _entier(regle.denominateur)),
                    (_entier(regle.seuil_numerateur), _entier(regle.seuil_denominateur)),
                    regle.tickets_en_cause,
                )
                for regle in entite_meteo.regles
            ),
        )
    assert tuple(m.entite for m in calculees) == calcul.entites
    assert calcules == attendus, f"{ou} :\n{_ecarts(calcules, attendus)}"


# --- Inspection du jeu ---


def test_jeu_reduit_deux_entites_cinquante_huit_tickets_une_date(
    calcul: _Calcul, attendu: dict[str, Any]
) -> None:
    """H-20 : 2 Entités, tickets REF-1 à REF-58, une seule Date d'arrêté, Jour ouvré."""
    assert len(calcul.entites) == 2
    assert tuple(attendu["entites"]) == calcul.entites
    tickets = {e.cle_ticket for e in calcul.source.evenements()}
    assert tickets == {f"REF-{numero}" for numero in range(1, 59)}
    assert isinstance(attendu["date_arrete"], date)
    assert est_jour_ouvre(calcul.date_arrete)
    assert set(attendu["kpi"]) == {*calcul.entites, PERIMETRE_PROGRAMME}
    assert set(attendu["indicateurs"]) == set(calcul.entites) == set(attendu["meteo"])


def test_jeu_contient_les_pieges_prevus(calcul: _Calcul) -> None:
    """Événement postérieur à D, clôture un samedi, création après minuit à Paris, Cas de test
    TNR et Certification d'une autre Vague : présents dans le Journal."""
    evenements = list(calcul.source.evenements())
    assert any(jour_ouvre_de(e.horodatage) > calcul.date_arrete for e in evenements)
    assert any(
        e.nature is NatureEvenement.transition
        and e.vers == StatutAnomalie.fermee.value
        and not est_jour_ouvre(jour_local(e.horodatage))
        for e in evenements
    )
    assert any(
        e.nature is NatureEvenement.creation and e.horodatage.date() != jour_local(e.horodatage)
        for e in evenements
    )
    assert any(
        e.type_ticket is TypeTicket.cas_de_test
        and e.champ is Champ.phase
        and e.vers == Phase.tnr.value
        for e in evenements
    )
    vagues = {entite.vague for entite in calcul.programme.entites}
    assert any(
        e.type_ticket is TypeTicket.certification
        and e.champ is Champ.vague
        and e.vers is not None
        and e.vers not in vagues
        for e in evenements
    )


def test_chaque_indicateur_declenche_et_non_declenche(attendu: dict[str, Any]) -> None:
    """Chaque IND déclenché (couleur non verte) sur une Entité et vert sur une autre."""
    for code in CodeIndicateur:
        couleurs = {
            Couleur(lignes[code.value]["couleur"]) for lignes in attendu["indicateurs"].values()
        }
        assert Couleur.vert in couleurs, code
        assert couleurs - {Couleur.vert}, code


def test_indicateurs_a_garde_evalues_et_non_evaluables(attendu: dict[str, Any]) -> None:
    """IND-2, IND-4, IND-7, IND-8 évalués une fois et non évaluables une fois."""
    for code in _INDICATEURS_A_GARDE:
        statuts = {lignes[code.value]["statut"] for lignes in attendu["indicateurs"].values()}
        assert statuts == {"evalue", "non_evaluable"}, code


def test_chaque_garde_fou_bloquant_et_satisfait(attendu: dict[str, Any]) -> None:
    """Garde-fous IND-4 et IND-7 (volume) et IND-8 (IND-4 aux deux dates) : bloquant une fois,
    satisfait une fois."""
    for code, marque in (
        (CodeIndicateur.ind_4, _GARDE_FOU),
        (CodeIndicateur.ind_7, _GARDE_FOU),
        (CodeIndicateur.ind_8, _IND8_SANS_IND4),
    ):
        lignes = [entite[code.value] for entite in attendu["indicateurs"].values()]
        assert any(ligne["statut"] == "evalue" for ligne in lignes), code
        assert any(
            ligne["statut"] == "non_evaluable" and marque in ligne["motif"] for ligne in lignes
        ), code


# --- Réconciliation ---


def test_kpi_reconcilies_a_100_pourcent(calcul: _Calcul, attendu: dict[str, Any]) -> None:
    """3 périmètres × 22 lignes à D, couples entiers égaux, sans ligne en plus ni en moins,
    dans l'ordre promis (périmètres, puis `CODES_KPI` et `DIMENSIONS_KPI`)."""
    attendus: dict[tuple[str, str, str], Couple] = {
        (perimetre, code, dimension): _couple(valeur, f"kpi.{perimetre}.{code}.{dimension!r}")
        for perimetre, codes in attendu["kpi"].items()
        for code, dimensions in codes.items()
        for dimension, valeur in dimensions.items()
    }
    du_jour = calcul.kpi.filter(pl.col("date") == calcul.date_arrete)
    lignes = du_jour.select(
        "perimetre", "code_kpi", "dimension", "numerateur", "denominateur"
    ).rows()
    calcules: dict[tuple[str, str, str], Couple] = {
        (perimetre, code, dimension): (_entier(numerateur), _entier(denominateur))
        for perimetre, code, dimension, numerateur, denominateur in lignes
    }
    lignes_par_perimetre = sum(len(DIMENSIONS_KPI[code]) for code in CODES_KPI)
    assert lignes_par_perimetre == 22
    assert du_jour.height == len(calcules) == 3 * lignes_par_perimetre
    assert calcules == attendus, _ecarts(calcules, attendus)
    ordre_promis = [
        (perimetre, code, dimension)
        for perimetre in (*calcul.entites, PERIMETRE_PROGRAMME)
        for code in CODES_KPI
        for dimension in DIMENSIONS_KPI[code]
    ]
    assert [ligne[:3] for ligne in lignes] == ordre_promis


def test_indicateurs_reconcilies_a_100_pourcent(calcul: _Calcul, attendu: dict[str, Any]) -> None:
    """2 Entités × 8 indicateurs : statut, motif, couple et couleur égaux, dans l'ordre promis
    (Entités, puis `CodeIndicateur`)."""
    attendus: dict[tuple[str, str], tuple[str, str, Couple, str]] = {
        (entite, code): (
            ligne["statut"],
            ligne["motif"],
            _couple(ligne["valeur"], f"indicateurs.{entite}.{code}"),
            ligne["couleur"],
        )
        for entite, codes in attendu["indicateurs"].items()
        for code, ligne in codes.items()
    }
    table = calcul.indicateurs
    assert table.get_column("date").unique().to_list() == [calcul.date_arrete]
    lignes = table.select(
        "entite", "code", "statut", "motif", "numerateur", "denominateur", "couleur"
    ).rows()
    calcules: dict[tuple[str, str], tuple[str, str, Couple, str]] = {
        (entite, code): (statut, motif, (_entier(numerateur), _entier(denominateur)), couleur)
        for entite, code, statut, motif, numerateur, denominateur, couleur in lignes
    }
    assert table.height == len(calcules) == 2 * len(CodeIndicateur)
    assert calcules == attendus, _ecarts(calcules, attendus)
    ordre_promis = [(entite, code.value) for entite in calcul.entites for code in CodeIndicateur]
    assert [ligne[:2] for ligne in lignes] == ordre_promis


def test_meteo_reconciliee_a_100_pourcent(calcul: _Calcul, attendu: dict[str, Any]) -> None:
    """Couleur, Règles déclenchantes (valeur, opérateur, seuil, tickets) et `version_grille`
    attendue (empreinte de la Grille figée inscrite dans le YAML)."""
    version_attendue = attendu["version_grille"]
    assert calcul.version_grille == version_attendue
    _reconcilier_meteo(calcul.meteo, attendu["meteo"], calcul, version_attendue, "meteo")


def test_meteo_variantes_reconciliees(calcul: _Calcul, attendu: dict[str, Any]) -> None:
    """Agrégation orange et jaune, tickets en cause d'IND-2, 3, 6, 7, 8 : Grille du jeu dont
    des indicateurs sont rendus inactifs."""
    variantes = attendu["meteo_variantes"]
    assert len(variantes) == 2
    for rang, variante in enumerate(variantes, start=1):
        grille = _grille_sans(calcul.grille, variante["inactifs"])
        _reconcilier_meteo(
            calcul.meteo_avec(grille),
            variante["meteo"],
            calcul,
            calcul.version_grille,
            f"meteo_variantes[{rang}]",
        )
