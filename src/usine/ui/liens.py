"""Rendu Markdown d'une clé de ticket : seul point de passage d'une clé affichée (FR-29).

L'URL vient toujours de `Consultation.url_ticket(cle)` ; elle vaut `None` en Mode repli, et la
clé reste alors en texte simple.
"""

import re

_SPECIAUX = re.compile(r"([\\`*_{}\[\]()<>#+!|~$])")
"""Caractères Markdown (et `$` des formules de Streamlit) échappés par une barre oblique."""

_DESTINATION = str.maketrans(
    {" ": "%20", "(": "%28", ")": "%29", "<": "%3C", ">": "%3E", "\\": "%5C", "|": "%7C"}
)
"""Caractères d'une URL qui casseraient la destination d'un lien ou une cellule de tableau."""


def echapper_markdown(texte: str) -> str:
    """Texte affiché tel quel en Markdown : `A]B` → `A\\]B`."""
    return _SPECIAUX.sub(r"\\\1", texte)


def lien_ticket(cle: str, url: str | None) -> str:
    """`[CLE](url)` si l'URL est connue, sinon la clé en texte simple (Mode repli)."""
    texte = echapper_markdown(cle)
    if url is None:
        return texte
    return f"[{texte}]({url.translate(_DESTINATION)})"
