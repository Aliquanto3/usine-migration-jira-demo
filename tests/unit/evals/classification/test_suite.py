"""Suite d'évaluation de la classification (Story 6.9, SM-9) : rejeu hors réseau.

Le mode `--reel` (réseau, secrets, coût) n'est jamais lancé ici : le seul test du chemin réel
remplace la façade de composition par un classificateur aux réponses enregistrées.
"""

import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from evals.classification import __main__ as cli
from evals.classification import suite as module_suite
from evals.classification import tickets as module_tickets
from evals.classification.metriques import NON_CLASSE, evaluer
from evals.classification.suite import (
    VERSION_MODELE_ENREGISTRE,
    FournisseurEnregistre,
    PseudonymiseurIdentite,
    ReponsesEnregistrees,
    ajouter_historique,
    ecrire_resultat,
    executer_suite,
    lire_reponses,
    verifier_ad19,
)
from evals.classification.tickets import (
    CHEMIN_TICKETS_MANUELS,
    NOMBRE_TICKETS_MANUELS,
    SourceGenerateur,
    TicketManuel,
    charger_source_generateur,
    charger_tickets_manuels,
)
from usine.composition import Classificateur, construire_classificateur
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import (
    EnteteJournal,
    Evenement,
    NatureEvenement,
    SourceEvenement,
)
from usine.contrats.tickets import CauseRacine, Champ, TypeTicket
from usine.contrats.versions import version_prompt
from usine.generateur import corpus as corpus_generateur
from usine.ports.fournisseur_llm import FournisseurLLM
from usine.ports.pseudonymiseur import Pseudonymiseur

INSTANT = datetime(2026, 10, 13, 7, 30, tzinfo=UTC)
RACINE = Path(__file__).resolve().parents[4]
VERSION_CORPUS = "llm-1"
MODELE_CORPUS = "mistral:mistral-medium-latest"
MODELE_CLASSIFICATION = "anthropic:claude-haiku-5-5"

R = CauseRacine.reprise_donnees
T = CauseRacine.regle_transformation
P = CauseRacine.parametrage
E = CauseRacine.environnement

VERITE_MINI = {"DEMO-1": R, "DEMO-2": T, "DEMO-3": P, "DEMO-5": R}
"""Vérité du mini-Journal : quatre Anomalies (DEMO-4 est un Cas de test)."""


# --- Fabriques ---


def _evenement(
    numero: int, cle: str, type_ticket: TypeTicket, champ: Champ | None = None, vers: str = ""
) -> Evenement:
    return Evenement(
        id_evenement=f"e{numero}",
        cle_ticket=cle,
        type_ticket=type_ticket,
        horodatage=datetime(2026, 9, 1, 8, numero, tzinfo=UTC),
        nature=NatureEvenement.creation if champ is None else NatureEvenement.modification_champ,
        champ=champ,
        vers=vers if champ is not None else None,
        source=SourceEvenement.journal,
    )


def _ecrire_donnees(
    repertoire: Path,
    *,
    verite: dict[str, CauseRacine] | None = None,
    version_corpus: str = VERSION_CORPUS,
    modele_corpus: str = MODELE_CORPUS,
) -> Path:
    """Mini-Journal (quatre Anomalies, un Cas de test) et sa vérité terrain sous `repertoire`."""
    repertoire.mkdir(parents=True, exist_ok=True)
    entete = EnteteJournal(
        graine=1,
        date_generation=date(2026, 9, 30),
        date_injection=date(2026, 9, 1),
        ancrage_semaines=date(2026, 8, 31),
        version_corpus=version_corpus,
        modele_corpus=modele_corpus,
    )
    evenements: list[Evenement] = []
    for rang, cle in enumerate(("DEMO-1", "DEMO-2", "DEMO-3", "DEMO-5"), start=1):
        base = rang * 10
        evenements += [
            _evenement(base, cle, TypeTicket.anomalie),
            _evenement(base + 1, cle, TypeTicket.anomalie, Champ.entite, "credits"),
            _evenement(base + 2, cle, TypeTicket.anomalie, Champ.titre, f"Titre {cle}"),
            _evenement(base + 3, cle, TypeTicket.anomalie, Champ.description, f"Texte {cle}"),
        ]
    evenements.append(_evenement(55, "DEMO-4", TypeTicket.cas_de_test))
    lignes = [entete.model_dump_json(), *(e.model_dump_json() for e in evenements)]
    (repertoire / "journal.jsonl").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    contenu = {cle: cause.value for cle, cause in (verite or VERITE_MINI).items()}
    (repertoire / "verite_terrain.json").write_text(json.dumps(contenu), encoding="utf-8")
    return repertoire


