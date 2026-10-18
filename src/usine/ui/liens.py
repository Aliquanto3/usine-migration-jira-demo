"""Rendu Markdown d'une clé de ticket : seul point de passage d'une clé affichée (FR-29).

L'URL vient toujours de `Consultation.url_ticket(cle)` ; elle vaut `None` en Mode repli, et la
clé reste alors en texte simple.
"""

from usine.ui.vues import VueTicket


def vue_ticket(cle: str, url: str | None) -> VueTicket:
    """Clé de ticket en donnée : lien (nouvel onglet) si l'URL est connue, sinon texte simple."""
    return VueTicket(
        cle=cle, url=url, nom_accessible=None if url is None else f"{cle} (nouvel onglet)"
    )
