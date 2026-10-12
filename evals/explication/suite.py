"""Exécution et notation de la suite d'évaluation de l'Explication sourcée (SM-3).

`executer_suite` passe chaque cas par la vraie tâche `expliquer`, passerelle comprise (façade
`usine.composition.construire_explicateur`), puis applique `controler_citations` à chaque
sortie avec les tickets en cause du cas. Le taux de Citations valides est le cumul, sur les
cas, des phrases retenues divisé par le cumul des phrases : une « explication indisponible »
ne cite aucun ticket et compte donc comme une phrase invalide.

Par défaut, le fournisseur est `FournisseurEnregistre` (réponses enregistrées du cas, sans
réseau) et le pseudonymiseur `PseudonymiseurIdentite` (aucun secret). `reel=True` lit
`config/llm.yaml`, la clé du fournisseur et `USINE_CLE_PSEUDO`, comme un Passage Palier 2.

`noter` lit un résultat dont chaque cas porte ses notes humaines entières de 1 à 5
(`exactitude`, `utilite`) et ajoute à l'historique la moyenne, les versions, le taux et le
verdict SM-3 (taux de 100 % et moyenne ≥ 4).
"""

import json
from collections import deque
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from evals.explication.cas import NOMBRE_CAS, CasExplication
from usine.composition import Explicateur, construire_explicateur, controler_citations
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    MessageAgent,
    OutilAgent,
    ParametresAppel,
    ReponseAgentBrute,
    ReponseExplication,
    ReponseStructuree,
)

VERSION_MODELE_ENREGISTRE = "enregistre:rejeu"
"""`version_modele` annoncée par `FournisseurEnregistre`."""

CRITERES = ("exactitude", "utilite")
"""Critères de la note humaine, chacun noté de 1 à 5."""

NOTE_MIN, NOTE_MAX = 1, 5
MOYENNE_SM3 = 4.0
"""Moyenne humaine minimale de SM-3."""

REPERTOIRE_RESULTATS = Path(__file__).parent / "resultats"
CHEMIN_HISTORIQUE = Path(__file__).parent / "historique.jsonl"


def _jetons(texte: str) -> int:
    return len(texte.split())


class FournisseurEnregistre:
    """Fournisseur LLM sans réseau : rejoue les réponses enregistrées d'un cas, dans l'ordre."""

    def __init__(self, identifiant: str, reponses: Iterable[ReponseExplication]) -> None:
        self._identifiant = identifiant
        self._reponses: deque[ReponseExplication] = deque(reponses)

    @property
    def version_modele(self) -> str:
        """Version de modèle annoncée (`enregistre:rejeu`)."""
        return VERSION_MODELE_ENREGISTRE

    def generer_structure[T: BaseModel](
        self, prompt: str, schema: type[T], parametres: ParametresAppel
    ) -> ReponseStructuree[T]:
        """Prochaine réponse enregistrée, validée par `schema` ; épuisée : `UsineErreur`."""
        if not self._reponses:
            raise UsineErreur(
                f"cas « {self._identifiant} » : réponses enregistrées épuisées"
                f" (appel de tentative {parametres.tentative})"
            )
        brut = self._reponses.popleft().model_dump_json()
        return ReponseStructuree[T](
            sortie=schema.model_validate_json(brut),
            brut=brut,
            jetons_entree=_jetons(prompt),
            jetons_sortie=_jetons(brut),
            version_modele=VERSION_MODELE_ENREGISTRE,
        )

    def executer_agent(
        self,
        messages: Sequence[MessageAgent],
        outils: Sequence[OutilAgent],
        parametres: ParametresAppel,
    ) -> ReponseAgentBrute:
        """Sans objet pour l'explication."""
        raise UsineErreur(f"cas « {self._identifiant} » : aucun tour d'Agent enregistré")


