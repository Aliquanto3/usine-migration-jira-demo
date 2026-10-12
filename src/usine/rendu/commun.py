"""Éléments partagés du rendu : contexte, libellés, formatage, propriétés et archive déterministes.

Le rendu ne calcule rien (AD-9) : il lit via `Consultation` (et le `ContexteRendu` transmis par
la Chaîne) et formate via `contrats.format`. Les libellés des KPI recopient les codes du
domaine, que `rendu` ne peut pas importer.
"""

import io
import re
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from enum import StrEnum
from fractions import Fraction
from types import MappingProxyType

from usine.consultation.prevision import EtatPrevision, etat_prevision, previsions_calculees
from usine.contrats.calcul import PERIMETRE_PROGRAMME
from usine.contrats.config import GrilleMeteo
from usine.contrats.format import (
    formater_date,
    formater_entier,
    formater_fraction,
    formater_pourcentage,
)
from usine.contrats.meteo import (
    LIBELLES_COULEURS,
    CodeIndicateur,
    Couleur,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.passage import ManifestePassage
from usine.contrats.prevision import Prevision, RisqueEntreeRouge, StatutPrevision
from usine.contrats.tickets import LIBELLES
from usine.contrats.trace import TypeTrace
from usine.contrats.versions import CONTRATS_VERSION
from usine.ports.consultation import Consultation, Palier

AUTEUR = "Usine de migration (démonstrateur)"
"""Auteur fixe des documents rendus (`docProps`)."""

MENTION_PALIER_1 = "commentaire non généré (Palier 1)"
"""Zones de commentaire et Cause racine proposée en Palier 1 (FR-28)."""

MENTION_BROUILLON = "brouillon IA, à valider"
"""Marque de chaque Brouillon de commentaire (Palier 2)."""

AUCUN_RISQUE = "Aucun Risque d'entrée en rouge"
NON_CALCULEE = "Prévision non calculée"
NON_COUVERTE = "non couverte"
"""Météo J-1 ou J-5 d'une date que le Passage ne couvre pas."""
SANS_OBJET = "sans objet"
"""Mesure `0/0` (taux sans dénominateur, âge sans Anomalie)."""
INFINI = "∞"
"""Valeur `n/0` avec `n > 0`."""

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

SYMBOLES: Mapping[Operateur, str] = MappingProxyType(
    {Operateur.superieur_ou_egal: "≥", Operateur.superieur: ">"}
)
"""Symbole affiché de chaque opérateur de seuil."""


# --- Contexte du rendu ---


@dataclass(frozen=True)
class ContexteRendu:
    """Ce que le rendu affiche sans le lire dans les fichiers du Passage.

    Pendant le Passage, le manifeste n'existe pas encore : la Chaîne transmet le Palier, la
    Grille et l'identité des données (`DonneesPassage`, instant d'extraction).
    """

    palier: Palier
    source: str
    version_grille: str
    version_donnees: str
    horodatage_extraction: datetime | None = None
    grille: GrilleMeteo | None = None
    previsions_calculees: bool = True
    """L'étape `prevision` a réussi (toujours vrai pendant le rendu, qui la suit, AD-8)."""
    programme: str = ""
    """Nom du Programme (`config/programme.yaml`) ; `""` s'il n'est pas connu."""


def depuis_manifeste(manifeste: ManifestePassage, grille: GrilleMeteo | None) -> ContexteRendu:
    """Contexte du rendu d'un Passage publié, lu dans son manifeste."""
    return ContexteRendu(
        palier=manifeste.palier,
        source=manifeste.source,
        version_grille=manifeste.version_grille,
        version_donnees=manifeste.version_donnees,
        horodatage_extraction=manifeste.horodatage_extraction,
        grille=grille,
        previsions_calculees=previsions_calculees(manifeste),
    )


# --- Libellés ---


class NatureMesure(StrEnum):
    """Écriture d'une mesure : compte, taux (en %) ou âge (en Jours ouvrés)."""

    compte = "compte"
    taux = "taux"
    age = "age"


LIBELLES_KPI: Mapping[str, tuple[str, NatureMesure]] = MappingProxyType(
    {
        "anomalies_ouvertes": ("Anomalies ouvertes", NatureMesure.compte),
        "anomalies_ouvertes_gravite": ("Anomalies ouvertes par gravité", NatureMesure.compte),
        "anomalies_ouvertes_phase": ("Anomalies ouvertes par Phase", NatureMesure.compte),
        "entrees_jour": ("Entrées d'Anomalies du jour", NatureMesure.compte),
        "sorties_jour": ("Sorties d'Anomalies du jour", NatureMesure.compte),
        "entrees_fenetre": ("Entrées d'Anomalies, Fenêtre glissante", NatureMesure.compte),
        "sorties_fenetre": ("Sorties d'Anomalies, Fenêtre glissante", NatureMesure.compte),
        "age_median_anomalies_ouvertes": (
            "Âge médian des Anomalies ouvertes (Jours ouvrés)",
            NatureMesure.age,
        ),
        "age_max_anomalies_ouvertes": (
            "Âge maximal des Anomalies ouvertes (Jours ouvrés)",
            NatureMesure.age,
        ),
        "taux_ko_cas_de_test": ("Taux de KO des Cas de test", NatureMesure.taux),
        "taux_non_execution_cas_de_test": (
            "Taux de non-exécution des Cas de test",
            NatureMesure.taux,
        ),
        "certifications": ("Certifications par statut", NatureMesure.compte),
        "entrees_semaine": ("Entrées d'Anomalies de la semaine", NatureMesure.compte),
        "sorties_semaine": ("Sorties d'Anomalies de la semaine", NatureMesure.compte),
    }
)
"""Libellé et nature de chaque code de KPI et de Tendance (recopiés de `domaine.kpi`)."""

CODE_TAUX_KO = "taux_ko_cas_de_test"
CODE_TAUX_NON_EXECUTION = "taux_non_execution_cas_de_test"

NATURES_INDICATEURS: Mapping[CodeIndicateur, NatureMesure] = MappingProxyType(
    {
        CodeIndicateur.ind_1: NatureMesure.compte,
        CodeIndicateur.ind_2: NatureMesure.age,
        CodeIndicateur.ind_3: NatureMesure.compte,
        CodeIndicateur.ind_4: NatureMesure.taux,
        CodeIndicateur.ind_5: NatureMesure.compte,
        CodeIndicateur.ind_6: NatureMesure.compte,
        CodeIndicateur.ind_7: NatureMesure.compte,
        CodeIndicateur.ind_8: NatureMesure.taux,
    }
)
"""Nature de chaque Indicateur : IND-4 (taux de KO) et IND-8 (hausse de ce taux) en %."""


def libelle_kpi(code: str) -> str:
    """Libellé d'un code de KPI ; le code lui-même s'il est inconnu."""
    return LIBELLES_KPI[code][0] if code in LIBELLES_KPI else code


def libelle_perimetre(perimetre: str) -> str:
    """« Programme » pour le périmètre Programme, sinon le code d'Entité."""
    return "Programme" if perimetre == PERIMETRE_PROGRAMME else perimetre


def libelle(valeur: str | None) -> str:
    """Libellé d'une valeur canonique (gravité, Phase, statut, Cause racine) ; `""` si nulle."""
    if valeur is None:
        return ""
    return LIBELLES.get(valeur, valeur)


def libelle_couleur(couleur: Couleur | None) -> str:
    """Libellé d'une couleur de Météo ; « non couverte » si `None`."""
    return NON_COUVERTE if couleur is None else LIBELLES_COULEURS[couleur]


def libelle_indicateur(grille: GrilleMeteo | None, code: CodeIndicateur) -> str:
    """Libellé de l'Indicateur dans la Grille ; son code si la Grille ne le porte pas."""
    if grille is None or code not in grille.indicateurs:
        return code.value
    return grille.indicateurs[code].libelle


# --- Formatage ---


def formater_mesure(numerateur: int, denominateur: int, nature: NatureMesure) -> str:
    """Mesure exacte : `n/1` en entier, taux en %, `0/0` « sans objet », `n/0` « ∞ »."""
    if denominateur == 0:
        return INFINI if numerateur > 0 else SANS_OBJET
    if nature is NatureMesure.taux:
        return formater_pourcentage(Fraction(numerateur, denominateur))
    if denominateur == 1:
        return formater_entier(numerateur)
    return formater_fraction(Fraction(numerateur, denominateur))


def formater_kpi(code: str, numerateur: int, denominateur: int) -> str:
    """Valeur d'un KPI ou d'une Tendance selon la nature de son code."""
    nature = LIBELLES_KPI[code][1] if code in LIBELLES_KPI else NatureMesure.compte
    return formater_mesure(numerateur, denominateur, nature)


def formater_indicateur(code: CodeIndicateur, numerateur: int, denominateur: int) -> str:
    """Valeur d'un Indicateur de météo évalué selon sa nature."""
    return formater_mesure(numerateur, denominateur, NATURES_INDICATEURS[code])


def formater_seuil(code: CodeIndicateur, operateur: Operateur, seuil: Fraction) -> str:
    """`≥ 20 %` : opérateur et valeur du seuil, écrite comme l'Indicateur."""
    valeur = formater_indicateur(code, seuil.numerator, seuil.denominator)
    return f"{SYMBOLES[operateur]} {valeur}"


def formater_seuils(grille: GrilleMeteo | None, code: CodeIndicateur) -> str:
    """`Jaune ≥ 5 ; Orange ≥ 10 ; Rouge ≥ 20` : seuils de la Grille, du moins au plus grave."""
    if grille is None or code not in grille.indicateurs:
        return ""
    seuils = grille.indicateurs[code].seuils
    return " ; ".join(
        f"{LIBELLES_COULEURS[couleur]} {formater_seuil(code, *seuils[couleur])}"
        for couleur in Couleur
        if couleur in seuils
    )


def formater_regle(regle: RegleDeclenchante) -> str:
    """`IND-1 : 12 (seuil ≥ 10)` : code, valeur et seuil formatés."""
    valeur = formater_indicateur(regle.code, regle.numerateur, regle.denominateur)
    seuil = formater_seuil(
        regle.code, regle.operateur, Fraction(regle.seuil_numerateur, regle.seuil_denominateur)
    )
    return f"{regle.code.value} : {valeur} (seuil {seuil})"


def tickets_en_cause(regles: tuple[RegleDeclenchante, ...]) -> tuple[str, ...]:
    """Clés des tickets en cause, sans doublon, dans l'ordre des règles."""
    return tuple(dict.fromkeys(cle for regle in regles for cle in regle.tickets_en_cause))


def formater_horodatage(instant: datetime) -> str:
    """`12/10/2026 07:30:00 UTC`."""
    utc = instant.astimezone(UTC)
    return f"{formater_date(utc.date())} {utc:%H:%M:%S} UTC"


def formater_jours_ouvres(nombre: int) -> str:
    """`1 Jour ouvré`, `10 Jours ouvrés`."""
    pluriel = "s" if nombre > 1 else ""
    return f"{formater_entier(nombre)} Jour{pluriel} ouvré{pluriel}"


def formater_prevision(prevision: Prevision) -> str:
    """Prévision de sortie du rouge en une phrase : date, fourchette, probabilité, horizon."""
    probabilite = formater_pourcentage(
        Fraction(prevision.probabilite_numerateur, prevision.probabilite_denominateur)
    )
    horizon = formater_jours_ouvres(prevision.horizon_jours_ouvres)
    if prevision.statut is StatutPrevision.regle_non_projetable:
        codes = ", ".join(code.value for code in prevision.regles_non_projetables)
        return f"Sortie du rouge non projetable (règle {codes})"
    estimee = prevision.date_sortie_estimee
    if prevision.statut is StatutPrevision.pas_de_sortie_projetee or estimee is None:
        return f"Pas de sortie du rouge projetée (probabilité {probabilite} sous {horizon})"
    texte = f"Sortie du rouge estimée le {formater_date(estimee)}"
    optimiste, pessimiste = prevision.date_sortie_optimiste, prevision.date_sortie_pessimiste
    if optimiste is not None or pessimiste is not None:
        bornes = [
            formater_date(borne) if borne is not None else "non bornée"
            for borne in (optimiste, pessimiste)
        ]
        texte += f" (fourchette {bornes[0]} – {bornes[1]})"
    return f"{texte}, probabilité {probabilite} sous {horizon}"


def formater_risque(risque: RisqueEntreeRouge) -> str:
    """Risque d'entrée en rouge en une phrase : indicateur, date, valeur courante et seuil.

    Suivie de « , valeur projetée X » quand le Risque la porte (contrats 1.1.0).
    """
    valeur = formater_indicateur(risque.indicateur, risque.numerateur, risque.denominateur)
    seuil = formater_indicateur(
        risque.indicateur, risque.seuil_numerateur, risque.seuil_denominateur
    )
    texte = (
        f"Risque d'entrée en rouge {risque.indicateur.value} : franchissement estimé le"
        f" {formater_date(risque.date_franchissement_estimee)} (valeur {valeur}, seuil rouge"
        f" {seuil}, horizon {formater_jours_ouvres(risque.horizon_jours_ouvres)})"
    )
    numerateur = risque.valeur_projetee_numerateur
    denominateur = risque.valeur_projetee_denominateur
    if numerateur is not None and denominateur is not None:
        projetee = formater_indicateur(risque.indicateur, numerateur, denominateur)
        texte += f", valeur projetée {projetee}"
    return texte


def texte_prevision(
    consultation: Consultation, entite: str, date_arrete: date, calculees: bool
) -> str:
    """Prévision, Risques, « Aucun Risque d'entrée en rouge » ou « Prévision non calculée »."""
    etat = etat_prevision(consultation, entite, date_arrete, calculees)
    if etat is EtatPrevision.prevision:
        previsions = consultation.previsions(date_arrete, entite)
        return "\n".join(formater_prevision(p) for p in previsions)
    if etat is EtatPrevision.risque:
        return "\n".join(formater_risque(r) for r in consultation.risques(date_arrete, entite))
    if etat is EtatPrevision.aucun_risque:
        return AUCUN_RISQUE
    return NON_CALCULEE


# --- Traçabilité ---


LIBELLES_TRACABILITE = (
    "Date d'arrêté",
    "Palier",
    "Source",
    "Horodatage d'extraction",
    "Nombre de tickets",
    "Version de la Grille",
    "Version des données",
    "Version du prompt",
    "Version du modèle",
    "Version des contrats",
)
"""Lignes fixes de la traçabilité (onglet Traçabilité de l'Excel, Annexe méthode du PowerPoint).

L'horodatage d'extraction et la version des données affichent des champs exclus du Rejeu au
manifeste : à déclarer sous `EXCLUSIONS_REJEU["rapport_xlsx"]` et `["rapport_pptx"]` (5.5).
"""

SANS_EXTRACTION = "sans extraction Jira"
SANS_LLM_PALIER_1 = "sans objet (Palier 1)"
AUCUN_APPEL_LLM = "aucun appel LLM"


def versions_llm(consultation: Consultation, contexte: ContexteRendu) -> tuple[str, str]:
    """Versions de prompt et de modèle des traces LLM du Passage, sans doublon, triées."""
    if contexte.palier == 1:
        return SANS_LLM_PALIER_1, SANS_LLM_PALIER_1
    traces = [t for t in consultation.traces() if t.type_trace is TypeTrace.llm]
    prompts = sorted({t.version_prompt for t in traces if t.version_prompt is not None})
    modeles = sorted({t.version_modele for t in traces if t.version_modele is not None})
    return ", ".join(prompts) or AUCUN_APPEL_LLM, ", ".join(modeles) or AUCUN_APPEL_LLM


def lignes_tracabilite(
    consultation: Consultation, jour: date, contexte: ContexteRendu
) -> tuple[tuple[str, str], ...]:
    """Libellé et valeur de chaque ligne de traçabilité, dans l'ordre de `LIBELLES_TRACABILITE`."""
    prompt, modele = versions_llm(consultation, contexte)
    extraction = contexte.horodatage_extraction
    valeurs = (
        formater_date(jour),
        f"Palier {contexte.palier}",
        contexte.source,
        SANS_EXTRACTION if extraction is None else formater_horodatage(extraction),
        formater_entier(consultation.tickets_etats(jour).height),
        contexte.version_grille,
        contexte.version_donnees,
        prompt,
        modele,
        CONTRATS_VERSION,
    )
    return tuple(zip(LIBELLES_TRACABILITE, valeurs, strict=True))


# --- Documents ---


def horodatage_fixe(date_arrete: date) -> datetime:
    """`created` = `modified` des documents : minuit UTC de la Date d'arrêté (FR-14)."""
    return datetime.combine(date_arrete, time(0), UTC)


def titre_document(date_arrete: date) -> str:
    """Titre des documents rendus."""
    return f"Rapport quotidien du {formater_date(date_arrete)}"


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
