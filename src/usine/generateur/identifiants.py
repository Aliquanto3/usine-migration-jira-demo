"""Identifiants sensibles fictifs des descriptions d'Anomalies (Story 1.4, FR-4).

Fabrication pure : tout le hasard vient de l'instance `Random` passée en paramètre. Chaque
identifiant est entièrement fictif et de forme manifestement factice :

- compte : IBAN au format français, code banque `99999`, clé de contrôle fausse (mod 97 ≠ 1) ;
- client : civilité, prénom et NOM pris dans des listes inventées, construites sur les racines
  « fictif, simulé, exemple, leurre, maquette, factice » ;
- identifiant client : 10 chiffres préfixés `99`, clé de Luhn fausse.

Les identifiants injectés servent de liste de référence au test de balayage de la
Pseudonymisation (SM-7) ; leurs types suivent `contrats.llm.MOTIF_TYPE_JETON`.
"""

import random
from dataclasses import dataclass
from enum import StrEnum


class TypeIdentifiant(StrEnum):
    """Type d'un identifiant injecté, au format des types de jetons de la Pseudonymisation.

    L'ordre des membres est celui des identifiants dans la phrase insérée.
    """

    CLIENT = "CLIENT"
    COMPTE = "COMPTE"
    ID_CLIENT = "ID_CLIENT"


@dataclass(frozen=True)
class IdentifiantInjecte:
    """Identifiant fictif inséré dans la description de l'Anomalie `cle_ticket`."""

    cle_ticket: str
    type: TypeIdentifiant
    valeur: str


CODE_BANQUE_FICTIF = "99999"
"""Code banque de tous les IBAN fictifs : signale le faux au premier regard."""

PREFIXE_ID_CLIENT = "99"
"""Préfixe de tous les identifiants clients fictifs."""

LONGUEUR_ID_CLIENT = 10
"""Nombre de chiffres d'un identifiant client, clé de Luhn comprise."""

LONGUEUR_BBAN = 23
"""Chiffres du BBAN français : banque (5), guichet (5), compte (11), clé RIB (2)."""

CIVILITES = ("M.", "Mme")
"""Civilités des clients fictifs."""

PRENOMS_FICTIFS = (
    "Fictivia",
    "Fictorin",
    "Simulie",
    "Simulien",
    "Exemplaine",
    "Exemplin",
    "Leurrette",
    "Leurrand",
    "Maquettine",
    "Maquettin",
    "Facticia",
    "Facticette",
)
"""Prénoms inventés, construits sur les racines fictif, simulé, exemple, leurre, maquette,
factice : aucun prénom réel."""

NOMS_FICTIFS = (
    "FICTIVET",
    "FICTIVARD",
    "SIMULARD",
    "SIMULOT",
    "EXEMPLON",
    "EXEMPLIER",
    "LEURREAU",
    "LEURRIN",
    "MAQUETTEAU",
    "MAQUETTIER",
    "FACTICIER",
    "FACTICEAU",
)
"""Noms de famille inventés, sur les mêmes racines : aucun nom réel."""

_LIBELLES = {
    TypeIdentifiant.CLIENT: "client",
    TypeIdentifiant.COMPTE: "compte",
    TypeIdentifiant.ID_CLIENT: "identifiant client",
}
"""Libellé qui précède chaque identifiant dans la phrase insérée."""


def _chiffres(nombre: int, rng: random.Random) -> str:
    return "".join(str(rng.randrange(10)) for _ in range(nombre))


def _numerique(iban: str) -> int:
    """IBAN réarrangé (4 premiers caractères en fin) et lettres converties (A = 10…)."""
    compact = iban.replace(" ", "")
    reordonne = compact[4:] + compact[:4]
    return int("".join(str(int(c, 36)) for c in reordonne))


def iban_valide(iban: str) -> bool:
    """Vrai si la clé de contrôle de `iban` est juste (ISO 13616 : mod 97 = 1)."""
    compact = iban.replace(" ", "")
    if len(compact) < 5 or not (compact.isascii() and compact.isalnum()):
        return False
    return _numerique(compact) % 97 == 1


def iban_fictif(rng: random.Random) -> str:
    """IBAN français fictif à clé fausse, groupé par 4 : `FRkk 9999 9ccc … ccc`.

    BBAN : code banque `CODE_BANQUE_FICTIF` puis 18 chiffres tirés ; la clé `kk` est tirée
    parmi les clés qui ne vérifient pas mod 97 = 1.
    """
    bban = CODE_BANQUE_FICTIF + _chiffres(LONGUEUR_BBAN - len(CODE_BANQUE_FICTIF), rng)
    fausses = [f"{k:02d}" for k in range(100) if not iban_valide(f"FR{k:02d}{bban}")]
    compact = f"FR{rng.choice(fausses)}{bban}"
    return " ".join(compact[i : i + 4] for i in range(0, len(compact), 4))


def luhn_valide(nombre: str) -> bool:
    """Vrai si la suite de chiffres `nombre` vérifie la clé de Luhn."""
    if not (nombre.isascii() and nombre.isdigit()):
        return False
    total = 0
    for rang, chiffre in enumerate(reversed(nombre)):
        valeur = int(chiffre)
        if rang % 2 == 1:
            valeur = valeur * 2 - 9 if valeur > 4 else valeur * 2
        total += valeur
    return total % 10 == 0


def identifiant_client_fictif(rng: random.Random) -> str:
    """Identifiant client fictif : `PREFIXE_ID_CLIENT`, chiffres tirés et clé de Luhn fausse."""
    corps = PREFIXE_ID_CLIENT + _chiffres(LONGUEUR_ID_CLIENT - len(PREFIXE_ID_CLIENT) - 1, rng)
    fausses = [c for c in "0123456789" if not luhn_valide(corps + c)]
    return corps + rng.choice(fausses)


def nom_client_fictif(rng: random.Random) -> str:
    """Nom de client inventé : civilité, prénom et NOM des listes fictives."""
    civilite = rng.choice(CIVILITES)
    prenom = rng.choice(PRENOMS_FICTIFS)
    nom = rng.choice(NOMS_FICTIFS)
    return f"{civilite} {prenom} {nom}"


_FABRIQUES = {
    TypeIdentifiant.CLIENT: nom_client_fictif,
    TypeIdentifiant.COMPTE: iban_fictif,
    TypeIdentifiant.ID_CLIENT: identifiant_client_fictif,
}


def phrase_identifiants(
    entite: str, rng: random.Random
) -> tuple[str, tuple[tuple[TypeIdentifiant, str], ...]]:
    """Phrase citant un à trois identifiants fictifs, et ces identifiants.

    Le sous-ensemble non vide de types est tiré, puis rangé dans l'ordre de
    `TypeIdentifiant` ; chaque valeur est fabriquée dans cet ordre. Exemple : « Cas cité par
    l'Entité ENT-B : client Mme Simulie MAQUETTEAU, compte FR42 9999 9123 …, identifiant
    client 9912345670. »
    """
    tires = set(rng.sample(list(TypeIdentifiant), rng.randint(1, len(TypeIdentifiant))))
    identifiants = tuple(
        (type_identifiant, _FABRIQUES[type_identifiant](rng))
        for type_identifiant in TypeIdentifiant
        if type_identifiant in tires
    )
    fragments = ", ".join(f"{_LIBELLES[t]} {valeur}" for t, valeur in identifiants)
    return f"Cas cité par l'Entité {entite} : {fragments}.", identifiants
