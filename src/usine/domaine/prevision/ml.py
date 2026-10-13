"""Prévision `methode=ml` par agrégation de la probabilité de résolution d'une bloquante (FR-22).

Le Modèle ML (hors du domaine, `evaluation.zenodo.modele_ml`) estime la probabilité p qu'une
Anomalie bloquante ouverte soit résolue sous N Jours ouvrés (N = horizon de FR-20). Règle
d'agrégation de l'addendum PRD : la sortie du rouge de l'Entité exige qu'au moins k bloquantes
sur les S ouvertes soient résolues, k étant le plus petit nombre de résolutions qui ramène le
stock S − k hors de la règle IND-1 rouge (k = S − (seuil − 1) pour `>=`).

Hypothèses assumées et documentées : les S bloquantes se résolvent **indépendamment** avec la
même probabilité p (loi binomiale), et aucune nouvelle Entrée n'est comptée dans l'horizon.
P(sortie) = P(Binomiale(S, p) ≥ k), en nombres exacts. Fonction pure et déterministe ; les
facteurs explicatifs (Story 4.7) viennent des contributions de variables du Modèle ML
(`pred_contrib` de LightGBM, en log-cotes), libellées en français ici.
"""

import math
from collections.abc import Mapping
from fractions import Fraction

from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import CodeIndicateur, Couleur, MeteoEntite, Operateur
from usine.contrats.prevision import (
    FacteurExplicatif,
    MethodePrevision,
    Prevision,
    StatutPrevision,
)
from usine.domaine.prevision.commun import avancer, declenche

DENOMINATEUR_MAX = 10**6
"""Dénominateur maximal de la probabilité publiée (approximation de la fraction exacte)."""


MAX_FACTEURS = 5
"""Nombre maximal de facteurs explicatifs d'une Prévision ML (FR-23)."""
DENOMINATEUR_CONTRIBUTION = 1000
"""Les contributions (log-cotes) sont publiées au millième."""

_VARIABLES = {
    "stock": "Stock courant d'Anomalies bloquantes ouvertes",
    "variation_stock_10": "Variation du stock sur les 10 derniers Jours ouvrés",
    "stock_max_20": "Stock maximal des 20 derniers Jours ouvrés",
}
for _w in (5, 10, 20):
    _VARIABLES[f"entrees_{_w}"] = f"Entrées sur les {_w} derniers Jours ouvrés"
    _VARIABLES[f"sorties_{_w}"] = f"Sorties sur les {_w} derniers Jours ouvrés"


def libelle_variable(nom: str) -> str:
    """Libellé français d'une variable du Modèle ML ; une variable sans libellé est refusée.

    Garde-fou SM-C4 : une variable qu'on ne sait pas dire en mots simples n'entre pas dans le
    Modèle ML, quel que soit son gain d'AUC.
    """
    if nom not in _VARIABLES:
        raise UsineErreur(f"Prévision ML : variable {nom!r} sans libellé français")
    return _VARIABLES[nom]


def facteurs_depuis_contributions(
    contributions: Mapping[str, Fraction],
) -> tuple[FacteurExplicatif, ...]:
    """Au plus 5 facteurs : les plus fortes contributions (valeur absolue, puis nom) non nulles.

    La contribution est celle de la variable à la probabilité de résolution d'une bloquante, en
    log-cotes (positive : elle rend la sortie du rouge plus probable), arrondie au millième.
    """
    arrondies = {
        nom: Fraction(round(c * DENOMINATEUR_CONTRIBUTION), DENOMINATEUR_CONTRIBUTION)
        for nom, c in contributions.items()
    }
    retenus = sorted(
        ((nom, c) for nom, c in arrondies.items() if c != 0), key=lambda x: (-abs(x[1]), x[0])
    )[:MAX_FACTEURS]
    return tuple(
        FacteurExplicatif(
            nom=nom,
            libelle=f"{libelle_variable(nom)} : "
            + ("favorise" if c > 0 else "freine")
            + " la sortie du rouge",
            numerateur=c.numerator,
            denominateur=c.denominator,
        )
        for nom, c in retenus
    )


