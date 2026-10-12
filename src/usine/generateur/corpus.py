"""Format du Corpus de textes du générateur : lecture, écriture et production par LLM (FR-2).

Le Corpus range des paires (titre, description) fictives : Anomalies par Domaine et par
Cause racine, Cas de test par Domaine, Certifications, plus une section `generique` pour
tout Domaine de configuration absent du Corpus. Les textes sont des gabarits : `{entite}`
(et `{domaine}`, hors Certifications) sont remplacés à la génération du Journal.

`generateur` possède seul ce format (Story 1.2) : il l'écrit, le relit et le produit par
`FournisseurLLM.generer_structure` (AD-24), sans aucun SDK de fournisseur. La génération du
Journal ne fait que lire un Corpus déjà écrit : elle n'émet aucun appel LLM.
"""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from string import Formatter
from types import MappingProxyType
from typing import Annotated, Self

from pydantic import AfterValidator, Field, ValidationError, model_validator

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ParametresAppel, Tache
from usine.contrats.modele import Enregistrement, MappingFige
from usine.contrats.tickets import CauseRacine
from usine.ports.fournisseur_llm import FournisseurLLM

CHEMIN_CORPUS = Path("donnees") / "corpus" / "textes.json"
"""Corpus versionné, relatif à la racine du dépôt."""

MODELE_GABARITS = "gabarits-provisoires"
"""`modele_corpus` du Corpus provisoire, construit par gabarits sans LLM."""

VERSION_CORPUS_PROVISOIRE = "provisoire-1"
"""`version_corpus` par défaut du Corpus provisoire."""

VERSION_CORPUS_LLM = "llm-1"
"""`version_corpus` par défaut d'un Corpus produit par LLM."""

CHAMPS_GABARIT = frozenset({"entite", "domaine"})
"""Champs remplaçables dans un texte du Corpus."""

LIBELLES_CAUSES: Mapping[CauseRacine, str] = MappingProxyType(
    {
        CauseRacine.reprise_donnees: "reprise de données (données mal migrées de l'ancien SI)",
        CauseRacine.regle_transformation: "règle de transformation (calcul ou conversion faux)",
        CauseRacine.parametrage: "paramétrage (table ou option du nouveau SI mal réglée)",
        CauseRacine.interface_flux: "interface ou flux (échange entre applications en échec)",
        CauseRacine.environnement: "environnement (plateforme de test indisponible, instable)",
        CauseRacine.donnee_test: "donnée de test (jeu d'essai faux ou incomplet)",
        CauseRacine.hors_perimetre: "hors périmètre (demande ne relevant pas de la migration)",
    }
)
"""Libellé de chaque Cause racine, pour les consignes données au LLM."""

TEXTES_PAR_CASE = 6
"""Nombre de paires (titre, description) demandées au LLM par case du Corpus."""

MAX_JETONS_CASE = 2_000
"""Plafond de jetons de sortie d'un appel de production du Corpus."""

TEMPERATURE_CORPUS = 0.7
"""Température des appels de production : de la variété entre les textes."""


def _champs(texte: str) -> set[str]:
    """Champs `{...}` d'un gabarit ; lève `ValueError` sur une accolade mal formée."""
    champs: set[str] = set()
    for _, nom, format_spec, conversion in Formatter().parse(texte):
        if nom is None:
            continue
        if format_spec or conversion:
            raise ValueError(f"champ « {{{nom}}} » : ni conversion ni format admis")
        champs.add(nom)
    return champs


def _gabarit(texte: str) -> str:
    inconnus = _champs(texte) - CHAMPS_GABARIT
    if inconnus:
        raise ValueError(
            f"champ inconnu {sorted(inconnus)} (admis : {{entite}}, {{domaine}}) dans {texte!r}"
        )
    return texte


Gabarit = Annotated[str, Field(min_length=1), AfterValidator(_gabarit)]
"""Texte du Corpus : non vide, seuls `{entite}` et `{domaine}` y sont remplaçables."""


