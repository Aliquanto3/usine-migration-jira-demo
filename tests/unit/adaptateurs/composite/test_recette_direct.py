"""Recette en direct de la source composite sur Jira Cloud, projet `DEMO` (Story 2.7).

Tests `@pytest.mark.reseau` : exclus de la CI et de `pytest` par défaut. Lecture par
`ClientJiraLecture` seul ; aucune écriture dans Jira, aucun fichier de la racine modifié.

Procédure de recette
--------------------

Prérequis, dans la racine de recette `M` (`USINE_RACINE_RECETTE`, défaut : répertoire
courant) : `config/jira.yaml` (`mode: cloud`, `cle_projet: DEMO`), `config/` et `gabarits/`
complets, Journal `donnees/journal.jsonl` et manifeste d'injection
`donnees/injection/manifeste_injection.json` (Story 1.7), secrets `JIRA_EMAIL` et
`JIRA_TOKEN_LECTURE` dans l'environnement ou `M/.env`. Sans l'un d'eux, les tests sont
sautés avec leur motif.

1. AC1, deux extractions successives (entrepôt temporaire, jamais celui de `M`) :

       USINE_RACINE_RECETTE=<M> uv run pytest -m reseau \\
           tests/unit/adaptateurs/composite/test_recette_direct.py

   La première extraction stocke au moins 3 384 créations ; la seconde n'ajoute aucun
   événement ni alignement.

2. AC2, transition faite à la main :

   a. relever le statut d'un seul ticket `DEMO` de l'Entité A (jamais `KAN`) ;
   b. le passer par une transition (client d'écriture, script hors dépôt), consigner ticket,
      champ, avant et après ;
   c. relancer la commande ci-dessus avec `USINE_RECETTE_TRANSITION=<clé>=<statut canonique>`
      (ex. `DEMO-1356=en_correction`) : un Passage `usine rapport` est exécuté à la date du
      jour (Jour ouvré) sur une copie temporaire de `M` (`config/`, `gabarits/`, Journal,
      manifeste) ; `tickets_etats.parquet` du Passage publié porte le nouveau statut du
      ticket à ce jour, et le manifeste `source` = `composite` ;
   d. restaurer le statut d'origine par une transition inverse, et le consigner.

3. AC3 : `usine extraction rafraichir-fixtures --racine <M>` écrit
   `tests/fixtures/jira_cloud/direct_recherche_page_1.json` anonymisée ; puis
   `gitleaks dir tests/fixtures` et `gitleaks git` ne signalent aucune fuite.
"""

import os
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from usine.adaptateurs.composite import DetecteurAlignements
from usine.adaptateurs.entrepot_duckdb import EntrepotDuckDB, extraire
from usine.adaptateurs.jira_cloud import SourceJiraCloud
from usine.adaptateurs.jira_http import construire_client_lecture
from usine.adaptateurs.journal import (
    CHEMIN_MANIFESTE_INJECTION,
    SourceJournal,
    charger_manifeste,
)
from usine.composition import CHEMIN_GABARIT, lancer_rapport
from usine.config import Secrets, charger_secrets, charger_yaml
from usine.contrats.calendrier import est_jour_ouvre
from usine.contrats.config import ConfigJira
from usine.contrats.evenements import NatureEvenement, SourceEvenement
from usine.contrats.passage import CHEMIN_JOURNAL, FICHIERS_PASSAGE
from usine.contrats.tickets import TypeTicket

pytestmark = pytest.mark.reseau

CREATIONS_MINIMUM = 3_384
"""Créations Jira du projet `DEMO` après l'injection de la Story 1.7."""
_VARIABLES_SECRETES = ("JIRA_EMAIL", "JIRA_TOKEN_LECTURE")
# Relevées à la collecte : la fixture de session `_sans_secret_jira` les retire ensuite.
_ENVIRONNEMENT = {nom: os.environ.get(nom) for nom in _VARIABLES_SECRETES}
_COLONNE_STATUT = {
    TypeTicket.anomalie.value: "statut",
    TypeTicket.cas_de_test.value: "statut_test",
    TypeTicket.certification.value: "statut_certification",
}


@dataclass(frozen=True)
class Recette:
    """Racine de recette `M`, sa configuration Jira et ses secrets."""

    racine: Path
    config: ConfigJira
    secrets: Secrets


@pytest.fixture
def recette(monkeypatch: pytest.MonkeyPatch) -> Iterator[Recette]:
    """Racine `M` prête, ou test sauté avec le motif de l'absence."""
    racine = Path(os.environ.get("USINE_RACINE_RECETTE") or ".").resolve()
    chemin_config = racine / "config" / "jira.yaml"
    if not chemin_config.exists():
        pytest.skip(f"recette sans racine configurée : {chemin_config} absent")
    for chemin, quoi in (
        (racine / CHEMIN_MANIFESTE_INJECTION, "manifeste d'injection"),
        (racine / CHEMIN_JOURNAL, "Journal"),
    ):
        if not chemin.exists():
            pytest.skip(f"recette sans {quoi} : {chemin} absent")
    config = charger_yaml(chemin_config, ConfigJira)
    if config.mode != "cloud":
        pytest.skip(f"recette Jira Cloud seulement : {chemin_config} en mode {config.mode!r}")
    for nom, valeur in _ENVIRONNEMENT.items():
        if valeur:
            monkeypatch.setenv(nom, valeur)
    secrets_usine = charger_secrets(racine)
    jeton = secrets_usine.jira_token_lecture
    if jeton is None or not jeton.get_secret_value().strip():
        pytest.skip("recette sans secret de lecture : JIRA_TOKEN_LECTURE absent")
    if not (secrets_usine.jira_email or "").strip():
        pytest.skip("recette sans compte de lecture : JIRA_EMAIL absent")
    yield Recette(racine, config, secrets_usine)


