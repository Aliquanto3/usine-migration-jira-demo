"""Passerelle LLM : ordre d'AD-12, jetons stables, cache, trace (Story 0.7), coût et
plafond (Story 6.3)."""

import re
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import cast

import pytest
from pydantic import BaseModel

from tests.doublures.fournisseur_factice import FournisseurFactice
from tests.unit.ia.espions import (
    DATE_ARRETE,
    NUMERO_COMPTE,
    PASSAGE_ID,
    CacheMemoire,
    EspionFournisseur,
    EspionPseudonymiseur,
    fusionner_reidentifier,
    horloge_espion,
    jeton_compte,
    pseudonymiseur,
)
from usine.contrats.llm import (
    ParametresAppel,
    ReponseExplication,
    ReponseStructuree,
    SortieExplication,
    StatutControle,
    Tache,
)
from usine.contrats.trace import TypeTrace
from usine.ia.passerelle import (
    ContexteAppel,
    Controle,
    Passerelle,
    PlafondCoutAtteint,
    ResultatAppel,
    cle_cache,
)
from usine.ports.fournisseur_llm import FournisseurLLM

PROMPT = f"Explique ENT-A. DEMO-3 : virement refusé sur le compte {NUMERO_COMPTE}."
CONTEXTE = ContexteAppel(
    passage_id=PASSAGE_ID,
    date_arrete=DATE_ARRETE,
    cible="ENT-A",
    version_prompt="p" * 64,
    version_grille="grille123456",
    version_donnees="d" * 64,
    entite="ENT-A",
)
PARAMETRES = ParametresAppel(tache=Tache.explication, max_jetons_sortie=256)


def _reponse() -> ReponseExplication:
    return ReponseExplication(
        texte=f"DEMO-3 bloque le compte {jeton_compte()}.",
        brouillon_commentaire=f"Vérifier {jeton_compte()} (DEMO-3).",
    )


class Controleur:
    """Contrôle trivial, conforme, qui journalise son passage."""

    def __init__(self, journal: list[str]) -> None:
        self.journal = journal
        self.recus: list[ReponseExplication] = []

    def __call__(self, reponse: ReponseExplication) -> Controle[SortieExplication]:
        self.journal.append("controle")
        self.recus.append(reponse)
        sortie = SortieExplication(
            date_arrete=DATE_ARRETE,
            entite="ENT-A",
            texte=reponse.texte,
            citations=("DEMO-3",),
            brouillon_commentaire=reponse.brouillon_commentaire,
            statut_controle=StatutControle.conforme,
        )
        return Controle(sortie, StatutControle.conforme)


def _appeler(
    passerelle: Passerelle, journal: list[str]
) -> tuple[ResultatAppel[SortieExplication], Controleur]:
    controleur = Controleur(journal)
    resultat = passerelle.executer_structure(
        PROMPT, ReponseExplication, PARAMETRES, CONTEXTE, controleur
    )
    return resultat, controleur


def test_ordre_impose() -> None:
    journal: list[str] = []
    factice = FournisseurFactice([_reponse()])
    passerelle = Passerelle(
        EspionFournisseur(factice, journal),
        EspionPseudonymiseur(pseudonymiseur(), journal),
        CacheMemoire(journal),
        horloge_espion(journal),
    )
    resultat, controleur = _appeler(passerelle, journal)
    assert fusionner_reidentifier(journal) == [
        "pseudonymiser",
        "cache.lire",
        "fournisseur",
        "cache.ecrire",
        "controle",
        "reidentifier",
        "trace",
    ]
    (appel,) = factice.appels
    assert isinstance(appel.entree, str)
    assert NUMERO_COMPTE not in appel.entree
    assert re.search(r"\bCOMPTE_[0-9a-f]{6}\b", appel.entree)
    assert jeton_compte() in appel.entree
    assert "DEMO-3" in appel.entree  # clé de ticket jamais pseudonymisée
    assert NUMERO_COMPTE not in controleur.recus[0].texte  # contrôle avant ré-identification
    assert resultat.sortie.texte == f"DEMO-3 bloque le compte {NUMERO_COMPTE}."
    assert NUMERO_COMPTE in resultat.sortie.brouillon_commentaire
    assert resultat.sortie.date_arrete == DATE_ARRETE


