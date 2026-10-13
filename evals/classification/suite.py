"""Exécution de la suite d'évaluation de la classification des Causes racines (SM-9).

`executer_suite` passe chaque Anomalie d'une source par la vraie tâche `classer`, passerelle
comprise (façade `usine.composition.construire_classificateur`), puis compare les Causes
racines proposées à la vérité de la source (`metriques.evaluer`). Chaque source (`manuels`,
`generateur`) publie son propre F1 macro ; `sm9_atteint` vaut vrai quand les deux sont
≥ 0,8, `null` si une source manque.

Rejeu (défaut, sans réseau ni secret) : `FournisseurEnregistre` sert la réponse enregistrée
de chaque clé. Pour les tickets manuels, c'est la réponse du fichier versionné ; pour la
source générateur, ce sont les `propositions` d'un résultat antérieur (`--reponses`), ce qui
rend un run réel rejouable hors réseau. `reel=True` lit `config/llm.yaml`, la clé du
fournisseur et `USINE_CLE_PSEUDO`, comme un Passage Palier 2.

Garde-fou AD-19 (seconde moitié) : le modèle de classification (celui du fournisseur réel, ou
celui du résultat rejoué) doit différer du `modele_corpus` du Journal ; sinon `UsineErreur`.
"""

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import polars as pl
from pydantic import BaseModel, TypeAdapter, ValidationError

from evals.classification.metriques import evaluer
from evals.classification.tickets import (
    SourceGenerateur,
    TicketManuel,
    table_textes_manuels,
)
from usine.composition import Classificateur, construire_classificateur
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    MessageAgent,
    OutilAgent,
    ParametresAppel,
    ReponseAgentBrute,
    ReponseClassification,
    ReponseStructuree,
)
from usine.contrats.tickets import MOTIF_CLE_TICKET, CauseRacine, rang_cle
from usine.ports.fournisseur_llm import FournisseurLLM

VERSION_MODELE_ENREGISTRE = "enregistre:rejeu"
"""`version_modele` annoncée par `FournisseurEnregistre`."""

SEUIL_F1_MACRO = 0.8
"""F1 macro minimal de SM-9, sur chaque source."""

SOURCES = ("manuels", "generateur")
"""Sources de la suite, dans l'ordre d'exécution."""

REPERTOIRE_RESULTATS = Path(__file__).parent / "resultats"
CHEMIN_HISTORIQUE = Path(__file__).parent / "historique.jsonl"

_CLE_PROMPT = re.compile(rf"```text\n({MOTIF_CLE_TICKET}) : ")
"""Clé de l'Anomalie en tête du bloc de données du prompt `classification`."""

_PROPOSITIONS = TypeAdapter(dict[str, CauseRacine])


def _jetons(texte: str) -> int:
    return len(texte.split())


class FournisseurEnregistre:
    """Fournisseur LLM sans réseau : sert la réponse enregistrée de la clé de chaque prompt."""

    def __init__(self, source: str, reponses: Mapping[str, ReponseClassification]) -> None:
        self._source = source
        self._reponses = dict(reponses)

    @property
    def version_modele(self) -> str:
        """Version de modèle annoncée (`enregistre:rejeu`)."""
        return VERSION_MODELE_ENREGISTRE

    def generer_structure[T: BaseModel](
        self, prompt: str, schema: type[T], parametres: ParametresAppel
    ) -> ReponseStructuree[T]:
        """Réponse enregistrée de la clé du prompt ; clé absente : `UsineErreur` la nommant."""
        trouvee = _CLE_PROMPT.search(prompt)
        if trouvee is None:
            raise UsineErreur(f"source « {self._source} » : clé de ticket introuvable au prompt")
        cle = trouvee.group(1)
        reponse = self._reponses.get(cle)
        if reponse is None:
            raise UsineErreur(f"source « {self._source} » : aucune réponse enregistrée pour {cle}")
        brut = reponse.model_dump_json()
        return ReponseStructuree[T](
            sortie=schema.model_validate_json(brut),
            brut=brut,
            jetons_entree=_jetons(prompt),
            jetons_sortie=_jetons(brut),
            version_modele=VERSION_MODELE_ENREGISTRE,
        )

    def executer_agent(
        self,
        messages: Sequence[MessageAgent],
        outils: Sequence[OutilAgent],
        parametres: ParametresAppel,
    ) -> ReponseAgentBrute:
        """Sans objet pour la classification."""
        raise UsineErreur(f"source « {self._source} » : aucun tour d'Agent enregistré")


