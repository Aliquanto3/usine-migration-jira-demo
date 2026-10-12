"""Passage : étapes, manifeste, enveloppes, contexte (AD-2, AD-7, AD-8, AD-22)."""

from dataclasses import fields
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, get_args

import pytest
from pydantic import BaseModel, ValidationError

from usine.contrats.config import ConfigChaine, ConfigUsine
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import Couleur, MeteoEntite
from usine.contrats.passage import (
    CONTENUS_JSON,
    EXCLUSIONS_REJEU,
    FICHIERS_PASSAGE,
    MOTIF_PASSAGE_ID,
    ContextePassage,
    EnveloppeFichier,
    Etape,
    EvenementProgression,
    ExecutionEtape,
    ManifestePassage,
    ResultatEtape,
    StatutEtape,
    chemin_fichier_passage,
    former_passage_id,
    lire_enveloppe,
)
from usine.contrats.prevision import ContenuPrevisions
from usine.contrats.trace import EntreeTrace

H = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
PASSAGE = "20261012T080000Z-0a1b2c"
D = date(2026, 10, 12)


def test_ordre_des_etapes() -> None:
    assert [e.value for e in Etape] == [
        "extraction",
        "instantanes",
        "kpi",
        "meteo",
        "prevision",
        "classification",
        "repartition_causes",
        "explications",
        "narration",
        "rendu",
    ]


def test_former_passage_id() -> None:
    paris = timezone(timedelta(hours=2))
    identifiant = former_passage_id(datetime(2026, 10, 12, 10, 0, 0, tzinfo=paris), "0a1b2c")
    assert identifiant == PASSAGE
    assert MOTIF_PASSAGE_ID.fullmatch(identifiant)


@pytest.mark.parametrize("suffixe", ["0A1B2C", "0a1b2", "zzzzzz"])
def test_former_passage_id_suffixe_invalide(suffixe: str) -> None:
    with pytest.raises(UsineErreur):
        former_passage_id(H, suffixe)


def test_former_passage_id_horodatage_naif() -> None:
    with pytest.raises(UsineErreur):
        former_passage_id(datetime(2026, 10, 12), "0a1b2c")  # noqa: DTZ001


def _execution(etape: Etape, debut_s: int, fin_s: int) -> ExecutionEtape:
    return ExecutionEtape(
        etape=etape,
        statut=StatutEtape.reussie,
        horodatage_debut=H + timedelta(seconds=debut_s),
        horodatage_fin=H + timedelta(seconds=fin_s),
    )


def _manifeste(**champs: Any) -> ManifestePassage:
    base: dict[str, Any] = {
        "passage_id": PASSAGE,
        "date_arrete": D,
        "palier": 1,
        "source": "journal",
        "horodatage_debut": H,
        "horodatage_fin": H + timedelta(seconds=30),
        "version_grille": "0123456789ab",
        "version_donnees": "b" * 64,
        "cout_llm_eur": Decimal(0),
        "nb_alignements": 0,
        "nb_tickets": 30,
        "etapes": (_execution(Etape.extraction, 0, 2), _execution(Etape.instantanes, 2, 9)),
    }
    base.update(champs)
    return ManifestePassage.model_validate(base)


def test_manifeste_et_duree() -> None:
    manifeste = _manifeste()
    assert manifeste.etapes[1].duree == timedelta(seconds=7)
    assert manifeste.contrats_version == "1.3.0"


def test_exclusions_rejeu_par_fichier() -> None:
    """Forme et contenu d'AD-7 : nom logique → chemins de champ ; aucune table Parquet."""
    assert set(EXCLUSIONS_REJEU) <= set(FICHIERS_PASSAGE)
    assert not [n for n in EXCLUSIONS_REJEU if FICHIERS_PASSAGE[n].endswith(".parquet")]
    assert all(isinstance(c, frozenset) and c for c in EXCLUSIONS_REJEU.values())
    assert EXCLUSIONS_REJEU["manifeste"] == {
        "passage_id",
        "horodatage_debut",
        "horodatage_fin",
        "horodatage_extraction",
        "version_donnees",
        "etapes[].horodatage_debut",
        "etapes[].horodatage_fin",
        "classification_initiale",
        "cout_llm_eur",
    }
    for nom in ("meteo", "previsions", "classification", "explications", "narrations"):
        assert EXCLUSIONS_REJEU[nom] == {"passage_id"}, nom
    assert EXCLUSIONS_REJEU["trace_llm"] == {
        "horodatage",
        "passage_id",
        "version_donnees",
        "depuis_cache",
        "jetons_entree",
        "jetons_sortie",
        "cout_estime_eur",
    }
    assert EXCLUSIONS_REJEU["trace_previsions"] == {"horodatage", "passage_id", "version_donnees"}
    with pytest.raises(TypeError):
        EXCLUSIONS_REJEU["kpi"] = frozenset()  # type: ignore[index]


