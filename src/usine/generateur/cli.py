"""Sous-application `usine donnees` : Génération du Programme fictif et injection dans Jira."""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import typer

from usine.config import charger_yaml
from usine.contrats.calendrier import analyser_date_iso, jour_local
from usine.contrats.config import ConfigJira, ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import CHEMIN_JOURNAL
from usine.generateur.corpus import CHEMIN_CORPUS, charger_corpus
from usine.generateur.injecteur.cli import commande_injecter
from usine.generateur.journal import NOM_IDENTIFIANTS, ecrire_journal
from usine.generateur.journal import generer as generer_journal
from usine.generateur.scenarios import AUCUN_SCENARIO

app = typer.Typer(
    help="Génération du Programme fictif et injection dans Jira.", no_args_is_help=True
)


@app.callback()
def principal() -> None:
    """Génération du Programme fictif et injection dans Jira."""


def _date(valeur: str) -> date:
    """Lit une date `AAAA-MM-JJ` ; toute autre forme devient une `UsineErreur`."""
    jour = analyser_date_iso(valeur)
    if jour is None:
        raise UsineErreur(f"date de génération invalide : {valeur!r} (attendu : AAAA-MM-JJ)")
    return jour


@app.command()
def generer(
    graine: Annotated[
        int | None, typer.Option(help="Graine du tirage (défaut : celle de la configuration).")
    ] = None,
    date_generation: Annotated[
        str | None,
        typer.Option(
            "--date-generation",
            metavar="AAAA-MM-JJ",
            help="Date de génération (défaut : aujourd'hui, heure de Paris).",
        ),
    ] = None,
    config: Annotated[Path, typer.Option(help="Configuration du Programme.")] = Path(
        "config/programme.yaml"
    ),
    config_jira: Annotated[
        Path,
        typer.Option(
            "--config-jira", help="Configuration Jira, dont la clé de projet des tickets."
        ),
    ] = Path("config/jira.yaml"),
    sortie: Annotated[
        Path, typer.Option(help="Répertoire du Journal, de la vérité terrain et des identifiants.")
    ] = CHEMIN_JOURNAL.parent,
    corpus: Annotated[
        Path, typer.Option(help="Corpus de textes versionné (titres et descriptions).")
    ] = CHEMIN_CORPUS,
    sans_scenarios: Annotated[
        bool,
        typer.Option(
            "--sans-scenarios",
            help="Désactive les Scénarios de démo A, B et C, même ceux de la configuration :"
            " toutes les Entités suivent le profil normal.",
        ),
    ] = False,
) -> None:
    """Génère le Journal d'événements du Programme fictif, sa vérité terrain et la liste des
    identifiants sensibles fictifs injectés (`identifiants_injectes.json`, à côté du Journal).

    Les clés de tickets sont `<cle_projet>-<n>`, avec la clé de projet de `--config-jira`.
    Les textes viennent du Corpus `--corpus`, déjà écrit : aucun appel LLM. Les Scénarios de
    démo sont lus dans la clé `scenarios` de `--config` (à défaut, ceux du générateur) et
    appliqués s'ils tiennent dans l'historique (`--sans-scenarios` : aucun) ; la sortie liste
    les Scénarios appliqués.
    """
    jour = jour_local(datetime.now(UTC)) if date_generation is None else _date(date_generation)
    programme = charger_yaml(config, ConfigProgramme)
    jira = charger_yaml(config_jira, ConfigJira)
    textes = charger_corpus(corpus)
    generation = generer_journal(
        programme,
        programme.graine if graine is None else graine,
        jour,
        cle_projet=jira.cle_projet,
        corpus=textes,
        scenarios=AUCUN_SCENARIO if sans_scenarios else None,
    )
    journal = ecrire_journal(generation, sortie)
    typer.echo(
        f"Journal écrit : {journal} ({len(generation.evenements)} événements,"
        f" graine {generation.entete.graine}, Date d'injection"
        f" {generation.entete.date_injection.isoformat()})"
    )
    typer.echo(
        f"Identifiants injectés : {journal.parent / NOM_IDENTIFIANTS}"
        f" ({len(generation.identifiants)} identifiants fictifs)"
    )
    typer.echo(f"Scénarios appliqués : {generation.scenarios.resume()}")


app.command("injecter")(commande_injecter)