def test_jeton_stable_entre_deux_passerelles() -> None:
    entrees: list[object] = []
    for _ in range(2):
        factice = FournisseurFactice([_reponse()])
        passerelle = Passerelle(factice, pseudonymiseur(), CacheMemoire(), horloge_espion([]))
        _appeler(passerelle, [])
        (appel,) = factice.appels
        entrees.append(appel.entree)
    assert entrees[0] == entrees[1]
    assert jeton_compte() in str(entrees[0])


def test_cache() -> None:
    factice = FournisseurFactice([_reponse()])
    cache = CacheMemoire()
    passerelle = Passerelle(factice, pseudonymiseur(), cache, horloge_espion([]))
    premier, _ = _appeler(passerelle, [])
    journal: list[str] = []
    second, controleur = _appeler(passerelle, journal)
    assert len(factice.appels) == 1
    assert journal == ["controle"]
    assert len(cache.valeurs) == 1
    assert not premier.trace.depuis_cache
    assert premier.trace.jetons_entree > 0
    assert second.trace.depuis_cache
    assert (second.trace.jetons_entree, second.trace.jetons_sortie) == (0, 0)
    assert second.sortie == premier.sortie
    assert controleur.recus  # contrôle refait sur la réponse en cache


def test_fournisseur_par_tache() -> None:
    """Story 6.5 : la tâche routée passe par son fournisseur (clé de cache, trace, appel) ;
    les autres tâches restent au fournisseur par défaut."""
    defaut = FournisseurFactice([_reponse()], version_modele="anthropic:claude-sonnet-5-5")
    dedie = FournisseurFactice([_reponse()], version_modele="anthropic:claude-haiku-5-5")
    cache = CacheMemoire()
    passerelle = Passerelle(
        defaut,
        pseudonymiseur(),
        cache,
        horloge_espion([]),
        fournisseurs_par_tache={Tache.classification: dedie},
    )
    classification = PARAMETRES.model_copy(update={"tache": Tache.classification})
    routee = passerelle.executer_structure(
        PROMPT, ReponseExplication, classification, CONTEXTE, Controleur([])
    )
    assert (len(dedie.appels), len(defaut.appels)) == (1, 0)
    assert routee.trace.version_modele == "anthropic:claude-haiku-5-5"
    entree = pseudonymiseur().apercu(PROMPT)
    assert cle_cache(classification, CONTEXTE, "anthropic:claude-haiku-5-5", entree) in (
        cache.valeurs
    )
    explication, _ = _appeler(passerelle, [])
    assert (len(dedie.appels), len(defaut.appels)) == (1, 1)
    assert explication.trace.version_modele == "anthropic:claude-sonnet-5-5"


def test_cache_illisible_rappelle_le_fournisseur() -> None:
    factice = FournisseurFactice([_reponse()])
    cache = CacheMemoire()
    passerelle = Passerelle(factice, pseudonymiseur(), cache, horloge_espion([]))
    cle = cle_cache(PARAMETRES, CONTEXTE, factice.version_modele, pseudonymiseur().apercu(PROMPT))
    cache.valeurs[cle] = "{pas du json"
    resultat, _ = _appeler(passerelle, [])
    assert len(factice.appels) == 1
    assert not resultat.trace.depuis_cache
    assert cache.valeurs[cle] != "{pas du json"


def test_cle_de_cache() -> None:
    entree = pseudonymiseur().apercu(PROMPT)
    cle = cle_cache(PARAMETRES, CONTEXTE, "factice:modele", entree)
    assert NUMERO_COMPTE not in cle
    autre_tentative = PARAMETRES.model_copy(update={"tentative": 1})
    assert cle_cache(autre_tentative, CONTEXTE, "factice:modele", entree) != cle
    autres_donnees = replace(CONTEXTE, version_donnees="e" * 64)
    assert cle_cache(PARAMETRES, autres_donnees, "factice:modele", entree) == cle
    assert cle_cache(PARAMETRES, CONTEXTE, "autre:modele", entree) != cle
    assert cle_cache(PARAMETRES, CONTEXTE, "factice:modele", entree + " ") != cle


