"""Registre des quotas et des prix par modèle (AD-13, NFR-9).

Inspiré de wavestack : pour chaque `fournisseur:modele`, le prix par million de jetons (en
euros, converti au taux indicatif `TAUX_USD_EUR` quand le tarif public est en dollars) et le
débit autorisé, qui fixe l'espacement minimal entre deux appels au même modèle. Les quotas
gratuits de Mistral (offre « Experiment ») sont ceux de la console au 12/10/2026 ; ils changent
sans préavis et se relèvent en console avant une démo.
"""

from dataclasses import dataclass
from decimal import Decimal

from usine.contrats.erreurs import UsineErreur

TAUX_USD_EUR = Decimal("0.92")
"""Taux indicatif dollar → euro des tarifs publics, pour `cout_estime_eur`."""

_MILLION = Decimal(1_000_000)


@dataclass(frozen=True)
class TarifModele:
    """Prix et quota d'un modèle."""

    prix_entree_eur_mtok: Decimal
    """Euros par million de jetons d'entrée."""
    prix_sortie_eur_mtok: Decimal
    """Euros par million de jetons de sortie."""
    requetes_par_minute: int
    """Débit autorisé ; l'adaptateur espace ses appels d'au moins `60 / requetes_par_minute` s."""
    jetons_par_minute: int
    gratuit: bool = False
    """Quota gratuit (offre « Experiment » de Mistral) : coût réel nul, coût estimé conservé."""
    temperature: bool = True
    """Faux si le modèle refuse le réglage de température (Claude Haiku, Sonnet et Opus 5.5)."""

    @property
    def espacement_s(self) -> float:
        """Délai minimal entre deux appels au même modèle, en secondes."""
        return 60.0 / self.requetes_par_minute


def _usd(entree: str, sortie: str) -> tuple[Decimal, Decimal]:
    return Decimal(entree) * TAUX_USD_EUR, Decimal(sortie) * TAUX_USD_EUR


# Tarifs publics relevés sur platform.claude.com/docs/en/about-claude/pricing le 13/10/2026.
_SONNET = _usd("2", "10")
_HAIKU = _usd("1", "5")
_OPUS = _usd("4", "20")

REGISTRE: dict[str, TarifModele] = {
    # Anthropic, palier 1 de l'API (50 requêtes par minute).
    "anthropic:claude-sonnet-5-5": TarifModele(*_SONNET, 50, 30_000, temperature=False),
    "anthropic:claude-opus-5-5": TarifModele(*_OPUS, 50, 30_000, temperature=False),
    "anthropic:claude-haiku-4-5": TarifModele(*_HAIKU, 50, 50_000),
    # Haiku 5.5 : modèle de la classification (Story 6.5) ; refuse une température non par
    # défaut, comme Sonnet et Opus 5.5.
    "anthropic:claude-haiku-5-5": TarifModele(*_usd("0.1", "0.5"), 50, 50_000, temperature=False),
    # Mistral, offre gratuite « Experiment » : 1 requête par seconde, 500 000 jetons par minute.
    "mistral:mistral-large-latest": TarifModele(*_usd("2", "6"), 60, 500_000, gratuit=True),
    "mistral:mistral-medium-latest": TarifModele(*_usd("0.4", "2"), 60, 500_000, gratuit=True),
    "mistral:mistral-small-latest": TarifModele(*_usd("0.1", "0.3"), 60, 500_000, gratuit=True),
    # llama.cpp local (llama-server) : aucun coût, débit borné par le poste seulement.
    "llama:qwen3-8b-q4_k_m": TarifModele(Decimal(0), Decimal(0), 600, 10_000_000, gratuit=True),
}
"""Tarifs par `version_modele` (`fournisseur:modele`)."""


def tarif(version_modele: str) -> TarifModele:
    """Tarif de `version_modele` ; un modèle absent du registre lève une `UsineErreur`."""
    try:
        return REGISTRE[version_modele]
    except KeyError:
        connus = ", ".join(sorted(REGISTRE))
        raise UsineErreur(
            f"config/llm.yaml : modèle {version_modele!r} absent du registre des quotas et des"
            f" prix (adaptateurs/llm/registre.py) ; modèles connus : {connus}"
        ) from None


def cout_estime_eur(version_modele: str, jetons_entree: int, jetons_sortie: int) -> Decimal:
    """Coût estimé d'un appel, en euros, d'après le registre."""
    prix = tarif(version_modele)
    return (
        prix.prix_entree_eur_mtok * jetons_entree + prix.prix_sortie_eur_mtok * jetons_sortie
    ) / _MILLION
