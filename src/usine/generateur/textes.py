"""Corpus provisoire, construit par gabarits sans LLM (Story 1.2).

Chaque gabarit de Cause racine est rempli avec le vocabulaire d'un Domaine livré (objets
métier, flux, écran) ; la section `generique`, où tirent les Domaines sans vocabulaire, prend
le vocabulaire générique, où `{domaine}` nomme le Domaine. `{entite}` reste un marqueur, remplacé
à la génération du Journal. La construction est pure et déterministe : mêmes Domaines, même
Corpus, octet pour octet. Tout est fictif : aucun nom réel de personne ou d'organisation.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from usine.contrats.tickets import CauseRacine
from usine.generateur.corpus import (
    MODELE_GABARITS,
    VERSION_CORPUS_PROVISOIRE,
    Corpus,
    TextesDomaine,
    TexteTicket,
)


@dataclass(frozen=True)
class Vocabulaire:
    """Mots d'un Domaine qui remplissent les gabarits."""

    libelle: str
    objets: tuple[str, ...]
    """Objets métier, avec leur article (« les comptes courants »), pris tour à tour."""
    flux: str
    ecran: str


VOCABULAIRES: Mapping[str, Vocabulaire] = MappingProxyType(
    {
        "credits": Vocabulaire(
            "crédits",
            (
                "les échéanciers de prêt",
                "les dossiers de crédit immobilier",
                "les garanties des prêts",
                "les taux des prêts à la consommation",
            ),
            "le flux d'octroi de crédit",
            "l'écran de suivi des prêts",
        ),
        "depots": Vocabulaire(
            "dépôts",
            (
                "les comptes courants",
                "les autorisations de découvert",
                "les relevés de compte",
                "les agios trimestriels",
            ),
            "le flux des opérations de guichet",
            "l'écran de consultation des comptes",
        ),
        "paiements": Vocabulaire(
            "paiements",
            (
                "les virements permanents",
                "les prélèvements",
                "les opérations par carte",
                "les mandats de prélèvement",
            ),
            "le flux de compensation",
            "l'écran de saisie des virements",
        ),
        "referentiel_clients": Vocabulaire(
            "référentiel clients",
            (
                "les fiches clients",
                "les adresses postales",
                "les liens entre titulaires",
                "les segments de clientèle",
            ),
            "le flux de synchronisation des tiers",
            "l'écran de fiche client",
        ),
        "comptabilite": Vocabulaire(
            "comptabilité",
            (
                "les écritures comptables",
                "le plan de comptes",
                "les balances générales",
                "les comptes de suspens",
            ),
            "le flux d'alimentation du grand livre",
            "l'écran de consultation des écritures",
        ),
        "epargne": Vocabulaire(
            "épargne",
            (
                "les livrets d'épargne",
                "les intérêts courus",
                "les plans d'épargne",
                "les plafonds de versement",
            ),
            "le flux de capitalisation des intérêts",
            "l'écran de synthèse de l'épargne",
        ),
    }
)
"""Vocabulaire des Domaines livrés dans `config/programme.yaml`."""

VOCABULAIRE_GENERIQUE = Vocabulaire(
    "domaine {domaine}",
    (
        "les données du domaine {domaine}",
        "les dossiers du domaine {domaine}",
        "les écritures du domaine {domaine}",
        "les référentiels du domaine {domaine}",
    ),
    "le flux du domaine {domaine}",
    "l'écran de consultation du domaine {domaine}",
)
"""Vocabulaire de tout autre Domaine : `{domaine}` est remplacé à la génération."""

Gabarits = tuple[tuple[str, str], ...]
"""Paires (titre, description) ; champs : `{objet}`, `{flux}`, `{ecran}`, `{libelle}`,
`{entite}` (laissé tel quel)."""

