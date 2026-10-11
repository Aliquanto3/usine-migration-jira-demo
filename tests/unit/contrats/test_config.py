"""Modèles de configuration (AD-19) ; `ConfigChaine` est couvert par `test_chargeur`."""

from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from usine.contrats.config import (
    ConfigChaine,
    ConfigDemo,
    ConfigJira,
    ConfigLLM,
    ConfigProgramme,
    ConfigPseudonymisation,
    ConfigUsine,
    GrilleMeteo,
)
from usine.contrats.meteo import CodeIndicateur, Couleur, Operateur
from usine.contrats.tickets import Champ, TypeTicket

GRILLE_ADDENDUM_D = """
version: 1
couleurs: [vert, jaune, orange, rouge]
regle_agregation: pire_couleur
garde_fous:
  ind4_min_tests_executes: 20
  ind7_min_entrees_fenetre_glissante: 5
indicateurs:
  IND-1:
    libelle: "Anomalies bloquantes ouvertes"
    seuils: { rouge: ">= 3", orange: ">= 1" }
  IND-2:
    libelle: "Âge de la plus ancienne bloquante ouverte (jours ouvrés)"
    seuils: { rouge: "> 10", orange: "> 5" }
  IND-4:
    libelle: "Taux de KO des cas de test exécutés, phase en cours"
    seuils: { rouge: ">= 0.20", orange: ">= 0.10", jaune: ">= 0.05" }
"""


def _grille(**remplacements: Any) -> GrilleMeteo:
    donnees = yaml.safe_load(GRILLE_ADDENDUM_D)
    donnees.update(remplacements)
    return GrilleMeteo.model_validate(donnees)


def test_grille_de_l_addendum() -> None:
    grille = _grille()
    ind4 = grille.indicateurs[CodeIndicateur.ind_4]
    assert ind4.seuils[Couleur.rouge] == (Operateur.superieur_ou_egal, Fraction(1, 5))
    assert grille.indicateurs[CodeIndicateur.ind_2].seuils[Couleur.orange] == (
        Operateur.superieur,
        Fraction(5),
    )
    assert ind4.active


@pytest.mark.parametrize("seuil", ["=> 3", ">= trois", "3", ">= 0,20", ">= 1e3", 3])
def test_seuil_illisible(seuil: object) -> None:
    indicateurs = {"IND-1": {"libelle": "x", "seuils": {"rouge": seuil}}}
    with pytest.raises(ValidationError):
        _grille(indicateurs=indicateurs)


def test_indicateur_ou_couleur_inconnus() -> None:
    with pytest.raises(ValidationError):
        _grille(indicateurs={"IND-9": {"libelle": "x", "seuils": {"rouge": ">= 1"}}})
    with pytest.raises(ValidationError):
        _grille(indicateurs={"IND-1": {"libelle": "x", "seuils": {"violet": ">= 1"}}})
    with pytest.raises(ValidationError):
        _grille(indicateurs={"IND-1": {"libelle": "x", "seuils": {"vert": ">= 0"}}})


def test_grille_couleurs_dans_l_ordre_de_gravite() -> None:
    with pytest.raises(ValidationError, match="ordre de gravité"):
        _grille(couleurs=["rouge", "orange", "jaune", "vert"])
    with pytest.raises(ValidationError):
        _grille(couleurs=["vert", "rouge"])


def test_grille_seuils_vides() -> None:
    with pytest.raises(ValidationError, match="au moins un seuil"):
        _grille(indicateurs={"IND-1": {"libelle": "x", "seuils": {}}})


def test_grille_sans_indicateur() -> None:
    with pytest.raises(ValidationError, match="indicateurs"):
        _grille(indicateurs={})


def test_grille_agregation_et_cle_inconnue() -> None:
    with pytest.raises(ValidationError):
        _grille(regle_agregation="moyenne")
    with pytest.raises(ValidationError):
        _grille(hysteresis=True)


