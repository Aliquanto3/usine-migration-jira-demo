"""Racine de composition : seul lieu qui instancie les adaptateurs et câble les étapes (AD-1).

Elle lit `config/*.yaml` et les secrets (Mode repli), calcule `version_grille` et
`version_donnees`, instancie la `SourceJournal` (avec le manifeste d'injection
`donnees/injection/manifeste_injection.json` s'il existe, pour lire le Journal aux clés Jira ;
sinon aux clés générées), charge le gabarit PowerPoint et construit le
registre des étapes de la Chaîne selon le Palier. En Palier 2, elle câble la passerelle LLM
(fournisseur injecté, cache `donnees/cache_llm.sqlite`) dans l'étape `explications` ; les
autres étapes LLM restent sautées. Sans pseudonymiseur injecté, elle construit le moteur de
la clé `moteur` de `config/pseudonymisation.yaml` (AD-15) sur la clé `USINE_CLE_PSEUDO` et la
table `donnees/pseudonymes.sqlite` : `PseudonymiseurPresidio` (`presidio`, défaut) ou
`PseudonymiseurHmac` sur les motifs des reconnaisseurs (`regex`) ; sans ce fichier,
`PseudonymiseurHmac` sur `MOTIFS_PAR_DEFAUT`. La passerelle reçoit le plafond de coût de
`config/llm.yaml` (s'il existe) et le tarif du registre des prix (0 € pour un modèle absent du
registre, comme une doublure). Un fournisseur construit ici depuis `config/llm.yaml` est fermé
par `Rapport.fermer`, ou dès l'échec de `construire_rapport`. Les secrets passent par
`charger_secrets` (erreur nommant la variable) ; l'URL Jira se résout dans `url_jira` seulement.

L'étape `extraction` verse Jira dans `donnees/entrepot.duckdb` (`EtapeExtraction`) quand
`config/jira.yaml` existe, hors Mode repli, et que le secret de lecture de sa plateforme est
présent (`mode: cloud` : `JIRA_TOKEN_LECTURE`, puis `JIRA_EMAIL` exigé ; `mode: dc` :
`JIRA_DC_PAT`) ; l'adaptateur (`SourceJiraCloud` ou `SourceJiraDC`) suit `mode`. Sinon elle
reste un bouchon et le Journal est la seule source.

Quand l'extraction Jira est active et que le manifeste d'injection existe, la source est
`composite` (Story 2.6) : `instantanes` lit `SourceComposite` (Journal, puis événements Jira
de l'entrepôt postérieurs à la fin d'injection) et l'étape `extraction` persiste les
alignements détectés (`DetecteurAlignements`). L'instant d'extraction est alors figé à la
composition : repère, instant de détection et `version_donnees` le partagent, et la Chaîne
le recopie au manifeste du Passage avec le nombre d'alignements. `version_donnees` porte sur
les octets du Journal, suivis de `\n` et du manifeste d'injection s'il existe.

`instantanes` et `meteo` couvrent chaque Jour ouvré depuis `EnteteJournal.ancrage_semaines`,
aussi ancrage des semaines ; `kpi` (KPI et Tendances), chaque Jour ouvré du premier jour où un
ticket existe à la Date d'arrêté, aucun avant. `prevision` est une `EtapePrevision` sur
`prevision_du_passage` : chaque Jour ouvré, la Baseline (`domaine.prevision.baseline`) pour les
Entités rouges et les Risques d'entrée en rouge (`domaine.prevision.risque`) pour les autres,
avec les paramètres H-7 et H-8 de `ConfigChaine.prevision` (défauts du domaine si absents de
`chaine.yaml`), sur la `SerieStock` que construit `domaine.prevision.serie`. `meteo` reçoit
`ConfigChaine.decalage_comparaison` (H-19), qui dimensionne l'historique transmis au domaine.
`rendu` reçoit l'identité des données (source, versions) et
l'instant d'extraction, affichés dans l'onglet Traçabilité.

Les services de l'UI vivent dans `ui/cli.py`, l'écriture du Journal dans
`generateur.journal.ecrire_journal`.
"""

import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import partial
from pathlib import Path
from types import MappingProxyType

from pydantic import SecretStr

