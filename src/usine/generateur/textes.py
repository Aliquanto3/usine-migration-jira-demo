"""Mini-corpus fictif intégré du générateur E0 : titres et descriptions, sans nom réel.

Pas de LLM en E0 : le corpus est figé ici et identifié par `VERSION_CORPUS`.
"""

from collections.abc import Mapping
from types import MappingProxyType

from usine.contrats.tickets import TypeTicket

VERSION_CORPUS = "mini-e0"
"""Version du corpus, reportée dans l'`EnteteJournal`."""

MODELE_CORPUS = "aucun"
"""Modèle ayant produit le corpus : aucun, il est écrit à la main."""

TITRES: Mapping[TypeTicket, tuple[str, ...]] = MappingProxyType(
    {
        TypeTicket.anomalie: (
            "Écart de solde après reprise ({domaine})",
            "Code devise absent sur les écritures migrées ({domaine})",
            "Rejet de l'interface de chargement nocturne ({domaine})",
            "Libellé tronqué dans l'écran de consultation ({domaine})",
            "Règle d'arrondi différente de l'ancien système ({domaine})",
            "Référentiel tiers incomplet après bascule ({domaine})",
            "Environnement de recette indisponible ({domaine})",
            "Jeu d'essai incohérent pour le scénario ({domaine})",
        ),
        TypeTicket.cas_de_test: (
            "Contrôle des totaux après reprise ({domaine})",
            "Parcours de bout en bout ({domaine})",
            "Vérification des habilitations ({domaine})",
            "Rapprochement ancien et nouveau système ({domaine})",
        ),
        TypeTicket.certification: (
            "Certification de la reprise de l'Entité {entite}",
            "Validation métier de la bascule de l'Entité {entite}",
        ),
    }
)
"""Gabarits de titre par type ; `{domaine}` et `{entite}` sont remplacés à la génération."""

DESCRIPTIONS: Mapping[TypeTicket, tuple[str, ...]] = MappingProxyType(
    {
        TypeTicket.anomalie: (
            "Constaté lors du contrôle quotidien sur le périmètre {domaine} de l'Entité {entite}.",
            "Le résultat diffère de l'ancien système sur un échantillon de dossiers fictifs.",
            "Signalé par l'équipe de recette ; reproductible sur le jeu d'essai courant.",
            "L'anomalie bloque la suite du scénario tant qu'elle n'est pas corrigée.",
        ),
        TypeTicket.cas_de_test: (
            "Exécuter le scénario sur le périmètre {domaine} et comparer aux attendus.",
            "Vérifier les montants et les comptes sur un échantillon fictif de l'Entité {entite}.",
        ),
        TypeTicket.certification: (
            "Avis de l'équipe métier de l'Entité {entite} sur la qualité de la migration.",
            "Synthèse des contrôles réalisés avant la bascule de l'Entité {entite}.",
        ),
    }
)
"""Gabarits de description par type."""
