"""Conversion Jira → `Evenement` canoniques : matrice de la Story 2.2 (AD-3, AD-23)."""

from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

import pytest

from tests.unit.adaptateurs.jira_http.outils import config_jira
from usine.adaptateurs.jira_cloud import (
    convertir_ticket,
    lire_horodatage,
    texte_adf,
    trier_evenements,
    valeur_courante,
)
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, NatureEvenement, SourceEvenement
from usine.contrats.tickets import Champ, TypeTicket

CLOUD = SourceEvenement.jira_cloud


def _ticket(type_jira: str = "Anomalie", **champs: Any) -> dict[str, Any]:
    return {
        "id": "10001",
        "key": "DEMO-1",
        "fields": {
            "issuetype": {"name": type_jira},
            "created": "2026-09-01T09:00:00.000+0000",
            **champs,
        },
    }


def _historique(identifiant: str, instant: str, *items: dict[str, Any]) -> dict[str, Any]:
    return {"id": identifiant, "created": instant, "items": list(items)}


def _item(field_id: str, de: str | None, vers: str | None) -> dict[str, Any]:
    return {"field": field_id, "fieldId": field_id, "fromString": de, "toString": vers}


def _par_id(evenements: list[Evenement]) -> dict[str, Evenement]:
    return {e.id_evenement: e for e in evenements}


def _convertir(
    ticket: dict[str, Any], *historiques: dict[str, Any], config: ConfigJira | None = None
) -> list[Evenement]:
    return convertir_ticket(ticket, historiques, config or config_jira("cloud"), CLOUD)


# --- Création et valeurs initiales ---


def test_creation_puis_attributs_initiaux_non_vides_au_meme_horodatage() -> None:
    evenements = _convertir(
        _ticket(
            status={"name": "Nouvelle"},
            summary="Titre",
            description=None,
            customfield_10043={"value": "ENT-A"},
            customfield_10046={"value": "Bloquante"},
            customfield_10044=None,
            customfield_10045={"value": "  "},
        )
    )
    instant = datetime(2026, 9, 1, 9, tzinfo=UTC)
    assert [e.id_evenement for e in evenements] == [
        "C-10001",
        "C-10001-statut",
        "C-10001-entite",
        "C-10001-gravite",
        "C-10001-titre",
    ]
    assert all(e.horodatage == instant for e in evenements)
    assert evenements[0].nature is NatureEvenement.creation
    assert all(e.nature is NatureEvenement.modification_champ for e in evenements[1:])
    assert [e.vers for e in evenements[1:]] == ["nouvelle", "ENT-A", "bloquante", "Titre"]
    assert all(e.de is None and e.source is CLOUD for e in evenements)


def test_valeur_initiale_issue_du_premier_item_du_champ() -> None:
    evenements = _par_id(
        _convertir(
            _ticket(status={"name": "Fermée"}, customfield_10046={"value": "Mineure"}),
            _historique(
                "30002",
                "2026-09-03T09:00:00.000+0000",
                _item("status", "En analyse", "Fermée"),
            ),
            _historique(
                "30001",
                "2026-09-02T09:00:00.000+0000",
                _item("status", "Nouvelle", "En analyse"),
            ),
        )
    )
    assert evenements["C-10001-statut"].vers == "nouvelle"
    assert evenements["C-10001-gravite"].vers == "mineure"


def test_valeur_initiale_vide_dans_le_premier_item_non_emise() -> None:
    evenements = _par_id(
        _convertir(
            _ticket(status={"name": "Nouvelle"}, customfield_10043={"value": "ENT-A"}),
            _historique(
                "30001", "2026-09-02T09:00:00.000+0000", _item("customfield_10043", None, "ENT-A")
            ),
        )
    )
    assert "C-10001-entite" not in evenements
    assert evenements["30001-1"].de is None
    assert evenements["30001-1"].vers == "ENT-A"


# --- Changelog ---


def test_transition_de_statut() -> None:
    evenements = _par_id(
        _convertir(
            _ticket(status={"name": "En correction"}),
            _historique(
                "20001",
                "2026-09-02T10:00:00.000+0200",
                _item("status", "Nouvelle", "En correction"),
            ),
        )
    )
    transition = evenements["20001-1"]
    assert transition.nature is NatureEvenement.transition
    assert transition.champ is Champ.statut
    assert (transition.de, transition.vers) == ("nouvelle", "en_correction")
    assert transition.horodatage == datetime(2026, 9, 2, 8, tzinfo=UTC)


