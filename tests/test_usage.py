import json

from hm_api.config import get_usage_file
from hm_api.usage import get_usage_summary, record_usage_event


def test_usage_records_metadata_without_message_content(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))

    record_usage_event(
        account_id="acc-1",
        endpoint="/v1/chat/completions",
        request_body={
            "model": "GLM-5.1",
            "stream": True,
            "messages": [{"role": "user", "content": "不要保存这句话"}],
        },
        status_code=200,
        latency_ms=123,
        success=True,
        usage={"total_tokens": 42},
    )

    raw = get_usage_file().read_text(encoding="utf-8")
    event = json.loads(raw.splitlines()[0])

    assert event["model"] == "GLM-5.1"
    assert event["stream"] is True
    assert event["usage"]["total_tokens"] == 42
    assert "messages" not in event
    assert "不要保存这句话" not in raw


def test_usage_summary_groups_by_account_and_model(monkeypatch, tmp_path):
    monkeypatch.setenv("HM_API_CRED_DIR", str(tmp_path / "cred"))

    record_usage_event(
        account_id="acc-1",
        endpoint="/v1/models",
        request_body={},
        status_code=200,
        latency_ms=50,
        success=True,
    )
    record_usage_event(
        account_id="acc-1",
        endpoint="/v1/chat/completions",
        request_body={"model": "GLM-5.1", "stream": False},
        status_code=500,
        latency_ms=150,
        success=False,
    )

    summary = get_usage_summary()

    assert summary["total_requests"] == 2
    assert summary["success_count"] == 1
    assert summary["error_count"] == 1
    assert summary["average_latency_ms"] == 100
    assert summary["by_account"]["acc-1"]["requests"] == 2
    assert summary["by_model"]["GLM-5.1"]["requests"] == 1
    assert len(summary["recent"]) == 2
