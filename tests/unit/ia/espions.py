"""Espions partagés des tests de la couche LLM : un journal commun enregistre l'ordre des appels."""

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime

import polars as pl
from pydantic import BaseModel

from tests.doublures.fournisseur_factice import FournisseurFactice
from tests.doublures.pseudonymiseur_factice import PseudonymiseurFactice
from usine.contrats.llm import (
    MessageAgent,
    OutilAgent,
    ParametresAppel,
    ReponseAgentBrute,
    ReponseStructuree,
)
from usine.contrats.meteo import (
    CodeIndicateur,
    Couleur,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.prevision import (
    FacteurExplicatif,
    MethodePrevision,
    Prevision,
    RisqueEntreeRouge,
    StatutPrevision,
)
from usine.contrats.tickets import SCHEMA_TICKET_TEXTE

CLE_PSEUDO = b"cle-de-test-fictive"
NUMERO_COMPTE = "FR76 3000 6000 0112 3456 7890 189"
"""Numéro de compte fictif (IBAN de démonstration)."""
MOTIFS = {"COMPTE": r"FR\d{2}(?: \d{4}){5} \d{3}"}
PASSAGE_ID = "20261012T073000Z-abc123"
DATE_ARRETE = date(2026, 10, 9)
INSTANT = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)


def pseudonymiseur() -> PseudonymiseurFactice:
    """Pseudonymiseur factice qui reconnaît le numéro de compte."""
    return PseudonymiseurFactice(CLE_PSEUDO, MOTIFS)


def jeton_compte() -> str:
    """Jeton `COMPTE_<6 hex>` du numéro de compte fictif."""
    return pseudonymiseur().apercu(NUMERO_COMPTE)


class CacheMemoire:
    """Cache en mémoire qui satisfait `CacheLLM` et journalise ses accès."""

    def __init__(self, journal: list[str] | None = None) -> None:
        self.valeurs: dict[str, str] = {}
        self._journal = journal if journal is not None else []

    def lire(self, cle: str) -> str | None:
        self._journal.append("cache.lire")
        return self.valeurs.get(cle)

    def ecrire(self, cle: str, brut: str) -> None:
        self._journal.append("cache.ecrire")
        self.valeurs[cle] = brut


class EspionFournisseur:
    """Enveloppe un `FournisseurFactice` et journalise chaque appel structuré."""

    def __init__(self, fournisseur: FournisseurFactice, journal: list[str]) -> None:
        self.fournisseur = fournisseur
        self._journal = journal

    @property
    def version_modele(self) -> str:
        return self.fournisseur.version_modele

    def generer_structure[T: BaseModel](
        self, prompt: str, schema: type[T], parametres: ParametresAppel
    ) -> ReponseStructuree[T]:
        self._journal.append("fournisseur")
        return self.fournisseur.generer_structure(prompt, schema, parametres)

    def executer_agent(
        self,
        messages: Sequence[MessageAgent],
        outils: Sequence[OutilAgent],
        parametres: ParametresAppel,
    ) -> ReponseAgentBrute:
        self._journal.append("fournisseur.agent")
        return self.fournisseur.executer_agent(messages, outils, parametres)


class EspionPseudonymiseur:
    """Enveloppe un `PseudonymiseurFactice` et journalise chaque appel."""

    def __init__(self, pseudo: PseudonymiseurFactice, journal: list[str]) -> None:
        self.pseudo = pseudo
        self._journal = journal

    def pseudonymiser(self, texte: str) -> str:
        self._journal.append("pseudonymiser")
        return self.pseudo.pseudonymiser(texte)

    def reidentifier(self, texte: str) -> str:
        self._journal.append("reidentifier")
        return self.pseudo.reidentifier(texte)

    def apercu(self, texte: str) -> str:
        self._journal.append("apercu")
        return self.pseudo.apercu(texte)


def horloge_espion(journal: list[str]) -> Callable[[], datetime]:
    """Horloge figée ; la passerelle ne la lit qu'en formant la trace."""

    def horloge() -> datetime:
        journal.append("trace")
        return INSTANT

    return horloge


def fusionner_reidentifier(journal: list[str]) -> list[str]:
    """Journal dont seules les répétitions consécutives de `reidentifier` sont fusionnées.

    La ré-identification s'applique à chaque champ texte de la sortie ; tout autre appel répété
    (pseudonymiser, cache, fournisseur, contrôle, trace) reste visible.
    """
    return [
        nom
        for rang, nom in enumerate(journal)
        if nom != "reidentifier" or rang == 0 or journal[rang - 1] != nom
    ]


def meteo_rouge(
    entite: str = "ENT-A", tickets: tuple[str, ...] = ("DEMO-3", "DEMO-7")
) -> MeteoEntite:
    """Météo rouge d'une Entité, une Règle déclenchante sur `tickets`."""
    regle = RegleDeclenchante(
        code=CodeIndicateur.ind_1,
        couleur=Couleur.rouge,
        operateur=Operateur.superieur_ou_egal,
        numerateur=max(len(tickets), 1),
        denominateur=1,
        seuil_numerateur=1,
        seuil_denominateur=1,
        tickets_en_cause=tickets,
    )
    return MeteoEntite(
        date_arrete=DATE_ARRETE,
        entite=entite,
        couleur=Couleur.rouge,
        regles=(regle,),
        version_grille="grille123456",
    )


def textes(lignes: dict[str, tuple[str, str]], entite: str = "ENT-A") -> pl.DataFrame:
    """Table `SCHEMA_TICKET_TEXTE` d'Anomalies : clé → (titre, description)."""
    return pl.DataFrame(
        {
            "cle_ticket": list(lignes),
            "type_ticket": ["anomalie"] * len(lignes),
            "entite": [entite] * len(lignes),
            "titre": [titre for titre, _ in lignes.values()],
            "description": [description for _, description in lignes.values()],
        },
        schema=dict(SCHEMA_TICKET_TEXTE.colonnes),
    )


def prevision_rouge() -> Prevision:
    """Prévision projetée de `ENT-A` : 3/5, sortie le 15/10/2026 (14 au 20/10)."""
    return Prevision(
        date_arrete=DATE_ARRETE,
        entite="ENT-A",
        methode=MethodePrevision.baseline,
        statut=StatutPrevision.sortie_projetee,
        date_sortie_estimee=date(2026, 10, 15),
        date_sortie_optimiste=date(2026, 10, 14),
        date_sortie_pessimiste=date(2026, 10, 20),
        probabilite_numerateur=3,
        probabilite_denominateur=5,
        horizon_jours_ouvres=10,
        facteurs=(
            FacteurExplicatif(nom="stock", libelle="stock", numerateur=1234, denominateur=1),
            FacteurExplicatif(nom="velocite", libelle="vélocité", numerateur=7, denominateur=2),
            FacteurExplicatif(nom="evolution", libelle="évolution", numerateur=-3, denominateur=1),
        ),
        version_grille="grille123456",
    )


def risque_entree_rouge(indicateur: CodeIndicateur = CodeIndicateur.ind_1) -> RisqueEntreeRouge:
    """Risque d'entrée en rouge de `ENT-B` le 16/10/2026."""
    return RisqueEntreeRouge(
        date_arrete=DATE_ARRETE,
        entite="ENT-B",
        indicateur=indicateur,
        date_franchissement_estimee=date(2026, 10, 16),
        horizon_jours_ouvres=10,
        numerateur=4,
        denominateur=1,
        seuil_numerateur=6,
        seuil_denominateur=1,
        version_grille="grille123456",
    )
