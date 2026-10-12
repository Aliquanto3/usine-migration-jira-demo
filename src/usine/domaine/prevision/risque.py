"""Risque d'entrée en rouge d'une Entité non rouge (FR-21, addendum PRD § E, H-8).

Fonction pure et déterministe, sans horloge ni hasard, en nombres exacts (`Fraction`). Pour
IND-1, IND-3 et IND-4, elle lit dans `SCHEMA_INDICATEUR` les `fenetre` derniers Jours ouvrés
de l'Entité finissant à la Date d'arrêté D, ajuste une droite des moindres carrés
(x = 0..n−1 rang du Jour ouvré, y = valeur de l'indicateur) :

    b = Σ(x − x̄)(y − ȳ) / Σ(x − x̄)²,  a = ȳ − b·x̄,  p(h) = a + b·(n − 1 + h)

et la projette de 1 à `horizon` Jours ouvrés après D. Le premier h où p(h) déclenche la règle
rouge de la Grille donne un `RisqueEntreeRouge` (franchissement estimé à D + h Jours ouvrés),
rendu avec la valeur projetée p(h). Un indicateur inactif, sans seuil rouge, non évaluable sur
un Jour ouvré de la fenêtre ou à l'historique d'un seul Jour ouvré est écarté avec son motif.

Ce n'est pas la Baseline (vélocité nette sur `SerieStock`, `baseline`) : les primitives
communes (avance en Jours ouvrés, test de seuil) viennent de `commun` (AD-18).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from fractions import Fraction

import polars as pl

from usine.contrats.calcul import SCHEMA_INDICATEUR, StatutIndicateur
from usine.contrats.calendrier import est_jour_ouvre, jour_ouvre_suivant
from usine.contrats.config import GrilleMeteo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import CodeIndicateur, Couleur, MeteoEntite, Operateur
from usine.contrats.prevision import RisqueEntreeRouge
from usine.contrats.schemas import valider
from usine.domaine.prevision.commun import avancer, declenche

INDICATEURS_PROJETES: tuple[CodeIndicateur, ...] = (
    CodeIndicateur.ind_1,
    CodeIndicateur.ind_3,
    CodeIndicateur.ind_4,
)
"""Indicateurs projetés, dans l'ordre de `CodeIndicateur` (FR-21)."""


@dataclass(frozen=True)
class ParametresRisque:
    """Paramètres H-8 du Risque d'entrée en rouge, en Jours ouvrés (chacun entier ≥ 1)."""

    fenetre: int = 10
    horizon: int = 5

    def __post_init__(self) -> None:
        for nom in ("fenetre", "horizon"):
            valeur = getattr(self, nom)
            if type(valeur) is not int or valeur < 1:
                raise UsineErreur(
                    f"Risque d'entrée en rouge : paramètre {nom} invalide {valeur!r}"
                    " (entier ≥ 1 attendu)"
                )


@dataclass(frozen=True)
class RisqueProjete:
    """Risque d'entrée en rouge et valeur projetée au franchissement (hors contrat gelé)."""

    risque: RisqueEntreeRouge
    valeur_projetee: Fraction


@dataclass(frozen=True)
class IndicateurExclu:
    """Indicateur écarté du calcul du risque, avec son motif."""

    code: CodeIndicateur
    motif: str


@dataclass(frozen=True)
class ResultatRisque:
    """Risques détectés et indicateurs écartés, chacun dans l'ordre de `CodeIndicateur`."""

    risques: tuple[RisqueProjete, ...]
    exclus: tuple[IndicateurExclu, ...]


@dataclass(frozen=True)
class _Point:
    date: date
    statut: StatutIndicateur
    motif: str
    numerateur: int
    denominateur: int


