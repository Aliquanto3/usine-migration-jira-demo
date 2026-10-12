"""Composition de l'injecteur : seule racine qui construit le client d'écriture Jira (AD-5, FR-5).

Lit la configuration Jira, le Journal, le jeton d'injection et l'état laissé par une injection
précédente (manifeste, `etat_injection_partielle.json`, `site_jira.json`), refuse avant tout
envoi un Journal d'une autre Date d'injection sur le même site, plafonne le débit, puis
enchaîne `preparer_site` et `injecter` (réinjection idempotente). Écrit, de façon atomique,
à côté du manifeste et seulement si le contenu change : `site_jira.json` (identifiants réels
du site) et le manifeste d'injection en cas de succès ; `etat_injection_partielle.json` en
cas d'interruption (supprimé après un succès).
"""

import contextlib
import json
import os
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from usine.adaptateurs.jira_http import construire_client_ecriture
from usine.adaptateurs.journal import (
    CHEMIN_MANIFESTE_INJECTION,
    SourceJournal,
    charger_manifeste,
)
from usine.config import charger_secrets, charger_yaml
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import ManifesteInjection
from usine.contrats.passage import CHEMIN_JOURNAL
from usine.generateur.injecteur.injection import (
    BilanInjection,
    EtatInjectionPartielle,
    EtatPrecedent,
    InjectionInterrompue,
    injecter,
)
from usine.generateur.injecteur.plan import CHAMPS_SELECTION, PlanInjection, planifier
from usine.generateur.injecteur.site import ClientJira, SiteDemo, preparer_site

NOM_SITE = "site_jira.json"
"""Identifiants réels du site préparé, écrits à côté du manifeste."""

NOM_ETAT_PARTIEL = "etat_injection_partielle.json"
"""État d'une injection interrompue, écrit à côté du manifeste."""

DEBIT_DEFAUT = 5.0
"""Débit plafond par défaut, en requêtes par seconde."""


class Limiteur:
    """Plafonne le débit : appelé avant chaque requête, attend si la précédente est trop proche."""

    def __init__(
        self,
        debit: float,
        *,
        horloge_monotone: Callable[[], float] = time.monotonic,
        attendre: Callable[[float], None] = time.sleep,
    ) -> None:
        if not debit > 0:
            raise UsineErreur(f"débit : strictement positif attendu, reçu {debit}")
        self._intervalle = 1.0 / debit
        self._horloge = horloge_monotone
        self._attendre = attendre
        self._prochain: float | None = None

    def __call__(self) -> None:
        maintenant = self._horloge()
        if self._prochain is not None and self._prochain > maintenant:
            self._attendre(self._prochain - maintenant)
            maintenant = self._prochain
        self._prochain = maintenant + self._intervalle


