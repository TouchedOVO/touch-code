"""Provider abstraction shared by the real DeepSeek client and the mock."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..app.config import AppConfig


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    requests: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def cost_usd(self, config: AppConfig) -> float:
        fresh = max(0, self.input_tokens - self.cached_tokens)
        return (
            fresh / 1_000_000 * config.price_input_per_mtok
            + self.cached_tokens / 1_000_000 * config.price_cached_input_per_mtok
            + self.output_tokens / 1_000_000 * config.price_output_per_mtok
        )

    def merge(self, other: "TokenUsage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cached_tokens += other.cached_tokens
        self.reasoning_tokens += other.reasoning_tokens
        self.requests += max(1, other.requests)

    def as_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_tokens": self.cached_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
            "requests": self.requests,
        }


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: dict
    raw_arguments: str = ""

    def summary(self, limit: int = 300) -> str:
        try:
            rendered = json.dumps(self.arguments, ensure_ascii=False)
        except (TypeError, ValueError):
            rendered = str(self.arguments)
        return f"{self.name}({rendered[:limit]})"


@dataclass
class ProviderResponse:
    id: str = ""
    output_items: list[dict] = field(default_factory=list)
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    status: str = "completed"
    model: str = ""
    incomplete_reason: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class ProviderError(Exception):
    """Structured provider failure with a stable machine code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        request_id: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.request_id = request_id

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "status_code": self.status_code,
            "retryable": self.retryable,
            "request_id": self.request_id,
        }


@runtime_checkable
class LLMProvider(Protocol):
    name: str

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
    ) -> ProviderResponse: ...

    def list_models(self) -> list[str]: ...

    def close(self) -> None: ...
