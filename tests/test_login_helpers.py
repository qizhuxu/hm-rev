import asyncio
from urllib.parse import parse_qs, urlparse

import pytest

import hm_api.login as login_module
from hm_api.login import (
    LoginCancelledError,
    UnsupportedRegionError,
    complete_manual_login,
    create_login_challenge,
    parse_callback_input,
    validate_callback_input,
)


def test_create_login_challenge_builds_deveco_login_url():
    challenge = create_login_challenge(port=34567, code="expected-code")

    parsed = urlparse(challenge.login_url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "cn.devecostudio.huawei.com"
    assert parsed.path.endswith("/console/DevEcoIDE/apply")
    assert query["port"] == ["34567"]
    assert query["appid"] == ["1008"]
    assert query["code"] == ["expected-code"]
    assert challenge.code == "expected-code"
    assert challenge.port == 34567


def test_parse_callback_input_accepts_full_callback_url():
    params = parse_callback_input(
        "http://127.0.0.1:10101/callback?code=expected-code&tempToken=temp%26extra&siteId=1"
    )

    assert params.code == "expected-code"
    assert params.temp_token == "temp&extra"
    assert params.site_id == "1"
    assert params.quit is None


def test_parse_callback_input_accepts_raw_query_string():
    params = parse_callback_input("code=expected-code&tempToken=temp-token&siteId=1")

    assert params.code == "expected-code"
    assert params.temp_token == "temp-token"
    assert params.site_id == "1"


def test_validate_callback_input_rejects_unsupported_region():
    with pytest.raises(UnsupportedRegionError):
        validate_callback_input(
            "code=expected-code&tempToken=temp-token&siteId=2",
            expected_code="expected-code",
        )


def test_validate_callback_input_rejects_missing_temp_token():
    with pytest.raises(LoginCancelledError, match="Missing tempToken or siteId"):
        validate_callback_input("code=expected-code&siteId=1", expected_code="expected-code")


def test_complete_manual_login_redacts_unexpected_exchange_errors(monkeypatch):
    async def fake_exchange_temp_token(
        temp_token: str,
        proxy: str | None = None,
    ):
        raise RuntimeError(f"upstream failed for {temp_token}")

    monkeypatch.setattr(login_module, "exchange_temp_token", fake_exchange_temp_token)

    result = asyncio.run(
        complete_manual_login(
            "code=expected-code&tempToken=secret-temp-token&siteId=1",
            expected_code="expected-code",
        )
    )

    assert not result.success
    assert result.error == "Login failed"
    assert "secret-temp-token" not in str(result.error)
