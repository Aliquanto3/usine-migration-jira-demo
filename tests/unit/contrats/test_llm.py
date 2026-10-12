"""Contrats de la couche LLM et de la trace (AD-12, AD-13, AD-16)."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from usine.contrats.llm import (
    CANDIDAT_JETON,
    LONGUEUR_EMPREINTE_JETON,
    AppelOutil,
    EnveloppeCache,
    MessageAgent,
    ReponseAgent,
    ReponseAgentEnregistree,
    ReponseExplication,
    ReponseStructuree,
    SortieClassification,
    StatutControle,
    Tache,
    est_type_jeton,
    variantes_jeton,
)
from usine.contrats.tickets import CauseRacine
from usine.contrats.trace import EntreeTrace, TypeTrace

H = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
PASSAGE = "20261012T080000Z-0a1b2c"


def test_taches_figees() -> None:
    assert [t.value for t in Tache] == ["classification", "explication", "narration", "agent"]


def test_reponse_structuree_generique() -> None:
    sortie = SortieClassification(cle_ticket="DEMO-1", cause_racine=CauseRacine.parametrage)
    reponse = ReponseStructuree[SortieClassification](
        sortie=sortie,
        brut=sortie.model_dump_json(),
        jetons_entree=10,
        jetons_sortie=5,
        version_modele="anthropic:m",
    )
    assert reponse.sortie.statut_controle is StatutControle.non_controle
    relue = ReponseStructuree[SortieClassification].model_validate_json(reponse.model_dump_json())
    assert relue == reponse


def test_classification_refuse_une_cause_inconnue() -> None:
    with pytest.raises(ValidationError):
        SortieClassification.model_validate({"cle_ticket": "DEMO-1", "cause_racine": "autre"})


def test_messages_agent() -> None:
    appel = AppelOutil(id_appel="a1", nom_outil="get_meteo", arguments={"entite": "ENT-A"})
    MessageAgent(role="assistant", contenu="", appels_outils=(appel,))
    MessageAgent(role="outil", contenu="{}", id_appel="a1")
    with pytest.raises(ValidationError):
        MessageAgent(role="utilisateur", contenu="?", appels_outils=(appel,))
    with pytest.raises(ValidationError):
        MessageAgent(role="outil", contenu="{}")


def test_reponse_agent_enregistree() -> None:
    enregistree = ReponseAgentEnregistree(
        passage_id=PASSAGE, horodatage=H, reponse=ReponseAgent(question="?", texte="ENT-A.")
    )
    assert enregistree.contrats_version == "1.2.0"
    with pytest.raises(ValidationError):
        ReponseAgentEnregistree.model_validate(enregistree.model_dump() | {"passage_id": "x"})
    with pytest.raises(ValidationError, match="incompatible"):
        ReponseAgentEnregistree.model_validate(
            enregistree.model_dump() | {"contrats_version": "2.0.0"}
        )


def _trace(**champs: object) -> EntreeTrace:
    base: dict[str, object] = {
        "type_trace": TypeTrace.llm,
        "horodatage": H,
        "passage_id": PASSAGE,
        "date_arrete": date(2026, 10, 12),
        "entite": "ENT-A",
        "tache": Tache.explication,
        "cible": "ENT-A",
        "fournisseur": "anthropic",
        "version_prompt": "a" * 64,
        "version_modele": "anthropic:m",
        "version_grille": "0123456789ab",
        "version_donnees": "b" * 64,
        "entree_pseudonymisee": "CLIENT_3f9a2c",
        "sortie": "…",
        "statut_controle": StatutControle.conforme,
        "cout_estime_eur": Decimal("0.002"),
    }
    base.update(champs)
    return EntreeTrace.model_validate(base)


def test_trace_llm_porte_les_quatre_versions() -> None:
    trace = _trace()
    assert trace.version_prompt and trace.version_modele
    for manquant in ("version_prompt", "version_modele", "tache", "fournisseur", "statut_controle"):
        with pytest.raises(ValidationError):
            _trace(**{manquant: None})


def test_trace_de_prevision() -> None:
    _trace(
        type_trace=TypeTrace.prevision,
        tache=None,
        fournisseur=None,
        version_prompt=None,
        version_modele=None,
        statut_controle=None,
    )
    with pytest.raises(ValidationError):
        _trace(type_trace=TypeTrace.prevision, depuis_cache=True, tache=None)
    with pytest.raises(ValidationError, match="tâche"):
        _trace(type_trace=TypeTrace.prevision, depuis_cache=False, tache=Tache.explication)


def test_trace_cout_negatif_refuse() -> None:
    with pytest.raises(ValidationError):
        _trace(cout_estime_eur=Decimal("-1"))


class _Libre(BaseModel):
    x: int


def test_reponse_structuree_accepte_tout_modele() -> None:
    reponse = ReponseStructuree[_Libre](
        sortie=_Libre(x=1), brut="{}", jetons_entree=0, jetons_sortie=0, version_modele="a:b"
    )
    assert reponse.sortie.x == 1


def test_appel_outil_arguments_figes() -> None:
    """D4 : `arguments` est figé ; l'aller-retour JSON redonne le même modèle."""
    appel = AppelOutil(
        id_appel="a1", nom_outil="list_anomalies", arguments={"entite": "ENT-A", "limite": 3}
    )
    with pytest.raises(TypeError):
        appel.arguments["x"] = 1  # type: ignore[index]
    texte = appel.model_dump_json()
    assert json.loads(texte)["arguments"] == {"entite": "ENT-A", "limite": 3}
    assert AppelOutil.model_validate_json(texte) == appel


@pytest.mark.parametrize(
    ("type_jeton", "attendu"),
    [("COMPTE", True), ("ID_CLIENT", True), ("A", True), ("compte", False), ("_X", False)],
)
def test_type_de_jeton(type_jeton: str, attendu: bool) -> None:
    assert est_type_jeton(type_jeton) is attendu


@pytest.mark.parametrize(
    ("texte", "variantes"),
    [
        ("le COMPTE_abc123 est bloqué", [("COMPTE_abc123",)]),
        ("ID_COMPTE_abc123", [("ID_COMPTE_abc123", "COMPTE_abc123")]),
        ("xCOMPTE_abc123", [("COMPTE_abc123",)]),
        ("COMPTE_abc1234", []),
        ("COMPTE_ABC123", []),
        ("DEMO-12 et ENT-A", []),
    ],
)
def test_grammaire_des_jetons(texte: str, variantes: list[tuple[str, ...]]) -> None:
    assert [variantes_jeton(m) for m in CANDIDAT_JETON.finditer(texte)] == variantes
    assert LONGUEUR_EMPREINTE_JETON == 6


def test_enveloppe_cache_et_reponse_explication() -> None:
    enveloppe = EnveloppeCache(brut='{"texte": "DEMO-3 bloque."}', version_modele="factice:v1")
    assert EnveloppeCache.model_validate_json(enveloppe.model_dump_json()) == enveloppe
    with pytest.raises(ValidationError):
        EnveloppeCache(brut="x", version_modele="")
    reponse = ReponseExplication.model_validate_json(enveloppe.brut)
    assert reponse.brouillon_commentaire == ""
