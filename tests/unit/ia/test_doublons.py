"""Tâche `doublons` (bonus) : paires d'Anomalies ouvertes probablement en doublon (FR-36)."""

import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import polars as pl
import pytest
from typer.testing import CliRunner

from tests.doublures.fournisseur_factice import FournisseurFactice
from tests.unit.ia.espions import (
    DATE_ARRETE,
    NUMERO_COMPTE,
    PASSAGE_ID,
    CacheMemoire,
    horloge_espion,
    jeton_compte,
    pseudonymiseur,
    textes,
)
from usine import composition
from usine.contrats.agent import AnomalieResume, ResultatListAnomalies
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ReponseDoublon, SortieDoublon, StatutControle, Tache
from usine.contrats.tickets import SCHEMA_TICKET_TEXTE, Gravite, Phase, StatutAnomalie
from usine.contrats.trace import EntreeTrace, TypeTrace
from usine.contrats.versions import version_prompt
from usine.ia import cli as cli_ia
from usine.ia.doublons import (
    MAX_PAIRES,
    ContexteDoublons,
    DetecteurDoublons,
    candidats,
    detecter_doublons,
    lire_prompt,
    mots,
    similarite,
)
from usine.ia.passerelle import Passerelle
from usine.ports.consultation import Consultation

AUTRE_DATE = date(2026, 10, 12)
SOLDE = ("Solde du compte faux après reprise", "Le solde repris du compte diffère de l'ancien.")
SOLDE_BIS = (
    "Solde du compte erroné après reprise",
    "Le solde repris du compte diffère de l'ancien.",
)
FLUX = ("Flux comptable en retard", "Le fichier du flux arrive après la clôture.")
TEXTES = textes({"DEMO-10": SOLDE_BIS, "DEMO-2": FLUX, "DEMO-1": SOLDE})
"""Deux Anomalies voisines (DEMO-1, DEMO-10) et une sans rapport (DEMO-2), dans le désordre."""
OUVERTES = frozenset({"DEMO-1", "DEMO-2", "DEMO-10"})


def _contexte() -> ContexteDoublons:
    return ContexteDoublons(
        passage_id=PASSAGE_ID,
        version_donnees="d" * 64,
        version_grille="grille123456",
        gabarit=lire_prompt(),
    )


def _reponse(score: float = 0.9, justification: str = "Même écart de solde.") -> ReponseDoublon:
    return ReponseDoublon(score=score, justification=justification)


def _passerelle(
    factice: FournisseurFactice,
    cache: CacheMemoire | None = None,
    plafond: Decimal | None = None,
) -> Passerelle:
    return Passerelle(
        factice,
        pseudonymiseur(),
        cache if cache is not None else CacheMemoire(),
        horloge_espion([]),
        tarif=lambda *_: Decimal(1),
        plafond_cout_passage_eur=plafond,
    )


def _detecter(
    factice: FournisseurFactice,
    table: pl.DataFrame = TEXTES,
    ouvertes: frozenset[str] = OUVERTES,
    cache: CacheMemoire | None = None,
    date_arrete: date = DATE_ARRETE,
    plafond: Decimal | None = None,
) -> tuple[tuple[SortieDoublon, ...], tuple[EntreeTrace, ...]]:
    return detecter_doublons(
        _passerelle(factice, cache, plafond), table, ouvertes, date_arrete, _contexte()
    )


class FournisseurEchouantSur(FournisseurFactice):
    """Échoue (comme un `UnexpectedModelBehavior` converti) aux appels de rang donné."""

    def __init__(self, rangs: set[int], reponses: list[ReponseDoublon]) -> None:
        super().__init__(reponses)
        self._rangs = rangs
        self._rang = 0

    def generer_structure(self, prompt, schema, parametres):  # type: ignore[no-untyped-def]
        rang, self._rang = self._rang, self._rang + 1
        if rang in self._rangs:
            raise UsineErreur("anthropic:modele : appel en échec (UnexpectedModelBehavior)")
        return super().generer_structure(prompt, schema, parametres)


# --- Pré-filtre déterministe ---


def test_mots_sans_accent_ni_cle_ni_mot_vide() -> None:
    assert mots("Solde du compte DEMO-12 erroné", "Écart dans les reprises") == frozenset(
        {"solde", "compte", "errone", "ecart", "reprises"}
    )
    assert mots(None, None) == frozenset()


