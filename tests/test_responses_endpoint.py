"""Integration tests for POST /v1/responses (OpenAI Responses endpoint)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from hm_api.accounts import save_account_from_user_info
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


def test_responses_nonstream_returns_responses_shape(monkeypatch, tmp_path):
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
                    "id": "r1",
                    "choices": [
                        {"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
                },
            )

    monkeypatch.setattr("hm_api.server.httpx.AsyncClient", FakeClient)
    client = TestClient(build_app())
    resp = client.post(
        "/v1/responses",
        json={
            "model": "m",
            "max_output_tokens": 10,
            "instructions": "be brief",
            "input": "hi",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "response"
    assert body["status"] == "completed"
    assert body["output"][0]["type"] == "message"
    assert body["output"][0]["content"][0] == {
        "type": "output_text",
        "text": "hello",
        "annotations": [],
    }
    assert body["usage"] == {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5}

    sent = json.loads(captured[0])
    assert sent["messages"][0] == {"role": "system", "content": "be brief"}
    assert sent["messages"][1] == {"role": "user", "content": "hi"}
    assert sent["max_tokens"] == 10
    assert "access-1" not in resp.text


def test_responses_stream_emits_responses_sse(monkeypatch, tmp_path):
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
        "/v1/responses",
        json={"model": "m", "input": "hi", "stream": True},
    )

    assert resp.status_code == 200
    assert "event: response.created" in resp.text
    assert "event: response.output_text.delta" in resp.text
    assert "event: response.completed" in resp.text
    assert "Hi" in resp.text and " there" in resp.text
    assert "access-1" not in resp.text


def test_responses_no_account_returns_responses_error(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    client = TestClient(build_app())
    resp = client.post("/v1/responses", json={"model": "m", "input": "hi"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["type"] == "invalid_request_error"


def test_responses_requires_auth(monkeypatch, tmp_path):
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
    payload = {"model": "m", "input": "hi"}

    assert client.post("/v1/responses", json=payload).status_code == 401
    assert (
        client.post(
            "/v1/responses", json=payload, headers={"x-api-key": "secret"}
        ).status_code
        == 200
    )
