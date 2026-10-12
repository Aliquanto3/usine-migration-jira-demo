"""Contrôles déterministes des sorties LLM (AD-12, FR-32).

`controler_citations` garde les seules phrases qui citent au moins une clé de ticket et
aucune clé hors des tickets autorisés. N'est une Citation qu'une clé dont le projet (partie
avant le dernier `-`) est celui d'au moins un ticket autorisé : `IND-1`, `ENT-12`, `UTF-8` ou
`SHA-256` ont la forme d'une clé de ticket mais sont ignorés. Les clés de ticket ne sont jamais
pseudonymisées : le contrôle s'applique donc indifféremment avant ou après la
ré-identification.
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from fractions import Fraction

from usine.contrats.format import ESPACE_INSECABLE, formater_nombre
from usine.contrats.llm import CANDIDAT_JETON
from usine.contrats.tickets import MOTIF_CLE_TICKET, rang_cle

_CLE_TICKET = re.compile(rf"\b{MOTIF_CLE_TICKET}\b")
_FIN_DE_PHRASE = re.compile(r"(?<=[.!?])\s+|\s*\n\s*")
"""Une phrase finit par `.`, `!` ou `?` suivi d'un blanc (ou de la fin), ou par un saut de ligne."""


@dataclass(frozen=True)
class ControleCitations:
    """Résultat de `controler_citations`."""

    texte: str
    """Phrases retenues, jointes par une espace."""
    citations: tuple[str, ...]
    """Clés citées par les phrases retenues, sans doublon, triées."""
    phrases_retirees: int
    phrases_total: int


def decouper_phrases(texte: str) -> tuple[str, ...]:
    """Phrases de `texte` ; coupe après `.`, `!` ou `?` suivi d'un blanc, et à chaque ligne."""
    morceaux = (phrase.strip() for phrase in _FIN_DE_PHRASE.split(texte.strip()))
    return tuple(phrase for phrase in morceaux if phrase)


def projet(cle: str) -> str:
    """Projet d'une clé : partie avant le dernier `-` (`DEMO-12` → `DEMO`)."""
    return cle.rpartition("-")[0]


def citations(phrase: str, projets: frozenset[str]) -> frozenset[str]:
    """Clés de ticket citées par `phrase` dont le projet figure dans `projets`."""
    return frozenset(cle for cle in _CLE_TICKET.findall(phrase) if projet(cle) in projets)


def controler_citations(texte: str, tickets_autorises: Iterable[str]) -> ControleCitations:
    """Retire chaque phrase sans clé de ticket ou citant une clé hors de `tickets_autorises`."""
    autorises = frozenset(tickets_autorises)
    projets = frozenset(projet(cle) for cle in autorises)
    retenues: list[str] = []
    citees: set[str] = set()
    phrases = decouper_phrases(texte)
    for phrase in phrases:
        cles = citations(phrase, projets)
        if cles and cles <= autorises:
            retenues.append(phrase)
            citees |= cles
    return ControleCitations(
        texte=" ".join(retenues),
        citations=tuple(sorted(citees, key=rang_cle)),
        phrases_retirees=len(phrases) - len(retenues),
        phrases_total=len(phrases),
    )


def retirer_citations_hors(texte: str, tickets_autorises: Iterable[str]) -> str:
    """Retire de `texte` les phrases qui citent une clé hors de `tickets_autorises`.

    Une phrase sans Citation reste (brouillon de commentaire).
    """
    autorises = frozenset(tickets_autorises)
    projets = frozenset(projet(cle) for cle in autorises)
    return " ".join(
        phrase for phrase in decouper_phrases(texte) if citations(phrase, projets) <= autorises
    )


# --- Contrôle des nombres et des dates d'une narration (AD-14, NFR-1) ---

_MASQUE = "\x00"
"""Caractère de masquage : ni chiffre, ni lettre, ni séparateur de milliers."""

_IGNORES = (
    _CLE_TICKET,
    re.compile(r"\bENT-[A-Z0-9]+\b"),
    re.compile(r"\bJ-\d+\b"),
    CANDIDAT_JETON,
)
"""Clés de ticket (dont `IND-n`), Entités, jalons `J-n` et jetons : jamais contrôlés."""

_MOIS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
    "janv": 1,
    "févr": 2,
    "fevr": 2,
    "avr": 4,
    "juil": 7,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "déc": 12,
    "dec": 12,
}

_DATE_FR = re.compile(r"(?<!\w)(\d{1,2})/(\d{1,2})/(\d{4})(?!\w)")
_DATE_COURTE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{2})(?![\d/])")
"""Date `JJ/MM/AA`, lue au XXIe siècle."""
_POINT_DECIMAL = re.compile(r"\d+(?:\.\d+)+")
"""Nombre à point (`2.15`, `15.10.2026`) : hors format français, toujours refusé."""
_DATE_ISO = re.compile(r"(?<!\w)(\d{4})-(\d{2})-(\d{2})(?!\w)")
_DATE_LONGUE = re.compile(
    rf"(?<!\w)(1er|\d{{1,2}})\s+({'|'.join(_MOIS)})\.?(?:\s+(\d{{4}}))?(?!\w)", re.IGNORECASE
)
_FRACTION = re.compile(r"(?<![\d/])(\d+)\s*/\s*(\d+)(?![\d/])")
_SEPARATEURS = "\u0020\u00a0\u202f"
_NOMBRE = re.compile(
    rf"(?<!\d)(?<!\d,)(\d{{1,3}}(?:[{_SEPARATEURS}]\d{{3}})+|\d+)(?:,(\d+))?"
    rf"(?:[{_SEPARATEURS}]?(%))?(?!\d)(?!,\d)"
)
"""Nombre français, même collé à des lettres (`12j`) ou suivi d'une virgule de ponctuation."""

