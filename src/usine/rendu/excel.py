"""Excel du Rapport quotidien : 9 onglets dans l'ordre de H-9 (FR-26, FR-28, FR-29, SM-1).

Chaque cellule est une valeur lue via `Consultation` (ou le `ContexteRendu`), formatée par
`contrats.format` : le rendu ne calcule rien. Toute clé de ticket affichée est liée à
`consultation.url_ticket(cle)` quand l'URL existe (FR-29). En Palier 1, l'onglet Commentaires
et la colonne Cause racine proposée portent « commentaire non généré (Palier 1) » (FR-28).

- Synthèse : une ligne par Entité (ordre de `meteo.json`) : Météo J, J-1, J-5, Règles
  déclenchantes, Prévision ou Risque, puis une clé en cause par colonne.
- Météo détaillée : une ligne par Indicateur de `indicateurs(D)`, avec libellé et seuils de la
  Grille, motif si non évaluable.
- KPI : `kpi(D)` en format long. Tendances : `tendances()`, une colonne par semaine.
- Anomalies ouvertes : bloquantes, puis majeures.
- Tests : Instantanés des Cas de test (Entité, Vague, Phase × statut), puis taux de KO et de
  non-exécution du KPI par périmètre et Phase. Certifications : Instantanés (Entité, Vague ×
  statut). Une combinaison absente d'un Instantané vaut 0 ticket.
- Commentaires : Explications, Brouillons et répartition des Causes racines (Palier 2).
- Traçabilité : libellé / valeur, à lignes fixes.
"""

import io
from collections.abc import Sequence
from datetime import date

import polars as pl
from openpyxl import Workbook  # type: ignore[import-untyped]
from openpyxl.styles import Alignment, Font, PatternFill  # type: ignore[import-untyped]
from openpyxl.worksheet.worksheet import Worksheet  # type: ignore[import-untyped]

from usine.contrats.calcul import StatutIndicateur
from usine.contrats.format import formater_date, formater_entier
from usine.contrats.meteo import CodeIndicateur, Couleur
from usine.contrats.tickets import Gravite, StatutCertification, StatutTest, TypeTicket
from usine.ports.consultation import Consultation
from usine.rendu.commun import (
    AUTEUR,
    CODE_TAUX_KO,
    CODE_TAUX_NON_EXECUTION,
    MENTION_BROUILLON,
    MENTION_PALIER_1,
    TEINTES_COULEURS,
    TEXTES_COULEURS,
    ContexteRendu,
    archive_deterministe,
    formater_indicateur,
    formater_kpi,
    formater_regle,
    formater_seuils,
    horodatage_fixe,
    libelle,
    libelle_couleur,
    libelle_indicateur,
    libelle_kpi,
    libelle_perimetre,
    lignes_tracabilite,
    texte_prevision,
    tickets_en_cause,
    titre_document,
)

ONGLETS = (
    "Synthèse",
    "Météo détaillée",
    "KPI",
    "Tendances",
    "Anomalies ouvertes",
    "Tests",
    "Certifications",
    "Commentaires",
    "Traçabilité",
)
"""Onglets du classeur, dans l'ordre de H-9."""

EN_TETES_SYNTHESE = (
    "Entité",
    "Météo J",
    "Météo J-1",
    "Météo J-5",
    "Règles déclenchantes",
    "Prévision ou Risque",
    "Tickets en cause",
)
COLONNE_TICKETS = len(EN_TETES_SYNTHESE)
"""Colonne (1-indexée) de la première clé de ticket en cause ; les suivantes à sa droite."""

