"""FastAPI OpenAI-compatible proxy server for DevEco Code."""

from __future__ import annotations

import json
import secrets
import time
import uuid
import re
from typing import Any
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from .accounts import (
    activate_account,
    check_account_connectivity,
    delete_account,
    fetch_account_models,
    get_active_account,
    get_account_strategy,
    list_accounts,
    load_account_state,
    mark_account_used,
    rename_account,
    select_account_candidates,
    set_account_strategy,
    update_account_profile,
)
from .config import DEVECO_BASE_URL, DEVECO_DEFAULT_AUTH_PORT, USER_AGENT, get_cred_dir
from .login import (
    _parse_callback_params,
    complete_manual_login,
    create_login_challenge,
    exchange_temp_token,
    get_challenge,
    is_logged_in,
    load_session,
    register_challenge,
    remove_challenge,
    save_user_info,
)
from .ui import render_ui_html
from .usage import get_usage_events, get_usage_summary, record_usage_event


TARGET_BASE = f"{DEVECO_BASE_URL}/sse/codeGenie/maas"


class LoginUrlRequest(BaseModel):
    callback_port: int = Field(DEVECO_DEFAULT_AUTH_PORT, ge=1, le=65535)


class ManualCallbackRequest(BaseModel):
    callback_url: str = Field(..., min_length=1, max_length=4096)
    expected_code: str = Field(..., min_length=1, max_length=128)


class AccountManualCallbackRequest(ManualCallbackRequest):
    display_name: str | None = Field(default=None, max_length=128)
    account_id: str | None = Field(default=None, max_length=128)
    tags: list[str] = Field(default_factory=list, max_length=12)
    note: str | None = Field(default=None, max_length=500)


class RenameAccountRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    tags: list[str] | None = Field(default=None, max_length=12)
    note: str | None = Field(default=None, max_length=500)


class AccountStrategyRequest(BaseModel):
    strategy: str = Field(..., min_length=1, max_length=32)


class ModelRefreshRequest(BaseModel):
    account_id: str | None = Field(default=None, max_length=128)


def _current_account() -> dict[str, Any] | None:
    account = get_active_account()
    if account and account.get("account_id"):
        mark_account_used(str(account["account_id"]))
    return account


def _current_access_token() -> str | None:
    account = _current_account()
    if not account:
        return None
    access = account.get("access_token")
    return str(access) if access else None


def _account_candidates() -> tuple[str, list[dict[str, Any]]]:
    strategy = get_account_strategy()
    accounts = select_account_candidates(strategy)
    return strategy, accounts


def _can_try_next(strategy: str, index: int, accounts: list[dict[str, Any]]) -> bool:
    return strategy == "failover" and index < len(accounts) - 1


def _model_list(data: dict[str, Any]) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    for group in data.get("body", {}).get("inner_models", []):
        for cfg in group.get("model_configs", []):
            model_id = cfg.get("model_id")
            if model_id:
                models.append({"id": str(model_id), "object": "model", "owned_by": "deveco"})
    return models


def _redact_sensitive(message: str, account: dict[str, Any] | None = None) -> str:
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [redacted]", message)
    redacted = re.sub(r"tempToken=([^&\s]+)", "tempToken=[redacted]", redacted)
    if account:
        for key in ("access_token", "refresh_token", "jwt_token"):
            value = account.get(key)
            if value:
                redacted = redacted.replace(str(value), "[redacted]")
    return redacted[:500] or "Upstream error"


def _usage_payload(response_data: Any) -> dict[str, Any] | None:
    if isinstance(response_data, dict) and isinstance(response_data.get("usage"), dict):
        return response_data["usage"]
    return None


def _overview_payload(api_key: str | None) -> dict[str, Any]:
    state = load_account_state()
    accounts = state["accounts"]
    active_account = next(
        (account for account in accounts if account.get("is_active")),
        None,
    )
    cred_dir = get_cred_dir()
    credential_files = {
        "accounts_json": (cred_dir / "accounts.json").exists(),
        "usage_jsonl": (cred_dir / "usage.jsonl").exists(),
        "auth_json": (cred_dir / "auth.json").exists(),
        "token_enc": (cred_dir / "token.enc").exists(),
        "kek": (cred_dir / ".kek").exists(),
    }
    return {
        "logged_in": active_account is not None,
        "auth_enabled": api_key is not None,
        "credential_dir": {
            "path": str(cred_dir),
            "exists": cred_dir.exists(),
        },
        "credential_files": credential_files,
        "account_strategy": get_account_strategy(),
        "active_account": active_account,
        "active_account_id": state["active_account_id"],
        "accounts": accounts,
        "usage": get_usage_summary(),
    }


