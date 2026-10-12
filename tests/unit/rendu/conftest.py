"""Passages pour les tests du rendu (graine 42, 2026-10-09).

Publiés par `lancer_rapport` : normal, en Mode repli, sans `config/jira.yaml`. Fixture Palier 2 :
copie du Passage normal, manifeste en Palier 2, complétée de `llm/*.json`,
`repartition_causes.parquet` et `trace/llm.jsonl` écrits par les modèles de contrats.
"""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from tests.unit.chaine.environnement import (
    DATE_ARRETE,
    RACINE_DEPOT,
    horloge_figee,
    preparer_racine,
)
from usine.composition import lancer_rapport
from usine.config import charger_yaml
from usine.consultation.passage import ConsultationPassage
from usine.contrats.config import ConfigJira, GrilleMeteo
from usine.contrats.llm import (
    SCHEMA_REPARTITION_CAUSES,
    SortieClassification,
    SortieExplication,
    SortieNarration,
    StatutControle,
    Tache,
)
from usine.contrats.meteo import CodeIndicateur, Couleur, MeteoEntite, Operateur, RegleDeclenchante
from usine.contrats.passage import EnveloppeFichier, ManifestePassage
from usine.contrats.tickets import CauseRacine, Gravite
from usine.contrats.trace import EntreeTrace, TypeTrace
from usine.contrats.versions import CLE_VERSION, CONTRATS_VERSION
from usine.rendu.commun import ContexteRendu

URL_JIRA = charger_yaml(RACINE_DEPOT / "config" / "jira.yaml", ConfigJira).url_site
"""URL du site Jira de `config/jira.yaml`, celle des Passages publiés."""

GRILLE = charger_yaml(RACINE_DEPOT / "config" / "grille_meteo.yaml", GrilleMeteo)
"""Grille livrée, celle des Passages d'essai."""

CONTEXTE_FICTIF = ContexteRendu(
    palier=1, source="journal", version_grille="abc", version_donnees="def", grille=GRILLE
)
"""Contexte d'un rendu hors Passage publié (Passage réduit ou vide)."""

VERSION_PROMPT = "a" * 64
VERSION_MODELE = "factice:modele-1"


def _publier(
    racine: Path, mode_repli: bool, monkeypatch: pytest.MonkeyPatch, sans_jira: bool = False
) -> Path:
    preparer_racine(racine)
    if sans_jira:
        (racine / "config" / "jira.yaml").unlink()
    monkeypatch.chdir(racine)  # aucun `.env` du poste lu par `Secrets`
    if mode_repli:
        monkeypatch.setenv("USINE_MODE_REPLI", "1")
    else:
        monkeypatch.delenv("USINE_MODE_REPLI", raising=False)
    return lancer_rapport(racine, DATE_ARRETE, horloge_figee(), lambda: "abcdef").repertoire