def risques_entree_rouge(
    indicateurs: pl.DataFrame,
    meteo: MeteoEntite,
    grille: GrilleMeteo,
    parametres: ParametresRisque = ParametresRisque(),  # noqa: B008 (dataclass gelée)
) -> ResultatRisque:
    """Risques d'entrée en rouge de `meteo.entite` à `meteo.date_arrete` (FR-21).

    `indicateurs` suit `SCHEMA_INDICATEUR` et couvre chaque Jour ouvré de la fenêtre ; seules
    les lignes de l'Entité datées au plus D sont lues. Lève une `UsineErreur` nommant l'Entité
    si la Météo est rouge ou si la série d'un indicateur projeté est invalide.
    """
    entite, arrete = meteo.entite, meteo.date_arrete
    if meteo.couleur is Couleur.rouge:
        raise UsineErreur(f"Risque d'entrée en rouge {entite} : Météo rouge, non rouge attendue")
    a_projeter: list[tuple[CodeIndicateur, Operateur, Fraction]] = []
    exclus: list[IndicateurExclu] = []
    for code in INDICATEURS_PROJETES:
        regle = grille.indicateurs.get(code)
        if regle is None:
            exclus.append(IndicateurExclu(code, "indicateur absent de la Grille"))
        elif not regle.active:
            exclus.append(IndicateurExclu(code, "indicateur inactif dans la Grille"))
        elif Couleur.rouge not in regle.seuils:
            exclus.append(IndicateurExclu(code, "aucun seuil rouge dans la Grille"))
        else:
            operateur, seuil = regle.seuils[Couleur.rouge]
            a_projeter.append((code, operateur, seuil))

    risques: list[RisqueProjete] = []
    if a_projeter:
        table = _table(indicateurs, entite, arrete)
        for code, operateur, seuil in a_projeter:
            fenetre = _serie(table, meteo, code)[-parametres.fenetre :]
            non_evalue = next(
                (p for p in fenetre if p.statut is StatutIndicateur.non_evaluable), None
            )
            if non_evalue is not None:
                exclus.append(
                    IndicateurExclu(
                        code,
                        f"non évaluable le {non_evalue.date.isoformat()} : {non_evalue.motif}",
                    )
                )
                continue
            if len(fenetre) < 2:
                exclus.append(
                    IndicateurExclu(
                        code,
                        f"historique insuffisant : {len(fenetre)} Jour ouvré (2 au moins attendus)",
                    )
                )
                continue
            franchissement = _franchissement(fenetre, operateur, seuil, parametres.horizon)
            if franchissement is None:
                continue
            h, projetee = franchissement
            courant = fenetre[-1]
            risque = RisqueEntreeRouge(
                date_arrete=arrete,
                entite=entite,
                indicateur=code,
                date_franchissement_estimee=avancer(arrete, h),
                horizon_jours_ouvres=parametres.horizon,
                numerateur=courant.numerateur,
                denominateur=courant.denominateur,
                seuil_numerateur=seuil.numerator,
                seuil_denominateur=seuil.denominator,
                version_grille=meteo.version_grille,
            )
            risques.append(RisqueProjete(risque=risque, valeur_projetee=projetee))

    ordre = {code: rang for rang, code in enumerate(CodeIndicateur)}
    exclus.sort(key=lambda e: ordre[e.code])
    return ResultatRisque(risques=tuple(risques), exclus=tuple(exclus))


def _table(indicateurs: pl.DataFrame, entite: str, arrete: date) -> pl.DataFrame:
    """Lignes de l'Entité datées au plus D, table validée."""
    try:
        table = valider(indicateurs, SCHEMA_INDICATEUR)
    except UsineErreur as exc:
        raise UsineErreur(f"Risque d'entrée en rouge {entite} : {exc}") from exc
    return table.filter((pl.col("entite") == entite) & (pl.col("date") <= arrete))


def _serie(table: pl.DataFrame, meteo: MeteoEntite, code: CodeIndicateur) -> list[_Point]:
    """Points de `code` jusqu'à D, contrôlés (Jours ouvrés consécutifs finissant à D)."""
    entite, arrete = meteo.entite, meteo.date_arrete
    prefixe = f"Risque d'entrée en rouge {entite} {code}"
    lignes = table.filter(pl.col("code") == code.value).sort("date").to_dicts()
    points: list[_Point] = []
    for ligne in lignes:
        jour: date = ligne["date"]
        if not est_jour_ouvre(jour):
            raise UsineErreur(f"{prefixe} : {jour.isoformat()} n'est pas un Jour ouvré")
        if points and points[-1].date == jour:
            raise UsineErreur(f"{prefixe} : date {jour.isoformat()} en double")
        if points and jour_ouvre_suivant(points[-1].date) != jour:
            raise UsineErreur(
                f"{prefixe} : trou de Jours ouvrés entre"
                f" {points[-1].date.isoformat()} et {jour.isoformat()}"
            )
        statut = StatutIndicateur(ligne["statut"])
        if statut is StatutIndicateur.evalue and ligne["denominateur"] <= 0:
            raise UsineErreur(
                f"{prefixe} : valeur évaluée {ligne['numerateur']}/{ligne['denominateur']}"
                f" le {jour.isoformat()} (dénominateur > 0 attendu)"
            )
        points.append(
            _Point(
                date=jour,
                statut=statut,
                motif=ligne["motif"],
                numerateur=ligne["numerateur"],
                denominateur=ligne["denominateur"],
            )
        )
    if not points or points[-1].date != arrete:
        raise UsineErreur(
            f"{prefixe} : Date d'arrêté {arrete.isoformat()} absente de la table des indicateurs"
        )
    return points


def _franchissement(
    fenetre: Sequence[_Point], operateur: Operateur, seuil: Fraction, horizon: int
) -> tuple[int, Fraction] | None:
    """Premier h ∈ [1, horizon] où la droite des moindres carrés déclenche, avec p(h)."""
    n = len(fenetre)
    ys = [Fraction(p.numerateur, p.denominateur) for p in fenetre]
    x_moyen = Fraction(n - 1, 2)
    y_moyen = sum(ys, Fraction(0)) / n
    covariance = sum(((x - x_moyen) * (y - y_moyen) for x, y in enumerate(ys)), Fraction(0))
    variance = sum(((x - x_moyen) ** 2 for x in range(n)), Fraction(0))
    pente = covariance / variance
    ordonnee = y_moyen - pente * x_moyen
    for h in range(1, horizon + 1):
        projetee = ordonnee + pente * (n - 1 + h)
        if declenche(projetee, operateur, seuil):
            return h, projetee
    return None
