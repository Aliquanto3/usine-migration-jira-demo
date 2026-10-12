"""Étapes déterministes de la Chaîne (Stories 0.5 et 5.1).

Les étapes déterministes enveloppent le domaine sans aucun recalcul : `EtapeInstantanes` et
`EtapeMeteo` couvrent chaque Jour ouvré de l'historique jusqu'à la Date d'arrêté ;
`EtapeKpi` (KPI quotidiens et Tendances) couvre chaque Jour ouvré du premier jour où un ticket
existe jusqu'à la Date d'arrêté, aucun avant ; `EtapePrevision` reçoit la prévision sous forme de
fonction injectée et trace chaque Prévision et chaque Risque (AD-16, FR-34) ;
`prevision_du_passage` est cette fonction pour un Passage (Baseline des Entités rouges, Risques
des autres, chaque Jour ouvré). Les étapes pas encore implémentées sont des bouchons, et les
étapes LLM sont sautées en Palier 1. Aucune
étape n'écrit : elle lit le Passage en cours par `ctx.consultation` et renvoie un
`ResultatEtape`, que l'`EcrivainPassage` écrit.
"""

import json
from collections import deque
from collections.abc import Callable, Sequence
from datetime import date, datetime

import polars as pl

from usine.contrats.calcul import SCHEMA_INDICATEUR
from usine.contrats.calendrier import TAILLE_FENETRE_GLISSANTE, jours_ouvres
from usine.contrats.config import ConfigProgramme, GrilleMeteo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import Couleur, MeteoEntite
from usine.contrats.passage import ContextePassage, ResultatEtape, StatutEtape
from usine.contrats.prevision import ContenuPrevisions, Prevision, RisqueEntreeRouge
from usine.contrats.trace import EntreeTrace, TypeTrace
from usine.domaine.instantanes import instantane, tickets_etats, tickets_textes
from usine.domaine.kpi import kpi, tendances
from usine.domaine.meteo import DECALAGE_IND8, indicateurs, meteo
from usine.domaine.prevision.baseline import ParametresBaseline, prevoir_sortie
from usine.domaine.prevision.risque import ParametresRisque, risques_entree_rouge
from usine.domaine.prevision.serie import series_stock
from usine.ports.consultation import Consultation
from usine.ports.source_tickets import SourceTickets

type Prevoir = Callable[[ContextePassage[Consultation]], ContenuPrevisions]
"""Fonction de prévision injectée dans `EtapePrevision` (lit le Passage, appelle le domaine)."""


def jours_du_passage(premier_jour: date, date_arrete: date) -> tuple[date, ...]:
    """Jours ouvrés de `premier_jour` à la Date d'arrêté ; refuse une date antérieure."""
    if date_arrete < premier_jour:
        raise UsineErreur(
            f"Date d'arrêté {date_arrete.isoformat()} antérieure au premier jour de"
            f" l'historique {premier_jour.isoformat()}"
        )
    return jours_ouvres(premier_jour, date_arrete)


