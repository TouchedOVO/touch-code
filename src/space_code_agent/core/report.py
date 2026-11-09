"""Generation report, traceability matrix and machine-readable manifest."""

from __future__ import annotations

import csv
import io
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..app.config import AppConfig
from ..agent.orchestrator import RunOutcome
from ..agent.planner import ProjectPlan
from ..security.policy import WorkspacePolicy
from .delivery import DeliveryReport, DeliveryValidator
from .requirements import NormalizedRequirements
from .session import FileRegistry, SessionStore


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / 1024 / 1024:.2f} MB"


class ReportBuilder:
    def __init__(
        self,
        *,
        policy: WorkspacePolicy,
        requirements: NormalizedRequirements,
        plan: ProjectPlan,
        outcome: RunOutcome,
        delivery: DeliveryReport,
        config: AppConfig,
        session: SessionStore,
        files: FileRegistry,
        started_at: float,
        phases: list[dict],
        mode: str,
        static_checks: list[dict] | None = None,
        test_results: list[dict] | None = None,
        inputs: list[dict] | None = None,
        errors: list[str] | None = None,
    ) -> None:
        self.policy = policy
        self.requirements = requirements
        self.plan = plan
        self.outcome = outcome
        self.delivery = delivery
        self.config = config
        self.session = session
        self.files = files
        self.started_at = started_at
        self.phases = phases
        self.mode = mode
        self.static_checks = static_checks or []
        self.test_results = test_results or []
        self.inputs = inputs or []
        self.errors = errors or []

    # ------------------------------------------------------------------ #
    def write(self) -> dict[str, str]:
        validator = DeliveryValidator(self.policy, self.requirements, self.plan, self.config, self.files)
        validator.apply()
        rows = validator.traceability_rows()
        report_path = self.policy.write_text_atomic(
            "GENERATION_REPORT.md", self._report_markdown(rows), overwrite=True,
            max_bytes=4 * 1024 * 1024,
        )["path"]
        csv_path = self.policy.write_text_atomic(
            "traceability_matrix.csv", self._traceability_csv(rows), overwrite=True,
            max_bytes=1024 * 1024,
        )["path"]
        manifest = self._manifest(rows)
        manifest_path = self.policy.write_text_atomic(
            "run_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
            overwrite=True, max_bytes=4 * 1024 * 1024,
        )["path"]
        self.session.write_json("run_manifest.json", manifest)
        self.session.write_json("traceability.json", rows)
        return {
            "report": report_path,
            "traceability": csv_path,
            "manifest": manifest_path,
        }

    # ------------------------------------------------------------------ #
    def _report_markdown(self, rows: list[dict]) -> str:
        coverage = self.delivery.coverage
        duration = time.time() - self.started_at
        status_label = {
            "completed": "COMPLETED",
            "partial": "PARTIAL",
            "cancelled": "CANCELLED",
            "budget_exhausted": "BUDGET_EXHAUSTED",
            "failed": "FAILED",
        }.get(self.outcome.status, self.outcome.status.upper())
        lines: list[str] = [
            f"# {self.requirements.project_name} — Code Agent 生成报告",
            "",
            f"**状态：{status_label}**  ",
            f"**生成时间：** {datetime.now().astimezone().isoformat(timespec='seconds')}  ",
            f"**运行模式：** {self.mode}  ",
            f"**模型：** {self.config.model}（reasoning effort={self.config.reasoning_effort}）  ",
            f"**输出目录：** `{self.policy.root_str}`  ",
            f"**总耗时：** {duration:.1f}s  ",
            f"**Agent 步数 / 工具调用：** {self.outcome.steps} / {self.outcome.tool_calls}  ",
            f"**需求覆盖率：** {coverage.get('implemented', 0)}/{coverage.get('total', 0)} "
            f"（{coverage.get('percent', 0)}%），partial={coverage.get('partial', 0)}，"
            f"missing={coverage.get('missing', 0)}  ",
            "",
            "> 本报告由本地验收器依据真实磁盘文件、工具执行记录与静态检查生成。"
            "模型文本自述不作为完成依据；未运行的测试明确标记为 not run。",
            "",
            "## 1. 执行摘要",
            "",
            self.plan.summary or "（计划未提供摘要）",
            "",
        ]
        if self.errors:
            lines.append("**运行中的错误/告警：**")
            lines.extend(f"- {_md(error)}" for error in self.errors)
            lines.append("")
        if self.delivery.missing:
            lines.append("**本地验收未通过项：**")
            lines.extend(f"- {_md(item)}" for item in self.delivery.missing)
            lines.append("")

        if self.phases:
            lines.extend(["### 1.1 执行阶段", "", "| 阶段 | 说明 | 相对时间 |", "|---|---|---:|"])
            for phase in self.phases:
                lines.append(
                    f"| {phase.get('phase', '')} | {_md(phase.get('message', ''))} | "
                    f"{phase.get('at_s', 0)}s |"
                )
            lines.append("")

        lines.extend([
            "## 2. 输入与解析",
            "",
            "| 文档 | 行数 | 章节 | 表格 | 代码块 | PlantUML | SHA-256 |",
            "|---|---:|---:|---:|---:|---:|---|",
        ])
        for item in self.inputs:
            lines.append(
                f"| {_md(item.get('path'))} | {item.get('lines', 0)} | {item.get('sections', 0)} | "
                f"{item.get('tables', 0)} | {item.get('code_blocks', 0)} | "
                f"{item.get('plantuml_blocks', 0)} | `{str(item.get('sha256', ''))[:16]}` |"
            )
        stats = self.requirements.summary_counts()
        lines.extend([
            "",
            f"- 需求：{stats['requirements']} 条（显式 {stats['explicit']}，图推导 {stats['derived']}）；"
            f"组件：{stats['components']}；架构视图：{stats['diagrams']}；"
            f"冲突：{stats['conflicts']}；假设：{stats['assumptions']}。",
            "- 架构视图清单：",
        ])
        for diagram in self.requirements.diagrams:
            lines.append(
                f"  - `{diagram.id}`（{diagram.kind}，{diagram.source_doc}:{diagram.line_start}，"
                f"{len(diagram.elements)} 个元素）"
            )
        if self.requirements.conflicts:
            lines.extend(["", "### 文档冲突与处置", "", "| ID | 严重度 | 冲突 | 处置 |", "|---|---|---|---|"])
            for conflict in self.requirements.conflicts:
                lines.append(
                    f"| {conflict.id} | {conflict.severity} | {_md(conflict.message)} | "
                    f"{_md(conflict.resolution)} |"
                )

        lines.extend([
            "",
            "## 3. 需求覆盖矩阵",
            "",
            "| 需求 | 类型 | 标题 | 置信度 | 状态 | 实现文件 | 测试 |",
            "|---|---|---|---|---|---|---|",
        ])
        for row in rows:
            lines.append(
                f"| {row['requirement_id']} | {row['kind']} | {_md(row['title'])} | "
                f"{row['confidence']} | {row['status']} | {_md(row['files']) or '—'} | "
                f"{_md(row['tests']) or '—'} |"
            )
        lines.extend([
            "",
            "完整机器可读矩阵见 `traceability_matrix.csv`；逐文件哈希见 `run_manifest.json`。",
            "",
            "## 4. 交付物清单",
            "",
            "| 文件 | 大小 | SHA-256 |",
            "|---|---:|---|",
        ])
        for entry in sorted(self.delivery.files, key=lambda item: item["path"]):
            record = self.files.records.get(entry["path"])
            sha = record.sha256[:24] if record else "（未由 Agent 写入）"
            lines.append(f"| `{_md(entry['path'])}` | {_bytes(entry['size'])} | `{sha}` |")
        lines.append(f"\n共 {len(self.delivery.files)} 个文件，"
                     f"其中 Agent 记录写入 {len(self.files.records)} 个，"
                     f"累计 {_bytes(self.files.total_bytes())}。")

        lines.extend([
            "",
            "## 5. 验证结果",
            "",
            "### 5.1 静态检查",
            "",
            "| 检查 | 状态 | 详情 |",
            "|---|---|---|",
        ])
        if self.static_checks:
            for check in self.static_checks:
                detail = json.dumps(check.get("details", {}), ensure_ascii=False)
                lines.append(f"| {check.get('id')} | {check.get('status')} | {_md(detail[:400])} |")
        else:
            lines.append("| — | not run | 未执行静态检查 |")
        lines.extend(["", "### 5.2 自动化测试", ""])
        if not self.test_results:
            lines.append("**未运行（not run）。** 原因：未启用命令执行、未找到 Node/Python 测试入口，"
                         "或用户未授权。文件存在不等于测试通过。")
        else:
            for result in self.test_results:
                lines.append(
                    f"- `{result.get('profile', 'test')}`：exit={result.get('exit_code')}，"
                    f"passed={result.get('passed')}，耗时 {result.get('duration_s', '?')}s"
                )
                output = (result.get("output") or "").strip()
                if output:
                    lines.extend(["", "```text", output[:3000], "```", ""])

        lines.extend(["", "## 6. 假设与重大偏离", ""])
        for assumption in self.requirements.assumptions:
            lines.append(f"- **{assumption.id}**（{assumption.category}）：{assumption.text}")
        if self.plan.deviations:
            lines.extend(["", "### 计划中的偏离", ""])
            for deviation in self.plan.deviations:
                lines.append(f"- **{deviation.decision}**：{deviation.reason}；影响：{deviation.impact}")

        usage = self.outcome.usage
        lines.extend([
            "",
            "## 7. 用量与预算",
            "",
            f"- 模型请求：{usage.requests} 次",
            f"- 输入 tokens：{usage.input_tokens}（缓存命中 {usage.cached_tokens}）",
            f"- 输出 tokens：{usage.output_tokens}（推理 tokens {usage.reasoning_tokens}）",
            f"- 估算费用：${usage.cost_usd(self.config):.4f}（价格参数可配置，非账单依据）",
            f"- 预算：最多 {self.config.max_agent_steps} 步 / "
            f"{self.config.max_total_tokens} tokens / ${self.config.max_cost_usd} / "
            f"{self.config.max_wall_seconds / 60:.0f} 分钟",
            "",
            "## 8. 风险与未解决问题",
            "",
        ])
        if self.plan.risks:
            lines.extend(f"- {_md(risk)}" for risk in self.plan.risks)
        else:
            lines.append("- 未登记额外风险。")
        lines.extend([
            "- 生成的示例项目用于教学演示，不应视为生产级微服务；"
            "Redis/RabbitMQ/Elasticsearch/Kubernetes/Istio/Vault/Terraform 未纳入演示依赖。",
            "- 真实 DeepSeek API 端到端运行需用户提供有效 API Key；Mock 模式只验证工具与编排回路。",
            "",
            "## 9. 追溯信息",
            "",
            f"- 会话状态：`{self.session.dir}`",
            f"- 工具日志：`{self.session.dir / 'tools.jsonl'}`",
            f"- 事件日志：`{self.session.dir / 'events.jsonl'}`",
            f"- 归一化需求：`{self.session.dir / 'requirements.json'}`",
            f"- 实施计划：`{self.session.dir / 'plan.json'}`",
            "",
        ])
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------ #
    @staticmethod
    def _traceability_csv(rows: list[dict]) -> str:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=[
            "requirement_id", "kind", "title", "confidence", "status",
            "components", "files", "tests", "evidence", "source",
        ], lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
        return "\ufeff" + buffer.getvalue()

    def _manifest(self, rows: list[dict]) -> dict:
        usage = self.outcome.usage
        return {
            "schema_version": "1.0",
            "run": {
                "status": self.outcome.status,
                "mode": self.mode,
                "started_at": self.started_at,
                "finished_at": time.time(),
                "duration_s": round(time.time() - self.started_at, 2),
                "steps": self.outcome.steps,
                "tool_calls": self.outcome.tool_calls,
                "phases": self.phases,
                "errors": self.errors + self.outcome.errors,
                "missing": self.delivery.missing,
                "session_id": self.session.session_id,
                "output_dir": self.policy.root_str,
            },
            "model": {
                "name": self.config.model,
                "base_url": self.config.base_url,
                "reasoning_effort": self.config.reasoning_effort,
                "mock": self.config.mock_mode,
            },
            "inputs": self.inputs,
            "requirements": [req.model_dump() for req in self.requirements.requirements],
            "diagrams": [diagram.model_dump() for diagram in self.requirements.diagrams],
            "conflicts": [conflict.model_dump() for conflict in self.requirements.conflicts],
            "assumptions": [assumption.model_dump() for assumption in self.requirements.assumptions],
            "plan": self.plan.model_dump(),
            "coverage": self.delivery.coverage,
            "traceability": rows,
            "validation": {
                "static": self.static_checks,
                "tests": self.test_results,
                "delivery": self.delivery.as_dict(),
            },
            "usage": {
                **usage.as_dict(),
                "estimated_cost_usd": round(usage.cost_usd(self.config), 6),
            },
            "files": [
                {
                    "path": entry["path"],
                    "bytes": entry["size"],
                    "sha256": self.files.records[entry["path"]].sha256
                    if entry["path"] in self.files.records else "",
                }
                for entry in sorted(self.delivery.files, key=lambda item: item["path"])
            ],
            "artifacts": {
                "report": "GENERATION_REPORT.md",
                "traceability": "traceability_matrix.csv",
                "manifest": "run_manifest.json",
            },
        }
