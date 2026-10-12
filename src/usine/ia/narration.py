"""Tâche `narration` : une phrase qui raconte la Prévision d'une Entité (FR-24, AD-14).

Le prompt `prompts/narration.md` reçoit les seules valeurs de la Prévision de sortie du rouge
et des Risques d'entrée en rouge de l'Entité à la Date d'arrêté, formatées par
`contrats.format` et placées entre délimiteurs. Le même collecteur produit ces valeurs et la
liste des valeurs autorisées par `controler_nombres` : une narration qui contient un nombre ou
une date absents, ou un texte vide, est rejetée sans régénération. La sortie publiée porte
alors la Prévision brute (texte déterministe formé des mêmes valeurs) et
`statut_controle = rejete`. Plafond de coût du Passage atteint : Prévision brute (`rejete`),
sans faire échouer le Passage. `version_prompt` est calculée à partir des octets du gabarit
envoyé.
"""

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from fractions import Fraction
from importlib import resources

from usine.contrats.format import (
    formater_date,
    formater_entier,
    formater_fraction,
    formater_pourcentage,
)
from usine.contrats.llm import (
    ParametresAppel,
    ReponseNarration,
    SortieNarration,
    StatutControle,
    Tache,
)
from usine.contrats.prevision import (
    MethodePrevision,
    Prevision,
    RisqueEntreeRouge,
    StatutPrevision,
)
from usine.contrats.trace import EntreeTrace
from usine.ia.controles import ValeurAutorisee, controler_nombres
from usine.ia.explication import ContexteExplication, _donnee, rendre_prompt
from usine.ia.passerelle import ContexteAppel, Controle, Passerelle, PlafondCoutAtteint

MAX_JETONS_SORTIE = 256
"""Plafond de jetons de sortie d'une narration (une phrase)."""

journal = logging.getLogger(__name__)


def lire_prompt() -> bytes:
    """Octets de `ia/prompts/narration.md` (source de `version_prompt`)."""
    return (resources.files("usine.ia") / "prompts" / "narration.md").read_bytes()


class ContexteNarration(ContexteExplication):
    """Contexte du Passage commun aux narrations (identifiant, données, gabarit envoyé)."""


@dataclass
class _Collecteur:
    """Valeurs de la Prévision : lignes du prompt et valeurs autorisées, produites ensemble."""

    lignes: list[str] = field(default_factory=list)
    morceaux: list[str] = field(default_factory=list)
    autorisees: list[ValeurAutorisee] = field(default_factory=list)

    def section(self, titre: str) -> None:
        self.lignes.append(f"### {_donnee(titre)}")
        self.morceaux.append(f"{titre} :")

    def ajouter(self, libelle: str, texte: str, *valeurs: ValeurAutorisee) -> None:
        self.lignes.append(f"- {_donnee(libelle)} : {_donnee(texte)}")
        self.morceaux.append(f"{libelle} {texte} ;")
        self.autorisees.extend(valeurs)
        # Les libellés déterministes portent parfois un nombre (« les 10 derniers Jours
        # ouvrés ») : il figure dans le prompt, il est donc autorisé.
        self.autorisees.extend(int(chiffres) for chiffres in re.findall(r"\d+", libelle))

    def date(self, libelle: str, valeur: date | None) -> None:
        if valeur is not None:
            self.ajouter(libelle, formater_date(valeur), valeur)

    def entier(self, libelle: str, valeur: int) -> None:
        self.ajouter(libelle, formater_entier(valeur), valeur)

    def ratio(self, libelle: str, numerateur: int, denominateur: int) -> None:
        """`n` si `d = 1`, sinon `n/d` ; autorisés : la fraction, `n` et `d`."""
        if denominateur == 1:
            self.entier(libelle, numerateur)
            return
        fraction = Fraction(numerateur, denominateur)
        texte = (
            f"{formater_entier(numerateur)}/{formater_entier(denominateur)}"
            f" (soit {formater_fraction(fraction, 2)})"
        )
        self.ajouter(libelle, texte, fraction, numerateur, denominateur)


LIBELLES_STATUT = {
    StatutPrevision.sortie_projetee: "sortie du rouge projetée",
    StatutPrevision.pas_de_sortie_projetee: "pas de sortie du rouge projetée dans l'horizon",
    StatutPrevision.regle_non_projetable: "sortie non projetable",
}
"""Libellés français des statuts de Prévision (prompt et Prévision brute)."""

LIBELLES_METHODE = {MethodePrevision.baseline: "Baseline", MethodePrevision.ml: "Modèle ML"}
"""Libellés français des méthodes de Prévision."""


