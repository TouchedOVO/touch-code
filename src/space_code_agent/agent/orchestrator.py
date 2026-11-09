"""Bounded plan-execute-observe-verify loop.

The orchestrator never trusts the model's claim of completion: a local
completion checker must also pass, and every tool result is paired by call_id.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..app.config import AppConfig
from ..app.events import Event
from ..core.requirements import NormalizedRequirements
from ..core.session import FileRegistry, SessionStore
from ..providers.base import LLMProvider, ProviderError, TokenUsage
from ..security.secrets import SecretRedactor
from ..tools.base import ToolContext
from ..tools.registry import ToolRegistry
from .prompts import SYSTEM_PROMPT, build_initial_message


@dataclass
class RunOutcome:
    status: str = "failed"              # completed | partial | cancelled | budget_exhausted | failed
    steps: int = 0
    tool_calls: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_summary: str = ""
    errors: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    compactions: int = 0
    last_message: str = ""
    models_used: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "steps": self.steps,
            "tool_calls": self.tool_calls,
            "usage": self.usage.as_dict(),
            "finish_summary": self.finish_summary,
            "errors": self.errors,
            "missing": self.missing,
            "elapsed_s": round(self.elapsed_s, 2),
            "compactions": self.compactions,
            "models_used": self.models_used,
        }


class AgentOrchestrator:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        registry: ToolRegistry,
        config: AppConfig,
        session: SessionStore,
        requirements: NormalizedRequirements,
        files: FileRegistry,
        emit: Callable[[Event], None],
        cancel: threading.Event | None = None,
        approve: Callable[[str, str], bool] | None = None,
        plan_summary: str = "",
        completion_check: Callable[[], tuple[bool, list[str]]] | None = None,
        redactor: SecretRedactor | None = None,
        max_steps: int | None = None,
        policy: Any = None,
        initial_footer: str = "",
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.config = config
        self.session = session
        self.requirements = requirements
        self.files = files
        self.emit = emit
        self.cancel = cancel or threading.Event()
        self.approve = approve
        self.plan_summary = plan_summary
        self.completion_check = completion_check or self._default_completion
        self.redactor = redactor or SecretRedactor()
        self.max_steps = max_steps or config.max_agent_steps
        self.policy = policy or self._policy()
        self.context = ToolContext(
            policy=self.policy,
            config=config,
            session=session,
            files=files,
            redactor=self.redactor,
            emit=emit,
            cancel=self.cancel,
            approve=approve,
            requirements=requirements,
        )
        self.initial_footer = initial_footer
        self.history: list[dict] = []
        self._finish_requested = False
        self._finish_attempts = 0
        self._compactions = 0

    def _policy(self):
        # The controller passes the policy through the session's workspace.
        from ..security.policy import WorkspacePolicy
        return WorkspacePolicy(self.session.root, max_file_bytes=self.config.max_file_bytes,
                               state_dir=self.config.state_dir_name)

    # ------------------------------------------------------------------ #
    def run(self) -> RunOutcome:
        started = time.perf_counter()
        outcome = RunOutcome()
        instructions = SYSTEM_PROMPT
        self.history = [{
            "role": "user",
            "content": build_initial_message(
                self.requirements.to_prompt_summary(),
                self.plan_summary or "（未提供单独计划，请按需求自行拆分任务）",
                workspace_hint=self.initial_footer,
            ),
        }]
        self._emit("phase", "实现阶段开始", phase="IMPLEMENTING")
        nudges = 0

        while outcome.steps < self.max_steps:
            if self.cancel.is_set():
                outcome.status = "cancelled"
                break
            budget = self._budget_exhausted(outcome)
            if budget:
                outcome.status = "budget_exhausted"
                outcome.errors.append(budget)
                break
            outcome.steps += 1
            self.context.step = outcome.steps
            self._emit("progress", f"第 {outcome.steps}/{self.max_steps} 步",
                       step=outcome.steps, max_steps=self.max_steps, usage=outcome.usage.as_dict())
            try:
                response = self.provider.create(
                    instructions=instructions,
                    input_items=self.history,
                    tools=self.registry.schemas(),
                    effort=self.config.reasoning_effort,
                    max_output_tokens=self.config.max_output_tokens,
                    cancellation=self.cancel,
                )
            except ProviderError as exc:
                outcome.status = "cancelled" if exc.code == "cancelled" else "failed"
                outcome.errors.append(f"{exc.code}: {exc.message}")
                self._emit("error", f"模型调用失败：{exc.message}", code=exc.code)
                break
            except Exception as exc:  # noqa: BLE001
                outcome.status = "failed"
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                self._emit("error", f"模型调用异常：{type(exc).__name__}: {exc}")
                break

            outcome.usage.merge(response.usage)
            outcome.last_message = response.text
            if response.model and response.model not in outcome.models_used:
                outcome.models_used.append(response.model)
            if response.model and response.model != self.config.model:
                self._emit("log", f"服务端返回模型 {response.model}，与配置 {self.config.model} 不一致。", "warn")
            if response.output_items:
                self.history.extend(response.output_items)
                try:
                    self.session.log_history_items(response.output_items)
                except Exception:
                    pass
            if response.text.strip():
                preview = response.text.strip()[:1200]
                self._emit("log", f"模型：{preview}")
            self._emit("usage", "用量更新", usage=outcome.usage.as_dict(),
                       cost_usd=outcome.usage.cost_usd(self.config))

            if response.status == "incomplete":
                self._emit("log", f"模型输出被截断（{response.incomplete_reason}），继续执行。", "warn")

            if response.tool_calls:
                nudges = 0
                for call in response.tool_calls:
                    if self.cancel.is_set():
                        break
                    result = self._execute(call.name, call.arguments, call.call_id, outcome)
                    output = self.registry.render_for_model(result)
                    self.history.append({
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": output,
                    })
                    outcome.tool_calls += 1
                    if result.get("ok"):
                        self._emit("tool", f"{call.name}: {result.get('summary', '')}",
                                   tool=call.name, ok=True)
                    else:
                        error = result.get("error", {})
                        self._emit("tool", f"{call.name} 失败：{error.get('message', '')}",
                                   tool=call.name, ok=False, error=error, level="warn")
                    if result.get("finished"):
                        self._finish_requested = True
                        outcome.finish_summary = result.get("summary_text", "")
                self._maybe_compact()
                if self._complete_if_finish_requested(outcome):
                    break
                continue

            # No tool call: completion or corrective nudge.
            if self._finish_requested:
                if self._complete_if_finish_requested(outcome):
                    break
                nudges = 0
                continue

            ok, missing = self.completion_check()
            if ok and not self.config.require_finish_tool:
                outcome.status = "completed"
                break
            nudges += 1
            if nudges > 2:
                outcome.status = "partial"
                outcome.missing = missing
                outcome.errors.append("模型连续未调用工具/完成工具，提前结束。")
                break
            self.history.append({
                "role": "user",
                "content": "尚未满足验收条件：" + "；".join(missing[:8])
                           + "\n请继续调用工具实现，完成后调用 finish_task；若无法完成，请明确说明缺口。",
            })
            self._maybe_compact()

        else:
            outcome.status = "budget_exhausted"
            outcome.errors.append(f"达到最大步数 {self.max_steps}。")

        outcome.elapsed_s = time.perf_counter() - started
        if outcome.status in {"failed", "partial", "budget_exhausted"}:
            ok, missing = self.completion_check()
            if ok:
                outcome.missing = []
            else:
                outcome.missing = missing
        self._emit("done", f"Agent 结束：{outcome.status}", outcome=outcome.as_dict(),
                   level="success" if outcome.status == "completed" else "warn")
        return outcome

    # ------------------------------------------------------------------ #
    def _complete_if_finish_requested(self, outcome: RunOutcome) -> bool:
        """Validate a finish request. Returns True when the run should stop."""
        if not self._finish_requested:
            return False
        ok, missing = self.completion_check()
        if ok:
            outcome.status = "completed"
            return True
        outcome.missing = missing
        self._finish_attempts += 1
        self._finish_requested = False
        self._emit("validation", "完成请求被本地验收拒绝：" + "；".join(missing[:6]), "warn")
        if self._finish_attempts >= 3:
            outcome.status = "partial"
            outcome.errors.append("本地验收连续 3 次未通过，停止修复。")
            return True
        self.history.append({
            "role": "user",
            "content": "本地验收未通过，尚缺：\n- " + "\n- ".join(missing[:12])
                       + "\n请补齐后再次调用 finish_task。",
        })
        return False

    def _execute(self, name: str, arguments: dict, call_id: str, outcome: RunOutcome) -> dict:
        del call_id
        return self.registry.execute(name, arguments, self.context)

    def _default_completion(self) -> tuple[bool, list[str]]:
        if not self.files.records:
            return False, ["工作区没有任何已写入文件"]
        if self.config.require_finish_tool and not self._finish_requested:
            return False, ["尚未调用 finish_task"]
        return True, []

    def _budget_exhausted(self, outcome: RunOutcome) -> str:
        if outcome.usage.total_tokens > self.config.max_total_tokens:
            return f"Token 预算耗尽（{outcome.usage.total_tokens}）"
        if outcome.usage.cost_usd(self.config) > self.config.max_cost_usd:
            return f"费用预算耗尽（${outcome.usage.cost_usd(self.config):.2f}）"
        if time.perf_counter() - self.session.started_at > self.config.max_wall_seconds:
            return "总时长预算耗尽"
        return ""

    def _maybe_compact(self) -> None:
        serialized = json.dumps(self.history, ensure_ascii=False)
        if len(serialized) <= self.config.context_char_budget:
            return
        keep_from = max(0, len(self.history) - 8)
        for index, item in enumerate(self.history):
            if index >= keep_from:
                continue
            kind = item.get("type")
            if kind == "function_call_output":
                output = str(item.get("output", ""))
                if len(output) > 700:
                    item["output"] = output[:700] + "...[older tool output compacted]"
            elif kind == "reasoning":
                content = item.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and len(str(part.get("text", ""))) > 500:
                            part["text"] = str(part["text"])[:500] + "...[compacted]"
        self._compactions += 1
        self._emit("log", f"上下文已压缩（第 {self._compactions} 次），保留最近工具结果。", "info")

    def _emit(self, kind: str, message: str, level: str = "info", **data: Any) -> None:
        try:
            event = Event(kind=kind, message=self.redactor.redact(message), data=data, level=level)
            self.emit(event)
            self.session.log_event(event)
        except Exception:
            pass
