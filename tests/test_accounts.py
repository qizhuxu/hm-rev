import json

from hm_api.accounts import (
    activate_account,
    delete_account,
    get_active_account,
    get_account_strategy,
    list_accounts,
    load_account_state,
    rename_account,
    save_account_from_user_info,
    select_account_candidates,
    set_account_strategy,
    update_account_connectivity,
    update_account_profile,
)
from hm_api.config import get_accounts_file, get_auth_file, get_token_file
from hm_api.crypto import encrypt_value, save_auth_data
from hm_api.login import UserInfo


def _fake_jwt(user_id: str = "legacy-user", user_name: str = "旧账号") -> str:
    import base64

    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"userId": user_id, "userName": user_name}).encode()
        )
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}.sig"


def _user_info(
    user_id: str,
    user_name: str,
    access: str,
    refresh: str,
    jwt: str,
) -> UserInfo:
    return UserInfo(
        user_id=user_id,
        user_name=user_name,
        access_token=access,
        refresh_token=refresh,
        jwt_token=jwt,
    )


def test_legacy_single_account_is_migrated(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_auth_data(
        {
            "deveco": {
                "type": "oauth",
                "access": "legacy-access-token",
                "refresh": "legacy-refresh-token",
            }
        }
    )
    token_file = get_token_file()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(json.dumps(encrypt_value(_fake_jwt())), encoding="utf-8")

    state = load_account_state()
    accounts = list_accounts()
    active = get_active_account()

    assert state["version"] == 1
    assert len(accounts) == 1
    assert accounts[0]["is_active"] is True
    assert accounts[0]["user_name"] == "旧账号"
    assert active is not None
    assert active["access_token"] == "legacy-access-token"
    assert active["refresh_token"] == "legacy-refresh-token"
    assert get_accounts_file().exists()


def test_legacy_single_account_without_refresh_is_migrated(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    save_auth_data(
        {
            "deveco": {
                "type": "oauth",
                "access": "legacy-access-token",
            }
        }
    )
    token_file = get_token_file()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(json.dumps(encrypt_value(_fake_jwt())), encoding="utf-8")

    accounts = list_accounts()
    active = get_active_account()

    assert len(accounts) == 1
    assert accounts[0]["is_active"] is True
    assert active is not None
    assert active["access_token"] == "legacy-access-token"
    assert active["refresh_token"] == ""


def test_save_activate_rename_and_delete_accounts(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))

    first_id = save_account_from_user_info(
        _user_info("u1", "账号一", "access-1", "refresh-1", "jwt-1"),
        display_name="生产账号",
    )
    second_id = save_account_from_user_info(
        _user_info("u2", "账号二", "access-2", "refresh-2", "jwt-2"),
        display_name="备用账号",
    )

    activate_account(first_id)
    rename_account(first_id, "主力账号")
    delete_account(second_id)

    accounts = list_accounts()
    active = get_active_account()

    assert [account["account_id"] for account in accounts] == [first_id]
    assert accounts[0]["display_name"] == "主力账号"
    assert active is not None
    assert active["account_id"] == first_id
    assert active["access_token"] == "access-1"


def test_account_profile_tags_and_note_are_migrated_and_preserved(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))

    account_id = save_account_from_user_info(
        _user_info("u1", "账号一", "access-1", "refresh-1", "jwt-1"),
        display_name="生产账号",
    )

    account = list_accounts()[0]
    assert account["tags"] == []
    assert account["note"] == ""

    updated = update_account_profile(
        account_id,
        display_name="生产主号",
        tags=["生产", "主力"],
        note="工作日优先使用",
    )
    assert updated["display_name"] == "生产主号"
    assert updated["tags"] == ["生产", "主力"]
    assert updated["note"] == "工作日优先使用"

    save_account_from_user_info(
        _user_info("u1", "账号一", "access-new", "refresh-new", "jwt-new"),
        account_id=account_id,
        display_name=None,
    )

    account = list_accounts()[0]
    assert account["display_name"] == "生产主号"
    assert account["tags"] == ["生产", "主力"]
    assert account["note"] == "工作日优先使用"


def test_account_strategy_defaults_to_env_and_can_be_updated(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    monkeypatch.setenv("HM_API_ACCOUNT_STRATEGY", "round_robin")

    assert get_account_strategy() == "round_robin"
    assert set_account_strategy("failover") == "failover"
    assert get_account_strategy() == "failover"


def test_active_only_selects_only_active_account(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    first_id = save_account_from_user_info(
        _user_info("u1", "账号一", "access-1", "refresh-1", "jwt-1"),
        display_name="生产账号",
    )
    save_account_from_user_info(
        _user_info("u2", "账号二", "access-2", "refresh-2", "jwt-2"),
        display_name="备用账号",
        activate=False,
    )

    selected = select_account_candidates("active_only")

    assert [account["account_id"] for account in selected] == [first_id]


def test_round_robin_selects_next_healthy_account(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    first_id = save_account_from_user_info(
        _user_info("u1", "账号一", "access-1", "refresh-1", "jwt-1"),
        display_name="生产账号",
    )
    second_id = save_account_from_user_info(
        _user_info("u2", "账号二", "access-2", "refresh-2", "jwt-2"),
        display_name="备用账号",
        activate=False,
    )

    set_account_strategy("round_robin")

    assert select_account_candidates()[0]["account_id"] == first_id
    assert select_account_candidates()[0]["account_id"] == second_id
    assert select_account_candidates()[0]["account_id"] == first_id


def test_failover_prefers_active_then_healthy_backups(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))
    first_id = save_account_from_user_info(
        _user_info("u1", "账号一", "access-1", "refresh-1", "jwt-1"),
        display_name="生产账号",
    )
    second_id = save_account_from_user_info(
        _user_info("u2", "账号二", "access-2", "refresh-2", "jwt-2"),
        display_name="备用账号",
        activate=False,
    )
    update_account_connectivity(
        first_id,
        {
            "success": False,
            "status_code": 401,
            "latency_ms": 5,
            "model_count": 0,
            "checked_at": "2026-06-30T12:00:00Z",
            "error": "unauthorized",
        },
    )

    selected = select_account_candidates("failover")

    assert [account["account_id"] for account in selected] == [second_id, first_id]


def test_accounts_file_never_stores_plain_tokens(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))

    save_account_from_user_info(
        _user_info(
            "u1",
            "账号一",
            "plain-access-token",
            "plain-refresh-token",
            "plain-jwt-token",
        )
    )

    raw = get_accounts_file().read_text(encoding="utf-8")
    assert "plain-access-token" not in raw
    assert "plain-refresh-token" not in raw
    assert "plain-jwt-token" not in raw
    assert get_auth_file().exists()
