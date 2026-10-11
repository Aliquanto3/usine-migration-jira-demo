"""`PseudonymiseurFactice` : Pseudonymisation par expressions régulières et HMAC (AD-15).

Jeton = `<TYPE>_<6 hex de HMAC-SHA256(cle, valeur)>` ; une clé de ticket n'est jamais touchée.
La correspondance reste en mémoire.
"""

import hashlib
import hmac
import re
from collections.abc import Mapping

from usine.contrats.erreurs import UsineErreur
from usine.contrats.tickets import MOTIF_CLE_TICKET

_CLE_TICKET = re.compile(rf"\b{MOTIF_CLE_TICKET}\b")
_JETON = re.compile(r"\b([A-Z](?:[A-Z_]*[A-Z])?)_([0-9a-f]{6})\b")


class PseudonymiseurFactice:
    """Pseudonymiseur déterministe, sans Presidio ni stockage."""

    def __init__(self, cle: bytes, motifs: Mapping[str, str]) -> None:
        self._cle = cle
        self._motifs = [(type_jeton, re.compile(motif)) for type_jeton, motif in motifs.items()]
        self.table: dict[str, str] = {}

    def _jeton(self, type_jeton: str, valeur: str) -> str:
        empreinte = hmac.new(self._cle, valeur.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{type_jeton}_{empreinte[:6]}"

    def _remplacer(self, texte: str, enregistrer: bool) -> str:
        proteges = [m.span() for m in _CLE_TICKET.finditer(texte)]
        retenus: list[tuple[int, int, str]] = []
        for type_jeton, motif in self._motifs:
            for trouve in motif.finditer(texte):
                debut, fin = trouve.span()
                if debut == fin:
                    continue
                chevauche = any(d < fin and debut < f for d, f in proteges)
                chevauche = chevauche or any(d < fin and debut < f for d, f, _ in retenus)
                if not chevauche:
                    retenus.append((debut, fin, type_jeton))
        morceaux: list[str] = []
        position = 0
        for debut, fin, type_jeton in sorted(retenus):
            valeur = texte[debut:fin]
            jeton = self._jeton(type_jeton, valeur)
            if enregistrer:
                connue = self.table.setdefault(jeton, valeur)
                if connue != valeur:
                    raise UsineErreur(f"collision de jeton {jeton} entre deux valeurs")
            morceaux.extend((texte[position:debut], jeton))
            position = fin
        morceaux.append(texte[position:])
        return "".join(morceaux)

    def pseudonymiser(self, texte: str) -> str:
        """Texte pseudonymisé ; la correspondance est gardée pour `reidentifier`."""
        return self._remplacer(texte, enregistrer=True)

    def reidentifier(self, texte: str) -> str:
        """Remplace les jetons connus par leur valeur ; les autres restent tels quels."""
        return _JETON.sub(lambda m: self.table.get(m.group(0), m.group(0)), texte)

    def apercu(self, texte: str) -> str:
        """Comme `pseudonymiser`, sans écrire la correspondance."""
        return self._remplacer(texte, enregistrer=False)
