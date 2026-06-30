"""Pure-function tests for the Anthropic Messages adapter.

No httpx, disk, or network: these exercise the translation functions
directly against OpenAI-shaped dicts and parsed SSE streams.
"""

from __future__ import annotations

import asyncio
import json

from hm_api.adapters import (
    StreamEvent,
    anthropic_error,
    anthropic_request_to_openai,
    openai_response_to_anthropic,
    openai_stream_to_anthropic,
)


# --------------------------------------------------------------------------- #
# SSE helpers
# --------------------------------------------------------------------------- #

async def _events_gen(items: list[StreamEvent]):
    for item in items:
        yield item


def _run_stream(translator_agen) -> list[bytes]:
    async def _collect() -> list[bytes]:
        out: list[bytes] = []
        async for chunk in translator_agen:
            out.append(chunk)
        return out

    return asyncio.run(_collect())


def _parse_sse(frames: list[bytes]) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for frame in frames:
        text = frame.decode("utf-8").rstrip("\n")
        etype = ""
        data: dict = {}
        for line in text.split("\n"):
            if line.startswith("event: "):
                etype = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        events.append((etype, data))
    return events


# --------------------------------------------------------------------------- #
# Request: Anthropic -> OpenAI
# --------------------------------------------------------------------------- #

def test_anthropic_request_translates_system_and_string_messages():
    body = {
        "model": "m",
        "max_tokens": 100,
        "system": "Be brief.",
        "messages": [{"role": "user", "content": "hi"}],
    }
    out = anthropic_request_to_openai(body)
    assert out["model"] == "m"
    assert out["max_tokens"] == 100
    assert out["messages"] == [
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": "hi"},
    ]


def test_anthropic_request_translates_tool_use_and_tool_result():
    body = {
        "model": "m",
        "max_tokens": 100,
        "messages": [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "ok"},
                    {"type": "tool_use", "id": "tu1", "name": "get", "input": {"a": 1}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tu1", "content": "42"},
                    {"type": "text", "text": "thanks"},
                ],
            },
        ],
    }
    msgs = anthropic_request_to_openai(body)["messages"]
    assert msgs[0]["role"] == "assistant"
    assert msgs[0]["content"] == "ok"
    call = msgs[0]["tool_calls"][0]
    assert call["id"] == "tu1"
    assert call["type"] == "function"
    assert call["function"]["name"] == "get"
    assert json.loads(call["function"]["arguments"]) == {"a": 1}
    assert msgs[1] == {"role": "tool", "tool_call_id": "tu1", "content": "42"}
    assert msgs[2]["role"] == "user"
    assert msgs[2]["content"] == {"type": "text", "text": "thanks"}


def test_anthropic_request_translates_tools_and_tool_choice():
    body = {
        "model": "m",
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "x"}],
        "tools": [
            {
                "name": "get",
                "description": "d",
                "input_schema": {"type": "object", "properties": {"a": {"type": "number"}}},
            }
        ],
        "tool_choice": {"type": "any"},
        "stop_sequences": ["END"],
    }
    out = anthropic_request_to_openai(body)
    assert out["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "get",
                "description": "d",
                "parameters": {"type": "object", "properties": {"a": {"type": "number"}}},
            },
        }
    ]
    assert out["tool_choice"] == "required"
    assert out["stop"] == ["END"]


def test_anthropic_tool_choice_variants():
    req = {"model": "m", "max_tokens": 1, "messages": [{"role": "user", "content": "x"}]}
    assert anthropic_request_to_openai({**req, "tool_choice": "auto"})["tool_choice"] == "auto"
    assert anthropic_request_to_openai({**req, "tool_choice": "none"})["tool_choice"] == "none"
    assert anthropic_request_to_openai(
        {**req, "tool_choice": {"type": "tool", "name": "get"}}
    )["tool_choice"] == {"type": "function", "function": {"name": "get"}}


# --------------------------------------------------------------------------- #
# Response: OpenAI -> Anthropic (non-stream)
# --------------------------------------------------------------------------- #

