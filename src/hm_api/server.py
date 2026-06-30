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
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .accounts import (
    activate_account,
    check_account_connectivity,
    delete_account,
    get_active_account,
    list_accounts,
    load_account_state,
    mark_account_used,
    rename_account,
)
from .config import DEVECO_BASE_URL, DEVECO_DEFAULT_AUTH_PORT, USER_AGENT, get_cred_dir
from .login import complete_manual_login, create_login_challenge, is_logged_in, load_session
from .ui import render_ui_html
from .usage import get_usage_summary, record_usage_event


TARGET_BASE = f"{DEVECO_BASE_URL}/sse/codeGenie/maas"


class LoginUrlRequest(BaseModel):
    callback_port: int = Field(DEVECO_DEFAULT_AUTH_PORT, ge=1, le=65535)


class ManualCallbackRequest(BaseModel):
    callback_url: str = Field(..., min_length=1, max_length=4096)
    expected_code: str = Field(..., min_length=1, max_length=128)


class AccountManualCallbackRequest(ManualCallbackRequest):
    display_name: str | None = Field(default=None, max_length=128)
    account_id: str | None = Field(default=None, max_length=128)


class RenameAccountRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=128)


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
        if api_key is None or request.url.path == "/ui":
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
        return JSONResponse(
            {
                "login_url": challenge.login_url,
                "code": challenge.code,
                "callback_port": challenge.port,
            }
        )

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

    @app.get("/ui/api/accounts", response_model=None)
    async def ui_accounts() -> JSONResponse:
        state = load_account_state()
        return JSONResponse(
            {
                "active_account_id": state["active_account_id"],
                "accounts": state["accounts"],
            }
        )

    @app.post("/ui/api/accounts/login-url", response_model=None)
    async def ui_account_login_url(payload: LoginUrlRequest) -> JSONResponse:
        challenge = create_login_challenge(port=payload.callback_port)
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
            account = rename_account(account_id, payload.display_name.strip())
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

    @app.get("/v1/models", response_model=None)
    async def list_models() -> JSONResponse:
        started = time.perf_counter()
        account = _current_account()
        if not account:
            record_usage_event(
                account_id=None,
                endpoint="/v1/models",
                request_body={},
                status_code=401,
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=False,
            )
            raise HTTPException(status_code=401, detail="Not logged in")
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
            raise HTTPException(
                status_code=resp.status_code,
                detail=_redact_sensitive(resp.text, account),
            )
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
            raise HTTPException(status_code=502, detail="Invalid upstream response")
        models: list[dict] = []
        for group in data.get("body", {}).get("inner_models", []):
            for cfg in group.get("model_configs", []):
                model_id = cfg.get("model_id")
                if model_id:
                    models.append({"id": model_id, "object": "model", "owned_by": "deveco"})
        record_usage_event(
            account_id=str(account["account_id"]),
            endpoint="/v1/models",
            request_body={},
            status_code=resp.status_code,
            latency_ms=latency_ms,
            success=True,
        )
        return JSONResponse({"object": "list", "data": models})

    @app.post("/v1/chat/completions", response_model=None)
    async def chat_completions(request: Request) -> StreamingResponse | JSONResponse:
        started = time.perf_counter()
        account = _current_account()
        if not account:
            record_usage_event(
                account_id=None,
                endpoint="/v1/chat/completions",
                request_body={},
                status_code=401,
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=False,
            )
            raise HTTPException(status_code=401, detail="Not logged in")
        token = str(account["access_token"])

        body_bytes = await request.body()
        if not body_bytes:
            body_bytes = b"{}"
        try:
            body_json = json.loads(body_bytes)
        except json.JSONDecodeError:
            record_usage_event(
                account_id=str(account["account_id"]),
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

        upstream_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "lang": "en",
            "Chat-Id": chat_id,
        }
        if session_id:
            upstream_headers["Session-Id"] = session_id

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
            upstream_headers[key] = value

        if stream:
            async def streamer() -> AsyncGenerator[bytes, None]:
                status_code = 502
                success = False
                try:
                    async with client.stream(
                        "POST",
                        url,
                        headers=upstream_headers,
                        content=body_bytes,
                    ) as upstream_resp:
                        status_code = upstream_resp.status_code
                        if upstream_resp.status_code != 200:
                            text = await upstream_resp.aread()
                            error = _redact_sensitive(
                                text.decode("utf-8", errors="replace")
                                or "Upstream error",
                                account,
                            )
                            yield json.dumps({"error": error}).encode()
                            return
                        success = True
                        async for chunk in upstream_resp.aiter_bytes():
                            yield chunk
                finally:
                    record_usage_event(
                        account_id=str(account["account_id"]),
                        endpoint="/v1/chat/completions",
                        request_body=body_json,
                        status_code=status_code,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        success=success,
                    )

            return StreamingResponse(
                streamer(),
                status_code=200,
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )

        upstream_resp = await client.post(url, headers=upstream_headers, content=body_bytes)
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
            return JSONResponse(
                content={
                    "error": _redact_sensitive(
                        upstream_resp.text or "Upstream error",
                        account,
                    )
                },
                status_code=upstream_resp.status_code,
            )

        response_content: dict[str, Any]
        if upstream_resp.headers.get("content-type", "").startswith("application/json"):
            response_content = upstream_resp.json()
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

    return app


def run_server(host: str, port: int, api_key: str | None, proxy: str | None) -> None:
    import uvicorn

    app = build_app(api_key=api_key, proxy=proxy)
    uvicorn.run(app, host=host, port=port)