class PseudonymiseurIdentite:
    """Pseudonymiseur sans secret : les cas ne contiennent aucune donnée personnelle."""

    def pseudonymiser(self, texte: str) -> str:
        """`texte` inchangé."""
        return texte

    def reidentifier(self, texte: str) -> str:
        """`texte` inchangé."""
        return texte

    def apercu(self, texte: str) -> str:
        """`texte` inchangé."""
        return texte


def _expliquer(explicateur: Explicateur, cas: CasExplication) -> dict[str, Any]:
    sortie, traces = explicateur(
        cas.meteo,
        cas.table_textes(),
        kpi=cas.table_kpi(),
        repartition=cas.table_repartition(),
    )
    controle = controler_citations(sortie.texte, cas.tickets_en_cause)
    return {
        "identifiant": cas.identifiant,
        "description": cas.description,
        "entite": cas.meteo.entite,
        "couleur": cas.meteo.couleur.value,
        "tickets_en_cause": list(cas.tickets_en_cause),
        "texte": sortie.texte,
        "citations": list(sortie.citations),
        "brouillon_commentaire": sortie.brouillon_commentaire,
        "statut_controle": sortie.statut_controle.value,
        "tentatives": len(traces),
        "phrases_retirees": sum(trace.phrases_retirees for trace in traces),
        "phrases_total": controle.phrases_total,
        "phrases_valides": controle.phrases_total - controle.phrases_retirees,
        "notes": dict.fromkeys(CRITERES),
    }


def executer_suite(
    cas: Sequence[CasExplication],
    racine: Path,
    *,
    reel: bool = False,
    horloge: datetime | None = None,
) -> dict[str, Any]:
    """Résultat JSON de la suite : sorties par cas, taux de Citations valides, versions.

    Rejeu (défaut) : un `FournisseurEnregistre` par cas, sans réseau ni secret. `reel=True` :
    un seul explicateur construit depuis la configuration de `racine` (réseau, coût).
    """
    instant = horloge or datetime.now(UTC)
    sorties: list[dict[str, Any]] = []
    versions_prompt: set[str] = set()
    versions_modele: set[str] = set()
    if reel:
        explicateur = construire_explicateur(racine)
        try:
            for un_cas in cas:
                sorties.append(_expliquer(explicateur, un_cas))
        finally:
            explicateur.fermer()
        versions_prompt.add(explicateur.version_prompt)
        versions_modele.add(explicateur.version_modele)
    else:
        for un_cas in cas:
            explicateur = construire_explicateur(
                racine,
                fournisseur=FournisseurEnregistre(un_cas.identifiant, un_cas.reponses),
                pseudonymiseur=PseudonymiseurIdentite(),
            )
            sorties.append(_expliquer(explicateur, un_cas))
            versions_prompt.add(explicateur.version_prompt)
            versions_modele.add(explicateur.version_modele)
    total = sum(sortie["phrases_total"] for sortie in sorties)
    valides = sum(sortie["phrases_valides"] for sortie in sorties)
    return {
        "horodatage": instant.isoformat(),
        "mode": "reel" if reel else "rejeu",
        "version_prompt": ", ".join(sorted(versions_prompt)),
        "version_modele": ", ".join(sorted(versions_modele)),
        "nombre_cas": len(sorties),
        "phrases_total": total,
        "phrases_valides": valides,
        "taux_citations_valides": valides / total if total else 0.0,
        "phrases_retirees_passerelle": sum(sortie["phrases_retirees"] for sortie in sorties),
        "moyenne_humaine": None,
        "cas": sorties,
    }


def nom_resultat(instant: datetime) -> str:
    """Nom de fichier d'un résultat : `<AAAAMMJJTHHMMSSZ>.json`."""
    return instant.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ") + ".json"


