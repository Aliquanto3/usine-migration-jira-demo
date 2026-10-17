"""`ConsultationPassage` : lecteur unique d'un Passage, publié ou en construction (AD-11, AD-22).

Chaque fichier est lu en ouvrir-lire-fermer, sa version de contrats vérifiée (métadonnée
Parquet, enveloppe JSON, manifeste) et chaque table validée par son `SCHEMA_X`. Un fichier
absent du Passage (étape bouchon ou sautée) donne un résultat vide ; seul le manifeste est
obligatoire. Un `date_arrete` à `None` désigne la Date d'arrêté du Passage.

Un Passage de version majeure étrangère est refusé (AD-2) : quand `manifeste.json` existe, il
fait foi pour tout le Passage. Il est lu (version comprise) avant tout autre fichier, puis mis
en cache ; chaque lecture de données du Passage lève alors une `UsineErreur` qui le nomme.
`url_ticket` (aucun fichier du Passage lu) et `dernier_passage` (qui parcourt les autres
Passages) ne sont pas concernés. Un Passage en construction, sans manifeste, reste lisible :
ses fichiers sont contrôlés un par un.
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Literal

import polars as pl
from pydantic import ValidationError

from usine.contrats.agent import AnomalieResume, ResultatListAnomalies
from usine.contrats.calcul import SCHEMA_INDICATEUR, SCHEMA_INSTANTANE, SCHEMA_KPI, SCHEMA_TENDANCE
from usine.contrats.calendrier import analyser_date_iso, jour_ouvre_precedent, jours_ouvres
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    SCHEMA_REPARTITION_CAUSES,
    SortieClassification,
    SortieExplication,
    SortieNarration,
)
from usine.contrats.meteo import EvolutionMeteo, MeteoEntite
from usine.contrats.passage import (
    CONTENUS_JSON,
    FICHIERS_PASSAGE,
    EnveloppeFichier,
    ManifestePassage,
    chemin_fichier_passage,
    lire_enveloppe,
)
from usine.contrats.prevision import ContenuPrevisions, Prevision, RisqueEntreeRouge
from usine.contrats.schemas import SchemaTable, valider
from usine.contrats.tickets import (
    SCHEMA_TICKET_ETAT,
    SCHEMA_TICKET_TEXTE,
    STATUTS_FERMES,
    Gravite,
    Phase,
    StatutAnomalie,
    TypeTicket,
    rang_cle,
)
from usine.contrats.trace import EntreeTrace
from usine.contrats.versions import CLE_VERSION, verifier_version
from usine.ports.consultation import Palier

FICHIER_MANIFESTE = FICHIERS_PASSAGE["manifeste"]
"""Nom du manifeste, seul fichier obligatoire d'un Passage."""

_PREFIXE_CACHE = "."
"""Répertoires ignorés par `dernier_passage` (`.en-cours-*`)."""

journal = logging.getLogger(__name__)


def lire_table(chemin: Path, schema: SchemaTable) -> pl.DataFrame:
    """Lit une table Parquet d'un Passage : version de contrats vérifiée, puis schéma validé."""
    try:
        metadonnees = pl.read_parquet_metadata(chemin)
    except FileNotFoundError as exc:
        raise UsineErreur(f"{chemin} : fichier du Passage introuvable") from exc
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise UsineErreur(f"{chemin} : fichier Parquet illisible ({exc})") from exc
    version = metadonnees.get(CLE_VERSION)
    if version is None:
        raise UsineErreur(f"{chemin} : métadonnée « {CLE_VERSION} » absente")
    try:
        verifier_version(version)
    except UsineErreur as exc:
        raise UsineErreur(f"{chemin} : {exc}") from exc
    try:
        table = pl.read_parquet(chemin)
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise UsineErreur(f"{chemin} : fichier Parquet illisible ({exc})") from exc
    try:
        return valider(table, schema)
    except UsineErreur as exc:
        raise UsineErreur(f"{chemin} : {exc}") from exc


