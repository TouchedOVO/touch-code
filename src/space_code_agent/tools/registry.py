"""Tool registry with JSON-schema validation and structured failures."""

from __future__ import annotations

import json
import time
from typing import Any

from ..app.events import Event
from ..security.policy import PolicyError
from .base import ToolContext, ToolError, ToolSpec


class ToolRegistry:
    def __init__(self, max_result_chars: int = 6000) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self.max_result_chars = max_result_chars

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"duplicate tool: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict]:
        return [self._tools[name].schema() for name in sorted(self._tools)]

    def execute(self, name: str, arguments: dict, context: ToolContext) -> dict:
        started = time.perf_counter()
        spec = self._tools.get(name)
        if spec is None:
            result = self._error("unknown_tool", f"未知工具：{name}")
            self._finish(context, name, arguments, result, started)
            return result
        if context.cancel.is_set():
            result = self._error("cancelled", "用户已取消。")
            self._finish(context, name, arguments, result, started)
            return result
        try:
            self._validate(spec.parameters, arguments, path="arguments")
            if spec.requires_approval:
                approved = context.approve is not None and context.approve(
                    name, json.dumps(arguments, ensure_ascii=False)[:2000]
                )
                if not approved:
                    raise ToolError("approval_denied", f"用户未授权执行工具 {name}。")
            payload = spec.handler(context, arguments)
            if not isinstance(payload, dict):
                payload = {"ok": True, "summary": str(payload)}
            result = {"ok": True, "tool": name, "summary": payload.pop("summary", "ok"), **payload}
        except ToolError as exc:
            result = self._error(exc.code, exc.message, exc.details)
        except PolicyError as exc:
            result = self._error(exc.code, exc.message, {"path": exc.path})
        except Exception as exc:  # noqa: BLE001 - tools must never crash the loop
            result = self._error("tool_exception", f"{type(exc).__name__}: {exc}")
        self._finish(context, name, arguments, result, started)
        return result

    # ------------------------------------------------------------------ #
    def _finish(self, context: ToolContext, name: str, arguments: dict,
                result: dict, started: float) -> None:
        duration_ms = int((time.perf_counter() - started) * 1000)
        try:
            context.session.log_tool(context.step, name, arguments, result, duration_ms)
        except Exception:
            pass
        if not result.get("ok"):
            context.notify("log", f"工具 {name} 失败：{result.get('error', {}).get('message', '')}",
                           level="error", tool=name)

    @staticmethod
    def _error(code: str, message: str, details: dict | None = None) -> dict:
        return {
            "ok": False,
            "error": {"code": code, "message": message, "details": details or {}},
            "summary": f"{code}: {message}",
        }

    # -- minimal JSON schema validation ----------------------------------
    def _validate(self, schema: dict, value: Any, path: str) -> None:
        expected = schema.get("type")
        if expected == "object":
            if not isinstance(value, dict):
                raise ToolError("invalid_arguments", f"{path} 必须是对象。")
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            for key in required:
                if key not in value:
                    raise ToolError("invalid_arguments", f"缺少必填参数：{path}.{key}")
            for key, child in value.items():
                if key in properties:
                    self._validate(properties[key], child, f"{path}.{key}")
                elif schema.get("additionalProperties") is False:
                    raise ToolError("invalid_arguments", f"不支持的参数：{path}.{key}")
            return
        if expected == "array":
            if not isinstance(value, list):
                raise ToolError("invalid_arguments", f"{path} 必须是数组。")
            item_schema = schema.get("items")
            if item_schema:
                for index, item in enumerate(value):
                    self._validate(item_schema, item, f"{path}[{index}]")
            return
        if expected == "string":
            if not isinstance(value, str):
                raise ToolError("invalid_arguments", f"{path} 必须是字符串。")
        elif expected == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ToolError("invalid_arguments", f"{path} 必须是整数。")
        elif expected == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ToolError("invalid_arguments", f"{path} 必须是数字。")
        elif expected == "boolean":
            if not isinstance(value, bool):
                raise ToolError("invalid_arguments", f"{path} 必须是布尔值。")
        if "enum" in schema and value not in schema["enum"]:
            raise ToolError("invalid_arguments", f"{path} 必须是 {schema['enum']} 之一。")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                raise ToolError("invalid_arguments", f"{path} 不能小于 {schema['minimum']}。")
            if "maximum" in schema and value > schema["maximum"]:
                raise ToolError("invalid_arguments", f"{path} 不能大于 {schema['maximum']}。")

    # -- truncation for model context ------------------------------------
    def render_for_model(self, result: dict) -> str:
        text = json.dumps(result, ensure_ascii=False)
        if len(text) <= self.max_result_chars:
            return text
        compact = dict(result)
        for key in ("content", "output", "matches", "entries", "files"):
            if key in compact and isinstance(compact[key], (str, list)):
                if isinstance(compact[key], str):
                    compact[key] = compact[key][: self.max_result_chars // 3] + "...[truncated]"
                else:
                    compact[key] = compact[key][:50]
        compact["truncated"] = True
        text = json.dumps(compact, ensure_ascii=False)
        if len(text) <= self.max_result_chars:
            return text
        return text[: self.max_result_chars] + "...[truncated]"