def test_openai_response_to_anthropic_text():
    content = {
        "id": "chatcmpl-1",
        "choices": [
            {"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }
    out = openai_response_to_anthropic(content, "m")
    assert out["type"] == "message"
    assert out["role"] == "assistant"
    assert out["model"] == "m"
    assert out["content"] == [{"type": "text", "text": "hello"}]
    assert out["stop_reason"] == "end_turn"
    assert out["stop_sequence"] is None
    assert out["usage"] == {"input_tokens": 5, "output_tokens": 3}
    assert out["id"].startswith("msg_")


def test_openai_response_to_anthropic_tool_calls():
    content = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": "c1", "function": {"name": "get", "arguments": '{"a": 1}'}}
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {},
    }
    out = openai_response_to_anthropic(content, "m")
    block = out["content"][0]
    assert block["type"] == "tool_use"
    assert block["id"] == "c1"
    assert block["name"] == "get"
    assert block["input"] == {"a": 1}
    assert out["stop_reason"] == "tool_use"


def test_openai_response_to_anthropic_length_is_max_tokens():
    content = {
        "choices": [
            {"message": {"role": "assistant", "content": "cut"}, "finish_reason": "length"}
        ],
        "usage": {},
    }
    assert openai_response_to_anthropic(content, "m")["stop_reason"] == "max_tokens"


def test_anthropic_error_shape():
    err = anthropic_error(401, "nope")
    assert err == {"type": "error", "error": {"type": "invalid_request_error", "message": "nope"}}
    assert anthropic_error(503, "boom")["error"]["type"] == "api_error"


# --------------------------------------------------------------------------- #
# Stream: OpenAI SSE -> Anthropic SSE
# --------------------------------------------------------------------------- #

def test_anthropic_stream_text_only():
    items = [
        StreamEvent("chunk", {"choices": [{"delta": {"content": "Hello"}, "index": 0}]}),
        StreamEvent(
            "chunk",
            {
                "choices": [{"delta": {"content": " world"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        ),
        StreamEvent("done"),
    ]
    frames = _run_stream(openai_stream_to_anthropic(_events_gen(items), "m"))
    events = _parse_sse(frames)
    types = [e[0] for e in events]
    assert types == [
        "message_start",
        "ping",
        "content_block_start",
        "content_block_delta",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
    ]
    deltas = [e[1] for e in events if e[0] == "content_block_delta"]
    assert deltas[0]["delta"] == {"type": "text_delta", "text": "Hello"}
    assert deltas[1]["delta"] == {"type": "text_delta", "text": " world"}
    msg_delta = next(e[1] for e in events if e[0] == "message_delta")
    assert msg_delta["delta"]["stop_reason"] == "end_turn"
    assert msg_delta["usage"]["output_tokens"] == 2


def test_anthropic_stream_tool_use():
    items = [
        StreamEvent(
            "chunk",
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "function": {"name": "get_weather", "arguments": '{"loc":'},
                                }
                            ]
                        }
                    }
                ]
            },
        ),
        StreamEvent(
            "chunk",
            {
                "choices": [
                    {"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"SF"}'}}]}}
                ]
            },
        ),
        StreamEvent("chunk", {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
        StreamEvent("done"),
    ]
    frames = _run_stream(openai_stream_to_anthropic(_events_gen(items), "m"))
    events = _parse_sse(frames)
    types = [e[0] for e in events]
    assert "content_block_start" in types
    assert types[-2] == "message_delta"
    assert types[-1] == "message_stop"
    start = next(e[1] for e in events if e[0] == "content_block_start")
    assert start["content_block"]["type"] == "tool_use"
    assert start["content_block"]["id"] == "call_1"
    assert start["content_block"]["name"] == "get_weather"
    deltas = [e[1] for e in events if e[0] == "content_block_delta"]
    assert all(d["delta"]["type"] == "input_json_delta" for d in deltas)
    assert "".join(d["delta"]["partial_json"] for d in deltas) == '{"loc":"SF"}'
    msg_delta = next(e[1] for e in events if e[0] == "message_delta")
    assert msg_delta["delta"]["stop_reason"] == "tool_use"


def test_anthropic_stream_empty_still_emits_lifecycle():
    items = [StreamEvent("done")]
    frames = _run_stream(openai_stream_to_anthropic(_events_gen(items), "m"))
    types = [e[0] for e in _parse_sse(frames)]
    assert types[0] == "message_start"
    assert types[-1] == "message_stop"


def test_anthropic_stream_error_event():
    items = [StreamEvent("error", "boom")]
    frames = _run_stream(openai_stream_to_anthropic(_events_gen(items), "m"))
    events = _parse_sse(frames)
    types = [e[0] for e in events]
    assert types[0] == "message_start"
    assert "error" in types
    err = next(e[1] for e in events if e[0] == "error")
    assert err["error"]["message"] == "boom"


def test_openai_response_to_anthropic_multiple_tool_calls():
    content = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": "c1", "function": {"name": "get", "arguments": '{"a": 1}'}},
                        {"id": "c2", "function": {"name": "set", "arguments": '{"b": 2}'}},
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {},
    }
    out = openai_response_to_anthropic(content, "m")
    blocks = out["content"]
    assert [b["id"] for b in blocks] == ["c1", "c2"]
    assert [b["name"] for b in blocks] == ["get", "set"]
    assert blocks[0]["input"] == {"a": 1}
    assert blocks[1]["input"] == {"b": 2}


def test_anthropic_stream_multiple_parallel_tool_calls():
    items = [
        StreamEvent(
            "chunk",
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "id": "c1", "function": {"name": "get", "arguments": '{"a":1}'}},
                                {"index": 1, "id": "c2", "function": {"name": "set", "arguments": '{"b":2}'}},
                            ]
                        }
                    }
                ]
            },
        ),
        StreamEvent("chunk", {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
        StreamEvent("done"),
    ]
    frames = _run_stream(openai_stream_to_anthropic(_events_gen(items), "m"))
    events = _parse_sse(frames)
    starts = [e[1] for e in events if e[0] == "content_block_start"]
    stops = [e[1] for e in events if e[0] == "content_block_stop"]
    assert len(starts) == 2
    assert len(stops) == 2
    assert [s["content_block"]["id"] for s in starts] == ["c1", "c2"]
    assert [s["index"] for s in stops] == [0, 1]