def _lire_octets(chemin: Path) -> bytes:
    try:
        return chemin.read_bytes()
    except FileNotFoundError as exc:
        raise UsineErreur(f"{chemin} : fichier du Passage introuvable") from exc
    except OSError as exc:
        raise UsineErreur(f"{chemin} : fichier illisible ({exc.strerror or exc})") from exc


def lire_manifeste(chemin: Path) -> ManifestePassage:
    """Lit `manifeste.json` : version de contrats vérifiée avant toute validation."""
    octets = _lire_octets(chemin)
    try:
        donnees = json.loads(octets)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise UsineErreur(f"{chemin} : manifeste illisible ({exc})") from exc
    version = donnees.get(CLE_VERSION) if isinstance(donnees, dict) else None
    if not isinstance(version, str):
        raise UsineErreur(f"{chemin} : « {CLE_VERSION} » absente ou illisible")
    try:
        verifier_version(version)
        return ManifestePassage.model_validate(donnees)
    except UsineErreur as exc:
        raise UsineErreur(f"{chemin} : {exc}") from exc
    except ValidationError as exc:
        raise UsineErreur(
            f"{chemin} : manifeste invalide ({exc.error_count()} erreur(s)) : {exc}"
        ) from exc


class ConsultationPassage:
    """Lecteur d'un Passage (publié ou en construction) dans `repertoire`.

    `racine_passages` (`sorties/passages/`) sert à `dernier_passage` ; par défaut, elle se
    déduit de `repertoire` (`<racine>/<date>/<id>/` publié, `<racine>/.en-cours-<id>/` en
    construction). `url_jira` est l'URL du site Jira (`None` en Mode repli ou sans
    configuration Jira). `date_arrete` est la Date d'arrêté d'un Passage en construction,
    utilisée tant que le manifeste n'existe pas.
    """

    def __init__(
        self,
        repertoire: Path,
        *,
        racine_passages: Path | None = None,
        url_jira: str | None = None,
        date_arrete: date | None = None,
    ) -> None:
        self._repertoire = repertoire
        self._date_arrete = date_arrete
        if racine_passages is None:
            parent = repertoire.parent
            publie = analyser_date_iso(parent.name) is not None
            racine_passages = parent.parent if publie else parent
        self._racine_passages = racine_passages
        self._url_jira = url_jira.rstrip("/") if url_jira else None
        self._tables: dict[str, pl.DataFrame] = {}
        self._json: dict[str, object] = {}
        self._manifeste: ManifestePassage | None = None

    @property
    def repertoire(self) -> Path:
        """Répertoire du Passage lu."""
        return self._repertoire

    # --- Lecture des fichiers (une fois chacun : un fichier de Passage n'est écrit qu'une fois)

    def _chemin(self, nom: str) -> Path:
        return self._repertoire / FICHIERS_PASSAGE[nom]

    def _verifier_passage(self) -> None:
        """Lit le manifeste s'il existe (version vérifiée, AD-2), une fois grâce au cache.

        Les lignes de `trace/*.jsonl` ne portent pas de version, et un fichier en `1.x` peut
        cohabiter avec un manifeste d'une autre version majeure : le manifeste fait foi.
        """
        if self._manifeste is None and self._chemin("manifeste").exists():
            self.manifeste()

    def _table(self, nom: str, schema: SchemaTable) -> pl.DataFrame:
        """Table `nom` validée ; table vide au schéma si le fichier est absent du Passage."""
        self._verifier_passage()
        if nom not in self._tables:
            chemin = self._chemin(nom)
            if chemin.exists():
                self._tables[nom] = lire_table(chemin, schema)
            else:
                return pl.DataFrame(schema=dict(schema.colonnes))
        return self._tables[nom]

    def _contenu(self, nom: str) -> object | None:
        """Contenu de l'enveloppe JSON `nom`, ou `None` si le fichier est absent du Passage."""
        self._verifier_passage()
        if nom not in self._json:
            chemin = self._chemin(nom)
            if not chemin.exists():
                return None
            octets = _lire_octets(chemin)
            try:
                enveloppe: EnveloppeFichier[object] = lire_enveloppe(octets, CONTENUS_JSON[nom])
            except UsineErreur as exc:
                raise UsineErreur(f"{chemin} : {exc}") from exc
            self._json[nom] = enveloppe.contenu
        return self._json[nom]

    def _meteos(self) -> tuple[MeteoEntite, ...]:
        contenu = self._contenu("meteo")
        return contenu if isinstance(contenu, tuple) else ()

    def _date(self, date_arrete: date | None) -> date:
        """Date demandée, ou Date d'arrêté du Passage.

        Celle-ci vient du manifeste ; pendant la construction, de la `date_arrete` donnée au
        lecteur, sinon de la dernière date de `meteo.json`, puis de `tickets_etats`.
        """
        jour = self._date_connue(date_arrete)
        if jour is None:
            raise UsineErreur(
                f"{self._chemin('manifeste')} : Date d'arrêté du Passage indéterminable"
                " (ni manifeste, ni Météo, ni `date_arrete` donnée)"
            )
        return jour

    def _date_connue(self, date_arrete: date | None) -> date | None:
        """Comme `_date`, mais `None` si la Date d'arrêté du Passage est indéterminable."""
        if date_arrete is not None:
            return date_arrete
        if self._manifeste is not None or self._chemin("manifeste").exists():
            return self.manifeste().date_arrete
        if self._date_arrete is not None:
            return self._date_arrete
        dates = self.dates_disponibles()
        if dates:
            return dates[-1]
        derniere = self._table("tickets_etats", SCHEMA_TICKET_ETAT).get_column("date").max()
        return derniere if isinstance(derniere, date) else None

    # --- Passage ---

    def dernier_passage(
        self, sans_classification_initiale: bool = False
    ) -> ManifestePassage | None:
        """Manifeste de `(date_arrete, horodatage_fin)` maximal sous la racine des Passages.

        `sans_classification_initiale=True` écarte les Passages dont le manifeste porte
        `classification_initiale` (mesure de FR-44).
        """
        racine = self._racine_passages
        if not racine.is_dir():
            return None
        meilleur: ManifestePassage | None = None
        for repertoire_date in sorted(racine.iterdir()):
            nom = repertoire_date.name
            if (
                not repertoire_date.is_dir()
                or nom.startswith(_PREFIXE_CACHE)
                or analyser_date_iso(nom) is None
            ):
                continue
            for repertoire in sorted(repertoire_date.iterdir()):
                chemin = repertoire / FICHIER_MANIFESTE
                if repertoire.name.startswith(_PREFIXE_CACHE) or not chemin.is_file():
                    continue
                try:
                    manifeste = lire_manifeste(chemin)
                except UsineErreur as exc:
                    journal.warning("Passage ignoré, manifeste illisible : %s", exc)
                    continue
                if (manifeste.date_arrete.isoformat(), manifeste.passage_id) != (
                    nom,
                    repertoire.name,
                ):
                    journal.warning(
                        "Passage ignoré, %s : manifeste du Passage %s (%s) rangé sous %s/%s",
                        chemin,
                        manifeste.passage_id,
                        manifeste.date_arrete.isoformat(),
                        nom,
                        repertoire.name,
                    )
                    continue
                if sans_classification_initiale and manifeste.classification_initiale:
                    continue
                if meilleur is None or (manifeste.date_arrete, manifeste.horodatage_fin) > (
                    meilleur.date_arrete,
                    meilleur.horodatage_fin,
                ):
                    meilleur = manifeste
        return meilleur

    def manifeste(self) -> ManifestePassage:
        """Manifeste du Passage lu ; son absence lève une `UsineErreur` qui le nomme."""
        if self._manifeste is None:
            self._manifeste = lire_manifeste(self._chemin("manifeste"))
        return self._manifeste

    def dates_disponibles(self) -> tuple[date, ...]:
        """Dates couvertes par `meteo.json`, triées."""
        return tuple(sorted({m.date_arrete for m in self._meteos()}))

    # --- Météo ---

    def meteo(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[MeteoEntite, ...]:
        """Météo par Entité à la date, dans l'ordre de `meteo.json`."""
        meteos = self._meteos()
        if not meteos:
            return ()
        jour = self._date(date_arrete)
        return tuple(
            m for m in meteos if m.date_arrete == jour and (entite is None or m.entite == entite)
        )

    def evolution_meteo(self, date_arrete: date | None = None) -> tuple[EvolutionMeteo, ...]:
        """Météo à J, J-1 et J-5 par Entité ; couleur `None` si la date n'est pas couverte."""
        meteos = self._meteos()
        if not meteos:
            return ()
        jour = self._date(date_arrete)
        couleurs = {(m.date_arrete, m.entite): m.couleur for m in meteos}
        j1, j5 = jour_ouvre_precedent(jour, 1), jour_ouvre_precedent(jour, 5)
        return tuple(
            EvolutionMeteo(
                entite=m.entite,
                date_arrete=jour,
                couleur=m.couleur,
                date_j1=j1,
                couleur_j1=couleurs.get((j1, m.entite)),
                date_j5=j5,
                couleur_j5=couleurs.get((j5, m.entite)),
            )
            for m in meteos
            if m.date_arrete == jour
        )

    # --- Tables ---

    def _filtrer(
        self,
        table: pl.DataFrame,
        date_arrete: date | None,
        colonne_entite: str,
        entite: str | None,
    ) -> pl.DataFrame:
        if table.is_empty():
            return table
        table = table.filter(pl.col("date") == self._date(date_arrete))
        if entite is not None:
            table = table.filter(pl.col(colonne_entite) == entite)
        return table

    def instantanes(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> pl.DataFrame:
        """Table `SCHEMA_INSTANTANE` à la date."""
        table = self._table("instantanes", SCHEMA_INSTANTANE)
        return self._filtrer(table, date_arrete, "entite", entite)

    def indicateurs(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> pl.DataFrame:
        """Table `SCHEMA_INDICATEUR` à la date."""
        table = self._table("indicateurs", SCHEMA_INDICATEUR)
        return self._filtrer(table, date_arrete, "entite", entite)

    def kpi(self, date_arrete: date | None = None, entite: str | None = None) -> pl.DataFrame:
        """Table `SCHEMA_KPI` à la date ; `entite=None` rend tous les périmètres."""
        table = self._table("kpi", SCHEMA_KPI)
        return self._filtrer(table, date_arrete, "perimetre", entite)

    def tendances(self, entite: str | None = None, code_kpi: str | None = None) -> pl.DataFrame:
        """Table `SCHEMA_TENDANCE`, filtrée par périmètre et par KPI."""
        table = self._table("tendances", SCHEMA_TENDANCE)
        if entite is not None:
            table = table.filter(pl.col("perimetre") == entite)
        if code_kpi is not None:
            table = table.filter(pl.col("code_kpi") == code_kpi)
        return table

    def tickets_etats(self, date_arrete: date | None = None) -> pl.DataFrame:
        """Table `SCHEMA_TICKET_ETAT` à la date."""
        table = self._table("tickets_etats", SCHEMA_TICKET_ETAT)
        if table.is_empty():
            return table
        return table.filter(pl.col("date") == self._date(date_arrete))

    def textes_tickets(self) -> pl.DataFrame:
        """Table `SCHEMA_TICKET_TEXTE` entière (titres et descriptions du Passage)."""
        return self._table("tickets_textes", SCHEMA_TICKET_TEXTE)

    # --- Anomalies ---

    def anomalies(
        self,
        date_arrete: date | None = None,
        entite: str | None = None,
        gravite: Gravite | None = None,
        phase: Phase | None = None,
        domaine: str | None = None,
        limite: int | None = None,
        palier: Palier = 2,
    ) -> ResultatListAnomalies:
        """Anomalies ouvertes à la date, filtrées, triées par numéro de clé.

        La cause racine proposée vient de la classification (Palier 2) : `None` en `palier=1`.

        Sans `tickets_etats` dans le Passage, le résultat est vide ; si la Date d'arrêté est
        alors indéterminable (ni manifeste, ni Météo, ni `date_arrete`), lève une `UsineErreur`.
        """
        if limite is not None and limite < 0:
            raise UsineErreur(f"limite invalide : {limite!r} (entier ≥ 0 attendu)")
        if self._table("tickets_etats", SCHEMA_TICKET_ETAT).is_empty():
            return ResultatListAnomalies(date_arrete=self._date(date_arrete), anomalies=(), total=0)
        jour = self._date(date_arrete)
        table = self.tickets_etats(jour).filter(
            (pl.col("type_ticket") == TypeTicket.anomalie.value)
            & ~pl.col("statut").is_in([s.value for s in STATUTS_FERMES])
        )
        for colonne, valeur in (
            ("entite", entite),
            ("gravite", None if gravite is None else gravite.value),
            ("phase", None if phase is None else phase.value),
            ("domaine", domaine),
        ):
            if valeur is not None:
                table = table.filter(pl.col(colonne) == valeur)
        causes = {c.cle_ticket: c.cause_racine for c in self.classification(palier)}
        lignes = sorted(
            table.iter_rows(named=True), key=lambda ligne: rang_cle(ligne["cle_ticket"])
        )
        total = len(lignes)
        if limite is not None:
            lignes = lignes[:limite]
        return ResultatListAnomalies(
            date_arrete=jour,
            anomalies=tuple(
                AnomalieResume(
                    cle_ticket=ligne["cle_ticket"],
                    entite=ligne["entite"] or "",
                    gravite=Gravite(ligne["gravite"]),
                    phase=Phase(ligne["phase"]),
                    domaine=ligne["domaine"] or "",
                    statut=StatutAnomalie(ligne["statut"]),
                    age_jours_ouvres=_age(ligne["date_derniere_entree"], jour),
                    cause_racine_proposee=causes.get(ligne["cle_ticket"]),
                )
                for ligne in lignes
            ),
            total=total,
        )

    # --- Prévisions ---

    def _previsions(self) -> ContenuPrevisions:
        contenu = self._contenu("previsions")
        if isinstance(contenu, ContenuPrevisions):
            return contenu
        return ContenuPrevisions(previsions=(), risques=())

    def previsions(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[Prevision, ...]:
        """Prévisions de sortie du rouge à la date (statistiques, jamais LLM : pas de palier).

        `()` sans `previsions.json` : Passage antérieur au câblage de l'étape `prevision`
        (Story 5.3) ou en construction avant elle. C'est la valeur absente explicite, distincte
        d'une `Prevision` de statut `pas_de_sortie_projetee` ; `consultation.prevision` dit si
        la Prévision a été calculée.
        """
        previsions = self._previsions().previsions
        if not previsions:
            return ()
        jour = self._date(date_arrete)
        return tuple(
            p
            for p in previsions
            if p.date_arrete == jour and (entite is None or p.entite == entite)
        )

    def risques(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[RisqueEntreeRouge, ...]:
        """Risques d'entrée en rouge à la date.

        `()` sans `previsions.json` (Passage antérieur au câblage de l'étape `prevision`) comme
        sans Risque : `consultation.prevision` distingue les deux par le manifeste.
        """
        risques = self._previsions().risques
        if not risques:
            return ()
        jour = self._date(date_arrete)
        return tuple(
            r for r in risques if r.date_arrete == jour and (entite is None or r.entite == entite)
        )

    # --- Sorties LLM (vides en Palier 1, FR-46) ---

    def _sorties_llm(self, nom: str, palier: Palier) -> tuple[Any, ...]:
        """Contenu du fichier LLM `nom` (type de `CONTENUS_JSON`), vide en Palier 1."""
        self._verifier_passage()
        if palier == 1:
            return ()
        contenu = self._contenu(nom)
        return contenu if isinstance(contenu, tuple) else ()

    def classification(self, palier: Palier = 2) -> tuple[SortieClassification, ...]:
        """Causes racines proposées ; vide en Palier 1 ou sans fichier."""
        sorties: tuple[SortieClassification, ...] = self._sorties_llm("classification", palier)
        return sorties

    def repartition_causes(self, entite: str | None = None, palier: Palier = 2) -> pl.DataFrame:
        """Table `SCHEMA_REPARTITION_CAUSES` ; vide en Palier 1 ou sans fichier.

        Filtrée sur la Date d'arrêté du Passage, puis sur l'Entité.
        """
        self._verifier_passage()
        if palier == 1:
            return pl.DataFrame(schema=dict(SCHEMA_REPARTITION_CAUSES.colonnes))
        table = self._table("repartition_causes", SCHEMA_REPARTITION_CAUSES)
        if not table.is_empty():
            table = table.filter(pl.col("date") == self._date(None))
        if entite is not None:
            table = table.filter(pl.col("entite") == entite)
        return table

    def explications(
        self, entite: str | None = None, palier: Palier = 2
    ) -> tuple[SortieExplication, ...]:
        """Explications sourcées ; vides en Palier 1 ou sans fichier."""
        sorties: tuple[SortieExplication, ...] = self._sorties_llm("explications", palier)
        return tuple(s for s in sorties if entite is None or s.entite == entite)

    def narrations(
        self, entite: str | None = None, palier: Palier = 2
    ) -> tuple[SortieNarration, ...]:
        """Narrations des Prévisions ; vides en Palier 1 ou sans fichier."""
        sorties: tuple[SortieNarration, ...] = self._sorties_llm("narrations", palier)
        return tuple(s for s in sorties if entite is None or s.entite == entite)

    # --- Traces ---

    def traces(self) -> tuple[EntreeTrace, ...]:
        """Lignes `EntreeTrace` de `trace/llm.jsonl` puis de `trace/previsions.jsonl`."""
        self._verifier_passage()
        entrees: list[EntreeTrace] = []
        for nom in ("trace_llm", "trace_previsions"):
            chemin = self._chemin(nom)
            if not chemin.exists():
                continue
            try:
                texte = _lire_octets(chemin).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise UsineErreur(f"{chemin} : fichier non encodé en UTF-8") from exc
            for numero, ligne in enumerate(texte.splitlines(), start=1):
                if not ligne.strip():
                    continue
                try:
                    entrees.append(EntreeTrace.model_validate_json(ligne))
                except ValidationError as exc:
                    raise UsineErreur(f"{chemin}, ligne {numero} : trace invalide ({exc})") from exc
        return tuple(entrees)

    # --- Liens ---

    def url_ticket(self, cle: str) -> str | None:
        """`<url_site>/browse/<cle>` ; `None` en Mode repli ou sans configuration Jira."""
        if self._url_jira is None:
            return None
        return f"{self._url_jira}/browse/{cle}"

    # --- Livrables ---

    def livrable(self, nom: Literal["rapport_xlsx", "rapport_pptx"]) -> bytes | None:
        """Contenu du Rapport `nom` du Passage lu, ou `None` s'il est absent."""
        chemin = self._repertoire / chemin_fichier_passage(nom, self.manifeste().date_arrete)
        if not chemin.exists():
            return None
        return _lire_octets(chemin)


def _age(date_derniere_entree: date | None, jour: date) -> int:
    """Jours ouvrés écoulés depuis la dernière Entrée (0 si inconnue ou le jour même)."""
    if date_derniere_entree is None or date_derniere_entree >= jour:
        return 0
    return len(jours_ouvres(date_derniere_entree, jour)) - 1
