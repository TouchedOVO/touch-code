"""M3 tests: tool schemas, validation and file/search behaviour (T04/T05)."""

from __future__ import annotations

import json

import pytest

from space_code_agent.app.config import AppConfig
from space_code_agent.app.events import EventSink
from space_code_agent.core.session import FileRegistry, SessionStore
from space_code_agent.security.policy import WorkspacePolicy
from space_code_agent.security.secrets import SecretRedactor
from space_code_agent.tools import build_registry
from space_code_agent.tools.base import ToolContext


@pytest.fixture()
def context(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    session = SessionStore(workspace)
    sink = EventSink()
    policy = WorkspacePolicy(workspace, max_file_bytes=1024 * 1024)
    config = AppConfig(max_tool_output_chars=4000)
    return ToolContext(
        policy=policy,
        config=config,
        session=session,
        files=FileRegistry(),
        redactor=SecretRedactor(["sk-secret123"]),
        emit=sink,
    ), build_registry(config)


def test_registry_exposes_json_schemas(context):
    ctx, registry = context
    names = set(registry.names())
    assert {"list_files", "read_file", "write_file", "replace_in_file",
            "search_in_files", "inspect_project", "run_tests", "finish_task"} <= names
    schemas = registry.schemas()
    assert all(schema["type"] == "function" and schema["name"] for schema in schemas)
    assert all("parameters" in schema for schema in schemas)


def test_write_read_replace(context):
    ctx, registry = context
    result = registry.execute("write_file", {"path": "src/a.js", "content": "line1\nline2\n"}, ctx)
    assert result["ok"] is True
    assert ctx.policy.read_text("src/a.js")[0] == "line1\nline2\n"
    assert ctx.files.records["src/a.js"].bytes == 12

    read = registry.execute("read_file", {"path": "src/a.js", "start_line": 2}, ctx)
    assert read["ok"] is True
    assert "line2" in read["content"]

    replaced = registry.execute(
        "replace_in_file", {"path": "src/a.js", "old_text": "line1", "new_text": "LINE1"}, ctx
    )
    assert replaced["ok"] is True
    assert replaced["replacements"] == 1


def test_replace_requires_unique_match(context):
    ctx, registry = context
    registry.execute("write_file", {"path": "a.txt", "content": "x x"}, ctx)
    result = registry.execute(
        "replace_in_file", {"path": "a.txt", "old_text": "x", "new_text": "y"}, ctx
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "not_unique"
    assert result["error"]["details"]["occurrences"] == 2


def test_missing_argument_returns_structured_error(context):
    ctx, registry = context
    result = registry.execute("write_file", {"path": "a.txt"}, ctx)
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"
    assert "content" in result["error"]["message"]


def test_unknown_tool_returns_error(context):
    ctx, registry = context
    result = registry.execute("rm_rf", {"path": "."}, ctx)
    assert result["ok"] is False
    assert result["error"]["code"] == "unknown_tool"


def test_write_escape_is_denied(context):
    ctx, registry = context
    result = registry.execute("write_file", {"path": "../evil.txt", "content": "x"}, ctx)
    assert result["ok"] is False
    assert result["error"]["code"] == "parent_traversal"


def test_search_and_list(context):
    ctx, registry = context
    registry.execute("write_file", {"path": "src/a.js", "content": "const needle = 1;\n"}, ctx)
    registry.execute("write_file", {"path": "src/b.js", "content": "other\n"}, ctx)
    found = registry.execute("search_in_files", {"pattern": "needle", "glob": "**/*.js"}, ctx)
    assert found["ok"] is True
    assert len(found["matches"]) == 1
    assert found["matches"][0]["path"] == "src/a.js"
    listed = registry.execute("list_files", {"relative_path": "src"}, ctx)
    assert listed["count"] == 2


def test_inspect_project_passes_basic_structure(context):
    ctx, registry = context
    files = {
        "README.md": "# Demo\n\nSee [src](src/app.js).\n",
        "package.json": json.dumps({"name": "demo", "scripts": {"test": "node --test"}}),
        "src/app.js": "export const x = 1;\n",
        "src/domain.js": "export const y = 2;\n",
        "tests/app.test.js": "// test\n",
    }
    for path, content in files.items():
        result = registry.execute("write_file", {"path": path, "content": content}, ctx)
        assert result["ok"], result
    inspected = registry.execute("inspect_project", {"checks": ["structure", "json", "links"]}, ctx)
    assert inspected["ok"] is True
    by_id = {check["id"]: check for check in inspected["checks"]}
    assert by_id["structure"]["status"] == "pass"
    assert by_id["json_syntax"]["status"] == "pass"
    assert by_id["readme_links"]["status"] == "pass"


def test_finish_task_marks_finished(context):
    ctx, registry = context
    result = registry.execute("finish_task", {"summary": "done"}, ctx)
    assert result["ok"] is True
    assert result["finished"] is True


def test_run_tests_disabled_by_default(context):
    ctx, registry = context
    result = registry.execute("run_tests", {"predefined_profile": "node"}, ctx)
    assert result["ok"] is False
    assert result["error"]["code"] == "execution_disabled"


def test_run_tests_reports_not_available_without_node(context, monkeypatch):
    ctx, registry = context
    ctx.config.allow_command_execution = True
    ctx.approve = lambda name, message: True
    monkeypatch.setattr("space_code_agent.tools.runner.shutil.which", lambda name: None)
    result = registry.execute("run_tests", {"predefined_profile": "node"}, ctx)
    assert result["ok"] is False
    assert result["error"]["code"] == "not_available"
    assert "not run" in result["error"]["message"]


def test_js_check_is_skipped_without_node(context, monkeypatch):
    ctx, registry = context
    registry.execute("write_file", {"path": "src/a.js", "content": "export const x = 1;\n"}, ctx)
    monkeypatch.setattr("space_code_agent.tools.validation.shutil.which", lambda name: None)
    result = registry.execute("inspect_project", {"checks": ["js"]}, ctx)
    assert result["checks"][0]["status"] == "skipped"
    assert "not run" in result["checks"][0]["details"]["reason"]


def test_tool_audit_log_written(context):
    ctx, registry = context
    registry.execute("write_file", {"path": "a.txt", "content": "x"}, ctx)
    registry.execute("read_file", {"path": "a.txt"}, ctx)
    log = (ctx.session.dir / "tools.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(log) == 2
    assert json.loads(log[0])["tool"] == "write_file"
