"""Écran « Avant / après » : reporting manuel déclaré contre Chaîne mesurée.

Le temps manuel vient de `config/demo.yaml` (valeur déclarative fictive, Q-5) ; le temps de la
Chaîne vient des horodatages du manifeste du dernier Passage publié sans classification
initiale (FR-44). Seul le cumul sur `NB_RAPPORTS_CUMUL` Rapports est dérivé : aucun gain ni
ratio n'est calculé.
"""

from datetime import timedelta

from usine.contrats.format import formater_date
from usine.contrats.passage import ManifestePassage

NB_RAPPORTS_CUMUL = 5
"""Nombre de Rapports quotidiens du cumul affiché."""

CLE_TEMPS_MANUEL = "temps_manuel_minutes_par_rapport"
"""Clé de `config/demo.yaml` qui déclare le temps manuel."""

FICHIER_CONFIG = "config/demo.yaml"
"""Fichier de configuration de la démo, relatif à la racine."""

SEULE_CLASSIFICATION_INITIALE = (
    "Seul un Passage avec classification initiale est publié : son temps, qui inclut la"
    " classification de tous les tickets, n'est pas celui d'un Rapport quotidien. Relancer la"
    " Chaîne pour mesurer un Passage sans classification initiale."
)
"""Avertissement affiché au lieu d'un temps trompeur."""

AUCUN_PASSAGE = "Aucun Passage publié : lancer la Chaîne pour mesurer son temps."
"""Information affichée quand aucun Passage n'est publié."""

CONFIG_ABSENTE = (
    f"Configuration absente : `{FICHIER_CONFIG}` (clé `{CLE_TEMPS_MANUEL}`) ; le temps de"
    " reporting manuel déclaré ne peut pas être affiché."
)
"""Avertissement affiché quand `config/demo.yaml` n'existe pas."""

MENTION_FICTIVE = f"Temps manuel : valeur déclarative fictive (`{FICHIER_CONFIG}`, Q-5)."
"""Mention de la légende sur la nature du temps manuel."""

MENTION_CUMUL = f"Cumul : {NB_RAPPORTS_CUMUL} × le temps d'un Rapport."
"""Mention de la légende : le cumul est dérivé d'une seule mesure."""


def duree_mesuree(manifeste: ManifestePassage) -> timedelta:
    """Temps mesuré du Passage : `horodatage_fin − horodatage_debut` du manifeste."""
    return manifeste.horodatage_fin - manifeste.horodatage_debut


def legende(manifeste: ManifestePassage) -> str:
    """Date d'arrêté et `passage_id` du Passage mesuré, mentions du temps fictif et du cumul."""
    return (
        f"Chaîne mesurée sur le Passage `{manifeste.passage_id}`, Date d'arrêté"
        f" {formater_date(manifeste.date_arrete)}, sans classification initiale. "
        f"{MENTION_FICTIVE} {MENTION_CUMUL}"
    )
