"""M4/M5 tests: full controller pipeline with Mock provider (T13), cancellation."""

from __future__ import annotations

import csv
import json
import shutil
import threading
from pathlib import Path

import pytest

from space_code_agent.app.config import AppConfig
from space_code_agent.app.controller import Controller, RunRequest
from space_code_agent.app.events import EventSink
from space_code_agent.agent.planner import fallback_plan, validate_plan
from space_code_agent.core.delivery import DeliveryValidator
from space_code_agent.core.document_parser import DocumentParser
from space_code_agent.core.requirements import RequirementNormalizer
from space_code_agent.core.sample_project import build_sample_plan, iter_sample_files
from space_code_agent.providers.mock import MockProvider, tool_response
from space_code_agent.security.policy import WorkspacePolicy

FIXTURES = Path(__file__).parent / "fixtures" / "Task"
DOC = FIXTURES / "Architecture_Documentation.md"
VIEW = FIXTURES / "Architecture_View.md"


def make_request(tmp_path, **config_overrides):
    config = AppConfig(mock_mode=True, max_agent_steps=60, allow_command_execution=True)
    for key, value in config_overrides.items():
        setattr(config, key, value)
    return RunRequest(
        doc_path=str(DOC),
        view_path=str(VIEW),
        output_dir=str(tmp_path / "out"),
        config=config,
        approve=lambda name, message: True,
    )


@pytest.fixture(scope="module")
def mock_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("mockrun")
    sink = EventSink()
    request = make_request(root)
    result = Controller(emit=sink).run(request)
    return result, sink, root / "out"


def test_mock_run_completes_with_full_deliverables(mock_run):
    result, sink, output = mock_run
    assert result.status == "completed", result.error
    assert result.outcome is not None and result.outcome.status == "completed"
    assert result.coverage["percent"] == 100.0
    assert result.coverage["implemented"] == 7
    assert result.coverage["verified"] == 7
    assert result.coverage["verified_percent"] == 100.0
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    checks = {check["id"]: check["status"] for check in manifest["validation"]["delivery"]["checks"]}
    assert checks["web_ui"] == "pass"
    assert checks["persistence"] == "pass"
    for relative in (
        "README.md",
        "package.json",
        ".env.example",
        "docs/ASSUMPTIONS.md",
        "docs/architecture-summary.md",
        "services/question-service/src/index.js",
        "services/game-service/src/game.js",
        "apps/web/index.html",
        "tests/e2e/flow.test.js",
        "GENERATION_REPORT.md",
        "traceability_matrix.csv",
        "run_manifest.json",
    ):
        assert (output / relative).is_file(), relative
    phases = [event.data.get("phase") for event in sink.of("phase")]
    assert "NORMALIZING" in phases
    assert "PLANNING" in phases
    assert "IMPLEMENTING" in phases
    assert "VERIFYING" in phases
    assert "REPORTING" in phases


