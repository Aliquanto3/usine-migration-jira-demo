"""Mesure NFR-2 : durée de `usine rapport` en Palier 1 à la volumétrie cible.

Génère dans un répertoire temporaire un Journal de 10 Entités, 5 000 Anomalies et 8 semaines,
exécute la Chaîne en Palier 1 et affiche la durée de chaque étape et la durée totale.

Usage : `uv run python outils/mesurer_nfr2.py [--graine 42] [--date-generation 2026-10-12]`.
"""

import argparse
import platform
import shutil
import tempfile
import time
from datetime import date
from pathlib import Path

import yaml

from usine.composition import generer_journal, lancer_rapport
from usine.contrats.config import ConfigProgramme
from usine.contrats.evenements import EnteteJournal

RACINE_DEPOT = Path(__file__).resolve().parents[1]
NB_ENTITES = 10
NB_ANOMALIES = 5_000
NB_SEMAINES = 8
CIBLE_SECONDES = 5 * 60
"""Cible NFR-2 : un Passage en Palier 1 en moins de 5 minutes."""


def programme_cible(graine: int) -> ConfigProgramme:
    """Programme livré, porté à 10 Entités et 5 000 Anomalies sur 8 semaines."""
    donnees = yaml.safe_load((RACINE_DEPOT / "config" / "programme.yaml").read_text("utf-8"))
    vague = donnees["vagues"][0]["code"]
    donnees.update(
        graine=graine,
        nb_semaines=NB_SEMAINES,
        entites=[
            {"code": f"ENT-{n:02d}", "libelle": f"Entité {n:02d}", "vague": vague}
            for n in range(1, NB_ENTITES + 1)
        ],
    )
    donnees["volumetrie"].update(anomalies_min=NB_ANOMALIES, anomalies_max=NB_ANOMALIES)
    return ConfigProgramme.model_validate(donnees)


def mesurer(graine: int, date_generation: date) -> None:
    """Prépare la racine temporaire, exécute un Passage et affiche les durées."""
    programme = programme_cible(graine)
    with tempfile.TemporaryDirectory(prefix="usine-nfr2-") as temporaire:
        racine = Path(temporaire)
        (racine / "config").mkdir()
        shutil.copy(RACINE_DEPOT / "config" / "grille_meteo.yaml", racine / "config")
        (racine / "config" / "chaine.yaml").write_text(
            "# Palier de la Chaîne : la mesure NFR-2 porte sur le Palier 1.\npalier: 1\n",
            encoding="utf-8",
        )
        (racine / "config" / "programme.yaml").write_text(
            yaml.safe_dump(programme.model_dump(mode="json"), allow_unicode=True),
            encoding="utf-8",
        )
        debut_generation = time.perf_counter()
        chemin = generer_journal(programme, graine, date_generation, racine)
        duree_generation = time.perf_counter() - debut_generation
        nb_lignes = len(chemin.read_bytes().splitlines()) - 1

        debut = time.perf_counter()
        lance = lancer_rapport(racine, date_arrete_mesuree(chemin))
        total = time.perf_counter() - debut

    manifeste = lance.manifeste
    print(f"Poste : {platform.platform()}, {platform.processor() or platform.machine()},")
    print(f"        Python {platform.python_version()}")
    print(
        f"Journal : {NB_ENTITES} Entités, {NB_ANOMALIES} Anomalies, {NB_SEMAINES} semaines,"
        f" {nb_lignes} événements (généré en {duree_generation:.1f} s)"
    )
    print(f"Passage {manifeste.passage_id}, Date d'arrêté {manifeste.date_arrete.isoformat()},")
    print(f"        Palier {manifeste.palier}, {manifeste.nb_tickets} tickets")
    print()
    print(f"{'Étape':<20} {'Statut':<8} {'Durée (s)':>10}")
    for execution in manifeste.etapes:
        secondes = execution.duree.total_seconds()
        print(f"{execution.etape.value:<20} {execution.statut.value:<8} {secondes:>10.2f}")
    print(f"{'Total (commande)':<29} {total:>10.2f}")
    ecart = "dans la cible" if total <= CIBLE_SECONDES else "AU-DELÀ de la cible"
    print(f"Cible NFR-2 : {CIBLE_SECONDES} s ; {ecart}.")


def date_arrete_mesuree(journal: Path) -> date:
    """Date d'arrêté du Passage mesuré : Date d'injection lue dans l'en-tête du Journal."""
    with journal.open("rb") as fichier:
        return EnteteJournal.model_validate_json(fichier.readline()).date_injection


def main() -> None:
    """Point d'entrée en ligne de commande."""
    analyseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analyseur.add_argument("--graine", type=int, default=42)
    analyseur.add_argument("--date-generation", type=date.fromisoformat, default=date(2026, 10, 12))
    arguments = analyseur.parse_args()
    mesurer(arguments.graine, arguments.date_generation)


if __name__ == "__main__":
    main()
