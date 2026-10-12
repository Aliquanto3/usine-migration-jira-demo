"""`executer_passage` : Passage complet ou rien, progression, manifeste (Story 0.5)."""

import json
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from tests.doublures.fournisseur_factice import FournisseurFactice
from tests.doublures.pseudonymiseur_factice import PseudonymiseurFactice
from tests.doublures.source_en_memoire import SourceEnMemoire
from tests.unit.chaine.environnement import (
    DATE_ARRETE,
    INSTANT,
    horloge_figee,
    horloge_pas_a_pas,
    preparer_racine,
    sans_exclusions,
)
from tests.unit.domaine.constructeur import Flux
from usine.adaptateurs.journal import SourceJournal
from usine.adaptateurs.pseudonymisation import MOTIFS_PAR_DEFAUT
from usine.chaine.ecrivain import EcrivainPassage
from usine.chaine.etapes import EtapeInstantanes, EtapeMeteo
from usine.chaine.execution import executer_passage
from usine.composition import PassageLance, Rapport, construire_rapport, lancer_rapport
from usine.consultation.passage import ConsultationPassage
from usine.contrats.calendrier import jours_ouvres
from usine.contrats.config import GrilleMeteo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ReponseExplication, StatutControle
from usine.contrats.meteo import CodeIndicateur, Couleur, MeteoEntite
from usine.contrats.passage import (
    CHEMIN_JOURNAL,
    FICHIERS_PASSAGE,
    MOTIF_PASSAGE_ID,
    ContextePassage,
    Etape,
    EvenementProgression,
    ManifestePassage,
    ResultatEtape,
    StatutEtape,
    lire_enveloppe,
)
from usine.contrats.trace import EntreeTrace
from usine.contrats.versions import version_prompt
from usine.domaine.meteo import indicateurs as calculer_indicateurs
from usine.domaine.meteo import meteo as calculer_meteo
from usine.ia.explication import lire_prompt
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
        "tickets_textes.parquet",
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
    assert manifeste.horodatage_extraction is None
    assert manifeste.nb_alignements == 0


class EtapeNotee:
    """Étape réussie sans sortie qui note son passage."""

    def __init__(self, journal: list[str], nom: str) -> None:
        self._journal = journal
        self._nom = nom

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        self._journal.append(self._nom)
        return ResultatEtape(StatutEtape.reussie)