_DECIMALES_MAX = 6
"""Au-delà, un nombre écrit n'est accepté qu'en égalité exacte (arrondi hors précision)."""

type ValeurAutorisee = int | Fraction | Decimal | date


@dataclass(frozen=True)
class ControleNombres:
    """Résultat de `controler_nombres`."""

    refuses: tuple[str, ...]
    """Nombres et dates du texte absents des valeurs autorisées, dans l'ordre du texte."""

    @property
    def conforme(self) -> bool:
        """Vrai si aucun nombre ni aucune date n'est refusé."""
        return not self.refuses


def _masquer(texte: str, debut: int, fin: int) -> str:
    return texte[:debut] + _MASQUE * (fin - debut) + texte[fin:]


def _date(annee: int, mois: int, jour: int) -> date | None:
    try:
        return date(annee, mois, jour)
    except ValueError:
        return None


def _nombre_accepte(
    valeur: Decimal, decimales: int, nombres: tuple[Fraction, ...], *, pourcent: bool = False
) -> bool:
    """Égalité en valeur absolue avec une valeur, exacte ou arrondie à `decimales` (AD-11).

    Hors pourcentage, un entier écrit n'est jamais l'arrondi d'une valeur non entière
    (« 1 » ne vaut pas 3/5).
    """
    cible = abs(valeur)
    for nombre in nombres:
        if Fraction(cible) == abs(nombre):
            return True
        if decimales > _DECIMALES_MAX:
            continue
        if decimales == 0 and not pourcent and nombre.denominator != 1:
            continue
        arrondi = formater_nombre(abs(nombre), decimales)
        ecrit = arrondi.replace(ESPACE_INSECABLE, "").replace(",", ".")
        if Decimal(ecrit) == cible:
            return True
    return False


def controler_nombres(texte: str, valeurs_autorisees: Iterable[ValeurAutorisee]) -> ControleNombres:
    """Refuse chaque nombre ou date de `texte` absent de `valeurs_autorisees` (AD-14).

    Sont d'abord masqués les clés de ticket (dont `IND-n`), les Entités `ENT-x`, les jalons
    `J-n` et les jetons de Pseudonymisation ; puis sont contrôlées les dates (`JJ/MM/AAAA`,
    ISO, « 15 octobre [2026] », « 1er octobre ») ; puis les fractions `n/d` ; puis les nombres
    au format français (milliers séparés par une espace, fine ou insécable, virgule décimale,
    `%` facultatif). Un nombre est accepté s'il égale, en valeur absolue, une valeur autorisée
    ou son arrondi au nombre de décimales écrit ; suivi de `%`, il est comparé à la valeur
    × 100. Une fraction `n/d` est acceptée si elle égale une valeur ou si `n` et `d` le sont.
    Les nombres écrits en toutes lettres ne sont pas contrôlés.
    """
    valeurs = tuple(valeurs_autorisees)
    dates = frozenset(v for v in valeurs if isinstance(v, date))
    nombres = tuple(Fraction(v) for v in valeurs if not isinstance(v, date | bool))
    pourcentages = tuple(n * 100 for n in nombres)
    jours_mois = frozenset((d.day, d.month) for d in dates)
    refuses: list[tuple[int, str]] = []
    for motif in _IGNORES:
        for trouve in motif.finditer(texte):
            texte = _masquer(texte, trouve.start(), trouve.end())

    def controler(motif: re.Pattern[str], accepter: Callable[[re.Match[str]], bool]) -> None:
        nonlocal texte
        for trouve in motif.finditer(texte):
            if not accepter(trouve):
                refuses.append((trouve.start(), trouve.group(0)))
            texte = _masquer(texte, trouve.start(), trouve.end())

    def entier_accepte(chiffres: str) -> bool:
        return _nombre_accepte(Decimal(chiffres), 0, nombres)

    controler(_DATE_FR, lambda m: _date(int(m[3]), int(m[2]), int(m[1])) in dates)
    controler(_DATE_COURTE, lambda m: _date(2000 + int(m[3]), int(m[2]), int(m[1])) in dates)
    controler(_DATE_ISO, lambda m: _date(int(m[1]), int(m[2]), int(m[3])) in dates)
    controler(_POINT_DECIMAL, lambda m: False)

    def date_longue(trouve: re.Match[str]) -> bool:
        jour = 1 if trouve[1].lower() == "1er" else int(trouve[1])
        mois = _MOIS[trouve[2].lower()]
        if trouve[3] is None:
            return (jour, mois) in jours_mois
        return _date(int(trouve[3]), mois, jour) in dates

    controler(_DATE_LONGUE, date_longue)
    controler(
        _FRACTION,
        lambda m: (
            (int(m[2]) != 0 and Fraction(int(m[1]), int(m[2])) in {abs(n) for n in nombres})
            or (
                (int(m[1]), int(m[2])) in jours_mois
                if 1 <= int(m[1]) <= 31 and 1 <= int(m[2]) <= 12
                else entier_accepte(m[1]) and entier_accepte(m[2])
            )
        ),
    )

    def nombre(trouve: re.Match[str]) -> bool:
        entiere, fraction, pourcent = trouve[1], trouve[2] or "", trouve[3]
        chiffres = "".join(c for c in entiere if c.isdigit())
        valeur = Decimal(f"{chiffres}.{fraction}" if fraction else chiffres)
        return _nombre_accepte(
            valeur,
            len(fraction),
            pourcentages if pourcent else nombres,
            pourcent=bool(pourcent),
        )

    controler(_NOMBRE, nombre)
    return ControleNombres(tuple(texte_refuse for _, texte_refuse in sorted(refuses)))
