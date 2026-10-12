"""Métriques pures de la classification des Causes racines (SM-9).

Pour chaque Cause racine : précision = VP ÷ (VP + FP), rappel = VP ÷ (VP + FN),
F1 = 2·P·R ÷ (P + R), chacun valant 0 quand son dénominateur est nul. Une Anomalie non classée
(plafond de coût) compte comme un faux négatif de sa cause vraie. Le F1 macro est la moyenne
des F1 des Causes racines présentes dans la vérité ou dans les propositions.
"""

from collections.abc import Mapping
from typing import Any

from usine.contrats.erreurs import UsineErreur
from usine.contrats.tickets import CauseRacine, rang_cle

NON_CLASSE = "non_classe"
"""Colonne de la matrice de confusion des Anomalies sans proposition."""


def _ratio(numerateur: int, denominateur: int) -> float:
    return numerateur / denominateur if denominateur else 0.0


def evaluer(
    verite: Mapping[str, CauseRacine], propositions: Mapping[str, CauseRacine]
) -> dict[str, Any]:
    """Précision, rappel et F1 par Cause racine, F1 macro, exactitude, matrice de confusion.

    `verite` et `propositions` sont indexées par clé de ticket ; une proposition sans vérité
    lève une `UsineErreur`. La matrice est `{cause vraie: {cause proposée ou « non_classe »:
    nombre}}`, sur les sept Causes racines.
    """
    inconnues = sorted(set(propositions) - set(verite), key=rang_cle)
    if inconnues:
        raise UsineErreur(f"proposition(s) sans vérité terrain : {inconnues}")
    colonnes = [cause.value for cause in CauseRacine] + [NON_CLASSE]
    matrice = {cause.value: dict.fromkeys(colonnes, 0) for cause in CauseRacine}
    for cle, vraie in verite.items():
        proposee = propositions.get(cle)
        matrice[vraie.value][NON_CLASSE if proposee is None else proposee.value] += 1
    presentes = [
        cause
        for cause in CauseRacine
        if cause in set(verite.values()) or cause in set(propositions.values())
    ]
    par_cause: dict[str, dict[str, float | int]] = {}
    for cause in presentes:
        vp = sum(
            1 for cle, vraie in verite.items() if vraie is cause and propositions.get(cle) is cause
        )
        proposees = sum(1 for proposee in propositions.values() if proposee is cause)
        support = sum(1 for vraie in verite.values() if vraie is cause)
        precision = _ratio(vp, proposees)
        rappel = _ratio(vp, support)
        f1 = 2 * precision * rappel / (precision + rappel) if precision + rappel else 0.0
        par_cause[cause.value] = {
            "precision": precision,
            "rappel": rappel,
            "f1": f1,
            "support": support,
            "proposees": proposees,
        }
    corrects = sum(1 for cle, vraie in verite.items() if propositions.get(cle) is vraie)
    f1s = [float(mesures["f1"]) for mesures in par_cause.values()]
    return {
        "nombre": len(verite),
        "classes": len(propositions),
        "corrects": corrects,
        "exactitude": _ratio(corrects, len(verite)),
        "f1_macro": sum(f1s) / len(f1s) if f1s else 0.0,
        "par_cause": par_cause,
        "matrice_confusion": matrice,
        "non_classes": sorted(set(verite) - set(propositions), key=rang_cle),
    }
