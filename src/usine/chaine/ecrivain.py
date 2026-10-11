"""`EcrivainPassage` : seul écrivain des fichiers d'un Passage (AD-7, AD-8, AD-22).

Le Passage est construit dans `sorties/passages/.en-cours-<passage_id>/`, puis publié par un
seul renommage vers `sorties/passages/<date_arrete>/<passage_id>/` ; en échec, il est déplacé
sous `sorties/echecs/<passage_id>/`. La progression est tenue hors du Passage, dans
`sorties/progression/<passage_id>.jsonl`. Chaque fichier est écrit en ouvrir-écrire-fermer :
rien ne reste ouvert au moment du renommage (Windows).
"""

from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType

import polars as pl

from usine.contrats.calcul import SCHEMA_INDICATEUR, SCHEMA_INSTANTANE, SCHEMA_KPI, SCHEMA_TENDANCE
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import SCHEMA_REPARTITION_CAUSES
from usine.contrats.passage import (
    CONTENUS_JSON,
    EnveloppeFichier,
    Etape,
    EvenementProgression,
    ManifestePassage,
    StatutEtape,
    chemin_fichier_passage,
    est_du_type,
)
from usine.contrats.schemas import SchemaTable, valider
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, SCHEMA_TICKET_TEXTE
from usine.contrats.trace import EntreeTrace, TypeTrace
from usine.contrats.versions import CLE_VERSION, CONTRATS_VERSION

SCHEMAS_TABLES: Mapping[str, SchemaTable] = MappingProxyType(
    {
        "tickets_etats": SCHEMA_TICKET_ETAT,
        "tickets_textes": SCHEMA_TICKET_TEXTE,
        "instantanes": SCHEMA_INSTANTANE,
        "kpi": SCHEMA_KPI,
        "indicateurs": SCHEMA_INDICATEUR,
        "tendances": SCHEMA_TENDANCE,
        "repartition_causes": SCHEMA_REPARTITION_CAUSES,
    }
)
"""Schéma de chaque table Parquet d'un Passage, par nom logique de `FICHIERS_PASSAGE`."""

FICHIERS_TRACE: Mapping[TypeTrace, str] = MappingProxyType(
    {TypeTrace.llm: "trace_llm", TypeTrace.prevision: "trace_previsions"}
)
"""Fichier de traces (nom logique) de chaque type d'`EntreeTrace`."""

_RESERVES = frozenset({"manifeste", *FICHIERS_TRACE.values()})
"""Fichiers écrits par l'écrivain lui-même, jamais rendus comme sortie d'étape."""

PREFIXE_EN_COURS = ".en-cours-"
"""Préfixe du répertoire d'un Passage en construction."""


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _ajouter_ligne(chemin: Path, ligne: str) -> None:
    """Ajoute une ligne à `chemin` en ouvrir-ajouter-fermer."""
    with chemin.open("a", encoding="utf-8", newline="\n") as fichier:
        fichier.write(ligne + "\n")