def test_exclusions_rejeu_couvrent_chaque_enveloppe() -> None:
    """Chaque JSON enveloppé (`CONTENUS_JSON`) exclut son `passage_id` du Rejeu."""
    assert [n for n in CONTENUS_JSON if "passage_id" not in EXCLUSIONS_REJEU.get(n, ())] == []


def _champs(modele: type[BaseModel], chemin: str) -> bool:
    """Vrai si `chemin` (`a`, `a[].b`) désigne un champ de `modele`."""
    tete, _, reste = chemin.partition("[].")
    if tete not in modele.model_fields:
        return False
    if not reste:
        return True
    annotation = modele.model_fields[tete].annotation
    (element, _points) = get_args(annotation)
    return _champs(element, reste)


@pytest.mark.parametrize("nom", sorted(n for n in EXCLUSIONS_REJEU if not n.startswith("rapport_")))
def test_exclusions_rejeu_designent_des_champs(nom: str) -> None:
    """Les rendus (`rapport_*`) sont repérés par cellule ou libellé, pas par champ : `contrats`
    n'importe pas `rendu`, leur garde vit sous `tests/unit/rendu/` (contrats 1.2)."""
    modele: type[BaseModel]
    if nom == "manifeste":
        modele = ManifestePassage
    elif nom.startswith("trace_"):
        modele = EntreeTrace
    else:
        modele = EnveloppeFichier[CONTENUS_JSON[nom]]  # type: ignore[valid-type]
    assert [c for c in EXCLUSIONS_REJEU[nom] if not _champs(modele, c)] == []


def test_manifeste_etapes_hors_ordre() -> None:
    with pytest.raises(ValidationError):
        _manifeste(etapes=(_execution(Etape.kpi, 0, 1), _execution(Etape.extraction, 1, 2)))
    with pytest.raises(ValidationError):
        _manifeste(etapes=(_execution(Etape.kpi, 0, 1), _execution(Etape.kpi, 1, 2)))


def test_manifeste_passage_id_invalide() -> None:
    with pytest.raises(ValidationError):
        _manifeste(passage_id="passage-1")


def test_execution_fin_avant_debut() -> None:
    with pytest.raises(ValidationError):
        _execution(Etape.kpi, 5, 1)


def test_evenement_progression() -> None:
    evenement = EvenementProgression(
        passage_id=PASSAGE, etape=Etape.kpi, statut=StatutEtape.en_cours, horodatage=H
    )
    assert EvenementProgression.model_validate_json(evenement.model_dump_json()) == evenement


def test_fichiers_du_passage() -> None:
    assert chemin_fichier_passage("rapport_xlsx", D) == "rapport-2026-10-12.xlsx"
    assert chemin_fichier_passage("trace_llm", D) == "trace/llm.jsonl"
    assert "manifeste" in FICHIERS_PASSAGE
    with pytest.raises(UsineErreur):
        chemin_fichier_passage("inconnu", D)


def _meteo() -> MeteoEntite:
    return MeteoEntite(
        date_arrete=D, entite="ENT-A", couleur=Couleur.vert, regles=(), version_grille="abc"
    )


def test_enveloppe_aller_retour() -> None:
    enveloppe = EnveloppeFichier[tuple[MeteoEntite, ...]](
        passage_id=PASSAGE, date_arrete=D, contenu=(_meteo(),)
    )
    texte = enveloppe.model_dump_json()
    assert '"contrats_version":"1.3.0"' in texte
    relue = lire_enveloppe(texte, tuple[MeteoEntite, ...])
    assert relue.contenu == (_meteo(),)
    assert relue.passage_id == PASSAGE


def test_enveloppe_version_majeure_differente() -> None:
    enveloppe = EnveloppeFichier[MeteoEntite](passage_id=PASSAGE, date_arrete=D, contenu=_meteo())
    texte = enveloppe.model_dump_json().replace('"1.3.0"', '"2.0.0"')
    with pytest.raises(UsineErreur) as erreur:
        lire_enveloppe(texte, MeteoEntite)
    assert "2.0.0" in str(erreur.value)
    assert "1.3.0" in str(erreur.value)


def test_enveloppe_1_0_0_lisible() -> None:
    """Contrats 1.3.0 : un Passage écrit en 1.0.0 (même majeure) reste lisible (AD-2)."""
    enveloppe = EnveloppeFichier[MeteoEntite](passage_id=PASSAGE, date_arrete=D, contenu=_meteo())
    texte = enveloppe.model_dump_json().replace('"1.3.0"', '"1.0.0"')
    assert '"contrats_version":"1.0.0"' in texte
    relue = lire_enveloppe(texte, MeteoEntite)
    assert relue.contrats_version == "1.0.0"
    assert relue.contenu == _meteo()
    manifeste = ManifestePassage.model_validate_json(
        _manifeste().model_dump_json().replace('"1.3.0"', '"1.0.0"')
    )
    assert manifeste.contrats_version == "1.0.0"


