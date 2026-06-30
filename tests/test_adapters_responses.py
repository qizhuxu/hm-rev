"""Pure-function tests for the OpenAI Responses adapter."""

from __future__ import annotations

import asyncio
import json

from hm_api.adapters import (
    StreamEvent,
    openai_response_to_responses,
    openai_stream_to_responses,
    responses_error,
    responses_request_to_openai,
)


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
# Request: Responses -> OpenAI
# --------------------------------------------------------------------------- #

def test_responses_request_translates_instructions_and_items():
    body = {
        "model": "m",
        "max_output_tokens": 50,
        "instructions": "Be brief.",
        "input": [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]},
            {"type": "function_call", "call_id": "c1", "name": "get", "arguments": '{"a": 1}'},
            {"type": "function_call_output", "call_id": "c1", "output": "42"},
        ],
        "tools": [{"type": "function", "name": "get", "description": "d", "parameters": {"type": "object"}}],
        "tool_choice": "auto",
    }
    out = responses_request_to_openai(body)
    msgs = out["messages"]
    assert msgs[0] == {"role": "system", "content": "Be brief."}
    assert msgs[1] == {"role": "user", "content": {"type": "text", "text": "hi"}}
    assert msgs[2]["role"] == "assistant"
    assert msgs[2]["tool_calls"][0]["id"] == "c1"
    assert msgs[2]["tool_calls"][0]["function"]["arguments"] == '{"a": 1}'
    assert msgs[3] == {"role": "tool", "tool_call_id": "c1", "content": "42"}
    assert out["max_tokens"] == 50
    assert out["tools"] == [
        {
            "type": "function",
            "function": {"name": "get", "description": "d", "parameters": {"type": "object"}},
        }
    ]
    assert out["tool_choice"] == "auto"


def test_responses_request_string_input():
    out = responses_request_to_openai({"model": "m", "input": "hello"})
    assert out["messages"] == [{"role": "user", "content": "hello"}]


def test_responses_tools_skip_builtin():
    out = responses_request_to_openai(
        {
            "model": "m",
            "input": "x",
            "tools": [
                {"type": "web_search_preview"},
                {"type": "function", "name": "f", "parameters": {"type": "object"}},
            ],
        }
    )
    assert out["tools"] == [
        {"type": "function", "function": {"name": "f", "description": "", "parameters": {"type": "object"}}}
    ]


# --------------------------------------------------------------------------- #
# Response: OpenAI -> Responses (non-stream)
# --------------------------------------------------------------------------- #