def _ecrire_corpus(
    chemin: Path, version: str = VERSION_CORPUS, modele: str = MODELE_CORPUS
) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps({"version_corpus": version, "modele_corpus": modele, "domaines": {}}),
        encoding="utf-8",
    )
    return chemin


@pytest.fixture
def source(tmp_path: Path) -> SourceGenerateur:
    donnees = _ecrire_donnees(tmp_path / "donnees")
    return charger_source_generateur(donnees, _ecrire_corpus(tmp_path / "textes.json"))


def _reponses(
    propositions: dict[str, CauseRacine], modele: str | None = MODELE_CLASSIFICATION
) -> ReponsesEnregistrees:
    return ReponsesEnregistrees(propositions, modele, Path("anterieur.json"))


@pytest.fixture(scope="module")
def tickets() -> tuple[TicketManuel, ...]:
    return charger_tickets_manuels()


@pytest.fixture(scope="module")
def resultat_manuels(
    tickets: tuple[TicketManuel, ...], tmp_path_factory: pytest.TempPathFactory
) -> Any:
    return executer_suite(tmp_path_factory.mktemp("racine"), manuels=tickets, horloge=INSTANT)


# --- Doublures, constantes, façade ---


def test_doublures_implementent_les_ports() -> None:
    assert isinstance(FournisseurEnregistre("manuels", {}), FournisseurLLM)
    assert isinstance(PseudonymiseurIdentite(), Pseudonymiseur)


def test_constantes_alignees_sur_le_generateur() -> None:
    assert module_tickets.CHEMIN_CORPUS == corpus_generateur.CHEMIN_CORPUS
    assert module_tickets.MODELE_GABARITS == corpus_generateur.MODELE_GABARITS


def test_facade_classificateur_version_du_prompt_et_du_modele(tmp_path: Path) -> None:
    classificateur = construire_classificateur(
        tmp_path,
        fournisseur=FournisseurEnregistre("x", {}),
        pseudonymiseur=PseudonymiseurIdentite(),
    )
    assert isinstance(classificateur, Classificateur)
    gabarit = (RACINE / "src" / "usine" / "ia" / "prompts" / "classification.md").read_bytes()
    assert classificateur.version_prompt == version_prompt(gabarit)
    assert classificateur.version_modele == VERSION_MODELE_ENREGISTRE
    classificateur.fermer()


def test_fournisseur_enregistre_cle_sans_reponse_nommee(source: SourceGenerateur) -> None:
    classificateur = construire_classificateur(
        Path("."),
        fournisseur=FournisseurEnregistre("generateur", {}),
        pseudonymiseur=PseudonymiseurIdentite(),
    )
    with pytest.raises(UsineErreur, match="aucune réponse enregistrée pour DEMO-1"):
        classificateur(source.textes)


# --- Métriques ---


def test_metriques_exemple_calcule_a_la_main() -> None:
    verite = {"A-1": R, "A-2": R, "A-3": T, "A-4": T}
    propositions = {"A-1": R, "A-2": T, "A-3": T}
    mesures = evaluer(verite, propositions)
    # R : VP 1, FP 0, FN 1 → P 1, R 0,5, F1 2/3 ; T : VP 1, FP 1, FN 1 → P 0,5, R 0,5, F1 0,5.
    assert mesures["par_cause"]["reprise_donnees"]["f1"] == pytest.approx(2 / 3)
    assert mesures["par_cause"]["regle_transformation"]["precision"] == pytest.approx(0.5)
    assert mesures["par_cause"]["regle_transformation"]["rappel"] == pytest.approx(0.5)
    assert mesures["f1_macro"] == pytest.approx((2 / 3 + 0.5) / 2)
    assert mesures["exactitude"] == pytest.approx(0.5)
    assert mesures["non_classes"] == ["A-4"]
    assert mesures["matrice_confusion"]["regle_transformation"][NON_CLASSE] == 1
    assert mesures["matrice_confusion"]["reprise_donnees"]["regle_transformation"] == 1
    assert set(mesures["par_cause"]) == {"reprise_donnees", "regle_transformation"}


def test_metriques_cause_seulement_proposee_compte_pour_zero() -> None:
    mesures = evaluer({"A-1": R, "A-2": R}, {"A-1": R, "A-2": E})
    assert mesures["par_cause"]["environnement"] == {
        "precision": 0.0,
        "rappel": 0.0,
        "f1": 0.0,
        "support": 0,
        "proposees": 1,
    }
    assert mesures["f1_macro"] == pytest.approx((2 / 3 + 0.0) / 2)