GABARITS_ANOMALIES: Mapping[CauseRacine, Gabarits] = MappingProxyType(
    {
        CauseRacine.reprise_donnees: (
            (
                "Écart de volumétrie après reprise sur {objet}",
                "Le nombre d'enregistrements chargés pour l'Entité {entite} diffère de"
                " l'extraction de l'ancien système ({libelle}).",
            ),
            (
                "Valeurs tronquées après chargement sur {objet}",
                "Des zones de texte de l'Entité {entite} sont coupées après chargement"
                " ({libelle}).",
            ),
            (
                "Doublons créés lors du chargement sur {objet}",
                "Une partie des enregistrements de l'Entité {entite} a été chargée deux fois"
                " ({libelle}).",
            ),
            (
                "Historique incomplet sur {objet}",
                "Les mouvements antérieurs à la bascule manquent pour l'Entité {entite}"
                " ({libelle}).",
            ),
            (
                "Anciens codes non convertis sur {objet}",
                "Des codes de l'ancien système subsistent dans les données de l'Entité"
                " {entite} ({libelle}).",
            ),
            (
                "Soldes d'ouverture différents de l'ancien système sur {objet}",
                "Le rapprochement des soldes chargés de l'Entité {entite} fait apparaître un"
                " écart ({libelle}).",
            ),
        ),
        CauseRacine.regle_transformation: (
            (
                "Arrondi différent de l'ancien système sur {objet}",
                "Les montants recalculés pour l'Entité {entite} diffèrent d'un centime sur un"
                " échantillon fictif ({libelle}).",
            ),
            (
                "Conversion de devise erronée sur {objet}",
                "Le taux appliqué à la conversion ne correspond pas à la règle attendue pour"
                " l'Entité {entite} ({libelle}).",
            ),
            (
                "Date de valeur décalée d'un jour sur {objet}",
                "La règle de calcul des dates produit un décalage pour l'Entité {entite}"
                " ({libelle}).",
            ),
            (
                "Statut mal déduit après transformation sur {objet}",
                "La correspondance des statuts entre ancien et nouveau système est fausse pour"
                " l'Entité {entite} ({libelle}).",
            ),
            (
                "Cumul recalculé incorrect sur {objet}",
                "Le total obtenu après transformation ne correspond pas à la somme des détails"
                " pour l'Entité {entite} ({libelle}).",
            ),
            (
                "Signe inversé sur {objet}",
                "Des débits apparaissent en crédits après transformation pour l'Entité {entite}"
                " ({libelle}).",
            ),
        ),
        CauseRacine.parametrage: (
            (
                "Plafond mal paramétré sur {objet}",
                "Le plafond appliqué à l'Entité {entite} ne correspond pas à la fiche de"
                " paramétrage ({libelle}).",
            ),
            (
                "Table de codes incomplète pour {objet}",
                "Un code attendu par l'Entité {entite} est absent de la table de paramètres"
                " ({libelle}).",
            ),
            (
                "Option désactivée dans {ecran}",
                "Une option utilisée par l'Entité {entite} n'est pas activée dans le nouveau"
                " système ({libelle}).",
            ),
            (
                "Calendrier de traitement mal réglé pour {objet}",
                "Le traitement de l'Entité {entite} se déclenche au mauvais jour ({libelle}).",
            ),
            (
                "Habilitations mal attribuées sur {ecran}",
                "Des profils de l'Entité {entite} n'accèdent pas aux fonctions prévues"
                " ({libelle}).",
            ),
            (
                "Libellé de paramétrage erroné sur {objet}",
                "Le libellé affiché à l'Entité {entite} ne correspond pas au référentiel"
                " ({libelle}).",
            ),
        ),
        CauseRacine.interface_flux: (
            (
                "Rejet constaté sur {flux}",
                "Le fichier de la nuit est rejeté pour l'Entité {entite} : format non reconnu"
                " ({libelle}).",
            ),
            (
                "Retard constaté sur {flux}",
                "Les données de l'Entité {entite} arrivent après l'heure de clôture ({libelle}).",
            ),
            (
                "Messages perdus dans {flux}",
                "Une partie des messages émis pour l'Entité {entite} n'est pas reçue par"
                " l'application cible ({libelle}).",
            ),
            (
                "Doublon de messages dans {flux}",
                "Des messages de l'Entité {entite} sont rejoués deux fois ({libelle}).",
            ),
            (
                "Accusé de réception absent pour {flux}",
                "L'application émettrice de l'Entité {entite} n'obtient pas de confirmation"
                " ({libelle}).",
            ),
            (
                "Encodage des caractères altéré dans {flux}",
                "Les accents des données de l'Entité {entite} sont remplacés par des"
                " caractères illisibles ({libelle}).",
            ),
        ),
        CauseRacine.environnement: (
            (
                "Environnement de recette indisponible pour {objet}",
                "L'Entité {entite} ne peut pas exécuter ses tests : la plateforme ne répond"
                " plus ({libelle}).",
            ),
            (
                "Temps de réponse dégradé sur {ecran}",
                "Les écrans de l'Entité {entite} mettent plus d'une minute à s'afficher"
                " ({libelle}).",
            ),
            (
                "Espace disque saturé lors du traitement portant sur {objet}",
                "Le traitement de l'Entité {entite} s'arrête faute de place sur le serveur"
                " ({libelle}).",
            ),
            (
                "Certificat expiré sur {flux}",
                "La connexion sécurisée de l'Entité {entite} échoue sur l'environnement de test"
                " ({libelle}).",
            ),
            (
                "Version applicative différente entre environnements pour {objet}",
                "L'environnement de recette de l'Entité {entite} n'a pas reçu la dernière"
                " livraison ({libelle}).",
            ),
            (
                "Redémarrage du serveur lors du traitement portant sur {objet}",
                "Le traitement de l'Entité {entite} est interrompu sans message d'erreur"
                " ({libelle}).",
            ),
        ),
        CauseRacine.donnee_test: (
            (
                "Jeu d'essai incohérent pour {objet}",
                "Les données préparées pour l'Entité {entite} ne respectent pas les règles"
                " métier ({libelle}).",
            ),
            (
                "Résultat attendu erroné dans le cas de test sur {objet}",
                "L'attendu du scénario de l'Entité {entite} ne tient pas compte de la règle"
                " en vigueur ({libelle}).",
            ),
            (
                "Données de test périmées sur {objet}",
                "Le jeu d'essai de l'Entité {entite} date d'avant la dernière bascule ({libelle}).",
            ),
            (
                "Jeu d'essai incomplet pour {objet}",
                "Des dossiers nécessaires au scénario manquent pour l'Entité {entite} ({libelle}).",
            ),
            (
                "Même dossier de test utilisé par deux scénarios sur {objet}",
                "Les tests de l'Entité {entite} se perturbent l'un l'autre ({libelle}).",
            ),
            (
                "Dates de test incohérentes avec le calendrier sur {objet}",
                "Les dates du jeu d'essai de l'Entité {entite} tombent hors de la période"
                " testée ({libelle}).",
            ),
        ),
        CauseRacine.hors_perimetre: (
            (
                "Demande d'évolution sur {ecran}",
                "L'Entité {entite} souhaite un affichage supplémentaire, absent de l'ancien"
                " système ({libelle}).",
            ),
            (
                "Nouveau rapport souhaité sur {objet}",
                "L'Entité {entite} demande un état qui n'existait pas avant la migration"
                " ({libelle}).",
            ),
            (
                "Comportement identique à l'ancien système sur {objet}",
                "Le fonctionnement signalé par l'Entité {entite} est conforme à l'existant"
                " ({libelle}).",
            ),
            (
                "Question d'utilisation sur {ecran}",
                "L'Entité {entite} demande comment réaliser une opération courante ({libelle}).",
            ),
            (
                "Anomalie de l'ancien système signalée sur {objet}",
                "L'écart signalé par l'Entité {entite} existait déjà avant la migration"
                " ({libelle}).",
            ),
            (
                "Demande d'ergonomie sur {ecran}",
                "L'Entité {entite} propose de réorganiser les zones de saisie ({libelle}).",
            ),
        ),
    }
)
"""Gabarits d'Anomalies par Cause racine (H-18), la cause jamais nommée."""