class TexteTicket(Enregistrement):
    """Paire (titre, description) d'un ticket, tirée d'un seul coup à la génération."""

    titre: Gabarit
    description: Gabarit

    def remplir(self, entite: str, domaine: str) -> tuple[str, str]:
        """Titre et description, `{entite}` et `{domaine}` remplacés."""
        return (
            self.titre.format(entite=entite, domaine=domaine),
            self.description.format(entite=entite, domaine=domaine),
        )


Textes = Annotated[tuple[TexteTicket, ...], Field(min_length=1)]
"""Case du Corpus : au moins une paire."""


class TextesDomaine(Enregistrement):
    """Textes d'un Domaine : Anomalies par Cause racine (les 7) et Cas de test."""

    anomalies: MappingFige[CauseRacine, Textes]
    cas_de_test: Textes

    @model_validator(mode="after")
    def _sept_causes(self) -> Self:
        manquantes = [c.value for c in CauseRacine if c not in self.anomalies]
        if manquantes:
            raise ValueError(f"Causes racines manquantes : {', '.join(manquantes)}")
        return self


class Corpus(Enregistrement):
    """Corpus de textes du générateur, versionné dans `donnees/corpus/textes.json`."""

    version_corpus: str = Field(min_length=1)
    modele_corpus: str = Field(min_length=1)
    """`gabarits-provisoires`, ou le `version_modele` du fournisseur qui l'a produit."""
    domaines: MappingFige[str, TextesDomaine]
    generique: TextesDomaine
    """Textes de tout Domaine absent de `domaines` ; `{domaine}` y nomme le Domaine."""
    certifications: Textes

    @model_validator(mode="after")
    def _certifications_sans_domaine(self) -> Self:
        for texte in self.certifications:
            if "domaine" in _champs(texte.titre) | _champs(texte.description):
                raise ValueError("une Certification n'a pas de Domaine : {domaine} interdit")
        if any(not nom.strip() for nom in self.domaines):
            raise ValueError("nom de Domaine vide")
        return self

    def textes_domaine(self, domaine: str) -> TextesDomaine:
        """Textes de `domaine`, ou la section générique s'il est absent du Corpus."""
        return self.domaines.get(domaine, self.generique)


class ReponseCorpus(Enregistrement):
    """Schéma demandé au fournisseur LLM pour une case du Corpus."""

    textes: Textes


def charger_corpus(chemin: Path) -> Corpus:
    """Lit et valide le Corpus de `chemin` ; toute erreur lève une `UsineErreur` qui le nomme."""
    try:
        contenu = chemin.read_bytes()
    except FileNotFoundError as exc:
        raise UsineErreur(f"{chemin} : Corpus de textes introuvable") from exc
    except OSError as exc:
        raise UsineErreur(f"{chemin} : Corpus illisible ({exc.strerror or exc})") from exc
    try:
        return Corpus.model_validate_json(contenu)
    except ValidationError as exc:
        lignes = [
            f"{chemin} : Corpus invalide, clé « {'.'.join(str(p) for p in err['loc']) or '.'} »"
            f" ({err['msg']})"
            for err in exc.errors()
        ]
        raise UsineErreur("\n".join(lignes)) from exc


