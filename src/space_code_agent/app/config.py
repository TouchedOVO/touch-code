"""Central configuration for SpaceCode Agent.

All engineering limits live here so they are auditable and testable.  The
defaults are deliberately conservative: bounded steps, bounded cost, no shell
execution unless the user opts in.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://api.deepseek.com"


def app_data_dir() -> Path:
    """Writable per-user directory for logs/session copies (outside projects)."""

    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    root = Path(base) / "SpaceCodeAgent" if base else Path.home() / ".space_code_agent"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        root = Path.home() / ".space_code_agent"
        root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass
class AppConfig:
    # --- model -----------------------------------------------------------
    model: str = DEFAULT_MODEL
    allow_model_override: bool = False
    base_url: str = DEFAULT_BASE_URL
    reasoning_effort: str = "high"
    temperature: float | None = None
    max_output_tokens: int = 16000
    plan_max_output_tokens: int = 16000
    request_timeout_s: float = 180.0
    max_retries: int = 4
    retry_base_delay_s: float = 1.0

    # --- budgets ---------------------------------------------------------
    max_agent_steps: int = 60
    max_planning_steps: int = 2
    max_repair_rounds: int = 3
    max_total_tokens: int = 3_000_000
    max_cost_usd: float = 6.0
    max_wall_seconds: float = 45 * 60

    # --- tool / workspace limits ----------------------------------------
    max_input_bytes: int = 2 * 1024 * 1024
    max_file_bytes: int = 1024 * 1024
    max_read_chars: int = 40_000
    max_tool_output_chars: int = 6000
    max_tool_result_bytes: int = 200_000
    tool_timeout_s: float = 30.0
    allow_command_execution: bool = False
    test_command_timeout_s: float = 300.0
    context_char_budget: int = 180_000

    # --- pricing (USD per 1M tokens; editable, estimates only) ----------
    price_input_per_mtok: float = 0.28
    price_cached_input_per_mtok: float = 0.028
    price_output_per_mtok: float = 0.42

    # --- behaviour -------------------------------------------------------
    mock_mode: bool = False
    mock_scenario: str = "space_fractions"
    require_finish_tool: bool = True
    stream_reasoning: bool = False
    state_dir_name: str = ".agent_state"

    # --- runtime (not persisted) ----------------------------------------
    extra: dict = field(default_factory=dict)

    def copy(self, **changes) -> "AppConfig":
        return replace(self, **changes)

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.model.strip():
            problems.append("模型名称不能为空")
        if not self.allow_model_override and self.model != DEFAULT_MODEL:
            problems.append(f"正式模式必须使用 {DEFAULT_MODEL}（如需实验模型请显式允许覆盖）")
        if not self.base_url.startswith(("https://", "http://")):
            problems.append("API 端点必须以 http(s):// 开头")
        if self.reasoning_effort not in {"none", "low", "medium", "high", "max"}:
            problems.append(f"不支持的思考强度: {self.reasoning_effort}")
        if not 1 <= self.max_agent_steps <= 500:
            problems.append("max_agent_steps 必须在 1..500 之间")
        if not 1 <= self.max_file_bytes <= 16 * 1024 * 1024:
            problems.append("max_file_bytes 必须在 1..16MiB 之间")
        if self.max_repair_rounds < 0:
            problems.append("max_repair_rounds 不能为负")
        if self.max_cost_usd <= 0:
            problems.append("max_cost_usd 必须为正")
        return problems
