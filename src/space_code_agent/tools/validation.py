"""Static project inspection. Never executes project code."""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

from .base import ToolContext, ToolSpec

SOURCE_EXTS = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".css", ".sql", ".yml", ".yaml"}
MANIFESTS = {"package.json", "requirements.txt", "pyproject.toml", "cargo.toml", "go.mod", "pom.xml"}


def _iter(context: ToolContext):
    return list(context.policy.iter_files(".", "**/*", limit=5000))


def _check_structure(context: ToolContext, entries: list[dict]) -> dict:
    paths = {entry["path"] for entry in entries}
    lower_names = {Path(path).name.lower() for path in paths}
    issues: list[str] = []
    notes: list[str] = []
    readme = any(name == "readme.md" for name in lower_names)
    manifest = any(name in MANIFESTS for name in lower_names)
    tests = any(path.startswith("tests/") or "test" in Path(path).name.lower() or Path(path).name.endswith(".test.js") for path in paths)
    sources = [path for path in paths if Path(path).suffix.lower() in SOURCE_EXTS]
    if not readme:
        issues.append("缺少 README.md")
    if not manifest:
        issues.append("缺少依赖声明（package.json / requirements.txt / pyproject.toml）")
    if not tests:
        issues.append("缺少测试文件")
    if len(sources) < 3:
        issues.append(f"源码文件过少（{len(sources)} 个）")
    if not any(path.startswith("src/") or path.startswith("apps/") or path.startswith("services/") for path in paths):
        notes.append("未使用 src/apps/services 目录约定")
    return {
        "id": "structure",
        "status": "pass" if not issues else "fail",
        "details": {
            "files": len(paths),
            "sources": len(sources),
            "readme": readme,
            "manifest": manifest,
            "tests": tests,
            "issues": issues,
            "notes": notes,
        },
    }


def _check_json(context: ToolContext, entries: list[dict]) -> dict:
    errors: list[dict] = []
    checked = 0
    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".json":
            continue
        checked += 1
        try:
            text, _ = context.policy.read_text(entry["path"], max_chars=2_000_000)
            json.loads(text)
        except Exception as exc:  # noqa: BLE001 - report every parse failure
            errors.append({"path": entry["path"], "error": str(exc)[:300]})
    return {
        "id": "json_syntax",
        "status": "pass" if not errors else "fail",
        "details": {"checked": checked, "errors": errors},
    }


def _check_python(context: ToolContext, entries: list[dict]) -> dict:
    errors: list[dict] = []
    checked = 0
    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".py":
            continue
        checked += 1
        try:
            text, _ = context.policy.read_text(entry["path"], max_chars=2_000_000)
            ast.parse(text, filename=entry["path"])
        except Exception as exc:  # noqa: BLE001
            errors.append({"path": entry["path"], "error": str(exc)[:300]})
    return {
        "id": "python_syntax",
        "status": "pass" if not errors else "fail",
        "details": {"checked": checked, "errors": errors},
    }


def _check_js(context: ToolContext, entries: list[dict]) -> dict:
    node = shutil.which("node")
    js_files = [entry for entry in entries if Path(entry["path"]).suffix.lower() in {".js", ".mjs", ".cjs"}]
    if not node:
        return {
            "id": "js_syntax",
            "status": "skipped",
            "details": {"reason": "未找到 Node.js，JavaScript 语法检查跳过（not run）", "files": len(js_files)},
        }
    errors: list[dict] = []
    checked = 0
    for entry in js_files:
        checked += 1
        try:
            proc = subprocess.run(
                [node, "--check", str(context.policy.root / entry["path"])],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
            )
            if proc.returncode != 0:
                errors.append({"path": entry["path"], "error": (proc.stderr or proc.stdout)[:300]})
        except Exception as exc:  # noqa: BLE001
            errors.append({"path": entry["path"], "error": str(exc)[:300]})
    return {
        "id": "js_syntax",
        "status": "pass" if not errors else "fail",
        "details": {"checked": checked, "errors": errors, "runtime": node},
    }


def _check_links(context: ToolContext, entries: list[dict]) -> dict:
    readme = next((entry for entry in entries if entry["path"].lower() == "readme.md"), None)
    if readme is None:
        return {"id": "readme_links", "status": "skipped", "details": {"reason": "no README.md"}}
    text, _ = context.policy.read_text(readme["path"], max_chars=500_000)
    missing: list[str] = []
    checked = 0
    for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        checked += 1
        candidate = (context.policy.root / target.lstrip("/")).resolve()
        if not candidate.exists():
            missing.append(target)
    return {
        "id": "readme_links",
        "status": "pass" if not missing else "warn",
        "details": {"checked": checked, "missing": missing},
    }


def _check_requirements(context: ToolContext, entries: list[dict]) -> dict:
    requirements = context.requirements
    if requirements is None:
        return {"id": "requirement_traceability", "status": "skipped",
                "details": {"reason": "no normalized requirements in context"}}
    paths = {entry["path"] for entry in entries}
    items = getattr(requirements, "requirements", requirements)
    rows: list[dict] = []
    for requirement in items:
        files = [path for path in getattr(requirement, "files", []) if path in paths]
        evidence = bool(files)
        rows.append({"id": getattr(requirement, "id", ""), "files": files, "evidence": evidence})
    covered = sum(1 for row in rows if row["evidence"])
    return {
        "id": "requirement_traceability",
        "status": "pass" if covered == len(rows) and rows else "warn",
        "details": {"total": len(rows), "covered": covered, "rows": rows},
    }


def inspect_project(context: ToolContext, args: dict) -> dict:
    checks = args.get("checks") or ["structure", "json", "python", "js", "links", "requirements"]
    entries = _iter(context)
    results: list[dict] = []
    for check in checks:
        if check == "structure":
            results.append(_check_structure(context, entries))
        elif check == "json":
            results.append(_check_json(context, entries))
        elif check == "python":
            results.append(_check_python(context, entries))
        elif check == "js":
            results.append(_check_js(context, entries))
        elif check == "links":
            results.append(_check_links(context, entries))
        elif check == "requirements":
            results.append(_check_requirements(context, entries))
        else:
            results.append({"id": check, "status": "skipped", "details": {"reason": "unknown check"}})
    failed = [result for result in results if result["status"] == "fail"]
    return {
        "ok": True,
        "summary": "静态检查：" + ", ".join(f"{r['id']}={r['status']}" for r in results),
        "passed": not failed,
        "checks": results,
    }


SPECS = [
    ToolSpec(
        name="inspect_project",
        description="Statically inspect the generated project (structure, JSON/Python/JS syntax, README links, requirement traceability). Does not execute project code.",
        parameters={
            "type": "object",
            "properties": {
                "checks": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["structure", "json", "python", "js", "links", "requirements"]},
                }
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=inspect_project,
        category="validation",
    )
]
