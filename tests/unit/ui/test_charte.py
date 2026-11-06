"""Charte générique v2.1 sur l'interface web : contrastes des deux thèmes, icône, polices.

`cadre.css` s'écrit à la main. Le test lit ses blocs de variables (sombre en `:root`, clair sous
`prefers-color-scheme: light` et `[data-theme="light"]`), résout les `var()` et vérifie une liste
explicite de couples texte/fond tirés de l'interface. Bibliothèque standard seulement.
"""

import re

import pytest

from usine.ui.serveur import REPERTOIRE_STATIQUE, _page_erreur

CSS = (REPERTOIRE_STATIQUE / "cadre.css").read_text(encoding="utf-8")
SANS_COMMENTAIRE = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")


def _declarations(corps: str) -> dict[str, str]:
    return {k.strip(): v.strip() for k, v in re.findall(r"([\w-]+)\s*:\s*([^;]+);?", corps)}


def _bloc(entete: str) -> str:
    """Corps du bloc dont l'en-tête est exactement `entete` (accolades imbriquées gérées)."""
    debut = SANS_COMMENTAIRE.index(entete + " {") + len(entete) + 2
    profondeur, i = 1, debut
    while profondeur:
        profondeur += {"{": 1, "}": -1}.get(SANS_COMMENTAIRE[i], 0)
        i += 1
    return SANS_COMMENTAIRE[debut : i - 1]


SOMBRE = _declarations(_bloc(":root"))
CLAIR = _declarations(_bloc(':root[data-theme="light"]'))
CLAIR_SYSTEME = _declarations(_bloc(':root:not([data-theme="dark"])'))
SOMBRE_FORCE = _declarations(_bloc(':root[data-theme="dark"]'))
THEMES = {"sombre": SOMBRE, "clair": CLAIR}


def _regles() -> list[tuple[list[str], dict[str, str]]]:
    """Règles à plat (hors @media et blocs de variables), dans l'ordre du fichier."""
    reste = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*\s*\}", "", SANS_COMMENTAIRE)
    reste = re.sub(r"@font-face\s*\{[^}]*\}", "", reste)
    regles = []
    for selecteurs, corps in re.findall(r"([^{}]+)\{([^{}]*)\}", reste):
        liste = [s.strip() for s in selecteurs.split(",")]
        if liste[0].startswith(":root"):
            continue
        regles.append((liste, _declarations(corps)))
    return regles


REGLES = _regles()


def _propriete(selecteur: str, propriete: str) -> str:
    """Dernière valeur déclarée pour `propriete` par une règle qui cible exactement `selecteur`."""
    valeur = None
    for liste, decl in REGLES:
        if selecteur not in liste:
            continue
        if propriete == "background" and "background" in decl:
            valeur = decl["background"]
        elif propriete in decl:
            valeur = decl[propriete]
    assert valeur is not None, f"{selecteur} ne déclare pas {propriete}"
    return valeur


def _resoudre(valeur: str, theme: dict[str, str]) -> str:
    m = re.fullmatch(r"var\((--[\w-]+)\)", valeur)
    assert m, f"valeur non résolue : {valeur}"
    resolu = theme[m.group(1)]
    return resolu if resolu.startswith("#") else _resoudre(resolu, theme)


