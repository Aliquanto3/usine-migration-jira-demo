"""Vérification des commentaires des fichiers YAML de configuration (NFR-10).

Les clés viennent de l'arbre YAML (`yaml.compose_all`) : toute clé de mapping compte, quelle
que soit sa forme (entre guillemets, numérique, en flow mapping). Un `#` n'est un commentaire
que hors de tout jeton YAML (scalaire, bloc littéral, URL…) et précédé d'un blanc ou en début
de ligne.
"""

import re

import yaml

_SAUT_DE_LIGNE = re.compile(r"\r\n|[\r\n\x85\u2028\u2029]")
_ETIQUETTE_FUSION = "tag:yaml.org,2002:merge"
_BOM = "\ufeff"


def _lignes(texte: str) -> list[tuple[int, int]]:
    """Bornes `(début, fin)` de chaque ligne, découpées comme le fait PyYAML."""
    bornes: list[tuple[int, int]] = []
    debut = 0
    for saut in _SAUT_DE_LIGNE.finditer(texte):
        bornes.append((debut, saut.start()))
        debut = saut.end()
    bornes.append((debut, len(texte)))
    return bornes


def _positions_dans_un_jeton(texte: str) -> set[int]:
    """Positions des caractères couverts par un jeton YAML (les commentaires n'en sont pas)."""
    couvertes: set[int] = set()
    for jeton in yaml.scan(texte, Loader=yaml.SafeLoader):
        debut, fin = jeton.start_mark.index, jeton.end_mark.index
        if isinstance(jeton, yaml.ScalarToken) and jeton.style in ("|", ">"):
            # Le jeton d'un bloc littéral englobe son en-tête `|  # commentaire`.
            saut = _SAUT_DE_LIGNE.search(texte, debut, fin)
            debut = saut.start() if saut else fin
        couvertes.update(range(debut, fin))
    return couvertes


def _commentaires(texte: str) -> dict[int, tuple[bool, bool]]:
    """Pour chaque ligne (numérotée à partir de 0) portant un commentaire non vide :
    `(seul sur sa ligne, non vide)`."""
    couvertes = _positions_dans_un_jeton(texte)
    resultat: dict[int, tuple[bool, bool]] = {}
    for numero, (debut, fin) in enumerate(_lignes(texte)):
        for position in range(debut, fin):
            if texte[position] != "#" or position in couvertes:
                continue
            avant = texte[debut:position]
            if avant and avant[-1] not in " \t" and avant != _BOM:
                continue
            seul = not avant.replace(_BOM, "").strip(" \t")
            resultat[numero] = (seul, bool(texte[position + 1 : fin].strip()))
            break
    return resultat


def _cles(texte: str) -> list[tuple[int, int, str]]:
    """`(position, ligne, clé)` de chaque clé de mapping, dans l'ordre du texte."""
    cles: list[tuple[int, int, str]] = []
    vus: set[int] = set()
    a_visiter: list[yaml.Node] = [n for n in yaml.compose_all(texte, Loader=yaml.SafeLoader) if n]
    while a_visiter:
        noeud = a_visiter.pop()
        if id(noeud) in vus:
            continue
        vus.add(id(noeud))
        if isinstance(noeud, yaml.MappingNode):
            for noeud_cle, noeud_valeur in noeud.value:
                if noeud_cle.tag == _ETIQUETTE_FUSION:
                    a_visiter.append(noeud_valeur)  # `<<` n'est pas une clé à commenter.
                    continue
                nom = noeud_cle.value if isinstance(noeud_cle, yaml.ScalarNode) else "?"
                marque = noeud_cle.start_mark
                cles.append((marque.index, marque.line, str(nom)))
                a_visiter.extend((noeud_cle, noeud_valeur))
        elif isinstance(noeud, yaml.SequenceNode):
            a_visiter.extend(noeud.value)
    return sorted(cles)


def cles_sans_commentaire(texte: str) -> list[tuple[int, str]]:
    """Liste les `(numéro de ligne, clé)` sans commentaire.

    Une clé est commentée si sa ligne porte un commentaire non vide, ou si la ligne qui la
    précède immédiatement est un commentaire non vide seul sur sa ligne.
    """
    commentaires = _commentaires(texte)
    manquantes: list[tuple[int, str]] = []
    for _, ligne, cle in _cles(texte):
        en_ligne = commentaires.get(ligne, (False, False))[1]
        seul_au_dessus, non_vide_au_dessus = commentaires.get(ligne - 1, (False, False))
        if not (en_ligne or (seul_au_dessus and non_vide_au_dessus)):
            manquantes.append((ligne + 1, cle))
    return manquantes
