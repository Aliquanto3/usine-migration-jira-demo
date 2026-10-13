"""Vérification du déroulé de la démo (Story 7.12) : chaque écran du script a ses données.

Contrôle automatique, sans réseau ni LLM, sur le Passage enregistré du Mode repli
(`demo/repli/passage/`), séquence par séquence de `demo/script-demo.md` : Avant / après, carte
météo (A et B rouges, C orange), détail des Entités, Prévisions et Risque, Explication sourcée
(Palier 2) ou message attendu (Palier 1), Pseudonymisation, réponses enregistrées de l'Agent
(`demo/repli/agent/*.json`, même `passage_id` que la copie) et fiche outillage. Chaque
séquence est chronométrée. Il ne remplace pas une répétition : il dit seulement si un écran
risque d'arriver vide.

La lecture passe par le port `Consultation`, construit par `composition.consultation_repertoire`
comme `ui/cli.consultation_repli` (même lecteur, sans URL Jira) : `outils` n'a pas le droit
d'importer `usine.ui` ni `usine.ia` (contrat import-linter « hors produit »). Le test de
l'outil vérifie que ses constantes et son chargement des réponses de l'Agent concordent avec
ceux de l'UI.

L'aperçu de la Pseudonymisation lit `USINE_CLE_PSEUDO` (environnement ou `.env` de la racine),
comme l'UI ; rien n'est affiché du texte ni de la clé.

Usage : `uv run python outils/verifier_demo.py [--racine .]`. Code de sortie : 0 déroulé
complet, 1 au moins une séquence en échec.
"""

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import ValidationError

from usine.composition import apercu_pseudonymisation, consultation_repertoire
from usine.contrats.config import ConfigDemo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.format import formater_date
from usine.contrats.llm import ReponseAgentEnregistree, StatutControle
from usine.contrats.meteo import Couleur
from usine.contrats.passage import FICHIERS_PASSAGE, ManifestePassage
from usine.contrats.prevision import StatutPrevision
from usine.ports.consultation import Consultation

REPERTOIRE_REPLI = Path("demo/repli/passage")
"""Copie du Mode repli, relative à la racine (même valeur que `ui/cli.REPERTOIRE_REPLI`)."""
REPERTOIRE_REPONSES = Path("demo/repli/agent")
"""Réponses enregistrées de l'Agent (même valeur que `ia/agent/repli.REPERTOIRE_REPONSES`)."""
FICHIER_CONFIG_DEMO = Path("config/demo.yaml")
"""Temps manuel déclaré de l'Avant / après (même valeur que `ui/avant_apres.FICHIER_CONFIG`)."""
FICHIER_FICHE = Path("docs/fiche-outillage.md")
"""Fiche de l'écran outillage (même valeur que `ui/outillage.FICHIER_FICHE`)."""

COULEURS_ATTENDUES = {"ENT-A": Couleur.rouge, "ENT-B": Couleur.rouge, "ENT-C": Couleur.orange}
"""Scénarios A, B (rouges) et C (orange) racontés par le script."""

MESSAGE_PALIER_1 = "commentaire non généré (Palier 1)"
"""Texte du bloc Explication d'un Passage Palier 1 (même valeur que
`ui/detail.EXPLICATION_PALIER_1`)."""

MAX_DESCRIPTIONS = 200
"""Descriptions essayées au plus pour trouver une pseudonymisation visible."""

STATUTS_REJOUABLES = (StatutControle.conforme, StatutControle.corrige)


class Echec(Exception):
    """Séquence dont les données ne permettent pas de jouer l'écran."""


@dataclass(frozen=True)
class Resultat:
    """Bilan d'une séquence du script."""

    sequence: str
    ok: bool
    detail: str
    duree_s: float


Apercu = Callable[[str], str]


def _date(jour: date | None) -> str:
    return "?" if jour is None else formater_date(jour)


def _passage(racine: Path) -> tuple[Consultation, ManifestePassage]:
    repertoire = racine / REPERTOIRE_REPLI
    if not (repertoire / FICHIERS_PASSAGE["manifeste"]).is_file():
        raise Echec(f"copie du Mode repli absente : {repertoire} (pas de manifeste)")
    consultation = consultation_repertoire(repertoire)
    return consultation, consultation.manifeste()


def charger_reponses(racine: Path, passage_id: str) -> tuple[ReponseAgentEnregistree, ...]:
    """Réponses de `demo/repli/agent/*.json` dans l'ordre des fichiers, refusées comme l'UI."""
    repertoire = racine / REPERTOIRE_REPONSES
    chemins = sorted(repertoire.glob("*.json")) if repertoire.is_dir() else []
    if not chemins:
        raise Echec(f"aucune réponse enregistrée dans {repertoire}")
    reponses = []
    for chemin in chemins:
        try:
            enregistree = ReponseAgentEnregistree.model_validate_json(chemin.read_bytes())
        except (OSError, ValidationError) as exc:
            raise Echec(f"{chemin.name} illisible ({exc})") from exc
        if enregistree.passage_id != passage_id:
            raise Echec(
                f"{chemin.name} porte le Passage {enregistree.passage_id}, la copie est"
                f" {passage_id} : l'UI refusera les réponses"
            )
        reponses.append(enregistree)
    return tuple(reponses)


