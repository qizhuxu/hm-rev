"""DevEco OAuth login flow with local callback server."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import uuid
import webbrowser
from dataclasses import dataclass
from threading import Lock
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .config import (
    DEVECO_APP_ID,
    DEVECO_AUTH_URL,
    DEVECO_BASE_URL,
    DEVECO_DEFAULT_AUTH_PORT,
    DEVECO_FAILED_REDIRECT_URL,
    DEVECO_JWT_TOKEN_CHECK_URL,
    DEVECO_SUCCESS_REDIRECT_URL,
    DEVECO_TEMP_TOKEN_CHECK_URL,
    USER_AGENT,
    get_token_file,
)
from .accounts import get_active_account, save_account_from_user_info
from .crypto import decrypt_value, encrypt_value, load_auth_data, save_auth_data


@dataclass(frozen=True)
class LoginChallenge:
    code: str
    port: int
    login_url: str


@dataclass(frozen=True)
class CallbackParams:
    code: str | None
    temp_token: str | None
    site_id: str | None
    quit: str | None


@dataclass
class UserInfo:
    user_id: str
    user_name: str
    access_token: str
    refresh_token: str
    jwt_token: str
    country_code: str = "CN"
    language: str = "zh_CN"
    is_real_name: bool = False


@dataclass
class LoginResult:
    success: bool
    user_info: UserInfo | None = None
    account_id: str | None = None
    cancelled: bool = False
    unsupported_region: bool = False
    error: str | None = None


class LoginCancelledError(Exception):
    pass


class UnsupportedRegionError(Exception):
    pass


def create_login_challenge(
    port: int = DEVECO_DEFAULT_AUTH_PORT,
    code: str | None = None,
) -> LoginChallenge:
    challenge_code = code or uuid.uuid4().hex.replace("-", "")
    query = urlencode(
        {
            "port": port,
            "appid": DEVECO_APP_ID,
            "code": challenge_code,
        }
    )
    return LoginChallenge(
        code=challenge_code,
        port=port,
        login_url=f"{DEVECO_BASE_URL}/{DEVECO_AUTH_URL}?{query}",
    )


def _parse_request(data: bytes) -> tuple[str, str, bytes]:
    """Parse a simple HTTP request; return (method, path, body)."""
    try:
        header_end = data.index(b"\r\n\r\n")
    except ValueError:
        header_end = data.index(b"\n\n") + 1
    header_lines = data[:header_end].split(b"\r\n")
    if len(header_lines) == 1:
        header_lines = data[:header_end].split(b"\n")

    first = header_lines[0].decode("utf-8", errors="replace")
    parts = first.split()
    method = parts[0] if len(parts) > 0 else "GET"
    path = parts[1] if len(parts) > 1 else "/"

    content_length = 0
    for line in header_lines[1:]:
        if line.lower().startswith(b"content-length:"):
            try:
                content_length = int(line.split(b":", 1)[1].strip())
            except ValueError:
                content_length = 0
            break

    body = data[header_end + 4 : header_end + 4 + content_length]
    return method, path, body


def _parse_callback_params(path: str, body: bytes) -> CallbackParams:
    parsed = urlparse(path)
    params = parse_qs(parsed.query)
    if body:
        body_params = parse_qs(body.decode("utf-8"))
        for k, v in body_params.items():
            params[k] = v

    def _first(key: str) -> str | None:
        values = params.get(key)
        return values[0] if values else None

    return CallbackParams(
        code=_first("code"),
        temp_token=_first("tempToken"),
        site_id=_first("siteId"),
        quit=_first("quit"),
    )


def _parse_callback(path: str, body: bytes) -> dict[str, str | None]:
    params = _parse_callback_params(path, body)
    return {
        "code": params.code,
        "tempToken": params.temp_token,
        "siteId": params.site_id,
        "quit": params.quit,
    }


def parse_callback_input(callback_input: str) -> CallbackParams:
    value = callback_input.strip()
    if not value:
        return CallbackParams(code=None, temp_token=None, site_id=None, quit=None)

    if value.upper().startswith(("GET ", "POST ")):
        _method, path, body = _parse_request(value.encode("utf-8"))
        return _parse_callback_params(path, body)

    first_line = value.splitlines()[0].strip()
    if first_line.startswith("?"):
        path = f"/callback{first_line}"
    elif "?" not in first_line and "=" in first_line:
        path = f"/callback?{first_line.lstrip('?')}"
    else:
        path = first_line
    return _parse_callback_params(path, b"")


def validate_callback_params(
    params: CallbackParams,
    expected_code: str | None,
) -> CallbackParams:
    if not params.code or (expected_code and params.code != expected_code):
        raise LoginCancelledError("Login code mismatch")
    if params.quit in ("true", "access_denied"):
        raise LoginCancelledError(
            "Access denied by user"
            if params.quit == "access_denied"
            else "Login cancelled by user"
        )
    if not params.temp_token or not params.site_id:
        raise LoginCancelledError("Missing tempToken or siteId")
    if params.site_id != "1":
        raise UnsupportedRegionError("Unsupported region")
    return params


def validate_callback_input(
    callback_input: str,
    expected_code: str | None,
) -> CallbackParams:
    return validate_callback_params(parse_callback_input(callback_input), expected_code)


async def _callback_handler(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    expected_code: str,
    future: asyncio.Future,
) -> None:
    try:
        data = await asyncio.wait_for(reader.read(65535), timeout=5.0)
    except asyncio.TimeoutError:
        writer.close()
        await writer.wait_closed()
        return

    method, path, body = _parse_request(data)
    parsed = urlparse(path)

    if parsed.path != "/callback":
        writer.write(b"HTTP/1.1 204 No Content\r\n\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return

    params = _parse_callback_params(path, body)
    code = params.code
    temp_token = params.temp_token
    site_id = params.site_id
    quit = params.quit

    print(
        f"[hm-api login] callback received: code={bool(code)}, "
        f"tempToken_len={len(temp_token) if temp_token else 0}, "
        f"siteId={site_id}, quit={quit}"
    )

    response_status = 302
    location = f"{DEVECO_BASE_URL}/{DEVECO_SUCCESS_REDIRECT_URL}"

    if not code or code != expected_code:
        print("[hm-api login] code mismatch or missing")
        response_status = 400
        location = ""
    elif quit in ("true", "access_denied"):
        if not future.done():
            future.set_exception(
                LoginCancelledError(
                    "Access denied by user"
                    if quit == "access_denied"
                    else "Login cancelled by user"
                )
            )
        location = f"{DEVECO_BASE_URL}/{DEVECO_FAILED_REDIRECT_URL}"
    elif not temp_token or not site_id:
        print("[hm-api login] missing tempToken or siteId")
        if not future.done():
            future.set_exception(LoginCancelledError("Missing tempToken or siteId"))
        location = f"{DEVECO_BASE_URL}/{DEVECO_FAILED_REDIRECT_URL}"
    elif site_id != "1":
        if not future.done():
            future.set_exception(UnsupportedRegionError("Unsupported region"))
        location = f"{DEVECO_BASE_URL}/{DEVECO_FAILED_REDIRECT_URL}"
    else:
        if not future.done():
            future.set_result({"tempToken": temp_token, "siteId": site_id})

    if response_status == 400:
        writer.write(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
    else:
        writer.write(
            f"HTTP/1.1 {response_status} Found\r\n"
            f"Location: {location}\r\n"
            "Content-Length: 0\r\n\r\n".encode("utf-8")
        )
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def _open_browser(url: str) -> bool:
    try:
        return webbrowser.open(url)
    except Exception:
        return False


def _build_client(proxy: str | None = None, timeout: float = 30.0) -> httpx.AsyncClient:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-CN",
    }
    mounts = {}
    if proxy:
        mounts = {
            "http://": httpx.AsyncHTTPTransport(proxy=proxy),
            "https://": httpx.AsyncHTTPTransport(proxy=proxy),
        }
    return httpx.AsyncClient(
        headers=headers,
        timeout=httpx.Timeout(timeout),
        follow_redirects=True,
        mounts=mounts,
    )


def _parse_jwt(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    payload = parts[1]
    payload = payload.replace("-", "+").replace("_", "/")
    pad = (4 - len(payload) % 4) % 4
    payload += "=" * pad
    decoded = base64.b64decode(payload).decode("utf-8")
    return json.loads(decoded)


def _save_token(jwt_token: str) -> None:
    token_file = get_token_file()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    blob = encrypt_value(jwt_token)
    with open(token_file, "w", encoding="utf-8") as f:
        json.dump(blob, f)
    os.chmod(token_file, 0o600)


def _load_token() -> str | None:
    token_file = get_token_file()
    if not token_file.exists():
        return None
    with open(token_file, "r", encoding="utf-8") as f:
        blob = json.load(f)
    return decrypt_value(blob)


def _save_access_token(access_token: str, refresh_token: str) -> None:
    data = load_auth_data()
    data["deveco"] = {
        "type": "oauth",
        "access": access_token,
        "refresh": refresh_token,
    }
    save_auth_data(data)


def save_user_info(
    user_info: UserInfo,
    *,
    display_name: str | None = None,
    account_id: str | None = None,
) -> str:
    return save_account_from_user_info(
        user_info,
        display_name=display_name,
        account_id=account_id,
        activate=True,
    )


async def exchange_temp_token(
    temp_token: str,
    proxy: str | None = None,
) -> UserInfo:
    actual_temp_token = temp_token.split("&")[0]

    async with _build_client(proxy, timeout=30.0) as client:
        jwt_resp = await client.get(
            f"{DEVECO_BASE_URL}/{DEVECO_TEMP_TOKEN_CHECK_URL}",
            params={
                "tempToken": actual_temp_token,
                "site": "CN",
                "version": "1.0.0",
                "appid": DEVECO_APP_ID,
            },
        )
        if jwt_resp.status_code != 200:
            raise RuntimeError(f"Failed to get JWT: {jwt_resp.status_code}")
        jwt_token = jwt_resp.text.strip()
        if len(jwt_token.split(".")) != 3:
            raise ValueError("Invalid JWT format")

        info_resp = await client.get(
            f"{DEVECO_BASE_URL}/{DEVECO_JWT_TOKEN_CHECK_URL}",
            headers={"refresh": "false", "jwtToken": jwt_token},
        )
        if info_resp.status_code != 200:
            raise RuntimeError(f"Failed to check JWT: {info_resp.status_code}")
        info_data = info_resp.json()
        if not info_data.get("status") or not info_data.get("userInfo"):
            raise ValueError("Invalid JWT userInfo")

        user_info_raw = info_data["userInfo"]
        payload = _parse_jwt(jwt_token)
        return UserInfo(
            user_id=payload.get("userId", ""),
            user_name=payload.get("userName", ""),
            access_token=user_info_raw.get("accessToken", ""),
            refresh_token=user_info_raw.get("refreshToken", ""),
            jwt_token=jwt_token,
            country_code="CN",
            language="zh_CN",
            is_real_name=user_info_raw.get("realName") == "true",
        )


async def complete_manual_login(
    callback_input: str,
    expected_code: str | None,
    proxy: str | None = None,
    *,
    display_name: str | None = None,
    account_id: str | None = None,
) -> LoginResult:
    try:
        params = validate_callback_input(callback_input, expected_code)
        assert params.temp_token is not None
        user_info = await exchange_temp_token(params.temp_token, proxy=proxy)
        saved_account_id = save_user_info(
            user_info,
            display_name=display_name,
            account_id=account_id,
        )
        return LoginResult(
            success=True,
            user_info=user_info,
            account_id=saved_account_id,
        )
    except LoginCancelledError as exc:
        return LoginResult(success=False, cancelled=True, error=str(exc))
    except UnsupportedRegionError:
        return LoginResult(
            success=False,
            unsupported_region=True,
            error="Only China site accounts are currently supported",
        )
    except Exception:
        return LoginResult(success=False, error="Login failed")


async def _start_callback_server(
    port: int, expected_code: str
) -> tuple[asyncio.Server, asyncio.Future]:
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _callback_handler(reader, writer, expected_code, future)

    server = await asyncio.start_server(handler, "127.0.0.1", port)
    return server, future


_pending_challenges: dict[str, dict] = {}
_pending_challenges_lock = Lock()
PENDING_CHALLENGE_TTL = 1800  # 30 minutes

def register_challenge(challenge: LoginChallenge) -> None:
    """Register a pending login challenge for the hosted /callback route."""
    with _pending_challenges_lock:
        _clean_pending()
        _pending_challenges[challenge.code] = {
            "challenge": challenge,
            "created_at": time.time(),
        }

def get_challenge(code: str) -> LoginChallenge | None:
    """Look up a pending challenge by code."""
    with _pending_challenges_lock:
        _clean_pending()
        entry = _pending_challenges.get(code)
        if entry:
            return entry["challenge"]
        return None

def remove_challenge(code: str) -> None:
    """Remove a pending challenge after successful/failed login."""
    with _pending_challenges_lock:
        _pending_challenges.pop(code, None)

def _clean_pending() -> None:
    """Evict challenges older than TTL."""
    now = time.time()
    expired = [
        k for k, v in _pending_challenges.items()
        if now - v["created_at"] > PENDING_CHALLENGE_TTL
    ]
    for k in expired:
        del _pending_challenges[k]


async def login(
    proxy: str | None = None,
    *,
    no_browser: bool = False,
    timeout: float = 600.0,
) -> LoginResult:
    client_secret = uuid.uuid4().hex.replace("-", "")
    ports = [DEVECO_DEFAULT_AUTH_PORT, 34567, 34568, 34569, 34570]

    server: asyncio.Server | None = None
    future: asyncio.Future | None = None

    for port in ports:
        try:
            server, future = await _start_callback_server(port, client_secret)
            break
        except OSError:
            continue
    else:
        return LoginResult(success=False, error="All local ports are in use")

    try:
        login_url = create_login_challenge(port=port, code=client_secret).login_url
        if no_browser:
            print(f"Please open this URL in your browser to login:\n{login_url}")
        else:
            opened = await _open_browser(login_url)
            if not opened:
                print(f"Failed to open browser automatically. Please open:\n{login_url}")

        result = await asyncio.wait_for(future, timeout=timeout)
        temp_token = result["tempToken"]
        user_info = await exchange_temp_token(temp_token, proxy=proxy)
        saved_account_id = save_user_info(user_info)
        return LoginResult(
            success=True,
            user_info=user_info,
            account_id=saved_account_id,
        )
    except asyncio.TimeoutError:
        return LoginResult(success=False, error="Login timeout")
    except LoginCancelledError:
        return LoginResult(success=False, cancelled=True, error="Login cancelled")
    except UnsupportedRegionError:
        return LoginResult(
            success=False,
            unsupported_region=True,
            error="Only China site accounts are currently supported",
        )
    except Exception as exc:
        return LoginResult(success=False, error=str(exc))
    finally:
        if server:
            server.close()
            await server.wait_closed()


def is_logged_in() -> bool:
    try:
        return get_active_account() is not None
    except Exception:
        return _load_token() is not None


async def load_session() -> dict | None:
    try:
        active = get_active_account()
    except Exception:
        active = None
    if active:
        return {
            "account_id": active.get("account_id", ""),
            "display_name": active.get("display_name", ""),
            "user_id": active.get("user_id", ""),
            "user_name": active.get("user_name", ""),
            "access_token": active.get("access_token", ""),
            "refresh_token": active.get("refresh_token", ""),
            "jwt_token": active.get("jwt_token", ""),
        }

    token = _load_token()
    if not token:
        return None
    try:
        payload = _parse_jwt(token)
        data = load_auth_data()
        deveco = data.get("deveco", {})
        return {
            "user_id": payload.get("userId", ""),
            "user_name": payload.get("userName", ""),
            "access_token": deveco.get("access", ""),
            "refresh_token": deveco.get("refresh", ""),
            "jwt_token": token,
        }
    except Exception:
        return None
