"""Tests for the hosted /callback OAuth route (Docker/UI login flow)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from hm_api.login import (
    LoginResult,
    UserInfo,
    create_login_challenge,
    register_challenge,
    remove_challenge,
)
from hm_api.server import build_app


def _fake_user_info() -> UserInfo:
    return UserInfo(
        user_id="u1",
        user_name="Test",
        access_token="access",
        refresh_token="refresh",
        jwt_token="jwt",
    )


def _patch_login(monkeypatch):
    async def fake_exchange(temp_token, proxy=None):
        return _fake_user_info()

    def fake_save(user_info, *, display_name=None, account_id=None, activate=True):
        return "acct-1"

    monkeypatch.setattr("hm_api.server.exchange_temp_token", fake_exchange)
    monkeypatch.setattr("hm_api.server.save_user_info", fake_save)


def test_callback_get_with_query_params_completes_login(monkeypatch, tmp_path):
    """DevEco redirects the browser via GET 302 to /callback?code=...&tempToken=...
    with params in the query string. The route must accept GET and parse query."""
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    _patch_login(monkeypatch)
    challenge = create_login_challenge(port=8257, code="test-code-123")
    register_challenge(challenge)
    client = TestClient(build_app())

    resp = client.get(
        "/callback",
        params={"code": "test-code-123", "tempToken": "tt", "siteId": "1"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert resp.headers["location"] == "/ui?login_success=1"


def test_callback_post_with_form_body_completes_login(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    _patch_login(monkeypatch)
    challenge = create_login_challenge(port=8257, code="post-code-123")
    register_challenge(challenge)
    client = TestClient(build_app())

    resp = client.post(
        "/callback",
        data={"code": "post-code-123", "tempToken": "tt", "siteId": "1"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert resp.headers["location"] == "/ui?login_success=1"


def test_callback_unknown_code_redirects_expired(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    _patch_login(monkeypatch)
    client = TestClient(build_app())

    resp = client.get(
        "/callback",
        params={"code": "nonexistent", "tempToken": "tt", "siteId": "1"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert resp.headers["location"] == "/ui?login_error=expired"
