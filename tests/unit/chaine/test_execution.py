"""`executer_passage` : Passage complet ou rien, progression, manifeste (Story 0.5)."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from tests.doublures.source_en_memoire import SourceEnMemoire
from tests.unit.chaine.environnement import (
    DATE_ARRETE,
    horloge_figee,
    horloge_pas_a_pas,
    preparer_racine,
)
from tests.unit.domaine.constructeur import Flux
from usine.chaine.ecrivain import EcrivainPassage
from usine.chaine.etapes import EtapeInstantanes, EtapeMeteo
from usine.chaine.execution import executer_passage
from usine.composition import Rapport, construire_rapport
from usine.consultation.passage import ConsultationPassage
from usine.contrats.calendrier import jours_ouvres
from usine.contrats.config import GrilleMeteo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import Couleur, MeteoEntite
from usine.contrats.passage import (
    MOTIF_PASSAGE_ID,
    ContextePassage,
    Etape,
    EvenementProgression,
    ManifestePassage,
    ResultatEtape,
    StatutEtape,
    lire_enveloppe,
)
from usine.ports.consultation import Consultation
from usine.ports.etape import Etape as PortEtape

ETAPES_LLM = {Etape.classification, Etape.repartition_causes, Etape.explications, Etape.narration}


class EtapeEnEchec:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        raise self._exc


class EtapeHorsSchema:
    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        return ResultatEtape(StatutEtape.reussie, {"indicateurs": pl.DataFrame({"x": [1]})})


@pytest.fixture
def rapport(tmp_path: Path) -> Rapport:
    return construire_rapport(preparer_racine(tmp_path))


def _executer(
    rapport: Rapport,
    *,
    remplacements: dict[Etape, object] | None = None,
    horloge: Callable[[], datetime] | None = None,
    date_arrete: date = DATE_ARRETE,
) -> tuple[ManifestePassage, EcrivainPassage]:
    horloge = horloge or horloge_pas_a_pas()
    registre = {**rapport.registre, **(remplacements or {})}
    ecrivain = EcrivainPassage(rapport.racine_sorties, horloge)
    manifeste = executer_passage(
        registre,  # type: ignore[arg-type]
        rapport.configuration,
        date_arrete,
        ecrivain,
        ConsultationPassage,
        horloge,
        lambda: "abc123",
        rapport.donnees,
    )
    return manifeste, ecrivain


def _progression(ecrivain: EcrivainPassage) -> list[EvenementProgression]:
    lignes = ecrivain.chemin_progression.read_text(encoding="utf-8").split("\n")
    return [EvenementProgression.model_validate_json(ligne) for ligne in lignes if ligne]


def test_passage_publie(rapport: Rapport) -> None:
    manifeste, ecrivain = _executer(rapport)
    assert MOTIF_PASSAGE_ID.fullmatch(manifeste.passage_id)
    assert manifeste.passage_id == "20261012T073000Z-abc123"
    repertoire = rapport.racine_sorties / "passages" / "2026-10-09" / manifeste.passage_id
    assert ecrivain.repertoire_publie == repertoire
    assert sorted(p.name for p in repertoire.iterdir()) == [
        "indicateurs.parquet",
        "instantanes.parquet",
        "manifeste.json",
        "meteo.json",
        "rapport-2026-10-09.pptx",
        "rapport-2026-10-09.xlsx",
        "tickets_etats.parquet",
    ]
    assert not list((rapport.racine_sorties / "passages").glob(".en-cours-*"))
    relu = ManifestePassage.model_validate_json((repertoire / "manifeste.json").read_bytes())
    assert relu == manifeste


def test_manifeste(rapport: Rapport) -> None:
    manifeste, ecrivain = _executer(rapport)
    assert [e.etape for e in manifeste.etapes] == list(Etape)
    for execution in manifeste.etapes:
        attendu = StatutEtape.sautee if execution.etape in ETAPES_LLM else StatutEtape.reussie
        assert execution.statut is attendu
        assert execution.horodatage_fin > execution.horodatage_debut
    assert manifeste.palier == 1
    assert manifeste.version_grille == rapport.donnees.version_grille
    assert manifeste.version_donnees == rapport.donnees.version_donnees
    assert manifeste.source == "journal"
    assert ecrivain.repertoire_publie is not None
    etats = pl.read_parquet(ecrivain.repertoire_publie / "tickets_etats.parquet")
    nb_attendu = etats.filter(pl.col("date") == DATE_ARRETE).height
    assert manifeste.nb_tickets == nb_attendu > 0
    assert manifeste.horodatage_debut < manifeste.horodatage_fin


def test_progression(rapport: Rapport) -> None:
    _, ecrivain = _executer(rapport)
    lignes = _progression(ecrivain)
    attendu = []
    for etape in Etape:
        final = StatutEtape.sautee if etape in ETAPES_LLM else StatutEtape.reussie
        attendu += [(etape, StatutEtape.en_cours), (etape, final)]
    assert [(e.etape, e.statut) for e in lignes] == attendu
    assert {e.passage_id for e in lignes} == {ecrivain.passage_id}


def test_autoportance_meteo(rapport: Rapport) -> None:
    manifeste, ecrivain = _executer(rapport)
    assert ecrivain.repertoire_publie is not None
    texte = (ecrivain.repertoire_publie / "meteo.json").read_bytes()
    meteo = lire_enveloppe(texte, tuple[MeteoEntite, ...]).contenu
    jours = jours_ouvres(date(2026, 8, 17), DATE_ARRETE)
    attendu = [(jour, entite) for jour in jours for entite in ("ENT-A", "ENT-B")]
    assert [(m.date_arrete, m.entite) for m in meteo] == attendu
    assert {m.version_grille for m in meteo} == {manifeste.version_grille}
    indicateurs = pl.read_parquet(ecrivain.repertoire_publie / "indicateurs.parquet")
    assert indicateurs.height == len(attendu)


@pytest.mark.parametrize(
    ("exc", "message"),
    [
        (RuntimeError("panne"), "RuntimeError : panne"),
        (UsineErreur("message d'origine"), "message d'origine"),
    ],
)
def test_echec_d_etape(rapport: Rapport, exc: Exception, message: str) -> None:
    with pytest.raises(UsineErreur, match="kpi") as erreur:
        _executer(rapport, remplacements={Etape.kpi: EtapeEnEchec(exc)})
    assert message in str(erreur.value)
    passage_id = "20261012T073000Z-abc123"
    echec = rapport.racine_sorties / "echecs" / passage_id
    assert (echec / "tickets_etats.parquet").exists()
    assert not (echec / "manifeste.json").exists()
    assert not (rapport.racine_sorties / "passages" / "2026-10-09").exists()
    assert not list((rapport.racine_sorties / "passages").glob(".en-cours-*"))
    progression = rapport.racine_sorties / "progression" / f"{passage_id}.jsonl"
    derniere = EvenementProgression.model_validate_json(
        progression.read_text(encoding="utf-8").splitlines()[-1]
    )
    assert (derniere.etape, derniere.statut) == (Etape.kpi, StatutEtape.echouee)
    assert message in derniere.message


def test_sortie_hors_schema(rapport: Rapport) -> None:
    with pytest.raises(UsineErreur, match=r"kpi.*SCHEMA_INDICATEUR"):
        _executer(rapport, remplacements={Etape.kpi: EtapeHorsSchema()})
    assert (rapport.racine_sorties / "echecs" / "20261012T073000Z-abc123").is_dir()


def test_registre_incomplet(rapport: Rapport) -> None:
    registre: dict[Etape, PortEtape] = {
        e: i for e, i in rapport.registre.items() if e is not Etape.rendu
    }
    with pytest.raises(UsineErreur, match="rendu"):
        _executer(replace(rapport, registre=registre))
    assert not rapport.racine_sorties.exists()


def test_horloge_figee(rapport: Rapport) -> None:
    manifeste, _ = _executer(rapport, horloge=horloge_figee())
    assert all(e.duree.total_seconds() == 0 for e in manifeste.etapes)


def test_jours_sans_ticket_verts(rapport: Rapport) -> None:
    """Premiers jours et Date d'arrêté sans ticket créé : Météo verte, sans erreur."""
    flux = Flux()
    flux.anomalie("DEMO-1", datetime(2026, 10, 7, 9, tzinfo=UTC))  # mercredi
    flux.transition("DEMO-1", datetime(2026, 10, 8, 9, tzinfo=UTC), "nouvelle", "rejetee")
    grille = rapport.configuration.grille_meteo
    assert isinstance(grille, GrilleMeteo)
    premier = date(2026, 10, 5)
    remplacements: dict[Etape, object] = {
        Etape.instantanes: EtapeInstantanes(SourceEnMemoire(flux.evenements), premier),
        Etape.meteo: EtapeMeteo(grille, "abcdef012345", ["ENT-A", "ENT-B"], premier),
    }
    _, ecrivain = _executer(rapport, remplacements=remplacements)
    assert ecrivain.repertoire_publie is not None
    texte = (ecrivain.repertoire_publie / "meteo.json").read_bytes()
    couleurs = {
        (m.date_arrete.day, m.entite): m.couleur
        for m in lire_enveloppe(texte, tuple[MeteoEntite, ...]).contenu
    }
    assert couleurs[(5, "ENT-A")] is Couleur.vert
    assert couleurs[(7, "ENT-A")] is Couleur.orange
    assert couleurs[(9, "ENT-A")] is Couleur.vert
    assert all(couleurs[(jour, "ENT-B")] is Couleur.vert for jour in range(5, 10))
    # Date d'arrêté antérieure à toute création : aucune ligne d'état, tout est vert.
    plus_tard = horloge_pas_a_pas(datetime(2026, 10, 12, 8, tzinfo=UTC))
    manifeste, ecrivain = _executer(
        rapport, remplacements=remplacements, horloge=plus_tard, date_arrete=date(2026, 10, 6)
    )
    assert manifeste.nb_tickets == 0
    assert ecrivain.repertoire_publie is not None
    texte = (ecrivain.repertoire_publie / "meteo.json").read_bytes()
    meteo = lire_enveloppe(texte, tuple[MeteoEntite, ...]).contenu
    assert len(meteo) == 4
    assert {m.couleur for m in meteo} == {Couleur.vert}


