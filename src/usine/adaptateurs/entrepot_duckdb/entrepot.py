"""`EntrepotDuckDB` : port `EntrepotExtraction` sur `donnees/entrepot.duckdb` (AD-6, AD-9).

Deux tables : `evenements` (une colonne par champ d'`Evenement`, clé `id_evenement`, plus le
numéro de lot et le rang dans le lot, qui donnent l'ordre d'insertion) et `repere` (une ligne).
DuckDB stocke et relit, sans agrégat ni calcul : le dédoublonnage du lot se fait en Polars, le
rejet des identifiants déjà stockés par `ON CONFLICT DO NOTHING` (le premier stocké gagne).

Horodatages en `TIMESTAMP` naïfs exprimés en UTC (relire un `TIMESTAMPTZ` exigerait une
bibliothèque de fuseaux absente des dépendances), relus avec le fuseau UTC. Chaque opération
ouvre puis ferme sa connexion (rien ne reste ouvert, ce qui compte sous Windows) ; toute
erreur `duckdb` devient une `UsineErreur` qui nomme le fichier.
"""

from collections.abc import Callable, Iterable, Iterator
from contextlib import closing, suppress
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import polars as pl
from pydantic import ValidationError

from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, evenements_en_table
from usine.contrats.passage import REPERTOIRE_DONNEES

CHEMIN_ENTREPOT = REPERTOIRE_DONNEES / "entrepot.duckdb"
"""Entrepôt d'extraction, ouvert par la seule étape `extraction` (AD-6)."""

_COLONNES = (
    "id_evenement",
    "cle_ticket",
    "type_ticket",
    "horodatage",
    "nature",
    "champ",
    "de",
    "vers",
    "source",
)
_LISTE_COLONNES = ", ".join(_COLONNES)

_CREER = (
    "CREATE SEQUENCE IF NOT EXISTS lots_evenements START 1",
    "CREATE TABLE IF NOT EXISTS evenements ("
    " id_evenement VARCHAR PRIMARY KEY,"
    " cle_ticket VARCHAR NOT NULL,"
    " type_ticket VARCHAR NOT NULL,"
    " horodatage TIMESTAMP NOT NULL,"
    " nature VARCHAR NOT NULL,"
    " champ VARCHAR,"
    " de VARCHAR,"
    " vers VARCHAR,"
    " source VARCHAR NOT NULL,"
    " lot BIGINT NOT NULL,"
    " rang BIGINT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS repere ("
    " cle INTEGER PRIMARY KEY CHECK (cle = 1),"
    " instant TIMESTAMP NOT NULL)",
)
_LIRE_REPERE = "SELECT instant FROM repere WHERE cle = 1"
_ECRIRE_REPERE = "INSERT OR REPLACE INTO repere (cle, instant) VALUES (1, ?)"
_NOUVEAU_LOT = "SELECT nextval('lots_evenements')"
_INSERER = (
    f"INSERT INTO evenements ({_LISTE_COLONNES}, lot, rang)"
    f" SELECT {_LISTE_COLONNES}, lot, rang FROM lot_evenements ON CONFLICT DO NOTHING"
)
_LIRE_EVENEMENTS = f"SELECT {_LISTE_COLONNES} FROM evenements ORDER BY horodatage, lot, rang"


def _en_utc_naif(instant: datetime) -> datetime:
    return instant.astimezone(UTC).replace(tzinfo=None)


def _table_du_lot(evenements: Iterable[Evenement], lot: int) -> pl.DataFrame:
    """Lot dédoublonné par `id_evenement` (le premier gagne), en colonnes texte et UTC naïf."""
    table = evenements_en_table(evenements).unique(
        subset="id_evenement", keep="first", maintain_order=True
    )
    return table.select(
        pl.col("id_evenement"),
        pl.col("cle_ticket"),
        pl.col("type_ticket").cast(pl.Utf8),
        pl.col("horodatage").dt.convert_time_zone("UTC").dt.replace_time_zone(None),
        pl.col("nature").cast(pl.Utf8),
        pl.col("champ").cast(pl.Utf8),
        pl.col("de"),
        pl.col("vers"),
        pl.col("source").cast(pl.Utf8),
        pl.lit(lot, dtype=pl.Int64).alias("lot"),
        pl.int_range(pl.len(), dtype=pl.Int64).alias("rang"),
    )


