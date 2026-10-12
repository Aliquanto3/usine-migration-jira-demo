"""`CacheMemoire` : doublure du port `CacheLLM`, en mémoire (AD-12, AD-20)."""


class CacheMemoire:
    """Cache clé → valeur dans un `dict` ; une écriture remplace la valeur existante."""

    def __init__(self) -> None:
        self.valeurs: dict[str, str] = {}

    def lire(self, cle: str) -> str | None:
        """Valeur enregistrée sous `cle`, ou `None`."""
        return self.valeurs.get(cle)

    def ecrire(self, cle: str, brut: str) -> None:
        """Enregistre (ou remplace) la valeur sous `cle`."""
        self.valeurs[cle] = brut
