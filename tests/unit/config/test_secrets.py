from pathlib import Path

import pytest

from usine.config import Secrets, charger_secrets
from usine.config import secrets as secrets_module
from usine.contrats.erreurs import UsineErreur


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


def test_charger_secrets_lit_le_env_de_la_racine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for nom in ("USINE_MODE_REPLI", "USINE_RACINE"):
        monkeypatch.delenv(nom, raising=False)
    (tmp_path / ".env").write_text("USINE_MODE_REPLI=1\nUSINE_RACINE=C:/depot\n", encoding="utf-8")
    secrets = charger_secrets(tmp_path)
    assert secrets.usine_mode_repli is True
    assert secrets.usine_racine == "C:/depot"
    assert charger_secrets(tmp_path / "absent").usine_racine is None


def test_charger_secrets_nomme_la_variable_illisible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("USINE_MODE_REPLI", "peut-être")
    with pytest.raises(UsineErreur, match="USINE_MODE_REPLI") as erreur:
        charger_secrets(tmp_path)
    assert "peut-être" not in str(erreur.value)
    assert erreur.value.__cause__ is None  # la ValidationError, qui cite la valeur, est coupée
    assert erreur.value.__suppress_context__


def test_charger_secrets_env_non_utf8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("USINE_MODE_REPLI", raising=False)
    (tmp_path / ".env").write_bytes("USINE_RACINE=dépôt\n".encode("latin-1"))
    with pytest.raises(UsineErreur, match=r"\.env.*UTF-8"):
        charger_secrets(tmp_path)


def test_charger_secrets_env_illisible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuser(**_options: object) -> Secrets:
        raise PermissionError(13, "accès refusé", str(tmp_path / ".env"))

    monkeypatch.setattr(secrets_module, "Secrets", refuser)
    with pytest.raises(UsineErreur, match=r"\.env.*accès refusé") as erreur:
        charger_secrets(tmp_path)
    assert erreur.value.__suppress_context__


def test_mode_llm_local_sans_cle_par_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    for nom in ("LLAMA_API_KEY", "USINE_URL_LLM_LOCAL"):
        monkeypatch.delenv(nom, raising=False)
    secrets = Secrets(_env_file=None)
    assert secrets.llama_api_key is None
    assert secrets.usine_url_llm_local is None
    monkeypatch.setenv("LLAMA_API_KEY", "cle-locale")
    monkeypatch.setenv("USINE_URL_LLM_LOCAL", "http://hote:9000/v1")
    secrets = Secrets(_env_file=None)
    assert secrets.llama_api_key is not None
    assert "cle-locale" not in repr(secrets)
    assert secrets.usine_url_llm_local == "http://hote:9000/v1"
