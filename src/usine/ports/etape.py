"""Port `Etape` : une étape de la Chaîne, injectée par la composition (AD-22)."""

from typing import Protocol, runtime_checkable

from usine.contrats.passage import ContextePassage, ResultatEtape
from usine.ports.consultation import Consultation


@runtime_checkable
class Etape(Protocol):
    """Étape de la Chaîne ; elle lit via `ctx.consultation` et n'écrit rien elle-même."""

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Exécute l'étape et renvoie ses sorties nommées et ses traces."""
        ...
