"""Pseudonymisation par HMAC-SHA256 : base commune et moteur de repli regex (AD-15).

`PseudonymiseurDerive` porte tout ce qui ne dépend pas du détecteur : dérivation des jetons,
protection des clés de ticket, regroupement des chevauchements, table et port
`Pseudonymiseur`. `PseudonymiseurHmac` (moteur de repli, sans Presidio) et
`PseudonymiseurPresidio` (`adaptateurs.presidio`) n'en diffèrent que par la détection.

Chaque plage détectée devient `<TYPE>_<6 hex de HMAC-SHA256(cle, valeur)>`. Le jeton ne
dépend que de la clé (`USINE_CLE_PSEUDO`) et de la valeur : il est stable d'une exécution à
l'autre. Une clé de ticket n'est jamais touchée : seules les parties d'une détection hors
des clés de ticket sont pseudonymisées, chaque fragment restant devenant son propre jeton.
`pseudonymiser` enregistre la correspondance dans la table, `apercu` ne l'enregistre pas,
`reidentifier` la relit.

Les motifs livrés sont dans `config/pseudonymisation.yaml` ; `MOTIFS_PAR_DEFAUT` n'est
qu'un motif d'amorce, utilisé sans ce fichier.
"""

import copy
import hashlib
import hmac
import re
from abc import ABC, abstractmethod
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from typing import Protocol, Self

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    CANDIDAT_JETON,
    LONGUEUR_EMPREINTE_JETON,
    est_type_jeton,
    variantes_jeton,
)
from usine.contrats.tickets import MOTIF_CLE_TICKET

MOTIFS_PAR_DEFAUT: Mapping[str, str] = {"COMPTE": r"FR\d{2}(?: \d{4}){5} \d{3}"}
"""Motif d'amorce, utilisé sans `config/pseudonymisation.yaml`."""

LONGUEUR_MIN_CLE = 16
"""Longueur minimale de `USINE_CLE_PSEUDO`."""

_CLE_TICKET = re.compile(rf"\b{MOTIF_CLE_TICKET}\b")


def verifier_cle(cle: bytes) -> None:
    """Refuse une clé de moins de `LONGUEUR_MIN_CLE` caractères (`UsineErreur`)."""
    if len(cle.strip()) < LONGUEUR_MIN_CLE:
        raise UsineErreur(
            f"USINE_CLE_PSEUDO : clé de Pseudonymisation absente ou trop courte"
            f" (au moins {LONGUEUR_MIN_CLE} caractères)"
        )


def fragments_hors_cles(
    texte: str, debut: int, fin: int, proteges: Sequence[tuple[int, int]]
) -> Iterator[tuple[int, int]]:
    """Parties de `texte[debut:fin]` hors des clés de ticket `proteges`.

    Au contact d'une clé coupée, la ponctuation et les blancs restent en clair, pour que la
    clé reste reconnaissable (`ABC-2024-5678` → `ABC-2024-` + jeton de `5678`).
    """
    morceaux: list[tuple[int, int]] = []
    position = debut
    for d, f in sorted(proteges):
        if f <= position or d >= fin:
            continue
        if d > position:
            morceaux.append((position, d))
        position = max(position, f)
    if position < fin:
        morceaux.append((position, fin))
    fins_de_cle = {f for _, f in proteges}
    debuts_de_cle = {d for d, _ in proteges}
    for gauche, droite in morceaux:
        if gauche in fins_de_cle:
            while gauche < droite and not texte[gauche].isalnum():
                gauche += 1
        if droite in debuts_de_cle:
            while gauche < droite and not texte[droite - 1].isalnum():
                droite -= 1
        if gauche < droite:
            yield gauche, droite


class TablePseudonymes(Protocol):
    """Correspondance jeton → valeur d'origine (satisfaite par `TablePseudonymesSqlite`)."""

    def enregistrer(self, correspondances: Mapping[str, str]) -> None:
        """Enregistre les correspondances ; un jeton lié à une autre valeur est refusé."""
        ...

    def lire(self, jetons: Collection[str]) -> dict[str, str]:
        """Valeurs d'origine des jetons connus."""
        ...


def verifier_types_jeton(types: Collection[str]) -> None:
    """Refuse un type de jeton hors de la grammaire de `contrats.llm` (`UsineErreur`)."""
    invalides = sorted(t for t in types if not est_type_jeton(t))
    if invalides:
        raise UsineErreur(
            f"Pseudonymisation : type de jeton invalide {invalides}"
            " (majuscules et « _ », ex. COMPTE) ; reidentifier ne le reconnaîtrait pas"
        )


