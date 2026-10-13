"""Secrets, lus uniquement dans les variables d'environnement ou `.env` (AD-19)."""

from pathlib import Path

from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from usine.contrats.erreurs import UsineErreur


class Secrets(BaseSettings):
    """Identifiants et bascules lus dans l'environnement ; aucun n'est exigé au chargement."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_ignore_empty=True, extra="ignore"
    )

    jira_email: str | None = None
    jira_token_lecture: SecretStr | None = None
    jira_token_injection: SecretStr | None = None
    jira_dc_pat: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    mistral_api_key: SecretStr | None = None
    usine_cle_pseudo: SecretStr | None = None
    usine_mode_repli: bool = False
    usine_langfuse: bool = False
    """Bonus (Story 6.13) : envoie les traces LLM à Langfuse ; désactivé par défaut."""
    langfuse_host: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    usine_racine: str | None = None
    """Racine de l'UI (répertoire du dépôt) ; vide ou absente : le répertoire courant."""


def charger_secrets(racine: Path) -> Secrets:
    """Secrets de l'environnement et de `racine/.env`.

    Une valeur illisible (`USINE_MODE_REPLI=peut-être`) lève une `UsineErreur` qui nomme la
    variable ; la valeur n'est jamais recopiée, elle peut être un secret (l'exception d'origine,
    qui la cite, n'est pas chaînée). Un `.env` illisible ou non UTF-8 lève une `UsineErreur`
    qui nomme le fichier.
    """
    fichier = racine / ".env"
    try:
        return Secrets(_env_file=fichier)
    except UnicodeDecodeError:
        raise UsineErreur(f"{fichier} : fichier non encodé en UTF-8") from None
    except OSError as exc:
        raise UsineErreur(f"{fichier} : fichier illisible ({exc.strerror or exc})") from None
    except ValidationError as exc:
        details = "; ".join(
            f"{str(erreur['loc'][0]).upper() if erreur['loc'] else '?'} : {erreur['msg']}"
            for erreur in exc.errors(include_input=False, include_url=False)
        )
        raise UsineErreur(
            f"variable d'environnement illisible ({fichier} ou environnement) : {details}"
        ) from None
