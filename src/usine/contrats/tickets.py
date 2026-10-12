"""Vocabulaire canonique des tickets et tables de tickets (AD-23, H-17, H-18).

Les valeurs canoniques sont en snake_case sans accent ; les libellés d'affichage sont dans
`LIBELLES`. La correspondance Jira → canonique vit dans `config/jira.yaml`, appliquée par les
adaptateurs seulement. `cause_racine` n'est jamais un `Champ` : c'est une vérité terrain.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

import polars as pl

from usine.contrats.schemas import SchemaTable, enum_polars

MOTIF_CLE_TICKET = r"[A-Z][A-Z0-9]+-\d+"
"""Forme d'une clé de ticket (`DEMO-123`) ; une clé n'est jamais pseudonymisée."""


def rang_cle(cle: str) -> tuple[str, int, str]:
    """Clé de tri d'une clé de ticket : projet, numéro, puis clé entière.

    `DEMO-2` vient avant `DEMO-10`. Une clé sans numéro ASCII (`DEMO-X`) prend le numéro -1 :
    elle précède les clés numérotées de son projet, et la clé entière départage.
    """
    projet, _, numero = cle.rpartition("-")
    return projet, int(numero) if numero.isascii() and numero.isdigit() else -1, cle


class TypeTicket(StrEnum):
    """Type de ticket Jira du Programme."""

    anomalie = "anomalie"
    cas_de_test = "cas_de_test"
    certification = "certification"


class Champ(StrEnum):
    """Champ d'un ticket porté par un `Evenement` (jamais `cause_racine`)."""

    statut = "statut"
    entite = "entite"
    vague = "vague"
    domaine = "domaine"
    gravite = "gravite"
    phase = "phase"
    titre = "titre"
    description = "description"
    statut_test = "statut_test"
    statut_certification = "statut_certification"


class StatutAnomalie(StrEnum):
    """Workflow fictif des Anomalies (H-17)."""

    nouvelle = "nouvelle"
    en_analyse = "en_analyse"
    en_correction = "en_correction"
    a_retester = "a_retester"
    fermee = "fermee"
    rejetee = "rejetee"


class Gravite(StrEnum):
    """Gravité d'une Anomalie."""

    bloquante = "bloquante"
    majeure = "majeure"
    mineure = "mineure"


class Phase(StrEnum):
    """Phase de test."""

    migration_a_blanc = "migration_a_blanc"
    recette = "recette"
    tnr = "tnr"


class StatutTest(StrEnum):
    """Statut d'un Cas de test."""

    ok = "ok"
    ko = "ko"
    non_execute = "non_execute"


class StatutCertification(StrEnum):
    """Statut d'une Certification."""

    accordee = "accordee"
    reservee = "reservee"
    refusee = "refusee"


class CauseRacine(StrEnum):
    """Les sept Causes racines (H-18) ; jamais portées par un `Evenement`."""

    reprise_donnees = "reprise_donnees"
    regle_transformation = "regle_transformation"
    parametrage = "parametrage"
    interface_flux = "interface_flux"
    environnement = "environnement"
    donnee_test = "donnee_test"
    hors_perimetre = "hors_perimetre"


def _valeurs(enumeration: type[StrEnum]) -> frozenset[str]:
    return frozenset(membre.value for membre in enumeration)


DOMAINES_CANONIQUES: Mapping[Champ, frozenset[str] | None] = MappingProxyType(
    {
        Champ.statut: _valeurs(StatutAnomalie),
        Champ.entite: None,
        Champ.vague: None,
        Champ.domaine: None,
        Champ.gravite: _valeurs(Gravite),
        Champ.phase: _valeurs(Phase),
        Champ.titre: None,
        Champ.description: None,
        Champ.statut_test: _valeurs(StatutTest),
        Champ.statut_certification: _valeurs(StatutCertification),
    }
)
"""Domaine de valeurs de chaque `Champ` ; `None` = valeur libre (codes, textes)."""

