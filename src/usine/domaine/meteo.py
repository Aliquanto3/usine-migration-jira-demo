"""Indicateurs de météo et Météo par Entité, selon la Grille (FR-15, FR-16, FR-17).

Fonctions pures : Date d'arrêté, Entités, Grille et `version_grille` arrivent en paramètre.
Seul IND-1 est calculé ici (walking skeleton) ; tout autre indicateur actif est refusé.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from fractions import Fraction

import polars as pl

from usine.contrats.calcul import SCHEMA_INDICATEUR, StatutIndicateur
from usine.contrats.config import GrilleMeteo, RegleIndicateur
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import (
    CodeIndicateur,
    Couleur,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.schemas import valider
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, STATUTS_FERMES, Gravite, TypeTicket

_COMPARAISONS: Mapping[Operateur, Callable[[Fraction, Fraction], bool]] = {
    Operateur.superieur_ou_egal: lambda valeur, seuil: valeur >= seuil,
    Operateur.superieur: lambda valeur, seuil: valeur > seuil,
}

_COULEURS_DE_REGLE: tuple[Couleur, ...] = tuple(
    couleur for couleur in sorted(Couleur, reverse=True) if couleur is not Couleur.vert
)
"""Couleurs portant un seuil, de la plus grave à la moins grave."""


@dataclass(frozen=True)
class _Mesure:
    """Valeur d'un indicateur pour une Entité et tickets en cause."""

    numerateur: int
    denominateur: int
    tickets_en_cause: tuple[str, ...]


def _indicateurs_actifs(grille: GrilleMeteo) -> dict[CodeIndicateur, RegleIndicateur]:
    """Indicateurs actifs de la Grille ; refuse ceux qui ne sont pas encore implémentés."""
    actifs = {code: regle for code, regle in grille.indicateurs.items() if regle.active}
    non_implementes = sorted(code.value for code in actifs if code is not CodeIndicateur.ind_1)
    if non_implementes:
        raise UsineErreur(
            f"Grille de météo : indicateur(s) actif(s) non implémenté(s) :"
            f" {', '.join(non_implementes)} (seul IND-1 est calculé)"
        )
    return actifs


def _verifier_entites(entites: Sequence[str]) -> None:
    doublons = sorted({e for e in entites if list(entites).count(e) > 1})
    if doublons:
        raise UsineErreur(f"Entités demandées en double : {', '.join(doublons)}")


def _ind1(etats: pl.DataFrame, date_arrete: date, entites: Sequence[str]) -> dict[str, _Mesure]:
    """IND-1 : Anomalies bloquantes ouvertes de chaque Entité en `date_arrete` (`n/1`)."""
    ouvertes = etats.filter(
        (pl.col("date") == date_arrete)
        & (pl.col("type_ticket") == TypeTicket.anomalie.value)
        & (pl.col("gravite") == Gravite.bloquante.value)
        & pl.col("statut").is_not_null()
        & ~pl.col("statut").cast(pl.Utf8).is_in([s.value for s in STATUTS_FERMES])
        & pl.col("entite").is_in(list(entites))
    )
    cles: dict[str, list[str]] = {entite: [] for entite in entites}
    for entite, cle in ouvertes.select("entite", "cle_ticket").iter_rows():
        cles[entite].append(cle)
    return {
        entite: _Mesure(len(liste), 1, tuple(sorted(liste, key=_cle_de_tri)))
        for entite, liste in cles.items()
    }


def _cle_de_tri(cle: str) -> tuple[str, int, str]:
    """`DEMO-2` avant `DEMO-10` : préfixe, puis numéro, puis clé entière."""
    prefixe, _, numero = cle.rpartition("-")
    return prefixe, int(numero) if numero.isdigit() else -1, cle


def _mesures(
    etats: pl.DataFrame, date_arrete: date, entites: Sequence[str], grille: GrilleMeteo
) -> dict[CodeIndicateur, tuple[RegleIndicateur, dict[str, _Mesure]]]:
    """Mesure de chaque indicateur actif, par Entité."""
    actifs = _indicateurs_actifs(grille)
    _verifier_entites(entites)
    etats = valider(etats, SCHEMA_TICKET_ETAT)
    # Un ticket créé reste dans l'état de chaque date suivante : une date sans ligne n'est
    # « aucun ticket créé » (vert) que si la table n'a aucune ligne antérieure. Sinon, la date
    # n'a pas été calculée (postérieure à la dernière date, week-end ou trou) : refusée.
    dates = etats.get_column("date")
    derniere = dates.max()
    if isinstance(derniere, date) and date_arrete > derniere:
        raise UsineErreur(
            f"Date d'arrêté {date_arrete.isoformat()} postérieure à la dernière date de l'état"
            f" des tickets reçu ({derniere.isoformat()}) : états non calculés jusque-là"
        )
    if not (dates == date_arrete).any() and (dates < date_arrete).any():
        raise UsineErreur(
            f"Date d'arrêté {date_arrete.isoformat()} absente de l'état des tickets reçu, qui"
            " a des dates antérieures : état non calculé à cette date (week-end ou trou)"
        )
    mesures: dict[CodeIndicateur, tuple[RegleIndicateur, dict[str, _Mesure]]] = {}
    for code, regle in actifs.items():
        # Seul IND-1 passe `_indicateurs_actifs`.
        mesures[code] = (regle, _ind1(etats, date_arrete, entites))
    return mesures


