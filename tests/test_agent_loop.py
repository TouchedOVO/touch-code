"""M3 tests: bounded agent loop, call_id pairing, cancellation and budgets."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from space_code_agent.agent.orchestrator import AgentOrchestrator
from space_code_agent.app.config import AppConfig
from space_code_agent.app.events import EventSink
from space_code_agent.core.requirements import (
    NormalizedRequirements,
    RequirementItem,
    SourceRef,
)
from space_code_agent.core.session import FileRegistry, SessionStore
from space_code_agent.providers.mock import MockProvider, text_response, tool_response
from space_code_agent.security.policy import WorkspacePolicy
from space_code_agent.tools import build_registry


def make_env(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    config = AppConfig(max_agent_steps=20, max_tool_output_chars=4000)
    session = SessionStore(workspace)
    policy = WorkspacePolicy(workspace, max_file_bytes=config.max_file_bytes)
    requirements = NormalizedRequirements(
        project_name="Demo",
        requirements=[RequirementItem(id="FR-1", kind="FR", title="Demo feature",
                                      source=SourceRef(document="d.md"))],
    )
    return workspace, config, session, policy, requirements


def build_orchestrator(tmp_path, responses, completion_check, config=None):
    workspace, base_config, session, policy, requirements = make_env(tmp_path)
    config = config or base_config
    registry = build_registry(config)
    sink = EventSink()
    orchestrator = AgentOrchestrator(
        provider=MockProvider(responses),
        registry=registry,
        config=config,
        session=session,
        requirements=requirements,
        files=FileRegistry(),
        emit=sink,
        policy=policy,
        completion_check=completion_check,
    )
    return orchestrator, sink, workspace, session


def two_files_check(workspace: Path):
    def check():
        missing = [name for name in ("a.txt", "b.txt") if not (workspace / name).exists()]
        return (not missing, missing)
    return check


def test_agent_writes_files_and_finishes(tmp_path):
    script = [
        tool_response([("write_file", {"path": "a.txt", "content": "alpha"})]),
        tool_response([("write_file", {"path": "b.txt", "content": "beta"})]),
        tool_response([("finish_task", {"summary": "wrote both files"})]),
    ]
    orchestrator, sink, workspace, session = build_orchestrator(
        tmp_path, script, lambda: ((tmp_path / "ws" / "a.txt").exists()
                                   and (tmp_path / "ws" / "b.txt").exists(), [])
    )
    outcome = orchestrator.run()
    assert outcome.status == "completed"
    assert outcome.steps == 3
    assert outcome.tool_calls == 3
    assert outcome.finish_summary == "wrote both files"
    assert (workspace / "a.txt").read_text() == "alpha"
    assert (workspace / "b.txt").read_text() == "beta"
    assert sink.of("done")[-1].data["outcome"]["status"] == "completed"
    assert (session.dir / "events.jsonl").exists()


def test_every_function_call_has_matching_output(tmp_path):
    script = [
        tool_response([("write_file", {"path": "a.txt", "content": "alpha"})]),
        tool_response([("read_file", {"path": "a.txt"})]),
        tool_response([("finish_task", {"summary": "ok"})]),
    ]
    orchestrator, _, _, _ = build_orchestrator(
        tmp_path, script, lambda: ((tmp_path / "ws" / "a.txt").exists(), [])
    )
    orchestrator.run()
    # The second model call receives the output of the first function call.
    second_input = orchestrator.provider.inputs[1]
    calls = [item for item in second_input if item.get("type") == "function_call"]
    outputs = [item for item in second_input if item.get("type") == "function_call_output"]
    assert calls and outputs
    assert calls[0]["call_id"] == outputs[0]["call_id"] == outputs[0]["call_id"]


def test_invalid_arguments_are_reported_but_loop_continues(tmp_path):
    script = [
        tool_response([("write_file", {"path": "bad.txt"})]),  # missing content
        tool_response([("write_file", {"path": "a.txt", "content": "ok"})]),
        tool_response([("finish_task", {"summary": "recovered"})]),
    ]
    orchestrator, _, workspace, _ = build_orchestrator(
        tmp_path, script, lambda: ((workspace / "a.txt").exists(), [])
    )
    # completion lambda needs the workspace captured before build; rebuild after
    outcome = orchestrator.run()
    assert outcome.status == "completed"
    assert (workspace / "a.txt").exists()
    second_input = orchestrator.provider.inputs[1]
    output = next(item for item in second_input if item.get("type") == "function_call_output")
    assert '"code": "invalid_arguments"' in output["output"]


def test_cancellation_before_first_step(tmp_path):
    cancel = threading.Event()
    cancel.set()
    orchestrator, _, workspace, _ = build_orchestrator(
        tmp_path, [tool_response([("write_file", {"path": "a.txt", "content": "x"})])],
        lambda: (False, ["not started"]),
    )
    orchestrator.cancel = cancel
    outcome = orchestrator.run()
    assert outcome.status == "cancelled"
    assert not (workspace / "a.txt").exists()


def test_step_budget_stops_loop(tmp_path):
    config = AppConfig(max_agent_steps=1)
    script = [tool_response([("write_file", {"path": "a.txt", "content": "x"})])]
    orchestrator, sink, workspace, _ = build_orchestrator(
        tmp_path, script, lambda: ((workspace_missing(tmp_path)), [])
        , config=config,
    )
    outcome = orchestrator.run()
    assert outcome.status == "budget_exhausted"
    assert outcome.steps == 1


def workspace_missing(tmp_path):
    return not (tmp_path / "ws" / "a.txt").exists()


def test_repeated_finish_rejection_becomes_partial(tmp_path):
    script = [tool_response([("finish_task", {"summary": "done"})]) for _ in range(3)]
    orchestrator, sink, workspace, _ = build_orchestrator(
        tmp_path, script, lambda: (False, ["README.md missing"])
    )
    outcome = orchestrator.run()
    assert outcome.status == "partial"
    assert "README.md missing" in outcome.missing


def test_finish_rejection_then_repair_succeeds(tmp_path):
    def complete():
        exists = (tmp_path / "ws" / "README.md").exists()
        return exists, [] if exists else ["README.md missing"]

    script = [
        tool_response([("finish_task", {"summary": "premature"})]),
        tool_response([("write_file", {"path": "README.md", "content": "# repaired\n"})]),
        tool_response([("finish_task", {"summary": "fixed"})]),
    ]
    orchestrator, _, workspace, _ = build_orchestrator(tmp_path, script, complete)
    outcome = orchestrator.run()
    assert outcome.status == "completed"
    assert outcome.steps == 3
    assert (workspace / "README.md").read_text().startswith("# repaired")
    second_input = orchestrator.provider.inputs[1]
    assert any("README.md missing" in str(item.get("content", "")) for item in second_input)


def test_no_tool_calls_gets_nudged_then_partial(tmp_path):
    script = [text_response("I am done") for _ in range(4)]
    orchestrator, _, _, _ = build_orchestrator(
        tmp_path, script, lambda: (False, ["still missing"])
    )
    outcome = orchestrator.run()
    assert outcome.status == "partial"
    assert "still missing" in outcome.missing
