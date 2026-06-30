"""Lightweight local encryption helpers for credentials."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import get_auth_file, get_cred_dir

SENSITIVE_KEYS = {"access", "refresh", "key", "token", "jwt_token"}


def _key_file() -> Path:
    return get_cred_dir() / ".kek"


def _get_kek() -> bytes:
    cred_dir = get_cred_dir()
    key_file = _key_file()
    cred_dir.mkdir(parents=True, exist_ok=True)
    if key_file.exists():
        with open(key_file, "rb") as f:
            return f.read()
    key = AESGCM.generate_key(bit_length=256)
    with open(key_file, "wb") as f:
        f.write(key)
    os.chmod(key_file, 0o600)
    return key


def _aes_gcm_encrypt(plaintext: str) -> dict[str, str]:
    key = _get_kek()
    aesgcm = AESGCM(key)
    iv = os.urandom(12)
    ct = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    return {
        "iv": base64.b64encode(iv).decode(),
        "ct": base64.b64encode(ct).decode(),
    }


def _aes_gcm_decrypt(blob: dict[str, str]) -> str:
    key = _get_kek()
    aesgcm = AESGCM(key)
    iv = base64.b64decode(blob["iv"])
    ct = base64.b64decode(blob["ct"])
    return aesgcm.decrypt(iv, ct, None).decode("utf-8")


def encrypt_value(value: str) -> dict[str, str]:
    return _aes_gcm_encrypt(value)


def decrypt_value(blob: dict[str, str]) -> str:
    return _aes_gcm_decrypt(blob)


def encrypt_record(record: dict) -> dict:
    result: dict = {}
    for k, v in record.items():
        if isinstance(v, str) and k in SENSITIVE_KEYS:
            result[k] = encrypt_value(v)
        else:
            result[k] = v
    return result


def decrypt_record(record: dict) -> dict:
    result: dict = {}
    for k, v in record.items():
        if isinstance(v, dict) and "iv" in v and "ct" in v:
            result[k] = decrypt_value(v)
        else:
            result[k] = v
    return result


def load_auth_data() -> dict:
    auth_file = get_auth_file()
    if not auth_file.exists():
        return {}
    with open(auth_file, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        return {}
    return {k: decrypt_record(v) if isinstance(v, dict) else v for k, v in raw.items()}


def save_auth_data(data: dict) -> None:
    cred_dir = get_cred_dir()
    auth_file = get_auth_file()
    cred_dir.mkdir(parents=True, exist_ok=True)
    encrypted = {
        k: encrypt_record(v) if isinstance(v, dict) else v for k, v in data.items()
    }
    with open(auth_file, "w", encoding="utf-8") as f:
        json.dump(encrypted, f, indent=2)
    os.chmod(auth_file, 0o600)