def test_champ_hors_type_et_champ_non_mappe_ignores_le_rang_compte() -> None:
    evenements = _par_id(
        _convertir(
            _ticket("Cas de test", status={"name": "À faire"}),
            _historique(
                "20004",
                "2026-09-05T16:00:00.000+0000",
                _item("status", "À faire", "In Progress"),
                _item("assignee", None, "Quelqu'un"),
                _item("customfield_10048", "Non exécuté", "OK"),
            ),
        )
    )
    assert "C-10001-statut" not in evenements
    assert [i for i in evenements if not i.startswith("C-")] == ["20004-3"]
    assert evenements["20004-3"].champ is Champ.statut_test
    assert (evenements["20004-3"].de, evenements["20004-3"].vers) == ("non_execute", "ok")


def test_item_sans_effet_canonique_ignore() -> None:
    config = config_jira("cloud")
    valeurs = dict(config.valeurs)
    valeurs[Champ.statut] = MappingProxyType({**config.valeurs[Champ.statut], "Fixed": "fermee"})
    config = config.model_copy(update={"valeurs": MappingProxyType(valeurs)})
    evenements = _par_id(
        _convertir(
            _ticket(status={"name": "Fixed"}),
            _historique(
                "20001", "2026-09-02T10:00:00.000+0000", _item("status", "Nouvelle", "Fermée")
            ),
            _historique(
                "20002", "2026-09-03T10:00:00.000+0000", _item("status", "Fermée", "Fixed")
            ),
            config=config,
        )
    )
    assert "20001-1" in evenements
    assert "20002-1" not in evenements


def test_correspondance_de_la_configuration_seule() -> None:
    config = config_jira("cloud")
    valeurs = dict(config.valeurs)
    valeurs[Champ.statut] = MappingProxyType(
        {**config.valeurs[Champ.statut], "In Progress": "en_correction"}
    )
    config = config.model_copy(update={"valeurs": MappingProxyType(valeurs)})
    evenements = _par_id(
        _convertir(
            _ticket(status={"name": "In Progress"}),
            _historique(
                "20001", "2026-09-02T10:00:00.000+0000", _item("status", "Nouvelle", "In Progress")
            ),
            config=config,
        )
    )
    assert evenements["20001-1"].vers == "en_correction"


def test_historiques_en_double_dedoublonnes() -> None:
    historique = _historique(
        "20001", "2026-09-02T10:00:00.000+0000", _item("status", "Nouvelle", "En analyse")
    )
    evenements = _convertir(_ticket(status={"name": "En analyse"}), historique, dict(historique))
    assert [e.id_evenement for e in evenements].count("20001-1") == 1


def test_meme_horodatage_departage_par_id_numerique() -> None:
    instant = "2026-09-02T10:00:00.000+0000"
    evenements = _convertir(
        _ticket(status={"name": "En correction"}),
        _historique("10000", instant, _item("status", "En analyse", "En correction")),
        _historique("9999", instant, _item("status", "Nouvelle", "En analyse")),
    )
    par_id = _par_id(evenements)
    assert par_id["C-10001-statut"].vers == "nouvelle"
    ids = [e.id_evenement for e in evenements]
    assert ids.index("9999-1") < ids.index("10000-1")


def test_item_standard_sans_field_id_lu_par_field() -> None:
    item = {"field": "status", "fieldtype": "jira", "fromString": "Nouvelle", "toString": "Fermée"}
    evenements = _par_id(
        _convertir(
            _ticket(status={"name": "Fermée"}),
            _historique("20001", "2026-09-02T10:00:00.000+0000", item),
        )
    )
    assert evenements["20001-1"].champ is Champ.statut
    assert (evenements["20001-1"].de, evenements["20001-1"].vers) == ("nouvelle", "fermee")


@pytest.mark.parametrize("field_id", [None, ""])
def test_item_personnalise_sans_field_id_refuse(field_id: str | None) -> None:
    item = {
        "field": "Gravité",
        "fieldtype": "custom",
        "fieldId": field_id,
        "fromString": "Bloquante",
        "toString": "Majeure",
    }
    with pytest.raises(UsineErreur, match=r"DEMO-1 : historique 20001, item 1 : .*fieldId"):
        _convertir(
            _ticket(status={"name": "Nouvelle"}),
            _historique("20001", "2026-09-02T10:00:00.000+0000", item),
        )


def test_contexte_d_erreur_nomme_historique_et_item() -> None:
    with pytest.raises(UsineErreur, match=r"historique 20001, item 2"):
        _convertir(
            _ticket(status={"name": "Nouvelle"}),
            _historique(
                "20001",
                "2026-09-02T10:00:00.000+0000",
                _item("assignee", None, "x"),
                _item("status", "Nouvelle", None),
            ),
        )


# --- Correspondance manquante ---


