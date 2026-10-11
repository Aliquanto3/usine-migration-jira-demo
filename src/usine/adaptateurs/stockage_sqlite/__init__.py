"""Stockage SQLite : cache LLM et table des pseudonymes (AD-12, AD-15).

- `CacheLLMSqlite` (`donnees/cache_llm.sqlite`) satisfait structurellement
  `usine.ia.passerelle.CacheLLM` ; seule la passerelle LLM y accède.
- `TablePseudonymesSqlite` (`donnees/pseudonymes.sqlite`) garde la correspondance
  jeton → valeur d'origine, pour la ré-identification locale ; hors git.

Chaque base est en mode WAL ; la connexion est ouverte et fermée à chaque opération (rien ne
reste ouvert, ce qui compte sous Windows). Toute erreur `sqlite3` devient une `UsineErreur`
qui nomme le fichier.
"""

import sqlite3
from collections.abc import Callable, Collection, Mapping
from contextlib import closing
from pathlib import Path

from usine.contrats.erreurs import UsineErreur


class _BaseSqlite:
    """Fichier SQLite en mode WAL, une connexion par opération, erreurs nommant le fichier."""

    def __init__(self, chemin: Path, quoi: str, creer_table: str) -> None:
        self._chemin = chemin
        self._quoi = quoi
        try:
            chemin.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise UsineErreur(
                f"{chemin} : création du répertoire du {quoi} impossible ({exc.strerror or exc})"
            ) from exc

        def initialiser(connexion: sqlite3.Connection) -> str:
            (mode,) = connexion.execute("PRAGMA journal_mode=WAL").fetchone()
            connexion.execute(creer_table)
            return str(mode).lower()

        mode = self._operation(initialiser, "initialisation")
        if mode != "wal":
            raise UsineErreur(f"{chemin} : {quoi}, mode WAL refusé (journal_mode = {mode})")

    @property
    def chemin(self) -> Path:
        """Fichier SQLite."""
        return self._chemin

    def _operation[R](self, operation: Callable[[sqlite3.Connection], R], quoi: str) -> R:
        """Ouvre la base, exécute `operation` dans une transaction, puis ferme la connexion."""
        try:
            with closing(sqlite3.connect(self._chemin)) as connexion, connexion:
                return operation(connexion)
        except sqlite3.Error as exc:
            raise UsineErreur(f"{self._chemin} : {self._quoi}, {quoi} impossible ({exc})") from exc


class CacheLLMSqlite(_BaseSqlite):
    """Cache `(cle TEXT PRIMARY KEY, brut TEXT)` dans un fichier SQLite en mode WAL."""

    def __init__(self, chemin: Path) -> None:
        super().__init__(
            chemin,
            "cache LLM",
            "CREATE TABLE IF NOT EXISTS cache_llm (cle TEXT PRIMARY KEY, brut TEXT NOT NULL)",
        )

    def lire(self, cle: str) -> str | None:
        """Réponse brute enregistrée sous `cle`, ou `None`."""

        def lire(connexion: sqlite3.Connection) -> str | None:
            ligne = connexion.execute("SELECT brut FROM cache_llm WHERE cle = ?", (cle,)).fetchone()
            return None if ligne is None else str(ligne[0])

        return self._operation(lire, "lecture")

    def ecrire(self, cle: str, brut: str) -> None:
        """Enregistre (ou remplace) la réponse brute sous `cle`."""

        def ecrire(connexion: sqlite3.Connection) -> None:
            connexion.execute(
                "INSERT OR REPLACE INTO cache_llm (cle, brut) VALUES (?, ?)", (cle, brut)
            )

        self._operation(ecrire, "écriture")


class TablePseudonymesSqlite(_BaseSqlite):
    """Table `(jeton TEXT PRIMARY KEY, valeur TEXT)` dans un fichier SQLite en mode WAL."""

    def __init__(self, chemin: Path) -> None:
        super().__init__(
            chemin,
            "table des pseudonymes",
            "CREATE TABLE IF NOT EXISTS pseudonymes (jeton TEXT PRIMARY KEY, valeur TEXT NOT NULL)",
        )

    def enregistrer(self, correspondances: Mapping[str, str]) -> None:
        """Enregistre chaque `jeton → valeur` ; un jeton déjà lié à une autre valeur est refusé.

        L'erreur de collision nomme le jeton, jamais la valeur. Rien n'est écrit en cas d'échec.
        """
        if not correspondances:
            return

        def enregistrer(connexion: sqlite3.Connection) -> list[str]:
            collisions: list[str] = []
            for jeton, valeur in correspondances.items():
                connexion.execute(
                    "INSERT OR IGNORE INTO pseudonymes (jeton, valeur) VALUES (?, ?)",
                    (jeton, valeur),
                )
                (connue,) = connexion.execute(
                    "SELECT valeur FROM pseudonymes WHERE jeton = ?", (jeton,)
                ).fetchone()
                if connue != valeur:
                    collisions.append(jeton)
            if collisions:
                connexion.rollback()
            return collisions

        collisions = self._operation(enregistrer, "écriture")
        if collisions:
            raise UsineErreur(
                f"{self._chemin} : collision de jeton {', '.join(sorted(collisions))}"
                " entre deux valeurs"
            )

    def lire(self, jetons: Collection[str]) -> dict[str, str]:
        """Valeurs d'origine des `jetons` connus ; les jetons inconnus sont absents."""
        if not jetons:
            return {}
        uniques = sorted(set(jetons))

        def lire(connexion: sqlite3.Connection) -> dict[str, str]:
            trouves: dict[str, str] = {}
            for jeton in uniques:
                ligne = connexion.execute(
                    "SELECT valeur FROM pseudonymes WHERE jeton = ?", (jeton,)
                ).fetchone()
                if ligne is not None:
                    trouves[jeton] = str(ligne[0])
            return trouves

        return self._operation(lire, "lecture")
