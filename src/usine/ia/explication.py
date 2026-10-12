"""Tâche `explication` : Explication sourcée d'une Entité rouge ou orange (FR-32, FR-33).

Le prompt `prompts/explication.md` reçoit les Règles déclenchantes, les KPI non ventilés de
l'Entité à la Date d'arrêté, les tickets en cause (titres et descriptions) et la répartition
des Causes racines proposées (« non disponible » sans répartition). La réponse passe
`controler_citations` : seules restent les phrases qui citent un ticket en cause, et chaque
retrait est journalisé (warning). Plus de la moitié des phrases retirées déclenche une seule
régénération (`tentative = 1`) ; un échec persistant donne « explication indisponible »
(`statut_controle = rejete`) sans faire échouer le Passage. Sans ticket en cause, aucune
Citation n'est possible : l'explication est indisponible d'emblée, sans appel au fournisseur.
Plafond de coût du Passage atteint (`PlafondCoutAtteint`) : l'explication porte
`TEXTE_PLAFOND` (`rejete`), sans faire échouer le Passage.

Les titres et descriptions des tickets, les KPI et les Causes racines sont des données,
placées entre délimiteurs dans le prompt ; `version_prompt` est calculée à partir des octets
du gabarit envoyé.
"""

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import resources

import polars as pl

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    ParametresAppel,
    ReponseExplication,
    SortieExplication,
    StatutControle,
    Tache,
)
from usine.contrats.meteo import MeteoEntite
from usine.contrats.tickets import rang_cle
from usine.contrats.trace import EntreeTrace
from usine.contrats.versions import version_prompt
from usine.ia.controles import controler_citations, retirer_citations_hors
from usine.ia.passerelle import ContexteAppel, Controle, Passerelle, PlafondCoutAtteint

TEXTE_INDISPONIBLE = "explication indisponible"
"""Texte d'une explication rejetée après régénération."""

TEXTE_PLAFOND = "explication indisponible : plafond de coût du Passage atteint"
"""Texte d'une explication non demandée, le plafond de coût du Passage étant atteint."""

MAX_JETONS_SORTIE = 1024
"""Plafond de jetons de sortie d'une explication."""

TENTATIVES = 2
"""Appel initial (`tentative = 0`) et une seule régénération (`tentative = 1`)."""

journal = logging.getLogger(__name__)

_VARIABLE = re.compile(r"\{\{(\w+)\}\}")

DELIMITEUR = "```"
"""Délimiteur du bloc de données des tickets ; neutralisé dans les textes des tickets."""


def lire_prompt() -> bytes:
    """Octets de `ia/prompts/explication.md` (source de `version_prompt`)."""
    return (resources.files("usine.ia") / "prompts" / "explication.md").read_bytes()


def rendre_prompt(gabarit: str, variables: Mapping[str, str]) -> str:
    """Remplace chaque `{{nom}}` ; une variable inconnue ou inutilisée lève une `UsineErreur`."""
    attendues = set(_VARIABLE.findall(gabarit))
    manquantes = sorted(attendues - set(variables))
    en_trop = sorted(set(variables) - attendues)
    if manquantes or en_trop:
        raise UsineErreur(
            f"prompt « explication » : variables manquantes {manquantes}, en trop {en_trop}"
        )
    return _VARIABLE.sub(lambda m: variables[m.group(1)], gabarit)


@dataclass(frozen=True)
class ContexteExplication:
    """Contexte du Passage commun aux explications."""

    passage_id: str
    version_donnees: str
    gabarit: bytes
    """Octets du gabarit envoyé (source de `version_prompt`)."""

    @property
    def version_prompt(self) -> str:
        """`version_prompt` du gabarit envoyé."""
        return version_prompt(self.gabarit)

    @property
    def texte_gabarit(self) -> str:
        """Gabarit décodé en UTF-8."""
        return self.gabarit.decode("utf-8")


