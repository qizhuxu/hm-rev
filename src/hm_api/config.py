"""Shared configuration and constants."""

from __future__ import annotations

import os
from pathlib import Path

DEVECO_BASE_URL = "https://cn.devecostudio.huawei.com"
DEVECO_AUTH_URL = "console/DevEcoIDE/apply"
DEVECO_TEMP_TOKEN_CHECK_URL = "authrouter/auth/api/temptoken/check"
DEVECO_JWT_TOKEN_CHECK_URL = "authrouter/auth/api/jwToken/check"
DEVECO_SUCCESS_REDIRECT_URL = "console/DevEcoCode/loginSuccess"
DEVECO_FAILED_REDIRECT_URL = "console/DevEcoCode/loginFailed"
DEVECO_APP_ID = "1008"
DEVECO_DEFAULT_AUTH_PORT = 10101

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_PROXY = ""

ENV_HOST = "HM_API_HOST"
ENV_PORT = "HM_API_PORT"
ENV_API_KEY = "HM_API_KEY"
ENV_PROXY = "HM_API_PROXY"
ENV_CRED_DIR = "HM_API_CRED_DIR"


def _env_value(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def get_default_host() -> str:
    return _env_value(ENV_HOST, DEFAULT_HOST)


def get_default_port() -> int:
    value = _env_value(ENV_PORT, str(DEFAULT_PORT))
    try:
        port = int(value)
    except ValueError as exc:
        raise ValueError(f"{ENV_PORT} must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"{ENV_PORT} must be between 1 and 65535")
    return port


def get_default_proxy() -> str | None:
    return _env_value(ENV_PROXY) or None


def get_default_api_key() -> str | None:
    return _env_value(ENV_API_KEY) or None


def get_cred_dir() -> Path:
    return Path(_env_value(ENV_CRED_DIR, "./cred")).expanduser()


def get_token_file() -> Path:
    return get_cred_dir() / "token.enc"


def get_auth_file() -> Path:
    return get_cred_dir() / "auth.json"


def get_accounts_file() -> Path:
    return get_cred_dir() / "accounts.json"


def get_usage_file() -> Path:
    return get_cred_dir() / "usage.jsonl"


CRED_DIR = get_cred_dir()
TOKEN_FILE = get_token_file()
AUTH_FILE = get_auth_file()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