EN_TETES_METEO = (
    "Entité",
    "Code",
    "Indicateur",
    "Statut",
    "Valeur",
    "Couleur",
    "Seuils",
    "Motif",
)
EN_TETES_KPI = ("Périmètre", "KPI", "Dimension", "Valeur")
EN_TETES_TENDANCES = ("Périmètre", "KPI", "Dimension")
"""Suivies d'une colonne par semaine (« Semaine au JJ/MM/AAAA »)."""
EN_TETES_ANOMALIES = (
    "Clé",
    "Entité",
    "Gravité",
    "Phase",
    "Domaine",
    "Statut",
    "Âge (Jours ouvrés)",
    "Cause racine proposée",
)
STATUTS_TESTS = (StatutTest.ok, StatutTest.ko, StatutTest.non_execute)
EN_TETES_TESTS = ("Entité", "Vague", "Phase", *(libelle(s) for s in STATUTS_TESTS))
TITRE_TAUX_TESTS = "Taux par périmètre et Phase (KPI)"
EN_TETES_TAUX_TESTS = ("Périmètre", "Phase", "Taux de KO", "Taux de non-exécution")
STATUTS_CERTIFICATIONS = tuple(StatutCertification)
EN_TETES_CERTIFICATIONS = ("Entité", "Vague", *(libelle(s) for s in STATUTS_CERTIFICATIONS))
EN_TETES_COMMENTAIRES_PALIER_1 = ("Commentaires",)
TITRE_EXPLICATIONS = "Explications et Brouillons de commentaire"
EN_TETES_EXPLICATIONS = ("Entité", "Explication", "Brouillon de commentaire", "Citations")
TITRE_REPARTITION = "Répartition des Causes racines"
EN_TETES_REPARTITION = ("Entité", "Cause racine", "Anomalies ouvertes")
EN_TETES_TRACABILITE = ("Libellé", "Valeur")
# Onglet Traçabilité : en-têtes en ligne 1, puis une ligne par entrée de
# `rendu.commun.LIBELLES_TRACABILITE`, dans son ordre, à partir de la ligne 2 (valeur en
# colonne B). Le 4e libellé (« Horodatage d'extraction ») tombe donc en `Traçabilité!B5` et le
# 7e (« Version des données ») en `Traçabilité!B8` : deux champs exclus du Rejeu au manifeste, à
# déclarer sous `EXCLUSIONS_REJEU["rapport_xlsx"]` (Story 5.5). Réordonner
# `LIBELLES_TRACABILITE` déplace ces cellules.

NON_EVALUABLE = "non évaluable"
NON_PROPOSEE = "non proposée"
LIBELLES_STATUTS_INDICATEUR = {
    StatutIndicateur.evalue: "Évalué",
    StatutIndicateur.non_evaluable: "Non évaluable",
}

_GRAS = Font(bold=True)
_RENVOI = Alignment(wrap_text=True, vertical="top")


# --- Écriture ---


def _en_tetes(onglet: Worksheet, ligne: int, en_tetes: Sequence[str]) -> None:
    for colonne, en_tete in enumerate(en_tetes, start=1):
        onglet.cell(row=ligne, column=colonne, value=en_tete).font = _GRAS


def _ligne(onglet: Worksheet, ligne: int, valeurs: Sequence[object]) -> None:
    for colonne, valeur in enumerate(valeurs, start=1):
        onglet.cell(row=ligne, column=colonne, value=valeur)


def _cle(onglet: Worksheet, ligne: int, colonne: int, cle: str, consultation: Consultation) -> None:
    """Clé de ticket, liée à `url_ticket(cle)` quand l'URL existe (FR-29)."""
    cellule = onglet.cell(row=ligne, column=colonne, value=cle)
    url = consultation.url_ticket(cle)
    if url is not None:
        cellule.hyperlink = url
        cellule.style = "Hyperlink"


def _couleur(onglet: Worksheet, ligne: int, colonne: int, couleur: Couleur | None) -> None:
    """Libellé de la couleur, sur sa teinte ; « non couverte » sans teinte."""
    cellule = onglet.cell(row=ligne, column=colonne, value=libelle_couleur(couleur))
    if couleur is not None:
        teinte = TEINTES_COULEURS[couleur]
        cellule.fill = PatternFill(fill_type="solid", start_color=teinte, end_color=teinte)
        cellule.font = Font(bold=True, color=TEXTES_COULEURS[couleur])


def _largeurs(onglet: Worksheet, largeurs: Sequence[int]) -> None:
    for rang, largeur in enumerate(largeurs):
        onglet.column_dimensions[chr(ord("A") + rang)].width = largeur


# --- Onglets ---