def test_trace() -> None:
    factice = FournisseurFactice([_reponse()], version_modele="factice:modele-1")
    passerelle = Passerelle(factice, pseudonymiseur(), CacheMemoire(), horloge_espion([]))
    resultat, _ = _appeler(passerelle, [])
    trace = resultat.trace
    assert trace.type_trace is TypeTrace.llm
    assert trace.passage_id == PASSAGE_ID
    assert trace.date_arrete == DATE_ARRETE
    assert (trace.entite, trace.cible, trace.tache) == ("ENT-A", "ENT-A", Tache.explication)
    assert trace.fournisseur == "factice"
    assert trace.version_prompt == CONTEXTE.version_prompt
    assert trace.version_modele == "factice:modele-1"
    assert trace.version_grille == CONTEXTE.version_grille
    assert trace.version_donnees == CONTEXTE.version_donnees
    assert trace.statut_controle is StatutControle.conforme
    assert trace.phrases_retirees == 0
    assert jeton_compte() in trace.entree_pseudonymisee
    assert jeton_compte() in trace.sortie
    assert NUMERO_COMPTE not in trace.model_dump_json()


class FournisseurAutreModele:
    """Fournisseur configuré sur un modèle, dont la réponse annonce un autre modèle."""

    def __init__(self, factice: FournisseurFactice) -> None:
        self.factice = factice

    @property
    def version_modele(self) -> str:
        return "factice:modele-configure"

    def generer_structure[T: BaseModel](
        self, prompt: str, schema: type[T], parametres: ParametresAppel
    ) -> ReponseStructuree[T]:
        reponse = self.factice.generer_structure(prompt, schema, parametres)
        return reponse.model_copy(update={"version_modele": "repli:modele-effectif"})


def test_trace_porte_le_modele_de_la_reponse() -> None:
    cache = CacheMemoire()
    fournisseur = FournisseurAutreModele(FournisseurFactice([_reponse()]))
    passerelle = Passerelle(
        cast(FournisseurLLM, fournisseur), pseudonymiseur(), cache, horloge_espion([])
    )
    premier, _ = _appeler(passerelle, [])
    assert premier.trace.version_modele == "repli:modele-effectif"
    assert premier.trace.fournisseur == "repli"
    (cle,) = cache.valeurs
    assert '"version_modele":"factice:modele-configure"' in cle  # clé : modèle connu avant
    second, _ = _appeler(passerelle, [])
    assert second.trace.depuis_cache
    assert second.trace.version_modele == "repli:modele-effectif"
    assert second.trace.fournisseur == "repli"


def test_jeton_hors_entree_non_reidentifie() -> None:
    pseudo = pseudonymiseur()
    autre_compte = "FR76 1111 2222 3333 4444 5555 666"
    autre_jeton = pseudo.pseudonymiser(autre_compte)  # autre enregistrement, autre appel
    reponse = ReponseExplication(texte=f"DEMO-3 bloque {jeton_compte()} et {autre_jeton}.")
    factice = FournisseurFactice([reponse])
    passerelle = Passerelle(factice, pseudo, CacheMemoire(), horloge_espion([]))
    resultat, _ = _appeler(passerelle, [])
    assert resultat.sortie.texte == f"DEMO-3 bloque {NUMERO_COMPTE} et {autre_jeton}."
    assert autre_compte not in resultat.sortie.model_dump_json()


def _tarif_fixe(version_modele: str, jetons_entree: int, jetons_sortie: int) -> Decimal:
    """1 € par million de jetons d'entrée, 5 € par million de jetons de sortie."""
    return (Decimal(jetons_entree) + 5 * Decimal(jetons_sortie)) / 1_000_000


def test_cle_de_cache_classification_sans_date_arrete() -> None:
    """Une classification garde sa clé d'une Date d'arrêté à l'autre ; pas une explication."""
    entree = pseudonymiseur().apercu(PROMPT)
    lendemain = replace(CONTEXTE, date_arrete=DATE_ARRETE + timedelta(days=1))
    classification = ParametresAppel(tache=Tache.classification, max_jetons_sortie=256)
    assert cle_cache(classification, CONTEXTE, "f:m", entree) == cle_cache(
        classification, lendemain, "f:m", entree
    )
    assert "date_arrete" not in cle_cache(classification, CONTEXTE, "f:m", entree)
    assert cle_cache(PARAMETRES, CONTEXTE, "f:m", entree) != cle_cache(
        PARAMETRES, lendemain, "f:m", entree
    )