def _journal(racine: Path) -> SourceJournal:
    manifeste = charger_manifeste(racine / CHEMIN_MANIFESTE_INJECTION)
    return SourceJournal(racine / CHEMIN_JOURNAL, manifeste)


def test_deux_extractions_successives(recette: Recette, tmp_path: Path) -> None:
    """AC1 : la seconde extraction n'ajoute ni événement ni alignement."""
    config = recette.config
    marge = timedelta(minutes=config.marge_extraction_minutes)
    aligner = DetecteurAlignements(_journal(recette.racine))
    entrepot = EntrepotDuckDB(tmp_path / "entrepot.duckdb")
    with construire_client_lecture(
        config,
        email=recette.secrets.jira_email,
        jeton_lecture=recette.secrets.jira_token_lecture,
        pat=None,
    ) as client:
        source = SourceJiraCloud(client, config)
        premiere = extraire(source, entrepot, marge, aligner=aligner)
        seconde = extraire(source, entrepot, marge, aligner=aligner)
    assert premiere.evenements is not None
    creations = sum(
        1
        for e in premiere.evenements
        if e.nature is NatureEvenement.creation and e.source is SourceEvenement.jira_cloud
    )
    print(
        f"\nrecette AC1 : 1re extraction {premiere.ajouts} événements ({creations} créations,"
        f" {premiere.alignements} alignements) ; 2e extraction {seconde.ajouts} événements,"
        f" {seconde.alignements} alignements ; depuis {seconde.depuis}"
    )
    assert creations >= CREATIONS_MINIMUM
    assert seconde.depuis is not None
    assert seconde.ajouts == 0
    assert seconde.alignements == 0


def _transition_attendue() -> tuple[str, str]:
    valeur = os.environ.get("USINE_RECETTE_TRANSITION", "").strip()
    if not valeur:
        pytest.skip("AC2 sans transition annoncée : USINE_RECETTE_TRANSITION absent")
    cle, separateur, statut = valeur.partition("=")
    if not separateur or not cle.strip() or not statut.strip():
        pytest.fail(
            f"USINE_RECETTE_TRANSITION : {valeur!r} : forme <clé>=<statut canonique> attendue"
        )
    return cle.strip(), statut.strip()


def _copie_racine(racine: Path, copie: Path) -> None:
    """`config/`, `gabarits/`, Journal et manifeste d'injection ; ni `.env` ni entrepôt."""
    shutil.copytree(racine / "config", copie / "config")
    shutil.copytree(racine / CHEMIN_GABARIT.parent, copie / CHEMIN_GABARIT.parent)
    for relatif in (CHEMIN_JOURNAL, CHEMIN_MANIFESTE_INJECTION):
        (copie / relatif).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(racine / relatif, copie / relatif)


def test_transition_visible_au_passage_publie(
    recette: Recette, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2 : une transition faite à la main apparaît au Passage suivant, source composite."""
    cle, statut = _transition_attendue()
    jour = datetime.now(UTC).date()
    if not est_jour_ouvre(jour):
        pytest.skip(f"AC2 : {jour.isoformat()} n'est pas un Jour ouvré")
    copie = tmp_path / "racine"
    _copie_racine(recette.racine, copie)
    # Secrets passés par l'environnement du test : la copie n'a pas de `.env`.
    email = recette.secrets.jira_email
    jeton = recette.secrets.jira_token_lecture
    assert email is not None and jeton is not None
    monkeypatch.setenv("JIRA_EMAIL", email)
    monkeypatch.setenv("JIRA_TOKEN_LECTURE", jeton.get_secret_value())
    monkeypatch.delenv("USINE_MODE_REPLI", raising=False)
    monkeypatch.delenv("JIRA_TOKEN_INJECTION", raising=False)

    passage = lancer_rapport(copie, jour)

    manifeste = passage.manifeste
    etats = pl.read_parquet(passage.repertoire / FICHIERS_PASSAGE["tickets_etats"])
    lignes = etats.filter((pl.col("cle_ticket") == cle) & (pl.col("date") == jour))
    print(
        f"\nrecette AC2 : Passage {manifeste.passage_id}, source {manifeste.source},"
        f" {manifeste.nb_tickets} tickets, {manifeste.nb_alignements} alignements"
    )
    assert manifeste.source == "composite"
    assert lignes.height == 1, f"{cle} absent de tickets_etats au {jour.isoformat()}"
    ligne = lignes.row(0, named=True)
    colonne = _COLONNE_STATUT[str(ligne["type_ticket"])]
    assert ligne[colonne] == statut, f"{cle} : {colonne} = {ligne[colonne]!r}, {statut!r} attendu"
