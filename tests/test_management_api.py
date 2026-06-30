from fastapi.testclient import TestClient

from hm_api.accounts import save_account_from_user_info
from hm_api.login import LoginResult, UserInfo
from hm_api.server import build_app
from hm_api.usage import record_usage_event


def _user_info(
    user_id: str = "user-1",
    user_name: str = "测试账号",
    access: str = "access-token",
) -> UserInfo:
    return UserInfo(
        user_id=user_id,
        user_name=user_name,
        access_token=access,
        refresh_token="refresh-token",
        jwt_token="jwt-token",
    )


def test_chinese_console_ui_contains_operations(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    client = TestClient(build_app())

    response = client.get("/ui")

    assert response.status_code == 200
    assert "总览" in response.text
    assert "账号工作台" in response.text
    assert "登录向导" in response.text
    assert "请求透视" in response.text
    assert "日志流" in response.text
    assert "模型与能力" in response.text
    assert "服务就绪度" in response.text
    assert "连通性检测" in response.text
    assert "账号标签" in response.text
    assert "接入配置" in response.text
    assert "autoRefreshLogs" in response.text
    assert "copyPythonConfig" in response.text
    assert "配置与安全" in response.text
    assert "账号状态加载中" in response.text
    assert "accountTarget" in response.text
    assert "覆盖：" in response.text
    assert "credentialFiles" in response.text
    assert "access_token" not in response.text
    assert "refresh_token" not in response.text


def test_accounts_api_does_not_return_tokens(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_account_from_user_info(_user_info(), display_name="生产账号")
    client = TestClient(build_app())

    response = client.get("/ui/api/accounts")

    assert response.status_code == 200
    assert response.json()["accounts"][0]["display_name"] == "生产账号"
    assert "access-token" not in response.text
    assert "refresh-token" not in response.text
    assert "jwt-token" not in response.text


def test_account_manual_callback_saves_new_account_without_leaking_tokens(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))

    async def fake_complete_manual_login(
        callback_url: str,
        expected_code: str | None,
        proxy: str | None = None,
        display_name: str | None = None,
        account_id: str | None = None,
    ) -> LoginResult:
        assert callback_url == "code=expected-code&tempToken=temp-token&siteId=1"
        assert expected_code == "expected-code"
        assert display_name == "新账号"
        assert account_id is None
        return LoginResult(
            success=True,
            user_info=_user_info(),
            account_id="acc-new",
        )

    monkeypatch.setattr("hm_api.server.complete_manual_login", fake_complete_manual_login)
    client = TestClient(build_app())

    response = client.post(
        "/ui/api/accounts/manual-callback",
        json={
            "callback_url": "code=expected-code&tempToken=temp-token&siteId=1",
            "expected_code": "expected-code",
            "display_name": "新账号",
        },
    )

    assert response.status_code == 200
    assert response.json()["account_id"] == "acc-new"
    assert "temp-token" not in response.text
    assert "access-token" not in response.text


def test_active_account_token_is_used_for_openai_api(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_account_from_user_info(
        _user_info(user_id="user-1", user_name="账号一", access="active-access"),
        display_name="生产账号",
    )
    client = TestClient(build_app())

    response = client.get("/ui/api/overview")

    assert response.status_code == 200
    assert response.json()["active_account"]["user_name"] == "账号一"


def test_overview_reports_credential_file_presence_only(monkeypatch, tmp_path):
    cred_dir = tmp_path / "cred"
    monkeypatch.setenv("HM_API_CRED_DIR", str(cred_dir))
    cred_dir.mkdir(parents=True)
    (cred_dir / "accounts.json").write_text(
        '{"version": 1, "active_account_id": null, "accounts": []}',
        encoding="utf-8",
    )
    (cred_dir / "usage.jsonl").write_text("", encoding="utf-8")
    client = TestClient(build_app())

    response = client.get("/ui/api/overview")

    assert response.status_code == 200
    files = response.json()["credential_files"]
    assert files == {
        "accounts_json": True,
        "usage_jsonl": True,
        "auth_json": False,
        "token_enc": False,
        "kek": False,
    }


def test_connectivity_check_success_and_failure_are_sanitized(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    account_id = save_account_from_user_info(_user_info(access="secret-access-token"))

    async def fake_check(account_id_arg: str, proxy: str | None = None):
        assert account_id_arg == account_id
        return {
            "success": False,
            "status_code": 502,
            "latency_ms": 31,
            "model_count": 0,
            "checked_at": "2026-06-30T12:00:00Z",
            "error": "上游不可用",
        }

    monkeypatch.setattr("hm_api.server.check_account_connectivity", fake_check)
    client = TestClient(build_app())

    response = client.post(f"/ui/api/accounts/{account_id}/check")

    assert response.status_code == 200
    assert response.json()["result"]["success"] is False
    assert "secret-access-token" not in response.text


def test_management_api_requires_bearer_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    client = TestClient(build_app(api_key="secret"))

    unauthorized = client.get("/ui/api/accounts")
    authorized = client.get(
        "/ui/api/accounts",
        headers={"Authorization": "Bearer secret"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200


def test_account_strategy_api_reads_and_updates_strategy(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    client = TestClient(build_app())

    initial = client.get("/ui/api/account-strategy")
    updated = client.put(
        "/ui/api/account-strategy",
        json={"strategy": "round_robin"},
    )

    assert initial.status_code == 200
    assert initial.json()["strategy"] == "active_only"
    assert updated.status_code == 200
    assert updated.json()["strategy"] == "round_robin"


def test_account_profile_api_updates_tags_and_note(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    account_id = save_account_from_user_info(_user_info(), display_name="生产账号")
    client = TestClient(build_app())

    response = client.patch(
        f"/ui/api/accounts/{account_id}",
        json={
            "display_name": "生产主号",
            "tags": ["生产", "主力"],
            "note": "工作日优先使用",
        },
    )

    assert response.status_code == 200
    account = response.json()["account"]
    assert account["display_name"] == "生产主号"
    assert account["tags"] == ["生产", "主力"]
    assert account["note"] == "工作日优先使用"
    assert "access-token" not in response.text


def test_usage_events_api_returns_recent_log_stream(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    record_usage_event(
        account_id="acc-1",
        endpoint="/v1/models",
        request_body={"messages": [{"role": "user", "content": "不要保存"}]},
        status_code=200,
        latency_ms=11,
        success=True,
    )
    client = TestClient(build_app())

    response = client.get("/ui/api/usage/events?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["events"][0]["account_id"] == "acc-1"
    assert body["events"][0]["endpoint"] == "/v1/models"
    assert "不要保存" not in response.text


def test_model_capabilities_api_refreshes_without_leaking_tokens(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    account_id = save_account_from_user_info(
        _user_info(access="secret-access-token"),
        display_name="生产账号",
    )

    async def fake_fetch(account_id_arg: str, proxy: str | None = None):
        assert account_id_arg == account_id
        return {
            "account_id": account_id_arg,
            "account_name": "生产账号",
            "success": True,
            "status_code": 200,
            "latency_ms": 23,
            "checked_at": "2026-06-30T12:00:00Z",
            "model_count": 2,
            "models": [
                {"id": "model-a", "owned_by": "deveco"},
                {"id": "model-b", "owned_by": "deveco"},
            ],
            "error": None,
        }

    monkeypatch.setattr("hm_api.server.fetch_account_models", fake_fetch)
    client = TestClient(build_app())

    response = client.post(
        "/ui/api/models/refresh",
        json={"account_id": account_id},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["models"][0]["id"] == "model-a"
    assert "secret-access-token" not in response.text
