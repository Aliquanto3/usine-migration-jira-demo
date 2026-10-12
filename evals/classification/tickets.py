"""Sources de la suite d'évaluation de la classification des Causes racines (SM-9).

- `manuels` : 30 tickets rédigés à la main (`tickets_manuels.json`), chacun avec sa Cause
  racine attendue et la réponse enregistrée du fournisseur (rejouée hors réseau).
- `generateur` : les Anomalies d'un Journal généré (`journal.jsonl`) et leur vérité terrain
  (`verite_terrain.json`), lus dans un répertoire de données. Seule cette suite lit la vérité
  terrain (AD-23).

Garde-fou AD-19 (première moitié) : le Journal doit avoir été généré avec le Corpus de textes
versionné définitif ; un Journal aux gabarits provisoires, ou d'un autre Corpus, est refusé.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import EnteteJournal, Evenement
from usine.contrats.llm import ReponseClassification
from usine.contrats.passage import CHEMIN_JOURNAL, CHEMIN_VERITE_TERRAIN
from usine.contrats.schemas import valider
from usine.contrats.tickets import (
    MOTIF_CLE_TICKET,
    SCHEMA_TICKET_TEXTE,
    CauseRacine,
    TypeTicket,
    rang_cle,
)
from usine.domaine.instantanes import tickets_textes

NOMBRE_TICKETS_MANUELS = 30
"""Nombre de tickets rédigés à la main exigé par SM-9."""

CHEMIN_TICKETS_MANUELS = Path(__file__).parent / "tickets_manuels.json"
"""Tickets manuels versionnés."""

CHEMIN_CORPUS = Path("donnees") / "corpus" / "textes.json"
"""Corpus de textes versionné, relatif à la racine (même valeur que
`usine.generateur.corpus.CHEMIN_CORPUS`, qu'`evals` ne peut pas importer)."""

MODELE_GABARITS = "gabarits-provisoires"
"""`modele_corpus` du Corpus provisoire (`usine.generateur.corpus.MODELE_GABARITS`)."""

_VERITE = TypeAdapter(dict[str, CauseRacine])


class TicketManuel(BaseModel):
    """Anomalie rédigée à la main, sa Cause racine attendue et la réponse enregistrée."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cle: str = Field(pattern=f"^{MOTIF_CLE_TICKET}$")
    domaine: str = Field(min_length=1)
    """Domaine fonctionnel (crédits, dépôts…), repris comme Entité du ticket."""
    titre: str = Field(min_length=1)
    description: str = Field(min_length=1)
    cause_attendue: CauseRacine
    reponse: ReponseClassification
    """Réponse du fournisseur rejouée hors réseau (elle peut être fausse)."""


def _premiere_erreur(exc: ValidationError) -> str:
    premiere = exc.errors()[0]
    lieu = ".".join(str(partie) for partie in premiere["loc"]) or "racine"
    return f"{exc.error_count()} erreur(s), {lieu} : {premiere['msg']}"


def charger_tickets_manuels(
    chemin: Path = CHEMIN_TICKETS_MANUELS,
) -> tuple[TicketManuel, ...]:
    """Tickets de `chemin` : exactement 30, clés uniques ; sinon `UsineErreur` nommant le
    fichier."""
    try:
        tickets = TypeAdapter(tuple[TicketManuel, ...]).validate_json(chemin.read_bytes())
    except OSError as exc:
        raise UsineErreur(f"{chemin} : tickets manuels illisibles ({exc.strerror or exc})") from exc
    except ValidationError as exc:
        raise UsineErreur(
            f"{chemin} : tickets manuels mal formés ({_premiere_erreur(exc)})"
        ) from exc
    if len(tickets) != NOMBRE_TICKETS_MANUELS:
        raise UsineErreur(
            f"{chemin} : {len(tickets)} tickets, {NOMBRE_TICKETS_MANUELS} attendus (SM-9)"
        )
    cles = [ticket.cle for ticket in tickets]
    doublons = sorted({cle for cle in cles if cles.count(cle) > 1}, key=rang_cle)
    if doublons:
        raise UsineErreur(f"{chemin} : clé(s) de ticket en double {doublons}")
    return tickets


def table_textes_manuels(tickets: Sequence[TicketManuel]) -> pl.DataFrame:
    """Table `SCHEMA_TICKET_TEXTE` des tickets manuels (Anomalies, Entité = domaine)."""
    table = pl.DataFrame(
        {
            "cle_ticket": [ticket.cle for ticket in tickets],
            "type_ticket": [TypeTicket.anomalie.value] * len(tickets),
            "entite": [ticket.domaine for ticket in tickets],
            "titre": [ticket.titre for ticket in tickets],
            "description": [ticket.description for ticket in tickets],
        },
        schema=dict(SCHEMA_TICKET_TEXTE.colonnes),
    )
    return valider(table, SCHEMA_TICKET_TEXTE)


@dataclass(frozen=True)
class SourceGenerateur:
    """Anomalies d'un Journal généré et leur vérité terrain."""

    entete: EnteteJournal
    textes: pl.DataFrame
    """`SCHEMA_TICKET_TEXTE` des seules Anomalies, à la date de génération."""
    verite: Mapping[str, CauseRacine]
    chemin_journal: Path
    chemin_verite: Path


def _extrait(cles: Sequence[str]) -> str:
    """Au plus cinq clés, suivies de « … » s'il y en a d'autres."""
    return ", ".join(cles[:5]) + (", …" if len(cles) > 5 else "")


def _lire_journal(chemin: Path) -> tuple[EnteteJournal, list[Evenement]]:
    try:
        lignes = chemin.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise UsineErreur(
            f"{chemin} : Journal illisible ({exc.strerror or exc}) ; le générer avec"
            " `usine donnees generer --sortie <répertoire>`"
        ) from exc
    except UnicodeDecodeError as exc:
        raise UsineErreur(f"{chemin} : Journal non encodé en UTF-8 ({exc.reason})") from exc
    lignes = [ligne for ligne in lignes if ligne.strip()]
    if not lignes:
        raise UsineErreur(f"{chemin} : Journal vide")
    try:
        entete = EnteteJournal.model_validate_json(lignes[0])
    except ValidationError as exc:
        raise UsineErreur(
            f"{chemin}, ligne 1 : en-tête de Journal mal formé ({_premiere_erreur(exc)})"
        ) from exc
    evenements: list[Evenement] = []
    for numero, ligne in enumerate(lignes[1:], start=2):
        try:
            evenements.append(Evenement.model_validate_json(ligne))
        except ValidationError as exc:
            raise UsineErreur(
                f"{chemin}, ligne {numero} : événement mal formé ({_premiere_erreur(exc)})"
            ) from exc
    return entete, evenements


def _lire_verite(chemin: Path) -> dict[str, CauseRacine]:
    try:
        return _VERITE.validate_json(chemin.read_bytes())
    except OSError as exc:
        raise UsineErreur(f"{chemin} : vérité terrain illisible ({exc.strerror or exc})") from exc
    except ValidationError as exc:
        raise UsineErreur(
            f"{chemin} : vérité terrain mal formée ({_premiere_erreur(exc)})"
        ) from exc


def corpus_versionne(chemin_corpus: Path) -> tuple[str, str]:
    """`(version_corpus, modele_corpus)` du Corpus de textes versionné ; `UsineErreur` sinon."""
    try:
        donnees = json.loads(chemin_corpus.read_bytes())
    except OSError as exc:
        raise UsineErreur(
            f"{chemin_corpus} : Corpus de textes illisible ({exc.strerror or exc})"
        ) from exc
    except ValueError as exc:
        raise UsineErreur(f"{chemin_corpus} : Corpus de textes mal formé ({exc})") from exc
    version = donnees.get("version_corpus") if isinstance(donnees, dict) else None
    modele = donnees.get("modele_corpus") if isinstance(donnees, dict) else None
    if not isinstance(version, str) or not isinstance(modele, str):
        raise UsineErreur(
            f"{chemin_corpus} : clés « version_corpus » et « modele_corpus » absentes ou non"
            " textuelles"
        )
    return version, modele


def _controler_corpus(entete: EnteteJournal, chemin_journal: Path, chemin_corpus: Path) -> None:
    version, modele = corpus_versionne(chemin_corpus)
    regenerer = (
        "régénérer le Journal avec le Corpus définitif : `usine donnees generer --sortie"
        " <répertoire>`"
    )
    if modele == MODELE_GABARITS:
        raise UsineErreur(
            f"{chemin_corpus} : Corpus provisoire (« modele_corpus » {modele!r}) ; produire le"
            " Corpus définitif avant d'évaluer la classification (AD-19)"
        )
    if entete.modele_corpus == MODELE_GABARITS:
        raise UsineErreur(
            f"{chemin_journal} : Journal généré avec les gabarits provisoires"
            f" (« modele_corpus » {entete.modele_corpus!r}) ; {regenerer}"
        )
    if (entete.version_corpus, entete.modele_corpus) != (version, modele):
        raise UsineErreur(
            f"{chemin_journal} : Journal généré avec le Corpus {entete.version_corpus!r}"
            f" ({entete.modele_corpus!r}), différent du Corpus versionné {version!r}"
            f" ({modele!r}, {chemin_corpus}) ; {regenerer}"
        )


def charger_source_generateur(donnees: Path, chemin_corpus: Path) -> SourceGenerateur:
    """Anomalies et vérité terrain du répertoire `donnees`, contrôlées.

    Refus (`UsineErreur` nommant le fichier) : Journal ou vérité absent ou mal formé, Corpus
    versionné provisoire, Journal d'un autre Corpus ou des gabarits provisoires, clé de vérité
    absente des Anomalies du Journal, Anomalie sans vérité.
    """
    chemin_journal = donnees / CHEMIN_JOURNAL.name
    chemin_verite = donnees / CHEMIN_VERITE_TERRAIN.name
    entete, evenements = _lire_journal(chemin_journal)
    _controler_corpus(entete, chemin_journal, chemin_corpus)
    verite = _lire_verite(chemin_verite)
    textes = tickets_textes(evenements, entete.date_generation).filter(
        pl.col("type_ticket") == TypeTicket.anomalie.value
    )
    anomalies = set(textes["cle_ticket"].to_list())
    hors_journal = sorted(set(verite) - anomalies, key=rang_cle)
    if hors_journal:
        raise UsineErreur(
            f"{chemin_verite} : {len(hors_journal)} clé(s) absente(s) des Anomalies du Journal"
            f" {chemin_journal} ({_extrait(hors_journal)})"
        )
    sans_verite = sorted(anomalies - set(verite), key=rang_cle)
    if sans_verite:
        raise UsineErreur(
            f"{chemin_verite} : {len(sans_verite)} Anomalie(s) du Journal sans vérité terrain"
            f" ({_extrait(sans_verite)})"
        )
    return SourceGenerateur(entete, textes, MappingProxyType(verite), chemin_journal, chemin_verite)