def test_similarite_jaccard() -> None:
    assert similarite(frozenset({"a", "b"}), frozenset({"b", "c"})) == pytest.approx(1 / 3)
    assert similarite(frozenset(), frozenset()) == 0.0


def test_candidats_bornes_a_max_paires() -> None:
    cles = {f"DEMO-{n}": SOLDE for n in range(1, MAX_PAIRES)}
    lignes = list(textes(cles).iter_rows(named=True))
    paires = candidats(lignes)
    assert len(paires) == MAX_PAIRES
    assert (paires[0][0]["cle_ticket"], paires[0][1]["cle_ticket"]) == ("DEMO-1", "DEMO-2")


def test_candidats_jamais_entre_entites() -> None:
    lignes = list(textes({"DEMO-1": SOLDE}, "ENT-A").iter_rows(named=True)) + list(
        textes({"DEMO-2": SOLDE}, "ENT-B").iter_rows(named=True)
    )
    assert candidats(lignes) == []


# --- Tâche ---


def test_paire_proche_scoree() -> None:
    factice = FournisseurFactice([_reponse(0.9)])
    sorties, traces = _detecter(factice)
    assert sorties == (
        SortieDoublon(
            cle_a="DEMO-1",
            cle_b="DEMO-10",
            score=0.9,
            justification="Même écart de solde.",
            statut_controle=StatutControle.conforme,
        ),
    )
    (appel,) = factice.appels  # DEMO-2 (flux) est trop loin : aucune comparaison
    assert appel.parametres.tache is Tache.doublons
    (trace,) = traces
    assert trace.type_trace is TypeTrace.llm
    assert (trace.tache, trace.cible, trace.entite) == (Tache.doublons, "DEMO-1+DEMO-10", "ENT-A")
    assert trace.version_prompt == version_prompt(lire_prompt())
    assert trace.version_grille == "grille123456"
    assert trace.date_arrete == DATE_ARRETE


def test_score_sous_le_seuil_non_publie_mais_trace() -> None:
    sorties, traces = _detecter(FournisseurFactice([_reponse(0.2)]))
    assert sorties == ()
    assert len(traces) == 1


def test_paires_triees_par_score_decroissant() -> None:
    table = textes({"DEMO-1": SOLDE, "DEMO-2": SOLDE_BIS, "DEMO-3": SOLDE})
    sorties, _ = _detecter(
        FournisseurFactice([_reponse(0.6), _reponse(0.95), _reponse(0.7)]),
        table,
        frozenset({"DEMO-1", "DEMO-2", "DEMO-3"}),
    )
    assert [(s.cle_a, s.cle_b, s.score) for s in sorties] == [
        ("DEMO-1", "DEMO-2", 0.95),
        ("DEMO-2", "DEMO-3", 0.7),
        ("DEMO-1", "DEMO-3", 0.6),  # identiques : similarité 1, comparée la première
    ]


def test_anomalies_fermees_et_autres_tickets_ignores() -> None:
    table = pl.DataFrame(
        {
            "cle_ticket": ["DEMO-1", "DEMO-2", "DEMO-3", "DEMO-4"],
            "type_ticket": ["anomalie", "anomalie", "cas_de_test", "certification"],
            "entite": ["ENT-A"] * 4,
            "titre": [SOLDE[0]] * 4,
            "description": [SOLDE[1]] * 4,
        },
        schema=dict(SCHEMA_TICKET_TEXTE.colonnes),
    )
    factice = FournisseurFactice()
    assert _detecter(factice, table, frozenset({"DEMO-1", "DEMO-3", "DEMO-4"})) == ((), ())
    assert factice.appels == []


def test_aucune_anomalie() -> None:
    factice = FournisseurFactice()
    assert _detecter(factice, textes({}), frozenset()) == ((), ())
    assert factice.appels == []


