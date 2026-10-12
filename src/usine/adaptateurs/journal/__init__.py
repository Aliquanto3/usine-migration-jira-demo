"""Adaptateur `SourceJournal` : `SourceTickets` sur un Journal JSONL (FR-8, AD-3, AD-4).

Le Journal est un fichier UTF-8 : un `EnteteJournal` en première ligne, puis un `Evenement`
par ligne, par horodatage croissant. Toute anomalie de lecture devient une `UsineErreur` qui
nomme le fichier et, pour une ligne, son numéro (1 = en-tête).

Avec un `ManifesteInjection` (`charger_manifeste`, `CHEMIN_MANIFESTE_INJECTION`), chaque
`cle_ticket` est remplacée par sa clé Jira (`correspondance_cles`) : la clé canonique en aval
est la clé Jira (AD-4). Les autres champs, dont `id_evenement` et l'ordre, sont inchangés.
"""

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from usine.adaptateurs.journal.manifeste import CHEMIN_MANIFESTE_INJECTION, charger_manifeste
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import EnteteJournal, Evenement, ManifesteInjection

__all__ = ["CHEMIN_MANIFESTE_INJECTION", "SourceJournal", "charger_manifeste"]


def _motifs(exc: ValidationError) -> str:
    """Résumé des erreurs Pydantic : `champ : message`, séparés par « ; »."""
    return " ; ".join(
        f"{'.'.join(str(partie) for partie in err['loc']) or '(ligne)'} : {err['msg']}"
        for err in exc.errors()
    )


class SourceJournal:
    """Lit et valide le Journal à la construction, puis rend ses événements à la demande.

    Avec `manifeste`, les clés générées sont remplacées par les clés Jira ; une clé absente de
    `correspondance_cles` ou une Date d'injection différente de celle de l'en-tête lève une
    `UsineErreur`.
    """

    def __init__(self, chemin: Path, manifeste: ManifesteInjection | None = None) -> None:
        self._chemin = chemin
        self._manifeste = manifeste
        # Découpe sur « \n » seul : `splitlines` couperait aussi sur U+2028, U+0085, etc.,
        # que `model_dump_json` laisse tels quels dans les chaînes.
        lignes = self._lire().split("\n")
        if lignes and lignes[-1] == "":
            lignes.pop()
        if not lignes or not lignes[0].strip():
            raise UsineErreur(f"{chemin} : en-tête du Journal manquant (ligne 1)")
        self._entete = self._valider(1, lignes[0], EnteteJournal, "en-tête invalide")
        correspondance = None if manifeste is None else manifeste.correspondance_cles
        if manifeste is not None and manifeste.date_injection != self._entete.date_injection:
            raise UsineErreur(
                f"{chemin} : Date d'injection du manifeste"
                f" ({manifeste.date_injection.isoformat()}) différente de celle de l'en-tête"
                f" du Journal ({self._entete.date_injection.isoformat()})"
            )
        evenements: list[Evenement] = []
        vus: set[str] = set()
        cles_lues: set[str] = set()
        for numero, ligne in enumerate(lignes[1:], start=2):
            if not ligne.strip():
                raise UsineErreur(f"{chemin} : ligne {numero} vide")
            evenement = self._valider(numero, ligne, Evenement, "événement invalide")
            if evenement.id_evenement in vus:
                raise UsineErreur(
                    f"{chemin} : ligne {numero} : id_evenement {evenement.id_evenement!r} en double"
                )
            if evenements and evenement.horodatage < evenements[-1].horodatage:
                raise UsineErreur(
                    f"{chemin} : ligne {numero} : horodatage"
                    f" {evenement.horodatage.isoformat()} antérieur à celui de la ligne"
                    f" précédente (ordre croissant attendu)"
                )
            vus.add(evenement.id_evenement)
            if correspondance is not None:
                cles_lues.add(evenement.cle_ticket)
                cle_jira = correspondance.get(evenement.cle_ticket)
                if cle_jira is None:
                    raise UsineErreur(
                        f"{chemin} : ligne {numero} : clé {evenement.cle_ticket!r} absente de"
                        " la correspondance des clés du manifeste d'injection"
                    )
                evenement = evenement.model_copy(update={"cle_ticket": cle_jira})
            evenements.append(evenement)
        if correspondance is not None:
            surplus = sorted(set(correspondance) - cles_lues)
            if surplus:
                listees = ", ".join(surplus[:5])
                reste = f" et {len(surplus) - 5} autre(s)" if len(surplus) > 5 else ""
                raise UsineErreur(
                    f"{chemin} : {len(surplus)} clé(s) du manifeste d'injection absente(s) du"
                    f" Journal ({listees}{reste}) : manifeste d'une autre génération ?"
                )
        self._evenements = tuple(evenements)

    def _lire(self) -> str:
        try:
            return self._chemin.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise UsineErreur(f"{self._chemin} : Journal introuvable") from exc
        except UnicodeDecodeError as exc:
            raise UsineErreur(
                f"{self._chemin} : Journal non encodé en UTF-8 (octet {exc.start})"
            ) from exc
        except OSError as exc:
            raise UsineErreur(
                f"{self._chemin} : Journal illisible ({exc.strerror or exc})"
            ) from exc

    def _valider[M: (EnteteJournal, Evenement)](
        self, numero: int, ligne: str, modele: type[M], quoi: str
    ) -> M:
        try:
            donnees = json.loads(ligne)
        except json.JSONDecodeError as exc:
            raise UsineErreur(
                f"{self._chemin} : ligne {numero} : {quoi}, JSON illisible ({exc.msg})"
            ) from exc
        if not isinstance(donnees, dict):
            raise UsineErreur(
                f"{self._chemin} : ligne {numero} : {quoi}, objet JSON attendu"
                f" ({type(donnees).__name__} reçu)"
            )
        try:
            return modele.model_validate(donnees)
        except ValidationError as exc:
            raise UsineErreur(f"{self._chemin} : ligne {numero} : {quoi} ({_motifs(exc)})") from exc

    @property
    def chemin(self) -> Path:
        """Chemin du Journal lu."""
        return self._chemin

    @property
    def manifeste(self) -> ManifesteInjection | None:
        """Manifeste d'injection appliqué à la lecture (`None` : clés générées)."""
        return self._manifeste

    @property
    def entete(self) -> EnteteJournal:
        """En-tête du Journal (paramètres de génération)."""
        return self._entete

    def evenements(self, depuis: datetime | None = None) -> Iterator[Evenement]:
        """Événements d'horodatage ≥ `depuis` (tous si `None`), dans l'ordre du fichier."""
        if depuis is not None and (depuis.tzinfo is None or depuis.utcoffset() is None):
            raise UsineErreur(f"{self._chemin} : « depuis » sans fuseau : {depuis!r}")
        for evenement in self._evenements:
            if depuis is None or evenement.horodatage >= depuis:
                yield evenement