class _ClientLimite:
    """`ClientJira` qui appelle le limiteur avant chaque requête (préparation du site)."""

    def __init__(self, client: ClientJira, limiter: Callable[[], None]) -> None:
        self._client = client
        self._limiter = limiter

    def requete(
        self,
        methode: str,
        chemin: str,
        *,
        params: Mapping[str, Any] | None = None,
        corps: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._limiter()
        return self._client.requete(methode, chemin, params=params, corps=corps)

    def requete_liste(
        self,
        methode: str,
        chemin: str,
        *,
        params: Mapping[str, Any] | None = None,
        corps: Mapping[str, Any] | None = None,
    ) -> list[Any]:
        self._limiter()
        return self._client.requete_liste(methode, chemin, params=params, corps=corps)


def _texte_json(contenu: object) -> str:
    return json.dumps(contenu, ensure_ascii=False, indent=2) + "\n"


def ecrire_json_si_change(chemin: Path, contenu: object) -> bool:
    """Écrit `contenu` comme `ecrire_json_atomique`, sauf si `chemin` le porte déjà.

    Rend `True` si le fichier a été (ré)écrit : un contenu identique laisse le fichier intact.
    """
    try:
        if chemin.read_bytes() == _texte_json(contenu).encode("utf-8"):
            return False
    except OSError:
        pass  # absent ou illisible : réécrit.
    ecrire_json_atomique(chemin, contenu)
    return True


def ecrire_json_atomique(chemin: Path, contenu: object) -> None:
    """Écrit `contenu` en JSON UTF-8 dans `chemin` par fichier temporaire et renommage."""
    texte = _texte_json(contenu)
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        descripteur, temporaire = tempfile.mkstemp(
            dir=chemin.parent, prefix=f".{chemin.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(descripteur, "w", encoding="utf-8", newline="\n") as fichier:
                fichier.write(texte)
                fichier.flush()
                os.fsync(fichier.fileno())
            os.replace(temporaire, chemin)
        except BaseException:
            Path(temporaire).unlink(missing_ok=True)
            raise
    except OSError as exc:
        raise UsineErreur(f"{chemin} : écriture impossible ({exc.strerror or exc})") from exc


@dataclass(frozen=True)
class ResultatInjection:
    """Issue d'une injection réussie."""

    manifeste: ManifesteInjection
    site: SiteDemo
    chemin_manifeste: Path
    chemin_site: Path
    avertissements: tuple[str, ...]
    bilan: BilanInjection
    manifeste_ecrit: bool
    """`False` : le manifeste existant portait déjà ce contenu, laissé intact."""


@dataclass(frozen=True)
class _Anterieur:
    """État laissé à côté du manifeste par une injection précédente."""

    site: dict[str, Any] | None
    manifeste: ManifesteInjection | None
    partiel: EtatInjectionPartielle | None


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _lire_json(chemin: Path) -> object:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UsineErreur(f"{chemin} : JSON illisible ({exc})") from exc


def _lire_anterieur(manifeste: Path) -> _Anterieur:
    chemin_site = manifeste.with_name(NOM_SITE)
    chemin_partiel = manifeste.with_name(NOM_ETAT_PARTIEL)
    site = _lire_json(chemin_site) if chemin_site.exists() else None
    if site is not None and not isinstance(site, dict):
        raise UsineErreur(f"{chemin_site} : objet JSON attendu")
    partiel = None
    if chemin_partiel.exists():
        partiel = EtatInjectionPartielle.depuis_json(
            _lire_json(chemin_partiel), str(chemin_partiel)
        )
    return _Anterieur(
        site=site,
        manifeste=charger_manifeste(manifeste) if manifeste.exists() else None,
        partiel=partiel,
    )


def _site_compatible(anterieur: _Anterieur, url_site: str, cle_projet: str) -> bool:
    """`site_jira.json` précédent absent, ou de même URL et même clé de projet."""
    site = anterieur.site
    if site is None:
        return True
    return (site.get("url_site"), site.get("cle_projet")) == (url_site, cle_projet)


def _meme_site(anterieur: _Anterieur, site: SiteDemo) -> bool:
    """`site_jira.json` précédent absent (même site présumé), ou de même site et projet."""
    precedent = anterieur.site
    if precedent is None:
        return True
    lu = (precedent.get("url_site"), precedent.get("cle_projet"), precedent.get("id_projet"))
    return lu == (site.url_site, site.cle_projet, site.id_projet)


def _partiel_du_site(
    anterieur: _Anterieur, url_site: str, cle_projet: str, id_projet: str | None
) -> EtatInjectionPartielle | None:
    """État partiel de ce site ; `id_projet` `None` (avant préparation) : URL et clé seules."""
    partiel = anterieur.partiel
    if partiel is None or partiel.cle_projet != cle_projet:
        return None
    if partiel.url_site is None:  # état partiel de la Story 1.6 : site de `site_jira.json`.
        if not _site_compatible(anterieur, url_site, cle_projet):
            return None
        if id_projet is not None and anterieur.site is not None:
            return partiel if anterieur.site.get("id_projet") == id_projet else None
        return partiel
    if partiel.url_site != url_site:
        return None
    return partiel if id_projet is None or partiel.id_projet == id_projet else None


def _verifier_date(
    anterieur: _Anterieur, manifeste: Path, config: ConfigJira, plan: PlanInjection
) -> None:
    """Refuse, avant tout envoi, un Journal d'une autre Date d'injection sur le même site."""
    candidats: list[tuple[str, date]] = []
    if (
        anterieur.manifeste is not None
        and anterieur.manifeste.cle_projet == config.cle_projet
        and _site_compatible(anterieur, config.url_site, config.cle_projet)
    ):
        candidats.append((manifeste.name, anterieur.manifeste.date_injection))
    partiel = _partiel_du_site(anterieur, config.url_site, config.cle_projet, None)
    if partiel is not None:
        candidats.append((NOM_ETAT_PARTIEL, partiel.date_injection))
    for nom, date_precedente in candidats:
        if date_precedente != plan.date_injection:
            raise UsineErreur(
                f"{nom} : Date d'injection {date_precedente.isoformat()}, Journal du"
                f" {plan.date_injection.isoformat()} : le projet {config.cle_projet} de"
                f" {config.url_site} a été injecté depuis un autre Journal ; rien n'est"
                " envoyé (nouveau site : déplacer d'abord le répertoire du manifeste)"
            )


def _precedent(anterieur: _Anterieur, site: SiteDemo) -> EtatPrecedent | None:
    """État précédent du même site : manifeste et état partiel fusionnés ; sinon `None`."""
    manifeste = anterieur.manifeste
    if manifeste is not None and not (
        _meme_site(anterieur, site) and manifeste.cle_projet == site.cle_projet
    ):
        manifeste = None
    partiel = _partiel_du_site(anterieur, site.url_site, site.cle_projet, site.id_projet)
    sources: list[Mapping[str, str]] = []
    if manifeste is not None:
        sources.append(manifeste.correspondance_cles)
    if partiel is not None:
        sources.append(partiel.correspondance_cles)
    correspondance: dict[str, str] = {}
    for source in sources:
        for generee, cle_jira in source.items():
            if correspondance.setdefault(generee, cle_jira) != cle_jira:
                raise UsineErreur(
                    f"{NOM_ETAT_PARTIEL} : {generee} → {cle_jira}, le manifeste porte"
                    f" {correspondance[generee]} ; rien n'est écrit"
                )
    if manifeste is not None:
        # Un état partiel signale des écritures après le manifeste : sa fin n'est plus sûre.
        fin = manifeste.horodatage_fin_injection if partiel is None else None
        return EtatPrecedent(manifeste.debut_injection, fin, correspondance)
    if partiel is not None:
        return EtatPrecedent(partiel.debut_injection, None, correspondance)
    return None


def ecarts_champs(config: ConfigJira, site: SiteDemo) -> list[str]:
    """Champs dont l'identifiant de `config/jira.yaml` diffère de celui du site."""
    return [
        f"{champ.value} : {config.champs[champ]} (config) ≠ {site.champs[champ]} (site)"
        for champ in CHAMPS_SELECTION
        if config.champs.get(champ) != site.champs[champ]
    ]


def executer_injection(
    *,
    racine: Path,
    config_jira: Path,
    journal: Path,
    manifeste: Path,
    debit: float = DEBIT_DEFAUT,
    attendre: Callable[[float], None] = time.sleep,
    horloge: Callable[[], datetime] = _maintenant,
    horloge_monotone: Callable[[], float] = time.monotonic,
    transport_http: Any = None,
) -> ResultatInjection:
    """Injecte le Journal `journal` dans le site de `config_jira` et écrit le manifeste.

    Réinjection idempotente : sur le même site (même URL, clé et identifiant de projet que
    `site_jira.json`), les tickets déjà présents sont repris, seuls les absents sont créés ;
    le manifeste garde la correspondance et le début d'origine. Nouveau site : l'état
    précédent est ignoré. Refusé avant tout envoi si le jeton d'injection manque ou si le
    manifeste du même site porte une autre Date d'injection. `transport_http` (transport
    httpx) ne sert qu'aux tests ; secrets lus dans `racine/.env` et l'environnement.
    """
    config = charger_yaml(config_jira, ConfigJira)
    source = SourceJournal(journal)
    plan = planifier(source.entete, source.evenements())
    anterieur = _lire_anterieur(manifeste)
    _verifier_date(anterieur, manifeste, config, plan)
    secrets = charger_secrets(racine)
    limiteur = Limiteur(debit, horloge_monotone=horloge_monotone, attendre=attendre)
    chemin_site = manifeste.with_name(NOM_SITE)
    chemin_partiel = manifeste.with_name(NOM_ETAT_PARTIEL)
    with construire_client_ecriture(
        config,
        email=secrets.jira_email,
        jeton_injection=secrets.jira_token_injection,
        attendre=attendre,
        transport_http=transport_http,
    ) as client:
        site = preparer_site(_ClientLimite(client, limiteur), config, plan.valeurs_libres)
        if _meme_site(anterieur, site):  # nouveau site : réécrit après le succès seulement.
            ecrire_json_si_change(chemin_site, site.vers_json())
        precedent = _precedent(anterieur, site)
        try:
            bilan = injecter(client, plan, site, config, horloge, limiteur, precedent)
        except InjectionInterrompue as exc:
            ecrire_json_atomique(chemin_partiel, exc.etat.vers_json())
            raise
    manifeste_ecrit = ecrire_json_si_change(manifeste, bilan.manifeste.model_dump(mode="json"))
    ecrire_json_si_change(chemin_site, site.vers_json())
    with contextlib.suppress(OSError):  # caduc une fois le manifeste écrit.
        chemin_partiel.unlink(missing_ok=True)
    return ResultatInjection(
        bilan.manifeste,
        site,
        manifeste,
        chemin_site,
        tuple(ecarts_champs(config, site)),
        bilan,
        manifeste_ecrit,
    )


def commande_injecter(
    journal: Annotated[
        Path, typer.Option(help="Journal d'événements à injecter.")
    ] = CHEMIN_JOURNAL,
    config_jira: Annotated[
        Path, typer.Option("--config-jira", help="Configuration Jira (site, projet, valeurs).")
    ] = Path("config/jira.yaml"),
    manifeste: Annotated[
        Path,
        typer.Option(help="Manifeste d'injection à écrire ; site_jira.json est écrit à côté."),
    ] = CHEMIN_MANIFESTE_INJECTION,
    debit: Annotated[
        float, typer.Option(help="Débit plafond, en requêtes par seconde.")
    ] = DEBIT_DEFAUT,
) -> None:
    """Injecte le Programme fictif dans Jira Cloud par l'API REST (jeton JIRA_TOKEN_INJECTION).

    Prépare le site (types, champs, workflow H-17, schémas, écran, projet ; idempotent par
    nom), liste les tickets du projet, reprend ceux déjà présents (amenés à leur état à la
    Date d'injection), crée les absents dans l'ordre des clés générées et écrit le manifeste
    d'injection. Relançable : une réinjection complète n'écrit rien. Refuse un ticket du
    projet étranger au Journal et un Journal d'une autre Date d'injection sur le même site.
    Après une interruption, attendre une minute avant de relancer (index de recherche Jira).
    """
    resultat = executer_injection(
        racine=Path("."),
        config_jira=config_jira,
        journal=journal,
        manifeste=manifeste,
        debit=debit,
    )
    bilan = resultat.bilan
    typer.echo(
        f"Site préparé : {resultat.chemin_site} ({len(resultat.site.crees)} objet(s) créé(s))"
    )
    typer.echo(
        f"Tickets : {len(bilan.crees)} créé(s), {len(bilan.repris)} repris,"
        f" {bilan.transitions} transition(s)"
    )
    etat = "écrit" if resultat.manifeste_ecrit else "inchangé"
    typer.echo(
        f"Manifeste {etat} : {resultat.chemin_manifeste}"
        f" ({len(resultat.manifeste.correspondance_cles)} tickets, projet"
        f" {resultat.manifeste.cle_projet}, Date d'injection"
        f" {resultat.manifeste.date_injection.isoformat()})"
    )
    if resultat.avertissements:
        typer.echo(
            "Avertissement : config/jira.yaml, champs : identifiants différents du site, à"
            f" aligner avant `usine rapport` (voir {resultat.chemin_site}) :",
            err=True,
        )
        for ecart in resultat.avertissements:
            typer.echo(f"  {ecart}", err=True)