def _avant_apres(racine: Path, manifeste: ManifestePassage) -> str:
    chemin = racine / FICHIER_CONFIG_DEMO
    if not chemin.is_file():
        raise Echec(f"{chemin} absent : temps manuel non affiché")
    config = ConfigDemo.model_validate(yaml.safe_load(chemin.read_text(encoding="utf-8")))
    if manifeste.classification_initiale:
        raise Echec("Passage avec classification initiale : temps non représentatif")
    duree = (manifeste.horodatage_fin - manifeste.horodatage_debut).total_seconds()
    return (
        f"manuel {config.temps_manuel_minutes_par_rapport} min contre {duree:.1f} s mesurées"
        " (Passage de repli)"
    )


def _carte(consultation: Consultation) -> str:
    couleurs = {meteo.entite: meteo.couleur for meteo in consultation.meteo()}
    ecarts = [
        f"{entite} {couleurs.get(entite, 'absente')} (attendu {attendue})"
        for entite, attendue in COULEURS_ATTENDUES.items()
        if couleurs.get(entite) is not attendue
    ]
    if ecarts:
        raise Echec("Météo inattendue : " + ", ".join(ecarts))
    if not consultation.evolution_meteo():
        raise Echec("aucune évolution J-1 / J-5 : flèches de tendance absentes")
    rouges = sorted(e for e, c in couleurs.items() if c is Couleur.rouge)
    return f"{len(couleurs)} Entités ; rouges : {', '.join(rouges)} ; ENT-C orange"


def _detail(consultation: Consultation) -> str:
    morceaux = []
    for entite in COULEURS_ATTENDUES:
        (meteo,) = consultation.meteo(entite=entite)
        if not meteo.regles:
            raise Echec(f"{entite} sans Règle déclenchante")
        if consultation.kpi(entite=entite).is_empty():
            raise Echec(f"{entite} sans KPI")
        morceaux.append(f"{entite} : {meteo.regles[0].code}")
    return "Règle principale " + ", ".join(morceaux)


def _prevision(consultation: Consultation, manifeste: ManifestePassage) -> str:
    statuts = {}
    for entite in ("ENT-A", "ENT-B"):
        previsions = consultation.previsions(entite=entite)
        if not previsions:
            raise Echec(f"aucune Prévision pour {entite}")
        statuts[entite] = previsions[0]
    a, b = statuts["ENT-A"], statuts["ENT-B"]
    if a.statut is not StatutPrevision.sortie_projetee:
        raise Echec(f"ENT-A : {a.statut} (le script annonce une sortie projetée)")
    if b.statut is StatutPrevision.sortie_projetee:
        raise Echec("ENT-B : sortie projetée (le script annonce l'inverse)")
    if not consultation.risques(entite="ENT-C"):
        raise Echec("aucun Risque d'entrée en rouge pour ENT-C")
    texte = (
        f"ENT-A sortie estimée le {_date(a.date_sortie_estimee)} ({a.probabilite_numerateur}/"
        f"{a.probabilite_denominateur}) ; ENT-B {b.statut} ; Risque ENT-C présent"
    )
    if manifeste.palier == 2:
        if not consultation.narrations(entite="ENT-A", palier=2):
            raise Echec("Passage Palier 2 sans narration pour ENT-A")
        return texte + " ; narration ENT-A présente"
    return texte + " ; pas de narration (Palier 1)"


def _explication(consultation: Consultation, manifeste: ManifestePassage) -> str:
    if manifeste.palier == 2:
        manquantes = [e for e in ("ENT-A", "ENT-B") if not consultation.explications(entite=e)]
        if manquantes:
            raise Echec("Passage Palier 2 sans Explication pour " + ", ".join(manquantes))
        if consultation.explications(entite="ENT-A", palier=1):
            raise Echec("filtre Palier 1 inopérant : Explication lue en Palier 1")
        return "Explications A et B présentes ; sélecteur Palier 1 / 2 proposé"
    if consultation.explications(entite="ENT-A", palier=1):
        raise Echec("Passage Palier 1 avec une Explication")
    return f"Palier 1 : bloc Explication « {MESSAGE_PALIER_1} », pas de sélecteur de Palier"