class PseudonymiseurDerive(ABC):
    """Base des pseudonymiseurs à jetons HMAC-SHA256 : un seul lieu de dérivation (AD-15).

    Une sous-classe ne fournit que `_detecter` (plages brutes et types de jeton) ; la
    protection des clés de ticket, le regroupement des chevauchements, la dérivation des
    jetons, la table et le port `Pseudonymiseur` sont communs.
    """

    def __init__(self, cle: bytes, table: TablePseudonymes) -> None:
        verifier_cle(cle)
        self._cle = cle
        self._table = table

    def avec_table(self, table: TablePseudonymes) -> Self:
        """Même pseudonymiseur (clé, détecteur partagé) sur une autre table."""
        copie = copy.copy(self)
        copie._table = table
        return copie

    @abstractmethod
    def _detecter(self, texte: str) -> Iterable[tuple[int, int, str]]:
        """Plages `(debut, fin, type_jeton)` détectées dans `texte`, chevauchements permis."""

    def jeton(self, type_jeton: str, valeur: str) -> str:
        """Jeton `<TYPE>_<6 hex>` de `valeur`."""
        empreinte = hmac.new(self._cle, valeur.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{type_jeton}_{empreinte[:LONGUEUR_EMPREINTE_JETON]}"

    def _plages(self, texte: str) -> list[tuple[int, int, str]]:
        """Plages à remplacer, triées et disjointes, avec leur type de jeton.

        Toutes les détections sont collectées ; seule est écartée celle qui tient tout
        entière dans une clé de ticket. Des détections qui se chevauchent forment un
        groupe (de son premier à son dernier caractère), avec le type de jeton de la plus
        longue, pour qu'aucun fragment ne reste en clair. Les clés de ticket sont ensuite
        retirées du groupe : chaque fragment restant est une plage.
        """
        proteges = [m.span() for m in _CLE_TICKET.finditer(texte)]
        trouvees = [
            (debut, fin, type_jeton)
            for debut, fin, type_jeton in self._detecter(texte)
            if debut < fin and not any(d <= debut and fin <= f for d, f in proteges)
        ]
        trouvees.sort(key=lambda t: (t[0], -(t[1] - t[0])))
        groupes: list[tuple[int, int, str]] = []
        longueur_type = 0
        for debut, fin, type_jeton in trouvees:
            if groupes and debut < groupes[-1][1]:
                debut_groupe, fin_groupe, type_groupe = groupes[-1]
                if fin - debut > longueur_type:
                    type_groupe, longueur_type = type_jeton, fin - debut
                groupes[-1] = (debut_groupe, max(fin, fin_groupe), type_groupe)
            else:
                groupes.append((debut, fin, type_jeton))
                longueur_type = fin - debut
        return [
            (d, f, type_groupe)
            for debut, fin, type_groupe in groupes
            for d, f in fragments_hors_cles(texte, debut, fin, proteges)
        ]

    def _remplacer(self, texte: str) -> tuple[str, dict[str, str]]:
        """Texte pseudonymisé et correspondances jeton → valeur de ce texte."""
        retenus = self._plages(texte)
        correspondances: dict[str, str] = {}
        morceaux: list[str] = []
        position = 0
        for debut, fin, type_jeton in retenus:
            valeur = texte[debut:fin]
            jeton = self.jeton(type_jeton, valeur)
            if correspondances.setdefault(jeton, valeur) != valeur:
                raise UsineErreur(f"Pseudonymisation : collision de jeton {jeton}")
            morceaux.extend((texte[position:debut], jeton))
            position = fin
        morceaux.append(texte[position:])
        return "".join(morceaux), correspondances

    def pseudonymiser(self, texte: str) -> str:
        """Texte pseudonymisé ; la correspondance est enregistrée dans la table."""
        sortie, correspondances = self._remplacer(texte)
        self._table.enregistrer(correspondances)
        return sortie

    def reidentifier(self, texte: str) -> str:
        """Remplace, localement, les jetons connus de la table ; les autres restent tels quels.

        Un jeton collé à des lettres ou précédé d'un préfixe `MAJUSCULES_` (`ID_COMPTE_abc123`)
        est reconnu : la plus longue variante connue de la table est remplacée, le préfixe
        reste.
        """
        candidats = list(CANDIDAT_JETON.finditer(texte))
        if not candidats:
            return texte
        valeurs = self._table.lire({v for c in candidats for v in variantes_jeton(c)})

        def remplacer(candidat: re.Match[str]) -> str:
            for variante in variantes_jeton(candidat):
                if variante in valeurs:
                    return candidat.group(0)[: -len(variante)] + valeurs[variante]
            return candidat.group(0)

        return CANDIDAT_JETON.sub(remplacer, texte)

    def apercu(self, texte: str) -> str:
        """Comme `pseudonymiser`, sans écrire la table (FR-31)."""
        return self._remplacer(texte)[0]


class PseudonymiseurHmac(PseudonymiseurDerive):
    """Pseudonymiseur par motifs et HMAC-SHA256 ; correspondance gardée dans `table`."""

    def __init__(self, cle: bytes, motifs: Mapping[str, str], table: TablePseudonymes) -> None:
        super().__init__(cle, table)
        verifier_types_jeton(motifs)
        try:
            self._motifs = [(type_jeton, re.compile(motif)) for type_jeton, motif in motifs.items()]
        except re.error as exc:
            raise UsineErreur(f"Pseudonymisation : motif invalide ({exc})") from exc

    def _detecter(self, texte: str) -> Iterator[tuple[int, int, str]]:
        for type_jeton, motif in self._motifs:
            for trouve in motif.finditer(texte):
                yield (*trouve.span(), type_jeton)