def _synthese(
    onglet: Worksheet, consultation: Consultation, jour: date, contexte: ContexteRendu
) -> None:
    _en_tetes(onglet, 1, EN_TETES_SYNTHESE)
    evolutions = {e.entite: e for e in consultation.evolution_meteo(jour)}
    for ligne, meteo in enumerate(consultation.meteo(jour), start=2):
        onglet.cell(row=ligne, column=1, value=meteo.entite)
        _couleur(onglet, ligne, 2, meteo.couleur)
        evolution = evolutions.get(meteo.entite)
        _couleur(onglet, ligne, 3, None if evolution is None else evolution.couleur_j1)
        _couleur(onglet, ligne, 4, None if evolution is None else evolution.couleur_j5)
        regles = "\n".join(formater_regle(regle) for regle in meteo.regles)
        onglet.cell(row=ligne, column=5, value=regles or None).alignment = _RENVOI
        prevision = texte_prevision(consultation, meteo.entite, jour, contexte.previsions_calculees)
        onglet.cell(row=ligne, column=6, value=prevision).alignment = _RENVOI
        for decalage, cle in enumerate(tickets_en_cause(meteo.regles)):
            _cle(onglet, ligne, COLONNE_TICKETS + decalage, cle, consultation)
    _largeurs(onglet, (14, 10, 10, 10, 32, 48))
    onglet.freeze_panes = "B2"


def _meteo_detaillee(
    onglet: Worksheet, consultation: Consultation, jour: date, contexte: ContexteRendu
) -> None:
    _en_tetes(onglet, 1, EN_TETES_METEO)
    lignes = consultation.indicateurs(jour).iter_rows(named=True)
    for ligne, indicateur in enumerate(lignes, start=2):
        code = CodeIndicateur(indicateur["code"])
        statut = StatutIndicateur(indicateur["statut"])
        evalue = statut is StatutIndicateur.evalue
        valeur = (
            formater_indicateur(code, indicateur["numerateur"], indicateur["denominateur"])
            if evalue
            else NON_EVALUABLE
        )
        _ligne(
            onglet,
            ligne,
            (
                indicateur["entite"],
                code.value,
                libelle_indicateur(contexte.grille, code),
                LIBELLES_STATUTS_INDICATEUR[statut],
                valeur,
            ),
        )
        _couleur(onglet, ligne, 6, Couleur(indicateur["couleur"]))
        onglet.cell(row=ligne, column=7, value=formater_seuils(contexte.grille, code) or None)
        onglet.cell(row=ligne, column=8, value=indicateur["motif"] or None)
    _largeurs(onglet, (12, 8, 48, 14, 12, 10, 40, 48))
    onglet.freeze_panes = "A2"


def _kpi(onglet: Worksheet, consultation: Consultation, jour: date) -> None:
    _en_tetes(onglet, 1, EN_TETES_KPI)
    for ligne, mesure in enumerate(consultation.kpi(jour).iter_rows(named=True), start=2):
        code = mesure["code_kpi"]
        _ligne(
            onglet,
            ligne,
            (
                libelle_perimetre(mesure["perimetre"]),
                libelle_kpi(code),
                libelle(mesure["dimension"] or None) or None,
                formater_kpi(code, mesure["numerateur"], mesure["denominateur"]),
            ),
        )
    _largeurs(onglet, (14, 48, 20, 14))
    onglet.freeze_panes = "A2"


def _tendances(onglet: Worksheet, consultation: Consultation) -> None:
    table = consultation.tendances()
    semaines: list[date] = sorted(set(table.get_column("date").to_list()))
    _en_tetes(
        onglet,
        1,
        (*EN_TETES_TENDANCES, *(f"Semaine au {formater_date(s)}" for s in semaines)),
    )
    colonnes = {semaine: rang for rang, semaine in enumerate(semaines, start=4)}
    lignes: dict[tuple[str, str, str], int] = {}
    for mesure in table.iter_rows(named=True):
        serie = (mesure["perimetre"], mesure["code_kpi"], mesure["dimension"])
        if serie not in lignes:
            lignes[serie] = len(lignes) + 2
            perimetre, code, dimension = serie
            _ligne(
                onglet,
                lignes[serie],
                (
                    libelle_perimetre(perimetre),
                    libelle_kpi(code),
                    libelle(dimension or None) or None,
                ),
            )
        onglet.cell(
            row=lignes[serie],
            column=colonnes[mesure["date"]],
            value=formater_kpi(mesure["code_kpi"], mesure["numerateur"], mesure["denominateur"]),
        )
    _largeurs(onglet, (14, 48, 20))
    onglet.freeze_panes = "D2"