def serialiser_corpus(corpus: Corpus) -> bytes:
    """Corpus en JSON indenté, UTF-8 sans échappement, fin de ligne `\\n`."""
    texte = json.dumps(corpus.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return (texte + "\n").encode("utf-8")


def ecrire_corpus(corpus: Corpus, chemin: Path) -> Path:
    """Écrit le Corpus à `chemin` (répertoires créés) et renvoie ce chemin."""
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(serialiser_corpus(corpus))
    except OSError as exc:
        raise UsineErreur(f"{chemin} : écriture impossible ({exc.strerror or exc})") from exc
    return chemin


# --- Production par LLM (AD-24) ---

_CONSIGNES = (
    "Tu rédiges des textes de tickets Jira pour un programme FICTIF de migration du SI cœur"
    " d'une banque fictive. Tous les textes sont 100 % fictifs : aucun nom réel de personne,"
    " d'entreprise, d'organisation, de produit ou de lieu, aucun identifiant réel."
    " Rédige en français, sur un ton factuel de recette informatique."
    " Écris le marqueur littéral {{entite}} là où doit figurer le code de l'Entité concernée."
    " N'emploie aucune autre accolade{autres}."
    " Rends exactement {nombre} paires (titre court, description d'une ou deux phrases),"
    " toutes différentes."
)


def _consignes(*, avec_domaine: bool) -> str:
    autres = (
        " que {domaine}, marqueur littéral du nom du Domaine fonctionnel" if avec_domaine else ""
    )
    return _CONSIGNES.format(autres=autres, nombre=TEXTES_PAR_CASE)


def _prompt_anomalie(domaine: str | None, cause: CauseRacine) -> str:
    perimetre = (
        f"du Domaine fonctionnel « {domaine} »"
        if domaine
        else "d'un Domaine fonctionnel quelconque, nommé par le marqueur {domaine}"
    )
    return (
        f"{_consignes(avec_domaine=domaine is None)}\n"
        f"Case : Anomalies {perimetre}, dont la cause est : {LIBELLES_CAUSES[cause]}."
        " Ne nomme jamais la cause explicitement : décris le symptôme observé."
    )


def _prompt_cas_de_test(domaine: str | None) -> str:
    perimetre = (
        f"du Domaine fonctionnel « {domaine} »"
        if domaine
        else "d'un Domaine fonctionnel quelconque, nommé par le marqueur {domaine}"
    )
    return (
        f"{_consignes(avec_domaine=domaine is None)}\n"
        f"Case : Cas de test de recette ou de non-régression {perimetre}."
    )


def _prompt_certifications() -> str:
    return (
        f"{_consignes(avec_domaine=False)}\n"
        "Case : Certifications, avis métier d'une Entité sur la qualité de sa migration avant"
        " bascule."
    )


def _demander(fournisseur: FournisseurLLM, prompt: str) -> tuple[TexteTicket, ...]:
    parametres = ParametresAppel(
        tache=Tache.narration,
        max_jetons_sortie=MAX_JETONS_CASE,
        temperature=TEMPERATURE_CORPUS,
    )
    reponse = fournisseur.generer_structure(prompt, ReponseCorpus, parametres)
    return reponse.sortie.textes


def _textes_domaine(fournisseur: FournisseurLLM, domaine: str | None) -> TextesDomaine:
    anomalies = {
        cause: _demander(fournisseur, _prompt_anomalie(domaine, cause)) for cause in CauseRacine
    }
    cas_de_test = _demander(fournisseur, _prompt_cas_de_test(domaine))
    return TextesDomaine(anomalies=anomalies, cas_de_test=cas_de_test)


def prompts_corpus(domaines: Sequence[str]) -> tuple[str, ...]:
    """Prompts de `produire_corpus`, dans l'ordre de ses appels (estimation du coût)."""
    prompts: list[str] = []
    for domaine in (*domaines, None):
        prompts.extend(_prompt_anomalie(domaine, cause) for cause in CauseRacine)
        prompts.append(_prompt_cas_de_test(domaine))
    prompts.append(_prompt_certifications())
    return tuple(prompts)


def produire_corpus(
    fournisseur: FournisseurLLM,
    domaines: Sequence[str],
    *,
    version_corpus: str = VERSION_CORPUS_LLM,
) -> Corpus:
    """Corpus produit par LLM, une case par appel `generer_structure` (tâche `narration`).

    Ordre des appels : pour chaque Domaine, ses 7 Causes racines puis ses Cas de test ; la
    section générique de même ; enfin les Certifications. `modele_corpus` est le
    `version_modele` du fournisseur. Un texte invalide lève une `UsineErreur`.
    """
    try:
        return Corpus(
            version_corpus=version_corpus,
            modele_corpus=fournisseur.version_modele,
            domaines={domaine: _textes_domaine(fournisseur, domaine) for domaine in domaines},
            generique=_textes_domaine(fournisseur, None),
            certifications=_demander(fournisseur, _prompt_certifications()),
        )
    except ValidationError as exc:
        raise UsineErreur(
            f"Corpus produit par {fournisseur.version_modele} invalide : {exc}"
        ) from exc
