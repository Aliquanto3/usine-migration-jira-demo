"""Secrets, lus uniquement dans les variables d'environnement ou `.env` (AD-19)."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
