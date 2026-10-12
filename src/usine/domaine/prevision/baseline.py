"""Baseline de sortie du rouge (FR-20, AD-18, addendum PRD § E, H-7).

Fonction pure et déterministe, sans horloge ni hasard, en nombres exacts (`Fraction`). Elle
lit la `SerieStock` d'une Entité (stock, Entrées et Sorties d'Anomalies bloquantes par Jour
ouvré) et sa `MeteoEntite` rouge à la Date d'arrêté D, et renvoie une `Prevision`
(`methode=baseline`) :

- vélocité nette v = Σ(Sorties − Entrées) / nombre de Jours ouvrés, sur les
  `fenetre_velocite` Jours ouvrés finissant à D présents dans la série ;
- date de sortie = D avancée du premier nombre t ≥ 1 de Jours ouvrés où le stock projeté
  S − v·t ne déclenche plus la règle IND-1 rouge (`>=` : sous le seuil ; `>` : au plus le seuil) ;
- fourchette = vélocités aux centiles 25 et 75 (interpolation linéaire, « type 7 ») des
  fenêtres glissantes complètes de `fenetre_fourchette` Jours ouvrés incluses dans les
  `profondeur_fourchette` derniers ; optimiste pour max(P75, v), pessimiste pour min(P25, v)
  si positive ;
- probabilité = part de ces fenêtres dont la vélocité ramène le stock sous le seuil dans
  l'horizon ;
- facteurs : stock, Entrées, Sorties, vélocité nette et sa variation.

Toute Règle déclenchante rouge autre qu'IND-1 est non projetable : aucune date, probabilité
0/1, facteurs conservés. C'est l'unique implémentation de la Baseline du dépôt (AD-18).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from fractions import Fraction

import polars as pl

from usine.contrats.calendrier import est_jour_ouvre, jour_ouvre_suivant
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import CodeIndicateur, Couleur, MeteoEntite, Operateur
from usine.contrats.prevision import (
    SCHEMA_SERIE_STOCK,
    FacteurExplicatif,
    MethodePrevision,
    Prevision,
    StatutPrevision,
)
from usine.contrats.schemas import valider

STOCK = "stock"
ENTREES = "entrees"
SORTIES = "sorties"
VELOCITE_NETTE = "velocite_nette"
VARIATION_VELOCITE = "variation_velocite"


@dataclass(frozen=True)
class ParametresBaseline:
    """Paramètres H-7 de la Baseline, en Jours ouvrés (chacun entier ≥ 1)."""

    fenetre_velocite: int = 10
    horizon: int = 10
    fenetre_fourchette: int = 5
    profondeur_fourchette: int = 20

    def __post_init__(self) -> None:
        for nom in ("fenetre_velocite", "horizon", "fenetre_fourchette", "profondeur_fourchette"):
            valeur = getattr(self, nom)
            if type(valeur) is not int or valeur < 1:
                raise UsineErreur(
                    f"Baseline : paramètre {nom} invalide {valeur!r} (entier ≥ 1 attendu)"
                )


@dataclass(frozen=True)
class _Jour:
    date: date
    stock: int
    net: int
    """Sorties − Entrées du Jour ouvré."""
    entrees: int
    sorties: int


def prevoir_sortie(
    serie: pl.DataFrame,
    meteo: MeteoEntite,
    parametres: ParametresBaseline = ParametresBaseline(),  # noqa: B008 (dataclass gelée)
) -> Prevision:
    """Prévision de sortie du rouge de `meteo.entite` à `meteo.date_arrete` par la Baseline.

    `serie` suit `SCHEMA_SERIE_STOCK` ; seules les lignes de la série `meteo.entite` datées au
    plus D sont lues, et elles doivent former des Jours ouvrés consécutifs finissant à D.
    Lève une `UsineErreur` nommant l'Entité si la Météo n'est pas rouge ou si la série est
    invalide.
    """
    entite = meteo.entite
    if meteo.couleur is not Couleur.rouge:
        raise UsineErreur(f"Baseline {entite} : Météo {meteo.couleur}, rouge attendue")
    jours = _jours(serie, meteo)
    fenetre = jours[-parametres.fenetre_velocite :]
    precedents = jours[: -len(fenetre)][-parametres.fenetre_velocite :]
    velocite = _velocite(fenetre)
    variation = velocite - _velocite(precedents) if precedents else Fraction(0)
    stock = jours[-1].stock
    facteurs = _facteurs(stock, fenetre, velocite, variation, len(precedents))

    def prevision(
        statut: StatutPrevision,
        probabilite: tuple[int, int],
        dates: tuple[date | None, date | None, date | None] = (None, None, None),
        non_projetables: tuple[CodeIndicateur, ...] = (),
    ) -> Prevision:
        return Prevision(
            date_arrete=meteo.date_arrete,
            entite=entite,
            methode=MethodePrevision.baseline,
            statut=statut,
            date_sortie_optimiste=dates[0],
            date_sortie_estimee=dates[1],
            date_sortie_pessimiste=dates[2],
            probabilite_numerateur=probabilite[0],
            probabilite_denominateur=probabilite[1],
            horizon_jours_ouvres=parametres.horizon,
            facteurs=facteurs,
            regles_non_projetables=non_projetables,
            version_grille=meteo.version_grille,
        )

    non_projetables = tuple(
        dict.fromkeys(r.code for r in meteo.regles if r.code is not CodeIndicateur.ind_1)
    )
    if non_projetables:
        return prevision(
            StatutPrevision.regle_non_projetable, (0, 1), non_projetables=non_projetables
        )

    regle = next(r for r in meteo.regles if r.code is CodeIndicateur.ind_1)
    seuil = Fraction(regle.seuil_numerateur, regle.seuil_denominateur)
    rouge = stock >= seuil if regle.operateur is Operateur.superieur_ou_egal else stock > seuil
    if not rouge:
        raise UsineErreur(
            f"Baseline {entite} : stock {stock} à {meteo.date_arrete.isoformat()} ne déclenche"
            f" pas la règle IND-1 rouge {regle.operateur} {seuil}"
        )

    def jours_a_la_sortie(w: Fraction) -> int:
        return _jours_a_la_sortie(stock, seuil, regle.operateur, w)

    profondeur = jours[-parametres.profondeur_fourchette :]
    taille = parametres.fenetre_fourchette
    velocites = [
        _velocite(profondeur[i : i + taille]) for i in range(len(profondeur) - taille + 1)
    ] or [velocite]
    reussites = sum(1 for w in velocites if w > 0 and jours_a_la_sortie(w) <= parametres.horizon)
    probabilite = (reussites, len(velocites))
    if velocite <= 0:
        return prevision(StatutPrevision.pas_de_sortie_projetee, probabilite)

    def date_pour(w: Fraction) -> date:
        return _avancer(meteo.date_arrete, jours_a_la_sortie(w))

    triees = sorted(velocites)
    optimiste = max(_centile(triees, Fraction(3, 4)), velocite)
    pessimiste = min(_centile(triees, Fraction(1, 4)), velocite)
    return prevision(
        StatutPrevision.sortie_projetee,
        probabilite,
        (
            date_pour(optimiste),
            date_pour(velocite),
            date_pour(pessimiste) if pessimiste > 0 else None,
        ),
    )


def _jours(serie: pl.DataFrame, meteo: MeteoEntite) -> list[_Jour]:
    """Jours ouvrés de la série de l'Entité jusqu'à D, contrôlés et dans l'ordre."""
    entite, arrete = meteo.entite, meteo.date_arrete
    try:
        table = valider(serie, SCHEMA_SERIE_STOCK)
    except UsineErreur as exc:
        raise UsineErreur(f"Baseline {entite} : {exc}") from exc
    lignes = (
        table.filter((pl.col("serie") == entite) & (pl.col("date") <= arrete))
        .sort("date")
        .to_dicts()
    )
    jours: list[_Jour] = []
    for ligne in lignes:
        jour: date = ligne["date"]
        if not est_jour_ouvre(jour):
            raise UsineErreur(f"Baseline {entite} : {jour.isoformat()} n'est pas un Jour ouvré")
        if jours and jours[-1].date == jour:
            raise UsineErreur(f"Baseline {entite} : date {jour.isoformat()} en double")
        if jours and jour_ouvre_suivant(jours[-1].date) != jour:
            raise UsineErreur(
                f"Baseline {entite} : trou de Jours ouvrés entre"
                f" {jours[-1].date.isoformat()} et {jour.isoformat()}"
            )
        jours.append(
            _Jour(
                date=jour,
                stock=ligne["stock"],
                net=ligne["sorties"] - ligne["entrees"],
                entrees=ligne["entrees"],
                sorties=ligne["sorties"],
            )
        )
    if not jours or jours[-1].date != arrete:
        raise UsineErreur(
            f"Baseline {entite} : Date d'arrêté {arrete.isoformat()} absente de la série"
        )
    return jours