def test_generated_report_is_traceable(mock_run):
    result, _sink, output = mock_run
    report = (output / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "状态：COMPLETED" in report
    assert "文件映射覆盖率：" in report
    assert "测试验证覆盖率：" in report
    assert "7/7" in report
    assert "SequenceDiagram1" in report
    assert "ObjectDiagram" in report

    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["run"]["status"] == result.status == "completed"
    assert manifest["run"]["agent_status"] == "completed"
    assert manifest["coverage"]["percent"] == 100.0
    assert manifest["coverage"]["verified"] == 7
    assert len(manifest["files"]) >= 30
    assert manifest["model"]["mock"] is True
    assert "api_key" not in json.dumps(manifest).lower()

    with open(output / "traceability_matrix.csv", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 7
    assert {row["requirement_id"] for row in rows} == {
        "FR-1", "NFR-1", "ASR-1", "ASR-2", "FR-DERIVED-1", "FR-DERIVED-2", "FR-DERIVED-3",
    }
    assert all(row["status"] == "verified" for row in rows)
    assert all(row["mapped"] == "True" and row["verified"] == "True" for row in rows)


def test_generated_project_tests_pass_when_node_exists(mock_run):
    result, _sink, output = mock_run
    if shutil.which("node") is None:
        pytest.skip("node not available")
    # The controller recorded the real test execution, not a fabricated pass.
    assert result.report_paths
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    tests = manifest["validation"]["tests"]
    assert tests, "controller should have run node tests"
    assert tests[0]["passed"] is True
    assert tests[0]["exit_code"] == 0


def test_session_state_contains_no_secret(mock_run):
    _result, _sink, output = mock_run
    state_files = list((output / ".agent_state").rglob("*.json")) + \
        list((output / ".agent_state").rglob("*.jsonl"))
    assert state_files
    for path in state_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "sk-" not in text
        assert "Bearer " not in text or "REDACTED" in text


def test_cancel_before_start_still_writes_report(tmp_path):
    request = make_request(tmp_path)
    request.cancel.set()
    result = Controller().run(request)
    assert result.status == "cancelled"
    output = Path(result.output_dir)
    assert (output / "GENERATION_REPORT.md").is_file()
    assert result.outcome is not None
    assert result.outcome.status == "cancelled"


def test_missing_document_fails_fast(tmp_path):
    request = make_request(tmp_path)
    request.doc_path = str(tmp_path / "missing.md")
    result = Controller().run(request)
    assert result.status == "failed"
    assert "不存在" in result.error


def test_output_dir_gets_unique_subdir_when_non_empty(tmp_path):
    base = tmp_path / "out"
    base.mkdir()
    (base / "sentinel.txt").write_text("keep me", encoding="utf-8")
    target = Controller._prepare_output(base)
    assert target.parent == base
    assert target != base
    assert (base / "sentinel.txt").read_text(encoding="utf-8") == "keep me"
    assert target.is_dir()


def test_unrun_tests_are_not_reported_as_success(tmp_path):
    request = make_request(tmp_path, allow_command_execution=False)
    result = Controller().run(request)
    assert result.status == "partial"
    assert result.outcome is not None and result.outcome.status == "completed"
    manifest = json.loads((Path(result.output_dir) / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["run"]["status"] == "partial"
    assert manifest["run"]["agent_status"] == "completed"
    assert manifest["coverage"]["tests_ran"] is False
    assert manifest["coverage"]["verified"] == 0
    report = (Path(result.output_dir) / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "未运行（not run）" in report
    assert "不得标记为完全成功" in report


def test_backend_only_project_fails_ui_and_persistence_contracts(tmp_path):
    """A backend-only project must not be accepted for a web/durability target."""
    workspace = tmp_path / "backend-only"
    (workspace / "src").mkdir(parents=True)
    (workspace / "tests").mkdir()
    (workspace / "README.md").write_text("# Backend only\n", encoding="utf-8")
    (workspace / "package.json").write_text('{"name":"backend-only"}', encoding="utf-8")
    (workspace / "src" / "app.js").write_text(
        "// Covers: FR-1\nexport const app = 1;\n", encoding="utf-8"
    )
    (workspace / "tests" / "app.test.js").write_text(
        "// Covers: FR-1\ntest('x', () => {});\n", encoding="utf-8"
    )
    parser = DocumentParser()
    requirements = RequirementNormalizer().normalize(
        parser.parse(DOC, "architecture"), parser.parse(VIEW, "view")
    )
    policy = WorkspacePolicy(workspace, max_file_bytes=1024 * 1024)
    report = DeliveryValidator(policy, requirements, None, AppConfig()).evaluate([])
    checks = {check["id"]: check for check in report.checks}
    assert checks["web_ui"]["status"] == "fail"
    assert checks["persistence"]["status"] == "fail"
    assert report.ok is False
    assert any("Web 目标" in item for item in report.missing)
    assert any("ASR-1" in item for item in report.missing)


def test_fallback_plan_requires_web_ui_and_persistence():
    parser = DocumentParser()
    requirements = RequirementNormalizer().normalize(
        parser.parse(DOC, "architecture"), parser.parse(VIEW, "view")
    )
    plan = fallback_plan(requirements)
    paths = {file.path.lower() for file in plan.files}
    assert any(path.endswith(".html") for path in paths)
    assert any("store" in path or "persist" in path for path in paths)
    assert validate_plan(plan, requirements) == []


def test_failing_generated_tests_downgrade_to_partial(tmp_path, monkeypatch):
    """A real test failure must never be reported as a clean completion."""
    monkeypatch.setattr(
        Controller,
        "_maybe_run_tests",
        lambda self, config, request, registry, context, output_root: [{
            "profile": "node",
            "exit_code": 1,
            "passed": False,
            "duration_s": 0.1,
            "output": "1 test failed: expected 100 got 90",
            "timed_out": False,
        }],
    )
    result = Controller().run(make_request(tmp_path))
    assert result.status == "partial"
    report = (Path(result.output_dir) / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "自动化测试未通过" in report
    assert "expected 100 got 90" in report
    manifest = json.loads((Path(result.output_dir) / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["run"]["status"] == "partial"
    assert manifest["run"]["agent_status"] == "completed"
    assert manifest["coverage"]["failed"] == 7


def test_test_failure_triggers_model_repair_and_retest(tmp_path):
    """The controller must feed test output back to the model and re-run tests."""
    if shutil.which("node") is None:
        pytest.skip("node not available")
    parser = DocumentParser()
    requirements = RequirementNormalizer().normalize(
        parser.parse(DOC, "architecture"), parser.parse(VIEW, "view")
    )
    plan = build_sample_plan(requirements)
    broken_test = (
        "const test = require('node:test');\n"
        "const assert = require('node:assert/strict');\n"
        "test('intentional failure', () => assert.equal(1, 2));\n"
    )
    original_files = dict(iter_sample_files())
    schema_path = "tests/unit/schema.test.js"
    assert schema_path in original_files

    script = []
    for path, content in original_files.items():
        payload = broken_test if path == schema_path else content
        script.append(tool_response([("write_file", {"path": path, "content": payload})]))
    script.append(tool_response([("finish_task", {"summary": "first attempt"})]))
    script.append(tool_response([(
        "write_file",
        {"path": schema_path, "content": original_files[schema_path], "overwrite": True},
    )]))
    script.append(tool_response([("finish_task", {"summary": "fixed failing test"})]))

    config = AppConfig(mock_mode=False, max_agent_steps=60, max_repair_rounds=2,
                       allow_command_execution=True)
    request = RunRequest(
        doc_path=str(DOC),
        view_path=str(VIEW),
        output_dir=str(tmp_path / "out"),
        config=config,
        approve=lambda name, message: True,
        provider_override=MockProvider(script),
        plan_override=plan,
    )
    sink = EventSink()
    result = Controller(emit=sink).run(request)
    phases = [event.data.get("phase") for event in sink.of("phase")]
    assert "REPAIRING" in phases
    assert result.status == "completed", result.error
    manifest = json.loads((Path(result.output_dir) / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["validation"]["tests"][0]["passed"] is True
    assert manifest["coverage"]["verified"] == 7
    assert manifest["run"]["status"] == "completed"