CHAMPS_PAR_TYPE: Mapping[TypeTicket, frozenset[Champ]] = MappingProxyType(
    {
        TypeTicket.anomalie: frozenset(
            {
                Champ.statut,
                Champ.entite,
                Champ.vague,
                Champ.domaine,
                Champ.gravite,
                Champ.phase,
                Champ.titre,
                Champ.description,
            }
        ),
        TypeTicket.cas_de_test: frozenset(
            {
                Champ.statut_test,
                Champ.entite,
                Champ.vague,
                Champ.domaine,
                Champ.phase,
                Champ.titre,
                Champ.description,
            }
        ),
        TypeTicket.certification: frozenset(
            {
                Champ.statut_certification,
                Champ.entite,
                Champ.vague,
                Champ.titre,
                Champ.description,
            }
        ),
    }
)
"""Champs portés par chaque type de ticket ; le workflow `statut` est celui des Anomalies."""

STATUTS_FERMES: frozenset[StatutAnomalie] = frozenset(
    {StatutAnomalie.fermee, StatutAnomalie.rejetee}
)
"""Statuts d'une Anomalie non ouverte ; y entrer est une Sortie, en sortir une Entrée."""

LIBELLES: Mapping[str, str] = MappingProxyType(
    {
        TypeTicket.anomalie: "Anomalie",
        TypeTicket.cas_de_test: "Cas de test",
        TypeTicket.certification: "Certification",
        StatutAnomalie.nouvelle: "Nouvelle",
        StatutAnomalie.en_analyse: "En analyse",
        StatutAnomalie.en_correction: "En correction",
        StatutAnomalie.a_retester: "À retester",
        StatutAnomalie.fermee: "Fermée",
        StatutAnomalie.rejetee: "Rejetée",
        Gravite.bloquante: "Bloquante",
        Gravite.majeure: "Majeure",
        Gravite.mineure: "Mineure",
        Phase.migration_a_blanc: "Migration à blanc",
        Phase.recette: "Recette",
        Phase.tnr: "TNR",
        StatutTest.ok: "OK",
        StatutTest.ko: "KO",
        StatutTest.non_execute: "Non exécuté",
        StatutCertification.accordee: "Accordée",
        StatutCertification.reservee: "Réservée",
        StatutCertification.refusee: "Refusée",
        CauseRacine.reprise_donnees: "Reprise de données",
        CauseRacine.regle_transformation: "Règle de transformation",
        CauseRacine.parametrage: "Paramétrage",
        CauseRacine.interface_flux: "Interface ou flux",
        CauseRacine.environnement: "Environnement",
        CauseRacine.donnee_test: "Donnée de test",
        CauseRacine.hors_perimetre: "Hors périmètre (faux positif)",
    }
)
"""Libellé français d'affichage de chaque valeur canonique."""

SCHEMA_TICKET_ETAT = SchemaTable(
    "SCHEMA_TICKET_ETAT",
    {
        "date": pl.Date(),
        "cle_ticket": pl.Utf8(),
        "type_ticket": enum_polars(TypeTicket),
        "entite": pl.Utf8(),
        "vague": pl.Utf8(),
        "domaine": pl.Utf8(),
        "gravite": enum_polars(Gravite),
        "phase": enum_polars(Phase),
        "statut": enum_polars(StatutAnomalie),
        "statut_test": enum_polars(StatutTest),
        "statut_certification": enum_polars(StatutCertification),
        "date_derniere_entree": pl.Date(),
    },
    non_nulles=frozenset({"date", "cle_ticket", "type_ticket"}),
)
"""`TicketEtat` : état de chaque ticket à chaque Jour ouvré (`tickets_etats.parquet`).

Les colonnes sans objet pour le type de ticket sont nulles. Les colonnes d'énumération sont
des `pl.Enum` : une valeur hors du domaine canonique est refusée.
"""

SCHEMA_TICKET_TEXTE = SchemaTable(
    "SCHEMA_TICKET_TEXTE",
    {
        "cle_ticket": pl.Utf8(),
        "type_ticket": enum_polars(TypeTicket),
        "entite": pl.Utf8(),
        "titre": pl.Utf8(),
        "description": pl.Utf8(),
    },
    non_nulles=frozenset({"cle_ticket", "type_ticket"}),
)
"""`TicketTexte` : titre et description à la Date d'arrêté (`tickets_textes.parquet`)."""