def test_extraction_et_alignements_recopies_au_manifeste(rapport: Rapport) -> None:
    """Constat 17 : `nb_alignements` et `horodatage_extraction` viennent de l'extraction."""
    ordre: list[str] = []

    def compter() -> int:
        ordre.append("compte")
        return 3

    extraction = INSTANT - timedelta(minutes=5)
    horloge = horloge_pas_a_pas()
    registre = {
        **rapport.registre,
        Etape.extraction: EtapeNotee(ordre, "extraction"),
        Etape.rendu: EtapeNotee(ordre, "rendu"),
    }
    manifeste = executer_passage(
        registre,
        rapport.configuration,
        DATE_ARRETE,
        EcrivainPassage(rapport.racine_sorties, horloge),
        ConsultationPassage,
        horloge,
        lambda: "abc123",
        rapport.donnees,
        horodatage_extraction=extraction,
        nb_alignements=compter,
    )
    assert ordre == ["extraction", "rendu", "compte"]
    assert manifeste.horodatage_extraction == extraction
    assert manifeste.nb_alignements == 3


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
    # Grille livrée : IND-1 à IND-8 actifs, une ligne par indicateur, Entité et jour.
    codes = [code.value for code in CodeIndicateur]
    assert indicateurs.height == len(attendu) * len(codes)
    assert indicateurs.select("date", "entite").unique(maintain_order=True).rows() == attendu
    assert indicateurs["code"].cast(pl.Utf8).to_list() == codes * len(attendu)
    # Valeurs : identiques à un appel direct du domaine sur tout l'historique du Passage.
    grille = rapport.configuration.grille_meteo
    programme = rapport.configuration.programme
    assert isinstance(grille, GrilleMeteo)
    assert programme is not None
    racine = rapport.racine_sorties.parent
    ancrage = SourceJournal(racine / CHEMIN_JOURNAL).entete.ancrage_semaines
    etats = pl.read_parquet(ecrivain.repertoire_publie / "tickets_etats.parquet")
    directs = pl.concat(
        [
            calculer_indicateurs(
                etats.filter(pl.col("date") <= jour),
                jour,
                ["ENT-A", "ENT-B"],
                grille,
                programme=programme,
                ancrage=ancrage,
            )
            for jour in jours
        ],
        how="vertical",
    )
    colonnes = ["date", "entite", "statut", "motif", "numerateur", "denominateur"]
    comparees = [*colonnes, pl.col("code").cast(pl.Utf8), pl.col("couleur").cast(pl.Utf8)]
    assert indicateurs.select(comparees).equals(directs.select(comparees))
    # Météo publiée (Story 3.6) : chaque `MeteoEntite` de `meteo.json`, règles, valeurs et
    # tickets en cause compris, est celle que calcule directement le domaine.
    meteos_directes = tuple(
        m
        for jour in jours
        for m in calculer_meteo(
            etats.filter(pl.col("date") <= jour),
            jour,
            ["ENT-A", "ENT-B"],
            grille,
            manifeste.version_grille,
            programme=programme,
            ancrage=ancrage,
        )
    )
    assert meteo == meteos_directes
    assert any(m.regles for m in meteo)
    assert all(regle.tickets_en_cause for m in meteo for regle in m.regles)


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
    programme = rapport.configuration.programme
    assert isinstance(grille, GrilleMeteo)
    assert programme is not None
    premier = date(2026, 10, 5)
    remplacements: dict[Etape, object] = {
        Etape.instantanes: EtapeInstantanes(SourceEnMemoire(flux.evenements), premier),
        Etape.meteo: EtapeMeteo(grille, "abcdef012345", ["ENT-A", "ENT-B"], premier, programme),
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


def _passer_en_palier_2(racine: Path) -> None:
    chemin = racine / "config" / "chaine.yaml"
    texte = chemin.read_text(encoding="utf-8")
    assert "palier: 1" in texte
    chemin.write_text(texte.replace("palier: 1", "palier: 2"), encoding="utf-8")


def test_palier_2_explications(tmp_path: Path) -> None:
    # Météo de référence (Palier 1, même Journal) : elle fixe les réponses scriptées.
    a_expliquer = _meteos_a_expliquer(preparer_racine(tmp_path / "p1"))
    reponses = _reponses(a_expliquer)

    racine = preparer_racine(tmp_path / "p2")
    _passer_en_palier_2(racine)
    fournisseur = FournisseurFactice(reponses)
    rapport = construire_rapport(
        racine, fournisseur, PseudonymiseurFactice(b"cle-fictive", {}), horloge_figee()
    )
    manifeste, ecrivain = _executer(rapport)
    assert manifeste.palier == 2
    statuts = {e.etape: e.statut for e in manifeste.etapes}
    assert statuts[Etape.explications] is StatutEtape.reussie
    for etape in (Etape.classification, Etape.repartition_causes, Etape.narration):
        assert statuts[etape] is StatutEtape.sautee
    repertoire = ecrivain.repertoire_publie
    assert repertoire is not None
    assert (repertoire / "llm" / "explications.json").is_file()
    assert (repertoire / "trace" / "llm.jsonl").is_file()
    consultation = ConsultationPassage(repertoire)
    explications = consultation.explications()
    assert [e.entite for e in explications] == [m.entite for m in a_expliquer]
    assert all(e.statut_controle is StatutControle.conforme for e in explications)
    traces = consultation.traces()
    assert len(traces) == len(a_expliquer) == len(fournisseur.appels)
    assert {t.passage_id for t in traces} == {manifeste.passage_id}
    assert {t.version_donnees for t in traces} == {rapport.donnees.version_donnees}
    assert (racine / "donnees" / "cache_llm.sqlite").is_file()


def test_palier_2_sans_fournisseur(tmp_path: Path) -> None:
    racine = preparer_racine(tmp_path)
    _passer_en_palier_2(racine)
    with pytest.raises(UsineErreur, match="aucun fournisseur LLM"):
        construire_rapport(racine)
    assert not (racine / "sorties").exists()
    assert not (racine / "donnees" / "cache_llm.sqlite").exists()


def test_palier_2_sans_cle_de_pseudonymisation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("USINE_CLE_PSEUDO", raising=False)
    racine = preparer_racine(tmp_path)
    _passer_en_palier_2(racine)
    with pytest.raises(UsineErreur, match="USINE_CLE_PSEUDO"):
        construire_rapport(racine, FournisseurFactice())
    assert not (racine / "sorties").exists()
    assert not (racine / "donnees" / "cache_llm.sqlite").exists()
    assert not (racine / "donnees" / "pseudonymes.sqlite").exists()


NUMERO_COMPTE = "FR76 3000 6000 0112 3456 7890 189"
"""Numéro de compte fictif (IBAN de démonstration)."""


def _meteos_a_expliquer(racine: Path) -> list[MeteoEntite]:
    """Météos rouges ou orange d'un Passage Palier 1 sur le Journal de `racine`."""
    reference, _ = _executer(construire_rapport(racine))
    repertoire = racine / "sorties" / "passages" / "2026-10-09" / reference.passage_id
    a_expliquer = [
        m
        for m in ConsultationPassage(repertoire).meteo(DATE_ARRETE)
        if m.couleur in (Couleur.rouge, Couleur.orange)
    ]
    assert a_expliquer, "le jeu de graine 42 doit avoir une Entité rouge ou orange"
    return a_expliquer


def _ajouter_compte_a_la_description(
    racine: Path, cle: str, ajout: str = f"Compte {NUMERO_COMPTE} concerné."
) -> None:
    """Ajoute `ajout` (numéro de compte fictif) à chaque description de `cle` dans le Journal."""
    chemin = racine / "donnees" / "journal.jsonl"
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    modifiees = 0
    for rang, ligne in enumerate(lignes[1:], start=1):
        evenement = json.loads(ligne)
        if evenement["cle_ticket"] == cle and evenement["champ"] == "description":
            evenement["vers"] = f"{evenement['vers']} {ajout}"
            lignes[rang] = json.dumps(evenement, ensure_ascii=False, separators=(",", ":"))
            modifiees += 1
    assert modifiees, f"aucune description pour {cle}"
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def _reponses(a_expliquer: list[MeteoEntite]) -> list[ReponseExplication]:
    return [
        ReponseExplication(texte=f"{m.regles[0].tickets_en_cause[0]} est en cause.")
        for m in a_expliquer
    ]


def test_palier_2_par_lancer_rapport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    a_expliquer = _meteos_a_expliquer(preparer_racine(tmp_path / "p1"))
    monkeypatch.setenv("USINE_CLE_PSEUDO", "cle-de-test-fictive")
    racine = preparer_racine(tmp_path / "p2")
    _passer_en_palier_2(racine)
    instant = datetime(2026, 10, 12, 6, 45, tzinfo=UTC)
    fournisseur = FournisseurFactice(_reponses(a_expliquer))
    lance = lancer_rapport(
        racine, DATE_ARRETE, horloge_figee(instant), lambda: "abc123", fournisseur
    )
    assert lance.manifeste.palier == 2
    traces = ConsultationPassage(lance.repertoire).traces()
    assert len(traces) == len(a_expliquer) == len(fournisseur.appels)
    assert {t.horodatage for t in traces} == {instant}
    assert {t.passage_id for t in traces} == {lance.manifeste.passage_id}
    assert (racine / "donnees" / "pseudonymes.sqlite").is_file()  # `PseudonymiseurHmac`


@pytest.mark.parametrize("pseudonymiseur", ["hmac", "factice"])
def test_deux_passages_palier_2_cache_et_pseudonymisation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pseudonymiseur: str
) -> None:
    a_expliquer = _meteos_a_expliquer(preparer_racine(tmp_path / "p1"))
    cle_en_cause = a_expliquer[0].regles[0].tickets_en_cause[0]
    monkeypatch.setenv("USINE_CLE_PSEUDO", "cle-de-test-fictive")
    racine = preparer_racine(tmp_path / "p2")
    _passer_en_palier_2(racine)
    _ajouter_compte_a_la_description(racine, cle_en_cause)

    def lancer(fournisseur: FournisseurFactice) -> PassageLance:
        injecte = (
            PseudonymiseurFactice(b"cle-de-test-fictive", {"COMPTE": MOTIFS_PAR_DEFAUT["COMPTE"]})
            if pseudonymiseur == "factice"
            else None
        )
        return lancer_rapport(
            racine,
            DATE_ARRETE,
            horloge_pas_a_pas(),
            fournisseur=fournisseur,
            pseudonymiseur=injecte,
        )

    premier_fournisseur = FournisseurFactice(_reponses(a_expliquer))
    premier = lancer(premier_fournisseur)
    second_fournisseur = FournisseurFactice()  # aucune réponse : tout doit venir du cache
    second = lancer(second_fournisseur)
    assert second.repertoire != premier.repertoire
    assert second_fournisseur.appels == []

    # Le numéro de compte a atteint le prompt, pseudonymisé.
    prompts = [str(appel.entree) for appel in premier_fournisseur.appels]
    assert any(re.search(r"\bCOMPTE_[0-9a-f]{6}\b", prompt) for prompt in prompts)
    assert all(NUMERO_COMPTE not in prompt for prompt in prompts)

    gabarit = version_prompt(lire_prompt())
    for lance, depuis_cache in ((premier, False), (second, True)):
        lignes = (lance.repertoire / "trace" / "llm.jsonl").read_text(encoding="utf-8")
        traces = [EntreeTrace.model_validate_json(ligne) for ligne in lignes.splitlines()]
        assert len(traces) == len(a_expliquer)
        assert {t.depuis_cache for t in traces} == {depuis_cache}
        meteos = {m.entite: m for m in ConsultationPassage(lance.repertoire).meteo(DATE_ARRETE)}
        for trace in traces:
            assert trace.entite is not None
            assert trace.version_grille == meteos[trace.entite].version_grille
            assert trace.version_prompt == gabarit
        for fichier in lance.repertoire.rglob("*"):
            if not fichier.is_file():
                continue
            if fichier.name == "tickets_textes.parquet":
                # Données sources du Passage (AD-23), locales et fictives : le numéro y est.
                textes = pl.read_parquet(fichier)
                assert textes["description"].str.contains(NUMERO_COMPTE, literal=True).any()
                continue
            assert NUMERO_COMPTE.encode("utf-8") not in fichier.read_bytes(), fichier.name