def _anomalies(
    onglet: Worksheet, consultation: Consultation, jour: date, contexte: ContexteRendu
) -> None:
    _en_tetes(onglet, 1, EN_TETES_ANOMALIES)
    ligne = 2
    for gravite in (Gravite.bloquante, Gravite.majeure):
        resultat = consultation.anomalies(jour, gravite=gravite, palier=contexte.palier)
        for anomalie in resultat.anomalies:
            _cle(onglet, ligne, 1, anomalie.cle_ticket, consultation)
            if contexte.palier == 1:
                cause = MENTION_PALIER_1
            elif anomalie.cause_racine_proposee is None:
                cause = NON_PROPOSEE
            else:
                cause = libelle(anomalie.cause_racine_proposee)
            for colonne, valeur in enumerate(
                (
                    anomalie.entite,
                    libelle(anomalie.gravite),
                    libelle(anomalie.phase),
                    anomalie.domaine,
                    libelle(anomalie.statut),
                    formater_entier(anomalie.age_jours_ouvres),
                    cause,
                ),
                start=2,
            ):
                onglet.cell(row=ligne, column=colonne, value=valeur)
            ligne += 1
    _largeurs(onglet, (12, 10, 12, 18, 16, 14, 18, 34))
    onglet.freeze_panes = "B2"


def _instantanes(
    consultation: Consultation, jour: date, type_ticket: TypeTicket, axes: Sequence[str]
) -> dict[tuple[str | None, ...], dict[str, int]]:
    """Nombres des Instantanés du type, par combinaison `axes` puis par statut (sans somme)."""
    table = consultation.instantanes(jour).filter(pl.col("type_ticket") == type_ticket.value)
    pivot: dict[tuple[str | None, ...], dict[str, int]] = {}
    for instantane in table.iter_rows(named=True):
        cle = tuple(instantane[axe] for axe in axes)
        pivot.setdefault(cle, {})[instantane["statut"]] = instantane["nombre"]
    return pivot


def _tests(onglet: Worksheet, consultation: Consultation, jour: date) -> None:
    _en_tetes(onglet, 1, EN_TETES_TESTS)
    pivot = _instantanes(consultation, jour, TypeTicket.cas_de_test, ("entite", "vague", "phase"))
    ligne = 2
    for (entite, vague, phase), nombres in pivot.items():
        _ligne(
            onglet,
            ligne,
            (
                entite,
                vague,
                libelle(phase),
                *(formater_entier(nombres.get(s.value, 0)) for s in STATUTS_TESTS),
            ),
        )
        ligne += 1
    ligne += 1
    onglet.cell(row=ligne, column=1, value=TITRE_TAUX_TESTS).font = _GRAS
    _en_tetes(onglet, ligne + 1, EN_TETES_TAUX_TESTS)
    ligne += 2
    taux: dict[tuple[str, str], dict[str, str]] = {}
    mesures = consultation.kpi(jour).filter(
        pl.col("code_kpi").is_in([CODE_TAUX_KO, CODE_TAUX_NON_EXECUTION])
    )
    for mesure in mesures.iter_rows(named=True):
        code = mesure["code_kpi"]
        valeur = formater_kpi(code, mesure["numerateur"], mesure["denominateur"])
        taux.setdefault((mesure["perimetre"], mesure["dimension"]), {})[code] = valeur
    for (perimetre, phase), valeurs in taux.items():
        _ligne(
            onglet,
            ligne,
            (
                libelle_perimetre(perimetre),
                libelle(phase),
                valeurs.get(CODE_TAUX_KO),
                valeurs.get(CODE_TAUX_NON_EXECUTION),
            ),
        )
        ligne += 1
    _largeurs(onglet, (14, 12, 18, 12, 12, 22))
    onglet.freeze_panes = "A2"


