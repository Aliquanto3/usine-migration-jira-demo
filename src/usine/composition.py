"""Racine de composition : seul lieu qui instancie les adaptateurs et câble les étapes (AD-1).

Elle lit `config/*.yaml` et les secrets (Mode repli), calcule `version_grille` et
`version_donnees`, instancie la `SourceJournal`, charge le gabarit PowerPoint et construit le
registre des étapes de la Chaîne selon le Palier. En Palier 2, elle câble la passerelle LLM
(fournisseur injecté, cache `donnees/cache_llm.sqlite`) dans l'étape `explications` ; les
autres étapes LLM restent sautées. Sans pseudonymiseur injecté, elle construit
`PseudonymiseurHmac` sur la clé `USINE_CLE_PSEUDO`, les motifs de
`config/pseudonymisation.yaml` (ou `MOTIFS_PAR_DEFAUT`) et la table
`donnees/pseudonymes.sqlite`. Les secrets passent par `charger_secrets` (erreur nommant la
variable) ; l'URL Jira se résout dans `url_jira` seulement. Les services de l'UI vivent dans
`ui/cli.py`, l'écriture du Journal dans `generateur.journal.ecrire_journal`.
"""

import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from types import MappingProxyType

from usine.adaptateurs.journal import SourceJournal
from usine.adaptateurs.pseudonymisation import (
    MOTIFS_PAR_DEFAUT,
    PseudonymiseurHmac,
    verifier_cle,
)
from usine.adaptateurs.stockage_sqlite import CacheLLMSqlite, TablePseudonymesSqlite
from usine.chaine.ecrivain import EcrivainPassage
from usine.chaine.etapes import EtapeBouchon, EtapeInstantanes, EtapeMeteo, EtapeSautee
from usine.chaine.execution import executer_passage
from usine.chaine.verrou import verrou_exclusif
from usine.config import Secrets, charger_secrets, charger_yaml
from usine.consultation.passage import ConsultationPassage
from usine.contrats.calendrier import est_jour_ouvre
from usine.contrats.config import (
    ConfigChaine,
    ConfigJira,
    ConfigProgramme,
    ConfigPseudonymisation,
    ConfigUsine,
    GrilleMeteo,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import (
    CHEMIN_CACHE_LLM,
    CHEMIN_JOURNAL,
    CHEMIN_PSEUDONYMES,
    CHEMIN_VERROU,
    REPERTOIRE_SORTIES,
    SOUS_REPERTOIRE_PASSAGES,
    DonneesPassage,
    Etape,
    ManifestePassage,
)
from usine.contrats.versions import version_donnees, version_grille
from usine.domaine.meteo import verifier_grille
from usine.generateur.corpus import (
    VERSION_CORPUS_LLM,
    VERSION_CORPUS_PROVISOIRE,
    ecrire_corpus,
    produire_corpus,
)
from usine.generateur.journal import ecrire_journal, generer
from usine.generateur.textes import corpus_provisoire
from usine.ia.etape import EtapeExplications
from usine.ia.passerelle import Passerelle
from usine.ports.consultation import Consultation
from usine.ports.etape import Etape as PortEtape
from usine.ports.fournisseur_llm import FournisseurLLM
from usine.ports.pseudonymiseur import Pseudonymiseur
from usine.rendu.etape import EtapeRendu

CHEMIN_GABARIT = Path("gabarits") / "rapport.pptx"
"""Gabarit neutre du PowerPoint, relatif à la racine."""

ETAPES_LLM = frozenset(
    {Etape.classification, Etape.repartition_causes, Etape.explications, Etape.narration}
)
"""Étapes de la couche LLM, sautées en Palier 1."""


@dataclass(frozen=True)
class Rapport:
    """Tout ce qu'il faut pour exécuter un Passage : configuration, registre, données."""

    configuration: ConfigUsine
    registre: Mapping[Etape, PortEtape]
    donnees: DonneesPassage
    racine_sorties: Path
    chemin_verrou: Path
    url_jira: str | None = None
    """URL du site Jira pour `url_ticket` ; `None` en Mode repli ou sans `config/jira.yaml`."""

    def fabrique_consultation(self, date_arrete: date) -> Callable[[Path], Consultation]:
        """Fabrique de la `Consultation` d'un Passage de ce rapport à la Date d'arrêté."""
        return partial(
            ConsultationPassage,
            racine_passages=self.racine_sorties / SOUS_REPERTOIRE_PASSAGES,
            url_jira=self.url_jira,
            date_arrete=date_arrete,
        )


def _octets(chemin: Path, quoi: str) -> bytes:
    try:
        return chemin.read_bytes()
    except FileNotFoundError as exc:
        raise UsineErreur(f"{chemin} : {quoi} introuvable") from exc
    except OSError as exc:
        raise UsineErreur(f"{chemin} : {quoi} illisible ({exc.strerror or exc})") from exc


def _maintenant() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class _ParametresPseudonymisation:
    """Clé et motifs de `PseudonymiseurHmac`, vérifiés avant tout Passage."""

    cle: bytes
    motifs: Mapping[str, str]


def _motifs_pseudonymisation(repertoire_config: Path) -> Mapping[str, str]:
    """Motifs de `config/pseudonymisation.yaml` s'il existe, sinon `MOTIFS_PAR_DEFAUT`.

    Plusieurs reconnaisseurs d'un même type de jeton sont combinés en une alternative.
    """
    chemin = repertoire_config / "pseudonymisation.yaml"
    if not chemin.exists():
        return MOTIFS_PAR_DEFAUT
    config = charger_yaml(chemin, ConfigPseudonymisation)
    if not config.reconnaisseurs:
        raise UsineErreur(
            f"{chemin}, clé « reconnaisseurs », valeur vide : aucun motif de Pseudonymisation ;"
            " déclarer au moins un reconnaisseur ou supprimer le fichier"
        )
    par_type: dict[str, list[str]] = {}
    for reconnaisseur in config.reconnaisseurs:
        par_type.setdefault(reconnaisseur.type_jeton, []).append(reconnaisseur.motif)
    return {
        type_jeton: motifs[0] if len(motifs) == 1 else "|".join(f"(?:{m})" for m in motifs)
        for type_jeton, motifs in par_type.items()
    }


def _verifier_llm(
    fournisseur: FournisseurLLM | None,
    pseudonymiseur: Pseudonymiseur | None,
    secrets_usine: Secrets,
    repertoire_config: Path,
) -> _ParametresPseudonymisation | None:
    """Palier 2 : refuse, avant tout Passage, l'absence de fournisseur LLM ou de clé.

    Sans pseudonymiseur injecté, renvoie la clé `USINE_CLE_PSEUDO` et les motifs de
    `PseudonymiseurHmac` ; sinon `None`.
    """
    if fournisseur is None:
        raise UsineErreur(
            "config/chaine.yaml, clé « palier », valeur 2 : aucun fournisseur LLM injecté ;"
            " repasser en palier 1 ou fournir un fournisseur LLM"
        )
    if pseudonymiseur is not None:
        return None
    cle = secrets_usine.usine_cle_pseudo
    if cle is None or not cle.get_secret_value().strip():
        raise UsineErreur(
            "config/chaine.yaml, clé « palier », valeur 2 : variable d'environnement"
            " USINE_CLE_PSEUDO absente ou vide ; aucun appel LLM sans Pseudonymisation"
        )
    octets_cle = cle.get_secret_value().encode("utf-8")
    verifier_cle(octets_cle)
    return _ParametresPseudonymisation(octets_cle, _motifs_pseudonymisation(repertoire_config))


def _config_jira(racine: Path) -> ConfigJira | None:
    """`config/jira.yaml` validé, ou `None` s'il n'existe pas."""
    chemin = racine / "config" / "jira.yaml"
    return charger_yaml(chemin, ConfigJira) if chemin.exists() else None


def url_jira(racine: Path) -> str | None:
    """URL du site Jira pour `url_ticket` (AD-11), seule résolution du dépôt.

    `None` en Mode repli (`USINE_MODE_REPLI`, environnement ou `racine/.env`) ou sans
    `config/jira.yaml`.
    """
    if charger_secrets(racine).usine_mode_repli:
        return None
    return _url_jira(False, _config_jira(racine))


def _url_jira(mode_repli: bool, jira: ConfigJira | None) -> str | None:
    """URL Jira déduite de valeurs déjà chargées : `None` en Mode repli ou sans configuration."""
    return None if mode_repli or jira is None else jira.url_site


def construire_rapport(
    racine: Path,
    fournisseur: FournisseurLLM | None = None,
    pseudonymiseur: Pseudonymiseur | None = None,
    horloge: Callable[[], datetime] = _maintenant,
) -> Rapport:
    """Charge la configuration et le Journal de `racine`, puis construit le registre.

    En Palier 2, `fournisseur` est obligatoire ; sans `pseudonymiseur`, `PseudonymiseurHmac`
    est construit et exige `USINE_CLE_PSEUDO`. Toute absence lève une `UsineErreur` avant tout
    Passage. `horloge` date les traces LLM.
    """
    repertoire_config = racine / "config"
    chaine = charger_yaml(repertoire_config / "chaine.yaml", ConfigChaine)
    secrets_usine = charger_secrets(racine)
    pseudonymisation = (
        _verifier_llm(fournisseur, pseudonymiseur, secrets_usine, repertoire_config)
        if chaine.palier == 2
        else None
    )
    programme = charger_yaml(repertoire_config / "programme.yaml", ConfigProgramme)
    chemin_grille = repertoire_config / "grille_meteo.yaml"
    grille = verifier_grille(charger_yaml(chemin_grille, GrilleMeteo), str(chemin_grille))
    jira = _config_jira(racine)
    configuration = ConfigUsine(chaine=chaine, programme=programme, grille_meteo=grille, jira=jira)
    gabarit = _octets(racine / CHEMIN_GABARIT, "gabarit PowerPoint")
    empreinte_grille = version_grille(_octets(chemin_grille, "Grille de météo"))

    chemin_journal = racine / CHEMIN_JOURNAL
    source = SourceJournal(chemin_journal)
    empreinte_donnees = version_donnees(_octets(chemin_journal, "Journal"), None)
    premier_jour = source.entete.ancrage_semaines
    entites = [entite.code for entite in programme.entites]

    registre: dict[Etape, PortEtape] = {
        Etape.extraction: EtapeBouchon(),
        Etape.instantanes: EtapeInstantanes(source, premier_jour),
        Etape.kpi: EtapeBouchon(),
        Etape.meteo: EtapeMeteo(grille, empreinte_grille, entites, premier_jour, programme),
        Etape.prevision: EtapeBouchon(),
        Etape.rendu: EtapeRendu(gabarit),
    }
    registre.update({etape: EtapeSautee() for etape in ETAPES_LLM})
    if chaine.palier == 2:
        if fournisseur is None:  # pragma: no cover - vérifié par `_verifier_llm`
            raise UsineErreur("Palier 2 sans fournisseur LLM")
        if pseudonymiseur is None:
            if pseudonymisation is None:  # pragma: no cover - vérifié par `_verifier_llm`
                raise UsineErreur("Palier 2 sans USINE_CLE_PSEUDO")
            pseudonymiseur = PseudonymiseurHmac(
                pseudonymisation.cle,
                pseudonymisation.motifs,
                TablePseudonymesSqlite(racine / CHEMIN_PSEUDONYMES),
            )
        passerelle = Passerelle(
            fournisseur, pseudonymiseur, CacheLLMSqlite(racine / CHEMIN_CACHE_LLM), horloge
        )
        registre[Etape.explications] = EtapeExplications(passerelle, empreinte_donnees)
    return Rapport(
        configuration=configuration,
        registre=MappingProxyType({etape: registre[etape] for etape in Etape}),
        donnees=DonneesPassage("journal", empreinte_grille, empreinte_donnees),
        racine_sorties=racine / REPERTOIRE_SORTIES,
        chemin_verrou=racine / CHEMIN_VERROU,
        url_jira=_url_jira(secrets_usine.usine_mode_repli, jira),
    )


def _suffixe() -> str:
    return secrets.token_hex(3)


@dataclass(frozen=True)
class PassageLance:
    """Résultat de `lancer_rapport` : manifeste et répertoire publié."""

    manifeste: ManifestePassage
    repertoire: Path


def verifier_date_arrete(jour: date) -> date:
    """Renvoie `jour` s'il est un Jour ouvré ; sinon lève une `UsineErreur` qui le nomme."""
    if not est_jour_ouvre(jour):
        raise UsineErreur(
            f"Date d'arrêté {jour.isoformat()} : ce n'est pas un Jour ouvré (lundi à vendredi)"
        )
    return jour


def lancer_rapport(
    racine: Path,
    date_arrete: date,
    horloge: Callable[[], datetime] = _maintenant,
    alea: Callable[[], str] = _suffixe,
    fournisseur: FournisseurLLM | None = None,
    pseudonymiseur: Pseudonymiseur | None = None,
) -> PassageLance:
    """Prend le verrou, construit le rapport et exécute un Passage ; verrou toujours rendu."""
    verifier_date_arrete(date_arrete)
    with verrou_exclusif(racine / CHEMIN_VERROU):
        rapport = construire_rapport(racine, fournisseur, pseudonymiseur, horloge)
        ecrivain = EcrivainPassage(rapport.racine_sorties, horloge)
        manifeste = executer_passage(
            rapport.registre,
            rapport.configuration,
            date_arrete,
            ecrivain,
            rapport.fabrique_consultation(date_arrete),
            horloge,
            alea,
            rapport.donnees,
        )
    repertoire = ecrivain.repertoire_publie
    if repertoire is None:  # pragma: no cover - executer_passage publie ou lève
        raise UsineErreur(f"Passage {manifeste.passage_id} non publié")
    return PassageLance(manifeste, repertoire)


def generer_journal(
    programme: ConfigProgramme, graine: int, date_generation: date, racine: Path
) -> Path:
    """Génère le Journal de `programme` sous `racine/donnees/` et renvoie son chemin.

    Délègue à `generateur.journal.ecrire_journal` (Journal et vérité terrain) ; sert à
    `outils/`, qui ne peut pas importer `generateur` (NFR-2). Les textes viennent du Corpus
    provisoire en mémoire (défaut de `generer`), non de `donnees/corpus/textes.json` : quand la
    Story 1.9 versionnera un Corpus produit par LLM, il faudra charger ici le Corpus versionné.
    """
    generation = generer(programme, graine, date_generation)
    return ecrire_journal(generation, racine / CHEMIN_JOURNAL.parent)


def generer_corpus(
    fournisseur: FournisseurLLM | None,
    domaines: Sequence[str],
    chemin: Path,
    *,
    version_corpus: str | None = None,
) -> Path:
    """Écrit le Corpus de textes des `domaines` à `chemin` et renvoie ce chemin (Story 1.2).

    Sans fournisseur : Corpus provisoire par gabarits (`gabarits-provisoires`). Avec : Corpus
    produit par `FournisseurLLM.generer_structure` seulement (AD-24). Délègue à
    `generateur.corpus`, seul propriétaire du format ; sert à `outils/`, qui ne peut pas
    importer `generateur`.
    """
    if fournisseur is None:
        corpus = corpus_provisoire(
            domaines, version_corpus=version_corpus or VERSION_CORPUS_PROVISOIRE
        )
    else:
        corpus = produire_corpus(
            fournisseur, domaines, version_corpus=version_corpus or VERSION_CORPUS_LLM
        )
    return ecrire_corpus(corpus, chemin)
