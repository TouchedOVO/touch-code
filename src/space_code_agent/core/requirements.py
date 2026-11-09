"""Pydantic normalized requirement model plus conflict/assumption handling."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .document_parser import ComponentInfo, Diagram, ParsedDocument, ParsedRequirement

Confidence = Literal["explicit", "diagram-derived", "inferred", "assumed"]


class SourceRef(BaseModel):
    document: str
    line: int = 0
    section: str = ""
    sha256: str = ""


class RequirementItem(BaseModel):
    id: str
    kind: str
    title: str
    description: str = ""
    source: SourceRef
    confidence: Confidence = "explicit"
    diagrams: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    test_types: list[str] = Field(default_factory=list)
    status: str = "unmapped"          # unmapped | planned | implemented | partial | missing
    files: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    evidence: str = ""


class DiagramInfo(BaseModel):
    id: str
    kind: str
    source_doc: str
    line_start: int = 0
    elements: list[str] = Field(default_factory=list)
    relation_count: int = 0
    message_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    raw_sha256: str = ""


class ComponentModel(BaseModel):
    name: str
    responsibilities: str = ""
    technologies: dict[str, str] = Field(default_factory=dict)
    source: SourceRef | None = None
    inferred: bool = False


class Assumption(BaseModel):
    id: str
    text: str
    category: str = "general"
    source: str = "agent"
    impact: str = ""


class Conflict(BaseModel):
    id: str
    severity: Literal["low", "medium", "high"] = "medium"
    message: str
    evidence: str = ""
    resolution: str = ""


class NormalizedRequirements(BaseModel):
    project_name: str = "Generated Project"
    target: str = ""
    style: str = "modular monolith"
    deployment: str = ""
    requirements: list[RequirementItem] = Field(default_factory=list)
    diagrams: list[DiagramInfo] = Field(default_factory=list)
    components: list[ComponentModel] = Field(default_factory=list)
    tech_stack: dict[str, list[str]] = Field(default_factory=dict)
    assumptions: list[Assumption] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    inputs: list[dict] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)

    # -- convenience ------------------------------------------------------
    def requirement(self, req_id: str) -> RequirementItem | None:
        return next((r for r in self.requirements if r.id == req_id), None)

    def explicit_requirements(self) -> list[RequirementItem]:
        return [r for r in self.requirements if r.confidence == "explicit"]

    def derived_requirements(self) -> list[RequirementItem]:
        return [r for r in self.requirements if r.confidence == "diagram-derived"]

    def coverage(self) -> dict:
        total = len(self.requirements)
        implemented = sum(1 for r in self.requirements if r.status == "implemented")
        partial = sum(1 for r in self.requirements if r.status == "partial")
        missing = sum(1 for r in self.requirements if r.status in {"missing", "unmapped"})
        return {
            "total": total,
            "implemented": implemented,
            "partial": partial,
            "missing": missing,
            "percent": round(100.0 * implemented / total, 1) if total else 0.0,
        }

    def to_prompt_summary(self, max_chars: int = 14000) -> str:
        lines: list[str] = [
            "## 归一化架构输入",
            f"项目：{self.project_name}",
            f"目标：{self.target or '（未给出）'}",
            f"架构风格：{self.style or '（未给出）'}；部署：{self.deployment or '（未给出）'}",
            "",
            "### 需求清单",
        ]
        for req in self.requirements:
            lines.append(
                f"- {req.id} [{req.kind}/{req.confidence}] {req.title}"
                + (f" | 组件: {', '.join(req.components)}" if req.components else "")
                + (f" | 视图: {', '.join(req.diagrams)}" if req.diagrams else "")
            )
        lines.append("")
        lines.append("### 组件")
        for component in self.components:
            tech = "; ".join(f"{k}={v}" for k, v in list(component.technologies.items())[:4])
            lines.append(f"- {component.name}: {component.responsibilities[:180]}"
                         + (f"（{tech}）" if tech else ""))
        lines.append("")
        lines.append("### 架构视图（PlantUML）")
        for diagram in self.diagrams:
            sample = ", ".join(diagram.elements[:8])
            lines.append(f"- {diagram.id} [{diagram.kind}] 元素: {sample}")
        if self.assumptions:
            lines.append("")
            lines.append("### 已登记假设")
            for assumption in self.assumptions[:12]:
                lines.append(f"- {assumption.id}: {assumption.text}")
        if self.warnings:
            lines.append("")
            lines.append("### 解析告警（必须在报告/假设中体现，不得静默忽略）")
            for warning in self.warnings[:12]:
                lines.append(f"- {warning}")
        if self.conflicts:
            lines.append("")
            lines.append("### 文档冲突")
            for conflict in self.conflicts[:10]:
                lines.append(f"- {conflict.id} [{conflict.severity}] {conflict.message}")
        text = "\n".join(lines)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...（摘要已截断，完整 JSON 见 .agent_state）"
        return text

    def summary_counts(self) -> dict:
        kinds: dict[str, int] = {}
        for req in self.requirements:
            kinds[req.kind] = kinds.get(req.kind, 0) + 1
        return {
            "requirements": len(self.requirements),
            "by_kind": kinds,
            "explicit": len(self.explicit_requirements()),
            "derived": len(self.derived_requirements()),
            "diagrams": len(self.diagrams),
            "components": len(self.components),
            "conflicts": len(self.conflicts),
            "assumptions": len(self.assumptions),
            "warnings": len(self.warnings),
        }


class RequirementNormalizer:
    """Merges the two documents into one auditable requirement set."""

    def __init__(self, extra_assumptions: bool = True) -> None:
        self.extra_assumptions = extra_assumptions

    def normalize(self, doc: ParsedDocument, view: ParsedDocument | None = None) -> NormalizedRequirements:
        model = NormalizedRequirements(
            project_name=doc.project_name or (view.project_name if view else "") or "Generated Project",
            target=doc.target or (view.target if view else ""),
            style=doc.style or "modular monolith",
            deployment=doc.deployment,
            inputs=[doc.stats] + ([view.stats] if view else []),
        )

        # requirements from the architecture document
        for req in doc.requirements:
            model.requirements.append(self._convert_requirement(req, doc))

        # requirements derived from the use-case diagram
        if view is not None:
            model.requirements.extend(self._derived_from_usecases(view, model.requirements))

        # diagrams
        if view is not None:
            for diagram in view.diagrams:
                model.diagrams.append(self._convert_diagram(diagram, view))
            model.warnings.extend(view.warnings)

        # components (merge doc + view artifacts)
        model.components = self._merge_components(doc, view)
        model.tech_stack = dict(doc.tech_stack)
        model.warnings.extend(doc.warnings)

        # conflicts and assumptions
        model.conflicts = self._detect_conflicts(doc, view, model)
        model.assumptions = self._build_assumptions(doc)
        model.stats = self._stats(model)
        return model

    # ------------------------------------------------------------------ #
    @staticmethod
    def _convert_requirement(req: ParsedRequirement, doc: ParsedDocument) -> RequirementItem:
        return RequirementItem(
            id=req.id,
            kind=req.kind,
            title=req.title,
            description=req.description,
            source=SourceRef(document=req.source_doc, line=req.line, sha256=doc.sha256),
            confidence=req.confidence if req.confidence in {"explicit", "inferred"} else "explicit",
            diagrams=req.diagrams,
            components=req.components,
            artifacts=req.artifacts,
            test_types=req.test_types,
        )

    @staticmethod
    def _convert_diagram(diagram: Diagram, doc: ParsedDocument) -> DiagramInfo:
        return DiagramInfo(
            id=diagram.id,
            kind=diagram.kind,
            source_doc=Path(doc.path).name,
            line_start=diagram.line_start,
            elements=diagram.elements,
            relation_count=len(diagram.relations),
            message_count=len(diagram.messages),
            warnings=diagram.warnings,
            raw_sha256=hashlib.sha256(diagram.raw.encode("utf-8")).hexdigest(),
        )

    def _derived_from_usecases(self, view: ParsedDocument,
                               existing: list[RequirementItem]) -> list[RequirementItem]:
        use_case_diagram = next((d for d in view.diagrams if d.kind == "use_case"), None)
        if use_case_diagram is None:
            return []
        known_titles = {req.title.lower().strip() for req in existing}
        known_titles |= {req.id.lower() for req in existing}
        derived: list[RequirementItem] = []
        counter = 0
        for usecase in use_case_diagram.usecases:
            title = usecase.strip()
            if not title or title.lower() in known_titles:
                continue
            counter += 1
            derived.append(
                RequirementItem(
                    id=f"FR-DERIVED-{counter}",
                    kind="FR",
                    title=title,
                    description=f"由用例图 {use_case_diagram.id} 推导：{title}",
                    source=SourceRef(document=Path(view.path).name, line=use_case_diagram.line_start,
                                     sha256=view.sha256),
                    confidence="diagram-derived",
                    diagrams=[use_case_diagram.id],
                    components=self._infer_components(title),
                )
            )
            known_titles.add(title.lower())
        return derived

    @staticmethod
    def _infer_components(title: str) -> list[str]:
        lowered = title.lower()
        components: list[str] = []
        if any(word in lowered for word in ("play", "game", "score", "answer", "round")):
            components.append("GameComponent")
        if any(word in lowered for word in ("question", "quiz", "prompt")):
            components.append("QuestionComponent")
        if any(word in lowered for word in ("admin", "update", "manage")):
            components.append("AdminComponent")
        if any(word in lowered for word in ("login", "user", "view", "help")):
            components.append("UserComponent")
        return components or ["GameComponent"]

    def _merge_components(self, doc: ParsedDocument, view: ParsedDocument | None) -> list[ComponentModel]:
        merged: dict[str, ComponentModel] = {}
        for component in doc.components:
            merged[component.name] = self._convert_component(component, doc, inferred=False)
        if view is not None:
            for diagram in view.diagrams:
                for name in diagram.artifacts + diagram.components:
                    if not name or name in merged:
                        continue
                    if name.endswith(("Component", "Service")):
                        merged[name] = ComponentModel(
                            name=name,
                            responsibilities=f"由 {diagram.id} 推导的组件边界；职责与接口待实现时确认。",
                            source=SourceRef(document=Path(view.path).name, line=diagram.line_start,
                                             sha256=view.sha256),
                            inferred=True,
                        )
        # Ensure the roles named by the architecture narrative exist.
        for name in ("GameComponent", "QuestionComponent", "UserComponent"):
            if name not in merged:
                merged[name] = ComponentModel(
                    name=name,
                    responsibilities="文档叙述中出现但缺乏独立设计章节；按最小职责实现。",
                    source=SourceRef(document=Path(doc.path).name, sha256=doc.sha256),
                    inferred=True,
                )
        return list(merged.values())

    @staticmethod
    def _convert_component(component: ComponentInfo, doc: ParsedDocument, inferred: bool) -> ComponentModel:
        return ComponentModel(
            name=component.name,
            responsibilities=component.responsibilities,
            technologies=component.technologies,
            source=SourceRef(document=Path(component.source_doc or doc.path).name,
                             line=component.line, sha256=doc.sha256),
            inferred=inferred,
        )

    # ------------------------------------------------------------------ #
    def _detect_conflicts(self, doc: ParsedDocument, view: ParsedDocument | None,
                          model: NormalizedRequirements) -> list[Conflict]:
        conflicts: list[Conflict] = []
        counter = 0

        def add(severity: str, message: str, evidence: str, resolution: str) -> None:
            nonlocal counter
            counter += 1
            conflicts.append(Conflict(id=f"C-{counter:03d}", severity=severity, message=message,
                                      evidence=evidence, resolution=resolution))

        actual_diagrams = len(view.diagrams) if view else 0
        claimed = None
        for text in (doc.text, view.text if view else ""):
            match = re.search(r"(\d+)\s+(?:PlantUML\s+)?(?:diagrams|UML|视图)", text, re.I)
            if match:
                claimed = int(match.group(1))
                break
        if claimed is not None and actual_diagrams and claimed != actual_diagrams:
            add(
                "medium",
                f"架构文档声称 {claimed} 个 PlantUML 图，实际解析到 {actual_diagrams} 个代码块。",
                f"{Path(doc.path).name} vs {Path(view.path).name if view else ''}",
                f"以实际解析结果 {actual_diagrams} 个视图为准，并在报告中记录差异。",
            )

        if any(r.id == "ASR-2" for r in model.requirements):
            asr2 = model.requirement("ASR-2")
            if asr2 is not None and asr2.confidence in {"inferred", "diagram-derived"}:
                add(
                    "medium",
                    "ASR-2（安全）在质量属性/测试表中被引用，但文档没有给出正式定义与验收指标。",
                    asr2.source.document,
                    "按 NFR-2 级安全约束处理（输入校验、无明文密钥、最小权限），并标注来源为推断。",
                )

        explicit = [r for r in model.requirements if r.confidence == "explicit"]
        if explicit and any(r.artifacts for r in explicit):
            mapped = [r for r in explicit if r.artifacts]
            if len(mapped) < len(explicit):
                add(
                    "medium",
                    f"追溯矩阵仅覆盖 {len(mapped)} 条显式需求，仍有 {len(explicit) - len(mapped)} 条缺少产物映射。",
                    "B. Traceability & Rationale",
                    "由 Agent 在实现阶段补充映射并在 traceability_matrix.csv 标注来源。",
                )

        test_matrix = next(
            (t for t in doc.tables if t.headers and t.headers[0].strip().lower() == "test type"),
            None,
        )
        if test_matrix is not None and all(all(not cell.strip() for cell in row[1:]) for row in test_matrix.rows):
            add(
                "high",
                "文档的测试矩阵为空（Unit/Integration/Contract/E2E/Chaos 均未填写覆盖组件）。",
                "H. Testing Strategy",
                "Agent 生成最小可用测试：领域单元测试 + REST 集成/端到端测试，并在报告中声明覆盖边界。",
            )

        if view is not None:
            for diagram in view.diagrams:
                if diagram.kind == "object" and diagram.participants:
                    add(
                        "low",
                        f"{diagram.id} 使用 participant 语法描述对象图，与图类型不一致。",
                        f"{diagram.id}, line {diagram.line_start}",
                        "按对象/参与者语义提取，不据此推断额外运行时行为。",
                    )
                if diagram.kind == "collaboration" and any(m.get("arrow", "").endswith(">>") for m in diagram.messages):
                    add(
                        "low",
                        f"{diagram.id} 使用序列图消息记法描述协作图。",
                        f"{diagram.id}, line {diagram.line_start}",
                        "按消息顺序提取协作语义，并在报告中标记语法偏差。",
                    )
            seq = [d.id for d in view.diagrams if d.kind == "sequence"]
            collab = [d.id for d in view.diagrams if d.kind == "collaboration"]
            if len(seq) > 1 and len(collab) > 1:
                add(
                    "low",
                    "序列图与协作图各有复数版本，信息高度重复。",
                    ", ".join(seq + collab),
                    "合并为两条主流程（答题、题目维护），不重复实现。",
                )

        heavy_stack = [name for name in ("Redis", "RabbitMQ", "Elasticsearch", "Kubernetes",
                                         "Istio", "Vault", "Terraform") if name in doc.text]
        if heavy_stack:
            add(
                "high",
                "文档推荐了 Redis/RabbitMQ/Elasticsearch/Kubernetes/Istio/Vault/Terraform 等重型组件，"
                "但没有给出对应的业务约束与运维预算。",
                ", ".join(heavy_stack),
                "保留微服务组件边界，但演示实现只使用业务必需的依赖；上述组件列入 ASSUMPTIONS.md 的可选扩展，"
                "明确标记为重大偏离，不声称生产就绪。",
            )

        if not doc.style.lower().startswith("microservice"):
            add(
                "low",
                "文档未明确给出可执行的架构风格。",
                doc.style or "（缺失）",
                "按模块化单体实现，保留清晰服务边界。",
            )
        return conflicts

    # ------------------------------------------------------------------ #
    def _build_assumptions(self, doc: ParsedDocument) -> list[Assumption]:
        assumptions: list[Assumption] = []
        for index, text in enumerate(doc.assumptions, start=1):
            assumptions.append(Assumption(
                id=f"A{index}", text=text, category="document",
                source=Path(doc.path).name, impact="容量/性能设计假设",
            ))
        if not self.extra_assumptions:
            return assumptions
        defaults = [
            ("ASM-01", "每局固定 10 道分数题；答对 +10 分、答错 0 分，满分 100 分，无倒计时。", "gameplay",
             "影响题库数量、计分逻辑与结束条件。"),
            ("ASM-02", "学生无需注册；会话开始时生成访客 ID，分数仅用于当前回合展示。管理员使用环境变量配置的令牌登录。", "identity",
             "影响 user-service 的范围；不实现完整 OAuth2。"),
            ("ASM-03", "题目为六年级分数四则运算单选题（4 个选项），题目与答案由种子数据提供，管理员可增删改。", "gameplay",
             "影响 question-service 的数据模型与校验。"),
            ("ASM-04", "开始/结束动画以 CSS 过渡和文本场景实现，不依赖外部图片或视频素材。", "ui",
             "影响前端资源与打包体积；不阻塞核心流程。"),
            ("ASM-05", "无障碍要求：键盘可操作、语义化标签、可见焦点、颜色对比度不低于 4.5:1。", "quality",
             "影响 UI 实现与验收清单。"),
            ("ASM-06", "保留 Game/Question/User 三个服务边界，使用 REST + 进程内仓库运行；PostgreSQL 以可选适配器提供，"
                       "Redis/RabbitMQ/Elasticsearch/Kubernetes/Istio/Vault/Terraform 不纳入演示依赖。"
                       "这是相对原文档微服务/云原生方案的重大偏离，必须在报告与 ASSUMPTIONS.md 中声明。", "architecture",
             "这是相对原文档微服务/云原生方案的重大偏离，必须在报告与 ASSUMPTIONS.md 中声明。"),
        ]
        existing_text = " ".join(a.text for a in assumptions)
        for assumption_id, text, category, impact in defaults:
            if text.split("，")[0][:12] in existing_text:
                continue
            assumptions.append(Assumption(id=assumption_id, text=text, category=category,
                                          source="agent", impact=impact))
        return assumptions

    @staticmethod
    def _stats(model: NormalizedRequirements) -> dict:
        return {
            "requirements": len(model.requirements),
            "explicit": len(model.explicit_requirements()),
            "derived": len(model.derived_requirements()),
            "diagrams": len(model.diagrams),
            "components": len(model.components),
            "conflicts": len(model.conflicts),
            "assumptions": len(model.assumptions),
            "warnings": len(model.warnings),
            "kinds": {
                kind: sum(1 for r in model.requirements if r.kind == kind)
                for kind in sorted({r.kind for r in model.requirements})
            },
        }
