"""Étape `repartition_causes` de la Chaîne (Palier 2, Story 6.5).

Entre `classification` et `explications` : lit via la Consultation les Causes racines
proposées et les Anomalies ouvertes à la Date d'arrêté, et renvoie la table
`SCHEMA_REPARTITION_CAUSES` que l'`EcrivainPassage` écrit dans `repartition_causes.parquet`.

Le calcul n'appartient qu'à `domaine.causes.repartition` (AD-9). La couche `ia` ne pouvant pas
importer le domaine, la fonction est injectée par la composition, comme la prévision de
`EtapePrevision`.
"""

from collections.abc import Callable, Sequence
from datetime import date

import polars as pl

from usine.contrats.llm import SortieClassification
from usine.contrats.passage import ContextePassage, ResultatEtape, StatutEtape
from usine.ports.consultation import Consultation

type Repartir = Callable[[date, Sequence[SortieClassification], pl.DataFrame], pl.DataFrame]
"""Signature de `domaine.causes.repartition.repartition`, injectée par la composition."""


class EtapeRepartitionCauses:
    """Répartition des Causes racines des Anomalies ouvertes classées ; n'écrit rien elle-même."""

    def __init__(self, repartir: Repartir) -> None:
        self._repartir = repartir

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sortie `repartition_causes`, lue via `ctx.consultation`, sans trace."""
        ouvertes = ctx.consultation.anomalies(ctx.date_arrete).anomalies
        # `cause_racine_proposee` des Anomalies est ignorée : la classification fait foi.
        anomalies = pl.DataFrame(
            {
                "cle_ticket": [a.cle_ticket for a in ouvertes],
                "entite": [a.entite for a in ouvertes],
            },
            schema={"cle_ticket": pl.Utf8(), "entite": pl.Utf8()},
        )
        table = self._repartir(ctx.date_arrete, ctx.consultation.classification(), anomalies)
        return ResultatEtape(StatutEtape.reussie, {"repartition_causes": table})
