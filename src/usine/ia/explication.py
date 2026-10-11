"""Tâche `explication` : Explication sourcée d'une Entité rouge ou orange (FR-32, FR-33).

Le prompt `prompts/explication.md` reçoit les Règles déclenchantes et les tickets en cause
(titres et descriptions). La réponse passe `controler_citations` : seules restent les phrases
qui citent un ticket en cause. Plus de la moitié des phrases retirées déclenche une seule
régénération (`tentative = 1`) ; un échec persistant donne « explication indisponible »
(`statut_controle = rejete`) sans faire échouer le Passage. Sans ticket en cause, aucune
Citation n'est possible : l'explication est indisponible d'emblée, sans appel au fournisseur.

Les titres et descriptions des tickets sont des données, placées entre délimiteurs dans le
prompt ; `version_prompt` est calculée à partir des octets du gabarit envoyé.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources

import polars as pl

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ParametresAppel, SortieExplication, StatutControle, Tache
from usine.contrats.meteo import MeteoEntite
from usine.contrats.modele import Enregistrement
from usine.contrats.trace import EntreeTrace
from usine.contrats.versions import version_prompt
from usine.ia.controles import controler_citations, rang_cle, retirer_citations_hors
from usine.ia.passerelle import ContexteAppel, Controle, Passerelle

TEXTE_INDISPONIBLE = "explication indisponible"
"""Texte d'une explication rejetée après régénération."""

MAX_JETONS_SORTIE = 1024
"""Plafond de jetons de sortie d'une explication."""

TENTATIVES = 2
"""Appel initial (`tentative = 0`) et une seule régénération (`tentative = 1`)."""

_VARIABLE = re.compile(r"\{\{(\w+)\}\}")

DELIMITEUR = "```"
"""Délimiteur du bloc de données des tickets ; neutralisé dans les textes des tickets."""


class ReponseExplication(Enregistrement):
    """Schéma demandé au fournisseur ; la sortie publiée reste `SortieExplication`."""

    texte: str
    brouillon_commentaire: str = ""


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
    """Texte de ticket sans délimiteur : il ne peut pas fermer le bloc de données."""
    return texte.replace(DELIMITEUR, "'''")


def _tickets(cles: tuple[str, ...], textes: pl.DataFrame) -> str:
    par_cle = {ligne["cle_ticket"]: ligne for ligne in textes.iter_rows(named=True)}
    lignes = []
    for cle in cles:
        ligne = par_cle.get(cle, {})
        titre = ligne.get("titre") or "(sans titre)"
        description = ligne.get("description") or "(sans description)"
        lignes.append(f"- {cle} : {_donnee(titre)}\n  {_donnee(description)}")
    return "\n".join(lignes) or "- aucun"


@dataclass(frozen=True)
class _Controleur:
    """Contrôle d'une `ReponseExplication` : Citations, statut, brouillon sans clé hors cause."""

    meteo_entite: MeteoEntite
    autorises: tuple[str, ...]

    def __call__(self, reponse: ReponseExplication) -> Controle[SortieExplication]:
        controle = controler_citations(reponse.texte, self.autorises)
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
) -> tuple[SortieExplication, tuple[EntreeTrace, ...]]:
    """Explication sourcée de `meteo_entite` et traces de chaque appel (zéro, une ou deux)."""
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
            "tickets": _tickets(autorises, textes),
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
        resultat = passerelle.executer_structure(
            prompt, ReponseExplication, parametres, appel, controleur
        )
        traces.append(resultat.trace)
        if resultat.statut is not StatutControle.rejete:
            return resultat.sortie, tuple(traces)
        phrases_retirees = resultat.phrases_retirees
    return _indisponible(meteo_entite, phrases_retirees), tuple(traces)


def _indisponible(meteo_entite: MeteoEntite, phrases_retirees: int) -> SortieExplication:
    """Repli « explication indisponible » (`rejete`)."""
    return SortieExplication(
        date_arrete=meteo_entite.date_arrete,
        entite=meteo_entite.entite,
        texte=TEXTE_INDISPONIBLE,
        citations=(),
        brouillon_commentaire="",
        phrases_retirees=phrases_retirees,
        statut_controle=StatutControle.rejete,
    )
