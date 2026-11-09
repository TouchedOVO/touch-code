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
    _result, _sink, output = mock_run
    report = (output / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "状态：COMPLETED" in report
    assert "需求覆盖率：" in report
    assert "7/7" in report
    assert "SequenceDiagram1" in report
    assert "ObjectDiagram" in report

    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["run"]["status"] == "completed"
    assert manifest["coverage"]["percent"] == 100.0
    assert len(manifest["files"]) >= 30
    assert manifest["model"]["mock"] is True
    assert "api_key" not in json.dumps(manifest).lower()

    with open(output / "traceability_matrix.csv", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 7
    assert {row["requirement_id"] for row in rows} == {
        "FR-1", "NFR-1", "ASR-1", "ASR-2", "FR-DERIVED-1", "FR-DERIVED-2", "FR-DERIVED-3",
    }
    assert all(row["status"] == "implemented" for row in rows)


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
