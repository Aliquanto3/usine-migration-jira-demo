"""Pseudonymisation par expressions régulières et HMAC-SHA256, sans Presidio (AD-15).

`PseudonymiseurHmac` implémente le port `Pseudonymiseur` : chaque correspondance d'un motif
devient `<TYPE>_<6 hex de HMAC-SHA256(cle, valeur)>`. Le jeton ne dépend que de la clé
(`USINE_CLE_PSEUDO`) et de la valeur : il est stable d'une exécution à l'autre. Une clé de
ticket n'est jamais touchée. `pseudonymiser` enregistre la correspondance dans la table,
`apercu` ne l'enregistre pas, `reidentifier` la relit.

Les reconnaisseurs Presidio et les motifs définitifs relèvent de la lane L6 ;
`MOTIFS_PAR_DEFAUT` n'est qu'un motif d'amorce.
"""

import hashlib
import hmac
import re
from collections.abc import Collection, Mapping
from typing import Protocol

from usine.contrats.erreurs import UsineErreur
from usine.contrats.tickets import MOTIF_CLE_TICKET

MOTIFS_PAR_DEFAUT: Mapping[str, str] = {"COMPTE": r"FR\d{2}(?: \d{4}){5} \d{3}"}
"""Motifs d'amorce, sans `config/pseudonymisation.yaml` ; remplacés par la lane L6."""

LONGUEUR_EMPREINTE = 6
"""Nombre de caractères hexadécimaux du HMAC gardés dans le jeton."""

_CLE_TICKET = re.compile(rf"\b{MOTIF_CLE_TICKET}\b")
_MOTIF_TYPE_JETON = r"[A-Z](?:[A-Z_]*[A-Z])?"
_TYPE_JETON = re.compile(_MOTIF_TYPE_JETON)
_JETON = re.compile(rf"\b{_MOTIF_TYPE_JETON}_[0-9a-f]{{{LONGUEUR_EMPREINTE}}}\b")


class TablePseudonymes(Protocol):
    """Correspondance jeton → valeur d'origine (satisfaite par `TablePseudonymesSqlite`)."""

    def enregistrer(self, correspondances: Mapping[str, str]) -> None:
        """Enregistre les correspondances ; un jeton lié à une autre valeur est refusé."""
        ...

    def lire(self, jetons: Collection[str]) -> dict[str, str]:
        """Valeurs d'origine des jetons connus."""
        ...


class PseudonymiseurHmac:
    """Pseudonymiseur par motifs et HMAC-SHA256 ; correspondance gardée dans `table`."""

    def __init__(self, cle: bytes, motifs: Mapping[str, str], table: TablePseudonymes) -> None:
        if not cle:
            raise UsineErreur("USINE_CLE_PSEUDO : clé de Pseudonymisation vide")
        self._cle = cle
        invalides = sorted(t for t in motifs if not _TYPE_JETON.fullmatch(t))
        if invalides:
            raise UsineErreur(
                f"Pseudonymisation : type de jeton invalide {invalides}"
                " (majuscules et « _ », ex. COMPTE) ; reidentifier ne le reconnaîtrait pas"
            )
        try:
            self._motifs = [(type_jeton, re.compile(motif)) for type_jeton, motif in motifs.items()]
        except re.error as exc:
            raise UsineErreur(f"Pseudonymisation : motif invalide ({exc})") from exc
        self._table = table

    def jeton(self, type_jeton: str, valeur: str) -> str:
        """Jeton `<TYPE>_<6 hex>` de `valeur`."""
        empreinte = hmac.new(self._cle, valeur.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{type_jeton}_{empreinte[:LONGUEUR_EMPREINTE]}"

    def _plages(self, texte: str) -> list[tuple[int, int, str]]:
        """Plages à remplacer, triées et disjointes, avec leur type de jeton.

        Toutes les correspondances sont collectées ; seule est écartée celle qui tient tout
        entière dans une clé de ticket. Des correspondances qui se chevauchent forment un
        groupe : il est remplacé d'un seul tenant (de son premier à son dernier caractère),
        avec le type de jeton de la plus longue, pour qu'aucun fragment ne reste en clair.
        """
        proteges = [m.span() for m in _CLE_TICKET.finditer(texte)]
        trouvees: list[tuple[int, int, str]] = []
        for type_jeton, motif in self._motifs:
            for trouve in motif.finditer(texte):
                debut, fin = trouve.span()
                if debut == fin or any(d <= debut and fin <= f for d, f in proteges):
                    continue
                trouvees.append((debut, fin, type_jeton))
        trouvees.sort(key=lambda t: (t[0], -(t[1] - t[0])))
        plages: list[tuple[int, int, str]] = []
        longueur_type = 0
        for debut, fin, type_jeton in trouvees:
            if plages and debut < plages[-1][1]:
                debut_groupe, fin_groupe, type_groupe = plages[-1]
                if fin - debut > longueur_type:
                    type_groupe, longueur_type = type_jeton, fin - debut
                plages[-1] = (debut_groupe, max(fin, fin_groupe), type_groupe)
            else:
                plages.append((debut, fin, type_jeton))
                longueur_type = fin - debut
        return plages

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
        """Remplace, localement, les jetons connus de la table ; les autres restent tels quels."""
        jetons = set(_JETON.findall(texte))
        if not jetons:
            return texte
        valeurs = self._table.lire(jetons)
        return _JETON.sub(lambda m: valeurs.get(m.group(0), m.group(0)), texte)

    def apercu(self, texte: str) -> str:
        """Comme `pseudonymiser`, sans écrire la table (FR-31)."""
        return self._remplacer(texte)[0]
