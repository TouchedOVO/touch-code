"""M1 tests: configuration, secret redaction, DeepSeek Responses provider."""

from __future__ import annotations

import json

import httpx2 as httpx
import pytest

from space_code_agent.app.config import AppConfig
from space_code_agent.providers.base import ProviderError
from space_code_agent.providers.deepseek import DeepSeekProvider
from space_code_agent.security.secrets import SecretRedactor, mask_key

API_KEY = "sk-test-1234567890abcdef"


def _provider(handler, **config_overrides):
    config = AppConfig(
        max_retries=config_overrides.pop("max_retries", 2),
        retry_base_delay_s=0.01,
        **config_overrides,
    )
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return DeepSeekProvider(API_KEY, config, http_client=client), config


def _response_payload(text="done", calls=None):
    output = []
    if calls:
        for index, (name, args) in enumerate(calls):
            output.append(
                {
                    "type": "function_call",
                    "id": f"fc_{index}",
                    "call_id": f"call_{index}",
                    "name": name,
                    "arguments": json.dumps(args),
                    "status": "completed",
                }
            )
    else:
        output.append(
            {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        )
    return {
        "id": "resp_1",
        "object": "response",
        "created_at": 1,
        "status": "completed",
        "model": "deepseek-v4-pro",
        "output": output,
        "output_text": text if not calls else "",
        "usage": {
            "input_tokens": 120,
            "output_tokens": 30,
            "total_tokens": 150,
            "input_tokens_details": {"cached_tokens": 20},
            "output_tokens_details": {"reasoning_tokens": 5},
        },
    }


def test_config_validation():
    assert AppConfig().validate() == []
    assert AppConfig(model="").validate()
    assert AppConfig(reasoning_effort="turbo").validate()
    assert AppConfig(max_agent_steps=0).validate()


def test_redactor_masks_registered_and_pattern_keys():
    redactor = SecretRedactor([API_KEY])
    text = f"key={API_KEY} Authorization: Bearer abcdef123456789 sk-otherkey123456"
    cleaned = redactor.redact(text)
    assert API_KEY not in cleaned
    assert "abcdef123456789" not in cleaned
    assert "sk-otherkey123456" not in cleaned
    assert mask_key(API_KEY).startswith("sk-te")
    assert mask_key(API_KEY).endswith("cdef")


def test_create_parses_text_and_usage():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=_response_payload("hello"))

    provider, _ = _provider(handler)
    response = provider.create(instructions="sys", input_items=[{"role": "user", "content": "hi"}])
    assert response.text == "hello"
    assert response.usage.input_tokens == 120
    assert response.usage.cached_tokens == 20
    assert response.usage.reasoning_tokens == 5
    assert response.usage.total_tokens == 150
    assert seen["body"]["model"] == "deepseek-v4-pro"
    assert seen["body"]["reasoning"] == {"effort": "high"}
    assert seen["body"]["instructions"] == "sys"
    assert seen["auth"].startswith("Bearer ")


def test_create_parses_function_call():
    def handler(request):
        return httpx.Response(200, json=_response_payload(calls=[("write_file", {"path": "a.txt", "content": "x"})]))

    provider, _ = _provider(handler)
    response = provider.create(instructions="s", input_items=[{"role": "user", "content": "go"}])
    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert call.name == "write_file"
    assert call.arguments == {"path": "a.txt", "content": "x"}
    assert call.call_id == "call_0"


def test_retry_429_then_success():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        return httpx.Response(200, json=_response_payload("ok"))

    provider, _ = _provider(handler, max_retries=2)
    response = provider.create(instructions="s", input_items=[{"role": "user", "content": "hi"}])
    assert calls["n"] == 2
    assert response.text == "ok"


def test_retry_5xx_exhausted():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503, json={"error": {"message": "unavailable"}})

    provider, _ = _provider(handler, max_retries=2)
    with pytest.raises(ProviderError) as info:
        provider.create(instructions="s", input_items=[{"role": "user", "content": "hi"}])
    assert info.value.code == "server"
    assert info.value.retryable is True
    assert calls["n"] == 3


def test_auth_error_is_not_retried_and_key_not_leaked():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, json={"error": {"message": f"bad key {API_KEY}"}})

    provider, _ = _provider(handler, max_retries=3)
    with pytest.raises(ProviderError) as info:
        provider.create(instructions="s", input_items=[{"role": "user", "content": "hi"}])
    assert info.value.code == "auth"
    assert calls["n"] == 1
    assert API_KEY not in info.value.message


def test_tool_payload_uses_responses_function_schema():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_response_payload("ok"))

    provider, _ = _provider(handler)
    tools = [{"type": "function", "name": "read_file", "description": "read", "parameters": {"type": "object"}}]
    provider.create(instructions="s", input_items=[], tools=tools, effort="max", max_output_tokens=1234)
    body = seen["body"]
    assert body["tools"] == tools
    assert body["reasoning"] == {"effort": "max"}
    assert body["max_output_tokens"] == 1234
    assert body["tool_choice"] == "auto"


def test_missing_api_key_raises():
    with pytest.raises(ProviderError) as info:
        DeepSeekProvider("", AppConfig())
    assert info.value.code == "missing_api_key"


def test_network_failure_is_retried_then_reported():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ConnectError("connection refused")

    provider, _ = _provider(handler, max_retries=1)
    with pytest.raises(ProviderError) as info:
        provider.create(instructions="s", input_items=[{"role": "user", "content": "hi"}])
    assert info.value.code in {"network", "unknown"}
    assert info.value.retryable is True
    assert calls["n"] == 2
