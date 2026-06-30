"""API-format translation adapters for the hm-api proxy.

Each adapter translates between a target API format (Anthropic Messages,
OpenAI Responses) and the OpenAI Chat Completions shape spoken by the DevEco
upstream. All functions are pure (or async-pure over parsed SSE events) so
they can be unit-tested without httpx, disk, or network.
"""

from __future__ import annotations

from .anthropic import (
    anthropic_error,
    anthropic_request_to_openai,
    openai_response_to_anthropic,
    openai_stream_to_anthropic,
)
from .common import SSE_DONE, StreamEvent, parse_openai_sse, sse_chunk
from .responses import (
    openai_response_to_responses,
    openai_stream_to_responses,
    responses_error,
    responses_request_to_openai,
)

__all__ = [
    "SSE_DONE",
    "StreamEvent",
    "anthropic_error",
    "anthropic_request_to_openai",
    "openai_response_to_anthropic",
    "openai_response_to_responses",
    "openai_stream_to_anthropic",
    "openai_stream_to_responses",
    "parse_openai_sse",
    "responses_error",
    "responses_request_to_openai",
    "sse_chunk",
]