def _franchit(mesure: _Mesure, seuil: tuple[Operateur, Fraction]) -> bool:
    if mesure.denominateur == 0:
        return mesure.numerateur > 0
    operateur, valeur_seuil = seuil
    return _COMPARAISONS[operateur](Fraction(mesure.numerateur, mesure.denominateur), valeur_seuil)


def _couleur_franchie(regle: RegleIndicateur, mesure: _Mesure) -> Couleur:
    """Couleur la plus grave dont le seuil est franchi ; vert sinon."""
    for couleur in _COULEURS_DE_REGLE:
        seuil = regle.seuils.get(couleur)
        if seuil is not None and _franchit(mesure, seuil):
            return couleur
    return Couleur.vert


def indicateurs(
    tickets_etats: pl.DataFrame, date_arrete: date, entites: Sequence[str], grille: GrilleMeteo
) -> pl.DataFrame:
    """`SCHEMA_INDICATEUR` : une ligne par Entité et par indicateur actif, à `date_arrete`.

    Précondition : `tickets_etats` a été calculé pour chaque Jour ouvré entre sa première date
    et la Date d'arrêté (comme le fait `EtapeMeteo`). Une Date d'arrêté sans ligne n'est verte
    (« aucun ticket créé ») que si la table n'a aucune ligne antérieure ; sinon (postérieure à
    sa dernière date, week-end ou trou dans les dates calculées), elle est refusée.
    """
    mesures = _mesures(tickets_etats, date_arrete, entites, grille)
    lignes: dict[str, list[object]] = {colonne: [] for colonne in SCHEMA_INDICATEUR.colonnes}
    for entite in entites:
        for code, (regle, par_entite) in mesures.items():
            mesure = par_entite[entite]
            lignes["date"].append(date_arrete)
            lignes["entite"].append(entite)
            lignes["code"].append(code.value)
            lignes["statut"].append(StatutIndicateur.evalue.value)
            lignes["motif"].append("")
            lignes["numerateur"].append(mesure.numerateur)
            lignes["denominateur"].append(mesure.denominateur)
            lignes["couleur"].append(_couleur_franchie(regle, mesure).value)
    table = pl.DataFrame(lignes, schema=dict(SCHEMA_INDICATEUR.colonnes))
    return valider(table, SCHEMA_INDICATEUR)


def meteo(
    tickets_etats: pl.DataFrame,
    date_arrete: date,
    entites: Sequence[str],
    grille: GrilleMeteo,
    version_grille: str,
) -> tuple[MeteoEntite, ...]:
    """Météo de chaque Entité (ordre de `entites`) : la couleur la plus grave l'emporte.

    La `MeteoEntite` porte toutes les Règles déclenchantes de la couleur retenue ; elle est
    verte, sans règle, si aucun seuil actif n'est franchi.

    Précondition : `tickets_etats` a été calculé pour chaque Jour ouvré entre sa première date
    et la Date d'arrêté (comme le fait `EtapeMeteo`). Une Date d'arrêté sans ligne n'est verte
    (« aucun ticket créé ») que si la table n'a aucune ligne antérieure ; sinon (postérieure à
    sa dernière date, week-end ou trou dans les dates calculées), elle est refusée.
    """
    mesures = _mesures(tickets_etats, date_arrete, entites, grille)
    resultat: list[MeteoEntite] = []
    for entite in entites:
        franchies = {
            code: (regle, par_entite[entite], _couleur_franchie(regle, par_entite[entite]))
            for code, (regle, par_entite) in mesures.items()
        }
        couleur_retenue = max(
            (couleur for _, _, couleur in franchies.values()), default=Couleur.vert
        )
        regles: list[RegleDeclenchante] = []
        if couleur_retenue is not Couleur.vert:
            for code, (regle, mesure, couleur) in franchies.items():
                if couleur is not couleur_retenue:
                    continue
                operateur, valeur_seuil = regle.seuils[couleur]
                regles.append(
                    RegleDeclenchante(
                        code=code,
                        couleur=couleur,
                        operateur=operateur,
                        numerateur=mesure.numerateur,
                        denominateur=mesure.denominateur,
                        seuil_numerateur=valeur_seuil.numerator,
                        seuil_denominateur=valeur_seuil.denominator,
                        tickets_en_cause=mesure.tickets_en_cause,
                    )
                )
        resultat.append(
            MeteoEntite(
                date_arrete=date_arrete,
                entite=entite,
                couleur=couleur_retenue,
                regles=tuple(regles),
                version_grille=version_grille,
            )
        )
    return tuple(resultat)
