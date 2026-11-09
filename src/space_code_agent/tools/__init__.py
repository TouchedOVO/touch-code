"""Default tool registry."""

from __future__ import annotations

from ..app.config import AppConfig
from . import filesystem, runner, search, validation
from .base import ToolContext, ToolSpec
from .registry import ToolRegistry


def finish_task(context: ToolContext, args: dict) -> dict:
    summary = args["summary"]
    context.notify("log", "模型请求结束任务（仍需通过本地验收检查）。", level="info")
    return {
        "ok": True,
        "summary": "已请求结束任务；本地验收器将继续检查交付物。",
        "finished": True,
        "summary_text": summary,
    }


FINISH_SPEC = ToolSpec(
    name="finish_task",
    description=(
        "Declare the project finished. Only call after README, dependency manifest, source code, "
        "tests and ASSUMPTIONS.md all exist. The local validator may reject completion."
    ),
    parameters={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Concise delivery summary and known gaps."},
        },
        "required": ["summary"],
        "additionalProperties": False,
    },
    handler=finish_task,
    category="meta",
)


def build_registry(config: AppConfig) -> ToolRegistry:
    registry = ToolRegistry(max_result_chars=config.max_tool_output_chars)
    for module in (filesystem, search, validation, runner):
        for spec in module.SPECS:
            registry.register(spec)
    registry.register(FINISH_SPEC)
    return registry
