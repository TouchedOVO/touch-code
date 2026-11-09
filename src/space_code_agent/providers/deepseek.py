"""Official DeepSeek provider using the Responses API (OpenAI-compatible SDK).

Network policy:
  * 429 / 5xx / connection errors -> bounded exponential backoff + jitter;
  * 401 / 403 -> fail immediately with a friendly, non-retryable error;
  * 400 -> fail immediately, keeping a *sanitized* request summary;
  * every other failure is surfaced as a structured ProviderError.

The provider never logs the API key or raw request headers.
"""

from __future__ import annotations

import json
import random
import time
from typing import Any

from openai import OpenAI

from ..app.config import DEFAULT_BASE_URL, AppConfig
from ..security.secrets import SecretRedactor
from .base import LLMProvider, ProviderError, ProviderResponse, TokenUsage, ToolCall


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _to_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "model_dump"):
        return item.model_dump(exclude_none=True)
    if hasattr(item, "to_dict"):
        return item.to_dict()
    return {"value": str(item)}


class DeepSeekProvider(LLMProvider):
    name = "deepseek"

    def __init__(
        self,
        api_key: str,
        config: AppConfig,
        redactor: SecretRedactor | None = None,
        on_retry: Any = None,
        http_client: Any = None,
    ) -> None:
        if not api_key:
            raise ProviderError("missing_api_key", "请先填写 DeepSeek API Key。")
        self._config = config
        self._redactor = redactor or SecretRedactor([api_key])
        self._redactor.add(api_key)
        self._on_retry = on_retry
        client_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "base_url": config.base_url or DEFAULT_BASE_URL,
            "timeout": config.request_timeout_s,
            "max_retries": 0,  # retries are implemented here so we can cancel/log them
        }
        if http_client is not None:
            client_kwargs["http_client"] = http_client
        self._client = OpenAI(**client_kwargs)

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
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
        payload: dict[str, Any] = {
            "model": self._config.model,
            "instructions": instructions,
            "input": input_items,
            "max_output_tokens": max_output_tokens or self._config.max_output_tokens,
            "reasoning": {"effort": effort or self._config.reasoning_effort},
        }
        if self._config.temperature is not None and (effort or self._config.reasoning_effort) == "none":
            payload["temperature"] = self._config.temperature
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if response_format:
            payload["text"] = {"format": response_format}

        response = self._request(payload, cancellation)
        return self._parse(response)

    def list_models(self) -> list[str]:
        try:
            page = self._retry(
                lambda: self._client.models.list(),
                cancellation=None,
                operation="list_models",
            )
        except ProviderError:
            raise
        ids: list[str] = []
        for item in _get(page, "data", []) or []:
            model_id = _get(item, "id")
            if model_id:
                ids.append(str(model_id))
        return ids

    def test_connection(self) -> tuple[bool, str]:
        models = self.list_models()
        if not models:
            return True, "连接成功（模型列表为空）。"
        if self._config.model in models:
            return True, f"连接成功，模型 {self._config.model} 可用。"
        return True, (
            f"连接成功，但模型列表中未找到 {self._config.model}；"
            f"可用: {', '.join(models[:8])}"
        )

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # pragma: no cover - best effort
            pass

    # ------------------------------------------------------------------ #
    # retry / error mapping
    # ------------------------------------------------------------------ #
    def _request(self, payload: dict, cancellation: Any) -> Any:
        def _call() -> Any:
            return self._client.responses.create(**payload)

        return self._retry(_call, cancellation=cancellation, operation="responses.create")

    def _retry(self, fn: Any, *, cancellation: Any, operation: str) -> Any:
        attempts = max(0, self._config.max_retries)
        last: ProviderError | None = None
        for attempt in range(attempts + 1):
            if cancellation is not None and cancellation.is_set():
                raise ProviderError("cancelled", "用户已取消。")
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - mapped below
                error = self._map_error(exc)
                last = error
                if not error.retryable or attempt >= attempts:
                    raise error
                delay = self._retry_delay(exc, attempt)
                if self._on_retry:
                    try:
                        self._on_retry(attempt + 1, delay, error.code, error.message)
                    except Exception:  # pragma: no cover
                        pass
                if cancellation is not None:
                    if cancellation.wait(delay):
                        raise ProviderError("cancelled", "用户已取消。")
                else:
                    time.sleep(delay)
        raise last or ProviderError("unknown", f"{operation} 失败。")

    def _retry_delay(self, exc: Exception, attempt: int) -> float:
        retry_after = None
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                retry_after = response.headers.get("retry-after")
            except Exception:
                retry_after = None
        if retry_after:
            try:
                return min(60.0, max(0.5, float(retry_after)))
            except ValueError:
                pass
        base = self._config.retry_base_delay_s
        return min(30.0, base * (2 ** attempt)) * (0.75 + random.random() * 0.5)

    def _map_error(self, exc: Exception) -> ProviderError:
        status = getattr(exc, "status_code", None)
        name = type(exc).__name__
        raw = self._redactor.redact(str(exc))[:1500]
        request_id = ""
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                request_id = response.headers.get("x-request-id", "") or ""
            except Exception:
                request_id = ""
        if status == 401 or name == "AuthenticationError":
            return ProviderError("auth", "API Key 无效或已失效（401），请检查后重试。", status_code=401)
        if status == 403 or name == "PermissionDeniedError":
            return ProviderError("permission", "该 API Key 无权访问所选模型（403）。", status_code=403)
        if status == 429 or name == "RateLimitError":
            return ProviderError("rate_limit", "请求过于频繁或额度受限（429），正在退避重试。", status_code=429, retryable=True, request_id=request_id)
        if status == 400 or name == "BadRequestError":
            code = "context_length" if "context" in raw.lower() and "length" in raw.lower() else "invalid_request"
            return ProviderError(code, f"请求被拒绝（400）：{raw}", status_code=400, request_id=request_id)
        if status is not None and int(status) >= 500:
            return ProviderError("server", f"服务端错误（{status}），正在退避重试。", status_code=int(status), retryable=True, request_id=request_id)
        if name in {"APIConnectionError", "APITimeoutError", "ConnectError", "ReadTimeout", "ConnectTimeout"}:
            return ProviderError("network", "无法连接 DeepSeek API 或请求超时，正在重试。", retryable=True)
        if "timeout" in name.lower():
            return ProviderError("timeout", "请求超时，正在重试。", retryable=True)
        return ProviderError("unknown", f"模型调用失败：{raw}", status_code=status, request_id=request_id)

    # ------------------------------------------------------------------ #
    # response parsing
    # ------------------------------------------------------------------ #
    def _parse(self, response: Any) -> ProviderResponse:
        output = list(_get(response, "output", []) or [])
        items = [_to_dict(item) for item in output]
        tool_calls: list[ToolCall] = []
        for item in items:
            if item.get("type") != "function_call":
                continue
            raw_args = item.get("arguments", "") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                if not isinstance(args, dict):
                    raise ValueError("arguments must be an object")
            except Exception:  # noqa: BLE001
                args = {}
                item["_parse_error"] = "工具参数不是合法 JSON 对象"
            tool_calls.append(
                ToolCall(
                    call_id=str(item.get("call_id") or item.get("id") or ""),
                    name=str(item.get("name") or ""),
                    arguments=args,
                    raw_arguments=raw_args if isinstance(raw_args, str) else json.dumps(raw_args, ensure_ascii=False),
                )
            )
        text = _get(response, "output_text", "") or ""
        if not text:
            chunks: list[str] = []
            for item in items:
                if item.get("type") != "message":
                    continue
                for part in item.get("content", []) or []:
                    if isinstance(part, dict) and part.get("type") in {"output_text", "text"}:
                        chunks.append(str(part.get("text", "")))
            text = "".join(chunks)
        usage_raw = _get(response, "usage")
        usage = TokenUsage(requests=1)
        if usage_raw is not None:
            usage.input_tokens = int(_get(usage_raw, "input_tokens", 0) or 0)
            usage.output_tokens = int(_get(usage_raw, "output_tokens", 0) or 0)
            in_details = _get(usage_raw, "input_tokens_details", {}) or {}
            out_details = _get(usage_raw, "output_tokens_details", {}) or {}
            usage.cached_tokens = int(_get(in_details, "cached_tokens", 0) or 0)
            usage.reasoning_tokens = int(_get(out_details, "reasoning_tokens", 0) or 0)
        status = str(_get(response, "status", "completed") or "completed")
        incomplete = _get(response, "incomplete_details", {}) or {}
        return ProviderResponse(
            id=str(_get(response, "id", "") or ""),
            output_items=items,
            text=text,
            tool_calls=tool_calls,
            usage=usage,
            status=status,
            model=str(_get(response, "model", self._config.model) or self._config.model),
            incomplete_reason=str(_get(incomplete, "reason", "") or ""),
        )