GABARITS_CAS_DE_TEST: Gabarits = (
    (
        "Contrôle des totaux après chargement sur {objet}",
        "Comparer les totaux de l'Entité {entite} entre ancien et nouveau système ({libelle}).",
    ),
    (
        "Parcours de bout en bout via {ecran}",
        "Dérouler le parcours complet de l'Entité {entite} et comparer aux attendus ({libelle}).",
    ),
    (
        "Vérification de bonne réception sur {flux}",
        "Envoyer un fichier fictif de l'Entité {entite} et vérifier sa bonne réception"
        " ({libelle}).",
    ),
    (
        "Rapprochement ancien et nouveau système sur {objet}",
        "Rapprocher un échantillon fictif de l'Entité {entite} ligne à ligne ({libelle}).",
    ),
    (
        "Non-régression sur {ecran}",
        "Rejouer les scénarios de l'Entité {entite} validés à la livraison précédente ({libelle}).",
    ),
)
"""Gabarits de Cas de test."""

CERTIFICATIONS: tuple[TexteTicket, ...] = (
    TexteTicket(
        titre="Certification de la migration de l'Entité {entite}",
        description="Avis de l'équipe métier de l'Entité {entite} sur la qualité de la migration.",
    ),
    TexteTicket(
        titre="Validation métier de la bascule de l'Entité {entite}",
        description="Synthèse des contrôles réalisés avant la bascule de l'Entité {entite}.",
    ),
    TexteTicket(
        titre="Recette finale de l'Entité {entite}",
        description="Décision de l'Entité {entite} à l'issue des tests de non-régression.",
    ),
    TexteTicket(
        titre="Attestation de conformité de l'Entité {entite}",
        description="Engagement de l'Entité {entite} sur la complétude des données migrées.",
    ),
)
"""Textes des Certifications : `{entite}` seulement, une Certification n'a pas de Domaine."""


