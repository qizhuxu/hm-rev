from fastapi.testclient import TestClient

from hm_api.login import LoginResult, UserInfo
from hm_api.server import build_app


def test_ui_page_is_served(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    client = TestClient(build_app())

    response = client.get("/ui")

    assert response.status_code == 200
    assert "hm-api" in response.text
    assert "access_token" not in response.text
    assert "refresh_token" not in response.text


def test_webui_page_is_not_served(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    client = TestClient(build_app())

    response = client.get("/webui")

    assert response.status_code == 404


def test_ui_status_reports_logged_out_without_tokens(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    client = TestClient(build_app())

    response = client.get("/ui/api/status")

    assert response.status_code == 200
    assert response.json() == {"logged_in": False, "user": None}


def test_ui_status_obeys_api_key_authentication(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    client = TestClient(build_app(api_key="secret"))

    unauthorized = client.get("/ui/api/status")
    authorized = client.get(
        "/ui/api/status",
        headers={"Authorization": "Bearer secret"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200


def test_ui_login_url_endpoint_returns_manual_login_challenge(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    client = TestClient(build_app())

    response = client.post("/ui/api/login-url", json={"callback_port": 34567})
    body = response.json()

    assert response.status_code == 200
    assert body["callback_port"] == 34567
    assert "login_url" in body
    assert "code" in body
    assert "tempToken" not in body["login_url"]


def test_ui_manual_callback_does_not_return_tokens(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))

    async def fake_complete_manual_login(
        callback_url: str,
        expected_code: str | None,
        proxy: str | None = None,
    ) -> LoginResult:
        assert callback_url == "code=expected-code&tempToken=temp-token&siteId=1"
        assert expected_code == "expected-code"
        assert proxy is None
        return LoginResult(
            success=True,
            user_info=UserInfo(
                user_id="user-1",
                user_name="Test User",
                access_token="access-token",
                refresh_token="refresh-token",
                jwt_token="jwt-token",
            ),
        )

    monkeypatch.setattr("hm_api.server.complete_manual_login", fake_complete_manual_login)
    client = TestClient(build_app())

    response = client.post(
        "/ui/api/manual-callback",
        json={
            "callback_url": "code=expected-code&tempToken=temp-token&siteId=1",
            "expected_code": "expected-code",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "user": {"user_id": "user-1", "user_name": "Test User"},
    }
    assert "access-token" not in response.text
    assert "refresh-token" not in response.text
    assert "jwt-token" not in response.text