def test_metriques_vides_et_proposition_sans_verite() -> None:
    assert evaluer({}, {})["f1_macro"] == 0.0
    with pytest.raises(UsineErreur, match="A-9"):
        evaluer({"A-1": R}, {"A-9": R})


# --- Tickets manuels ---


def test_trente_tickets_versionnes_varies(tickets: tuple[TicketManuel, ...]) -> None:
    assert len(tickets) == NOMBRE_TICKETS_MANUELS
    assert len({ticket.cle for ticket in tickets}) == NOMBRE_TICKETS_MANUELS
    par_cause = Counter(ticket.cause_attendue for ticket in tickets)
    assert set(par_cause) == set(CauseRacine)
    assert set(par_cause.values()) <= {4, 5}
    assert len({ticket.domaine for ticket in tickets}) >= 5
    erreurs = [t for t in tickets if t.reponse.cause_racine is not t.cause_attendue]
    assert 1 <= len(erreurs) <= 6


@pytest.mark.parametrize(
    ("modifier", "motif"),
    [
        (lambda donnees: donnees[:29], "29 tickets, 30 attendus"),
        (lambda donnees: [*donnees[:29], donnees[0]], "en double"),
        (
            lambda donnees: [{**donnees[0], "cause_attendue": "inconnue"}, *donnees[1:]],
            "mal formés",
        ),
    ],
)
def test_tickets_manuels_invalides(tmp_path: Path, modifier: Any, motif: str) -> None:
    donnees = json.loads(CHEMIN_TICKETS_MANUELS.read_text(encoding="utf-8"))
    chemin = tmp_path / "tickets.json"
    chemin.write_text(json.dumps(modifier(donnees)), encoding="utf-8")
    with pytest.raises(UsineErreur, match=motif) as erreur:
        charger_tickets_manuels(chemin)
    assert str(chemin) in str(erreur.value)


def test_rejeu_manuels_f1_et_versions(
    resultat_manuels: Any, tickets: tuple[TicketManuel, ...]
) -> None:
    bloc = resultat_manuels["sources"]["manuels"]
    attendu = evaluer(
        {t.cle: t.cause_attendue for t in tickets},
        {t.cle: t.reponse.cause_racine for t in tickets},
    )
    assert resultat_manuels["mode"] == "rejeu"
    assert bloc["f1_macro"] == pytest.approx(attendu["f1_macro"])
    assert set(bloc["par_cause"]) == {cause.value for cause in CauseRacine}
    assert bloc["nombre"] == NOMBRE_TICKETS_MANUELS
    assert bloc["non_classes"] == []
    assert len(bloc["details"]) == NOMBRE_TICKETS_MANUELS
    assert resultat_manuels["f1_macro"] == {"manuels": bloc["f1_macro"], "generateur": None}
    assert resultat_manuels["sm9_atteint"] is None
    assert resultat_manuels["version_modele"] == VERSION_MODELE_ENREGISTRE
    gabarit = (RACINE / "src" / "usine" / "ia" / "prompts" / "classification.md").read_bytes()
    assert resultat_manuels["version_prompt"] == version_prompt(gabarit)


# --- Source générateur ---


def test_source_generateur_anomalies_et_verite(source: SourceGenerateur) -> None:
    assert source.textes["cle_ticket"].to_list() == ["DEMO-1", "DEMO-2", "DEMO-3", "DEMO-5"]
    assert set(source.textes["type_ticket"].to_list()) == {"anomalie"}
    assert source.textes["titre"].to_list()[0] == "Titre DEMO-1"
    assert dict(source.verite) == VERITE_MINI


@pytest.mark.parametrize(
    ("journal", "corpus", "motif"),
    [
        (
            {"version_corpus": "provisoire-1", "modele_corpus": "gabarits-provisoires"},
            {},
            "gabarits provisoires",
        ),
        ({"version_corpus": "llm-0"}, {}, "différent du Corpus versionné"),
        ({"modele_corpus": "anthropic:autre"}, {}, "usine donnees generer"),
        (
            {},
            {"version": "provisoire-1", "modele": "gabarits-provisoires"},
            "Corpus provisoire",
        ),
    ],
)
def test_source_generateur_corpus_provisoire_ou_different(
    tmp_path: Path, journal: dict[str, str], corpus: dict[str, str], motif: str
) -> None:
    donnees = _ecrire_donnees(
        tmp_path / "donnees",
        version_corpus=journal.get("version_corpus", VERSION_CORPUS),
        modele_corpus=journal.get("modele_corpus", MODELE_CORPUS),
    )
    with pytest.raises(UsineErreur, match=motif):
        charger_source_generateur(donnees, _ecrire_corpus(tmp_path / "textes.json", **corpus))