def _public_session(session: dict | None) -> dict[str, str] | None:
    if not session:
        return None
    return {
        "user_id": str(session.get("user_id") or ""),
        "user_name": str(session.get("user_name") or ""),
    }


def build_app(api_key: str | None = None, proxy: str | None = None) -> FastAPI:
    app = FastAPI(title="hm-api", version="0.1.0")
    mounts: dict[str, httpx.AsyncHTTPTransport] | None = None
    if proxy:
        transport = httpx.AsyncHTTPTransport(proxy=proxy)
        mounts = {"http://": transport, "https://": transport}

    client = httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN"},
        timeout=httpx.Timeout(600.0),
        follow_redirects=True,
        mounts=mounts,
    )

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if api_key is None or request.url.path in ("/ui", "/callback"):
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or not secrets.compare_digest(
            auth[7:], api_key
        ):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)

    @app.get("/ui", response_model=None)
    async def ui() -> HTMLResponse:
        return HTMLResponse(render_ui_html())

    @app.get("/ui/api/status", response_model=None)
    async def ui_status() -> JSONResponse:
        if not is_logged_in():
            return JSONResponse({"logged_in": False, "user": None})
        session = await load_session()
        return JSONResponse(
            {
                "logged_in": bool(session),
                "user": _public_session(session),
            }
        )

    @app.post("/ui/api/login-url", response_model=None)
    async def ui_login_url(payload: LoginUrlRequest) -> JSONResponse:
        challenge = create_login_challenge(port=payload.callback_port)
        register_challenge(challenge)
        return JSONResponse(
            {
                "login_url": challenge.login_url,
                "code": challenge.code,
                "callback_port": challenge.port,
            }
        )

    @app.post("/callback")
    async def handle_callback(request: Request) -> RedirectResponse:
        """Receive DevEco OAuth POST callback and complete login.

        DevEco redirects the user's browser to POST the callback (form-urlencoded)
        to the URL we specified in the login URL. This endpoint captures it,
        exchanges the tempToken for real credentials, saves the account, then
        redirects the browser back to the management console.
        """
        body = await request.body()
        parsed = _parse_callback_params("/callback", body)

        code = parsed.code
        temp_token = parsed.temp_token
        site_id = parsed.site_id
        quit_val = parsed.quit

        # Look up the pending challenge
        challenge = get_challenge(code) if code else None

        if not challenge:
            return RedirectResponse(url="/ui?login_error=expired", status_code=303)
        # challenge is set → code is non-None
        assert code is not None

        if quit_val in ("true", "access_denied"):
            remove_challenge(code)
            return RedirectResponse(url="/ui?login_error=cancelled", status_code=303)

        if not temp_token or not site_id:
            remove_challenge(code)
            return RedirectResponse(url="/ui?login_error=missing", status_code=303)

        if site_id != "1":
            remove_challenge(code)
            return RedirectResponse(url="/ui?login_error=region", status_code=303)

        try:
            user_info = await exchange_temp_token(temp_token, proxy=proxy)
            save_user_info(user_info)
            remove_challenge(code)
            return RedirectResponse(url="/ui?login_success=1", status_code=303)
        except Exception:
            remove_challenge(code)
            return RedirectResponse(url="/ui?login_error=failed", status_code=303)

    @app.post("/ui/api/manual-callback", response_model=None)
    async def ui_manual_callback(payload: ManualCallbackRequest) -> JSONResponse:
        result = await complete_manual_login(
            payload.callback_url,
            expected_code=payload.expected_code,
            proxy=proxy,
        )
        if not result.success:
            return JSONResponse(
                {
                    "success": False,
                    "error": result.error or "Login failed",
                },
                status_code=400,
            )
        return JSONResponse(
            {
                "success": True,
                "user": _public_session(
                    {
                        "user_id": result.user_info.user_id if result.user_info else "",
                        "user_name": result.user_info.user_name if result.user_info else "",
                    }
                ),
            }
        )

    @app.get("/ui/api/overview", response_model=None)
    async def ui_overview() -> JSONResponse:
        return JSONResponse(_overview_payload(api_key))

    @app.get("/ui/api/account-strategy", response_model=None)
    async def ui_account_strategy() -> JSONResponse:
        return JSONResponse({"strategy": get_account_strategy()})

    @app.put("/ui/api/account-strategy", response_model=None)
    async def ui_account_strategy_update(payload: AccountStrategyRequest) -> JSONResponse:
        strategy = set_account_strategy(payload.strategy)
        return JSONResponse({"success": True, "strategy": strategy})

    @app.get("/ui/api/accounts", response_model=None)
    async def ui_accounts() -> JSONResponse:
        state = load_account_state()
        return JSONResponse(
            {
                "active_account_id": state["active_account_id"],
                "accounts": state["accounts"],
            }
        )

    @app.get("/ui/api/models", response_model=None)
    async def ui_models() -> JSONResponse:
        accounts = list_accounts()
        return JSONResponse(
            {
                "accounts": [
                    {
                        "account_id": account.get("account_id"),
                        "account_name": account.get("display_name")
                        or account.get("user_name")
                        or account.get("account_id"),
                        "connectivity": account.get("connectivity"),
                        "models": [],
                    }
                    for account in accounts
                ]
            }
        )

    @app.post("/ui/api/models/refresh", response_model=None)
    async def ui_models_refresh(payload: ModelRefreshRequest) -> JSONResponse:
        target_accounts = (
            [account for account in list_accounts() if account.get("account_id") == payload.account_id]
            if payload.account_id
            else list_accounts()
        )
        if payload.account_id and not target_accounts:
            raise HTTPException(status_code=404, detail="Account not found")
        results: list[dict[str, Any]] = []
        for account in target_accounts:
            account_id = str(account.get("account_id") or "")
            if not account_id:
                continue
            results.append(await fetch_account_models(account_id, proxy=proxy))
        return JSONResponse({"success": True, "results": results})

    @app.post("/ui/api/accounts/login-url", response_model=None)
    async def ui_account_login_url(payload: LoginUrlRequest) -> JSONResponse:
        challenge = create_login_challenge(port=payload.callback_port)
        register_challenge(challenge)
        return JSONResponse(
            {
                "login_url": challenge.login_url,
                "code": challenge.code,
                "callback_port": challenge.port,
            }
        )

    @app.post("/ui/api/accounts/manual-callback", response_model=None)
    async def ui_account_manual_callback(
        payload: AccountManualCallbackRequest,
    ) -> JSONResponse:
        display_name = payload.display_name.strip() if payload.display_name else None
        account_id = payload.account_id.strip() if payload.account_id else None
        result = await complete_manual_login(
            payload.callback_url,
            expected_code=payload.expected_code,
            proxy=proxy,
            display_name=display_name or None,
            account_id=account_id or None,
        )
        if not result.success:
            return JSONResponse(
                {
                    "success": False,
                    "error": result.error or "登录失败",
                },
                status_code=400,
            )
        if result.account_id and (payload.tags or payload.note):
            update_account_profile(
                result.account_id,
                tags=payload.tags,
                note=payload.note,
            )
        return JSONResponse(
            {
                "success": True,
                "account_id": result.account_id,
                "user": _public_session(
                    {
                        "user_id": result.user_info.user_id if result.user_info else "",
                        "user_name": result.user_info.user_name if result.user_info else "",
                    }
                ),
            }
        )

    @app.post("/ui/api/accounts/{account_id}/activate", response_model=None)
    async def ui_account_activate(account_id: str) -> JSONResponse:
        try:
            account = activate_account(account_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Account not found")
        return JSONResponse({"success": True, "account": account})

    @app.patch("/ui/api/accounts/{account_id}", response_model=None)
    async def ui_account_rename(
        account_id: str,
        payload: RenameAccountRequest,
    ) -> JSONResponse:
        try:
            if payload.tags is None and payload.note is None and payload.display_name:
                account = rename_account(account_id, payload.display_name.strip())
            else:
                account = update_account_profile(
                    account_id,
                    display_name=payload.display_name,
                    tags=payload.tags,
                    note=payload.note,
                )
        except KeyError:
            raise HTTPException(status_code=404, detail="Account not found")
        return JSONResponse({"success": True, "account": account})

    @app.delete("/ui/api/accounts/{account_id}", response_model=None)
    async def ui_account_delete(account_id: str) -> JSONResponse:
        try:
            delete_account(account_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Account not found")
        return JSONResponse({"success": True})

    @app.post("/ui/api/accounts/{account_id}/check", response_model=None)
    async def ui_account_check(account_id: str) -> JSONResponse:
        try:
            result = await check_account_connectivity(account_id, proxy=proxy)
        except KeyError:
            raise HTTPException(status_code=404, detail="Account not found")
        return JSONResponse({"success": True, "result": result})

    @app.post("/ui/api/accounts/check-all", response_model=None)
    async def ui_account_check_all() -> JSONResponse:
        results: list[dict[str, Any]] = []
        for account in list_accounts():
            account_id = str(account.get("account_id") or "")
            if not account_id:
                continue
            try:
                result = await check_account_connectivity(account_id, proxy=proxy)
            except KeyError:
                continue
            results.append({"account_id": account_id, "result": result})
        return JSONResponse({"success": True, "results": results})

    @app.get("/ui/api/usage", response_model=None)
    async def ui_usage() -> JSONResponse:
        return JSONResponse(get_usage_summary())

    @app.get("/ui/api/usage/events", response_model=None)
    async def ui_usage_events(
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> JSONResponse:
        return JSONResponse(get_usage_events(limit=limit, offset=offset))

    @app.get("/v1/models", response_model=None)
    async def list_models() -> JSONResponse:
        started = time.perf_counter()
        strategy, accounts = _account_candidates()
        if not accounts:
            record_usage_event(
                account_id=None,
                endpoint="/v1/models",
                request_body={},
                status_code=401,
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=False,
            )
            raise HTTPException(status_code=401, detail="Not logged in")
        last_error: HTTPException | None = None
        for index, account in enumerate(accounts):
            mark_account_used(str(account["account_id"]))
            token = str(account["access_token"])
            resp = await client.get(
                f"{DEVECO_BASE_URL}/codeGenie/modelConfig?localVersion=0&pluginVersion=CLI.0.1.0",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            if resp.status_code != 200:
                record_usage_event(
                    account_id=str(account["account_id"]),
                    endpoint="/v1/models",
                    request_body={},
                    status_code=resp.status_code,
                    latency_ms=latency_ms,
                    success=False,
                )
                last_error = HTTPException(
                    status_code=resp.status_code,
                    detail=_redact_sensitive(resp.text, account),
                )
                if _can_try_next(strategy, index, accounts):
                    continue
                raise last_error
            try:
                data = resp.json()
            except ValueError:
                record_usage_event(
                    account_id=str(account["account_id"]),
                    endpoint="/v1/models",
                    request_body={},
                    status_code=502,
                    latency_ms=latency_ms,
                    success=False,
                )
                last_error = HTTPException(
                    status_code=502,
                    detail="Invalid upstream response",
                )
                if _can_try_next(strategy, index, accounts):
                    continue
                raise last_error
            models = _model_list(data)
            record_usage_event(
                account_id=str(account["account_id"]),
                endpoint="/v1/models",
                request_body={},
                status_code=resp.status_code,
                latency_ms=latency_ms,
                success=True,
            )
            return JSONResponse({"object": "list", "data": models})
        assert last_error is not None
        raise last_error

    @app.post("/v1/chat/completions", response_model=None)
    async def chat_completions(request: Request) -> StreamingResponse | JSONResponse:
        started = time.perf_counter()
        strategy, accounts = _account_candidates()
        if not accounts:
            record_usage_event(
                account_id=None,
                endpoint="/v1/chat/completions",
                request_body={},
                status_code=401,
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=False,
            )
            raise HTTPException(status_code=401, detail="Not logged in")

        body_bytes = await request.body()
        if not body_bytes:
            body_bytes = b"{}"
        try:
            body_json = json.loads(body_bytes)
        except json.JSONDecodeError:
            record_usage_event(
                account_id=str(accounts[0]["account_id"]),
                endpoint="/v1/chat/completions",
                request_body={},
                status_code=400,
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=False,
            )
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        stream = bool(body_json.get("stream"))
        target_path = "v2/chat/completions"
        if not stream:
            target_path = "v2/no-stream/chat/completions"
        url = f"{TARGET_BASE}/{target_path}"

        session_id = request.headers.get("x-deveco-session") or request.headers.get("x-session-affinity")
        chat_id = uuid.uuid4().hex.replace("-", "")

        base_headers = {
            "Content-Type": "application/json",
            "lang": "en",
            "Chat-Id": chat_id,
        }
        if session_id:
            base_headers["Session-Id"] = session_id

        for key, value in request.headers.items():
            lower = key.lower()
            if lower in {
                "host",
                "authorization",
                "content-length",
                "content-type",
                "connection",
                "accept-encoding",
            }:
                continue
            base_headers[key] = value

        def headers_for(account: dict[str, Any]) -> dict[str, str]:
            return {
                **base_headers,
                "Authorization": f"Bearer {account['access_token']}",
            }

        if stream:
            async def streamer() -> AsyncGenerator[bytes, None]:
                last_error = "Upstream error"
                for index, account in enumerate(accounts):
                    mark_account_used(str(account["account_id"]))
                    status_code = 502
                    success = False
                    try:
                        async with client.stream(
                            "POST",
                            url,
                            headers=headers_for(account),
                            content=body_bytes,
                        ) as upstream_resp:
                            status_code = upstream_resp.status_code
                            if upstream_resp.status_code != 200:
                                text = await upstream_resp.aread()
                                last_error = _redact_sensitive(
                                    text.decode("utf-8", errors="replace")
                                    or "Upstream error",
                                    account,
                                )
                            else:
                                success = True
                                async for chunk in upstream_resp.aiter_bytes():
                                    yield chunk
                                return
                    finally:
                        record_usage_event(
                            account_id=str(account["account_id"]),
                            endpoint="/v1/chat/completions",
                            request_body=body_json,
                            status_code=status_code,
                            latency_ms=int((time.perf_counter() - started) * 1000),
                            success=success,
                        )
                    if _can_try_next(strategy, index, accounts):
                        continue
                    yield json.dumps({"error": last_error}).encode()
                    return

            return StreamingResponse(
                streamer(),
                status_code=200,
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )

        last_error_response: JSONResponse | None = None
        for index, account in enumerate(accounts):
            mark_account_used(str(account["account_id"]))
            upstream_resp = await client.post(
                url,
                headers=headers_for(account),
                content=body_bytes,
            )
            latency_ms = int((time.perf_counter() - started) * 1000)

            if upstream_resp.status_code != 200:
                record_usage_event(
                    account_id=str(account["account_id"]),
                    endpoint="/v1/chat/completions",
                    request_body=body_json,
                    status_code=upstream_resp.status_code,
                    latency_ms=latency_ms,
                    success=False,
                )
                last_error_response = JSONResponse(
                    content={
                        "error": _redact_sensitive(
                            upstream_resp.text or "Upstream error",
                            account,
                        )
                    },
                    status_code=upstream_resp.status_code,
                )
                if _can_try_next(strategy, index, accounts):
                    continue
                return last_error_response

            response_content: dict[str, Any]
            if upstream_resp.headers.get("content-type", "").startswith("application/json"):
                try:
                    response_content = upstream_resp.json()
                except ValueError:
                    record_usage_event(
                        account_id=str(account["account_id"]),
                        endpoint="/v1/chat/completions",
                        request_body=body_json,
                        status_code=502,
                        latency_ms=latency_ms,
                        success=False,
                    )
                    last_error_response = JSONResponse(
                        content={"error": "Invalid upstream response"},
                        status_code=502,
                    )
                    if _can_try_next(strategy, index, accounts):
                        continue
                    return last_error_response
            else:
                response_content = {"data": upstream_resp.text}
            record_usage_event(
                account_id=str(account["account_id"]),
                endpoint="/v1/chat/completions",
                request_body=body_json,
                status_code=upstream_resp.status_code,
                latency_ms=latency_ms,
                success=True,
                usage=_usage_payload(response_content),
            )
            return JSONResponse(
                content=response_content,
                status_code=upstream_resp.status_code,
            )
        assert last_error_response is not None
        return last_error_response

    return app


def run_server(host: str, port: int, api_key: str | None, proxy: str | None) -> None:
    import uvicorn

    app = build_app(api_key=api_key, proxy=proxy)
    uvicorn.run(app, host=host, port=port)
