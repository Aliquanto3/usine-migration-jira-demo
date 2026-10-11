"""Racine de composition : seul lieu qui instancie les adaptateurs et câble les étapes (AD-1).

Elle lit `config/*.yaml` et les secrets (Mode repli), calcule `version_grille` et
`version_donnees`, instancie la `SourceJournal`, charge le gabarit PowerPoint et construit le
registre des étapes de la Chaîne selon le Palier.
"""

import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from types import MappingProxyType

from usine.adaptateurs.journal import SourceJournal
from usine.chaine.ecrivain import EcrivainPassage
from usine.chaine.etapes import EtapeBouchon, EtapeInstantanes, EtapeMeteo, EtapeSautee
from usine.chaine.execution import DonneesPassage, executer_passage
from usine.chaine.verrou import verrou_exclusif
from usine.config import Secrets, charger_yaml
from usine.consultation.passage import ConsultationPassage
from usine.contrats.calendrier import est_jour_ouvre
from usine.contrats.config import (
    ConfigChaine,
    ConfigJira,
    ConfigProgramme,
    ConfigUsine,
    GrilleMeteo,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import Etape, ManifestePassage
from usine.contrats.versions import version_donnees, version_grille
from usine.generateur.journal import generer, serialiser_journal
from usine.ports.consultation import Consultation
from usine.ports.etape import Etape as PortEtape
from usine.rendu.etape import EtapeRendu

CHEMIN_JOURNAL = Path("donnees") / "journal.jsonl"
"""Journal lu par la Chaîne, relatif à la racine (écrit par `usine donnees generer`)."""

CHEMIN_VERROU = Path("donnees") / ".verrou-passage"
"""Verrou exclusif d'un Passage, relatif à la racine."""

CHEMIN_GABARIT = Path("gabarits") / "rapport.pptx"
"""Gabarit neutre du PowerPoint, relatif à la racine."""

REPERTOIRE_SORTIES = Path("sorties")
"""Racine des sorties (Passages, échecs, progression), relative à la racine."""

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
            racine_passages=self.racine_sorties / "passages",
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


def construire_rapport(racine: Path) -> Rapport:
    """Charge la configuration et le Journal de `racine`, puis construit le registre."""
    repertoire_config = racine / "config"
    chaine = charger_yaml(repertoire_config / "chaine.yaml", ConfigChaine)
    programme = charger_yaml(repertoire_config / "programme.yaml", ConfigProgramme)
    chemin_grille = repertoire_config / "grille_meteo.yaml"
    grille = charger_yaml(chemin_grille, GrilleMeteo)
    chemin_jira = repertoire_config / "jira.yaml"
    jira = charger_yaml(chemin_jira, ConfigJira) if chemin_jira.exists() else None
    configuration = ConfigUsine(chaine=chaine, programme=programme, grille_meteo=grille, jira=jira)
    mode_repli = Secrets(_env_file=racine / ".env").usine_mode_repli
    gabarit = _octets(racine / CHEMIN_GABARIT, "gabarit PowerPoint")
    empreinte_grille = version_grille(_octets(chemin_grille, "Grille de météo"))

    chemin_journal = racine / CHEMIN_JOURNAL
    source = SourceJournal(chemin_journal)
    empreinte_donnees = version_donnees(_octets(chemin_journal, "Journal"), None)
    premier_jour = source.entete.ancrage_semaines
    entites = [entite.code for entite in programme.entites]

    llm: PortEtape = EtapeSautee() if chaine.palier == 1 else EtapeBouchon()
    registre: dict[Etape, PortEtape] = {
        Etape.extraction: EtapeBouchon(),
        Etape.instantanes: EtapeInstantanes(source, premier_jour),
        Etape.kpi: EtapeBouchon(),
        Etape.meteo: EtapeMeteo(grille, empreinte_grille, entites, premier_jour),
        Etape.prevision: EtapeBouchon(),
        Etape.rendu: EtapeRendu(gabarit),
    }
    registre.update({etape: llm for etape in ETAPES_LLM})
    return Rapport(
        configuration=configuration,
        registre=MappingProxyType({etape: registre[etape] for etape in Etape}),
        donnees=DonneesPassage("journal", empreinte_grille, empreinte_donnees),
        racine_sorties=racine / REPERTOIRE_SORTIES,
        chemin_verrou=racine / CHEMIN_VERROU,
        url_jira=None if mode_repli or jira is None else jira.url_site,
    )


def _maintenant() -> datetime:
    return datetime.now(UTC)


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
) -> PassageLance:
    """Prend le verrou, construit le rapport et exécute un Passage ; verrou toujours rendu."""
    verifier_date_arrete(date_arrete)
    with verrou_exclusif(racine / CHEMIN_VERROU):
        rapport = construire_rapport(racine)
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
    """Génère le Journal de `programme` dans `racine/donnees/journal.jsonl` (outils, NFR-2)."""
    chemin = racine / CHEMIN_JOURNAL
    generation = generer(programme, graine, date_generation)
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(serialiser_journal(generation))
    except OSError as exc:
        raise UsineErreur(f"{chemin} : écriture impossible ({exc.strerror or exc})") from exc
    return chemin
