"""Anthropic Messages API (<- translate to/from OpenAI Chat Completions).

Endpoint: POST /v1/messages
Docs reference: https://docs.anthropic.com/en/api/messages

These functions are pure (the stream translator is async-pure over parsed
events) and do not touch httpx, disk, or the network.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator

from .common import StreamEvent, safe_json_dumps, safe_json_loads, sse_event


# --------------------------------------------------------------------------- #
# Request: Anthropic -> OpenAI Chat Completions
# --------------------------------------------------------------------------- #

def anthropic_request_to_openai(body: dict) -> dict:
    """Translate an Anthropic Messages request body to OpenAI Chat Completions."""
    messages: list[dict[str, Any]] = []
    system = body.get("system")
    if system is not None:
        messages.append({"role": "system", "content": _system_to_openai(system)})
    messages.extend(_messages_to_openai(body.get("messages") or []))

    out: dict[str, Any] = {"model": body.get("model"), "messages": messages}
    if "max_tokens" in body:
        out["max_tokens"] = body["max_tokens"]
    for key in (
        "temperature",
        "top_p",
        "stream",
        "n",
        "presence_penalty",
        "frequency_penalty",
    ):
        if key in body:
            out[key] = body[key]
    if "stop_sequences" in body:
        out["stop"] = body["stop_sequences"]
    if "stop" in body:
        out["stop"] = body["stop"]

    tools = _tools_to_openai(body.get("tools"))
    if tools is not None:
        out["tools"] = tools
    if "tool_choice" in body:
        choice = _tool_choice_to_openai(body["tool_choice"])
        if choice is not None:
            out["tool_choice"] = choice
    return out


def _system_to_openai(system: Any) -> str:
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        parts = [
            block.get("text", "")
            for block in system
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts)
    return ""


def _messages_to_openai(messages: list) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role") or "user"
        content = msg.get("content")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            out.append({"role": role, "content": ""})
            continue

        text_parts: list[str] = []
        image_parts: list[dict] = []
        tool_uses: list[dict] = []
        tool_results: list[dict] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                text_parts.append(str(block.get("text", "")))
            elif btype == "image":
                image = _image_to_openai(block)
                if image is not None:
                    image_parts.append(image)
            elif btype == "tool_use":
                tool_uses.append(block)
            elif btype == "tool_result":
                tool_results.append(block)

        if role == "assistant":
            amsg: dict[str, Any] = {"role": "assistant"}
            if text_parts:
                amsg["content"] = "".join(text_parts)
            if tool_uses:
                amsg["tool_calls"] = [
                    {
                        "id": tu.get("id") or ("call_" + uuid.uuid4().hex),
                        "type": "function",
                        "function": {
                            "name": tu.get("name", ""),
                            "arguments": safe_json_dumps(tu.get("input")),
                        },
                    }
                    for tu in tool_uses
                ]
            out.append(amsg)
        elif role == "user":
            # Each tool_result becomes its own OpenAI "tool" message.
            for tr in tool_results:
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr.get("tool_use_id") or "",
                        "content": _tool_result_content(tr.get("content")),
                    }
                )
            if text_parts or image_parts:
                if image_parts:
                    parts: list[dict] = list(image_parts)
                    if text_parts:
                        parts.append({"type": "text", "text": "".join(text_parts)})
                    out.append({"role": "user", "content": parts})
                else:
                    # Text-only: DevEco's OpenAI-compatible upstream accepts a
                    # plain string but not a bare content-part dict.
                    out.append({"role": "user", "content": "".join(text_parts)})
        else:
            out.append({"role": role, "content": "".join(text_parts) or ""})
    return out


def _image_to_openai(block: dict) -> dict | None:
    source = block.get("source")
    if not isinstance(source, dict):
        return None
    if source.get("type") == "base64":
        media = source.get("media_type") or "image/png"
        data = source.get("data") or ""
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{media};base64,{data}"},
        }
    if source.get("type") == "url":
        return {
            "type": "image_url",
            "image_url": {"url": str(source.get("url") or "")},
        }
    return None


def _tool_result_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts)
    if content is None:
        return ""
    return safe_json_dumps(content)


def _tools_to_openai(tools: Any) -> list[dict] | None:
    if not isinstance(tools, list) or not tools:
        return None
    out: list[dict] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema")
                    or {"type": "object", "properties": {}},
                },
            }
        )
    return out


def _tool_choice_to_openai(choice: Any) -> Any:
    if isinstance(choice, str):
        if choice == "auto":
            return "auto"
        if choice == "any":
            return "required"
        if choice == "none":
            return "none"
        return None
    if isinstance(choice, dict):
        ctype = choice.get("type")
        if ctype == "auto":
            return "auto"
        if ctype == "any":
            return "required"
        if ctype == "none":
            return "none"
        if ctype == "tool":
            return {"type": "function", "function": {"name": choice.get("name", "")}}
    return None


# --------------------------------------------------------------------------- #
# Response: OpenAI Chat Completions -> Anthropic (non-stream)
# --------------------------------------------------------------------------- #

def openai_response_to_anthropic(content: dict, model: str) -> dict:
    """Translate an OpenAI non-stream response into an Anthropic message."""
    choices = content.get("choices") or []
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}

    blocks: list[dict] = []
    text = message.get("content")
    if isinstance(text, str) and text:
        blocks.append({"type": "text", "text": text})
    elif isinstance(text, list):
        for part in text:
            if isinstance(part, dict) and part.get("type") == "text":
                blocks.append({"type": "text", "text": str(part.get("text", ""))})

    for tc in message.get("tool_calls") or []:
        fn = tc.get("function") or {}
        parsed = safe_json_loads(fn.get("arguments"))
        blocks.append(
            {
                "type": "tool_use",
                "id": tc.get("id") or ("call_" + uuid.uuid4().hex),
                "name": fn.get("name", ""),
                "input": parsed if isinstance(parsed, dict) else {},
            }
        )

    usage = content.get("usage") or {}
    return {
        "id": "msg_" + str(content.get("id") or uuid.uuid4().hex),
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": blocks,
        "stop_reason": _finish_to_stop(choice.get("finish_reason")),
        "stop_sequence": None,
        "usage": {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
        },
    }


def anthropic_error(status: int, message: str) -> dict:
    """Build an Anthropic-style error body."""
    etype = "invalid_request_error" if 400 <= status < 500 else "api_error"
    return {"type": "error", "error": {"type": etype, "message": message}}


def _finish_to_stop(reason: Any) -> str:
    return {
        "stop": "end_turn",
        "tool_calls": "tool_use",
        "function_call": "tool_use",
        "length": "max_tokens",
        "content_filter": "end_turn",
    }.get(reason, "end_turn")


# --------------------------------------------------------------------------- #
# Stream: OpenAI SSE -> Anthropic SSE
# --------------------------------------------------------------------------- #

async def openai_stream_to_anthropic(
    events: AsyncGenerator[StreamEvent, None],
    model: str,
) -> AsyncGenerator[bytes, None]:
    """Translate a parsed OpenAI SSE stream into Anthropic SSE bytes."""
    msg_id = "msg_" + uuid.uuid4().hex
    started = False
    text_open = False
    text_index = 0
    next_index = 0
    tool_indexes: dict[int, int] = {}
    finish_reason: Any = None
    usage_input = 0
    usage_output = 0

    async for ev in events:
        if ev.kind == "error":
            if not started:
                started = True
                yield sse_event(
                    "message_start",
                    _message_start(msg_id, model, 0, 0),
                )
            yield sse_event(
                "error",
                {"type": "error", "error": {"type": "api_error", "message": ev.data or "Upstream error"}},
            )
            return
        if ev.kind == "done":
            break
        chunk = ev.data or {}
        # Read usage first so message_start can report the real input_tokens
        # (DevEco sends prompt_tokens in every chunk, including the first).
        usage = chunk.get("usage")
        if isinstance(usage, dict):
            if usage.get("prompt_tokens") is not None:
                usage_input = int(usage["prompt_tokens"])
            if usage.get("completion_tokens") is not None:
                usage_output = int(usage["completion_tokens"])
        if not started:
            started = True
            yield sse_event("message_start", _message_start(msg_id, model, usage_input, 0))
            yield sse_event("ping", {"type": "ping"})

        choices = chunk.get("choices") or []
        choice = choices[0] if choices else {}
        delta = choice.get("delta") or {}

        text = delta.get("content")
        if isinstance(text, str) and text:
            if not text_open:
                text_index = next_index
                next_index += 1
                text_open = True
                yield sse_event(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": text_index,
                        "content_block": {"type": "text", "text": ""},
                    },
                )
            yield sse_event(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": text_index,
                    "delta": {"type": "text_delta", "text": text},
                },
            )

        for tc in delta.get("tool_calls") or []:
            idx = int(tc.get("index", 0) or 0)
            fn = tc.get("function") or {}
            if idx not in tool_indexes:
                if text_open:
                    yield sse_event(
                        "content_block_stop",
                        {"type": "content_block_stop", "index": text_index},
                    )
                    text_open = False
                bi = next_index
                next_index += 1
                tool_indexes[idx] = bi
                yield sse_event(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": bi,
                        "content_block": {
                            "type": "tool_use",
                            "id": tc.get("id") or ("toolu_" + uuid.uuid4().hex),
                            "name": fn.get("name", ""),
                            "input": {},
                        },
                    },
                )
            else:
                bi = tool_indexes[idx]
            if fn.get("arguments"):
                yield sse_event(
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": bi,
                        "delta": {
                            "type": "input_json_delta",
                            "partial_json": fn["arguments"],
                        },
                    },
                )

        if choice.get("finish_reason"):
            finish_reason = choice["finish_reason"]

    if not started:
        yield sse_event("message_start", _message_start(msg_id, model, 0, 0))
        yield sse_event("ping", {"type": "ping"})

    if text_open:
        yield sse_event("content_block_stop", {"type": "content_block_stop", "index": text_index})
    for bi in tool_indexes.values():
        yield sse_event("content_block_stop", {"type": "content_block_stop", "index": bi})

    yield sse_event(
        "message_delta",
        {
            "type": "message_delta",
            "delta": {
                "stop_reason": _finish_to_stop(finish_reason),
                "stop_sequence": None,
            },
            "usage": {"input_tokens": usage_input, "output_tokens": usage_output},
        },
    )
    yield sse_event("message_stop", {"type": "message_stop"})


def _message_start(msg_id: str, model: str, input_tokens: int, output_tokens: int) -> dict:
    return {
        "type": "message_start",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {
                "input_tokens": int(input_tokens or 0),
                "output_tokens": int(output_tokens or 0),
            },
        },
    }