def test_rejeu_sans_appel_et_paire_modifiee_redemandee() -> None:
    cache = CacheMemoire()
    premier, _ = _detecter(FournisseurFactice([_reponse()]), cache=cache)
    factice = FournisseurFactice()  # tout doit venir du cache
    sorties, traces = _detecter(factice, cache=cache)
    assert factice.appels == [] and sorties == premier
    assert [t.depuis_cache for t in traces] == [True]
    assert sum(t.cout_estime_eur for t in traces) == 0
    modifiee = textes(
        {"DEMO-1": SOLDE, "DEMO-10": ("Solde du compte erroné après reprise", "Écart de solde.")}
    )
    factice = FournisseurFactice([_reponse()])
    _detecter(factice, modifiee, cache=cache)
    assert len(factice.appels) == 1
    # Report : la Date d'arrêté entre dans la clé de cache de cette tâche (AD-12).
    factice = FournisseurFactice([_reponse()])
    _detecter(factice, cache=cache, date_arrete=AUTRE_DATE)
    assert len(factice.appels) == 1


def test_justification_hors_paire_retiree() -> None:
    reponse = _reponse(justification="Même écart de solde. Voir aussi DEMO-9.")
    (sortie,), (trace,) = _detecter(FournisseurFactice([reponse]))
    assert sortie.justification == "Même écart de solde."
    assert sortie.statut_controle is StatutControle.corrige
    assert (trace.statut_controle, trace.phrases_retirees) == (StatutControle.corrige, 1)


def test_justification_citant_la_paire_conforme() -> None:
    reponse = _reponse(justification="DEMO-1 et DEMO-10 : même écart.")
    (sortie,), _ = _detecter(FournisseurFactice([reponse]))
    assert sortie.justification == "DEMO-1 et DEMO-10 : même écart."
    assert sortie.statut_controle is StatutControle.conforme


def test_pseudonymisation_de_l_entree() -> None:
    jeton = jeton_compte()
    reponse = _reponse(justification=f"Le compte {jeton} est le même.")
    table = textes(
        {
            "DEMO-1": (SOLDE[0], f"Le solde du compte {NUMERO_COMPTE} diffère."),
            "DEMO-2": (SOLDE_BIS[0], f"Le solde du compte {NUMERO_COMPTE} diffère."),
        }
    )
    factice = FournisseurFactice([reponse])
    (sortie,), (trace,) = _detecter(factice, table, frozenset({"DEMO-1", "DEMO-2"}))
    (appel,) = factice.appels
    assert NUMERO_COMPTE not in str(appel.entree)
    assert jeton in str(appel.entree)
    assert NUMERO_COMPTE not in trace.entree_pseudonymisee
    assert NUMERO_COMPTE not in trace.sortie
    assert sortie.justification == f"Le compte {NUMERO_COMPTE} est le même."


def test_plafond_atteint_detection_arretee(caplog: pytest.LogCaptureFixture) -> None:
    """Tarif de 1 € par appel, plafond de 0,5 € : le premier appel passe, les autres non."""
    table = textes({"DEMO-1": SOLDE, "DEMO-2": SOLDE_BIS, "DEMO-3": SOLDE})
    factice = FournisseurFactice([_reponse()])
    with caplog.at_level(logging.WARNING, logger="usine.ia.doublons"):
        sorties, traces = _detecter(
            factice, table, frozenset({"DEMO-1", "DEMO-2", "DEMO-3"}), plafond=Decimal("0.5")
        )
    assert len(sorties) == len(traces) == len(factice.appels) == 1
    assert any("plafond" in r.getMessage() for r in caplog.records)


def test_echec_isole_paire_sans_score(caplog: pytest.LogCaptureFixture) -> None:
    table = textes({"DEMO-1": SOLDE, "DEMO-2": SOLDE_BIS, "DEMO-3": SOLDE})
    factice = FournisseurEchouantSur({0}, [_reponse(), _reponse()])
    with caplog.at_level(logging.WARNING, logger="usine.ia.doublons"):
        sorties, traces = _detecter(factice, table, frozenset({"DEMO-1", "DEMO-2", "DEMO-3"}))
    assert len(sorties) == 2
    assert [t.en_echec for t in traces] == [True, False, False]
    assert any("sans score" in r.getMessage() for r in caplog.records)


def test_echecs_consecutifs_font_echouer() -> None:
    cles = {f"DEMO-{n}": SOLDE for n in range(1, 5)}
    factice = FournisseurEchouantSur({0, 1, 2}, [_reponse()])
    with pytest.raises(UsineErreur, match=r"doublons : 3 échecs consécutifs"):
        _detecter(factice, textes(cles), frozenset(cles))


# --- Détecteur sur un Passage ---


