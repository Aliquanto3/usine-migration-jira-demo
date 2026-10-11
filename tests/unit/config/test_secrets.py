import pytest

from usine.config import Secrets


def test_secrets_lus_dans_l_environnement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIRA_TOKEN_LECTURE", "jeton-factice")
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    secrets = Secrets(_env_file=None)
    assert secrets.jira_token_lecture is not None
    assert secrets.jira_token_lecture.get_secret_value() == "jeton-factice"
    assert "jeton-factice" not in repr(secrets)
    assert secrets.usine_mode_repli is True


def test_secrets_absents_par_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    for nom in ("ANTHROPIC_API_KEY", "USINE_MODE_REPLI"):
        monkeypatch.delenv(nom, raising=False)
    secrets = Secrets(_env_file=None)
    assert secrets.anthropic_api_key is None
    assert secrets.usine_mode_repli is False


def test_variable_vide_ignoree(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un `.env` copié de `.env.example` sans valeur se charge."""
    monkeypatch.setenv("USINE_MODE_REPLI", "")
    assert Secrets(_env_file=None).usine_mode_repli is False
