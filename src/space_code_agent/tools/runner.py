"""Approval-gated test runner with a fixed command whitelist.

P0 keeps arbitrary shell disabled.  Only predefined profiles can run, only
inside the workspace, with a timeout, sanitized environment and captured
output.  The UI must explicitly approve each invocation.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from .base import ToolContext, ToolError, ToolSpec

PROFILES: dict[str, list[str]] = {
    "node": ["node", "--test"],
    "npm": ["npm", "test", "--silent"],
    "pytest": [sys.executable, "-m", "pytest", "-q"],
}

_SAFE_ENV_KEYS = (
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES",
    "PROGRAMFILES(X86)", "PROGRAMDATA", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
)


def _sanitized_env() -> dict[str, str]:
    env = {key: os.environ[key] for key in _SAFE_ENV_KEYS if key in os.environ}
    env["CI"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["NO_COLOR"] = "1"
    return env


def run_tests(context: ToolContext, args: dict) -> dict:
    profile = args.get("predefined_profile", "node")
    command = PROFILES.get(profile)
    if command is None:
        raise ToolError("unknown_profile", f"未知测试配置：{profile}，可用：{', '.join(PROFILES)}")
    if not context.config.allow_command_execution:
        raise ToolError("execution_disabled", "命令执行未启用（P0 默认关闭）。请在 GUI 中显式开启后再运行测试。")
    executable = shutil.which(command[0])
    if executable is None:
        raise ToolError("not_available", f"未找到可执行文件 {command[0]}；测试未运行（not run）。")

    if context.approve is None:
        raise ToolError("approval_required", "运行测试需要用户授权，但当前会话没有授权回调。")
    approved = context.approve("run_tests", f"即将在 {context.policy.root} 运行：{' '.join(command)}")
    if not approved:
        raise ToolError("approval_denied", "用户拒绝了测试执行授权；测试未运行（not run）。")

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [executable, *command[1:]],
            cwd=str(context.policy.root),
            env=_sanitized_env(),
            capture_output=True,
            timeout=context.config.test_command_timeout_s,
            shell=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        duration = round(time.perf_counter() - started, 2)
        context.notify("validation", f"测试 {profile} 结束，exit={completed.returncode}",
                       exit_code=completed.returncode, profile=profile)
        return {
            "ok": True,
            "summary": f"测试 {profile} 结束，退出码 {completed.returncode}（{duration}s）",
            "profile": profile,
            "command": " ".join(command),
            "exit_code": completed.returncode,
            "duration_s": duration,
            "passed": completed.returncode == 0,
            "output": output[: context.config.max_tool_output_chars],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or b"") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
        if isinstance(output, bytes):
            output = output.decode("utf-8", "replace")
        return {
            "ok": True,
            "summary": f"测试 {profile} 超时（>{context.config.test_command_timeout_s}s）",
            "profile": profile,
            "command": " ".join(command),
            "exit_code": None,
            "passed": False,
            "output": output[: context.config.max_tool_output_chars],
            "timed_out": True,
        }


SPECS = [
    ToolSpec(
        name="run_tests",
        description="Run one predefined project test profile after explicit user approval. Never accepts arbitrary commands.",
        parameters={
            "type": "object",
            "properties": {
                "predefined_profile": {"type": "string", "enum": sorted(PROFILES)},
            },
            "required": ["predefined_profile"],
            "additionalProperties": False,
        },
        handler=run_tests,
        category="runner",
    )
]
