"""Local delivery validation and requirement traceability.

The model's own "finished" claim is never enough: this module checks the real
files on disk, maps them back to requirements, and computes coverage.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..app.config import AppConfig
from ..security.policy import PolicyError, WorkspacePolicy
from .requirements import NormalizedRequirements
from .session import FileRegistry

MANIFEST_NAMES = {"package.json", "requirements.txt", "pyproject.toml", "cargo.toml", "go.mod"}
SOURCE_SUFFIXES = {".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", ".py", ".html", ".css", ".sql", ".sh"}
TEXT_SUFFIXES = SOURCE_SUFFIXES | {".json", ".yml", ".yaml", ".txt", ".proto", ".csv", ".env", ".example"}
DOC_SUFFIXES = {".md", ".markdown"}


@dataclass
class DeliveryReport:
    ok: bool = False
    missing: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)
    mappings: dict[str, list[str]] = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)
    files: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "missing": self.missing,
            "checks": self.checks,
            "coverage": self.coverage,
            "files": len(self.files),
        }


class DeliveryValidator:
    def __init__(self, policy: WorkspacePolicy, requirements: NormalizedRequirements,
                 plan=None, config: AppConfig | None = None,
                 files: FileRegistry | None = None) -> None:
        self.policy = policy
        self.requirements = requirements
        self.plan = plan
        self.config = config or AppConfig()
        self.files = files
        self.test_results: list[dict] = []

    # ------------------------------------------------------------------ #
    def evaluate(self, test_results: list[dict] | None = None) -> DeliveryReport:
        if test_results is not None:
            self.test_results = list(test_results)
        tests_ran = bool(self.test_results)
        tests_passed = tests_ran and all(item.get("passed") is True for item in self.test_results)
        report = DeliveryReport()
        entries = list(self.policy.iter_files(".", "**/*", limit=5000))
        report.files = entries
        paths = {entry["path"] for entry in entries}
        lower_paths = {path.lower() for path in paths}
        checks: list[dict] = []

        readme = "readme.md" in lower_paths
        manifests = [name for name in MANIFEST_NAMES if name in lower_paths]
        assumptions = "docs/assumptions.md" in lower_paths
        tests = [path for path in paths if path.startswith("tests/") or "/tests/" in path
                 or Path(path).name.lower().endswith((".test.js", "_test.py", ".spec.js"))]
        sources = [path for path in paths if Path(path).suffix.lower() in SOURCE_SUFFIXES]
        empty_sources = []
        for path in sources[:200]:
            try:
                text, _ = self.policy.read_text(path, max_chars=2000)
                if len(text.strip()) < 20:
                    empty_sources.append(path)
            except PolicyError:
                continue

        missing: list[str] = []
        if not readme:
            missing.append("缺少 README.md")
        if not manifests:
            missing.append("缺少依赖声明（package.json / requirements.txt / pyproject.toml）")
        if not assumptions:
            missing.append("缺少 docs/ASSUMPTIONS.md")
        if not tests:
            missing.append("缺少测试文件（tests/ 或 *.test.js）")
        if len(sources) < 3:
            missing.append(f"源码文件不足（当前 {len(sources)} 个，至少 3 个）")
        if empty_sources:
            missing.append("空壳源文件：" + ", ".join(empty_sources[:5]))

        checks.append({
            "id": "deliverables",
            "status": "pass" if not missing else "fail",
            "details": {
                "readme": readme, "manifest": manifests, "assumptions": assumptions,
                "tests": len(tests), "sources": len(sources), "empty_sources": empty_sources,
            },
        })

        json_errors: list[dict] = []
        for path in paths:
            if Path(path).suffix.lower() != ".json":
                continue
            try:
                text, _ = self.policy.read_text(path, max_chars=2_000_000)
                json.loads(text)
            except Exception as exc:  # noqa: BLE001
                json_errors.append({"path": path, "error": str(exc)[:200]})
        checks.append({
            "id": "json_manifest",
            "status": "pass" if not json_errors else "fail",
            "details": {"errors": json_errors},
        })
        if json_errors:
            missing.append("JSON 语法错误：" + ", ".join(item["path"] for item in json_errors[:3]))

        mappings = self._map_requirements(paths)
        report.mappings = mappings
        coverage = self._coverage(mappings, paths, tests_ran, tests_passed)
        report.coverage = coverage
        core_fr = [req for req in self.requirements.requirements if req.kind == "FR"]
        unmapped_fr = [req.id for req in core_fr if not mappings.get(req.id)]
        if unmapped_fr:
            missing.append("未被源码映射的 FR：" + ", ".join(unmapped_fr[:8]))
        checks.append({
            "id": "requirement_traceability",
            "status": "pass" if not unmapped_fr else "warn",
            "details": {"coverage": coverage, "unmapped_fr": unmapped_fr},
        })

        report.checks = checks
        report.missing = missing
        report.ok = not missing
        return report

    # ------------------------------------------------------------------ #
    def _map_requirements(self, paths: set[str]) -> dict[str, list[str]]:
        mappings: dict[str, list[str]] = {req.id: [] for req in self.requirements.requirements}
        # 1) plan-declared mapping
        if self.plan is not None:
            for plan_file in getattr(self.plan, "files", []):
                path = plan_file.path.replace("\\", "/")
                if path.startswith("./"):
                    path = path[2:]
                if path not in paths or Path(path).suffix.lower() in DOC_SUFFIXES:
                    continue
                for req_id in plan_file.requirement_ids:
                    if req_id in mappings and path not in mappings[req_id]:
                        mappings[req_id].append(path)
        # 2) source-content mapping ("Covers: FR-1")
        ids = list(mappings)
        if ids:
            pattern = re.compile(r"\b(" + "|".join(re.escape(req_id) for req_id in ids) + r")\b")
            for path in paths:
                suffix = Path(path).suffix.lower()
                if suffix in DOC_SUFFIXES:
                    continue
                if suffix not in TEXT_SUFFIXES and Path(path).name.lower() not in {".gitignore", ".env.example"}:
                    continue
                try:
                    text, _ = self.policy.read_text(path, max_chars=300_000)
                except PolicyError:
                    continue
                for req_id in set(pattern.findall(text)):
                    if path not in mappings[req_id]:
                        mappings[req_id].append(path)
        # 3) architecture-declared artifacts that actually exist
        for req in self.requirements.requirements:
            for artifact in req.artifacts:
                for path in paths:
                    if path.endswith(artifact.lstrip("./")) and path not in mappings[req.id]:
                        mappings[req.id].append(path)
        return mappings

    def _coverage(self, mappings: dict[str, list[str]], paths: set[str],
                  tests_ran: bool = False, tests_passed: bool = False) -> dict:
        total = len(self.requirements.requirements)
        mapped = implemented = verified = unverified = failed = missing = 0
        for req in self.requirements.requirements:
            files = mappings.get(req.id, [])
            tests = [path for path in files if "test" in path.lower()]
            if not files:
                missing += 1
                continue
            mapped += 1
            implemented += 1
            if tests and tests_ran and tests_passed:
                verified += 1
            elif tests and tests_ran and not tests_passed:
                failed += 1
            else:
                unverified += 1
        return {
            "total": total,
            "mapped": mapped,
            "implemented": implemented,
            "verified": verified,
            "unverified": unverified,
            "failed": failed,
            "partial": unverified,
            "missing": missing,
            "tests_ran": tests_ran,
            "tests_passed": tests_passed,
            "percent": round(100.0 * mapped / total, 1) if total else 0.0,
            "verified_percent": round(100.0 * verified / total, 1) if total else 0.0,
        }

    def apply(self, test_results: list[dict] | None = None) -> dict:
        """Write mapping/status back onto the normalized requirement objects."""
        report = self.evaluate(test_results)
        tests_ran = bool(self.test_results)
        tests_passed = tests_ran and all(item.get("passed") is True for item in self.test_results)
        for req in self.requirements.requirements:
            files = report.mappings.get(req.id, [])
            tests = [path for path in files if "test" in path.lower()]
            req.files = sorted(files)
            req.tests = sorted(tests)
            req.mapped = bool(files)
            if not files:
                req.status = "missing"
                req.verified = False
                req.verification = "no_source"
            elif tests and tests_ran and tests_passed:
                req.status = "verified"
                req.verified = True
                req.verification = "passed"
            elif tests and tests_ran and not tests_passed:
                req.status = "failed"
                req.verified = False
                req.verification = "failed"
            elif tests:
                req.status = "implemented"
                req.verified = False
                req.verification = "not_run"
            else:
                req.status = "implemented"
                req.verified = False
                req.verification = "no_tests"
            req.evidence = ("源码: " + ", ".join(req.files[:4])) if files else "未找到对应实现"
            if tests:
                req.evidence += "；测试: " + ", ".join(tests[:3])
            req.evidence += f"；验证: {req.verification}"
        self.requirements.stats = dict(self.requirements.stats)
        self.requirements.stats["coverage"] = report.coverage
        return report.as_dict()

    def traceability_rows(self) -> list[dict]:
        rows: list[dict] = []
        for req in self.requirements.requirements:
            rows.append({
                "requirement_id": req.id,
                "kind": req.kind,
                "title": req.title,
                "confidence": req.confidence,
                "status": req.status,
                "mapped": req.mapped,
                "verified": req.verified,
                "verification": req.verification,
                "components": "; ".join(req.components),
                "files": "; ".join(req.files),
                "tests": "; ".join(req.tests),
                "evidence": req.evidence,
                "source": f"{req.source.document}:{req.source.line}" if req.source.document else "",
            })
        return rows


def ensure_assumptions_file(policy: WorkspacePolicy, requirements: NormalizedRequirements) -> bool:
    """Write a transparent fallback if the model omitted ASSUMPTIONS.md."""
    path = "docs/ASSUMPTIONS.md"
    try:
        policy.resolve_read(path)
        return False
    except PolicyError:
        pass
    lines = [
        "# ASSUMPTIONS",
        "",
        "<!-- Covers: " + ", ".join(req.id for req in requirements.requirements) + " -->",
        "",
        "> 本文件由 SpaceCode Agent 在模型未生成假设文档时自动补充；内容来自归一化阶段的显式登记。",
        "",
        "## 文档假设",
    ]
    for assumption in requirements.assumptions:
        lines.append(f"- **{assumption.id}**（{assumption.category}）：{assumption.text}")
        if assumption.impact:
            lines.append(f"  - 影响：{assumption.impact}")
    lines.extend(["", "## 文档冲突与处置"])
    for conflict in requirements.conflicts:
        lines.append(f"- **{conflict.id}** [{conflict.severity}] {conflict.message}")
        if conflict.resolution:
            lines.append(f"  - 处置：{conflict.resolution}")
    policy.write_text_atomic(path, "\n".join(lines) + "\n", overwrite=True)
    return True
