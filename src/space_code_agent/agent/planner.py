"""Planning phase: turn normalized requirements into a structured ProjectPlan."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from ..app.config import AppConfig
from ..app.events import Event
from ..core.requirements import NormalizedRequirements
from ..providers.base import LLMProvider, ProviderError
from .prompts import PLAN_SYSTEM_PROMPT, build_plan_message


class PlanFile(BaseModel):
    path: str
    purpose: str = ""
    task_id: str = ""
    requirement_ids: list[str] = Field(default_factory=list)


class PlanTask(BaseModel):
    id: str
    title: str
    description: str = ""
    depends_on: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)


class Deviation(BaseModel):
    decision: str
    reason: str = ""
    impact: str = ""


class ProjectPlan(BaseModel):
    project_name: str = "Generated Project"
    summary: str = ""
    architecture_style: str = "modular monolith"
    stack: dict[str, str] = Field(default_factory=dict)
    deviations: list[Deviation] = Field(default_factory=list)
    tasks: list[PlanTask] = Field(default_factory=list)
    files: list[PlanFile] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    source: str = "model"

    def to_prompt_summary(self, max_chars: int = 12000) -> str:
        lines = [
            f"项目：{self.project_name}",
            f"摘要：{self.summary}",
            f"风格：{self.architecture_style}",
            "技术栈：" + ", ".join(f"{k}={v}" for k, v in self.stack.items()),
            "",
            "### 任务",
        ]
        for task in self.tasks:
            lines.append(f"- {task.id} {task.title}（依赖: {', '.join(task.depends_on) or '无'}；"
                         f"需求: {', '.join(task.requirement_ids) or '无'}）")
        lines.append("")
        lines.append("### 文件树")
        for file in self.files:
            lines.append(f"- {file.path} — {file.purpose}"
                         + (f" [{', '.join(file.requirement_ids)}]" if file.requirement_ids else ""))
        if self.verification_steps:
            lines.append("")
            lines.append("### 验证步骤")
            for step in self.verification_steps:
                lines.append(f"- {step}")
        text = "\n".join(lines)
        return text[:max_chars]

    def path_map(self) -> dict[str, PlanFile]:
        return {file.path: file for file in self.files}


class PlanError(Exception):
    def __init__(self, message: str, raw: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.raw = raw[:2000]


REQUIRED_FILE_HINTS = {
    "readme": "README.md",
    "manifest": ("package.json", "requirements.txt", "pyproject.toml"),
    "assumptions": "docs/ASSUMPTIONS.md",
}


def validate_plan(plan: ProjectPlan, requirements: NormalizedRequirements) -> list[str]:
    issues: list[str] = []
    paths = [file.path.replace("\\", "/").strip("/") for file in plan.files]
    if len(paths) != len(set(paths)):
        issues.append("计划中存在重复文件路径。")
    for path in paths:
        if path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", path) or ".." in path.split("/"):
            issues.append(f"计划包含不安全路径：{path}")
    lower = {path.lower() for path in paths}
    if "readme.md" not in lower:
        issues.append("计划缺少 README.md。")
    if not any(Path(path).name.lower() in REQUIRED_FILE_HINTS["manifest"] for path in lower):
        issues.append("计划缺少依赖声明（package.json / requirements.txt / pyproject.toml）。")
    if "docs/assumptions.md" not in lower:
        issues.append("计划缺少 docs/ASSUMPTIONS.md。")
    if not any(path.startswith("tests/") or "/tests/" in path or ".test." in path for path in lower):
        issues.append("计划缺少测试文件。")
    known = {req.id for req in requirements.requirements}
    referenced: set[str] = set()
    for file in plan.files:
        referenced.update(file.requirement_ids)
    unknown = sorted(referenced - known)
    if unknown:
        issues.append("计划引用了未知需求 ID：" + ", ".join(unknown[:8]))
    core = {req.id for req in requirements.requirements if req.kind == "FR"}
    unmapped = sorted(core - referenced)
    if unmapped:
        issues.append("计划未映射 FR：" + ", ".join(unmapped[:8]))
    if len(plan.files) < 5:
        issues.append("计划文件数量过少（<5）。")
    return issues


class Planner:
    def __init__(self, provider: LLMProvider, config: AppConfig,
                 emit: Callable[[Event], None] | None = None,
                 cancel: threading.Event | None = None,
                 redactor: Any = None) -> None:
        self.provider = provider
        self.config = config
        self.emit = emit or (lambda event: None)
        self.cancel = cancel or threading.Event()
        self.redactor = redactor

    def generate(self, requirements: NormalizedRequirements) -> ProjectPlan:
        prompt = build_plan_message(requirements.to_prompt_summary(max_chars=12000))
        response_format = {
            "type": "json_schema",
            "name": "project_plan",
            "schema": ProjectPlan.model_json_schema(),
            "strict": False,
        }
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self.provider.create(
                    instructions=PLAN_SYSTEM_PROMPT,
                    input_items=[{"role": "user", "content": prompt}],
                    tools=None,
                    max_output_tokens=self.config.plan_max_output_tokens,
                    response_format=response_format,
                    cancellation=self.cancel,
                )
                plan = self._parse(response.text)
                issues = validate_plan(plan, requirements)
                if issues:
                    self._emit("log", "计划校验未通过：" + "；".join(issues[:5]), "warn")
                    prompt += "\n\n上一次计划存在以下问题，请修正并重新输出完整 JSON：\n- " + "\n- ".join(issues)
                    last_error = PlanError("; ".join(issues))
                    continue
                plan.source = "model"
                self._emit("log", f"计划生成完成：{len(plan.tasks)} 个任务，{len(plan.files)} 个文件。", "success")
                return plan
            except ProviderError as exc:
                if exc.code in {"auth", "permission", "invalid_request"}:
                    raise
                last_error = exc
                self._emit("log", f"计划调用失败（{exc.code}），准备重试/回退。", "warn")
            except (PlanError, ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                self._emit("log", f"计划解析失败：{str(exc)[:200]}", "warn")
        raise PlanError(f"模型计划生成失败：{last_error}")

    @staticmethod
    def _parse(text: str) -> ProjectPlan:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise PlanError("模型回复中没有 JSON 对象。", cleaned)
        data = json.loads(cleaned[start:end + 1])
        return ProjectPlan.model_validate(data)

    def _emit(self, kind: str, message: str, level: str = "info") -> None:
        try:
            self.emit(Event(kind=kind, message=message, level=level))
        except Exception:
            pass


def fallback_plan(requirements: NormalizedRequirements) -> ProjectPlan:
    """Deterministic plan used when the model planning call fails.

    It is intentionally generic; the implementation loop still has to create
    every listed file and pass the local delivery validator.
    """
    req_ids = [req.id for req in requirements.requirements]
    core = [req.id for req in requirements.requirements if req.kind == "FR"]
    return ProjectPlan(
        project_name=requirements.project_name,
        summary=f"为 {requirements.project_name} 生成的模块化实现（模型计划失败后的确定性回退）。",
        architecture_style="modular monolith (documented deviation)",
        stack={"language": "javascript", "runtime": "Node.js >=20", "framework": "node:http",
               "persistence": "in-memory with optional PostgreSQL adapter", "testing": "node:test"},
        deviations=[Deviation(
            decision="计划阶段回退为模块化单体",
            reason="模型未返回可校验的结构化计划。",
            impact="服务边界保留在目录与模块中，但不部署独立容器。",
        )],
        tasks=[
            PlanTask(id="T1", title="文档与依赖骨架", description="README、依赖声明、假设",
                     requirement_ids=req_ids[:2], acceptance=["文件存在且可读"]),
            PlanTask(id="T2", title="核心业务实现", description="按组件实现领域逻辑与接口",
                     depends_on=["T1"], requirement_ids=core, acceptance=["核心流程可通过静态检查"]),
            PlanTask(id="T3", title="测试与验证", description="单元测试与端到端测试",
                     depends_on=["T2"], requirement_ids=core, acceptance=["测试文件存在"]),
        ],
        files=[
            PlanFile(path="README.md", purpose="项目说明与运行方式", task_id="T1", requirement_ids=req_ids),
            PlanFile(path="package.json", purpose="依赖与测试脚本", task_id="T1", requirement_ids=[]),
            PlanFile(path="docs/ASSUMPTIONS.md", purpose="假设与偏离记录", task_id="T1", requirement_ids=req_ids),
            PlanFile(path="docs/architecture-summary.md", purpose="架构摘要", task_id="T1",
                     requirement_ids=req_ids),
            PlanFile(path="src/index.js", purpose="应用入口", task_id="T2", requirement_ids=core),
            PlanFile(path="src/domain.js", purpose="领域逻辑", task_id="T2", requirement_ids=core),
            PlanFile(path="tests/domain.test.js", purpose="领域单元测试", task_id="T3", requirement_ids=core),
            PlanFile(path="tests/e2e/flow.test.js", purpose="端到端流程测试", task_id="T3",
                     requirement_ids=core),
        ],
        verification_steps=["node --check 所有 JS 文件", "node --test"],
        assumptions=[assumption.text for assumption in requirements.assumptions],
        risks=["回退计划可能与原架构文档的微服务部署不完全一致。"],
        source="fallback",
    )
