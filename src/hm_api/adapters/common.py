"""Shared helpers for API-format translation adapters.

The proxy forwards requests to DevEco's OpenAI-compatible upstream, so the
Anthropic Messages and OpenAI Responses endpoints are implemented as edge
translators: requests are translated *to* OpenAI Chat Completions shape, and
upstream OpenAI responses are translated *back* to the target format.

The helpers in this module are deliberately pure (or async-pure over byte
streams) so they can be unit-tested without touching httpx, disk, or network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncGenerator


def safe_json_loads(value: Any) -> Any:
    """Parse a JSON string; return None on failure or non-string input."""
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return None


def safe_json_dumps(value: Any) -> str:
    """Serialize to JSON; on failure, return the value stringified."""
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


@dataclass
class StreamEvent:
    """A parsed OpenAI SSE event fed into stream translators.

    kind:
      - "chunk": data is an OpenAI chat-completion chunk dict.
      - "done":  upstream signaled [DONE]; data is None.
      - "error": failover exhausted before any content; data is a message.
    """

    kind: str
    data: Any = None


async def parse_openai_sse(aiter_bytes: Any) -> AsyncGenerator[StreamEvent, None]:
    """Yield StreamEvents from an OpenAI-style SSE byte stream.

    Splits events on blank lines, joins multi-line ``data:`` fields, parses
    JSON, and emits ``[DONE]`` as a "done" event. Non-data lines (e.g.
    ``: keep-alive`` comments) are ignored. Non-JSON data lines are skipped.
    """
    buffer = b""
    async for chunk in aiter_bytes:
        buffer += chunk
        while b"\n\n" in buffer:
            raw, buffer = buffer.split(b"\n\n", 1)
            data_lines: list[bytes] = []
            for line in raw.split(b"\n"):
                if line.startswith(b"data:"):
                    data_lines.append(line[5:].lstrip(b" "))
            if not data_lines:
                continue
            data = b"\n".join(data_lines).strip()
            if not data:
                continue
            if data == b"[DONE]":
                yield StreamEvent(kind="done")
                return
            try:
                obj = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, dict):
                yield StreamEvent(kind="chunk", data=obj)


def sse_chunk(model_data: dict) -> bytes:
    """Serialize an OpenAI chunk dict as an OpenAI SSE frame (passthrough)."""
    return b"data: " + json.dumps(model_data, ensure_ascii=False).encode("utf-8") + b"\n\n"


SSE_DONE = b"data: [DONE]\n\n"


def sse_event(event_type: str, data: dict) -> bytes:
    """Serialize a named SSE event (Anthropic / Responses style)."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n".encode("utf-8")