class EtapeInstantanes:
    """États des tickets et Instantanés, pour chaque Jour ouvré de l'historique."""

    def __init__(self, source: SourceTickets, premier_jour: date) -> None:
        self._source = source
        self._premier_jour = premier_jour

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sorties `tickets_etats`, `instantanes` et `tickets_textes` (à la Date d'arrêté)."""
        dates = jours_du_passage(self._premier_jour, ctx.date_arrete)
        evenements = list(self._source.evenements())
        etats = tickets_etats(evenements, dates)
        return ResultatEtape(
            StatutEtape.reussie,
            {
                "tickets_etats": etats,
                "instantanes": instantane(etats),
                "tickets_textes": tickets_textes(evenements, ctx.date_arrete),
            },
        )


class EtapeMeteo:
    """Indicateurs et Météo par Entité, pour chaque Jour ouvré de l'historique.

    `premier_jour` est aussi l'ancrage des semaines du Programme (Phase en cours, IND-8).
    `decalage` est le décalage de comparaison de `ConfigChaine` (H-19), lu par la composition :
    il élargit seulement l'historique transmis au domaine, où IND-8 reste à `DECALAGE_IND8`.
    """

    def __init__(
        self,
        grille: GrilleMeteo,
        version_grille: str,
        entites: Sequence[str],
        premier_jour: date,
        programme: ConfigProgramme,
        decalage: int = DECALAGE_IND8,
    ) -> None:
        self._grille = grille
        self._version_grille = version_grille
        self._entites = tuple(entites)
        self._premier_jour = premier_jour
        self._programme = programme
        self._decalage = decalage

    @property
    def taille_historique(self) -> int:
        """Jours ouvrés d'état transmis au domaine : `max(décalage, IND-8, Fenêtre) + 1`."""
        return max(self._decalage, DECALAGE_IND8, TAILLE_FENETRE_GLISSANTE) + 1

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sorties `indicateurs` et `meteo`, lues depuis `tickets_etats` du Passage.

        Chaque jour reçoit l'état des tickets des `taille_historique` derniers Jours ouvrés,
        jour compris (Fenêtre glissante d'IND-7, comparaison d'IND-8 à J-5).
        """
        tables: list[pl.DataFrame] = []
        meteos: list[MeteoEntite] = []
        historique: deque[pl.DataFrame] = deque(maxlen=self.taille_historique)
        for jour in jours_du_passage(self._premier_jour, ctx.date_arrete):
            historique.append(ctx.consultation.tickets_etats(jour))
            etats = pl.concat(historique, how="vertical")
            tables.append(
                indicateurs(
                    etats,
                    jour,
                    self._entites,
                    self._grille,
                    programme=self._programme,
                    ancrage=self._premier_jour,
                )
            )
            meteos.extend(
                meteo(
                    etats,
                    jour,
                    self._entites,
                    self._grille,
                    self._version_grille,
                    programme=self._programme,
                    ancrage=self._premier_jour,
                )
            )
        table = (
            pl.concat(tables, how="vertical")
            if tables
            else pl.DataFrame(schema=dict(SCHEMA_INDICATEUR.colonnes))
        )
        return ResultatEtape(StatutEtape.reussie, {"indicateurs": table, "meteo": tuple(meteos)})


class EtapeKpi:
    """KPI quotidiens et Tendances, sur tout l'historique du Passage.

    `premier_jour` est aussi l'ancrage des semaines du Programme (`EnteteJournal.ancrage_semaines`).
    """

    def __init__(self, entites: Sequence[str], premier_jour: date) -> None:
        self._entites = tuple(entites)
        self._premier_jour = premier_jour

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sorties `kpi` et `tendances`, lues depuis `tickets_etats` du Passage.

        `kpi` reçoit l'état des tickets de chaque Jour ouvré de `premier_jour` à la Date
        d'arrêté ; ses lignes couvrent chaque Jour ouvré du premier jour où un ticket existe
        jusqu'à la Date d'arrêté, aucune avant. `tendances` reçoit ces KPI, la Date d'arrêté
        et l'ancrage. Sans aucun ticket, les deux tables sont vides.
        """
        jours = jours_du_passage(self._premier_jour, ctx.date_arrete)
        historique = pl.concat(
            [ctx.consultation.tickets_etats(jour) for jour in jours], how="vertical"
        )
        quotidiens = kpi(historique, self._entites)
        return ResultatEtape(
            StatutEtape.reussie,
            {
                "kpi": quotidiens,
                "tendances": tendances(quotidiens, ctx.date_arrete, self._premier_jour),
            },
        )


def prevision_du_passage(
    grille: GrilleMeteo,
    entites: Sequence[str],
    premier_jour: date,
    baseline: ParametresBaseline = ParametresBaseline(),  # noqa: B008 (dataclass gelée)
    risque: ParametresRisque = ParametresRisque(),  # noqa: B008 (dataclass gelée)
) -> Prevoir:
    """Prévision d'un Passage, à injecter dans `EtapePrevision` (FR-20, FR-21, AD-7).

    Pour chaque Jour ouvré de `premier_jour` à la Date d'arrêté, dans l'ordre, puis pour chaque
    Entité dans l'ordre de `meteo.json` : une Entité rouge reçoit la Prévision de la Baseline
    (`prevoir_sortie`) sur sa `SerieStock`, une autre ses Risques d'entrée en rouge
    (`risques_entree_rouge`) sur ses Indicateurs. `baseline` et `risque` (H-7, H-8) sont lus de
    `ConfigChaine.prevision` par la composition ; par défaut, ceux du domaine. La série vient de
    `series_stock` sur l'état des tickets du Passage : aucun calcul ici.
    """
    entites = tuple(entites)

    def prevoir(ctx: ContextePassage[Consultation]) -> ContenuPrevisions:
        consultation = ctx.consultation
        jours = jours_du_passage(premier_jour, ctx.date_arrete)
        etats = pl.concat([consultation.tickets_etats(jour) for jour in jours], how="vertical")
        series = series_stock(etats, entites, jours)
        tables = pl.concat([consultation.indicateurs(jour) for jour in jours], how="vertical")
        # Lignes de chaque Entité seulement : chaque appel du domaine valide sa table entière.
        serie_de: dict[str, pl.DataFrame] = {}
        indicateurs_de: dict[str, pl.DataFrame] = {}
        previsions: list[Prevision] = []
        risques: list[RisqueEntreeRouge] = []
        for jour in jours:
            for meteo_entite in consultation.meteo(jour):
                entite = meteo_entite.entite
                if meteo_entite.couleur is Couleur.rouge:
                    if entite not in serie_de:
                        serie_de[entite] = series.filter(pl.col("serie") == entite)
                    previsions.append(prevoir_sortie(serie_de[entite], meteo_entite, baseline))
                else:
                    if entite not in indicateurs_de:
                        indicateurs_de[entite] = tables.filter(pl.col("entite") == entite)
                    resultat = risques_entree_rouge(
                        indicateurs_de[entite], meteo_entite, grille, risque
                    )
                    risques.extend(projete.risque for projete in resultat.risques)
        return ContenuPrevisions(previsions=tuple(previsions), risques=tuple(risques))

    return prevoir


def _json(identite: dict[str, str]) -> str:
    return json.dumps(identite, ensure_ascii=False, separators=(",", ":"))


class EtapePrevision:
    """Prévisions de sortie du rouge et Risques d'entrée en rouge, avec leurs traces.

    La prévision elle-même est la fonction injectée `prevoir` (le domaine `prevision`) :
    l'étape ne connaît aucune Baseline. Chaque Prévision, puis chaque Risque, produit une
    `EntreeTrace` de type `prevision`, datée par `horloge`, avec `version_donnees`.
    """

    def __init__(
        self, prevoir: Prevoir, version_donnees: str, horloge: Callable[[], datetime]
    ) -> None:
        self._prevoir = prevoir
        self._version_donnees = version_donnees
        self._horloge = horloge

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sortie `previsions` et une trace par Prévision et par Risque, dans cet ordre."""
        contenu: object = self._prevoir(ctx)
        if not isinstance(contenu, ContenuPrevisions):
            raise UsineErreur(
                f"prévision de type {type(contenu).__name__}, attendu ContenuPrevisions"
            )
        traces = [
            self._trace(
                ctx,
                p.date_arrete,
                p.entite,
                p.version_grille,
                {"methode": p.methode.value},
                p.model_dump_json(),
            )
            for p in contenu.previsions
        ]
        traces += [
            self._trace(
                ctx,
                r.date_arrete,
                r.entite,
                r.version_grille,
                {"indicateur": r.indicateur.value},
                r.model_dump_json(),
            )
            for r in contenu.risques
        ]
        return ResultatEtape(StatutEtape.reussie, {"previsions": contenu}, tuple(traces))

    def _trace(
        self,
        ctx: ContextePassage[Consultation],
        date_arrete: date,
        entite: str,
        version_grille: str,
        identite: dict[str, str],
        sortie: str,
    ) -> EntreeTrace:
        entree = {"date_arrete": date_arrete.isoformat(), "entite": entite, **identite}
        return EntreeTrace(
            type_trace=TypeTrace.prevision,
            horodatage=self._horloge(),
            passage_id=ctx.passage_id,
            date_arrete=date_arrete,
            entite=entite,
            cible=entite,
            version_grille=version_grille,
            version_donnees=self._version_donnees,
            entree_pseudonymisee=_json(entree),
            sortie=sortie,
        )


class EtapeBouchon:
    """Étape pas encore implémentée : réussie, sans sortie."""

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Rend une étape réussie sans sortie."""
        return ResultatEtape(StatutEtape.reussie)


class EtapeSautee:
    """Étape sautée (étapes LLM en Palier 1)."""

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Rend une étape sautée."""
        return ResultatEtape(StatutEtape.sautee)