def test_date_anterieure_a_l_historique(rapport: Rapport) -> None:
    with pytest.raises(UsineErreur, match=r"instantanes.*2026-08-14"):
        _executer(rapport, date_arrete=date(2026, 8, 14))


ID = "20261012T073000Z-abc123"


def _lignes_progression(rapport: Rapport) -> list[EvenementProgression]:
    chemin = rapport.racine_sorties / "progression" / f"{ID}.jsonl"
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    return [EvenementProgression.model_validate_json(ligne) for ligne in lignes]


def test_interruption_nettoyee_et_propagee(rapport: Rapport) -> None:
    with pytest.raises(KeyboardInterrupt):
        _executer(rapport, remplacements={Etape.kpi: EtapeEnEchec(KeyboardInterrupt())})  # type: ignore[arg-type]
    assert (rapport.racine_sorties / "echecs" / ID).is_dir()
    assert not list((rapport.racine_sorties / "passages").glob(".en-cours-*"))
    derniere = _lignes_progression(rapport)[-1]
    assert (derniere.etape, derniere.statut) == (Etape.kpi, StatutEtape.echouee)


def test_echec_de_publication(rapport: Rapport, monkeypatch: pytest.MonkeyPatch) -> None:
    def publier_en_panne(self: EcrivainPassage, manifeste: ManifestePassage) -> Path:
        raise OSError("disque plein")

    monkeypatch.setattr(EcrivainPassage, "publier", publier_en_panne)
    with pytest.raises(UsineErreur, match="publication du Passage") as erreur:
        _executer(rapport)
    assert "disque plein" in str(erreur.value)
    derniere = _lignes_progression(rapport)[-1]
    assert (derniere.etape, derniere.statut) == (Etape.rendu, StatutEtape.reussie)
    assert (rapport.racine_sorties / "echecs" / ID).is_dir()
    assert not (rapport.racine_sorties / "passages" / "2026-10-09").exists()


def test_abandon_en_panne_garde_l_erreur_d_etape(
    rapport: Rapport, monkeypatch: pytest.MonkeyPatch
) -> None:
    def abandonner_en_panne(self: EcrivainPassage) -> Path | None:
        raise UsineErreur("déplacement impossible")

    monkeypatch.setattr(EcrivainPassage, "abandonner", abandonner_en_panne)
    with pytest.raises(UsineErreur, match="kpi") as erreur:
        _executer(rapport, remplacements={Etape.kpi: EtapeEnEchec(RuntimeError("panne"))})
    assert "panne" in str(erreur.value)
    assert "déplacement impossible" not in str(erreur.value)
