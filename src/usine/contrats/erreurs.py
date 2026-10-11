"""Erreurs du démonstrateur : toute exception métier dérive de `UsineErreur`."""


class UsineErreur(Exception):
    """Erreur explicite, traduite par la CLI en message et en code de sortie non nul."""