def _collecter(
    entite: str,
    date_arrete: date,
    prevision: Prevision | None,
    risques: Iterable[RisqueEntreeRouge],
) -> _Collecteur:
    collecteur = _Collecteur()
    collecteur.section(f"Entité {entite}")
    collecteur.date("Date d'arrêté", date_arrete)
    if prevision is not None:
        collecteur.section("Prévision de sortie du rouge")
        collecteur.ajouter("statut", LIBELLES_STATUT[prevision.statut])
        collecteur.ajouter("méthode", LIBELLES_METHODE[prevision.methode])
        collecteur.date("date de sortie estimée", prevision.date_sortie_estimee)
        collecteur.date("date de sortie optimiste", prevision.date_sortie_optimiste)
        collecteur.date("date de sortie pessimiste", prevision.date_sortie_pessimiste)
        probabilite = Fraction(prevision.probabilite_numerateur, prevision.probabilite_denominateur)
        collecteur.ajouter(
            "probabilité de sortie dans l'horizon",
            formater_pourcentage(probabilite),
            probabilite,
            prevision.probabilite_numerateur,
            prevision.probabilite_denominateur,
        )
        collecteur.entier("horizon en jours ouvrés", prevision.horizon_jours_ouvres)
        for facteur in prevision.facteurs:
            collecteur.ratio(facteur.libelle, facteur.numerateur, facteur.denominateur)
        if prevision.regles_non_projetables:
            codes = ", ".join(code.value for code in prevision.regles_non_projetables)
            collecteur.ajouter("règles non projetables", codes)
    for risque in risques:
        collecteur.section(f"Risque d'entrée en rouge sur {risque.indicateur.value}")
        collecteur.date("date de franchissement estimée", risque.date_franchissement_estimee)
        collecteur.entier("horizon en jours ouvrés", risque.horizon_jours_ouvres)
        collecteur.ratio("valeur courante", risque.numerateur, risque.denominateur)
        collecteur.ratio("seuil rouge", risque.seuil_numerateur, risque.seuil_denominateur)
        if (
            risque.valeur_projetee_numerateur is not None
            and risque.valeur_projetee_denominateur is not None
        ):
            collecteur.ratio(
                "valeur projetée au franchissement",
                risque.valeur_projetee_numerateur,
                risque.valeur_projetee_denominateur,
            )
    return collecteur


def prevision_brute(
    entite: str,
    date_arrete: date,
    prevision: Prevision | None,
    risques: Iterable[RisqueEntreeRouge] = (),
) -> str:
    """Prévision brute : texte déterministe formé des valeurs envoyées au LLM."""
    morceaux = " ".join(_collecter(entite, date_arrete, prevision, risques).morceaux)
    return f"Prévision brute. {morceaux.removesuffix(' ;')}."


@dataclass
class _Controleur:
    """Contrôle d'une `ReponseNarration` : nombres et dates, Prévision brute en cas de rejet."""

    entite: str
    date_arrete: date
    autorisees: tuple[ValeurAutorisee, ...]
    brute: str
    refuses: tuple[str, ...] = ()

    def __call__(self, reponse: ReponseNarration) -> Controle[SortieNarration]:
        texte = reponse.texte.strip()
        controle = controler_nombres(texte, self.autorisees)
        self.refuses = controle.refuses if texte else ("texte vide",)
        if not texte or not controle.conforme:
            return Controle(self.sortie(self.brute, StatutControle.rejete), StatutControle.rejete)
        return Controle(self.sortie(texte, StatutControle.conforme), StatutControle.conforme)

    def sortie(self, texte: str, statut: StatutControle) -> SortieNarration:
        return SortieNarration(
            date_arrete=self.date_arrete, entite=self.entite, texte=texte, statut_controle=statut
        )


def narrer(
    passerelle: Passerelle,
    entite: str,
    date_arrete: date,
    version_grille: str,
    prevision: Prevision | None,
    risques: tuple[RisqueEntreeRouge, ...],
    contexte: ContexteNarration,
) -> tuple[SortieNarration, tuple[EntreeTrace, ...]]:
    """Narration de la Prévision de `entite` et trace de l'appel (zéro ou une)."""
    collecteur = _collecter(entite, date_arrete, prevision, risques)
    brute = prevision_brute(entite, date_arrete, prevision, risques)
    prompt = rendre_prompt(
        contexte.texte_gabarit,
        {"entite": entite, "valeurs": "\n".join(collecteur.lignes)},
        Tache.narration,
    )
    appel = ContexteAppel(
        passage_id=contexte.passage_id,
        date_arrete=date_arrete,
        cible=entite,
        version_prompt=contexte.version_prompt,
        version_grille=version_grille,
        version_donnees=contexte.version_donnees,
        entite=entite,
    )
    controleur = _Controleur(entite, date_arrete, tuple(collecteur.autorisees), brute)
    parametres = ParametresAppel(tache=Tache.narration, max_jetons_sortie=MAX_JETONS_SORTIE)
    try:
        resultat = passerelle.executer_structure(
            prompt, ReponseNarration, parametres, appel, controleur
        )
    except PlafondCoutAtteint:
        journal.warning("narration de %s non demandée : plafond de coût", entite)
        return controleur.sortie(brute, StatutControle.rejete), ()
    if resultat.statut is StatutControle.rejete:
        journal.warning(
            "narration de %s rejetée (%s) : Prévision brute publiée",
            entite,
            ", ".join(controleur.refuses),
        )
    return resultat.sortie, (resultat.trace,)
