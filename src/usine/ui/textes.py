"""Textes et chemins communs à l'UI Streamlit et à l'UI web, sans dépendance externe.

Le Mode repli lit le Passage enregistré `demo/repli/passage/` : son chemin et les deux textes
qui le nomment vivent ici pour que `app.py` (Streamlit, retiré en Story 7.17) et `serveur.py`
(FastAPI) citent la même constante.
"""

from pathlib import Path

REPERTOIRE_REPLI = Path("demo/repli/passage")
"""Passage publié fictif et versionné, lu par toute l'UI en Mode repli (relatif à la racine).

Régénération, depuis un clone sans secrets Jira et avec `USINE_MODE_REPLI=1` :
`usine donnees generer --graine 42 --date-generation 2026-10-12`, puis
`usine rapport --date-arrete 2026-10-09`, puis copie de
`sorties/passages/2026-10-09/<passage_id>/` vers `demo/repli/passage/`. Régénérée en Story 5.6
sur le Journal des contrats 1.2 (A et B rouges, C orange). `passage_id` actuel :
`20261012T221158Z-96c621`, repris par les réponses enregistrées de l'Agent (Story 7.11).
"""

DOSSIER_REPLI = f"{REPERTOIRE_REPLI.as_posix()}/"

# Bandeau permanent du Mode repli, premier élément de la zone principale (Markdown en ligne).
BANDEAU_REPLI = (
    f"**Mode repli** : la démo lit le Passage enregistré `{DOSSIER_REPLI}`, sans Jira ni LLM"
    " réels ; les liens Jira sont inactifs."
)

# Mode repli sans copie versionnée : erreur explicite, jamais de repli silencieux.
REPLI_ABSENT = (
    f"Mode repli : Passage enregistré introuvable (`{DOSSIER_REPLI}manifeste.json` absent) ;"
    f" restaurer `{DOSSIER_REPLI}` depuis le dépôt ou désactiver le Mode repli."
)

# Écran Lancement en Mode repli : bouton visible mais bloqué.
LANCEMENT_REPLI = (
    "Mode repli : le lancement de la Chaîne est désactivé. L'UI lit le Passage enregistré"
    f" `{DOSSIER_REPLI}` ; désactiver le Mode repli pour lancer la Chaîne."
)

INTERVALLE_SONDAGE = 1.0
"""Secondes entre deux lectures de la progression, Chaîne en cours."""

LIGNES_ERREUR_MAX = 20
"""Dernières lignes de l'erreur standard affichées en cas d'échec."""
