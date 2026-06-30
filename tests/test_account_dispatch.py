from fastapi.testclient import TestClient

from hm_api.accounts import save_account_from_user_info, set_account_strategy
from hm_api.login import UserInfo
from hm_api.server import build_app


def _user_info(
    user_id: str,
    user_name: str,
    access: str,
) -> UserInfo:
    return UserInfo(
        user_id=user_id,
        user_name=user_name,
        access_token=access,
        refresh_token=f"refresh-{user_id}",
        jwt_token=f"jwt-{user_id}",
    )


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = {"content-type": "application/json"}

    def json(self) -> dict:
        return self._payload


def _models_payload(model_id: str) -> dict:
    return {
        "body": {
            "inner_models": [
                {"model_configs": [{"model_id": model_id}]},
            ]
        }
    }


def test_models_api_uses_round_robin_accounts(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_account_from_user_info(_user_info("u1", "账号一", "access-1"))
    save_account_from_user_info(
        _user_info("u2", "账号二", "access-2"),
        activate=False,
    )
    set_account_strategy("round_robin")
    calls: list[str] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def get(self, url, headers):
            calls.append(headers["Authorization"])
            model_id = f"model-{len(calls)}"
            return _FakeResponse(200, _models_payload(model_id))

    monkeypatch.setattr("hm_api.server.httpx.AsyncClient", FakeAsyncClient)
    client = TestClient(build_app())

    first = client.get("/v1/models")
    second = client.get("/v1/models")

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == ["Bearer access-1", "Bearer access-2"]


def test_chat_api_failover_retries_next_account(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_account_from_user_info(_user_info("u1", "账号一", "access-1"))
    save_account_from_user_info(
        _user_info("u2", "账号二", "access-2"),
        activate=False,
    )
    set_account_strategy("failover")
    calls: list[str] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, headers, content):
            calls.append(headers["Authorization"])
            if len(calls) == 1:
                return _FakeResponse(401, text="expired access-1")
            return _FakeResponse(
                200,
                {
                    "id": "chatcmpl-test",
                    "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                    "usage": {"total_tokens": 1},
                },
            )

    monkeypatch.setattr("hm_api.server.httpx.AsyncClient", FakeAsyncClient)
    client = TestClient(build_app())

    response = client.post(
        "/v1/chat/completions",
        json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "ok"
    assert calls == ["Bearer access-1", "Bearer access-2"]
    assert "access-1" not in response.text
