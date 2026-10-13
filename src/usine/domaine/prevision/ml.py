"""Prévision `methode=ml` par agrégation de la probabilité de résolution d'une bloquante (FR-22).

Le Modèle ML (hors du domaine, `evaluation.zenodo.modele_ml`) estime la probabilité p qu'une
Anomalie bloquante ouverte soit résolue sous N Jours ouvrés (N = horizon de FR-20). Règle
d'agrégation de l'addendum PRD : la sortie du rouge de l'Entité exige qu'au moins k bloquantes
sur les S ouvertes soient résolues, k étant le plus petit nombre de résolutions qui ramène le
stock S − k hors de la règle IND-1 rouge (k = S − (seuil − 1) pour `>=`).

Hypothèses assumées et documentées : les S bloquantes se résolvent **indépendamment** avec la
même probabilité p (loi binomiale), et aucune nouvelle Entrée n'est comptée dans l'horizon.
P(sortie) = P(Binomiale(S, p) ≥ k), en nombres exacts. Fonction pure et déterministe ; les
facteurs explicatifs du Modèle ML relèvent de la Story 4.7.
"""

import math
from fractions import Fraction

from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import CodeIndicateur, Couleur, MeteoEntite, Operateur
from usine.contrats.prevision import MethodePrevision, Prevision, StatutPrevision
from usine.domaine.prevision.commun import avancer, declenche

DENOMINATEUR_MAX = 10**6
"""Dénominateur maximal de la probabilité publiée (approximation de la fraction exacte)."""


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


def prevoir_sortie_ml(meteo: MeteoEntite, p_bloquante: Fraction, horizon: int) -> Prevision:
    """`Prevision` `methode=ml` d'une Entité rouge à partir de la probabilité p d'une bloquante.

    Le stock S et le seuil viennent de la règle IND-1 rouge de `meteo`. Toute autre règle
    déclenchante rouge rend la Prévision non projetable (comme la Baseline). Sinon la
    probabilité de sortie est P(au moins k résolues sous `horizon`) ; elle vaut « sortie
    projetée » à partir de 1/2, avec une date estimée à la fin de l'horizon (le Modèle ML
    prédit une probabilité à N Jours ouvrés, pas une date).
    """
    if meteo.couleur is not Couleur.rouge:
        raise UsineErreur(f"Prévision ML {meteo.entite} : Météo {meteo.couleur}, rouge attendue")
    if horizon < 1:
        raise UsineErreur(f"Prévision ML {meteo.entite} : horizon {horizon} invalide")

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
            facteurs=(),
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
