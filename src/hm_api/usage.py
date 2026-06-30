"""Local usage statistics without storing prompt or message content."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import get_usage_file


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _event_from_request(
    *,
    account_id: str | None,
    endpoint: str,
    request_body: dict[str, Any] | None,
    status_code: int,
    latency_ms: int,
    success: bool,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = request_body or {}
    event: dict[str, Any] = {
        "timestamp": _iso(_now()),
        "account_id": account_id,
        "endpoint": endpoint,
        "model": body.get("model"),
        "stream": bool(body.get("stream")),
        "status_code": status_code,
        "latency_ms": int(latency_ms),
        "success": bool(success),
        "usage": usage,
    }
    return event


def record_usage_event(
    *,
    account_id: str | None,
    endpoint: str,
    request_body: dict[str, Any] | None,
    status_code: int,
    latency_ms: int,
    success: bool,
    usage: dict[str, Any] | None = None,
) -> None:
    usage_file = get_usage_file()
    usage_file.parent.mkdir(parents=True, exist_ok=True)
    event = _event_from_request(
        account_id=account_id,
        endpoint=endpoint,
        request_body=request_body,
        status_code=status_code,
        latency_ms=latency_ms,
        success=success,
        usage=usage,
    )
    with open(usage_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    os.chmod(usage_file, 0o600)


def _read_events() -> list[dict[str, Any]]:
    usage_file = get_usage_file()
    if not usage_file.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in usage_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _bucket() -> dict[str, Any]:
    return {"requests": 0, "success": 0, "errors": 0, "average_latency_ms": 0}


def get_usage_summary(days: int = 7) -> dict[str, Any]:
    events = _read_events()
    cutoff = _now() - timedelta(days=days - 1)
    total_latency = 0
    success_count = 0
    error_count = 0
    streaming_count = 0
    non_streaming_count = 0
    token_usage: dict[str, int] = {}
    by_account: dict[str, dict[str, Any]] = defaultdict(_bucket)
    by_model: dict[str, dict[str, Any]] = defaultdict(_bucket)
    latency_by_account: dict[str, int] = defaultdict(int)
    latency_by_model: dict[str, int] = defaultdict(int)
    trend = {
        (cutoff + timedelta(days=offset)).date().isoformat(): 0
        for offset in range(days)
    }

    for event in events:
        total_latency += int(event.get("latency_ms") or 0)
        if event.get("success"):
            success_count += 1
        else:
            error_count += 1
        if event.get("stream"):
            streaming_count += 1
        else:
            non_streaming_count += 1
        usage = event.get("usage")
        if isinstance(usage, dict):
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = usage.get(key)
                if isinstance(value, int | float):
                    token_usage[key] = token_usage.get(key, 0) + int(value)

        account_id = str(event.get("account_id") or "未关联账号")
        account_bucket = by_account[account_id]
        account_bucket["requests"] += 1
        account_bucket["success"] += 1 if event.get("success") else 0
        account_bucket["errors"] += 0 if event.get("success") else 1
        latency_by_account[account_id] += int(event.get("latency_ms") or 0)

        model = str(event.get("model") or "上游未返回")
        model_bucket = by_model[model]
        model_bucket["requests"] += 1
        model_bucket["success"] += 1 if event.get("success") else 0
        model_bucket["errors"] += 0 if event.get("success") else 1
        latency_by_model[model] += int(event.get("latency_ms") or 0)

        timestamp = str(event.get("timestamp") or "")
        date_key = timestamp[:10]
        if date_key in trend:
            trend[date_key] += 1

    for account_id, bucket in by_account.items():
        bucket["average_latency_ms"] = (
            latency_by_account[account_id] // bucket["requests"]
            if bucket["requests"]
            else 0
        )
    for model, bucket in by_model.items():
        bucket["average_latency_ms"] = (
            latency_by_model[model] // bucket["requests"] if bucket["requests"] else 0
        )

    total_requests = len(events)
    today = _now().date().isoformat()
    return {
        "total_requests": total_requests,
        "today_requests": trend.get(today, 0),
        "success_count": success_count,
        "error_count": error_count,
        "streaming_count": streaming_count,
        "non_streaming_count": non_streaming_count,
        "success_rate": round(success_count / total_requests, 4)
        if total_requests
        else 0,
        "error_rate": round(error_count / total_requests, 4)
        if total_requests
        else 0,
        "average_latency_ms": total_latency // total_requests if total_requests else 0,
        "trend": [{"date": key, "requests": value} for key, value in trend.items()],
        "by_account": dict(by_account),
        "by_model": dict(by_model),
        "token_usage": token_usage or None,
        "recent": list(reversed(events[-20:])),
    }