def test_openai_response_to_responses_text():
    content = {
        "id": "r1",
        "choices": [{"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
    }
    out = openai_response_to_responses(content, "m")
    assert out["object"] == "response"
    assert out["model"] == "m"
    assert out["status"] == "completed"
    assert out["output"][0]["type"] == "message"
    assert out["output"][0]["content"][0] == {"type": "output_text", "text": "hello", "annotations": []}
    assert out["usage"] == {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5}
    assert out["id"].startswith("resp_")


def test_openai_response_to_responses_tool_call():
    content = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": "c1", "function": {"name": "get", "arguments": '{"a": 1}'}}],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {},
    }
    out = openai_response_to_responses(content, "m")
    fc = out["output"][0]
    assert fc["type"] == "function_call"
    assert fc["call_id"] == "c1"
    assert fc["name"] == "get"
    assert fc["arguments"] == '{"a": 1}'
    assert fc["status"] == "completed"


def test_openai_response_to_responses_length_is_incomplete():
    content = {
        "choices": [{"message": {"role": "assistant", "content": "cut"}, "finish_reason": "length"}],
        "usage": {},
    }
    assert openai_response_to_responses(content, "m")["status"] == "incomplete"


def test_responses_error_shape():
    err = responses_error(400, "bad")
    assert err == {"error": {"message": "bad", "type": "invalid_request_error"}}
    assert responses_error(503, "boom")["error"]["type"] == "server_error"


# --------------------------------------------------------------------------- #
# Stream: OpenAI SSE -> Responses SSE
# --------------------------------------------------------------------------- #

def test_responses_stream_text_only():
    items = [
        StreamEvent("chunk", {"choices": [{"delta": {"content": "Hi"}, "index": 0}]}),
        StreamEvent(
            "chunk",
            {
                "choices": [{"delta": {"content": " there"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
        ),
        StreamEvent("done"),
    ]
    frames = _run_stream(openai_stream_to_responses(_events_gen(items), "m"))
    events = _parse_sse(frames)
    types = [e[0] for e in events]
    assert types == [
        "response.created",
        "response.output_item.added",
        "response.content_part.added",
        "response.output_text.delta",
        "response.output_text.delta",
        "response.output_text.done",
        "response.content_part.done",
        "response.output_item.done",
        "response.completed",
    ]
    deltas = [e[1] for e in events if e[0] == "response.output_text.delta"]
    assert [d["delta"] for d in deltas] == ["Hi", " there"]
    completed = next(e[1] for e in events if e[0] == "response.completed")
    assert completed["response"]["status"] == "completed"
    assert completed["response"]["output"][0]["content"][0]["text"] == "Hi there"
    assert completed["response"]["usage"] == {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}


def test_responses_stream_tool_call():
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
                                    "function": {"name": "get", "arguments": '{"a":'},
                                }
                            ]
                        }
                    }
                ]
            },
        ),
        StreamEvent(
            "chunk",
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "1}"}}]}}]},
        ),
        StreamEvent("chunk", {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
        StreamEvent("done"),
    ]
    frames = _run_stream(openai_stream_to_responses(_events_gen(items), "m"))
    events = _parse_sse(frames)
    types = [e[0] for e in events]
    assert types[0] == "response.created"
    assert "response.output_item.added" in types
    assert types.count("response.function_call_arguments.delta") == 2
    assert "response.function_call_arguments.done" in types
    assert types[-1] == "response.completed"
    added = next(e[1] for e in events if e[0] == "response.output_item.added")
    assert added["item"]["type"] == "function_call"
    assert added["item"]["call_id"] == "call_1"
    assert added["item"]["name"] == "get"
    done = next(e[1] for e in events if e[0] == "response.function_call_arguments.done")
    assert done["arguments"] == '{"a":1}'
    completed = next(e[1] for e in events if e[0] == "response.completed")
    fc = completed["response"]["output"][0]
    assert fc["type"] == "function_call"
    assert fc["arguments"] == '{"a":1}'


def test_responses_stream_empty_emits_created_and_completed():
    items = [StreamEvent("done")]
    frames = _run_stream(openai_stream_to_responses(_events_gen(items), "m"))
    types = [e[0] for e in _parse_sse(frames)]
    assert types[0] == "response.created"
    assert types[-1] == "response.completed"


def test_openai_response_to_responses_multiple_tool_calls():
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
    out = openai_response_to_responses(content, "m")
    fcs = out["output"]
    assert [f["call_id"] for f in fcs] == ["c1", "c2"]
    assert [f["name"] for f in fcs] == ["get", "set"]
    assert fcs[0]["arguments"] == '{"a": 1}'
    assert fcs[1]["arguments"] == '{"b": 2}'


def test_responses_stream_multiple_parallel_tool_calls():
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
    frames = _run_stream(openai_stream_to_responses(_events_gen(items), "m"))
    events = _parse_sse(frames)
    added = [e[1] for e in events if e[0] == "response.output_item.added"]
    assert len(added) == 2
    assert [a["item"]["call_id"] for a in added] == ["c1", "c2"]
    completed = next(e[1] for e in events if e[0] == "response.completed")
    fcs = completed["response"]["output"]
    assert [f["arguments"] for f in fcs] == ['{"a":1}', '{"b":2}']
