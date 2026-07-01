"""Integration tests for POST /v1/messages (Anthropic Messages endpoint)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from hm_api.accounts import save_account_from_user_info, set_account_strategy
from hm_api.login import UserInfo
from hm_api.server import build_app


def _user_info(user_id: str = "u1", access: str = "access-1") -> UserInfo:
    return UserInfo(
        user_id=user_id,
        user_name=user_id,
        access_token=access,
        refresh_token="refresh",
        jwt_token="jwt",
    )


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = {"content-type": "application/json"}

    def json(self) -> dict:
        return self._payload


class _StreamResponse:
    def __init__(self, status_code: int, body: bytes):
        self.status_code = status_code
        self._body = body

    async def aread(self) -> bytes:
        return self._body

    async def aiter_bytes(self):
        for i in range(0, len(self._body), 64):
            yield self._body[i : i + 64]


class _StreamCtx:
    def __init__(self, status_code: int, body: bytes):
        self._resp = _StreamResponse(status_code, body)

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *args):
        return False


def test_messages_nonstream_returns_anthropic_shape(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_account_from_user_info(_user_info())
    captured: list[bytes] = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def post(self, url, headers, content):
            captured.append(content)
            return _FakeResponse(
                200,
                {
                    "id": "c1",
                    "choices": [
                        {"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
                },
            )

    monkeypatch.setattr("hm_api.server.httpx.AsyncClient", FakeClient)
    client = TestClient(build_app())
    resp = client.post(
        "/v1/messages",
        json={
            "model": "m",
            "max_tokens": 10,
            "system": "be brief",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "message"
    assert body["content"] == [{"type": "text", "text": "hello"}]
    assert body["stop_reason"] == "end_turn"
    assert body["usage"] == {"input_tokens": 2, "output_tokens": 3}

    sent = json.loads(captured[0])
    assert sent["messages"][0] == {"role": "system", "content": "be brief"}
    assert sent["messages"][1] == {"role": "user", "content": "hi"}
    assert sent["max_tokens"] == 10
    assert "access-1" not in resp.text


def test_messages_stream_emits_anthropic_sse(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_account_from_user_info(_user_info())
    sse = (
        b'data: {"choices":[{"delta":{"content":"Hi"},"index":0}]}\n\n'
        b'data: {"choices":[{"delta":{"content":" there"},"finish_reason":"stop"}],'
        b'"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}}\n\n'
        b"data: [DONE]\n\n"
    )

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def stream(self, method, url, headers, content):
            return _StreamCtx(200, sse)

    monkeypatch.setattr("hm_api.server.httpx.AsyncClient", FakeClient)
    client = TestClient(build_app())
    resp = client.post(
        "/v1/messages",
        json={
            "model": "m",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )

    assert resp.status_code == 200
    assert "event: message_start" in resp.text
    assert "event: content_block_delta" in resp.text
    assert "event: message_delta" in resp.text
    assert "event: message_stop" in resp.text
    assert "Hi" in resp.text and " there" in resp.text
    assert "access-1" not in resp.text


def test_messages_no_account_returns_anthropic_error(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    client = TestClient(build_app())
    resp = client.post(
        "/v1/messages",
        json={"model": "m", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["type"] == "error"
    assert body["error"]["type"] == "invalid_request_error"


def test_messages_accepts_x_api_key_and_bearer(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_account_from_user_info(_user_info())

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def post(self, url, headers, content):
            return _FakeResponse(
                200,
                {"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]},
            )

    monkeypatch.setattr("hm_api.server.httpx.AsyncClient", FakeClient)
    client = TestClient(build_app(api_key="secret"))
    payload = {"model": "m", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}

    assert client.post("/v1/messages", json=payload).status_code == 401
    assert (
        client.post("/v1/messages", json=payload, headers={"x-api-key": "secret"}).status_code
        == 200
    )
    assert (
        client.post(
            "/v1/messages", json=payload, headers={"Authorization": "Bearer secret"}
        ).status_code
        == 200
    )


def test_messages_failover_retries_next_account(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_account_from_user_info(_user_info("u1", "access-1"))
    save_account_from_user_info(_user_info("u2", "access-2"), activate=False)
    set_account_strategy("failover")
    calls: list[str] = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def post(self, url, headers, content):
            calls.append(headers["Authorization"])
            if len(calls) == 1:
                return _FakeResponse(401, text="expired access-1")
            return _FakeResponse(
                200,
                {"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]},
            )

    monkeypatch.setattr("hm_api.server.httpx.AsyncClient", FakeClient)
    client = TestClient(build_app())
    resp = client.post(
        "/v1/messages",
        json={"model": "m", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == [{"type": "text", "text": "ok"}]
    assert calls == ["Bearer access-1", "Bearer access-2"]
    assert "access-1" not in resp.text


def test_messages_stream_overrides_client_accept_header(monkeypatch, tmp_path):
    """Anthropic SDK sends Accept: application/json even when streaming; the
    upstream streaming endpoint rejects that. The proxy must set
    Accept: text/event-stream itself and not forward the client's value."""
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_account_from_user_info(_user_info())
    captured: list[dict] = []
    sse = b'data: {"choices":[{"delta":{"content":"Hi"},"index":0}]}\n\ndata: [DONE]\n\n'

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def stream(self, method, url, headers, content):
            captured.append(headers)
            return _StreamCtx(200, sse)

    monkeypatch.setattr("hm_api.server.httpx.AsyncClient", FakeClient)
    client = TestClient(build_app())
    resp = client.post(
        "/v1/messages",
        json={"model": "m", "max_tokens": 1, "stream": True, "messages": [{"role": "user", "content": "hi"}]},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert captured[0]["Accept"] == "text/event-stream"


def test_messages_nonstream_sets_accept_json(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_account_from_user_info(_user_info())
    captured: list[dict] = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def post(self, url, headers, content):
            captured.append(headers)
            return _FakeResponse(
                200,
                {"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]},
            )

    monkeypatch.setattr("hm_api.server.httpx.AsyncClient", FakeClient)
    client = TestClient(build_app())
    resp = client.post(
        "/v1/messages",
        json={"model": "m", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]},
        headers={"Accept": "text/event-stream"},
    )
    assert resp.status_code == 200
    assert captured[0]["Accept"] == "application/json"


def test_messages_does_not_forward_client_session_id(monkeypatch, tmp_path):
    """Codex sends its own session-id/thread-id UUIDs; DevEco's upstream rejects
    them ("Session-Id is too long"). The proxy must not forward client session
    headers — Session-Id comes only from x-deveco-session/x-session-affinity."""
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_account_from_user_info(_user_info())
    captured: list[dict] = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def post(self, url, headers, content):
            captured.append(headers)
            return _FakeResponse(
                200,
                {"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]},
            )

    monkeypatch.setattr("hm_api.server.httpx.AsyncClient", FakeClient)
    client = TestClient(build_app())
    client.post(
        "/v1/messages",
        json={"model": "m", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]},
        headers={
            "session-id": "019f1b2c-b4d2-7af2-bec6-242e802d0426",
            "thread-id": "019f1b2c-b4d2-7af2-bec6-242e802d0426",
            "x-deveco-session": "devsession123",
        },
    )
    sent = captured[0]
    # Client's session-id/thread-id must NOT be forwarded.
    assert "session-id" not in sent
    assert "thread-id" not in sent
    # x-deveco-session IS mapped to Session-Id.
    assert sent.get("Session-Id") == "devsession123"
