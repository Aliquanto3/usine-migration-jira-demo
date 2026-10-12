"""Outils des tests de la source composite : Journal aux clés Jira et injection simulée.

L'injection simulée part de l'état des tickets du Journal à la Date d'injection, calculé par
le vrai domaine (`tickets_etats`) : une création Jira par ticket dans l'intervalle
d'injection, suivie au même horodatage d'un attribut initial par champ d'état renseigné,
comme `convertir_ticket` (`C-<id>`, `C-<id>-<champ>`). Données fictives, projet `DEMO`.
"""

from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path

from tests.unit.adaptateurs.journal.outils import manifeste_pour
from usine.adaptateurs.composite import CHAMPS_ETAT
from usine.adaptateurs.journal import SourceJournal
from usine.config import charger_yaml
from usine.contrats.config import ConfigProgramme
from usine.contrats.evenements import (
    Evenement,
    ManifesteInjection,
    NatureEvenement,
    SourceEvenement,
)
from usine.contrats.tickets import CHAMPS_PAR_TYPE, Champ, TypeTicket
from usine.domaine.instantanes import tickets_etats
from usine.generateur.journal import Generation, generer, serialiser_journal

RACINE = Path(__file__).resolve().parents[4]
PREMIER_ID = 10_000
"""Identifiant Jira (`id`) du premier ticket injecté."""


def generation_reduite() -> Generation:
    """Journal du mini-générateur (Programme réduit, graine 42) : se termine le 2026-10-09."""
    config = charger_yaml(RACINE / "tests/unit/generateur/programme_reduit.yaml", ConfigProgramme)
    return generer(config, 42, date(2026, 10, 12))


def journal_aux_cles_jira(
    repertoire: Path,
    generation: Generation,
    manifeste: ManifesteInjection | None = None,
) -> SourceJournal:
    """Écrit le Journal sous `repertoire` et le lit aux clés Jira (`manifeste_pour` par défaut)."""
    chemin = repertoire / "journal.jsonl"
    chemin.write_bytes(serialiser_journal(generation))
    if manifeste is None:
        manifeste = manifeste_pour(generation.entete, generation.evenements)
    return SourceJournal(chemin, manifeste)


def injection_simulee(
    journal: SourceJournal,
    ecarts: Mapping[str, Mapping[Champ, str]] | None = None,
    source: SourceEvenement = SourceEvenement.jira_cloud,
) -> list[Evenement]:
    """Événements Jira d'une injection de l'état du Journal à la Date d'injection.

    Créations réparties dans `[debut_injection, horodatage_fin_injection]` ; `ecarts`
    (clé Jira → champ → valeur) rend l'injection infidèle sur ces champs.
    """
    manifeste = journal.manifeste
    assert manifeste is not None
    etats = tickets_etats(list(journal.evenements()), [manifeste.date_injection])
    debut, fin = manifeste.debut_injection, manifeste.horodatage_fin_injection
    lignes = list(etats.iter_rows(named=True))
    evenements: list[Evenement] = []
    for rang, ligne in enumerate(lignes):
        cle = ligne["cle_ticket"]
        type_ticket = TypeTicket(ligne["type_ticket"])
        instant = debut + (fin - debut) * rang // max(len(lignes) - 1, 1)
        id_ticket = PREMIER_ID + rang
        communs = {"cle_ticket": cle, "type_ticket": type_ticket, "source": source}
        evenements.append(
            Evenement(
                id_evenement=f"C-{id_ticket}",
                horodatage=instant,
                nature=NatureEvenement.creation,
                **communs,
            )
        )
        valeurs = {champ: ligne[champ.value] for champ in CHAMPS_ETAT}
        valeurs.update((ecarts or {}).get(cle, {}))
        for champ in CHAMPS_ETAT:
            if champ not in CHAMPS_PAR_TYPE[type_ticket] or valeurs[champ] is None:
                continue
            evenements.append(
                Evenement(
                    id_evenement=f"C-{id_ticket}-{champ.value}",
                    horodatage=instant,
                    nature=NatureEvenement.modification_champ,
                    champ=champ,
                    vers=valeurs[champ],
                    **communs,
                )
            )
    return evenements


def etat_a_l_injection(journal: SourceJournal, cle: str, champ: Champ) -> str | None:
    """Valeur de `champ` du ticket `cle` à la Date d'injection, selon le Journal."""
    manifeste = journal.manifeste
    assert manifeste is not None
    etats = tickets_etats(list(journal.evenements()), [manifeste.date_injection])
    valeur = etats.filter(etats["cle_ticket"] == cle)[champ.value].item()
    return None if valeur is None else str(valeur)


def premiere_anomalie(journal: SourceJournal, sauf: frozenset[str] = frozenset()) -> str:
    """Clé Jira de la première Anomalie du Journal (hors `sauf`) qui a une gravité."""
    for evenement in journal.evenements():
        if (
            evenement.type_ticket is TypeTicket.anomalie
            and evenement.champ is Champ.gravite
            and evenement.cle_ticket not in sauf
        ):
            return evenement.cle_ticket
    raise AssertionError("aucune Anomalie avec gravité dans le Journal")


def autre_valeur(champ: Champ, valeur: str | None) -> str:
    """Une valeur canonique de `champ` différente de `valeur`."""
    domaines = {
        Champ.gravite: ("bloquante", "majeure", "mineure"),
        Champ.statut: ("en_analyse", "en_correction", "fermee"),
    }
    return next(v for v in domaines[champ] if v != valeur)


def transition_jira(
    cle: str,
    de: str | None,
    vers: str,
    instant: datetime,
    id_historique: str = "20001",
    source: SourceEvenement = SourceEvenement.jira_cloud,
) -> Evenement:
    """Transition faite à la main dans Jira (`<id historique>-1`)."""
    return Evenement(
        id_evenement=f"{id_historique}-1",
        cle_ticket=cle,
        type_ticket=TypeTicket.anomalie,
        horodatage=instant,
        nature=NatureEvenement.transition,
        champ=Champ.statut,
        de=de,
        vers=vers,
        source=source,
    )
