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
    usine_racine: str | None = None
    """Racine de l'UI (répertoire du dépôt) ; vide ou absente : le répertoire courant."""


def charger_secrets(racine: Path) -> Secrets:
    """Secrets de l'environnement et de `racine/.env`.

    Une valeur illisible (`USINE_MODE_REPLI=peut-être`) lève une `UsineErreur` qui nomme la
    variable ; la valeur n'est jamais recopiée, elle peut être un secret.
    """
    try:
        return Secrets(_env_file=racine / ".env")
    except ValidationError as exc:
        details = "; ".join(
            f"{str(erreur['loc'][0]).upper() if erreur['loc'] else '?'} : {erreur['msg']}"
            for erreur in exc.errors(include_input=False, include_url=False)
        )
        raise UsineErreur(
            f"variable d'environnement illisible ({racine / '.env'} ou environnement) : {details}"
        ) from exc