class EcrivainPassage:
    """Construit, publie ou abandonne un Passage sous `racine_sorties`."""

    def __init__(self, racine_sorties: Path, horloge: Callable[[], datetime] = _maintenant) -> None:
        self._racine = racine_sorties
        self._horloge = horloge
        self._passage_id: str | None = None
        self._date_arrete: date | None = None
        self._ecrits: set[str] = set()
        self._publie: Path | None = None
        self._termine: str | None = None
        """`publié` ou `abandonné` : plus aucune écriture dans le Passage."""

    # --- Chemins ---

    @property
    def racine_sorties(self) -> Path:
        """Racine des sorties (`sorties/`)."""
        return self._racine

    @property
    def passage_id(self) -> str:
        """Identifiant du Passage en cours."""
        if self._passage_id is None:
            raise UsineErreur("aucun Passage commencé par l'écrivain")
        return self._passage_id

    @property
    def date_arrete(self) -> date:
        """Date d'arrêté du Passage en cours."""
        if self._date_arrete is None:
            raise UsineErreur("aucun Passage commencé par l'écrivain")
        return self._date_arrete

    @property
    def repertoire(self) -> Path:
        """Répertoire de construction `sorties/passages/.en-cours-<passage_id>/`."""
        return self._racine / "passages" / f"{PREFIXE_EN_COURS}{self.passage_id}"

    @property
    def chemin_progression(self) -> Path:
        """Fichier de progression `sorties/progression/<passage_id>.jsonl`, hors du Passage."""
        return self._racine / "progression" / f"{self.passage_id}.jsonl"

    @property
    def ecrits(self) -> frozenset[str]:
        """Noms logiques des fichiers déjà écrits dans le Passage en cours."""
        return frozenset(self._ecrits)

    def _en_construction(self) -> Path:
        """Répertoire de construction ; refuse toute écriture après publication ou abandon."""
        if self._termine is not None:
            raise UsineErreur(
                f"Passage {self.passage_id} déjà {self._termine} : plus aucune écriture permise"
            )
        return self.repertoire

    # --- Cycle de vie ---

    def commencer(self, passage_id: str, date_arrete: date) -> Path:
        """Crée le répertoire `.en-cours-<passage_id>` et renvoie son chemin."""
        if self._passage_id is not None:
            raise UsineErreur(f"écrivain déjà engagé sur le Passage {self._passage_id}")
        self._passage_id, self._date_arrete = passage_id, date_arrete
        repertoire = self.repertoire
        try:
            repertoire.mkdir(parents=True, exist_ok=False)
            self.chemin_progression.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise UsineErreur(
                f"{repertoire} : création du Passage impossible ({exc.strerror or exc})"
            ) from exc
        return repertoire

    def progression(self, etape: Etape, statut: StatutEtape, message: str = "") -> None:
        """Ajoute une ligne `EvenementProgression` au fichier de progression."""
        evenement = EvenementProgression(
            passage_id=self.passage_id,
            etape=etape,
            statut=statut,
            horodatage=self._horloge(),
            message=message,
        )
        _ajouter_ligne(self.chemin_progression, evenement.model_dump_json())

    def ecrire(self, sorties: Mapping[str, object]) -> None:
        """Écrit les sorties nommées d'une étape dans le Passage en construction.

        Table : validée par son `SCHEMA_X` puis écrite en Parquet avec `contrats_version` en
        métadonnée ; JSON de `CONTENUS_JSON` : écrit dans une `EnveloppeFichier` ; autre
        fichier : `bytes` écrits tels quels. Un fichier n'est écrit qu'une fois.
        """
        for nom, valeur in sorties.items():
            self._en_construction()
            if nom in _RESERVES:
                raise UsineErreur(f"sortie « {nom} » réservée à l'écrivain du Passage")
            if nom in self._ecrits:
                raise UsineErreur(f"sortie « {nom} » déjà écrite dans le Passage")
            chemin = self.repertoire / chemin_fichier_passage(nom, self.date_arrete)
            chemin.parent.mkdir(parents=True, exist_ok=True)
            if nom in SCHEMAS_TABLES:
                if not isinstance(valeur, pl.DataFrame):
                    raise UsineErreur(
                        f"sortie « {nom} » : polars.DataFrame attendu, pas {type(valeur).__name__}"
                    )
                table = valider(valeur, SCHEMAS_TABLES[nom])
                table.write_parquet(chemin, metadata={CLE_VERSION: CONTRATS_VERSION})
            elif nom in CONTENUS_JSON:
                type_contenu = CONTENUS_JSON[nom]
                if not est_du_type(valeur, type_contenu):
                    raise UsineErreur(
                        f"sortie « {nom} » de type {type(valeur).__name__}, attendu {type_contenu}"
                    )
                modele: type[EnveloppeFichier[object]] = EnveloppeFichier[type_contenu]  # type: ignore[valid-type]
                enveloppe = modele(
                    passage_id=self.passage_id, date_arrete=self.date_arrete, contenu=valeur
                )
                chemin.write_bytes(enveloppe.model_dump_json(indent=2).encode("utf-8"))
            elif isinstance(valeur, bytes):
                chemin.write_bytes(valeur)
            else:
                raise UsineErreur(
                    f"sortie « {nom} » : octets attendus, pas {type(valeur).__name__}"
                )
            self._ecrits.add(nom)

    def ajouter_traces(self, traces: Iterable[EntreeTrace]) -> None:
        """Ajoute chaque trace à `trace/llm.jsonl` ou `trace/previsions.jsonl`."""
        for trace in traces:
            self._en_construction()
            if trace.passage_id != self.passage_id:
                raise UsineErreur(
                    f"trace du Passage {trace.passage_id} ajoutée au Passage {self.passage_id}"
                )
            nom = FICHIERS_TRACE[trace.type_trace]
            chemin = self.repertoire / chemin_fichier_passage(nom, self.date_arrete)
            chemin.parent.mkdir(parents=True, exist_ok=True)
            _ajouter_ligne(chemin, trace.model_dump_json())
            self._ecrits.add(nom)

    def publier(self, manifeste: ManifestePassage) -> Path:
        """Écrit le manifeste en dernier, puis publie le Passage par un seul renommage."""
        self._en_construction()
        if manifeste.passage_id != self.passage_id or manifeste.date_arrete != self.date_arrete:
            raise UsineErreur(
                f"manifeste du Passage {manifeste.passage_id} ({manifeste.date_arrete})"
                f" publié pour le Passage {self.passage_id} ({self.date_arrete})"
            )
        chemin = self.repertoire / chemin_fichier_passage("manifeste", self.date_arrete)
        chemin.write_bytes(manifeste.model_dump_json(indent=2).encode("utf-8"))
        self._ecrits.add("manifeste")
        self._publie = self._deplacer(self.chemin_publication, "publication")
        self._termine = "publié"
        return self._publie

    @property
    def chemin_publication(self) -> Path:
        """Répertoire de publication `sorties/passages/<date_arrete>/<passage_id>/`."""
        return self._racine / "passages" / self.date_arrete.isoformat() / self.passage_id

    @property
    def repertoire_publie(self) -> Path | None:
        """Répertoire du Passage publié, `None` tant qu'il ne l'est pas."""
        return self._publie

    def abandonner(self) -> Path | None:
        """Déplace le Passage en construction sous `sorties/echecs/<passage_id>/`."""
        if self._passage_id is None or self._termine is not None or not self.repertoire.exists():
            return None
        cible = self._deplacer(self._racine / "echecs" / self.passage_id, "abandon")
        self._termine = "abandonné"
        return cible

    def _deplacer(self, cible: Path, quoi: str) -> Path:
        try:
            cible.parent.mkdir(parents=True, exist_ok=True)
            self.repertoire.rename(cible)
        except OSError as exc:
            raise UsineErreur(
                f"{quoi} du Passage {self.passage_id} vers {cible} impossible"
                f" ({exc.strerror or exc})"
            ) from exc
        return cible