@pytest.mark.parametrize(
    ("verite", "motif"),
    [
        ({**VERITE_MINI, "DEMO-4": R}, "absente.* des Anomalies du Journal.*DEMO-4"),
        ({"DEMO-1": R, "DEMO-2": T, "DEMO-3": P}, "sans vérité terrain.*DEMO-5"),
    ],
)
def test_source_generateur_verite_incoherente(
    tmp_path: Path, verite: dict[str, CauseRacine], motif: str
) -> None:
    donnees = _ecrire_donnees(tmp_path / "donnees", verite=verite)
    with pytest.raises(UsineErreur, match=motif) as erreur:
        charger_source_generateur(donnees, _ecrire_corpus(tmp_path / "textes.json"))
    assert "verite_terrain.json" in str(erreur.value)


@pytest.mark.parametrize(
    ("fichier", "contenu", "motif"),
    [
        ("verite_terrain.json", None, "vérité terrain illisible"),
        ("verite_terrain.json", '{"DEMO-1": "inconnue"}', "vérité terrain mal formée"),
        ("journal.jsonl", None, "Journal illisible"),
        ("journal.jsonl", "{}\n", "en-tête de Journal mal formé"),
    ],
)
def test_source_generateur_fichier_absent_ou_mal_forme(
    tmp_path: Path, fichier: str, contenu: str | None, motif: str
) -> None:
    donnees = _ecrire_donnees(tmp_path / "donnees")
    if contenu is None:
        (donnees / fichier).unlink()
    else:
        (donnees / fichier).write_text(contenu, encoding="utf-8")
    with pytest.raises(UsineErreur, match=motif) as erreur:
        charger_source_generateur(donnees, _ecrire_corpus(tmp_path / "textes.json"))
    assert fichier in str(erreur.value)


def test_rejeu_generateur_publie_f1_corpus_et_modele(
    source: SourceGenerateur, tmp_path: Path
) -> None:
    propositions = {"DEMO-1": R, "DEMO-2": T, "DEMO-3": R, "DEMO-5": R}
    resultat = executer_suite(
        tmp_path, generateur=source, reponses=_reponses(propositions), horloge=INSTANT
    )
    bloc = resultat["sources"]["generateur"]
    assert bloc["f1_macro"] == pytest.approx(evaluer(VERITE_MINI, propositions)["f1_macro"])
    assert bloc["propositions"] == {cle: cause.value for cle, cause in propositions.items()}
    assert bloc["modele_corpus"] == MODELE_CORPUS
    assert bloc["version_corpus"] == VERSION_CORPUS
    assert bloc["modele_classification"] == MODELE_CLASSIFICATION
    assert resultat["f1_macro"]["manuels"] is None
    assert resultat["sm9_atteint"] is None


def test_rejeu_toutes_sources_sm9(
    source: SourceGenerateur, tickets: tuple[TicketManuel, ...], tmp_path: Path
) -> None:
    resultat = executer_suite(
        tmp_path,
        manuels=tickets,
        generateur=source,
        reponses=_reponses(dict(VERITE_MINI)),
        horloge=INSTANT,
    )
    assert resultat["f1_macro"]["generateur"] == 1.0
    assert resultat["f1_macro"]["manuels"] >= 0.8
    assert resultat["sm9_atteint"] is True
    faible = executer_suite(
        tmp_path,
        manuels=tickets,
        generateur=source,
        reponses=_reponses(dict.fromkeys(VERITE_MINI, E)),
        horloge=INSTANT,
    )
    assert faible["sm9_atteint"] is False


def test_rejeu_generateur_sans_reponses(source: SourceGenerateur, tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match="--reponses"):
        executer_suite(tmp_path, generateur=source)


def test_rejeu_generateur_cle_sans_reponse(source: SourceGenerateur, tmp_path: Path) -> None:
    reponses = _reponses({"DEMO-1": R, "DEMO-2": T, "DEMO-5": R})
    with pytest.raises(UsineErreur, match="DEMO-3"):
        executer_suite(tmp_path, generateur=source, reponses=reponses)


def test_ad19_modele_enregistre_identique_au_corpus(
    source: SourceGenerateur, tmp_path: Path
) -> None:
    reponses = _reponses(dict(VERITE_MINI), modele=MODELE_CORPUS)
    with pytest.raises(UsineErreur, match="AD-19") as erreur:
        executer_suite(tmp_path, generateur=source, reponses=reponses)
    assert str(erreur.value).count(MODELE_CORPUS) == 2