def test_statut_sans_correspondance_nomme_fichier_cle_valeur_et_ticket() -> None:
    with pytest.raises(UsineErreur) as erreur:
        _convertir(
            _ticket(status={"name": "En analyse"}),
            _historique(
                "20001", "2026-09-02T10:00:00.000+0000", _item("status", "Nouvelle", "In Progress")
            ),
        )
    message = str(erreur.value)
    for attendu in ("config/jira.yaml", "valeurs.statut", "'In Progress'", "DEMO-1"):
        assert attendu in message


def test_type_sans_correspondance() -> None:
    with pytest.raises(UsineErreur, match=r"config/jira\.yaml : types_tickets : .*'Bug'.*DEMO-1"):
        _convertir(_ticket("Bug"))


def test_valeur_courante_sans_correspondance() -> None:
    with pytest.raises(UsineErreur, match=r"valeurs\.gravite : .*'Critique'.*DEMO-1"):
        _convertir(_ticket(customfield_10046={"value": "Critique"}))


# --- Valeurs ---


def test_valeur_courante_des_formes_jira() -> None:
    assert valeur_courante("texte", "x") == "texte"
    assert valeur_courante({"value": "ENT-A", "id": "1"}, "x") == "ENT-A"
    assert valeur_courante({"name": "Nouvelle"}, "x") == "Nouvelle"
    assert valeur_courante(None, "x") is None
    assert valeur_courante("", "x") is None
    with pytest.raises(UsineErreur, match="forme inconnue"):
        valeur_courante(["ENT-A"], "x")


def test_texte_adf_un_paragraphe_par_ligne() -> None:
    document = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Ligne "},
                    {"type": "text", "text": "une", "marks": [{"type": "em"}]},
                ],
            },
            {"type": "paragraph"},
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "a"}]}
                        ],
                    }
                ],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "b"},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "c"},
                ],
            },
        ],
    }
    assert texte_adf(document, "x") == "Ligne une\n\na\nb\nc"
    assert valeur_courante(document, "x") == "Ligne une\n\na\nb\nc"


def test_texte_adf_titre_et_bloc_de_code() -> None:
    document = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Constat"}],
            },
            {
                "type": "codeBlock",
                "attrs": {"language": "sql"},
                "content": [{"type": "text", "text": "SELECT solde FROM compte"}],
            },
            {"type": "paragraph", "content": [{"type": "text", "text": "Fin."}]},
        ],
    }
    assert texte_adf(document, "x") == "Constat\nSELECT solde FROM compte\nFin."


@pytest.mark.parametrize(
    "document",
    [
        {"type": "doc"},
        {"type": "doc", "content": "texte"},
        {"type": "doc", "content": [{"text": "sans type"}]},
        {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text"}]}]},
        {"type": "doc", "content": [{"type": "text", "text": "hors paragraphe"}]},
    ],
)
def test_texte_adf_forme_inconnue(document: dict[str, Any]) -> None:
    with pytest.raises(UsineErreur, match="ADF"):
        valeur_courante(document, "Jira : ticket DEMO-1")


def test_horodatages() -> None:
    assert lire_horodatage("2026-09-01T11:00:00.000+0200", "x") == datetime(
        2026, 9, 1, 9, tzinfo=UTC
    )
    with pytest.raises(UsineErreur, match="sans fuseau"):
        lire_horodatage("2026-09-01T11:00:00.000", "x")
    with pytest.raises(UsineErreur, match="illisible"):
        lire_horodatage("hier", "x")
    with pytest.raises(UsineErreur, match="absent"):
        lire_horodatage(None, "x")


def test_ticket_sans_creation_nomme_le_ticket() -> None:
    ticket = _ticket()
    del ticket["fields"]["created"]
    with pytest.raises(UsineErreur, match="DEMO-1 : created"):
        _convertir(ticket)


# --- Tri ---


def test_tri_global_horodatage_cle_puis_ordre_interne() -> None:
    instant = "2026-09-01T09:00:00.000+0000"
    dix = _convertir(
        {"id": "2", "key": "DEMO-10", "fields": {**_ticket()["fields"], "summary": "b"}}
    )
    deux = _convertir(
        {
            "id": "1",
            "key": "DEMO-2",
            "fields": {**_ticket()["fields"], "summary": "a", "created": instant},
        }
    )
    tries = trier_evenements([dix, deux])
    assert [e.cle_ticket for e in tries] == ["DEMO-2", "DEMO-2", "DEMO-10", "DEMO-10"]
    assert [e.nature for e in tries[:2]] == [
        NatureEvenement.creation,
        NatureEvenement.modification_champ,
    ]
    assert tries[0].type_ticket is TypeTicket.anomalie