def _remplir(gabarits: Gabarits, vocabulaire: Vocabulaire) -> tuple[TexteTicket, ...]:
    """Une paire par gabarit ; l'objet métier pris tour à tour dans le vocabulaire."""
    textes = []
    for rang, (titre, description) in enumerate(gabarits):
        mots = {
            "objet": vocabulaire.objets[rang % len(vocabulaire.objets)],
            "flux": vocabulaire.flux,
            "ecran": vocabulaire.ecran,
            "libelle": vocabulaire.libelle,
            "entite": "{entite}",
        }
        textes.append(
            TexteTicket(titre=titre.format(**mots), description=description.format(**mots))
        )
    return tuple(textes)


def textes_domaine(vocabulaire: Vocabulaire) -> TextesDomaine:
    """Textes d'un Domaine : Anomalies par Cause racine, puis Cas de test."""
    return TextesDomaine(
        anomalies={
            cause: _remplir(GABARITS_ANOMALIES[cause], vocabulaire) for cause in CauseRacine
        },
        cas_de_test=_remplir(GABARITS_CAS_DE_TEST, vocabulaire),
    )


def corpus_provisoire(
    domaines: Sequence[str], *, version_corpus: str = VERSION_CORPUS_PROVISOIRE
) -> Corpus:
    """Corpus provisoire des `domaines` (`modele_corpus: gabarits-provisoires`).

    Un Domaine sans vocabulaire n'a pas de section propre : il tirera dans `generique`.
    """
    return Corpus(
        version_corpus=version_corpus,
        modele_corpus=MODELE_GABARITS,
        domaines={
            domaine: textes_domaine(VOCABULAIRES[domaine])
            for domaine in domaines
            if domaine in VOCABULAIRES
        },
        generique=textes_domaine(VOCABULAIRE_GENERIQUE),
        certifications=CERTIFICATIONS,
    )
