"""Racine d'essai d'un Passage : configuration et gabarit livrés, Journal généré (graine 42)."""

import shutil
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from usine.composition import generer_journal
from usine.config import charger_yaml
from usine.contrats.config import ConfigProgramme
from usine.contrats.meteo import CodeIndicateur
from usine.contrats.passage import EXCLUSIONS_REJEU
from usine.contrats.prevision import (
    ContenuPrevisions,
    FacteurExplicatif,
    MethodePrevision,
    Prevision,
    RisqueEntreeRouge,
    StatutPrevision,
)

RACINE_DEPOT = Path(__file__).resolve().parents[3]
PROGRAMME_REDUIT = RACINE_DEPOT / "tests/unit/generateur/programme_reduit.yaml"
"""Programme réduit figé (2 Entités) : garde la durée et les attendus des essais."""
DATE_GENERATION = date(2026, 10, 12)
DATE_ARRETE = date(2026, 10, 9)
INSTANT = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)


def preparer_racine(racine: Path, journal: bool = True) -> Path:
    """Copie `config/` (Programme réduit) et `gabarits/` sous `racine`, y génère le Journal."""
    shutil.copytree(RACINE_DEPOT / "config", racine / "config")
    shutil.copyfile(PROGRAMME_REDUIT, racine / "config" / "programme.yaml")
    shutil.copytree(RACINE_DEPOT / "gabarits", racine / "gabarits")
    if journal:
        programme = charger_yaml(racine / "config" / "programme.yaml", ConfigProgramme)
        generer_journal(programme, 42, DATE_GENERATION, racine)
    return racine


def horloge_figee(instant: datetime = INSTANT) -> Callable[[], datetime]:
    """Horloge figée."""
    return lambda: instant


def horloge_pas_a_pas(instant: datetime = INSTANT) -> Callable[[], datetime]:
    """Horloge qui avance d'une seconde à chaque lecture."""
    compteur = iter(range(10_000))
    return lambda: instant + timedelta(seconds=next(compteur))


def contenu_previsions(date_arrete: date, version_grille: str) -> ContenuPrevisions:
    """Une Prévision (ENT-A, sortie projetée) et un Risque (ENT-B, IND-1), fictifs."""
    prevision = Prevision(
        date_arrete=date_arrete,
        entite="ENT-A",
        methode=MethodePrevision.baseline,
        statut=StatutPrevision.sortie_projetee,
        date_sortie_estimee=date_arrete + timedelta(days=14),
        probabilite_numerateur=3,
        probabilite_denominateur=4,
        horizon_jours_ouvres=20,
        facteurs=(
            FacteurExplicatif(
                nom="stock", libelle="Stock de bloquantes", numerateur=12, denominateur=1
            ),
        ),
        version_grille=version_grille,
    )
    risque = RisqueEntreeRouge(
        date_arrete=date_arrete,
        entite="ENT-B",
        indicateur=CodeIndicateur.ind_1,
        date_franchissement_estimee=date_arrete + timedelta(days=7),
        horizon_jours_ouvres=20,
        numerateur=4,
        denominateur=1,
        seuil_numerateur=5,
        seuil_denominateur=1,
        version_grille=version_grille,
    )
    return ContenuPrevisions(previsions=(prevision,), risques=(risque,))


def sans_exclusions(nom: str, valeur: object) -> object:
    """`valeur` (fichier `nom` de `FICHIERS_PASSAGE`) sans ses champs exclus du Rejeu (AD-7)."""
    exclus = EXCLUSIONS_REJEU.get(nom, frozenset())

    def retirer(valeur: object, chemin: str) -> object:
        if isinstance(valeur, dict):
            return {
                cle: retirer(v, f"{chemin}.{cle}" if chemin else cle)
                for cle, v in valeur.items()
                if (f"{chemin}.{cle}" if chemin else cle) not in exclus
            }
        if isinstance(valeur, list):
            return [retirer(v, f"{chemin}[]") for v in valeur]
        return valeur

    return retirer(valeur, "")