def test_cout_trace_et_cumule_un_succes_en_cache_coute_zero() -> None:
    factice = FournisseurFactice([_reponse()])
    recus: list[tuple[str, int, int]] = []

    def tarif(version_modele: str, jetons_entree: int, jetons_sortie: int) -> Decimal:
        recus.append((version_modele, jetons_entree, jetons_sortie))
        return _tarif_fixe(version_modele, jetons_entree, jetons_sortie)

    passerelle = Passerelle(
        factice, pseudonymiseur(), CacheMemoire(), horloge_espion([]), tarif=tarif
    )
    premier, _ = _appeler(passerelle, [])
    second, _ = _appeler(passerelle, [])
    trace = premier.trace
    assert recus == [("factice:modele", trace.jetons_entree, trace.jetons_sortie)]
    attendu = _tarif_fixe("", trace.jetons_entree, trace.jetons_sortie)
    assert trace.cout_estime_eur == attendu > 0
    assert second.trace.depuis_cache
    assert second.trace.cout_estime_eur == 0
    assert passerelle.cout_cumule_eur(PASSAGE_ID) == attendu
    assert passerelle.cout_cumule_eur("autre-passage") == 0


def test_sans_tarif_cout_nul() -> None:
    passerelle = Passerelle(
        FournisseurFactice([_reponse()]), pseudonymiseur(), CacheMemoire(), horloge_espion([])
    )
    resultat, _ = _appeler(passerelle, [])
    assert resultat.trace.cout_estime_eur == 0


def test_plafond_nul_aucun_appel() -> None:
    factice = FournisseurFactice([_reponse()])
    passerelle = Passerelle(
        factice,
        pseudonymiseur(),
        CacheMemoire(),
        horloge_espion([]),
        tarif=_tarif_fixe,
        plafond_cout_passage_eur=Decimal(0),
    )
    with pytest.raises(PlafondCoutAtteint, match="plafond_cout_passage_eur"):
        _appeler(passerelle, [])
    assert factice.appels == []


def test_l_appel_qui_franchit_le_plafond_passe_les_suivants_non() -> None:
    factice = FournisseurFactice([_reponse(), _reponse(), _reponse()])
    passerelle = Passerelle(
        factice,
        pseudonymiseur(),
        CacheMemoire(),
        horloge_espion([]),
        tarif=lambda *_: Decimal("0.6"),
        plafond_cout_passage_eur=Decimal(1),
    )
    _appeler(passerelle, [])
    autre_tentative = PARAMETRES.model_copy(update={"tentative": 1})
    passerelle.executer_structure(
        PROMPT, ReponseExplication, autre_tentative, CONTEXTE, Controleur([])
    )  # 0,6 € < 1 € : passe, et franchit le plafond (1,2 €)
    assert passerelle.cout_cumule_eur(PASSAGE_ID) == Decimal("1.2")
    autre_cible = replace(CONTEXTE, cible="ENT-B")
    with pytest.raises(PlafondCoutAtteint):
        passerelle.executer_structure(
            PROMPT, ReponseExplication, PARAMETRES, autre_cible, Controleur([])
        )
    assert len(factice.appels) == 2
    # Un autre Passage a son propre cumul.
    autre_passage = replace(CONTEXTE, passage_id="20261012T073000Z-bbbbbb", cible="ENT-B")
    passerelle.executer_structure(
        PROMPT, ReponseExplication, PARAMETRES, autre_passage, Controleur([])
    )
    assert len(factice.appels) == 3


def test_plafond_atteint_le_cache_reste_servi() -> None:
    cache = CacheMemoire()
    premier = Passerelle(
        FournisseurFactice([_reponse()]), pseudonymiseur(), cache, horloge_espion([])
    )
    _appeler(premier, [])
    factice = FournisseurFactice()
    plafonnee = Passerelle(
        factice,
        pseudonymiseur(),
        cache,
        horloge_espion([]),
        tarif=_tarif_fixe,
        plafond_cout_passage_eur=Decimal(0),
    )
    resultat, _ = _appeler(plafonnee, [])
    assert resultat.trace.depuis_cache
    assert resultat.trace.cout_estime_eur == 0
    assert factice.appels == []
