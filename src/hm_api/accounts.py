"""Multi-account credential storage and connectivity checks."""

from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import (
    DEVECO_BASE_URL,
    USER_AGENT,
    get_accounts_file,
    get_auth_file,
    get_token_file,
)
from .crypto import decrypt_value, encrypt_value, load_auth_data, save_auth_data


MODEL_CONFIG_URL = (
    f"{DEVECO_BASE_URL}/codeGenie/modelConfig?localVersion=0&pluginVersion=CLI.0.1.0"
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_state() -> dict[str, Any]:
    return {"version": 1, "active_account_id": None, "accounts": []}


def _parse_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1].replace("-", "+").replace("_", "/")
    payload += "=" * ((4 - len(payload) % 4) % 4)
    try:
        return json.loads(base64.b64decode(payload).decode("utf-8"))
    except Exception:
        return {}


def _new_account_id() -> str:
    return f"acct_{uuid.uuid4().hex[:12]}"


def _read_token_file() -> str | None:
    token_file = get_token_file()
    if not token_file.exists():
        return None
    try:
        raw = json.loads(token_file.read_text(encoding="utf-8"))
        return decrypt_value(raw)
    except Exception:
        return None


def _account_public(record: dict[str, Any], active_account_id: str | None) -> dict[str, Any]:
    private_keys = {"credentials", "access_token", "refresh_token", "jwt_token"}
    public = {
        key: value
        for key, value in record.items()
        if key not in private_keys
    }
    public["is_active"] = record.get("account_id") == active_account_id
    public.setdefault("connectivity", None)
    return public


def _decrypt_account(record: dict[str, Any], active_account_id: str | None) -> dict[str, Any]:
    credentials = record.get("credentials", {})
    account = _account_public(record, active_account_id)
    account["access_token"] = decrypt_value(credentials["access"])
    account["refresh_token"] = decrypt_value(credentials["refresh"])
    account["jwt_token"] = decrypt_value(credentials["jwt_token"])
    return account


def _encrypted_credentials(
    access_token: str,
    refresh_token: str,
    jwt_token: str,
) -> dict[str, dict[str, str]]:
    return {
        "access": encrypt_value(access_token),
        "refresh": encrypt_value(refresh_token),
        "jwt_token": encrypt_value(jwt_token),
    }


def _normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    accounts = state.get("accounts")
    if not isinstance(accounts, list):
        accounts = []
    active_account_id = state.get("active_account_id")
    if active_account_id and not any(
        account.get("account_id") == active_account_id for account in accounts
    ):
        active_account_id = accounts[0].get("account_id") if accounts else None
    return {
        "version": 1,
        "active_account_id": active_account_id,
        "accounts": accounts,
    }