def _luminance(hexa: str) -> float:
    canaux = [int(hexa[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canaux]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste(a: str, b: str) -> float:
    haut, bas = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (haut + 0.05) / (bas + 0.05)


# (étiquette, sélecteur du texte, propriété, sélecteur du fond)
TEXTE_SUR_FOND = [
    ("body", "body", "color", "body"),
    ("texte sur carte", "body", "color", ".carte"),
    ("légende sur carte", ".legende", "color", ".carte"),
    ("lien sur fond", "a", "color", "body"),
    ("lien sur carte", "a", "color", ".carte"),
    ("nom de marque", ".marque-nom", "color", ".entete"),
    ("sous-titre d'en-tête", ".marque-sous-titre", "color", ".entete"),
    ("navigation", ".nav-lien", "color", "body"),
    ("page courante", '.nav-lien[aria-current="page"]', "color", '.nav-lien[aria-current="page"]'),
    ("pastille mode réel", ".pastille-mode--reel", "color", ".pastille-mode--reel"),
    ("pastille météo verte", ".pastille-meteo", "color", ".pastille-meteo--vert"),
    ("pastille météo jaune", ".pastille-meteo", "color", ".pastille-meteo--jaune"),
    ("pastille météo orange", ".pastille-meteo", "color", ".pastille-meteo--orange"),
    ("pastille météo rouge", ".pastille-meteo", "color", ".pastille-meteo--rouge"),
    ("bouton principal", ".bouton-primaire", "color", ".bouton-primaire"),
    ("bouton principal survolé", ".bouton-primaire", "color", ".bouton-primaire:hover"),
    ("bouton secondaire", ".bouton-secondaire", "color", ".bouton-secondaire"),
    (
        "bouton secondaire inactif",
        '.bouton-primaire[aria-disabled="true"]',
        "color",
        '.bouton-primaire[aria-disabled="true"]',
    ),
    ("code", "body", "color", "code"),
    ("journal", ".journal", "color", ".journal"),
    ("heure du journal", ".journal-heure", "color", ".journal"),
    ("bandeau de succès", ".bandeau--succes", "color", ".bandeau--succes"),
    ("bandeau d'erreur", ".bandeau--erreur", "color", ".bandeau--erreur"),
    ("bandeau de repli", ".bandeau--repli", "color", ".bandeau--repli"),
    ("avertissement", ".avertissement", "color", ".avertissement"),
    ("badge conforme", ".badge--conforme", "color", ".badge--conforme"),
    ("badge rejeté", ".badge--rejete", "color", ".badge--rejete"),
    ("étape en cours", ".etape--en_cours .etape-badge", "color", ".etape--en_cours .etape-badge"),
    ("étape échouée", ".etape--echouee .etape-badge", "color", ".etape--echouee .etape-badge"),
    ("étape réussie", ".etape--reussie .etape-puce", "color", ".etape--reussie .etape-puce"),
    ("bulle question", ".bulle--question", "color", ".bulle--question"),
    ("champ", ".champ", "color", ".champ"),
]


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize(("etiquette", "sel_texte", "prop", "sel_fond"), TEXTE_SUR_FOND)
def test_texte_a_4_5_pour_1(
    etiquette: str, sel_texte: str, prop: str, sel_fond: str, theme: str
) -> None:
    jetons = THEMES[theme]
    if sel_fond.endswith(":hover"):
        fond = _propriete(sel_fond.removesuffix(":hover") + ":hover", "background")
    else:
        fond = _propriete(sel_fond, "background")
    texte = _resoudre(_propriete(sel_texte, prop), jetons)
    ratio = contraste(texte, _resoudre(fond, jetons))
    assert ratio >= 4.5, f"{etiquette} ({theme}) : {ratio:.2f}:1"


# Marques non textuelles : contour interactif, anneau de focus (3:1).
NON_TEXTUELLES = [
    ("contour secondaire sur carte", "--trait-fort", "--surface"),
    ("contour secondaire sur fond", "--trait-fort", "--fond"),
    ("focus sur fond", "--focus", "--fond"),
    ("focus sur carte", "--focus", "--surface"),
    ("focus d'en-tête", "--sur-encre", "--encre-pleine"),
    ("filet or sur carte", "--accent", "--surface"),
    ("filet or sur fond", "--accent", "--fond"),
]


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize(("etiquette", "marque", "fond"), NON_TEXTUELLES)
def test_marque_non_textuelle_a_3_pour_1(
    etiquette: str, marque: str, fond: str, theme: str
) -> None:
    jetons = THEMES[theme]
    ratio = contraste(jetons[marque], jetons[fond])
    assert ratio >= 3.0, f"{etiquette} ({theme}) : {ratio:.2f}:1"


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("couleur", ["vert", "jaune", "orange", "rouge"])
def test_point_meteo_a_3_pour_1_sur_sa_pastille(couleur: str, theme: str) -> None:
    jetons = THEMES[theme]
    point = _propriete(f".pastille-meteo--{couleur} .pastille-meteo-point", "background")
    fond = _propriete(f".pastille-meteo--{couleur}", "background")
    ratio = contraste(_resoudre(point, jetons), _resoudre(fond, jetons))
    assert ratio >= 3.0, f"point {couleur} ({theme}) : {ratio:.2f}:1"


BOUTONS = re.compile(r"(^|[\s>+~])(button|\.bouton[\w-]*|\.segment-option|\.question-choix)\b")


def test_le_bleu_n_est_jamais_un_aplat_de_bouton() -> None:
    fautifs = [
        sel
        for liste, decl in REGLES
        for sel in liste
        if BOUTONS.search(sel)
        and re.match(
            r"var\(--primaire(-vif)?\)", decl.get("background", decl.get("background-color", ""))
        )
    ]
    assert fautifs == []


def test_bouton_principal_est_neutre() -> None:
    assert _propriete(".bouton-primaire", "background") == "var(--bouton)"
    assert _propriete(".bouton-primaire", "color") == "var(--sur-bouton)"
    assert _propriete(".bouton-primaire:hover", "background") == "var(--bouton-survol)"
    assert _propriete(".bouton-secondaire", "border").endswith("var(--trait-fort)")
    assert _propriete(":focus-visible", "outline").startswith("2px solid var(--focus)")


def test_themes_et_valeurs() -> None:
    assert SOMBRE["color-scheme"] == "dark"
    assert CLAIR["color-scheme"] == "light"
    assert {k: v for k, v in SOMBRE_FORCE.items()} == {k: SOMBRE[k] for k in SOMBRE_FORCE}
    assert CLAIR_SYSTEME == CLAIR
    assert SOMBRE["--texte"] == "#E8ECF2"
    assert CLAIR["--texte"] == "#121821"
    assert SOMBRE["--bouton"] == "#E8ECF2"
    assert CLAIR["--bouton"] == "#121821"
    assert set(SOMBRE) - {
        "--police-titre",
        "--police-corps",
        "--police-code",
        "--gouttiere",
        "--entete",
        "--cible-min",
    } == set(CLAIR)


def test_aucune_couleur_en_dur_hors_des_blocs_de_theme() -> None:
    hors_blocs = SANS_COMMENTAIRE
    for entete in (
        ":root",
        ':root[data-theme="light"]',
        ':root:not([data-theme="dark"])',
        ':root[data-theme="dark"]',
    ):
        hors_blocs = hors_blocs.replace(_bloc(entete), "")
    assert HEX.findall(hors_blocs) == []
    assert "rgb(" not in hors_blocs


def test_police_des_titres_est_sora() -> None:
    assert SOMBRE["--police-titre"].startswith("Sora, ")
    fichiers = set(re.findall(r'url\("polices/([^"]+)"\)', CSS))
    assert "Sora-SemiBold.woff2" in fichiers
    assert len(fichiers) == 5


@pytest.mark.parametrize("page", sorted(p.name for p in REPERTOIRE_STATIQUE.glob("*.html")))
def test_page_avec_icone_et_pictogramme(page: str) -> None:
    html = (REPERTOIRE_STATIQUE / page).read_text(encoding="utf-8")
    assert '<link rel="icon" type="image/svg+xml" href="/statique/favicon.svg">' in html
    assert 'src="/statique/pictogramme.svg"' in html
    assert 'href="data:,"' not in html


def test_page_erreur_avec_icone() -> None:
    html = bytes(_page_erreur("Fichier absent.", 404).body).decode("utf-8")
    assert 'href="/statique/favicon.svg"' in html
    assert 'href="data:,"' not in html


def test_icones_presentes() -> None:
    for nom in ("favicon.svg", "pictogramme.svg"):
        svg = (REPERTOIRE_STATIQUE / nom).read_text(encoding="utf-8")
        assert re.search(r"<svg\b[^>]*viewBox=", svg), nom
        assert svg.rstrip().endswith("</svg>"), nom