def tickets_en_cause(meteo_entite: MeteoEntite) -> tuple[str, ...]:
    """Clés en cause de toutes les Règles déclenchantes, sans doublon, triées."""
    cles = {cle for regle in meteo_entite.regles for cle in regle.tickets_en_cause}
    return tuple(sorted(cles, key=rang_cle))


def _regles(meteo_entite: MeteoEntite) -> str:
    lignes = []
    for regle in meteo_entite.regles:
        valeur = f"{regle.numerateur}/{regle.denominateur}"
        seuil = f"{regle.operateur.value} {regle.seuil_numerateur}/{regle.seuil_denominateur}"
        lignes.append(
            f"- {regle.code.value} ({regle.couleur.value}) : valeur {valeur}, seuil {seuil} ;"
            f" tickets en cause : {', '.join(regle.tickets_en_cause) or 'aucun'}"
        )
    return "\n".join(lignes) or "- aucune"


def _donnee(texte: str) -> str:
    """Texte de donnée sans délimiteur : il ne peut pas fermer le bloc de données."""
    return texte.replace(DELIMITEUR, "'''")


def _kpi(table: pl.DataFrame | None) -> str:
    """Une ligne `code : valeur` par KPI non ventilé : `n`, `n/d`, ou `sans objet` pour 0/0."""
    if table is None or table.is_empty():
        return "- aucun"
    lignes = []
    for ligne in table.filter(pl.col("dimension") == "").sort("code_kpi").iter_rows(named=True):
        numerateur, denominateur = ligne["numerateur"], ligne["denominateur"]
        if denominateur == 0:
            valeur = "sans objet"
        elif denominateur == 1:
            valeur = f"{numerateur}"
        else:
            valeur = f"{numerateur}/{denominateur}"
        lignes.append(f"- {_donnee(str(ligne['code_kpi']))} : {valeur}")
    return "\n".join(lignes) or "- aucun"


def _causes(table: pl.DataFrame | None) -> str:
    """`- cause : nombre (pp %)`, nombre décroissant puis cause ; « non disponible » sinon.

    La répartition est lue telle quelle (AD-9 : aucun recalcul) ; sans colonne `part`
    (Passage antérieur aux contrats 1.5), la ligne est `- cause : nombre`.
    """
    if table is None or table.is_empty():
        return "- non disponible"
    avec_part = "part" in table.columns
    lignes = sorted(
        (
            (
                str(ligne["cause_racine"]),
                int(ligne["nombre"]),
                float(ligne["part"]) if avec_part else None,
            )
            for ligne in table.iter_rows(named=True)
        ),
        key=lambda ligne: (-ligne[1], ligne[0]),
    )
    return "\n".join(
        f"- {_donnee(cause)} : {nombre}" + ("" if part is None else f" ({part * 100:.0f} %)")
        for cause, nombre, part in lignes
    )


def _tickets(cles: tuple[str, ...], textes: pl.DataFrame) -> str:
    par_cle = {ligne["cle_ticket"]: ligne for ligne in textes.iter_rows(named=True)}
    lignes = []
    for cle in cles:
        if cle not in par_cle:
            journal.warning("ticket en cause %s absent des textes des tickets", cle)
        ligne = par_cle.get(cle, {})
        titre = ligne.get("titre") or "(sans titre)"
        description = ligne.get("description") or "(sans description)"
        lignes.append(f"- {cle} : {_donnee(titre)}\n  {_donnee(description)}")
    return "\n".join(lignes) or "- aucun"