def _pseudonymisation(consultation: Consultation, apercu: Apercu) -> str:
    table = consultation.textes_tickets()
    textes = [
        texte
        for texte in table.get_column("description").to_list()
        if texte is not None and texte.strip()
    ]
    if not textes:
        raise Echec("aucune description de ticket : rien à comparer")
    for rang, texte in enumerate(textes[:MAX_DESCRIPTIONS], start=1):
        if apercu(texte) != texte:
            return f"{len(textes)} descriptions ; la n° {rang} change à la pseudonymisation"
    raise Echec(f"aucune des {MAX_DESCRIPTIONS} premières descriptions ne change")


def _agent(racine: Path, manifeste: ManifestePassage) -> str:
    reponses = charger_reponses(racine, manifeste.passage_id)
    fautives = [
        r.reponse.question for r in reponses if r.reponse.statut_controle not in STATUTS_REJOUABLES
    ]
    if fautives:
        raise Echec("réponse non conforme : " + " | ".join(fautives))
    return f"{len(reponses)} réponses conformes sur {manifeste.passage_id}"


def _outillage(racine: Path) -> str:
    chemin = racine / FICHIER_FICHE
    if not chemin.is_file() or not chemin.read_text(encoding="utf-8-sig").strip():
        raise Echec(f"{chemin} absente ou vide")
    return f"{FICHIER_FICHE.as_posix()} présente"


def _chronometrer(sequence: str, controle: Callable[[], str]) -> Resultat:
    debut = time.perf_counter()
    try:
        detail, ok = controle(), True
    except (Echec, UsineErreur, OSError, ValidationError, ValueError) as exc:
        detail, ok = str(exc), False
    return Resultat(sequence, ok, detail, time.perf_counter() - debut)


def verifier(racine: Path, apercu: Apercu | None = None) -> list[Resultat]:
    """Contrôles de toutes les séquences, dans l'ordre du script ; `apercu` remplaçable."""
    etat: dict[str, tuple[Consultation, ManifestePassage]] = {}

    def charger() -> str:
        etat["passage"] = _passage(racine)
        m = etat["passage"][1]
        return (
            f"Passage {m.passage_id}, arrêté au {formater_date(m.date_arrete)}, Palier {m.palier},"
            f" {m.nb_tickets} tickets"
        )

    resultats = [_chronometrer("0. Chargement du Passage de repli", charger)]
    if "passage" not in etat:
        return resultats
    consultation, manifeste = etat["passage"]

    def pseudonymiser() -> str:
        return _pseudonymisation(consultation, apercu or apercu_pseudonymisation(racine))

    controles: list[tuple[str, Callable[[], str]]] = [
        ("1. Avant / après", lambda: _avant_apres(racine, manifeste)),
        ("2. Carte météo", lambda: _carte(consultation)),
        ("3. Détail A, B, C", lambda: _detail(consultation)),
        ("4. Prévision et narration", lambda: _prevision(consultation, manifeste)),
        ("5. Explication sourcée", lambda: _explication(consultation, manifeste)),
        ("6. Pseudonymisation", pseudonymiser),
        ("7. Agent (réponses enregistrées)", lambda: _agent(racine, manifeste)),
        ("8. Ce qu'il faut pour le faire en vrai", lambda: _outillage(racine)),
    ]
    resultats.extend(_chronometrer(nom, controle) for nom, controle in controles)
    return resultats


def compte_rendu(resultats: Sequence[Resultat]) -> str:
    """Compte rendu lisible : une ligne par séquence, puis le bilan et la durée totale."""
    lignes = ["Vérification du déroulé de la démo (Mode repli, sans réseau)"]
    for r in resultats:
        lignes.append(
            f"  [{'OK' if r.ok else 'KO'}] {r.sequence} ({r.duree_s * 1000:.0f} ms) : {r.detail}"
        )
    echecs = sum(not r.ok for r in resultats)
    total = sum(r.duree_s for r in resultats)
    bilan = "déroulé complet" if echecs == 0 else f"{echecs} séquence(s) en échec"
    lignes.append(f"Bilan : {bilan} ; lectures en {total * 1000:.0f} ms au total.")
    return "\n".join(lignes)


def main(arguments: Sequence[str] | None = None) -> int:
    """Point d'entrée en ligne de commande ; renvoie 0 (complet) ou 1 (échec)."""
    reconfigurer = getattr(sys.stdout, "reconfigure", None)
    if reconfigurer is not None:  # console Windows : libellés accentués
        reconfigurer(encoding="utf-8", errors="replace")
    analyseur = argparse.ArgumentParser(prog="verifier_demo", description=__doc__.splitlines()[0])
    analyseur.add_argument("--racine", type=Path, default=Path("."))
    args = analyseur.parse_args(arguments)
    resultats = verifier(args.racine)
    print(compte_rendu(resultats))
    return 0 if all(r.ok for r in resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