class ConsultationPassage:
    """Consultation réduite au manifeste, aux Anomalies ouvertes et aux textes."""

    def __init__(self, table: pl.DataFrame, ouvertes: tuple[str, ...]) -> None:
        self._table = table
        self._ouvertes = ouvertes
        self.dates: list[date | None] = []

    def manifeste(self) -> SimpleNamespace:
        return SimpleNamespace(
            passage_id=PASSAGE_ID,
            date_arrete=DATE_ARRETE,
            version_donnees="d" * 64,
            version_grille="grille123456",
        )

    def anomalies(self, date_arrete: date | None = None) -> ResultatListAnomalies:
        self.dates.append(date_arrete)
        resumes = tuple(
            AnomalieResume(
                cle_ticket=cle,
                entite="ENT-A",
                gravite=Gravite.majeure,
                phase=Phase.recette,
                domaine="",
                statut=StatutAnomalie.en_analyse,
                age_jours_ouvres=0,
            )
            for cle in self._ouvertes
        )
        return ResultatListAnomalies(date_arrete=DATE_ARRETE, anomalies=resumes, total=len(resumes))

    def textes_tickets(self) -> pl.DataFrame:
        return self._table


def test_detecteur_lit_les_anomalies_ouvertes_du_passage() -> None:
    consultation = ConsultationPassage(TEXTES, ("DEMO-1", "DEMO-10"))
    factice = FournisseurFactice([_reponse()])
    detecteur = DetecteurDoublons(_passerelle(factice))
    sorties, traces = detecteur.detecter(cast(Consultation, consultation))
    assert [(s.cle_a, s.cle_b) for s in sorties] == [("DEMO-1", "DEMO-10")]
    assert consultation.dates == [DATE_ARRETE]
    assert traces[0].passage_id == PASSAGE_ID
    assert traces[0].version_donnees == "d" * 64
    assert detecteur.version_prompt == version_prompt(lire_prompt())


def test_detecteur_anomalie_fermee_non_comparee() -> None:
    consultation = ConsultationPassage(TEXTES, ("DEMO-1",))
    factice = FournisseurFactice()
    sorties, _ = DetecteurDoublons(_passerelle(factice)).detecter(cast(Consultation, consultation))
    assert sorties == () and factice.appels == []


def test_composition_construire_doublons(tmp_path: Path) -> None:
    factice = FournisseurFactice([_reponse()])
    doublons = composition.construire_doublons(
        tmp_path, fournisseur=factice, pseudonymiseur=pseudonymiseur()
    )
    sorties, _ = doublons(cast(Consultation, ConsultationPassage(TEXTES, ("DEMO-1", "DEMO-10"))))
    assert len(sorties) == 1
    doublons.fermer()


# --- Commande `usine ia doublons` ---


def test_cli_ecrit_les_paires_et_la_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    passage = tmp_path / "passage"
    passage.mkdir()
    (passage / "manifeste.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    consultation = ConsultationPassage(TEXTES, ("DEMO-1", "DEMO-10"))
    construire = composition.construire_doublons
    monkeypatch.setattr(composition, "consultation_repertoire", lambda _: consultation)
    monkeypatch.setattr(
        composition,
        "construire_doublons",
        lambda racine: construire(racine, FournisseurFactice([_reponse()]), pseudonymiseur()),
    )
    resultat = CliRunner().invoke(cli_ia.app, ["doublons", "--passage", str(passage)])
    assert resultat.exit_code == 0, resultat.output
    assert "0.90  DEMO-1  DEMO-10" in resultat.output
    paires = json.loads(
        (tmp_path / "sorties" / "doublons" / f"{PASSAGE_ID}.json").read_text("utf-8")
    )
    assert [(p["cle_a"], p["cle_b"], p["score"]) for p in paires] == [("DEMO-1", "DEMO-10", 0.9)]
    trace = (tmp_path / "sorties" / "doublons" / f"{PASSAGE_ID}.trace.jsonl").read_text("utf-8")
    assert json.loads(trace)["tache"] == "doublons"


def test_cli_passage_introuvable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    resultat = CliRunner().invoke(cli_ia.app, ["doublons", "--passage", str(tmp_path / "absent")])
    assert resultat.exit_code != 0
    assert isinstance(resultat.exception, UsineErreur)
    assert "Passage publié introuvable" in str(resultat.exception)
