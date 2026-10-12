"""Éléments partagés du rendu : libellés, Date d'arrêté, propriétés et archive déterministes.

Le rendu ne calcule rien (AD-9) : il lit via `Consultation` et formate via `contrats.format`.
"""

import io
import re
import zipfile
from datetime import UTC, date, datetime, time
from fractions import Fraction

from usine.contrats.format import formater_date, formater_fraction
from usine.contrats.meteo import Couleur, Operateur, RegleDeclenchante

AUTEUR = "Usine de migration (démonstrateur)"
"""Auteur fixe des documents rendus (`docProps`)."""

TEINTES_COULEURS: dict[Couleur, str] = {
    Couleur.vert: "2E7D32",
    Couleur.jaune: "F9A825",
    Couleur.orange: "EF6C00",
    Couleur.rouge: "C62828",
}
"""Teinte RVB (hexadécimal) de chaque couleur de Météo."""

TEXTES_COULEURS: dict[Couleur, str] = {
    Couleur.vert: "FFFFFF",
    Couleur.jaune: "212121",
    Couleur.orange: "FFFFFF",
    Couleur.rouge: "FFFFFF",
}
"""Couleur RVB du texte posé sur chaque teinte : foncé sur le jaune, pour rester lisible."""

ZIP_SYSTEME = 3
"""`create_system` fixe des entrées d'archive (Unix), quel que soit le poste."""

ZIP_ATTRIBUTS = 0o100644 << 16
"""`external_attr` fixe des entrées d'archive (fichier ordinaire, rw-r--r--)."""

_SYMBOLES: dict[Operateur, str] = {Operateur.superieur_ou_egal: "≥", Operateur.superieur: ">"}


def horodatage_fixe(date_arrete: date) -> datetime:
    """`created` = `modified` des documents : minuit UTC de la Date d'arrêté (FR-14)."""
    return datetime.combine(date_arrete, time(0), UTC)


def titre_document(date_arrete: date) -> str:
    """Titre des documents rendus."""
    return f"Rapport quotidien du {formater_date(date_arrete)}"


def _valeur(numerateur: int, denominateur: int) -> str:
    if denominateur == 0:
        return "∞"
    return formater_fraction(Fraction(numerateur, denominateur))


def formater_regle(regle: RegleDeclenchante) -> str:
    """`IND-1 : 12 (seuil ≥ 10)` : code, valeur et seuil formatés."""
    valeur = _valeur(regle.numerateur, regle.denominateur)
    seuil = _valeur(regle.seuil_numerateur, regle.seuil_denominateur)
    return f"{regle.code.value} : {valeur} (seuil {_SYMBOLES[regle.operateur]} {seuil})"


def tickets_en_cause(regles: tuple[RegleDeclenchante, ...]) -> tuple[str, ...]:
    """Clés des tickets en cause, sans doublon, dans l'ordre des règles."""
    return tuple(dict.fromkeys(cle for regle in regles for cle in regle.tickets_en_cause))


_MODIFIE = re.compile(rb"<dcterms:modified([^>]*)>[^<]*</dcterms:modified>")


def archive_deterministe(octets: bytes, date_arrete: date) -> bytes:
    """Réécrit une archive OOXML : mêmes entrées, dans le même ordre, datées de la Date d'arrêté.

    `docProps/core.xml` reçoit `modified` = minuit UTC de la Date d'arrêté : openpyxl y écrit
    l'heure de sauvegarde.
    """
    modifie = horodatage_fixe(date_arrete).strftime("%Y-%m-%dT%H:%M:%SZ").encode("ascii")
    remplacement = rb"<dcterms:modified\1>" + modifie + b"</dcterms:modified>"
    horodatage_zip = (date_arrete.year, date_arrete.month, date_arrete.day, 0, 0, 0)
    sortie = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(octets)) as source,
        zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as cible,
    ):
        for entree in source.infolist():
            contenu = source.read(entree)
            if entree.filename == "docProps/core.xml":
                contenu = _MODIFIE.sub(remplacement, contenu)
            info = zipfile.ZipInfo(entree.filename, date_time=horodatage_zip)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = ZIP_SYSTEME
            info.external_attr = ZIP_ATTRIBUTS
            cible.writestr(info, contenu)
    return sortie.getvalue()