def _velocite(jours: Sequence[_Jour]) -> Fraction:
    """Moyenne par Jour ouvré de Sorties − Entrées (`jours` non vide)."""
    return Fraction(sum(j.net for j in jours), len(jours))


def _jours_a_la_sortie(stock: int, seuil: Fraction, operateur: Operateur, w: Fraction) -> int:
    """Premier t ≥ 1 où `stock − w·t` ne déclenche plus la règle (`w > 0`)."""
    ecart = (stock - seuil) / w
    t = math.floor(ecart) + 1 if operateur is Operateur.superieur_ou_egal else math.ceil(ecart)
    return max(t, 1)


def _avancer(jour: date, n: int) -> date:
    """`jour` avancé de `n` Jours ouvrés."""
    for _ in range(n):
        jour = jour_ouvre_suivant(jour)
    return jour


def _centile(triees: Sequence[Fraction], p: Fraction) -> Fraction:
    """Centile `p` par interpolation linéaire exacte (« type 7 ») de valeurs triées."""
    h = (len(triees) - 1) * p
    bas = math.floor(h)
    if bas + 1 >= len(triees):
        return triees[bas]
    return triees[bas] + (h - bas) * (triees[bas + 1] - triees[bas])


def _fraction(nom: str, libelle: str, valeur: Fraction) -> FacteurExplicatif:
    return FacteurExplicatif(
        nom=nom, libelle=libelle, numerateur=valeur.numerator, denominateur=valeur.denominator
    )


def _facteurs(
    stock: int,
    fenetre: Sequence[_Jour],
    velocite: Fraction,
    variation: Fraction,
    precedents: int,
) -> tuple[FacteurExplicatif, ...]:
    n = len(fenetre)
    reference = (
        f"par rapport aux {precedents} Jours ouvrés précédents"
        if precedents
        else "(aucun Jour ouvré précédent)"
    )
    return (
        _fraction(STOCK, "Stock courant d'Anomalies bloquantes ouvertes", Fraction(stock)),
        _fraction(
            ENTREES,
            f"Entrées sur les {n} derniers Jours ouvrés",
            Fraction(sum(j.entrees for j in fenetre)),
        ),
        _fraction(
            SORTIES,
            f"Sorties sur les {n} derniers Jours ouvrés",
            Fraction(sum(j.sorties for j in fenetre)),
        ),
        _fraction(
            VELOCITE_NETTE, "Vélocité nette moyenne par Jour ouvré (Sorties − Entrées)", velocite
        ),
        _fraction(
            VARIATION_VELOCITE,
            f"Variation de la vélocité nette {reference}",
            variation,
        ),
    )
