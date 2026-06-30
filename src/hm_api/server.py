"""FastAPI OpenAI-compatible proxy server for DevEco Code."""

from __future__ import annotations

import json
import secrets
import uuid
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .config import DEVECO_BASE_URL, DEVECO_DEFAULT_AUTH_PORT, USER_AGENT
from .crypto import load_auth_data
from .login import complete_manual_login, create_login_challenge, is_logged_in, load_session


TARGET_BASE = f"{DEVECO_BASE_URL}/sse/codeGenie/maas"


class LoginUrlRequest(BaseModel):
    callback_port: int = Field(DEVECO_DEFAULT_AUTH_PORT, ge=1, le=65535)


class ManualCallbackRequest(BaseModel):
    callback_url: str = Field(..., min_length=1, max_length=4096)
    expected_code: str = Field(..., min_length=1, max_length=128)


def _current_access_token() -> str | None:
    data = load_auth_data()
    deveco = data.get("deveco", {})
    access = deveco.get("access")
    return access if access else None


def _public_session(session: dict | None) -> dict[str, str] | None:
    if not session:
        return None
    return {
        "user_id": str(session.get("user_id") or ""),
        "user_name": str(session.get("user_name") or ""),
    }


def _ui_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>hm-api</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f7f8fa;
      color: #20242a;
    }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; background: #f7f8fa; }
    main { width: min(980px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 48px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
    h1 { font-size: 28px; line-height: 1.2; margin: 0; font-weight: 700; }
    h2 { font-size: 16px; margin: 0 0 14px; }
    button, input, textarea { font: inherit; }
    button {
      border: 1px solid #1d4ed8;
      background: #1d4ed8;
      color: white;
      border-radius: 6px;
      min-height: 40px;
      padding: 0 14px;
      cursor: pointer;
      font-weight: 600;
    }
    button.secondary { background: white; color: #1d4ed8; }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .status {
      display: inline-flex;
      align-items: center;
      min-height: 32px;
      border-radius: 999px;
      padding: 0 12px;
      border: 1px solid #d7dce3;
      background: white;
      font-size: 14px;
      white-space: nowrap;
    }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; align-items: start; }
    section {
      border: 1px solid #dfe3ea;
      background: white;
      border-radius: 8px;
      padding: 18px;
    }
    label { display: block; font-size: 13px; font-weight: 650; margin: 12px 0 6px; }
    input, textarea {
      width: 100%;
      border: 1px solid #cfd6df;
      border-radius: 6px;
      padding: 10px 11px;
      color: #20242a;
      background: white;
    }
    textarea { min-height: 150px; resize: vertical; }
    .row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
    .result {
      margin-top: 12px;
      border: 1px solid #dfe3ea;
      background: #fafbfc;
      border-radius: 6px;
      padding: 10px;
      word-break: break-word;
      min-height: 42px;
      font-size: 14px;
    }
    .message { margin-top: 14px; min-height: 24px; font-size: 14px; font-weight: 650; }
    .ok { color: #047857; }
    .err { color: #b91c1c; }
    a { color: #1d4ed8; }
    @media (max-width: 760px) {
      main { width: min(100% - 20px, 980px); padding-top: 18px; }
      header { align-items: flex-start; flex-direction: column; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>hm-api</h1>
      <div id="status" class="status">Checking</div>
    </header>
    <div class="grid">
      <section>
        <h2>Login URL</h2>
        <label for="callbackPort">Callback port</label>
        <input id="callbackPort" type="number" min="1" max="65535" value="10101">
        <div class="row">
          <button id="createLogin" type="button">Create URL</button>
          <button id="copyUrl" class="secondary" type="button" disabled>Copy</button>
        </div>
        <div id="loginUrl" class="result"></div>
      </section>
      <section>
        <h2>Manual Callback</h2>
        <label for="expectedCode">Code</label>
        <input id="expectedCode" autocomplete="off">
        <label for="callbackUrl">Callback URL or query</label>
        <textarea id="callbackUrl" spellcheck="false"></textarea>
        <div class="row">
          <button id="completeLogin" type="button">Save Login</button>
        </div>
        <div id="message" class="message"></div>
      </section>
    </div>
  </main>
  <script>
    const statusEl = document.querySelector("#status");
    const messageEl = document.querySelector("#message");
    const loginUrlEl = document.querySelector("#loginUrl");
    const createButton = document.querySelector("#createLogin");
    const copyButton = document.querySelector("#copyUrl");
    const completeButton = document.querySelector("#completeLogin");
    const callbackPort = document.querySelector("#callbackPort");
    const expectedCode = document.querySelector("#expectedCode");
    const callbackUrl = document.querySelector("#callbackUrl");
    let currentLoginUrl = "";

    function setMessage(text, ok) {
      messageEl.textContent = text;
      messageEl.className = ok ? "message ok" : "message err";
    }

    async function api(path, options = {}) {
      const headers = Object.assign({"Content-Type": "application/json"}, options.headers || {});
      const token = window.sessionStorage.getItem("hmApiBearer") || "";
      if (token) headers.Authorization = `Bearer ${token}`;
      const response = await fetch(path, Object.assign({}, options, {headers}));
      if (response.status === 401) {
        const tokenInput = window.prompt("API key");
        if (tokenInput) {
          window.sessionStorage.setItem("hmApiBearer", tokenInput);
          headers.Authorization = `Bearer ${tokenInput}`;
          return fetch(path, Object.assign({}, options, {headers}));
        }
      }
      return response;
    }

    async function loadStatus() {
      const response = await api("/ui/api/status", {method: "GET", headers: {}});
      if (!response.ok) {
        statusEl.textContent = "Unauthorized";
        return;
      }
      const data = await response.json();
      statusEl.textContent = data.logged_in
        ? `Logged in${data.user && data.user.user_name ? `: ${data.user.user_name}` : ""}`
        : "Not logged in";
    }

    createButton.addEventListener("click", async () => {
      createButton.disabled = true;
      try {
        const response = await api("/ui/api/login-url", {
          method: "POST",
          body: JSON.stringify({callback_port: Number(callbackPort.value)})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || data.error || "Failed to create URL");
        currentLoginUrl = data.login_url;
        expectedCode.value = data.code;
        loginUrlEl.innerHTML = `<a href="${data.login_url}" target="_blank" rel="noreferrer">Open DevEco login</a><br>${data.login_url}`;
        copyButton.disabled = false;
        setMessage("Login URL ready.", true);
      } catch (error) {
        setMessage(error.message, false);
      } finally {
        createButton.disabled = false;
      }
    });

    copyButton.addEventListener("click", async () => {
      if (!currentLoginUrl) return;
      await navigator.clipboard.writeText(currentLoginUrl);
      setMessage("Login URL copied.", true);
    });

    completeButton.addEventListener("click", async () => {
      completeButton.disabled = true;
      try {
        const response = await api("/ui/api/manual-callback", {
          method: "POST",
          body: JSON.stringify({
            callback_url: callbackUrl.value,
            expected_code: expectedCode.value
          })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || data.detail || "Login failed");
        setMessage("Login saved.", true);
        await loadStatus();
      } catch (error) {
        setMessage(error.message, false);
      } finally {
        completeButton.disabled = false;
      }
    });

    loadStatus();
  </script>
</body>
</html>"""


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
        return HTMLResponse(_ui_html())

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

    @app.get("/v1/models", response_model=None)
    async def list_models() -> JSONResponse:
        token = _current_access_token()
        if not token:
            raise HTTPException(status_code=401, detail="Not logged in")
        resp = await client.get(
            f"{DEVECO_BASE_URL}/codeGenie/modelConfig?localVersion=0&pluginVersion=CLI.0.1.0",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        data = resp.json()
        models: list[dict] = []
        for group in data.get("body", {}).get("inner_models", []):
            for cfg in group.get("model_configs", []):
                model_id = cfg.get("model_id")
                if model_id:
                    models.append({"id": model_id, "object": "model", "owned_by": "deveco"})
        return JSONResponse({"object": "list", "data": models})

    @app.post("/v1/chat/completions", response_model=None)
    async def chat_completions(request: Request) -> StreamingResponse | JSONResponse:
        token = _current_access_token()
        if not token:
            raise HTTPException(status_code=401, detail="Not logged in")

        body_bytes = await request.body()
        if not body_bytes:
            body_bytes = b"{}"
        try:
            body_json = json.loads(body_bytes)
        except json.JSONDecodeError:
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
                async with client.stream("POST", url, headers=upstream_headers, content=body_bytes) as upstream_resp:
                    if upstream_resp.status_code != 200:
                        text = await upstream_resp.aread()
                        yield json.dumps({"error": text.decode("utf-8", errors="replace") or "Upstream error"}).encode()
                        return
                    async for chunk in upstream_resp.aiter_bytes():
                        yield chunk

            return StreamingResponse(
                streamer(),
                status_code=200,
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )

        upstream_resp = await client.post(url, headers=upstream_headers, content=body_bytes)

        if upstream_resp.status_code != 200:
            return JSONResponse(
                content={"error": upstream_resp.text or "Upstream error"},
                status_code=upstream_resp.status_code,
            )

        return JSONResponse(
            content=upstream_resp.json()
                if upstream_resp.headers.get("content-type", "").startswith("application/json")
                else {"data": upstream_resp.text},
            status_code=upstream_resp.status_code,
        )

    return app


def run_server(host: str, port: int, api_key: str | None, proxy: str | None) -> None:
    import uvicorn

    app = build_app(api_key=api_key, proxy=proxy)
    uvicorn.run(app, host=host, port=port)
