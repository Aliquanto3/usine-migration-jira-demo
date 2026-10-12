"""KPI quotidiens par Entité et pour le Programme (FR-11, H-17, H-19, AD-9, AD-10, AD-17).

Fonction pure : l'état des tickets de chaque Jour ouvré (`SCHEMA_TICKET_ETAT`) et les Entités
arrivent en paramètre. Sortie dense au `SCHEMA_KPI` (format long) : une ligne par date,
périmètre, code et dimension, zéro explicite, jamais de ligne absente. Comptes en `n/1` ;
âges et taux en `numerateur`/`denominateur` entiers, `0/0` quand la valeur est sans objet.
"""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from enum import StrEnum
from fractions import Fraction

import polars as pl

from usine.contrats.calcul import PERIMETRE_PROGRAMME, SCHEMA_KPI
from usine.contrats.calendrier import (
    est_jour_ouvre,
    fenetre_glissante,
    jour_ouvre_precedent,
    jours_ouvres,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.schemas import valider
from usine.contrats.tickets import (
    SCHEMA_TICKET_ETAT,
    STATUTS_FERMES,
    Gravite,
    Phase,
    StatutCertification,
    StatutTest,
    TypeTicket,
)

ANOMALIES_OUVERTES = "anomalies_ouvertes"
ANOMALIES_OUVERTES_GRAVITE = "anomalies_ouvertes_gravite"
ANOMALIES_OUVERTES_PHASE = "anomalies_ouvertes_phase"
ENTREES_JOUR = "entrees_jour"
SORTIES_JOUR = "sorties_jour"
ENTREES_FENETRE = "entrees_fenetre"
SORTIES_FENETRE = "sorties_fenetre"
AGE_MEDIAN_ANOMALIES_OUVERTES = "age_median_anomalies_ouvertes"
AGE_MAX_ANOMALIES_OUVERTES = "age_max_anomalies_ouvertes"
TAUX_KO_CAS_DE_TEST = "taux_ko_cas_de_test"
TAUX_NON_EXECUTION_CAS_DE_TEST = "taux_non_execution_cas_de_test"
CERTIFICATIONS = "certifications"

_SANS_DIMENSION: tuple[str, ...] = ("",)


def _dimensions(enumeration: type[StrEnum]) -> tuple[str, ...]:
    return tuple(membre.value for membre in enumeration)


CODES_KPI: tuple[str, ...] = (
    ANOMALIES_OUVERTES,
    ANOMALIES_OUVERTES_GRAVITE,
    ANOMALIES_OUVERTES_PHASE,
    ENTREES_JOUR,
    SORTIES_JOUR,
    ENTREES_FENETRE,
    SORTIES_FENETRE,
    AGE_MEDIAN_ANOMALIES_OUVERTES,
    AGE_MAX_ANOMALIES_OUVERTES,
    TAUX_KO_CAS_DE_TEST,
    TAUX_NON_EXECUTION_CAS_DE_TEST,
    CERTIFICATIONS,
)
"""Catalogue des KPI quotidiens, dans l'ordre figé des lignes de sortie."""

DIMENSIONS_KPI: dict[str, tuple[str, ...]] = {
    ANOMALIES_OUVERTES: _SANS_DIMENSION,
    ANOMALIES_OUVERTES_GRAVITE: _dimensions(Gravite),
    ANOMALIES_OUVERTES_PHASE: _dimensions(Phase),
    ENTREES_JOUR: _SANS_DIMENSION,
    SORTIES_JOUR: _SANS_DIMENSION,
    ENTREES_FENETRE: _SANS_DIMENSION,
    SORTIES_FENETRE: _SANS_DIMENSION,
    AGE_MEDIAN_ANOMALIES_OUVERTES: _SANS_DIMENSION,
    AGE_MAX_ANOMALIES_OUVERTES: _SANS_DIMENSION,
    TAUX_KO_CAS_DE_TEST: _dimensions(Phase),
    TAUX_NON_EXECUTION_CAS_DE_TEST: _dimensions(Phase),
    CERTIFICATIONS: _dimensions(StatutCertification),
}
"""Dimensions de chaque code, dans l'ordre de l'énumération ; `""` = KPI non ventilé."""

_CODES_SANS_VALEUR_PAR_DEFAUT = frozenset(
    {
        AGE_MEDIAN_ANOMALIES_OUVERTES,
        AGE_MAX_ANOMALIES_OUVERTES,
        TAUX_KO_CAS_DE_TEST,
        TAUX_NON_EXECUTION_CAS_DE_TEST,
    }
)
"""Codes valant `0/0` (« pas de valeur ») sans donnée ; les comptes valent `0/1`."""

_FERMES = [statut.value for statut in STATUTS_FERMES]

_Cle = tuple[date, str, str, str]
"""(date, périmètre, code, dimension)."""


def _verifier_entites(entites: Sequence[str]) -> None:
    doublons = sorted({e for e in entites if list(entites).count(e) > 1})
    if doublons:
        raise UsineErreur(f"Entités demandées en double : {', '.join(doublons)}")
    if PERIMETRE_PROGRAMME in entites:
        raise UsineErreur(
            f"Entité demandée « {PERIMETRE_PROGRAMME} » : valeur réservée au périmètre Programme"
        )


def _verifier_dates(dates: Sequence[date]) -> None:
    """Refuse une date non ouvrée ou un Jour ouvré manquant entre la première et la dernière."""
    non_ouvres = [d.isoformat() for d in dates if not est_jour_ouvre(d)]
    if non_ouvres:
        raise UsineErreur(
            f"KPI : date(s) de l'état des tickets hors Jour ouvré : {', '.join(non_ouvres)}"
        )
    presentes = set(dates)
    manquantes = [d.isoformat() for d in jours_ouvres(dates[0], dates[-1]) if d not in presentes]
    if manquantes:
        raise UsineErreur(
            "KPI : état des tickets non calculé pour le(s) Jour(s) ouvré(s)"
            f" {', '.join(manquantes)} (dates contiguës attendues de {dates[0].isoformat()}"
            f" à {dates[-1].isoformat()})"
        )


def _par_perimetre(table: pl.DataFrame, entites: Sequence[str]) -> pl.DataFrame:
    """Chaque ligne une fois pour son Entité (si demandée), une fois pour le Programme."""
    return pl.concat(
        [
            table.filter(pl.col("entite").is_in(list(entites))).with_columns(
                pl.col("entite").alias("perimetre")
            ),
            table.with_columns(pl.lit(PERIMETRE_PROGRAMME, dtype=pl.Utf8).alias("perimetre")),
        ],
        how="vertical",
    )


def _anomalies(etats: pl.DataFrame, dates: Sequence[date]) -> pl.DataFrame:
    """Anomalies avec `ouvert`, `entree` (0/1), `sortie` (`entree − δ`) et `age`."""
    anomalies = etats.filter(pl.col("type_ticket") == TypeTicket.anomalie.value).with_columns(
        (pl.col("statut").is_not_null() & ~pl.col("statut").cast(pl.Utf8).is_in(_FERMES))
        .cast(pl.Int64)
        .alias("ouvert"),
        (pl.col("date_derniere_entree") == pl.col("date"))
        .fill_null(False)
        .cast(pl.Int64)
        .alias("entree"),
    )
    veilles = {d: jour_ouvre_precedent(d) for d in dates}
    veille = anomalies.select(
        "cle_ticket",
        pl.col("date")
        .replace_strict(
            list(veilles.values()), list(veilles.keys()), default=None, return_dtype=pl.Date()
        )
        .alias("date"),
        pl.col("ouvert").alias("ouvert_veille"),
    ).filter(pl.col("date").is_not_null())
    anomalies = anomalies.join(veille, on=["cle_ticket", "date"], how="left").with_columns(
        (pl.col("entree") - (pl.col("ouvert") - pl.col("ouvert_veille").fill_null(0))).alias(
            "sortie"
        )
    )
    sans_entree = anomalies.filter(
        (pl.col("ouvert") == 1) & pl.col("date_derniere_entree").is_null()
    )
    if sans_entree.height:
        cle, jour = sans_entree.select("cle_ticket", "date").row(0)
        raise UsineErreur(
            f"KPI : Anomalie {cle} ouverte le {jour.isoformat()} sans date de dernière Entrée"
        )
    incoherentes = anomalies.filter(pl.col("sortie") < 0)
    if incoherentes.height:
        cle, jour = incoherentes.select("cle_ticket", "date").row(0)
        raise UsineErreur(
            f"KPI : Anomalie {cle} ouverte le {jour.isoformat()} sans Entrée ce jour-là ni"
            " ouverture la veille (état des tickets incomplet ou incohérent)"
        )
    paires = (
        anomalies.filter(pl.col("ouvert") == 1)
        .select("date_derniere_entree", "date")
        .unique()
        .rows()
    )
    ages = pl.DataFrame(
        {
            "date_derniere_entree": [entree for entree, _ in paires],
            "date": [jour for _, jour in paires],
            "age": [len(jours_ouvres(entree, jour)) - 1 for entree, jour in paires],
        },
        schema={"date_derniere_entree": pl.Date(), "date": pl.Date(), "age": pl.Int64()},
    )
    return anomalies.join(ages, on=["date_derniere_entree", "date"], how="left")


def _mediane(ages: list[int]) -> Fraction:
    tries = sorted(ages)
    milieu = len(tries) // 2
    if len(tries) % 2:
        return Fraction(tries[milieu])
    return Fraction(tries[milieu - 1] + tries[milieu], 2)


def _valeurs(
    etats: pl.DataFrame, entites: Sequence[str], dates: Sequence[date]
) -> dict[_Cle, tuple[int, int]]:
    """Valeurs non par défaut, par (date, périmètre, code, dimension)."""
    valeurs: dict[_Cle, tuple[int, int]] = {}
    anomalies = _par_perimetre(_anomalies(etats, dates), entites)
    ouvertes = anomalies.filter(pl.col("ouvert") == 1)

    for jour, perimetre, nombre, ages in (
        ouvertes.group_by("date", "perimetre").agg(pl.len(), pl.col("age")).iter_rows()
    ):
        valeurs[(jour, perimetre, ANOMALIES_OUVERTES, "")] = (nombre, 1)
        mediane = _mediane(ages)
        valeurs[(jour, perimetre, AGE_MEDIAN_ANOMALIES_OUVERTES, "")] = (
            mediane.numerator,
            mediane.denominator,
        )
        valeurs[(jour, perimetre, AGE_MAX_ANOMALIES_OUVERTES, "")] = (max(ages), 1)
    for code, colonne in (
        (ANOMALIES_OUVERTES_GRAVITE, "gravite"),
        (ANOMALIES_OUVERTES_PHASE, "phase"),
    ):
        for jour, perimetre, dimension, nombre in (
            ouvertes.filter(pl.col(colonne).is_not_null())
            .group_by("date", "perimetre", pl.col(colonne).cast(pl.Utf8))
            .len()
            .iter_rows()
        ):
            valeurs[(jour, perimetre, code, dimension)] = (nombre, 1)

    mouvements: dict[tuple[date, str], tuple[int, int]] = {}
    for jour, perimetre, entrees, sorties in (
        anomalies.group_by("date", "perimetre")
        .agg(pl.col("entree").sum(), pl.col("sortie").sum())
        .iter_rows()
    ):
        mouvements[(jour, perimetre)] = (entrees, sorties)
        valeurs[(jour, perimetre, ENTREES_JOUR, "")] = (entrees, 1)
        valeurs[(jour, perimetre, SORTIES_JOUR, "")] = (sorties, 1)
    for jour in dates:
        fenetre = fenetre_glissante(jour)
        for perimetre in (*entites, PERIMETRE_PROGRAMME):
            du_jour = [mouvements.get((d, perimetre), (0, 0)) for d in fenetre]
            valeurs[(jour, perimetre, ENTREES_FENETRE, "")] = (sum(e for e, _ in du_jour), 1)
            valeurs[(jour, perimetre, SORTIES_FENETRE, "")] = (sum(s for _, s in du_jour), 1)

    cas = _par_perimetre(
        etats.filter(
            (pl.col("type_ticket") == TypeTicket.cas_de_test.value)
            & pl.col("phase").is_not_null()
            & pl.col("statut_test").is_not_null()
        ),
        entites,
    )
    statuts: dict[tuple[date, str, str], dict[str, int]] = defaultdict(dict)
    for jour, perimetre, phase, statut, nombre in (
        cas.group_by(
            "date", "perimetre", pl.col("phase").cast(pl.Utf8), pl.col("statut_test").cast(pl.Utf8)
        )
        .len()
        .iter_rows()
    ):
        statuts[(jour, perimetre, phase)][statut] = nombre
    for (jour, perimetre, phase), comptes in statuts.items():
        ok = comptes.get(StatutTest.ok.value, 0)
        ko = comptes.get(StatutTest.ko.value, 0)
        non_executes = comptes.get(StatutTest.non_execute.value, 0)
        valeurs[(jour, perimetre, TAUX_KO_CAS_DE_TEST, phase)] = (ko, ok + ko)
        valeurs[(jour, perimetre, TAUX_NON_EXECUTION_CAS_DE_TEST, phase)] = (
            non_executes,
            ok + ko + non_executes,
        )

    certifications = _par_perimetre(
        etats.filter(
            (pl.col("type_ticket") == TypeTicket.certification.value)
            & pl.col("statut_certification").is_not_null()
        ),
        entites,
    )
    for jour, perimetre, statut, nombre in (
        certifications.group_by("date", "perimetre", pl.col("statut_certification").cast(pl.Utf8))
        .len()
        .iter_rows()
    ):
        valeurs[(jour, perimetre, CERTIFICATIONS, statut)] = (nombre, 1)
    return valeurs


def kpi(tickets_etats: pl.DataFrame, entites: Sequence[str]) -> pl.DataFrame:
    """`SCHEMA_KPI` : les douze KPI de `CODES_KPI` pour chaque Jour ouvré de `tickets_etats`.

    Périmètres : chaque Entité de `entites` (dans cet ordre), puis `PERIMETRE_PROGRAMME`, qui
    compte toutes les lignes de la table (Entités hors de `entites` comprises). Anomalie
    ouverte = statut hors `STATUTS_FERMES` ; Entrée en D si `date_derniere_entree == D` ;
    Sortie = Entrée − (ouvert(D) − ouvert(D−1)), au périmètre de l'Entité du ticket en D.
    Fenêtre glissante : somme des 5 derniers Jours ouvrés, D compris (jours hors table = 0).
    Âge = Jours ouvrés depuis la dernière Entrée. Taux de KO = KO / (OK + KO) ; taux de
    non-exécution = non exécutés / Cas de test ayant un statut, par Phase.

    Un changement d'Entité n'est ni une Entrée ni une Sortie : stock(D) − stock(D−1) =
    entrées − sorties vaut toujours pour le Programme, et par Entité seulement sans transfert.
    Une Anomalie sans Gravité ou sans Phase compte dans les totaux mais dans aucune
    ventilation ; un Cas de test sans Phase, ou un ticket sans statut (Anomalie non ouverte,
    Cas de test ou Certification), n'entre dans aucune ventilation.

    Précondition : la table couvre chaque Jour ouvré de sa première à sa dernière date (sinon
    `UsineErreur`) ; à sa première date, la veille est vide (début de l'historique).
    """
    _verifier_entites(entites)
    etats = valider(tickets_etats, SCHEMA_TICKET_ETAT)
    dates: list[date] = sorted(etats.get_column("date").unique().to_list())
    lignes: dict[str, list[object]] = {colonne: [] for colonne in SCHEMA_KPI.colonnes}
    if dates:
        _verifier_dates(dates)
        valeurs = _valeurs(etats, entites, dates)
        for jour in dates:
            for perimetre in (*entites, PERIMETRE_PROGRAMME):
                for code in CODES_KPI:
                    defaut = (0, 0) if code in _CODES_SANS_VALEUR_PAR_DEFAUT else (0, 1)
                    for dimension in DIMENSIONS_KPI[code]:
                        numerateur, denominateur = valeurs.get(
                            (jour, perimetre, code, dimension), defaut
                        )
                        lignes["date"].append(jour)
                        lignes["perimetre"].append(perimetre)
                        lignes["code_kpi"].append(code)
                        lignes["dimension"].append(dimension)
                        lignes["numerateur"].append(numerateur)
                        lignes["denominateur"].append(denominateur)
    table = pl.DataFrame(lignes, schema=dict(SCHEMA_KPI.colonnes))
    return valider(table, SCHEMA_KPI)