def resolutions_requises(stock: int, operateur: Operateur, seuil: Fraction) -> int:
    """Plus petit k tel que `stock − k` ne déclenche plus la règle (0 si elle ne l'est pas)."""
    if stock < 0:
        raise UsineErreur(f"Prévision ML : stock {stock} négatif")
    k = 0
    while declenche(Fraction(stock - k), operateur, seuil):
        k += 1
    return k


def probabilite_sortie(stock: int, k: int, p: Fraction) -> Fraction:
    """P(Binomiale(stock, p) ≥ k), exacte ; indépendance des résolutions assumée."""
    if not 0 <= p <= 1:
        raise UsineErreur(f"Prévision ML : probabilité de résolution {p} hors de [0, 1]")
    if k <= 0:
        return Fraction(1)
    if k > stock:
        return Fraction(0)
    return sum(
        (math.comb(stock, j) * p**j * (1 - p) ** (stock - j) for j in range(k, stock + 1)),
        Fraction(0),
    )


def prevoir_sortie_ml(
    meteo: MeteoEntite,
    p_bloquante: Fraction,
    horizon: int,
    contributions: Mapping[str, Fraction] | None = None,
) -> Prevision:
    """`Prevision` `methode=ml` d'une Entité rouge à partir de la probabilité p d'une bloquante.

    Le stock S et le seuil viennent de la règle IND-1 rouge de `meteo`. Toute autre règle
    déclenchante rouge rend la Prévision non projetable (comme la Baseline). Sinon la
    probabilité de sortie est P(au moins k résolues sous `horizon`) ; elle vaut « sortie
    projetée » à partir de 1/2, avec une date estimée à la fin de l'horizon (le Modèle ML
    prédit une probabilité à N Jours ouvrés, pas une date). `contributions` (variable → log-cotes)
    donne les facteurs explicatifs ; une Prévision non projetable n'en porte pas.
    """
    if meteo.couleur is not Couleur.rouge:
        raise UsineErreur(f"Prévision ML {meteo.entite} : Météo {meteo.couleur}, rouge attendue")
    if horizon < 1:
        raise UsineErreur(f"Prévision ML {meteo.entite} : horizon {horizon} invalide")

    facteurs = facteurs_depuis_contributions(contributions) if contributions else ()

    def prevision(
        statut: StatutPrevision,
        probabilite: Fraction,
        estimee: bool = False,
        non_projetables: tuple[CodeIndicateur, ...] = (),
    ) -> Prevision:
        return Prevision(
            date_arrete=meteo.date_arrete,
            entite=meteo.entite,
            methode=MethodePrevision.ml,
            statut=statut,
            date_sortie_estimee=avancer(meteo.date_arrete, horizon) if estimee else None,
            probabilite_numerateur=probabilite.numerator,
            probabilite_denominateur=probabilite.denominator,
            horizon_jours_ouvres=horizon,
            facteurs=() if non_projetables else facteurs,
            regles_non_projetables=non_projetables,
            version_grille=meteo.version_grille,
        )

    autres = tuple(
        dict.fromkeys(r.code for r in meteo.regles if r.code is not CodeIndicateur.ind_1)
    )
    if autres:
        return prevision(StatutPrevision.regle_non_projetable, Fraction(0), non_projetables=autres)
    regle = next(r for r in meteo.regles if r.code is CodeIndicateur.ind_1)
    seuil = Fraction(regle.seuil_numerateur, regle.seuil_denominateur)
    valeur = Fraction(regle.numerateur, regle.denominateur)
    if valeur.denominator != 1 or not declenche(valeur, regle.operateur, seuil):
        raise UsineErreur(
            f"Prévision ML {meteo.entite} : stock {valeur} ne déclenche pas IND-1 rouge"
        )
    stock = valeur.numerator
    k = resolutions_requises(stock, regle.operateur, seuil)
    exacte = probabilite_sortie(stock, k, p_bloquante)
    probabilite = exacte.limit_denominator(DENOMINATEUR_MAX)
    if probabilite >= Fraction(1, 2):
        return prevision(StatutPrevision.sortie_projetee, probabilite, estimee=True)
    return prevision(StatutPrevision.pas_de_sortie_projetee, probabilite)
