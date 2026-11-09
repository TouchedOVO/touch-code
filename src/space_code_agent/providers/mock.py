"""Deterministic mock provider for offline tests and demos.

It implements the same interface as DeepSeekProvider but replays a scripted
sequence of Responses-API-shaped turns.  This exercises the *real* tool layer,
file policy and orchestrator; only the model is replaced.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable

from ..app.config import AppConfig
from ..app.events import Event
from .base import ProviderError, ProviderResponse, TokenUsage, ToolCall


class MockProvider:
    name = "mock"

    def __init__(
        self,
        responses: list[ProviderResponse] | Callable[[int, list[dict]], ProviderResponse],
        config: AppConfig | None = None,
        emit: Callable[[Event], None] | None = None,
        delay_s: float = 0.0,
    ) -> None:
        self._responses = responses
        self._config = config or AppConfig()
        self._emit = emit
        self._delay = delay_s
        self.calls = 0
        self.inputs: list[list[dict]] = []

    def create(
        self,
        *,
        instructions: str,
        input_items: list[dict],
        tools: list[dict] | None = None,
        effort: str | None = None,
        max_output_tokens: int | None = None,
        response_format: dict | None = None,
        cancellation: Any = None,
    ) -> ProviderResponse:
        del instructions, tools, effort, max_output_tokens, response_format
        if cancellation is not None and cancellation.is_set():
            raise ProviderError("cancelled", "用户已取消。")
        self.calls += 1
        self.inputs.append(list(input_items))
        if self._delay:
            time.sleep(self._delay)
        if callable(self._responses):
            response = self._responses(self.calls - 1, input_items)
        elif self.calls <= len(self._responses):
            response = self._responses[self.calls - 1]
        else:
            response = text_response("（Mock 脚本已结束）")
        if response.usage.requests == 0:
            response.usage.requests = 1
        if response.usage.total_tokens == 0:
            response.usage.input_tokens = 100
            response.usage.output_tokens = 20
        return response

    def list_models(self) -> list[str]:
        return ["mock"]

    def test_connection(self) -> tuple[bool, str]:
        return True, "Mock 模式可用（不调用真实 API）。"

    def close(self) -> None:
        return None


_counter = 0


def _next_call_id() -> str:
    global _counter
    _counter += 1
    return f"call_mock_{_counter:04d}"


def tool_response(
    calls: list[tuple[str, dict]],
    text: str = "",
    call_ids: list[str] | None = None,
) -> ProviderResponse:
    """Build a Responses-API-shaped turn containing function calls."""
    global _counter
    output_items: list[dict] = []
    tool_calls: list[ToolCall] = []
    if text:
        output_items.append({
            "type": "message",
            "id": f"msg_mock_{_counter:04d}",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        })
    for index, (name, arguments) in enumerate(calls):
        call_id = (call_ids[index] if call_ids and index < len(call_ids) else _next_call_id())
        raw = json.dumps(arguments, ensure_ascii=False)
        output_items.append({
            "type": "function_call",
            "id": f"fc_mock_{_counter:04d}_{index}",
            "call_id": call_id,
            "name": name,
            "arguments": raw,
            "status": "completed",
        })
        tool_calls.append(ToolCall(call_id=call_id, name=name, arguments=arguments, raw_arguments=raw))
    return ProviderResponse(
        id=f"resp_mock_{_counter:04d}",
        output_items=output_items,
        text=text,
        tool_calls=tool_calls,
        usage=TokenUsage(input_tokens=100, output_tokens=20, requests=1),
        status="completed",
        model="mock",
    )


def text_response(text: str) -> ProviderResponse:
    global _counter
    _counter += 1
    return ProviderResponse(
        id=f"resp_mock_{_counter:04d}",
        output_items=[{
            "type": "message",
            "id": f"msg_mock_{_counter:04d}",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }],
        text=text,
        usage=TokenUsage(input_tokens=100, output_tokens=20, requests=1),
        status="completed",
        model="mock",
    )
