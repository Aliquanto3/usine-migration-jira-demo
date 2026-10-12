"""Pseudonymisation par Presidio et spaCy, moteur du Palier 2 (AD-15).

`PseudonymiseurPresidio` détecte avec un `AnalyzerEngine` Presidio : un `PatternRecognizer`
par type de jeton des reconnaisseurs maison de `config/pseudonymisation.yaml`, et un
`SpacyRecognizer` pour les entités de `entites_presidio` (modèle spaCy chargé par son nom).
Le reconnaisseur maison prime : d'une entité spaCy qui chevauche une de ses plages, seules
les parties hors de ces plages restent.
La dérivation des jetons, la protection des clés de ticket et la table sont celles de
`PseudonymiseurDerive` : une même valeur détectée par un reconnaisseur maison donne le même
jeton que `PseudonymiseurHmac`.

Aucun modèle n'est téléchargé : un modèle spaCy absent lève une `UsineErreur`. Le moteur
spaCy chargé est gardé en cache par processus (langue, modèle), car son chargement est lent.
"""

from collections.abc import Iterable
from functools import cache

import spacy
from presidio_analyzer import (
    AnalyzerEngine,
    Pattern,
    PatternRecognizer,
    RecognizerRegistry,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import NlpEngine, SpacyNlpEngine
from presidio_analyzer.predefined_recognizers import SpacyRecognizer

from usine.adaptateurs.pseudonymisation import (
    PseudonymiseurDerive,
    TablePseudonymes,
    fragments_hors_cles,
    verifier_types_jeton,
)
from usine.contrats.config import ConfigPseudonymisation
from usine.contrats.erreurs import UsineErreur

PREFIXE_MAISON = "maison:"
"""Préfixe du nom des reconnaisseurs maison, pour les distinguer des entités spaCy."""


@cache
def _moteur_nlp(langue: str, modele: str) -> NlpEngine:
    """Moteur spaCy chargé, partagé par processus ; refuse un modèle absent sans télécharger."""
    if not spacy.util.is_package(modele):
        raise UsineErreur(
            f"Pseudonymisation : modèle spaCy « {modele} » absent ; l'installer avec les"
            " dépendances (`uv sync --locked`), aucun téléchargement n'est tenté"
        )
    moteur = SpacyNlpEngine(models=[{"lang_code": langue, "model_name": modele}])
    moteur.load()
    return moteur


class PseudonymiseurPresidio(PseudonymiseurDerive):
    """Pseudonymiseur Presidio + spaCy ; correspondance gardée dans `table`."""

    def __init__(self, cle: bytes, config: ConfigPseudonymisation, table: TablePseudonymes) -> None:
        super().__init__(cle, table)
        types_maison = {r.type_jeton for r in config.reconnaisseurs}
        verifier_types_jeton(types_maison | set(config.entites_presidio))
        communs = sorted(types_maison & set(config.entites_presidio))
        if communs:
            raise UsineErreur(
                f"Pseudonymisation : type {communs} à la fois reconnaisseur maison et entité"
                " Presidio ; le dédoublonnage de Presidio absorberait le reconnaisseur maison"
            )
        moteur_nlp = _moteur_nlp(config.langue, config.modele_spacy)
        inconnues = sorted(set(config.entites_presidio) - set(moteur_nlp.get_supported_entities()))
        if inconnues:
            raise UsineErreur(
                f"Pseudonymisation : entité Presidio {inconnues} jamais produite par le modèle"
                f" spaCy « {config.modele_spacy} » ; elle ne serait jamais détectée"
            )
        self._langue = config.langue
        registre = RecognizerRegistry(supported_languages=[config.langue])
        par_type: dict[str, list[Pattern]] = {}
        for rang, reconnaisseur in enumerate(config.reconnaisseurs):
            par_type.setdefault(reconnaisseur.type_jeton, []).append(
                Pattern(
                    f"{reconnaisseur.type_jeton}-{rang}", reconnaisseur.motif, reconnaisseur.score
                )
            )
        for type_jeton, motifs in par_type.items():
            registre.add_recognizer(
                PatternRecognizer(
                    supported_entity=type_jeton,
                    name=f"{PREFIXE_MAISON}{type_jeton}",
                    supported_language=config.langue,
                    patterns=motifs,
                    global_regex_flags=0,
                )
            )
        if config.entites_presidio:
            registre.add_recognizer(
                SpacyRecognizer(
                    supported_language=config.langue,
                    supported_entities=list(config.entites_presidio),
                )
            )
        self._entites = sorted(par_type) + [e for e in config.entites_presidio if e not in par_type]
        if not self._entites:
            raise UsineErreur("Pseudonymisation : ni reconnaisseur maison ni entité Presidio")
        self._analyseur = AnalyzerEngine(
            registry=registre,
            nlp_engine=moteur_nlp,
            supported_languages=[config.langue],
        )

    def _detecter(self, texte: str) -> Iterable[tuple[int, int, str]]:
        """Plages des reconnaisseurs maison, puis parties des entités spaCy hors de ces plages."""
        if not texte:
            return []
        resultats = self._analyseur.analyze(texte, language=self._langue, entities=self._entites)
        maison: list[tuple[int, int, str]] = []
        modele: list[tuple[int, int, str]] = []
        for resultat in resultats:
            nom = (resultat.recognition_metadata or {}).get(
                RecognizerResult.RECOGNIZER_NAME_KEY, ""
            )
            plage = (resultat.start, resultat.end, resultat.entity_type)
            (maison if str(nom).startswith(PREFIXE_MAISON) else modele).append(plage)
        plages_maison = [(d, f) for d, f, _ in maison]
        return maison + [
            (d, f, type_jeton)
            for debut, fin, type_jeton in modele
            for d, f in fragments_hors_cles(texte, debut, fin, plages_maison)
        ]