class _FournisseurNomme(FournisseurEnregistre):
    @property
    def version_modele(self) -> str:
        return MODELE_CORPUS


def test_ad19_chemin_reel_refuse_avant_tout_appel(
    source: SourceGenerateur, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def factice(racine: Path, **_: Any) -> Classificateur:
        return construire_classificateur(
            racine, fournisseur=_FournisseurNomme("x", {}), pseudonymiseur=PseudonymiseurIdentite()
        )

    monkeypatch.setattr(module_suite, "construire_classificateur", factice)
    with pytest.raises(UsineErreur, match="AD-19"):
        executer_suite(tmp_path, generateur=source, reel=True)
    verifier_ad19(MODELE_CLASSIFICATION, MODELE_CORPUS)


# --- Résultats, historique, CLI ---


def test_resultat_relu_comme_reponses(source: SourceGenerateur, tmp_path: Path) -> None:
    resultat = executer_suite(
        tmp_path, generateur=source, reponses=_reponses(dict(VERITE_MINI)), horloge=INSTANT
    )
    chemin = ecrire_resultat(resultat, tmp_path / "resultats")
    assert chemin.name == "20261013T073000Z.json"
    relues = lire_reponses(chemin)
    assert dict(relues.propositions) == VERITE_MINI
    assert relues.modele_classification == MODELE_CLASSIFICATION
    entree = ajouter_historique(resultat, chemin, tmp_path / "historique.jsonl")
    lignes = (tmp_path / "historique.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lignes[-1]) == entree
    assert entree["modele_corpus"] == MODELE_CORPUS
    assert entree["resultat"] == chemin.name


def test_lire_reponses_sans_propositions(tmp_path: Path) -> None:
    chemin = tmp_path / "r.json"
    chemin.write_text('{"sources": {"manuels": {}}}', encoding="utf-8")
    with pytest.raises(UsineErreur, match=r"sources.generateur.propositions"):
        lire_reponses(chemin)


def test_fichiers_non_utf8_refuses_en_nommant_le_fichier(tmp_path: Path) -> None:
    reponses = tmp_path / "r.json"
    reponses.write_bytes(b"\xff\xfe{}")
    with pytest.raises(UsineErreur, match=r"r\.json : résultat non encodé en UTF-8"):
        lire_reponses(reponses)
    donnees = _ecrire_donnees(tmp_path / "donnees")
    (donnees / "journal.jsonl").write_bytes(b"\xff\xfe")
    with pytest.raises(UsineErreur, match=r"journal\.jsonl : Journal non encodé en UTF-8"):
        charger_source_generateur(donnees, _ecrire_corpus(tmp_path / "textes.json"))


def test_cli_rejeu_manuels_par_defaut(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sortie = tmp_path / "resultats"
    assert cli.main(["executer", "--sortie", str(sortie), "--racine", str(tmp_path)]) == 0
    (chemin,) = sortie.glob("*.json")
    resultat = json.loads(chemin.read_text(encoding="utf-8"))
    assert set(resultat["sources"]) == {"manuels"}
    assert "manuels : F1 macro" in capsys.readouterr().out


def test_cli_generateur_rejoue_un_resultat(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _ecrire_corpus(tmp_path / "donnees" / "corpus" / "textes.json")
    donnees = _ecrire_donnees(tmp_path / "jeu")
    sortie = tmp_path / "resultats"
    commun = ["--sortie", str(sortie), "--racine", str(tmp_path), "--donnees", str(donnees)]
    assert cli.main(["executer", "--source", "generateur", *commun]) == 1
    assert "--reponses" in capsys.readouterr().err
    anterieur = ecrire_resultat(
        executer_suite(
            tmp_path,
            generateur=charger_source_generateur(
                donnees, tmp_path / "donnees" / "corpus" / "textes.json"
            ),
            reponses=_reponses(dict(VERITE_MINI)),
            horloge=INSTANT,
        ),
        tmp_path / "anterieur",
    )
    assert cli.main(["executer", "--reponses", str(anterieur), *commun]) == 0
    (chemin,) = sortie.glob("*.json")
    resultat = json.loads(chemin.read_text(encoding="utf-8"))
    assert set(resultat["sources"]) == {"manuels", "generateur"}
    assert resultat["sm9_atteint"] is True
    assert resultat["sources"]["generateur"]["modele_classification"] == MODELE_CLASSIFICATION