def _certifications(onglet: Worksheet, consultation: Consultation, jour: date) -> None:
    _en_tetes(onglet, 1, EN_TETES_CERTIFICATIONS)
    pivot = _instantanes(consultation, jour, TypeTicket.certification, ("entite", "vague"))
    for ligne, ((entite, vague), nombres) in enumerate(pivot.items(), start=2):
        _ligne(
            onglet,
            ligne,
            (
                entite,
                vague,
                *(formater_entier(nombres.get(s.value, 0)) for s in STATUTS_CERTIFICATIONS),
            ),
        )
    _largeurs(onglet, (14, 12, 12, 12, 12))
    onglet.freeze_panes = "A2"


def _commentaires(onglet: Worksheet, consultation: Consultation, contexte: ContexteRendu) -> None:
    if contexte.palier == 1:
        _en_tetes(onglet, 1, EN_TETES_COMMENTAIRES_PALIER_1)
        onglet.cell(row=2, column=1, value=MENTION_PALIER_1)
        _largeurs(onglet, (48,))
        return
    onglet.cell(row=1, column=1, value=TITRE_EXPLICATIONS).font = _GRAS
    _en_tetes(onglet, 2, EN_TETES_EXPLICATIONS)
    ligne = 3
    for explication in consultation.explications(palier=contexte.palier):
        brouillon = explication.brouillon_commentaire
        _ligne(
            onglet,
            ligne,
            (
                explication.entite,
                explication.texte,
                f"{MENTION_BROUILLON} : {brouillon}" if brouillon else None,
            ),
        )
        onglet.cell(row=ligne, column=2).alignment = _RENVOI
        onglet.cell(row=ligne, column=3).alignment = _RENVOI
        for decalage, cle in enumerate(explication.citations):
            _cle(onglet, ligne, len(EN_TETES_EXPLICATIONS) + decalage, cle, consultation)
        ligne += 1
    ligne += 1
    onglet.cell(row=ligne, column=1, value=TITRE_REPARTITION).font = _GRAS
    _en_tetes(onglet, ligne + 1, EN_TETES_REPARTITION)
    ligne += 2
    repartition = consultation.repartition_causes(palier=contexte.palier)
    for cause in repartition.iter_rows(named=True):
        _ligne(
            onglet,
            ligne,
            (cause["entite"], libelle(cause["cause_racine"]), formater_entier(cause["nombre"])),
        )
        ligne += 1
    _largeurs(onglet, (14, 60, 48, 14))


def _tracabilite(
    onglet: Worksheet, consultation: Consultation, jour: date, contexte: ContexteRendu
) -> None:
    _en_tetes(onglet, 1, EN_TETES_TRACABILITE)
    for ligne, valeurs in enumerate(lignes_tracabilite(consultation, jour, contexte), start=2):
        _ligne(onglet, ligne, valeurs)
    _largeurs(onglet, (26, 70))


def rendre_excel(consultation: Consultation, date_arrete: date, contexte: ContexteRendu) -> bytes:
    """Octets du classeur Excel du Passage à la Date d'arrêté, déterministes.

    Un Passage sans fichier donne les 9 onglets, en-têtes seuls (lignes fixes de Traçabilité).
    """
    classeur = Workbook()
    premier = classeur.active
    if premier is None:  # pragma: no cover - un classeur neuf a toujours un onglet actif
        premier = classeur.create_sheet()
    premier.title = ONGLETS[0]
    onglets = [premier, *(classeur.create_sheet(nom) for nom in ONGLETS[1:])]
    synthese, meteo, kpi, tendances, anomalies, tests, certifications, commentaires, trace = onglets
    _synthese(synthese, consultation, date_arrete, contexte)
    _meteo_detaillee(meteo, consultation, date_arrete, contexte)
    _kpi(kpi, consultation, date_arrete)
    _tendances(tendances, consultation)
    _anomalies(anomalies, consultation, date_arrete, contexte)
    _tests(tests, consultation, date_arrete)
    _certifications(certifications, consultation, date_arrete)
    _commentaires(commentaires, consultation, contexte)
    _tracabilite(trace, consultation, date_arrete, contexte)

    proprietes = classeur.properties
    proprietes.creator = AUTEUR
    proprietes.lastModifiedBy = AUTEUR
    proprietes.title = titre_document(date_arrete)
    proprietes.created = horodatage_fixe(date_arrete)
    proprietes.modified = horodatage_fixe(date_arrete)
    tampon = io.BytesIO()
    classeur.save(tampon)
    return archive_deterministe(tampon.getvalue(), date_arrete)
