"""Inventaire de la table *Contrats v1* du spine : chaque nom existe dans son module (AD-2)."""

import importlib
from dataclasses import fields, is_dataclass

import pytest
from pydantic import BaseModel

import usine.contrats as facade
from usine.contrats.schemas import SchemaTable

INVENTAIRE: dict[str, tuple[str, ...]] = {
    "evenements": (
        "EnteteJournal",
        "Evenement",
        "ManifesteInjection",
        "NatureEvenement",
        "SourceEvenement",
        "SCHEMA_EVENEMENT",
        "evenements_en_table",
    ),
    "tickets": (
        "TypeTicket",
        "Champ",
        "StatutAnomalie",
        "Gravite",
        "Phase",
        "StatutTest",
        "StatutCertification",
        "CauseRacine",
        "DOMAINES_CANONIQUES",
        "CHAMPS_PAR_TYPE",
        "STATUTS_FERMES",
        "LIBELLES",
        "SCHEMA_TICKET_ETAT",
        "SCHEMA_TICKET_TEXTE",
    ),
    "calcul": (
        "StatutIndicateur",
        "SCHEMA_INSTANTANE",
        "SCHEMA_KPI",
        "SCHEMA_INDICATEUR",
        "SCHEMA_TENDANCE",
        "PERIMETRE_PROGRAMME",
    ),
    "meteo": (
        "Couleur",
        "CodeIndicateur",
        "Operateur",
        "RegleDeclenchante",
        "MeteoEntite",
        "EvolutionMeteo",
    ),
    "prevision": (
        "SCHEMA_SERIE_STOCK",
        "MethodePrevision",
        "StatutPrevision",
        "FacteurExplicatif",
        "Prevision",
        "RisqueEntreeRouge",
        "ContenuPrevisions",
    ),
    "llm": (
        "Tache",
        "StatutControle",
        "ParametresAppel",
        "ReponseStructuree",
        "MessageAgent",
        "AppelOutil",
        "OutilAgent",
        "ReponseAgentBrute",
        "SortieClassification",
        "SCHEMA_REPARTITION_CAUSES",
        "SortieExplication",
        "SortieNarration",
        "ReponseAgent",
        "ReponseAgentEnregistree",
    ),
    "agent": (
        "ArgumentsGetMeteo",
        "ResultatGetMeteo",
        "ArgumentsListAnomalies",
        "AnomalieResume",
        "ResultatListAnomalies",
        "ArgumentsGetTendance",
        "PointTendance",
        "ResultatGetTendance",
        "ArgumentsGetPrevision",
        "ResultatGetPrevision",
        "ArgumentsGetRisques",
        "ResultatGetRisques",
    ),
    "trace": ("TypeTrace", "EntreeTrace"),
    "passage": (
        "Etape",
        "StatutEtape",
        "EvenementProgression",
        "ExecutionEtape",
        "ManifestePassage",
        "FICHIERS_PASSAGE",
        "CONTENUS_JSON",
        "EXCLUSIONS_REJEU",
        "MOTIF_PASSAGE_ID",
        "former_passage_id",
        "EnveloppeFichier",
        "lire_enveloppe",
        "ContextePassage",
        "ResultatEtape",
    ),
    "config": (
        "ConfigProgramme",
        "GrilleMeteo",
        "ConfigChaine",
        "ConfigJira",
        "ConfigLLM",
        "ConfigPseudonymisation",
        "ConfigDemo",
        "ConfigUsine",
    ),
    "calendrier": (
        "FUSEAU",
        "est_jour_ouvre",
        "jour_local",
        "jour_ouvre_de",
        "jour_ouvre_suivant",
        "jour_ouvre_precedent",
        "jours_ouvres",
        "fenetre_glissante",
        "semaine_programme",
        "dernier_jour_ouvre_ecoule",
    ),
    "format": (
        "formater_nombre",
        "formater_entier",
        "formater_fraction",
        "formater_pourcentage",
        "formater_date",
    ),
    "versions": (
        "CONTRATS_VERSION",
        "version_majeure",
        "verifier_version",
        "version_grille",
        "version_prompt",
        "version_modele",
        "version_donnees",
    ),
}

OBJETS = [
    (module, nom, getattr(importlib.import_module(f"usine.contrats.{module}"), nom))
    for module, noms in INVENTAIRE.items()
    for nom in noms
]


def test_facade() -> None:
    assert set(facade.__all__) == {"CONTRATS_VERSION", "SchemaTable", "UsineErreur", "valider"}


@pytest.mark.parametrize(("module", "nom", "objet"), OBJETS, ids=[f"{m}.{n}" for m, n, _ in OBJETS])
def test_forme_du_contrat(module: str, nom: str, objet: object) -> None:
    if nom.startswith("SCHEMA_"):
        assert isinstance(objet, SchemaTable)
        assert objet.nom == nom
    elif isinstance(objet, type) and issubclass(objet, BaseModel):
        configuration = objet.model_config
        assert configuration.get("frozen") is True, f"{module}.{nom} non gelé"
        assert configuration.get("extra") == "forbid", f"{module}.{nom} accepte l'inconnu"


def test_enregistrement_refuse_l_affectation() -> None:
    from usine.contrats.meteo import Couleur, MeteoEntite

    meteo = MeteoEntite(
        date_arrete="2026-10-12",
        entite="ENT-A",
        couleur=Couleur.vert,
        regles=(),
        version_grille="abc",
    )
    with pytest.raises(ValueError, match="frozen"):
        meteo.entite = "ENT-B"  # type: ignore[misc]


@pytest.mark.parametrize("nom", ["ContextePassage", "ResultatEtape"])
def test_dataclasses_gelees(nom: str) -> None:
    from usine.contrats import passage

    classe = getattr(passage, nom)
    assert is_dataclass(classe)
    assert vars(classe)["__dataclass_params__"].frozen
    assert fields(classe)