def _write_raw_state(state: dict[str, Any]) -> None:
    accounts_file = get_accounts_file()
    accounts_file.parent.mkdir(parents=True, exist_ok=True)
    accounts_file.write_text(
        json.dumps(_normalize_state(state), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.chmod(accounts_file, 0o600)


def _migrate_legacy_state() -> dict[str, Any]:
    data = load_auth_data()
    deveco = data.get("deveco", {}) if isinstance(data, dict) else {}
    access = deveco.get("access")
    refresh = deveco.get("refresh")
    jwt_token = _read_token_file()
    if not access or not refresh or not jwt_token:
        return _default_state()

    payload = _parse_jwt_payload(jwt_token)
    user_id = str(payload.get("userId") or "legacy")
    user_name = str(payload.get("userName") or user_id)
    account_id = f"legacy_{user_id}"
    now = _now()
    state = {
        "version": 1,
        "active_account_id": account_id,
        "accounts": [
            {
                "account_id": account_id,
                "display_name": user_name or "默认账号",
                "user_id": user_id,
                "user_name": user_name,
                "created_at": now,
                "updated_at": now,
                "last_used_at": None,
                "connectivity": None,
                "credentials": _encrypted_credentials(access, refresh, jwt_token),
            }
        ],
    }
    _write_raw_state(state)
    return state


def _read_raw_state() -> dict[str, Any]:
    accounts_file = get_accounts_file()
    if not accounts_file.exists():
        return _migrate_legacy_state()
    try:
        state = json.loads(accounts_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _default_state()
    if not isinstance(state, dict):
        return _default_state()
    return _normalize_state(state)


def _sync_legacy_files(account: dict[str, Any] | None) -> None:
    if not account:
        for path in (get_auth_file(), get_token_file()):
            if path.exists():
                path.unlink()
        return
    save_auth_data(
        {
            "deveco": {
                "type": "oauth",
                "access": account["access_token"],
                "refresh": account["refresh_token"],
            }
        }
    )
    token_file = get_token_file()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(
        json.dumps(encrypt_value(account["jwt_token"])),
        encoding="utf-8",
    )
    os.chmod(token_file, 0o600)


def load_account_state() -> dict[str, Any]:
    state = _read_raw_state()
    return {
        "version": state["version"],
        "active_account_id": state["active_account_id"],
        "accounts": [
            _account_public(account, state["active_account_id"])
            for account in state["accounts"]
        ],
    }


def list_accounts() -> list[dict[str, Any]]:
    return load_account_state()["accounts"]


def get_account(account_id: str) -> dict[str, Any] | None:
    state = _read_raw_state()
    for account in state["accounts"]:
        if account.get("account_id") == account_id:
            return _decrypt_account(account, state["active_account_id"])
    return None


def get_active_account() -> dict[str, Any] | None:
    state = _read_raw_state()
    active_account_id = state.get("active_account_id")
    if not active_account_id:
        return None
    for account in state["accounts"]:
        if account.get("account_id") == active_account_id:
            decrypted = _decrypt_account(account, active_account_id)
            return decrypted
    return None


def save_account_from_user_info(
    user_info: Any,
    *,
    display_name: str | None = None,
    account_id: str | None = None,
    activate: bool = True,
) -> str:
    state = _read_raw_state()
    now = _now()
    target_account_id = account_id or _new_account_id()
    accounts = [
        account
        for account in state["accounts"]
        if account.get("account_id") != target_account_id
    ]
    previous = next(
        (
            account
            for account in state["accounts"]
            if account.get("account_id") == target_account_id
        ),
        {},
    )
    record = {
        "account_id": target_account_id,
        "display_name": display_name
        or previous.get("display_name")
        or getattr(user_info, "user_name", "")
        or getattr(user_info, "user_id", "")
        or "DevEco 账号",
        "user_id": getattr(user_info, "user_id", ""),
        "user_name": getattr(user_info, "user_name", ""),
        "created_at": previous.get("created_at") or now,
        "updated_at": now,
        "last_used_at": previous.get("last_used_at"),
        "connectivity": previous.get("connectivity"),
        "credentials": _encrypted_credentials(
            getattr(user_info, "access_token", ""),
            getattr(user_info, "refresh_token", ""),
            getattr(user_info, "jwt_token", ""),
        ),
    }
    accounts.append(record)
    state["accounts"] = accounts
    if activate or not state.get("active_account_id"):
        state["active_account_id"] = target_account_id
    _write_raw_state(state)
    _sync_legacy_files(get_active_account())
    return target_account_id


def activate_account(account_id: str) -> dict[str, Any]:
    state = _read_raw_state()
    if not any(account.get("account_id") == account_id for account in state["accounts"]):
        raise KeyError("Account not found")
    state["active_account_id"] = account_id
    for account in state["accounts"]:
        if account.get("account_id") == account_id:
            account["updated_at"] = _now()
    _write_raw_state(state)
    active = get_active_account()
    _sync_legacy_files(active)
    assert active is not None
    return _account_public(active, account_id)


def rename_account(account_id: str, display_name: str) -> dict[str, Any]:
    state = _read_raw_state()
    for account in state["accounts"]:
        if account.get("account_id") == account_id:
            account["display_name"] = display_name
            account["updated_at"] = _now()
            _write_raw_state(state)
            return _account_public(account, state["active_account_id"])
    raise KeyError("Account not found")


def delete_account(account_id: str) -> None:
    state = _read_raw_state()
    remaining = [
        account
        for account in state["accounts"]
        if account.get("account_id") != account_id
    ]
    if len(remaining) == len(state["accounts"]):
        raise KeyError("Account not found")
    state["accounts"] = remaining
    if state.get("active_account_id") == account_id:
        state["active_account_id"] = remaining[0].get("account_id") if remaining else None
    _write_raw_state(state)
    _sync_legacy_files(get_active_account())


def mark_account_used(account_id: str) -> None:
    state = _read_raw_state()
    for account in state["accounts"]:
        if account.get("account_id") == account_id:
            account["last_used_at"] = _now()
            account["updated_at"] = _now()
            _write_raw_state(state)
            return


def _build_client(proxy: str | None = None, timeout: float = 30.0) -> httpx.AsyncClient:
    mounts = {}
    if proxy:
        mounts = {
            "http://": httpx.AsyncHTTPTransport(proxy=proxy),
            "https://": httpx.AsyncHTTPTransport(proxy=proxy),
        }
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN"},
        timeout=httpx.Timeout(timeout),
        follow_redirects=True,
        mounts=mounts,
    )


def _model_count(data: dict[str, Any]) -> int:
    count = 0
    for group in data.get("body", {}).get("inner_models", []):
        count += len(group.get("model_configs", []))
    return count


def _redact_error(message: str, account: dict[str, Any] | None) -> str:
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [redacted]", message)
    redacted = re.sub(r"tempToken=([^&\s]+)", "tempToken=[redacted]", redacted)
    if account:
        for key in ("access_token", "refresh_token", "jwt_token"):
            value = account.get(key)
            if value:
                redacted = redacted.replace(str(value), "[redacted]")
    return redacted[:240] or "连通性检测失败"


def update_account_connectivity(
    account_id: str,
    result: dict[str, Any],
) -> None:
    state = _read_raw_state()
    for account in state["accounts"]:
        if account.get("account_id") == account_id:
            account["connectivity"] = result
            account["updated_at"] = _now()
            _write_raw_state(state)
            return
    raise KeyError("Account not found")


async def check_account_connectivity(
    account_id: str,
    proxy: str | None = None,
) -> dict[str, Any]:
    account = get_account(account_id)
    if not account:
        raise KeyError("Account not found")

    started = time.perf_counter()
    checked_at = _now()
    try:
        async with _build_client(proxy=proxy, timeout=30.0) as client:
            response = await client.get(
                MODEL_CONFIG_URL,
                headers={
                    "Authorization": f"Bearer {account['access_token']}",
                    "Content-Type": "application/json",
                },
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        success = response.status_code == 200
        model_count = _model_count(response.json()) if success else 0
        result = {
            "success": success,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "model_count": model_count,
            "checked_at": checked_at,
            "error": None
            if success
            else _redact_error(response.text or "上游返回错误", account),
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        result = {
            "success": False,
            "status_code": None,
            "latency_ms": latency_ms,
            "model_count": 0,
            "checked_at": checked_at,
            "error": _redact_error(str(exc) or "连通性检测失败", account),
        }
    update_account_connectivity(account_id, result)
    return result