def test_contrats_version_verifiee_par_les_modeles() -> None:
    with pytest.raises(ValidationError, match=r"2\.0\.0"):
        EnveloppeFichier[MeteoEntite](
            contrats_version="2.0.0", passage_id=PASSAGE, date_arrete=D, contenu=_meteo()
        )
    with pytest.raises(ValidationError, match=r"2\.0\.0"):
        _manifeste(contrats_version="2.0.0")
    assert _manifeste(contrats_version="1.9.3").contrats_version == "1.9.3"


def test_contenus_json() -> None:
    assert set(CONTENUS_JSON) == {
        "meteo",
        "previsions",
        "classification",
        "explications",
        "narrations",
    }
    assert set(CONTENUS_JSON) <= set(FICHIERS_PASSAGE)
    assert all(FICHIERS_PASSAGE[nom].endswith(".json") for nom in CONTENUS_JSON)
    assert CONTENUS_JSON["previsions"] is ContenuPrevisions
    contenu = ContenuPrevisions(previsions=(), risques=())
    enveloppe = EnveloppeFichier[ContenuPrevisions](
        passage_id=PASSAGE, date_arrete=D, contenu=contenu
    )
    relue = lire_enveloppe(enveloppe.model_dump_json(), CONTENUS_JSON["previsions"])
    assert relue.contenu == contenu


def test_enveloppe_version_lue_avant_le_contenu() -> None:
    texte = '{"contrats_version": "2.0.0", "contenu": "illisible"}'
    with pytest.raises(UsineErreur, match=r"2\.0\.0"):
        lire_enveloppe(texte, MeteoEntite)


@pytest.mark.parametrize(
    "texte",
    [
        "{",
        "[]",
        '{"passage_id": "x"}',
        '{"contrats_version": 1}',
        '{"contrats_version": "1.0.0", "passage_id": "x", "date_arrete": "2026-10-12"}',
    ],
)
def test_enveloppe_invalide(texte: str) -> None:
    with pytest.raises(UsineErreur):
        lire_enveloppe(texte, MeteoEntite)


def _configuration() -> ConfigUsine:
    return ConfigUsine(chaine=ConfigChaine(palier=1))


def test_contexte_passage() -> None:
    ctx = ContextePassage(
        date_arrete=D,
        passage_id=PASSAGE,
        configuration=_configuration(),
        consultation="lecteur",
    )
    assert ctx.consultation == "lecteur"
    with pytest.raises(UsineErreur):
        ContextePassage(
            date_arrete=D,
            passage_id="x",
            configuration=_configuration(),
            consultation=None,
        )


def test_palier_lu_dans_la_configuration() -> None:
    ctx = ContextePassage(
        date_arrete=D,
        passage_id=PASSAGE,
        configuration=ConfigUsine(chaine=ConfigChaine(palier=2)),
        consultation=None,
    )
    assert ctx.palier == 2
    assert "palier" not in {f.name for f in fields(ContextePassage)}


def test_resultat_etape() -> None:
    resultat = ResultatEtape(StatutEtape.reussie, {"meteo": (_meteo(),)})
    assert resultat.traces == ()
    with pytest.raises(TypeError):
        resultat.sorties["kpi"] = None  # type: ignore[index]
    assert ResultatEtape(StatutEtape.sautee).sorties == {}


def test_resultat_etape_invalide() -> None:
    with pytest.raises(UsineErreur, match="inconnu"):
        ResultatEtape(StatutEtape.reussie, {"inconnu": 1})
    with pytest.raises(UsineErreur):
        ResultatEtape(StatutEtape.echouee)
    with pytest.raises(UsineErreur):
        ResultatEtape(StatutEtape.sautee, {"meteo": ()})


@pytest.mark.parametrize(
    ("nom", "valeur"),
    [
        ("meteo", [_meteo()]),
        ("meteo", ("vert",)),
        ("meteo", _meteo()),
        ("previsions", ()),
        ("narrations", (_meteo(),)),
    ],
)
def test_resultat_etape_sortie_json_mal_typee(nom: str, valeur: object) -> None:
    with pytest.raises(UsineErreur, match=nom):
        ResultatEtape(StatutEtape.reussie, {nom: valeur})


def test_resultat_etape_sorties_json_typees() -> None:
    resultat = ResultatEtape(
        StatutEtape.reussie,
        {
            "meteo": (),
            "previsions": ContenuPrevisions(previsions=(), risques=()),
            "classification": (),
        },
    )
    assert set(resultat.sorties) == {"meteo", "previsions", "classification"}


def test_execution_statut_non_final() -> None:
    for statut in (StatutEtape.en_cours, StatutEtape.echouee):
        with pytest.raises(ValidationError, match="statut final"):
            ExecutionEtape(etape=Etape.kpi, statut=statut, horodatage_debut=H, horodatage_fin=H)


def test_manifeste_fin_avant_debut() -> None:
    with pytest.raises(ValidationError, match="fin du Passage"):
        _manifeste(horodatage_fin=H - timedelta(seconds=1))