@pytest.fixture(scope="module")
def passage(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Répertoire d'un Passage publié avec `config/jira.yaml`."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        return _publier(tmp_path_factory.mktemp("normal"), False, monkeypatch)


@pytest.fixture(scope="module")
def passage_repli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Répertoire d'un Passage publié en Mode repli (`USINE_MODE_REPLI=1`)."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        return _publier(tmp_path_factory.mktemp("repli"), True, monkeypatch)


@pytest.fixture(scope="module")
def passage_sans_jira(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Répertoire d'un Passage publié sans `config/jira.yaml`."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        return _publier(tmp_path_factory.mktemp("sans-jira"), False, monkeypatch, sans_jira=True)


@pytest.fixture
def consultation(passage: Path) -> ConsultationPassage:
    """Consultation du Passage publié, avec l'URL du site Jira de `config/jira.yaml`."""
    return ConsultationPassage(passage, url_jira=URL_JIRA)


REGLE_JAUNE = RegleDeclenchante(
    code=CodeIndicateur.ind_2,
    couleur=Couleur.jaune,
    operateur=Operateur.superieur,
    numerateur=3,
    denominateur=8,
    seuil_numerateur=3,
    seuil_denominateur=10,
    tickets_en_cause=("DEMO-2",),
)
"""Règle `>` à valeur fractionnaire : `IND-2 : 0,4 (seuil > 0,3)`."""

REGLE_ROUGE = RegleDeclenchante(
    code=CodeIndicateur.ind_1,
    couleur=Couleur.rouge,
    operateur=Operateur.superieur_ou_egal,
    numerateur=7,
    denominateur=1,
    seuil_numerateur=3,
    seuil_denominateur=1,
    tickets_en_cause=("DEMO-6", "DEMO-24"),
)
"""Règle `>=` à valeur entière : `IND-1 : 7 (seuil ≥ 3)`."""


@pytest.fixture
def passage_jaune_rouge(tmp_path: Path) -> ConsultationPassage:
    """Passage réduit à un `meteo.json` : ENT-J jaune, ENT-R rouge, à la Date d'arrêté."""
    meteos = (
        MeteoEntite(
            date_arrete=DATE_ARRETE,
            entite="ENT-J",
            couleur=Couleur.jaune,
            regles=(REGLE_JAUNE,),
            version_grille="abc",
        ),
        MeteoEntite(
            date_arrete=DATE_ARRETE,
            entite="ENT-R",
            couleur=Couleur.rouge,
            regles=(REGLE_ROUGE,),
            version_grille="abc",
        ),
    )
    modele = EnveloppeFichier[tuple[MeteoEntite, ...]]
    enveloppe = modele(
        passage_id="20261012T073000Z-abcdef", date_arrete=DATE_ARRETE, contenu=meteos
    )
    (tmp_path / "meteo.json").write_text(enveloppe.model_dump_json(), encoding="utf-8")
    return ConsultationPassage(tmp_path, date_arrete=DATE_ARRETE)


def _ecrire_json[T](chemin: Path, manifeste: ManifestePassage, contenu: T) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    enveloppe = EnveloppeFichier[T](
        passage_id=manifeste.passage_id, date_arrete=manifeste.date_arrete, contenu=contenu
    )
    chemin.write_text(enveloppe.model_dump_json(), encoding="utf-8")


def completer_palier_2(repertoire: Path) -> None:
    """Manifeste en Palier 2 ; Explications, classification, répartition et trace LLM écrites.

    ENT-B reçoit une Explication citant ses deux premières Anomalies ouvertes, avec un
    Brouillon ; sa première bloquante ouverte est classée « paramétrage ». Depuis le flux
    scripté (contrats 1.2), ENT-A n'a plus d'Anomalie ouverte sur le Programme réduit : les
    bloquantes de B prennent les créations de chaque semaine.
    """
    chemin_manifeste = repertoire / "manifeste.json"
    donnees = json.loads(chemin_manifeste.read_text(encoding="utf-8"))
    donnees["palier"] = 2
    chemin_manifeste.write_text(json.dumps(donnees), encoding="utf-8")
    manifeste = ManifestePassage.model_validate(donnees)
    jour = manifeste.date_arrete
    lecteur = ConsultationPassage(repertoire)
    explications = []
    for entite, brouillon in (("ENT-B", "Relancer l'équipe paramétrage."),):
        cles = tuple(a.cle_ticket for a in lecteur.anomalies(entite=entite).anomalies[:2])
        assert cles, f"aucune Anomalie ouverte {entite} dans le Passage d'essai"
        explications.append(
            SortieExplication(
                date_arrete=jour,
                entite=entite,
                texte=f"{cles[0]} bloque la recette de {entite}.",
                citations=cles,
                brouillon_commentaire=brouillon,
                statut_controle=StatutControle.conforme,
            )
        )
    classee = lecteur.anomalies(entite="ENT-B", gravite=Gravite.bloquante).anomalies[0]
    _ecrire_json(repertoire / "llm" / "explications.json", manifeste, tuple(explications))
    _ecrire_json(
        repertoire / "llm" / "classification.json",
        manifeste,
        (
            SortieClassification(
                cle_ticket=classee.cle_ticket, cause_racine=CauseRacine.parametrage
            ),
        ),
    )
    _ecrire_json(
        repertoire / "llm" / "narrations.json",
        manifeste,
        (SortieNarration(date_arrete=jour, entite="ENT-B", texte="Narration."),),
    )
    pl.DataFrame(
        {
            "date": [jour, jour],
            "entite": ["ENT-A", "ENT-B"],
            "cause_racine": ["parametrage", "reprise_donnees"],
            "nombre": [1, 1234],
        },
        schema=dict(SCHEMA_REPARTITION_CAUSES.colonnes),
    ).write_parquet(
        repertoire / "repartition_causes.parquet", metadata={CLE_VERSION: CONTRATS_VERSION}
    )
    trace = EntreeTrace(
        type_trace=TypeTrace.llm,
        horodatage=datetime(2026, 10, 12, 7, 30, tzinfo=UTC),
        passage_id=manifeste.passage_id,
        date_arrete=jour,
        entite="ENT-B",
        tache=Tache.explication,
        cible="ENT-B",
        fournisseur="factice",
        version_prompt=VERSION_PROMPT,
        version_modele=VERSION_MODELE,
        version_grille=manifeste.version_grille,
        version_donnees=manifeste.version_donnees,
        entree_pseudonymisee="entrée",
        sortie="sortie",
        statut_controle=StatutControle.conforme,
    )
    (repertoire / "trace" / "llm.jsonl").write_text(
        trace.model_dump_json() + "\n", encoding="utf-8"
    )


@pytest.fixture(scope="module")
def passage_palier_2(passage: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Copie du Passage publié, complétée en Palier 2 (fixtures de contrats)."""
    cible = tmp_path_factory.mktemp("palier-2") / "passages" / passage.parent.name / passage.name
    shutil.copytree(passage, cible)
    completer_palier_2(cible)
    return cible