from usine.adaptateurs.composite import DetecteurAlignements, SourceComposite
from usine.adaptateurs.entrepot_duckdb import CHEMIN_ENTREPOT, EtapeExtraction
from usine.adaptateurs.jira_cloud import SourceJiraCloud
from usine.adaptateurs.jira_dc import SourceJiraDC
from usine.adaptateurs.jira_http import construire_client_lecture
from usine.adaptateurs.journal import (
    CHEMIN_MANIFESTE_INJECTION,
    SourceJournal,
    charger_manifeste,
)
from usine.adaptateurs.pseudonymisation import (
    MOTIFS_PAR_DEFAUT,
    PseudonymiseurHmac,
    verifier_cle,
)
from usine.adaptateurs.stockage_sqlite import CacheLLMSqlite, TablePseudonymesSqlite
from usine.chaine.ecrivain import EcrivainPassage
from usine.chaine.etapes import (
    EtapeBouchon,
    EtapeInstantanes,
    EtapeKpi,
    EtapeMeteo,
    EtapePrevision,
    EtapeSautee,
    prevision_du_passage,
)
from usine.chaine.execution import executer_passage
from usine.chaine.verrou import verrou_exclusif
from usine.config import Secrets, charger_secrets, charger_yaml
from usine.consultation.passage import ConsultationPassage
from usine.contrats.calendrier import est_jour_ouvre
from usine.contrats.config import (
    ConfigChaine,
    ConfigJira,
    ConfigLLM,
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
from usine.domaine.prevision.baseline import ParametresBaseline
from usine.domaine.prevision.risque import ParametresRisque
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
    horodatage_extraction: datetime | None = None
    """Instant d'extraction figé à la composition (source `composite`) ; sinon `None`."""
    fermeture: Callable[[], None] | None = None
    """Fermeture du fournisseur LLM construit par la composition ; `None` s'il est injecté."""

    def fermer(self) -> None:
        """Ferme le fournisseur LLM construit par la composition (aucun effet sinon)."""
        if self.fermeture is not None:
            self.fermeture()

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
    """Clé et moteur de Pseudonymisation, vérifiés avant tout Passage."""

    cle: bytes
    motifs: Mapping[str, str]
    """Motifs de `PseudonymiseurHmac` (moteur `regex`)."""
    presidio: ConfigPseudonymisation | None = None
    """Configuration de `PseudonymiseurPresidio` ; `None` pour le moteur `regex`."""


def _moteur_pseudonymisation(
    repertoire_config: Path,
) -> tuple[Mapping[str, str], ConfigPseudonymisation | None]:
    """Moteur de `config/pseudonymisation.yaml` : motifs du moteur `regex`, ou configuration
    du moteur `presidio` ; sans ce fichier, `MOTIFS_PAR_DEFAUT` (moteur `regex`)."""
    chemin = repertoire_config / "pseudonymisation.yaml"
    if not chemin.exists():
        return MOTIFS_PAR_DEFAUT, None
    config = charger_yaml(chemin, ConfigPseudonymisation)
    if config.moteur == "regex":
        return _motifs_pseudonymisation(repertoire_config), None
    if not config.reconnaisseurs and not config.entites_presidio:
        raise UsineErreur(
            f"{chemin}, clés « reconnaisseurs » et « entites_presidio », valeurs vides : rien à"
            " pseudonymiser ; déclarer au moins un reconnaisseur ou une entité"
        )
    return {}, config


def _tarif_registre(version_modele: str, jetons_entree: int, jetons_sortie: int) -> Decimal:
    """Coût estimé du registre des prix ; 0 € pour un modèle absent du registre (doublures)."""
    # Import différé : le paquet `adaptateurs.llm` charge `pydantic_ai` (Palier 2 seulement).
    from usine.adaptateurs.llm import REGISTRE, cout_estime_eur

    if version_modele not in REGISTRE:
        return Decimal(0)
    return cout_estime_eur(version_modele, jetons_entree, jetons_sortie)


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

    Sans pseudonymiseur injecté, renvoie la clé `USINE_CLE_PSEUDO` et le moteur de
    Pseudonymisation ; sinon `None`.
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
    motifs, presidio = _moteur_pseudonymisation(repertoire_config)
    return _ParametresPseudonymisation(octets_cle, motifs, presidio)


def construire_fournisseur(racine: Path, secrets_usine: Secrets | None = None) -> FournisseurLLM:
    """`FournisseurLLM` choisi par `config/llm.yaml`, avec la clé de son fournisseur (H-23).

    `fournisseur: anthropic` lit `ANTHROPIC_API_KEY`, `fournisseur: mistral` lit
    `MISTRAL_API_KEY` ; un fichier absent, un fournisseur inconnu, un modèle hors du registre
    des quotas et des prix ou une clé absente lèvent une `UsineErreur`.
    """
    # Import différé : `pydantic_ai` et les SDK ne se chargent qu'en Palier 2 (outils sans SDK).
    from usine.adaptateurs.llm import construire_fournisseur_llm

    config = _config_llm(racine)
    if config is None:
        chemin = racine / "config" / "llm.yaml"
        raise UsineErreur(f"{chemin} : fichier absent ; aucun fournisseur LLM configuré")
    secrets_usine = secrets_usine if secrets_usine is not None else charger_secrets(racine)
    cles = {"anthropic": secrets_usine.anthropic_api_key, "mistral": secrets_usine.mistral_api_key}
    cle = cles.get(config.fournisseur)
    return construire_fournisseur_llm(config, cle.get_secret_value() if cle is not None else "")


def _config_llm(racine: Path) -> ConfigLLM | None:
    """`config/llm.yaml` validé, ou `None` s'il n'existe pas."""
    chemin = racine / "config" / "llm.yaml"
    return charger_yaml(chemin, ConfigLLM) if chemin.exists() else None


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


def _secret_present(valeur: SecretStr | None) -> bool:
    return valeur is not None and bool(valeur.get_secret_value().strip())


def _jira_actif(jira: ConfigJira | None, secrets_usine: Secrets) -> ConfigJira | None:
    """`jira` si l'extraction Jira est active, sinon `None`.

    Inactive sans `config/jira.yaml`, en Mode repli (pas d'extraction automatique) ou sans le
    secret de lecture de la plateforme.
    """
    if jira is None or secrets_usine.usine_mode_repli:
        return None
    secret = secrets_usine.jira_token_lecture if jira.mode == "cloud" else secrets_usine.jira_dc_pat
    return jira if _secret_present(secret) else None


def _figee(instant: datetime) -> Callable[[], datetime]:
    """Horloge qui rend toujours `instant`."""
    return lambda: instant


def _etape_extraction(
    racine: Path,
    jira: ConfigJira,
    secrets_usine: Secrets,
    horloge: Callable[[], datetime],
    composite: tuple[SourceJournal, datetime] | None = None,
) -> EtapeExtraction:
    """Étape `extraction` : Jira (`mode` de `config/jira.yaml`) vers l'entrepôt.

    En Cloud, `JIRA_TOKEN_LECTURE` sans `JIRA_EMAIL` lève une `UsineErreur` qui nomme
    `JIRA_EMAIL`. Le client Jira est fermé après l'étape. Avec `composite` (Journal lu aux
    clés Jira, instant d'extraction figé), le repère est cet instant et l'étape persiste les
    alignements détectés à cet instant ; la source Jira garde `horloge` (fenêtre `updated`).
    """
    client = construire_client_lecture(
        jira,
        email=secrets_usine.jira_email,
        jeton_lecture=secrets_usine.jira_token_lecture,
        pat=secrets_usine.jira_dc_pat,
    )
    source = (
        SourceJiraCloud(client, jira, horloge)
        if jira.mode == "cloud"
        else SourceJiraDC(client, jira, horloge)
    )
    marge = timedelta(minutes=jira.marge_extraction_minutes)
    if composite is None:
        return EtapeExtraction(source, racine / CHEMIN_ENTREPOT, marge, horloge, client.fermer)
    journal, instant = composite
    return EtapeExtraction(
        source,
        racine / CHEMIN_ENTREPOT,
        marge,
        _figee(instant),
        client.fermer,
        aligner=DetecteurAlignements(journal),
    )


def construire_rapport(
    racine: Path,
    fournisseur: FournisseurLLM | None = None,
    pseudonymiseur: Pseudonymiseur | None = None,
    horloge: Callable[[], datetime] = _maintenant,
) -> Rapport:
    """Charge la configuration et le Journal de `racine`, puis construit le registre.

    En Palier 2, `fournisseur` est obligatoire ; sans `pseudonymiseur`, `PseudonymiseurHmac`
    est construit et exige `USINE_CLE_PSEUDO`. Toute absence lève une `UsineErreur` avant tout
    Passage. `horloge` date les traces LLM, les traces de Prévision et l'extraction Jira
    (repère, restriction `updated`). En source `composite`, l'instant d'extraction est lu une
    seule fois, ici : repère, détection des alignements, `version_donnees` et l'onglet
    Traçabilité du Rapport le partagent.

    Un fournisseur construit ici depuis `config/llm.yaml` est fermé si la construction échoue
    ensuite ; sinon `Rapport.fermer` le ferme.
    """
    chaine = charger_yaml(racine / "config" / "chaine.yaml", ConfigChaine)
    secrets_usine = charger_secrets(racine)
    config_llm = _config_llm(racine)
    fermeture: Callable[[], None] | None = None
    if chaine.palier == 2 and fournisseur is None and config_llm is not None:
        fournisseur = construire_fournisseur(racine, secrets_usine)
        fermeture = getattr(fournisseur, "fermer", None)
    try:
        return _assembler_rapport(
            racine,
            chaine,
            config_llm,
            secrets_usine,
            fournisseur,
            pseudonymiseur,
            horloge,
            fermeture,
        )
    except BaseException:
        if fermeture is not None:
            fermeture()
        raise


def _assembler_rapport(
    racine: Path,
    chaine: ConfigChaine,
    config_llm: ConfigLLM | None,
    secrets_usine: Secrets,
    fournisseur: FournisseurLLM | None,
    pseudonymiseur: Pseudonymiseur | None,
    horloge: Callable[[], datetime],
    fermeture: Callable[[], None] | None,
) -> Rapport:
    """Suite de `construire_rapport`, une fois le fournisseur LLM connu."""
    repertoire_config = racine / "config"
    pseudonymisation = (
        _verifier_llm(fournisseur, pseudonymiseur, secrets_usine, repertoire_config)
        if chaine.palier == 2
        else None
    )
    programme = charger_yaml(repertoire_config / "programme.yaml", ConfigProgramme)
    chemin_grille = repertoire_config / "grille_meteo.yaml"
    grille = verifier_grille(charger_yaml(chemin_grille, GrilleMeteo), str(chemin_grille))
    jira = _config_jira(racine)
    configuration = ConfigUsine(
        chaine=chaine, programme=programme, grille_meteo=grille, jira=jira, llm=config_llm
    )
    gabarit = _octets(racine / CHEMIN_GABARIT, "gabarit PowerPoint")
    empreinte_grille = version_grille(_octets(chemin_grille, "Grille de météo"))

    chemin_journal = racine / CHEMIN_JOURNAL
    chemin_manifeste = racine / CHEMIN_MANIFESTE_INJECTION
    manifeste = charger_manifeste(chemin_manifeste) if chemin_manifeste.exists() else None
    source = SourceJournal(chemin_journal, manifeste)
    jira_actif = _jira_actif(jira, secrets_usine)
    # Source composite : extraction Jira active et Journal lu aux clés Jira.
    horodatage_extraction = horloge() if jira_actif is not None and manifeste is not None else None
    octets_donnees = _octets(chemin_journal, "Journal")
    if manifeste is not None:
        octets_donnees += b"\n" + _octets(chemin_manifeste, "manifeste d'injection")
    empreinte_donnees = version_donnees(octets_donnees, horodatage_extraction)
    premier_jour = source.entete.ancrage_semaines
    entites = [entite.code for entite in programme.entites]
    donnees = DonneesPassage(
        "journal" if horodatage_extraction is None else "composite",
        empreinte_grille,
        empreinte_donnees,
    )

    registre: dict[Etape, PortEtape] = {
        Etape.extraction: EtapeBouchon(),
        Etape.instantanes: EtapeInstantanes(source, premier_jour),
        Etape.kpi: EtapeKpi(entites, premier_jour),
        Etape.meteo: EtapeMeteo(
            grille,
            empreinte_grille,
            entites,
            premier_jour,
            programme,
            decalage=chaine.decalage_comparaison,
        ),
        Etape.prevision: EtapePrevision(
            prevision_du_passage(
                grille,
                entites,
                premier_jour,
                baseline=ParametresBaseline(**chaine.prevision.baseline.model_dump()),
                risque=ParametresRisque(**chaine.prevision.risque.model_dump()),
            ),
            empreinte_donnees,
            horloge,
        ),
        Etape.rendu: EtapeRendu(gabarit, donnees, horodatage_extraction),
    }
    registre.update({etape: EtapeSautee() for etape in ETAPES_LLM})
    if chaine.palier == 2:
        if fournisseur is None:  # pragma: no cover - vérifié par `_verifier_llm`
            raise UsineErreur("Palier 2 sans fournisseur LLM")
        if pseudonymiseur is None:
            if pseudonymisation is None:  # pragma: no cover - vérifié par `_verifier_llm`
                raise UsineErreur("Palier 2 sans USINE_CLE_PSEUDO")
            pseudonymiseur = _pseudonymiseur(racine, pseudonymisation)
        passerelle = Passerelle(
            fournisseur,
            pseudonymiseur,
            CacheLLMSqlite(racine / CHEMIN_CACHE_LLM),
            horloge,
            tarif=_tarif_registre,
            plafond_cout_passage_eur=(
                None if config_llm is None else config_llm.plafond_cout_passage_eur
            ),
        )
        registre[Etape.explications] = EtapeExplications(passerelle, empreinte_donnees)
    # En dernier : le client Jira n'est ouvert qu'une fois tout le reste validé.
    if jira_actif is not None:
        composite = None if horodatage_extraction is None else (source, horodatage_extraction)
        extraction = _etape_extraction(racine, jira_actif, secrets_usine, horloge, composite)
        registre[Etape.extraction] = extraction
        if composite is not None:
            registre[Etape.instantanes] = EtapeInstantanes(
                SourceComposite(source, extraction.evenements_extraits), premier_jour
            )
    return Rapport(
        configuration=configuration,
        registre=MappingProxyType({etape: registre[etape] for etape in Etape}),
        donnees=donnees,
        racine_sorties=racine / REPERTOIRE_SORTIES,
        chemin_verrou=racine / CHEMIN_VERROU,
        url_jira=_url_jira(secrets_usine.usine_mode_repli, jira),
        horodatage_extraction=horodatage_extraction,
        fermeture=fermeture,
    )


def _pseudonymiseur(racine: Path, parametres: _ParametresPseudonymisation) -> Pseudonymiseur:
    """Moteur de Pseudonymisation de `config/pseudonymisation.yaml` (AD-15)."""
    table = TablePseudonymesSqlite(racine / CHEMIN_PSEUDONYMES)
    if parametres.presidio is None:
        return PseudonymiseurHmac(parametres.cle, parametres.motifs, table)
    # Import différé : Presidio et spaCy ne se chargent que pour ce moteur.
    from usine.adaptateurs.presidio import PseudonymiseurPresidio

    return PseudonymiseurPresidio(parametres.cle, parametres.presidio, table)


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
    """Prend le verrou, construit le rapport et exécute un Passage ; verrou toujours rendu.

    Le manifeste du Passage reçoit l'instant d'extraction du rapport et le nombre
    d'alignements persistés par l'étape `extraction`. Le client Jira et le fournisseur LLM
    construit par la composition sont fermés, que le Passage réussisse ou échoue.
    """
    verifier_date_arrete(date_arrete)
    with verrou_exclusif(racine / CHEMIN_VERROU):
        rapport = construire_rapport(racine, fournisseur, pseudonymiseur, horloge)
        extraction = rapport.registre[Etape.extraction]
        try:
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
                horodatage_extraction=rapport.horodatage_extraction,
                nb_alignements=(
                    extraction.nb_alignements if isinstance(extraction, EtapeExtraction) else None
                ),
            )
        finally:
            # Client Jira fermé même si le Passage échoue avant l'étape `extraction`.
            try:
                if isinstance(extraction, EtapeExtraction):
                    extraction.fermer()
            finally:
                rapport.fermer()
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
