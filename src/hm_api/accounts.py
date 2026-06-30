"""Multi-account credential storage and connectivity checks."""

from __future__ import annotations

import base64
import json
import os
import re
import threading
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
    get_default_account_strategy,
    get_token_file,
    normalize_account_strategy,
)
from .crypto import decrypt_value, encrypt_value, load_auth_data, save_auth_data


MODEL_CONFIG_URL = (
    f"{DEVECO_BASE_URL}/codeGenie/modelConfig?localVersion=0&pluginVersion=CLI.0.1.0"
)
_SELECTION_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_state() -> dict[str, Any]:
    return {
        "version": 1,
        "active_account_id": None,
        "settings": {
            "account_strategy": get_default_account_strategy(),
            "round_robin_cursor": 0,
        },
        "accounts": [],
    }


def _default_settings() -> dict[str, Any]:
    return {"account_strategy": get_default_account_strategy(), "round_robin_cursor": 0}


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
    public["tags"] = _normalize_tags(public.get("tags"))
    public["note"] = str(public.get("note") or "")
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


def _normalize_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        tag = str(item).strip()
        if tag and tag not in tags:
            tags.append(tag[:32])
    return tags[:12]


def _normalize_account_record(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    normalized = dict(record)
    normalized["tags"] = _normalize_tags(normalized.get("tags"))
    normalized["note"] = str(normalized.get("note") or "")[:500]
    normalized.setdefault("connectivity", None)
    normalized.setdefault("last_used_at", None)
    return normalized


def _normalize_settings(value: Any) -> dict[str, Any]:
    settings = value if isinstance(value, dict) else {}
    cursor = settings.get("round_robin_cursor", 0)
    try:
        cursor = int(cursor)
    except (TypeError, ValueError):
        cursor = 0
    return {
        "account_strategy": normalize_account_strategy(
            str(settings.get("account_strategy") or get_default_account_strategy())
        ),
        "round_robin_cursor": max(cursor, 0),
    }


def _normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    accounts = state.get("accounts")
    if not isinstance(accounts, list):
        accounts = []
    accounts = [
        normalized
        for account in accounts
        if (normalized := _normalize_account_record(account)) is not None
    ]
    active_account_id = state.get("active_account_id")
    if active_account_id and not any(
        account.get("account_id") == active_account_id for account in accounts
    ):
        active_account_id = accounts[0].get("account_id") if accounts else None
    return {
        "version": 1,
        "active_account_id": active_account_id,
        "settings": _normalize_settings(state.get("settings")),
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
    refresh = deveco.get("refresh") or ""
    jwt_token = _read_token_file()
    if not access or not jwt_token:
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
                "tags": [],
                "note": "",
                "credentials": _encrypted_credentials(access, refresh, jwt_token),
            }
        ],
    }
    _write_raw_state(state)
    return _normalize_state(state)


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
        "settings": dict(state["settings"]),
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


def get_account_strategy() -> str:
    return str(_read_raw_state()["settings"]["account_strategy"])


def set_account_strategy(strategy: str) -> str:
    normalized = normalize_account_strategy(strategy)
    state = _read_raw_state()
    state["settings"]["account_strategy"] = normalized
    _write_raw_state(state)
    return normalized


def _has_valid_credentials(record: dict[str, Any]) -> bool:
    credentials = record.get("credentials")
    if not isinstance(credentials, dict):
        return False
    required = ("access", "jwt_token")
    return all(isinstance(credentials.get(key), dict) for key in required)


def _connectivity_failed(record: dict[str, Any]) -> bool:
    connectivity = record.get("connectivity")
    return isinstance(connectivity, dict) and connectivity.get("success") is False


def _decrypt_records(
    records: list[dict[str, Any]],
    active_account_id: str | None,
) -> list[dict[str, Any]]:
    accounts: list[dict[str, Any]] = []
    for record in records:
        try:
            accounts.append(_decrypt_account(record, active_account_id))
        except Exception:
            continue
    return accounts


def select_account_candidates(strategy: str | None = None) -> list[dict[str, Any]]:
    with _SELECTION_LOCK:
        state = _read_raw_state()
        selected_strategy = normalize_account_strategy(
            strategy or str(state["settings"]["account_strategy"])
        )
        active_account_id = state.get("active_account_id")
        valid_records = [
            account for account in state["accounts"] if _has_valid_credentials(account)
        ]
        healthy_records = [
            account for account in valid_records if not _connectivity_failed(account)
        ]
        pool = healthy_records or valid_records

        if selected_strategy == "active_only":
            active_records = [
                account
                for account in valid_records
                if account.get("account_id") == active_account_id
            ]
            return _decrypt_records(active_records, active_account_id)

        if selected_strategy == "round_robin":
            if not pool:
                return []
            cursor = int(state["settings"].get("round_robin_cursor") or 0) % len(pool)
            ordered = pool[cursor:] + pool[:cursor]
            state["settings"]["round_robin_cursor"] = (cursor + 1) % len(pool)
            _write_raw_state(state)
            return _decrypt_records(ordered, active_account_id)

        active_records = [
            account for account in pool if account.get("account_id") == active_account_id
        ]
        backup_records = [
            account for account in pool if account.get("account_id") != active_account_id
        ]
        failed_active_records = [
            account
            for account in valid_records
            if account.get("account_id") == active_account_id and account not in pool
        ]
        return _decrypt_records(
            active_records + backup_records + failed_active_records,
            active_account_id,
        )


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
        "tags": _normalize_tags(previous.get("tags")),
        "note": str(previous.get("note") or "")[:500],
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


def update_account_profile(
    account_id: str,
    *,
    display_name: str | None = None,
    tags: list[str] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    state = _read_raw_state()
    for account in state["accounts"]:
        if account.get("account_id") == account_id:
            if display_name is not None:
                account["display_name"] = display_name.strip() or account.get(
                    "display_name",
                    "DevEco 账号",
                )
            if tags is not None:
                account["tags"] = _normalize_tags(tags)
            if note is not None:
                account["note"] = str(note).strip()[:500]
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


def _models(data: dict[str, Any]) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    for group in data.get("body", {}).get("inner_models", []):
        for cfg in group.get("model_configs", []):
            model_id = cfg.get("model_id")
            if model_id:
                models.append({"id": str(model_id), "owned_by": "deveco"})
    return models


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


async def fetch_account_models(
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
        body = response.json() if success else {}
        models = _models(body) if success else []
        connectivity = {
            "success": success,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "model_count": len(models),
            "checked_at": checked_at,
            "error": None
            if success
            else _redact_error(response.text or "上游返回错误", account),
        }
        update_account_connectivity(account_id, connectivity)
        return {
            "account_id": account_id,
            "account_name": account.get("display_name") or account.get("user_name"),
            **connectivity,
            "models": models,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        connectivity = {
            "success": False,
            "status_code": None,
            "latency_ms": latency_ms,
            "model_count": 0,
            "checked_at": checked_at,
            "error": _redact_error(str(exc) or "模型能力刷新失败", account),
        }
        update_account_connectivity(account_id, connectivity)
        return {
            "account_id": account_id,
            "account_name": account.get("display_name") or account.get("user_name"),
            **connectivity,
            "models": [],
        }