PROGRAMME: dict[str, Any] = {
    "nom": "Banque Exemple — migration SI cœur",
    "graine": 42,
    "entites": [
        {"code": "ENT-A", "libelle": "Entité A", "vague": "V1"},
        {"code": "ENT-B", "libelle": "Entité B", "vague": "V2"},
    ],
    "vagues": [
        {
            "code": "V1",
            "libelle": "Vague 1",
            "phases": [
                {"phase": "migration_a_blanc", "semaine_debut": 1, "semaine_fin": 3},
                {"phase": "recette", "semaine_debut": 4, "semaine_fin": 8},
            ],
        },
        {"code": "V2", "libelle": "Vague 2", "phases": []},
    ],
    "domaines": ["credits", "depots"],
    "volumetrie": {
        "anomalies_min": 3000,
        "anomalies_max": 5000,
        "entrees_semaine_min": 200,
        "entrees_semaine_max": 500,
    },
}


def test_programme() -> None:
    programme = ConfigProgramme.model_validate(PROGRAMME)
    assert programme.nb_semaines == 8
    assert programme.entites[0].vague == "V1"


@pytest.mark.parametrize(
    "remplacement",
    [
        {"entites": [{"code": "ENT-A", "libelle": "A", "vague": "V9"}]},
        {"entites": [{"code": "ENT-A", "libelle": "A", "vague": "V1"}] * 2},
        {"domaines": ["credits", "credits"]},
        {"nb_semaines": 2},
        {
            "volumetrie": {
                "anomalies_min": 10,
                "anomalies_max": 5,
                "entrees_semaine_min": 0,
                "entrees_semaine_max": 0,
            }
        },
        {
            "volumetrie": {
                "anomalies_min": 0,
                "anomalies_max": 0,
                "entrees_semaine_min": 500,
                "entrees_semaine_max": 200,
            }
        },
        {
            "vagues": [
                {
                    "code": "V1",
                    "libelle": "Vague 1",
                    "phases": [{"phase": "recette", "semaine_debut": 4, "semaine_fin": 2}],
                },
                {"code": "V2", "libelle": "Vague 2", "phases": []},
            ]
        },
        {
            "vagues": [
                {"code": "V1", "libelle": "Vague 1", "phases": []},
                {"code": "V1", "libelle": "Vague 1 bis", "phases": []},
                {"code": "V2", "libelle": "Vague 2", "phases": []},
            ]
        },
    ],
    ids=[
        "vague_inconnue",
        "entite_en_double",
        "domaine_en_double",
        "phase_au_dela_du_programme",
        "anomalies_max_inferieur",
        "entrees_semaine_max_inferieur",
        "semaine_fin_avant_debut",
        "vague_en_double",
    ],
)
def test_programme_incoherent(remplacement: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ConfigProgramme.model_validate(PROGRAMME | remplacement)


JIRA: dict[str, Any] = {
    "url_site": "https://exemple-fictif.atlassian.net",
    "mode": "cloud",
    "cle_projet": "DEMO",
    "marge_extraction_minutes": 5,
    "champs": {
        "statut": "status",
        "entite": "customfield_10031",
        "vague": "customfield_10032",
        "domaine": "customfield_10033",
        "gravite": "priority",
        "phase": "customfield_10034",
        "titre": "summary",
        "description": "description",
        "statut_test": "customfield_10035",
        "statut_certification": "customfield_10036",
    },
    "types_tickets": {"Bug": "anomalie", "Test": "cas_de_test", "Certification": "certification"},
    "valeurs": {
        "statut": {"In Progress": "en_correction", "Done": "fermee"},
        "gravite": {"Highest": "bloquante", "High": "majeure", "Low": "mineure"},
        "phase": {"Recette": "recette"},
        "statut_test": {"Passed": "ok", "Failed": "ko"},
        "statut_certification": {"Approved": "accordee"},
    },
}


def test_jira() -> None:
    jira = ConfigJira.model_validate(JIRA)
    assert jira.champs[Champ.entite] == "customfield_10031"
    assert jira.types_tickets["Test"] is TypeTicket.cas_de_test
    assert jira.valeurs[Champ.statut]["In Progress"] == "en_correction"
    assert jira.valeurs[Champ.statut_certification]["Approved"] == "accordee"


@pytest.mark.parametrize(
    "remplacement",
    [
        {"valeurs": JIRA["valeurs"] | {"statut": {"Done": "Fermée"}}},
        {"valeurs": JIRA["valeurs"] | {"statut_test": {"Passed": "en_correction"}}},
        {"valeurs": JIRA["valeurs"] | {"entite": {"Agence A": "ENT-A"}}},
        {"champs": JIRA["champs"] | {"entite": "customfield_1", "vague": "customfield_1"}},
        {"champs": JIRA["champs"] | {"entite": "  "}},
        {"types_tickets": JIRA["types_tickets"] | {"Bug": "bug"}},
        {"statuts": {"In Progress": "en_correction"}},
    ],
    ids=[
        "libelle_non_canonique",
        "valeur_hors_domaine_du_champ",
        "champ_libre",
        "identifiant_partage",
        "identifiant_vide",
        "type_inconnu",
        "ancienne_cle_statuts",
    ],
)
def test_jira_correspondance_incoherente(remplacement: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ConfigJira.model_validate(JIRA | remplacement)


def test_jira_champ_manquant() -> None:
    champs = {k: v for k, v in JIRA["champs"].items() if k != "gravite"}
    with pytest.raises(ValidationError, match="sans identifiant Jira : gravite"):
        ConfigJira.model_validate(JIRA | {"champs": champs})


def test_jira_type_de_ticket_manquant() -> None:
    types = {"Bug": "anomalie", "Test": "cas_de_test"}
    with pytest.raises(ValidationError, match="sans type Jira : certification"):
        ConfigJira.model_validate(JIRA | {"types_tickets": types})


def test_jira_valeurs_manquantes_pour_un_champ_ferme() -> None:
    valeurs = {k: v for k, v in JIRA["valeurs"].items() if k != "phase"}
    with pytest.raises(ValidationError, match="sans correspondance : phase"):
        ConfigJira.model_validate(JIRA | {"valeurs": valeurs})


def test_llm_lit_un_decimal_yaml() -> None:
    llm = ConfigLLM.model_validate(
        yaml.safe_load("fournisseur: anthropic\nmodele: m\nplafond_cout_passage_eur: '0.50'\n")
    )
    assert llm.plafond_cout_passage_eur == Decimal("0.50")
    assert llm.modeles_par_tache == {}


def test_llm_fournisseur_sans_deux_points() -> None:
    with pytest.raises(ValidationError, match="interdit"):
        ConfigLLM(fournisseur="anthropic:x", modele="m", plafond_cout_passage_eur=Decimal(1))


def test_pseudonymisation_motif_invalide() -> None:
    ConfigPseudonymisation.model_validate(
        {"reconnaisseurs": [{"type_jeton": "COMPTE", "motif": r"FR\d{2}"}]}
    )
    with pytest.raises(ValidationError):
        ConfigPseudonymisation.model_validate(
            {"reconnaisseurs": [{"type_jeton": "COMPTE", "motif": "("}]}
        )
    with pytest.raises(ValidationError):
        ConfigPseudonymisation.model_validate(
            {"reconnaisseurs": [{"type_jeton": "compte", "motif": "x"}]}
        )


def test_demo() -> None:
    assert ConfigDemo(temps_manuel_minutes_par_rapport=120).questions_repli == ()


def test_usine_chaine_seule_obligatoire() -> None:
    usine = ConfigUsine(chaine=ConfigChaine(palier=1))
    assert usine.grille_meteo is None
    with pytest.raises(ValidationError):
        ConfigUsine.model_validate({})


def test_modeles_geles() -> None:
    demo = ConfigDemo(temps_manuel_minutes_par_rapport=120)
    with pytest.raises(ValidationError):
        demo.temps_manuel_minutes_par_rapport = 1  # type: ignore[misc]


def test_aucun_yaml_de_lane_cree(racine_depot: Path) -> None:
    assert sorted(p.name for p in (racine_depot / "config").glob("*.yaml")) == ["chaine.yaml"]
