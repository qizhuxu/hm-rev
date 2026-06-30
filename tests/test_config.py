from pathlib import Path

from hm_api.config import get_cred_dir


def test_credential_directory_defaults_to_local_cred(monkeypatch):
    monkeypatch.delenv("HM_API_CRED_DIR", raising=False)

    assert get_cred_dir() == Path("./cred")


def test_credential_directory_uses_environment_variable(monkeypatch, tmp_path):
    custom_dir = tmp_path / "hm-api-data"
    monkeypatch.setenv("HM_API_CRED_DIR", str(custom_dir))

    assert get_cred_dir() == custom_dir