@dataclass
class _Controleur:
    """Contrôle d'une `ReponseExplication` : Citations, statut, brouillon sans clé hors cause.

    `totaux` garde le nombre de phrases de chaque réponse contrôlée (journal des retraits).
    """

    meteo_entite: MeteoEntite
    autorises: tuple[str, ...]
    totaux: list[int] = field(default_factory=list)

    def __call__(self, reponse: ReponseExplication) -> Controle[SortieExplication]:
        controle = controler_citations(reponse.texte, self.autorises)
        self.totaux.append(controle.phrases_total)
        if controle.phrases_total == 0 or 2 * controle.phrases_retirees > controle.phrases_total:
            statut = StatutControle.rejete
        elif controle.phrases_retirees:
            statut = StatutControle.corrige
        else:
            statut = StatutControle.conforme
        sortie = SortieExplication(
            date_arrete=self.meteo_entite.date_arrete,
            entite=self.meteo_entite.entite,
            texte=controle.texte,
            citations=controle.citations,
            brouillon_commentaire=retirer_citations_hors(
                reponse.brouillon_commentaire, self.autorises
            ),
            phrases_retirees=controle.phrases_retirees,
            statut_controle=statut,
        )
        return Controle(sortie, statut, controle.phrases_retirees)


def expliquer(
    passerelle: Passerelle,
    meteo_entite: MeteoEntite,
    textes: pl.DataFrame,
    contexte: ContexteExplication,
    *,
    kpi: pl.DataFrame | None = None,
    repartition: pl.DataFrame | None = None,
) -> tuple[SortieExplication, tuple[EntreeTrace, ...]]:
    """Explication sourcée de `meteo_entite` et traces de chaque appel (zéro, une ou deux).

    `kpi` (table `SCHEMA_KPI` de l'Entité à la Date d'arrêté) et `repartition` (table
    `SCHEMA_REPARTITION_CAUSES` de l'Entité) sont facultatifs : sans eux, les sections du
    prompt portent « aucun » et « non disponible ».
    """
    autorises = tickets_en_cause(meteo_entite)
    if not autorises:
        return _indisponible(meteo_entite, 0), ()
    prompt = rendre_prompt(
        contexte.texte_gabarit,
        {
            "entite": meteo_entite.entite,
            "couleur": meteo_entite.couleur.value,
            "date_arrete": meteo_entite.date_arrete.isoformat(),
            "regles": _regles(meteo_entite),
            "kpi": _kpi(kpi),
            "tickets": _tickets(autorises, textes),
            "causes": _causes(repartition),
        },
    )
    appel = ContexteAppel(
        passage_id=contexte.passage_id,
        date_arrete=meteo_entite.date_arrete,
        cible=meteo_entite.entite,
        version_prompt=contexte.version_prompt,
        version_grille=meteo_entite.version_grille,
        version_donnees=contexte.version_donnees,
        entite=meteo_entite.entite,
    )
    controleur = _Controleur(meteo_entite, autorises)
    traces: list[EntreeTrace] = []
    phrases_retirees = 0
    for tentative in range(TENTATIVES):
        parametres = ParametresAppel(
            tache=Tache.explication, max_jetons_sortie=MAX_JETONS_SORTIE, tentative=tentative
        )
        try:
            resultat = passerelle.executer_structure(
                prompt, ReponseExplication, parametres, appel, controleur
            )
        except PlafondCoutAtteint:
            journal.warning("explication de %s non demandée : plafond de coût", appel.cible)
            return _indisponible(meteo_entite, phrases_retirees, TEXTE_PLAFOND), tuple(traces)
        traces.append(resultat.trace)
        if resultat.phrases_retirees:
            journal.warning(
                "explication de %s (tentative %d) : %d phrase(s) retirée(s) sur %d",
                appel.cible,
                tentative,
                resultat.phrases_retirees,
                controleur.totaux[-1],
            )
        if resultat.statut is not StatutControle.rejete:
            return resultat.sortie, tuple(traces)
        phrases_retirees = resultat.phrases_retirees
    return _indisponible(meteo_entite, phrases_retirees), tuple(traces)


def _indisponible(
    meteo_entite: MeteoEntite, phrases_retirees: int, texte: str = TEXTE_INDISPONIBLE
) -> SortieExplication:
    """Repli « explication indisponible » (`rejete`)."""
    return SortieExplication(
        date_arrete=meteo_entite.date_arrete,
        entite=meteo_entite.entite,
        texte=texte,
        citations=(),
        brouillon_commentaire="",
        phrases_retirees=phrases_retirees,
        statut_controle=StatutControle.rejete,
    )
