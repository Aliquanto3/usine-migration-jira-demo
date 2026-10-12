"""Composition de l'injecteur : seule racine qui construit le client d'écriture Jira (AD-5, FR-5).

Lit la configuration Jira, le Journal et le jeton d'injection, refuse un manifeste existant
avant tout envoi, plafonne le débit, puis enchaîne `preparer_site` et `injecter`. Écrit, de
façon atomique et à côté du manifeste : `site_jira.json` (identifiants réels du site), le
manifeste d'injection en cas de succès, `etat_injection_partielle.json` en cas d'interruption.
"""

import json
import os
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from usine.adaptateurs.jira_http import construire_client_ecriture
from usine.adaptateurs.journal import CHEMIN_MANIFESTE_INJECTION, SourceJournal
from usine.config import charger_secrets, charger_yaml
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import ManifesteInjection
from usine.contrats.passage import CHEMIN_JOURNAL
from usine.generateur.injecteur.injection import InjectionInterrompue, injecter
from usine.generateur.injecteur.plan import CHAMPS_SELECTION, planifier
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


def ecrire_json_atomique(chemin: Path, contenu: object) -> None:
    """Écrit `contenu` en JSON UTF-8 dans `chemin` par fichier temporaire et renommage."""
    texte = json.dumps(contenu, ensure_ascii=False, indent=2) + "\n"
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


def ecarts_champs(config: ConfigJira, site: SiteDemo) -> list[str]:
    """Champs dont l'identifiant de `config/jira.yaml` diffère de celui du site."""
    return [
        f"{champ.value} : {config.champs[champ]} (config) ≠ {site.champs[champ]} (site)"
        for champ in CHAMPS_SELECTION
        if config.champs.get(champ) != site.champs[champ]
    ]


@dataclass(frozen=True)
class ResultatInjection:
    """Issue d'une injection réussie."""

    manifeste: ManifesteInjection
    site: SiteDemo
    chemin_manifeste: Path
    chemin_site: Path
    avertissements: tuple[str, ...]


def _maintenant() -> datetime:
    return datetime.now(UTC)


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

    Refusé avant tout envoi si `manifeste` existe déjà ou si le jeton d'injection manque.
    `transport_http` (transport httpx) ne sert qu'aux tests ; secrets lus dans `racine/.env`
    et l'environnement.
    """
    config = charger_yaml(config_jira, ConfigJira)
    if manifeste.exists():
        raise UsineErreur(
            f"{manifeste} : manifeste d'injection déjà présent : le site est déjà injecté"
            " (réinjection : Story 1.7) ; rien n'est envoyé"
        )
    source = SourceJournal(journal)
    plan = planifier(source.entete, source.evenements())
    secrets = charger_secrets(racine)
    limiteur = Limiteur(debit, horloge_monotone=horloge_monotone, attendre=attendre)
    with construire_client_ecriture(
        config,
        email=secrets.jira_email,
        jeton_injection=secrets.jira_token_injection,
        attendre=attendre,
        transport_http=transport_http,
    ) as client:
        site = preparer_site(_ClientLimite(client, limiteur), config, plan.valeurs_libres)
        chemin_site = manifeste.with_name(NOM_SITE)
        ecrire_json_atomique(chemin_site, site.vers_json())
        try:
            resultat = injecter(client, plan, site, config, horloge, limiteur)
        except InjectionInterrompue as exc:
            ecrire_json_atomique(manifeste.with_name(NOM_ETAT_PARTIEL), exc.etat.vers_json())
            raise
    ecrire_json_atomique(manifeste, resultat.model_dump(mode="json"))
    return ResultatInjection(
        resultat, site, manifeste, chemin_site, tuple(ecarts_champs(config, site))
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
    nom), crée les tickets dans l'ordre des clés générées, les amène à leur état à la Date
    d'injection et écrit le manifeste d'injection. Refuse un projet déjà peuplé ou un
    manifeste existant.
    """
    resultat = executer_injection(
        racine=Path("."),
        config_jira=config_jira,
        journal=journal,
        manifeste=manifeste,
        debit=debit,
    )
    crees = resultat.site.crees
    typer.echo(f"Site préparé : {resultat.chemin_site} ({len(crees)} objet(s) créé(s))")
    typer.echo(
        f"Manifeste écrit : {resultat.chemin_manifeste}"
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
