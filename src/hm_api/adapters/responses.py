"""OpenAI Responses API (<- translate to/from OpenAI Chat Completions).

Endpoint: POST /v1/responses
Docs reference: https://platform.openai.com/docs/api-reference/responses

Stateless: ``previous_response_id`` / ``store`` are accepted but ignored
(the proxy has no server-side conversation store). Built-in tools
(web_search / file_search / code_interpreter) are not implemented; function
tools are translated and forwarded.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, AsyncGenerator

from .common import StreamEvent, safe_json_dumps, sse_event


# --------------------------------------------------------------------------- #
# Request: Responses -> OpenAI Chat Completions
# --------------------------------------------------------------------------- #

def responses_request_to_openai(body: dict) -> dict:
    """Translate a Responses request body to OpenAI Chat Completions."""
    messages: list[dict[str, Any]] = []
    instructions = body.get("instructions")
    if isinstance(instructions, str) and instructions:
        messages.append({"role": "system", "content": instructions})

    raw_input = body.get("input")
    if isinstance(raw_input, str):
        messages.append({"role": "user", "content": raw_input})
    elif isinstance(raw_input, list):
        for item in raw_input:
            mapped = _input_item_to_openai(item)
            if mapped is None:
                continue
            messages.append(mapped)

    out: dict[str, Any] = {"model": body.get("model"), "messages": messages}
    if "max_output_tokens" in body:
        out["max_tokens"] = body["max_output_tokens"]
    elif "max_tokens" in body:
        out["max_tokens"] = body["max_tokens"]
    for key in (
        "temperature",
        "top_p",
        "stream",
        "stop",
        "n",
        "parallel_tool_calls",
        "presence_penalty",
        "frequency_penalty",
    ):
        if key in body:
            out[key] = body[key]
    tools = _tools_to_openai(body.get("tools"))
    if tools is not None:
        out["tools"] = tools
    if "tool_choice" in body:
        out["tool_choice"] = body["tool_choice"]
    return out


def _input_item_to_openai(item: Any) -> dict | None:
    if not isinstance(item, dict):
        return None
    itype = item.get("type")
    if itype == "message":
        role = item.get("role") or "user"
        content = item.get("content")
        if isinstance(content, str):
            return {"role": role, "content": content}
        if isinstance(content, list):
            parts: list[dict] = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype in ("input_text", "output_text"):
                    parts.append({"type": "text", "text": str(part.get("text", ""))})
                elif ptype == "input_image":
                    image = _image_to_openai(part)
                    if image is not None:
                        parts.append(image)
            if not parts:
                return {"role": role, "content": ""}
            return {"role": role, "content": parts[0] if len(parts) == 1 else parts}
        return {"role": role, "content": ""}
    if itype == "function_call":
        return {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": item.get("call_id") or ("call_" + uuid.uuid4().hex),
                    "type": "function",
                    "function": {
                        "name": item.get("name", ""),
                        "arguments": str(item.get("arguments") or ""),
                    },
                }
            ],
        }
    if itype == "function_call_output":
        return {
            "role": "tool",
            "tool_call_id": item.get("call_id") or "",
            "content": _as_text(item.get("output")),
        }
    # reasoning / other item types are not supported -> drop silently
    return None


def _image_to_openai(part: dict) -> dict | None:
    if part.get("image_url"):
        return {"type": "image_url", "image_url": {"url": str(part["image_url"])}}
    if part.get("data"):
        mime = part.get("mime_type") or "image/png"
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{part['data']}"},
        }
    return None


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return safe_json_dumps(value)


def _tools_to_openai(tools: Any) -> list[dict] | None:
    if not isinstance(tools, list) or not tools:
        return None
    out: list[dict] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") != "function":
            # Built-in tools (web_search / file_search / code_interpreter) are
            # out of scope for the proxy; skip rather than forward.
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters")
                    or {"type": "object", "properties": {}},
                },
            }
        )
    return out or None


# --------------------------------------------------------------------------- #
# Response: OpenAI Chat Completions -> Responses (non-stream)
# --------------------------------------------------------------------------- #

def openai_response_to_responses(content: dict, model: str) -> dict:
    """Translate an OpenAI non-stream response into a Responses object."""
    choices = content.get("choices") or []
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}

    output: list[dict] = []
    text = message.get("content")
    if isinstance(text, str) and text:
        output.append(_message_item(uuid.uuid4().hex, text))
    elif isinstance(text, list):
        parts = [
            {"type": "output_text", "text": str(p.get("text", "")), "annotations": []}
            for p in text
            if isinstance(p, dict) and p.get("type") == "text"
        ]
        if parts:
            output.append(
                {
                    "type": "message",
                    "id": "msg_" + uuid.uuid4().hex,
                    "role": "assistant",
                    "status": "completed",
                    "content": parts,
                }
            )

    for tc in message.get("tool_calls") or []:
        fn = tc.get("function") or {}
        output.append(
            {
                "type": "function_call",
                "id": "fc_" + uuid.uuid4().hex,
                "call_id": str(tc.get("id") or ""),
                "name": fn.get("name", ""),
                "arguments": str(fn.get("arguments") or ""),
                "status": "completed",
            }
        )

    status = "incomplete" if choice.get("finish_reason") == "length" else "completed"
    usage = content.get("usage") or {}
    return {
        "id": "resp_" + str(content.get("id") or uuid.uuid4().hex),
        "object": "response",
        "created_at": _now_ts(),
        "model": model,
        "status": status,
        "output": output,
        "usage": {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        },
        "metadata": {},
    }


def responses_error(status: int, message: str) -> dict:
    """Build a Responses-style error body."""
    etype = "invalid_request_error" if 400 <= status < 500 else "server_error"
    return {"error": {"message": message, "type": etype}}


def _message_item(suffix: str, text: str) -> dict:
    return {
        "type": "message",
        "id": "msg_" + suffix,
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def _now_ts() -> int:
    return int(time.time())


# --------------------------------------------------------------------------- #
# Stream: OpenAI SSE -> Responses SSE
# --------------------------------------------------------------------------- #

async def openai_stream_to_responses(
    events: AsyncGenerator[StreamEvent, None],
    model: str,
) -> AsyncGenerator[bytes, None]:
    """Translate a parsed OpenAI SSE stream into Responses SSE bytes."""
    resp_id = "resp_" + uuid.uuid4().hex
    created_at = _now_ts()
    started = False
    next_output_index = 0
    output_items: list[dict] = []
    text_item: dict | None = None
    tool_items: dict[int, dict] = {}
    finish_reason: Any = None
    usage: dict = {}

    async for ev in events:
        if ev.kind == "error":
            if not started:
                started = True
                yield sse_event(
                    "response.created",
                    {"type": "response.created", "response": _resp_obj(resp_id, created_at, model, "in_progress", [], {})},
                )
            yield sse_event(
                "response.failed",
                {
                    "type": "response.failed",
                    "response": {
                        "id": resp_id,
                        "error": {"code": "server_error", "message": ev.data or "Upstream error"},
                    },
                },
            )
            return
        if ev.kind == "done":
            break

        chunk = ev.data or {}
        if not started:
            started = True
            yield sse_event(
                "response.created",
                {"type": "response.created", "response": _resp_obj(resp_id, created_at, model, "in_progress", [], {})},
            )

        choices = chunk.get("choices") or []
        choice = choices[0] if choices else {}
        delta = choice.get("delta") or {}

        text = delta.get("content")
        if isinstance(text, str) and text:
            if text_item is None:
                oi = next_output_index
                next_output_index += 1
                item_id = "msg_" + uuid.uuid4().hex
                text_item = {"output_index": oi, "item_id": item_id, "text": ""}
                yield sse_event(
                    "response.output_item.added",
                    {
                        "type": "response.output_item.added",
                        "output_index": oi,
                        "item": {
                            "type": "message",
                            "id": item_id,
                            "role": "assistant",
                            "status": "in_progress",
                            "content": [],
                        },
                    },
                )
                yield sse_event(
                    "response.content_part.added",
                    {
                        "type": "response.content_part.added",
                        "item_id": item_id,
                        "output_index": oi,
                        "content_index": 0,
                        "part": {"type": "output_text", "text": "", "annotations": []},
                    },
                )
            text_item["text"] += text
            yield sse_event(
                "response.output_text.delta",
                {
                    "type": "response.output_text.delta",
                    "item_id": text_item["item_id"],
                    "output_index": text_item["output_index"],
                    "content_index": 0,
                    "delta": text,
                },
            )

        for tc in delta.get("tool_calls") or []:
            idx = int(tc.get("index", 0) or 0)
            fn = tc.get("function") or {}
            if idx not in tool_items:
                if text_item is not None:
                    ti = text_item
                    yield sse_event(
                        "response.output_text.done",
                        {
                            "type": "response.output_text.done",
                            "item_id": ti["item_id"],
                            "output_index": ti["output_index"],
                            "content_index": 0,
                            "text": ti["text"],
                        },
                    )
                    yield sse_event(
                        "response.content_part.done",
                        {
                            "type": "response.content_part.done",
                            "item_id": ti["item_id"],
                            "output_index": ti["output_index"],
                            "content_index": 0,
                            "part": {"type": "output_text", "text": ti["text"], "annotations": []},
                        },
                    )
                    full = _message_item(uuid.uuid4().hex, ti["text"])
                    yield sse_event(
                        "response.output_item.done",
                        {
                            "type": "response.output_item.done",
                            "output_index": ti["output_index"],
                            "item": full,
                        },
                    )
                    output_items.append(full)
                    text_item = None

                oi = next_output_index
                next_output_index += 1
                item_id = "fc_" + uuid.uuid4().hex
                call_id = str(tc.get("id") or ("call_" + uuid.uuid4().hex))
                tool_items[idx] = {
                    "output_index": oi,
                    "item_id": item_id,
                    "call_id": call_id,
                    "name": fn.get("name", ""),
                    "args": "",
                }
                yield sse_event(
                    "response.output_item.added",
                    {
                        "type": "response.output_item.added",
                        "output_index": oi,
                        "item": {
                            "type": "function_call",
                            "id": item_id,
                            "call_id": call_id,
                            "name": fn.get("name", ""),
                            "arguments": "",
                            "status": "in_progress",
                        },
                    },
                )
            ti = tool_items[idx]
            if fn.get("arguments"):
                ti["args"] += fn["arguments"]
                yield sse_event(
                    "response.function_call_arguments.delta",
                    {
                        "type": "response.function_call_arguments.delta",
                        "item_id": ti["item_id"],
                        "output_index": ti["output_index"],
                        "delta": fn["arguments"],
                    },
                )

        if choice.get("finish_reason"):
            finish_reason = choice["finish_reason"]
        u = chunk.get("usage")
        if isinstance(u, dict):
            usage = u

    if text_item is not None:
        ti = text_item
        yield sse_event(
            "response.output_text.done",
            {
                "type": "response.output_text.done",
                "item_id": ti["item_id"],
                "output_index": ti["output_index"],
                "content_index": 0,
                "text": ti["text"],
            },
        )
        yield sse_event(
            "response.content_part.done",
            {
                "type": "response.content_part.done",
                "item_id": ti["item_id"],
                "output_index": ti["output_index"],
                "content_index": 0,
                "part": {"type": "output_text", "text": ti["text"], "annotations": []},
            },
        )
        full = _message_item(uuid.uuid4().hex, ti["text"])
        yield sse_event(
            "response.output_item.done",
            {
                "type": "response.output_item.done",
                "output_index": ti["output_index"],
                "item": full,
            },
        )
        output_items.append(full)
        text_item = None

    for ti in tool_items.values():
        yield sse_event(
            "response.function_call_arguments.done",
            {
                "type": "response.function_call_arguments.done",
                "item_id": ti["item_id"],
                "output_index": ti["output_index"],
                "arguments": ti["args"],
            },
        )
        full = {
            "type": "function_call",
            "id": ti["item_id"],
            "call_id": ti["call_id"],
            "name": ti["name"],
            "arguments": ti["args"],
            "status": "completed",
        }
        yield sse_event(
            "response.output_item.done",
            {
                "type": "response.output_item.done",
                "output_index": ti["output_index"],
                "item": full,
            },
        )
        output_items.append(full)

    status = "incomplete" if finish_reason == "length" else "completed"
    if not started:
        yield sse_event(
            "response.created",
            {"type": "response.created", "response": _resp_obj(resp_id, created_at, model, status, [], usage)},
        )
    yield sse_event(
        "response.completed",
        {
            "type": "response.completed",
            "response": _resp_obj(resp_id, created_at, model, status, output_items, usage),
        },
    )


def _resp_obj(
    resp_id: str,
    created_at: int,
    model: str,
    status: str,
    output: list[dict],
    usage: dict,
) -> dict:
    u = usage or {}
    return {
        "id": resp_id,
        "object": "response",
        "created_at": created_at,
        "model": model,
        "status": status,
        "output": output,
        "usage": {
            "input_tokens": int(u.get("prompt_tokens") or 0),
            "output_tokens": int(u.get("completion_tokens") or 0),
            "total_tokens": int(u.get("total_tokens") or 0),
        },
        "metadata": {},
    }
