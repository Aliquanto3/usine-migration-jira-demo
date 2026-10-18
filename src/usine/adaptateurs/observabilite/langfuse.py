"""Envoi des `EntreeTrace` LLM à Langfuse 4.17.0 auto-hébergé, en plus du Journal (AD-12).

L'observateur n'émet que ce que porte la trace : entrée pseudonymisée et sortie avant
ré-identification, jamais un texte en clair. Il est facultatif et ne fait jamais échouer un
Passage : toute erreur du client est journalisée (sans le contenu) puis ignorée. Le paquet
`langfuse` est importé à la demande (groupe `bonus`), seulement quand l'envoi est activé.
"""

import importlib
import logging
from typing import Any, Protocol

from usine.contrats.erreurs import UsineErreur
from usine.contrats.trace import EntreeTrace, TypeTrace

journal = logging.getLogger(__name__)


class ObservationLangfuse(Protocol):
    """Observation Langfuse en cours (`start_observation`)."""

    def end(self) -> Any: ...


class ClientLangfuse(Protocol):
    """Partie du client `langfuse.Langfuse` utilisée ici ; simulée dans les tests."""

    def start_observation(self, **arguments: Any) -> ObservationLangfuse: ...

    def flush(self) -> None: ...


class ObservateurLangfuse:
    """Reçoit chaque `EntreeTrace` de la passerelle et l'envoie à Langfuse."""

    def __init__(self, client: ClientLangfuse) -> None:
        self._client = client

    def __call__(self, trace: EntreeTrace) -> None:
        """Envoie la trace LLM ; les traces de Prévision et toute erreur sont ignorées."""
        if trace.type_trace is not TypeTrace.llm:
            return
        try:
            observation = self._client.start_observation(
                name=f"{trace.tache.value if trace.tache else 'llm'}:{trace.cible or '-'}",
                as_type="generation",
                input=trace.entree_pseudonymisee,
                output=trace.sortie,
                model=trace.version_modele,
                usage_details={"input": trace.jetons_entree, "output": trace.jetons_sortie},
                cost_details={"total": float(trace.cout_estime_eur)},
                metadata={
                    "passage_id": trace.passage_id,
                    "entite": trace.entite,
                    "fournisseur": trace.fournisseur,
                    "version_prompt": trace.version_prompt,
                    "version_grille": trace.version_grille,
                    "version_donnees": trace.version_donnees,
                    "statut_controle": trace.statut_controle.value
                    if trace.statut_controle
                    else None,
                    "depuis_cache": trace.depuis_cache,
                    "en_echec": trace.en_echec,
                    "horodatage": trace.horodatage.isoformat(),
                },
            )
            observation.end()
            self._client.flush()
        except Exception as exc:
            journal.warning("Langfuse : trace non envoyée (%s)", type(exc).__name__)


def construire_observateur(
    hote: str | None, cle_publique: str | None, cle_secrete: str | None
) -> ObservateurLangfuse:
    """Observateur sur un client `langfuse.Langfuse` réel.

    `UsineErreur` si l'hôte ou une clé manque, ou si le paquet `langfuse` (groupe `bonus`)
    n'est pas installé.
    """
    manquants = [
        nom
        for nom, valeur in (
            ("LANGFUSE_HOST", hote),
            ("LANGFUSE_PUBLIC_KEY", cle_publique),
            ("LANGFUSE_SECRET_KEY", cle_secrete),
        )
        if not valeur
    ]
    if manquants:
        raise UsineErreur(f"Langfuse activé sans {', '.join(manquants)}")
    try:
        module = importlib.import_module("langfuse")
    except ImportError:
        raise UsineErreur("Langfuse activé : lancer `uv sync --group bonus`") from None
    client: ClientLangfuse = module.Langfuse(
        public_key=cle_publique, secret_key=cle_secrete, host=hote
    )
    return ObservateurLangfuse(client)