def ecrire_resultat(resultat: dict[str, Any], repertoire: Path) -> Path:
    """Écrit `resultat` sous `repertoire/<horodatage>.json` et renvoie le chemin."""
    repertoire.mkdir(parents=True, exist_ok=True)
    chemin = repertoire / nom_resultat(datetime.fromisoformat(resultat["horodatage"]))
    chemin.write_text(
        json.dumps(resultat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return chemin


def _note(valeur: object, identifiant: str, critere: str, chemin: Path) -> int:
    if (
        isinstance(valeur, bool)
        or not isinstance(valeur, int)
        or not NOTE_MIN <= valeur <= NOTE_MAX
    ):
        raise UsineErreur(
            f"{chemin}, cas « {identifiant} », note « {critere} » : {valeur!r} ;"
            f" note entière de {NOTE_MIN} à {NOTE_MAX} attendue"
        )
    return valeur


def _lire_resultat(chemin: Path) -> dict[str, Any]:
    try:
        resultat = json.loads(chemin.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UsineErreur(f"{chemin} : résultat illisible ({exc.strerror or exc})") from exc
    except json.JSONDecodeError as exc:
        raise UsineErreur(f"{chemin} : JSON mal formé ({exc.msg}, ligne {exc.lineno})") from exc
    if (
        not isinstance(resultat, dict)
        or not isinstance(resultat.get("cas"), list)
        or not resultat["cas"]
        or not isinstance(resultat.get("taux_citations_valides"), int | float)
    ):
        raise UsineErreur(f"{chemin} : résultat sans cas ni taux de Citations valides")
    return resultat


def noter(
    chemin_resultat: Path,
    chemin_historique: Path = CHEMIN_HISTORIQUE,
    *,
    horloge: datetime | None = None,
) -> dict[str, Any]:
    """Ajoute à `chemin_historique` la moyenne humaine du résultat noté et la renvoie.

    Toute note manquante ou hors de 1..5 lève une `UsineErreur` nommant le cas ; rien n'est
    alors écrit.
    """
    resultat = _lire_resultat(chemin_resultat)
    if len(resultat["cas"]) != NOMBRE_CAS:
        raise UsineErreur(
            f"{chemin_resultat} : {len(resultat['cas'])} cas, {NOMBRE_CAS} attendus (SM-3)"
        )
    identifiants = [str(un_cas.get("identifiant")) for un_cas in resultat["cas"]]
    doublons = sorted({i for i in identifiants if identifiants.count(i) > 1})
    if doublons:
        raise UsineErreur(f"{chemin_resultat} : identifiant(s) de cas en double {doublons}")
    notes: dict[str, list[int]] = {critere: [] for critere in CRITERES}
    for rang, un_cas in enumerate(resultat["cas"], start=1):
        identifiant = str(un_cas.get("identifiant", f"n° {rang}"))
        par_critere = un_cas.get("notes")
        if not isinstance(par_critere, dict):
            raise UsineErreur(f"{chemin_resultat}, cas « {identifiant} » : notes absentes")
        for critere in CRITERES:
            notes[critere].append(
                _note(par_critere.get(critere), identifiant, critere, chemin_resultat)
            )
    toutes = [note for valeurs in notes.values() for note in valeurs]
    moyenne = sum(toutes) / len(toutes)
    taux = float(resultat["taux_citations_valides"])
    entree = {
        "horodatage_notation": (horloge or datetime.now(UTC)).isoformat(),
        "resultat": chemin_resultat.name,
        "horodatage_execution": resultat.get("horodatage"),
        "mode": resultat.get("mode"),
        "version_prompt": resultat.get("version_prompt"),
        "version_modele": resultat.get("version_modele"),
        "nombre_cas": len(resultat["cas"]),
        "taux_citations_valides": taux,
        "moyenne_humaine": round(moyenne, 4),
        "moyennes_par_critere": {
            critere: round(sum(valeurs) / len(valeurs), 4) for critere, valeurs in notes.items()
        },
        "sm3_atteint": taux == 1.0 and moyenne >= MOYENNE_SM3,
    }
    chemin_historique.parent.mkdir(parents=True, exist_ok=True)
    with chemin_historique.open("a", encoding="utf-8", newline="\n") as fichier:
        fichier.write(json.dumps(entree, ensure_ascii=False) + "\n")
    return entree