class EntrepotDuckDB:
    """Événements extraits et repère d'extraction dans un fichier DuckDB."""

    def __init__(self, chemin: Path) -> None:
        self._chemin = chemin
        try:
            chemin.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise UsineErreur(
                f"{chemin} : création du répertoire de l'entrepôt impossible"
                f" ({exc.strerror or exc})"
            ) from exc

        def initialiser(connexion: duckdb.DuckDBPyConnection) -> None:
            for instruction in _CREER:
                connexion.execute(instruction)

        self._operation(initialiser, "initialisation")

    @property
    def chemin(self) -> Path:
        """Fichier DuckDB."""
        return self._chemin

    def _operation[R](self, operation: Callable[[duckdb.DuckDBPyConnection], R], quoi: str) -> R:
        """Ouvre l'entrepôt, exécute `operation` dans une transaction, puis ferme la connexion.

        Toute exception annule la transaction ; une erreur `duckdb` devient une `UsineErreur`.
        """
        try:
            with closing(duckdb.connect(str(self._chemin))) as connexion:
                connexion.execute("BEGIN TRANSACTION")
                try:
                    resultat = operation(connexion)
                except BaseException:
                    # Un échec du ROLLBACK ne doit pas masquer l'exception d'origine.
                    with suppress(duckdb.Error):
                        connexion.execute("ROLLBACK")
                    raise
                connexion.execute("COMMIT")
                return resultat
        except duckdb.Error as exc:
            raise UsineErreur(
                f"{self._chemin} : entrepôt d'extraction, {quoi} impossible ({exc})"
            ) from exc

    def repere(self) -> datetime | None:
        """Repère de la dernière extraction validée (`None` avant la première), en UTC."""

        def lire(connexion: duckdb.DuckDBPyConnection) -> datetime | None:
            ligne = connexion.execute(_LIRE_REPERE).fetchone()
            if ligne is None:
                return None
            instant = ligne[0]
            if not isinstance(instant, datetime):
                raise UsineErreur(f"{self._chemin} : repère illisible ({instant!r})")
            return instant.replace(tzinfo=UTC)

        return self._operation(lire, "lecture du repère")

    def enregistrer(self, evenements: Iterable[Evenement], repere: datetime) -> int:
        """Enregistre événements et repère dans une même transaction ; renvoie le nombre d'ajouts.

        Dédoublonnage par `id_evenement`, doublons du lot compris : un événement déjà stocké
        n'est jamais modifié. L'itérable est consommé dans la transaction ; toute exception,
        y compris pendant sa consommation, annule tout. Un repère sans fuseau est refusé.
        """
        if repere.tzinfo is None or repere.utcoffset() is None:
            raise UsineErreur(f"{self._chemin} : repère sans fuseau refusé ({repere!r})")
        instant = _en_utc_naif(repere)

        def enregistrer(connexion: duckdb.DuckDBPyConnection) -> int:
            ligne_lot = connexion.execute(_NOUVEAU_LOT).fetchone()
            if ligne_lot is None:
                raise UsineErreur(f"{self._chemin} : numéro de lot indisponible")
            lot_evenements = _table_du_lot(evenements, int(ligne_lot[0]))
            ajouts = 0
            if lot_evenements.height:
                connexion.register("lot_evenements", lot_evenements)
                ligne = connexion.execute(_INSERER).fetchone()
                connexion.unregister("lot_evenements")
                ajouts = 0 if ligne is None else int(ligne[0])
            connexion.execute(_ECRIRE_REPERE, [instant])
            return ajouts

        return self._operation(enregistrer, "enregistrement")

    def evenements(self) -> Iterator[Evenement]:
        """Tous les événements stockés, par horodatage puis ordre d'insertion."""

        def lire(connexion: duckdb.DuckDBPyConnection) -> list[tuple[object, ...]]:
            return connexion.execute(_LIRE_EVENEMENTS).fetchall()

        lignes = self._operation(lire, "lecture des événements")
        for ligne in lignes:
            valeurs = dict(zip(_COLONNES, ligne, strict=True))
            horodatage = valeurs["horodatage"]
            if not isinstance(horodatage, datetime):
                raise UsineErreur(f"{self._chemin} : horodatage illisible ({horodatage!r})")
            valeurs["horodatage"] = horodatage.replace(tzinfo=UTC)
            try:
                evenement = Evenement.model_validate(valeurs)
            except ValidationError as exc:
                raise UsineErreur(
                    f"{self._chemin} : événement stocké illisible"
                    f" ({valeurs['id_evenement']!r}) : {exc}"
                ) from exc
            yield evenement