def test_rejeu_palier_2_exclusions_par_fichier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-7 : deux Passages Palier 2 (le second servi par le cache) ne diffèrent que par les
    champs exclus de `explications` et de `trace_llm`."""
    a_expliquer = _meteos_a_expliquer(preparer_racine(tmp_path / "p1"))
    monkeypatch.setenv("USINE_CLE_PSEUDO", "cle-de-test-fictive")
    racine = preparer_racine(tmp_path / "p2")
    _passer_en_palier_2(racine)
    premier = lancer_rapport(
        racine,
        DATE_ARRETE,
        horloge_pas_a_pas(),
        fournisseur=FournisseurFactice(_reponses(a_expliquer)),
    )
    second_fournisseur = FournisseurFactice()  # aucune réponse : tout vient du cache
    second = lancer_rapport(
        racine,
        DATE_ARRETE,
        horloge_pas_a_pas(INSTANT + timedelta(hours=1)),
        fournisseur=second_fournisseur,
    )
    assert second_fournisseur.appels == []

    def lire(lance: PassageLance, nom: str) -> object:
        texte = (lance.repertoire / FICHIERS_PASSAGE[nom]).read_text(encoding="utf-8")
        if nom.startswith("trace_"):
            return [json.loads(ligne) for ligne in texte.splitlines() if ligne.strip()]
        return json.loads(texte)

    for nom in ("explications", "trace_llm"):
        a, b = lire(premier, nom), lire(second, nom)
        assert a != b, nom  # passage_id, horodatage, depuis_cache… diffèrent bien
        if nom == "trace_llm":
            assert isinstance(a, list) and isinstance(b, list)
            assert [sans_exclusions(nom, x) for x in a] == [sans_exclusions(nom, y) for y in b]
        else:
            assert sans_exclusions(nom, a) == sans_exclusions(nom, b), nom


def test_palier_2_cle_de_pseudonymisation_blanche(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("USINE_CLE_PSEUDO", "   ")
    racine = preparer_racine(tmp_path)
    _passer_en_palier_2(racine)
    with pytest.raises(UsineErreur, match="USINE_CLE_PSEUDO"):
        construire_rapport(racine, FournisseurFactice())
    assert not (racine / "donnees" / "pseudonymes.sqlite").exists()


def test_palier_2_pseudonymisation_sans_reconnaisseur(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("USINE_CLE_PSEUDO", "cle-de-test-fictive")
    racine = preparer_racine(tmp_path)
    _passer_en_palier_2(racine)
    (racine / "config" / "pseudonymisation.yaml").write_text(
        "langue: fr\nreconnaisseurs: []\n", encoding="utf-8"
    )
    with pytest.raises(UsineErreur, match=r"pseudonymisation\.yaml.*reconnaisseurs"):
        construire_rapport(racine, FournisseurFactice())
    assert not (racine / "sorties").exists()
    assert not (racine / "donnees" / "pseudonymes.sqlite").exists()


def test_palier_2_deux_reconnaisseurs_du_meme_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_expliquer = _meteos_a_expliquer(preparer_racine(tmp_path / "p1"))
    monkeypatch.setenv("USINE_CLE_PSEUDO", "cle-de-test-fictive")
    racine = preparer_racine(tmp_path / "p2")
    _passer_en_palier_2(racine)
    autre_compte = "cpt12345678"
    for meteo_entite in a_expliquer:
        _ajouter_compte_a_la_description(
            racine,
            meteo_entite.regles[0].tickets_en_cause[0],
            f"Comptes {NUMERO_COMPTE} et {autre_compte}.",
        )
    (racine / "config" / "pseudonymisation.yaml").write_text(
        "reconnaisseurs:\n"
        "  - type_jeton: COMPTE\n"
        f"    motif: '{MOTIFS_PAR_DEFAUT['COMPTE']}'\n"
        "  - type_jeton: COMPTE\n"
        "    motif: '\\bcpt\\d{8}\\b'\n",
        encoding="utf-8",
    )
    fournisseur = FournisseurFactice(_reponses(a_expliquer))
    lancer_rapport(racine, DATE_ARRETE, horloge_figee(), fournisseur=fournisseur)
    entrees = [str(appel.entree) for appel in fournisseur.appels]
    assert len(entrees) == len(a_expliquer)
    for entree in entrees:
        assert NUMERO_COMPTE not in entree
        assert autre_compte not in entree
        assert len(set(re.findall(r"\bCOMPTE_[0-9a-f]{6}\b", entree))) >= 2
