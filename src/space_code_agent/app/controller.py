"""Application controller: the deterministic state machine around the agent.

State machine:
  VALIDATING_INPUT -> NORMALIZING -> PLANNING -> IMPLEMENTING
  -> (REPAIRING -> VERIFYING)* -> REPORTING -> COMPLETED / PARTIAL / FAILED

The controller owns lifecycle, cancellation, workspace preparation, provider
selection, repair rounds, test execution and report generation.  The GUI only
forwards events and requests cancellation.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..agent.orchestrator import AgentOrchestrator, RunOutcome
from ..agent.planner import Planner, PlanError, ProjectPlan, fallback_plan, validate_plan
from ..app.config import AppConfig
from ..app.events import Event
from ..core.delivery import DeliveryReport, DeliveryValidator, ensure_assumptions_file
from ..core.document_parser import DocumentError, DocumentParser
from ..core.report import ReportBuilder
from ..core.requirements import NormalizedRequirements, RequirementNormalizer
from ..core.sample_project import build_mock_script, build_sample_plan
from ..core.session import FileRegistry, SessionStore
from ..providers.base import LLMProvider, ProviderError
from ..providers.deepseek import DeepSeekProvider
from ..providers.mock import MockProvider
from ..security.policy import PolicyError, WorkspacePolicy
from ..security.secrets import SecretRedactor
from ..tools import build_registry


class ControllerError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class RunRequest:
    doc_path: str
    view_path: str
    output_dir: str
    config: AppConfig
    api_key: str = ""
    approve: Callable[[str, str], bool] | None = None
    cancel: threading.Event = field(default_factory=threading.Event)


@dataclass
class ControllerResult:
    status: str = "failed"
    output_dir: str = ""
    outcome: RunOutcome | None = None
    report_paths: dict = field(default_factory=dict)
    error: str = ""
    coverage: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "output_dir": self.output_dir,
            "report_paths": self.report_paths,
            "error": self.error,
            "coverage": self.coverage,
            "outcome": self.outcome.as_dict() if self.outcome else None,
        }


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return slug or "generated-project"


class Controller:
    def __init__(self, emit: Callable[[Event], None] | None = None,
                 parser: DocumentParser | None = None) -> None:
        self.emit = emit or (lambda event: None)
        self.parser = parser or DocumentParser()
        self._phases: list[dict] = []
        self._started_at = 0.0

    # ------------------------------------------------------------------ #
    def run(self, request: RunRequest) -> ControllerResult:
        self._started_at = time.time()
        self._phases = []
        result = ControllerResult()
        self._active_provider: LLMProvider | None = None
        try:
            return self._run_inner(request, result)
        except ControllerError as exc:
            result.status = "failed"
            result.error = exc.message
            self._emit("error", exc.message, "error", code=exc.code)
            return result
        except Exception as exc:  # noqa: BLE001 - controller must return a result
            result.status = "failed"
            result.error = f"{type(exc).__name__}: {exc}"
            self._emit("error", f"未处理异常：{type(exc).__name__}: {exc}", "error")
            return result
        finally:
            provider = getattr(self, "_active_provider", None)
            if provider is not None:
                try:
                    provider.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------ #
    def _run_inner(self, request: RunRequest, result: ControllerResult) -> ControllerResult:
        config = request.config
        redactor = SecretRedactor([request.api_key] if request.api_key else [])
        cancel = request.cancel
        provider: LLMProvider | None = None

        self._phase("VALIDATING_INPUT", "校验输入文档与输出目录")
        doc_path = Path(request.doc_path).expanduser()
        view_path = Path(request.view_path).expanduser()
        if not doc_path.is_file():
            raise ControllerError("doc_missing", f"架构文档不存在：{doc_path}")
        if not view_path.is_file():
            raise ControllerError("view_missing", f"UML 视图文档不存在：{view_path}")
        if doc_path.resolve() == view_path.resolve():
            raise ControllerError("same_input", "两份输入文档不能是同一个文件。")
        if not config.mock_mode and not request.api_key:
            raise ControllerError("missing_api_key", "真实模式需要 DeepSeek API Key；也可勾选 Mock 模式。")
        output_root = self._prepare_output(Path(request.output_dir).expanduser())
        result.output_dir = str(output_root)

        session = SessionStore(
            output_root,
            state_dir_name=config.state_dir_name,
            redactor=redactor,
        )
        session.write_json("config.json", self._safe_config(config))

        self._phase("NORMALIZING", "解析架构文档与 UML 视图")
        try:
            doc = self.parser.parse(doc_path, "architecture")
            view = self.parser.parse(view_path, "view")
        except DocumentError as exc:
            raise ControllerError(exc.code, exc.message) from exc
        requirements = RequirementNormalizer().normalize(doc, view)
        session.write_json("requirements.json", requirements.model_dump())
        session.write_text("requirements-summary.md", requirements.to_prompt_summary())
        self._emit("log", f"解析完成：{len(view.diagrams)} 个 PlantUML 块，"
                          f"{len(requirements.requirements)} 条需求，"
                          f"{len(requirements.conflicts)} 个冲突。", "success",
                   data={"diagrams": len(view.diagrams), "requirements": len(requirements.requirements)})
        result.coverage = requirements.coverage()

        policy = WorkspacePolicy(
            output_root,
            max_file_bytes=config.max_file_bytes,
            protected_paths=[doc_path, view_path],
            state_dir=config.state_dir_name,
        )
        files = FileRegistry()
        registry = build_registry(config)

        self._phase("PLANNING", "生成结构化实施计划")
        if config.mock_mode:
            plan = build_sample_plan(requirements)
            self._emit("log", "Mock 模式：使用内置 Space Fractions 计划（真实工具落盘）。", "info")
        else:
            assert request.api_key
            provider = DeepSeekProvider(
                request.api_key, config, redactor,
                on_retry=lambda attempt, delay, code, message: self._emit(
                    "log", f"API {code}，第 {attempt} 次退避 {delay:.1f}s：{message}", "warn"
                ),
            )
            self._active_provider = provider
            try:
                plan = Planner(provider, config, self.emit, cancel, redactor).generate(requirements)
            except ProviderError as exc:
                if exc.code in {"auth", "permission"}:
                    raise ControllerError(exc.code, exc.message) from exc
                self._emit("log", f"模型计划失败（{exc.code}），使用确定性回退计划。", "warn")
                plan = fallback_plan(requirements)
            except PlanError as exc:
                self._emit("log", f"计划不可用（{exc.message[:160]}），使用确定性回退计划。", "warn")
                plan = fallback_plan(requirements)
        issues = validate_plan(plan, requirements)
        if issues:
            self._emit("log", "计划校验警告：" + "；".join(issues[:5]), "warn")
        session.write_json("plan.json", plan.model_dump())
        self._emit("log", f"计划：{len(plan.tasks)} 个任务，{len(plan.files)} 个文件。", "success")
        self._emit("plan", "实施计划已生成", data={
            "tasks": [task.model_dump() for task in plan.tasks],
            "files": [file.path for file in plan.files],
        })

        if provider is None:
            provider = MockProvider(build_mock_script(requirements), config, self.emit)
            self._active_provider = provider

        delivery = DeliveryValidator(policy, requirements, plan, config, files)
        orchestration_result: RunOutcome | None = None
        static_checks: list[dict] = []
        test_results: list[dict] = []
        errors: list[str] = []

        def completion() -> tuple[bool, list[str]]:
            report = delivery.evaluate()
            return report.ok, list(report.missing)

        self._phase("IMPLEMENTING", "Agent 正在写入项目文件")
        orchestrator = AgentOrchestrator(
            provider=provider,
            registry=registry,
            config=config,
            session=session,
            requirements=requirements,
            files=files,
            emit=self.emit,
            cancel=cancel,
            approve=request.approve,
            plan_summary=plan.to_prompt_summary(),
            completion_check=completion,
            redactor=redactor,
            policy=policy,
        )
        orchestration_result = orchestrator.run()
        errors.extend(orchestration_result.errors)
        result.outcome = orchestration_result

        # ---------------------------------------------------------- repair
        repair_round = 0
        while (
            not cancel.is_set()
            and orchestration_result.status not in {"cancelled"}
            and repair_round < config.max_repair_rounds
        ):
            report = delivery.evaluate()
            if report.ok:
                break
            repair_round += 1
            self._phase("REPAIRING", f"第 {repair_round}/{config.max_repair_rounds} 轮修复")
            if config.mock_mode:
                self._emit("log", "Mock 模式没有额外修复脚本，跳过修复。", "warn")
                break
            footer = (
                "## 修复轮次\n"
                f"本地验收未通过（第 {repair_round} 轮）。请先 list_files/read_file 检查现有文件，"
                "只修复缺失或错误的部分，不要重复创建已完成的文件。\n\n缺失项：\n- "
                + "\n- ".join(report.missing[:15])
            )
            repair_orchestrator = AgentOrchestrator(
                provider=provider,
                registry=registry,
                config=config,
                session=session,
                requirements=requirements,
                files=files,
                emit=self.emit,
                cancel=cancel,
                approve=request.approve,
                plan_summary=plan.to_prompt_summary(),
                completion_check=completion,
                redactor=redactor,
                policy=policy,
                initial_footer=footer,
            )
            repair_outcome = repair_orchestrator.run()
            self._merge_outcome(orchestration_result, repair_outcome)
            errors.extend(repair_outcome.errors)
            self._emit("log", f"修复轮 {repair_round} 结束：{repair_outcome.status}", "info")
            if repair_outcome.status == "completed":
                break

        # ------------------------------------------------------- verify
        self._phase("VERIFYING", "静态检查与本地测试")
        ensure_assumptions_file(policy, requirements)
        delivery.apply()
        context = orchestrator.context
        context.step = orchestration_result.steps
        inspection = registry.execute(
            "inspect_project",
            {"checks": ["structure", "json", "python", "js", "links", "requirements"]},
            context,
        )
        static_checks = inspection.get("checks", [])
        static_failed = any(check.get("status") == "fail" for check in static_checks)
        self._emit("log", "静态检查：" + ", ".join(
            f"{check['id']}={check['status']}" for check in static_checks
        ), "success" if not static_failed else "warn")

        test_results = self._maybe_run_tests(config, request, registry, context, output_root)
        tests_failed = any(result.get("passed") is False for result in test_results)
        if tests_failed:
            errors.append("自动化测试未通过；报告保留原始输出，完成状态降级为 partial。")

        # ------------------------------------------------------- report
        self._phase("REPORTING", "生成报告与追溯矩阵")
        delivery_report = delivery.evaluate()
        builder = ReportBuilder(
            policy=policy,
            requirements=requirements,
            plan=plan,
            outcome=orchestration_result,
            delivery=delivery_report,
            config=config,
            session=session,
            files=files,
            started_at=self._started_at,
            phases=self._phases,
            mode="Mock（内置样例）" if config.mock_mode else "DeepSeek 真实 API",
            static_checks=static_checks,
            test_results=test_results,
            inputs=[doc.stats, view.stats],
            errors=errors,
        )
        paths = builder.write()
        result.report_paths = paths
        result.coverage = delivery_report.coverage

        if orchestration_result.status == "cancelled":
            final_status = "cancelled"
        elif tests_failed:
            final_status = "partial"
        elif delivery_report.ok and not static_failed:
            final_status = "completed"
        elif delivery_report.files:
            final_status = "partial"
        else:
            final_status = "failed"
        if orchestration_result.status == "budget_exhausted" and final_status == "completed":
            final_status = "partial"
        result.status = final_status
        result.error = "" if final_status == "completed" else "; ".join(delivery_report.missing[:5])

        session.write_json("controller_result.json", result.as_dict())
        session.close()
        label = {
            "completed": "完成",
            "partial": "部分完成",
            "cancelled": "已取消",
            "failed": "失败",
            "budget_exhausted": "预算耗尽",
        }.get(final_status, final_status)
        self._phase("COMPLETED" if final_status == "completed" else "PARTIAL", f"运行结束：{label}")
        self._emit("log", f"生成完成：{final_status}，输出目录 {output_root}", "success")
        self._emit("report", "报告已生成", paths=paths, status=final_status)
        return result

    # ------------------------------------------------------------------ #
    @staticmethod
    def _prepare_output(base: Path) -> Path:
        if base.exists() and not base.is_dir():
            raise ControllerError("output_not_dir", f"输出路径不是目录：{base}")
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ControllerError("output_error", f"无法创建输出目录：{exc}") from exc
        try:
            non_empty = any(base.iterdir())
        except OSError as exc:
            raise ControllerError("output_error", f"无法读取输出目录：{exc}") from exc
        if not non_empty:
            return base.resolve()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        candidate = base / f"generated-{stamp}"
        suffix = 1
        while candidate.exists():
            suffix += 1
            candidate = base / f"generated-{stamp}-{suffix}"
        try:
            candidate.mkdir(parents=True)
        except OSError as exc:
            raise ControllerError("output_error", f"无法创建子目录：{exc}") from exc
        return candidate.resolve()

    @staticmethod
    def _safe_config(config: AppConfig) -> dict:
        return {
            "model": config.model,
            "base_url": config.base_url,
            "reasoning_effort": config.reasoning_effort,
            "max_agent_steps": config.max_agent_steps,
            "max_repair_rounds": config.max_repair_rounds,
            "max_total_tokens": config.max_total_tokens,
            "max_cost_usd": config.max_cost_usd,
            "allow_command_execution": config.allow_command_execution,
            "mock_mode": config.mock_mode,
        }

    @staticmethod
    def _merge_outcome(target: RunOutcome, extra: RunOutcome) -> None:
        target.steps += extra.steps
        target.tool_calls += extra.tool_calls
        target.usage.merge(extra.usage)
        target.elapsed_s += extra.elapsed_s
        target.compactions += extra.compactions
        if extra.status == "completed":
            target.status = "completed"
        target.finish_summary = extra.finish_summary or target.finish_summary

    def _maybe_run_tests(self, config: AppConfig, request: RunRequest, registry,
                         context, output_root: Path) -> list[dict]:
        if not config.allow_command_execution:
            self._emit("log", "未启用命令执行：测试标记为 not run。", "info")
            return []
        profile = None
        if (output_root / "package.json").exists():
            profile = "node"
        elif (output_root / "requirements.txt").exists() or (output_root / "pyproject.toml").exists():
            profile = "pytest"
        if profile is None:
            return []
        approval = request.approve
        if approval is None:
            self._emit("log", "没有测试授权回调：测试标记为 not run。", "warn")
            return []
        tool_result = registry.execute("run_tests", {"predefined_profile": profile}, context)
        if not tool_result.get("ok"):
            self._emit("log", "测试未运行：" + tool_result.get("summary", ""), "warn")
            return []
        test_result = {
            "profile": tool_result.get("profile", profile),
            "exit_code": tool_result.get("exit_code"),
            "passed": tool_result.get("passed"),
            "duration_s": tool_result.get("duration_s"),
            "output": tool_result.get("output", ""),
            "timed_out": tool_result.get("timed_out", False),
        }
        self._emit("log", tool_result.get("summary", "测试结束"),
                   "success" if tool_result.get("passed") else "warn")
        return [test_result]

    # ------------------------------------------------------------------ #
    def _phase(self, phase: str, message: str) -> None:
        self._phases.append({
            "phase": phase,
            "message": message,
            "at_s": round(time.time() - self._started_at, 2),
        })
        self._emit("phase", message, "info", phase=phase,
                   phases=self._phases, elapsed=round(time.time() - self._started_at, 1))

    def _emit(self, kind: str, message: str, level: str = "info", data: dict | None = None,
              **kwargs) -> None:
        payload = dict(data or {})
        payload.update(kwargs)
        try:
            self.emit(Event(kind=kind, message=message, level=level, data=payload))
        except Exception:
            pass
