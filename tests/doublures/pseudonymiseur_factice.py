"""`PseudonymiseurFactice` : Pseudonymisation par expressions régulières et HMAC (AD-15).

Jeton = `<TYPE>_<6 hex de HMAC-SHA256(cle, valeur)>` ; une clé de ticket n'est jamais touchée :
seules les parties d'une correspondance hors des clés de ticket sont pseudonymisées.
La correspondance reste en mémoire. La grammaire des jetons est celle de `contrats.llm`.
"""

import hashlib
import hmac
import re
from collections.abc import Mapping

from usine.adaptateurs.pseudonymisation import fragments_hors_cles
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import CANDIDAT_JETON, LONGUEUR_EMPREINTE_JETON, variantes_jeton
from usine.contrats.tickets import MOTIF_CLE_TICKET

_CLE_TICKET = re.compile(rf"\b{MOTIF_CLE_TICKET}\b")


class PseudonymiseurFactice:
    """Pseudonymiseur déterministe, sans Presidio ni stockage."""

    def __init__(self, cle: bytes, motifs: Mapping[str, str]) -> None:
        self._cle = cle
        self._motifs = [(type_jeton, re.compile(motif)) for type_jeton, motif in motifs.items()]
        self.table: dict[str, str] = {}

    def _jeton(self, type_jeton: str, valeur: str) -> str:
        empreinte = hmac.new(self._cle, valeur.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{type_jeton}_{empreinte[:LONGUEUR_EMPREINTE_JETON]}"

    def _remplacer(self, texte: str, enregistrer: bool) -> str:
        proteges = [m.span() for m in _CLE_TICKET.finditer(texte)]
        retenus: list[tuple[int, int, str]] = []
        for type_jeton, motif in self._motifs:
            for trouve in motif.finditer(texte):
                debut, fin = trouve.span()
                if debut == fin:
                    continue
                for d_frag, f_frag in fragments_hors_cles(texte, debut, fin, proteges):
                    if not any(d < f_frag and d_frag < f for d, f, _ in retenus):
                        retenus.append((d_frag, f_frag, type_jeton))
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
        """Remplace les jetons connus par leur valeur ; les autres restent tels quels.

        Un jeton préfixé (`ID_COMPTE_abc123`) est reconnu : la plus longue variante connue est
        remplacée, le préfixe reste.
        """

        def remplacer(candidat: re.Match[str]) -> str:
            for variante in variantes_jeton(candidat):
                if variante in self.table:
                    return candidat.group(0)[: -len(variante)] + self.table[variante]
            return candidat.group(0)

        return CANDIDAT_JETON.sub(remplacer, texte)

    def apercu(self, texte: str) -> str:
        """Comme `pseudonymiser`, sans écrire la correspondance."""
        return self._remplacer(texte, enregistrer=False)