class PseudonymiseurIdentite:
    """Pseudonymiseur sans secret : textes rejoués inchangés."""

    def pseudonymiser(self, texte: str) -> str:
        """`texte` inchangé."""
        return texte

    def reidentifier(self, texte: str) -> str:
        """`texte` inchangé."""
        return texte

    def apercu(self, texte: str) -> str:
        """`texte` inchangé."""
        return texte


@dataclass(frozen=True)
class ReponsesEnregistrees:
    """Propositions de la source générateur d'un résultat antérieur, rejouables."""

    propositions: Mapping[str, CauseRacine]
    modele_classification: str | None
    """Modèle de classification qui a produit ces propositions, s'il est connu."""
    chemin: Path


def lire_reponses(chemin: Path) -> ReponsesEnregistrees:
    """`sources.generateur.propositions` du résultat `chemin` ; `UsineErreur` sinon."""
    try:
        resultat = json.loads(chemin.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UsineErreur(f"{chemin} : résultat illisible ({exc.strerror or exc})") from exc
    except UnicodeDecodeError as exc:
        raise UsineErreur(f"{chemin} : résultat non encodé en UTF-8 ({exc.reason})") from exc
    except json.JSONDecodeError as exc:
        raise UsineErreur(f"{chemin} : JSON mal formé ({exc.msg}, ligne {exc.lineno})") from exc
    source = resultat.get("sources", {}) if isinstance(resultat, dict) else {}
    generateur = source.get("generateur") if isinstance(source, dict) else None
    if not isinstance(generateur, dict) or not isinstance(generateur.get("propositions"), dict):
        raise UsineErreur(f"{chemin} : résultat sans « sources.generateur.propositions »")
    try:
        propositions = _PROPOSITIONS.validate_python(generateur["propositions"])
    except ValidationError as exc:
        premiere = exc.errors()[0]
        raise UsineErreur(
            f"{chemin} : propositions mal formées ({'.'.join(map(str, premiere['loc']))} :"
            f" {premiere['msg']})"
        ) from exc
    modele = generateur.get("modele_classification")
    return ReponsesEnregistrees(
        MappingProxyType(propositions), modele if isinstance(modele, str) else None, chemin
    )


def verifier_ad19(modele_classification: str, modele_corpus: str) -> None:
    """Garde-fou AD-19 : le modèle de classification doit différer du `modele_corpus`."""
    if modele_classification == modele_corpus:
        raise UsineErreur(
            f"modèle de classification {modele_classification!r} identique au « modele_corpus »"
            f" {modele_corpus!r} du Journal : un modèle ne doit pas classer les textes qu'il a"
            " lui-même écrits (AD-19)"
        )


MAX_ECHECS_CONSECUTIFS = 10
"""Échecs consécutifs du fournisseur au-delà desquels le mode réel s'arrête (panne franche)."""


def _proposer(
    classificateur: Classificateur, textes: pl.DataFrame, *args: Any, tolerer: bool = False
) -> tuple[dict[str, CauseRacine], dict[str, str], float, dict[str, str]]:
    """Propositions, justifications, coût estimé et échecs du fournisseur par clé.

    `tolerer=True` (mode réel) : une Anomalie à la fois ; un échec isolé du fournisseur
    (`UsineErreur`) laisse l'Anomalie non classée et est consigné, au lieu de perdre tout le
    run ; `MAX_ECHECS_CONSECUTIFS` échecs d'affilée arrêtent la suite.
    """
    erreurs: dict[str, str] = {}
    try:
        if not tolerer:
            sorties, traces = classificateur(textes, *args)
        else:
            sorties, traces = (), ()
            consecutifs = 0
            for rang in range(textes.height):
                ligne = textes.slice(rang, 1)
                try:
                    une, ses_traces = classificateur(ligne, *args)
                except UsineErreur as exc:
                    erreurs[str(ligne["cle_ticket"][0])] = str(exc)
                    consecutifs += 1
                    if consecutifs >= MAX_ECHECS_CONSECUTIFS:
                        raise UsineErreur(
                            f"{consecutifs} échecs consécutifs du fournisseur ; dernier : {exc}"
                        ) from exc
                    continue
                consecutifs = 0
                sorties += une
                traces += ses_traces
    finally:
        classificateur.fermer()
    propositions = {sortie.cle_ticket: sortie.cause_racine for sortie in sorties}
    justifications = {sortie.cle_ticket: sortie.justification for sortie in sorties}
    cout = float(sum(trace.cout_estime_eur for trace in traces))
    return propositions, justifications, cout, erreurs


def _bloc(
    classificateur: Classificateur,
    verite: Mapping[str, CauseRacine],
    propositions: Mapping[str, CauseRacine],
    cout: float,
    erreurs: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "version_prompt": classificateur.version_prompt,
        "version_modele": classificateur.version_modele,
        **evaluer(verite, propositions),
        "cout_estime_eur": round(cout, 6),
        "erreurs_fournisseur": dict(sorted(erreurs.items(), key=lambda item: rang_cle(item[0]))),
        "propositions": {
            cle: propositions[cle].value for cle in sorted(propositions, key=rang_cle)
        },
    }


def _executer_manuels(
    tickets: Sequence[TicketManuel], fabrique: Callable[..., Classificateur], reel: bool
) -> dict[str, Any]:
    if reel:
        classificateur = fabrique()
    else:
        reponses = {ticket.cle: ticket.reponse for ticket in tickets}
        classificateur = fabrique(FournisseurEnregistre("manuels", reponses))
    propositions, justifications, cout, erreurs = _proposer(
        classificateur, table_textes_manuels(tickets), tolerer=reel
    )
    verite = {ticket.cle: ticket.cause_attendue for ticket in tickets}
    bloc = _bloc(classificateur, verite, propositions, cout, erreurs)
    bloc["details"] = [
        {
            "cle": ticket.cle,
            "domaine": ticket.domaine,
            "cause_attendue": ticket.cause_attendue.value,
            "cause_proposee": (
                propositions[ticket.cle].value if ticket.cle in propositions else None
            ),
            "justification": justifications.get(ticket.cle),
        }
        for ticket in tickets
    ]
    return bloc


def _executer_generateur(
    source: SourceGenerateur,
    fabrique: Callable[..., Classificateur],
    reel: bool,
    reponses: ReponsesEnregistrees | None,
) -> dict[str, Any]:
    modele_corpus = source.entete.modele_corpus
    if reel:
        classificateur = fabrique()
        modele_classification = classificateur.version_modele
        try:
            verifier_ad19(modele_classification, modele_corpus)
        except UsineErreur:
            classificateur.fermer()
            raise
    else:
        if reponses is None:
            raise UsineErreur(
                "source « generateur » en rejeu : `--reponses <résultat antérieur>` requis"
                " (ou `--reel` pour classer réellement)"
            )
        manquantes = sorted(set(source.verite) - set(reponses.propositions), key=rang_cle)
        if manquantes:
            raise UsineErreur(
                f"{reponses.chemin} : aucune réponse enregistrée pour {len(manquantes)}"
                f" Anomalie(s) du Journal, dont {manquantes[0]}"
            )
        if reponses.modele_classification is not None:
            verifier_ad19(reponses.modele_classification, modele_corpus)
        enregistrees = {
            cle: ReponseClassification(cause_racine=cause)
            for cle, cause in reponses.propositions.items()
        }
        classificateur = fabrique(FournisseurEnregistre("generateur", enregistrees))
        modele_classification = reponses.modele_classification or classificateur.version_modele
    propositions, _, cout, erreurs = _proposer(
        classificateur, source.textes, source.entete.date_generation, tolerer=reel
    )
    return {
        "journal": str(source.chemin_journal),
        "verite_terrain": str(source.chemin_verite),
        "date_generation": source.entete.date_generation.isoformat(),
        "version_corpus": source.entete.version_corpus,
        "modele_corpus": modele_corpus,
        "modele_classification": modele_classification,
        **_bloc(classificateur, source.verite, propositions, cout, erreurs),
    }


def executer_suite(
    racine: Path,
    *,
    manuels: Sequence[TicketManuel] | None = None,
    generateur: SourceGenerateur | None = None,
    reponses: ReponsesEnregistrees | None = None,
    reel: bool = False,
    horloge: datetime | None = None,
) -> dict[str, Any]:
    """Résultat JSON de la suite : métriques par source, versions, verdict SM-9.

    Une source à `None` n'est pas exécutée. Rejeu (défaut) : réponses enregistrées, sans
    réseau. `reel=True` : un classificateur par source construit depuis la configuration de
    `racine` (réseau, coût).
    """
    instant = horloge or datetime.now(UTC)

    def fabrique(fournisseur: FournisseurLLM | None = None) -> Classificateur:
        if fournisseur is None:
            return construire_classificateur(racine)
        return construire_classificateur(
            racine, fournisseur=fournisseur, pseudonymiseur=PseudonymiseurIdentite()
        )

    sources: dict[str, dict[str, Any]] = {}
    if manuels is not None:
        sources["manuels"] = _executer_manuels(manuels, fabrique, reel)
    if generateur is not None:
        sources["generateur"] = _executer_generateur(generateur, fabrique, reel, reponses)
    if not sources:
        raise UsineErreur("aucune source à évaluer")
    f1_macro = {nom: sources[nom]["f1_macro"] if nom in sources else None for nom in SOURCES}
    valeurs = [valeur for valeur in f1_macro.values() if valeur is not None]
    sm9 = (
        all(valeur >= SEUIL_F1_MACRO for valeur in valeurs)
        if len(valeurs) == len(SOURCES)
        else None
    )
    return {
        "horodatage": instant.isoformat(),
        "mode": "reel" if reel else "rejeu",
        "version_prompt": ", ".join(sorted({bloc["version_prompt"] for bloc in sources.values()})),
        "version_modele": ", ".join(sorted({bloc["version_modele"] for bloc in sources.values()})),
        "seuil_f1_macro": SEUIL_F1_MACRO,
        "f1_macro": f1_macro,
        "sm9_atteint": sm9,
        "sources": sources,
    }


def nom_resultat(instant: datetime) -> str:
    """Nom de fichier d'un résultat : `<AAAAMMJJTHHMMSSZ>.json`."""
    return instant.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ") + ".json"


def ecrire_resultat(resultat: dict[str, Any], repertoire: Path) -> Path:
    """Écrit `resultat` sous `repertoire/<horodatage>.json` et renvoie le chemin."""
    repertoire.mkdir(parents=True, exist_ok=True)
    chemin = repertoire / nom_resultat(datetime.fromisoformat(resultat["horodatage"]))
    chemin.write_text(
        json.dumps(resultat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return chemin


def ajouter_historique(
    resultat: dict[str, Any], chemin_resultat: Path, chemin_historique: Path = CHEMIN_HISTORIQUE
) -> dict[str, Any]:
    """Ajoute à `chemin_historique` la synthèse du résultat (une ligne JSON) et la renvoie."""
    sources = resultat["sources"]
    generateur = sources.get("generateur", {})
    entree = {
        "horodatage_execution": resultat["horodatage"],
        "resultat": chemin_resultat.name,
        "mode": resultat["mode"],
        "version_prompt": resultat["version_prompt"],
        "version_modele": resultat["version_modele"],
        "f1_macro": resultat["f1_macro"],
        "exactitude": {nom: bloc["exactitude"] for nom, bloc in sources.items()},
        "version_corpus": generateur.get("version_corpus"),
        "modele_corpus": generateur.get("modele_corpus"),
        "modele_classification": generateur.get("modele_classification"),
        "cout_estime_eur": round(sum(bloc["cout_estime_eur"] for bloc in sources.values()), 6),
        "sm9_atteint": resultat["sm9_atteint"],
    }
    chemin_historique.parent.mkdir(parents=True, exist_ok=True)
    with chemin_historique.open("a", encoding="utf-8", newline="\n") as fichier:
        fichier.write(json.dumps(entree, ensure_ascii=False) + "\n")
    return entree
