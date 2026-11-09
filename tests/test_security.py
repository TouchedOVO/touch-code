"""M3 tests: workspace confinement (T06/T07) and atomic writes."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from space_code_agent.security.policy import PolicyError, WorkspacePolicy


@pytest.fixture()
def policy(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    protected = tmp_path / "input.md"
    protected.write_text("# input", encoding="utf-8")
    return WorkspacePolicy(workspace, max_file_bytes=1024, protected_paths=[protected])


def test_write_read_roundtrip(policy):
    result = policy.write_text_atomic("src/app.js", "console.log('hi')\n")
    assert result["created"] is True
    assert result["bytes"] == 18
    assert len(result["sha256"]) == 64
    text, target = policy.read_text("src/app.js")
    assert text.startswith("console.log")
    assert target == policy.root / "src" / "app.js"


def test_no_overwrite_by_default(policy):
    policy.write_text_atomic("README.md", "a")
    with pytest.raises(PolicyError) as info:
        policy.write_text_atomic("README.md", "b")
    assert info.value.code == "exists"
    policy.write_text_atomic("README.md", "b", overwrite=True)
    assert policy.read_text("README.md")[0] == "b"


@pytest.mark.parametrize("bad", [
    "../escape.txt",
    "a/../../escape.txt",
    "C:\\Windows\\evil.txt",
    "\\\\server\\share\\evil.txt",
    "\\\\?\\C:\\evil.txt",
    "/etc/passwd",
    "a:b.txt",
    "CON",
    "aux.txt",
    "name.",
    "bad?.txt",
])
def test_rejects_unsafe_paths(policy, bad):
    with pytest.raises(PolicyError):
        policy.write_text_atomic(bad, "x")


def test_protected_input_file(policy, tmp_path):
    with pytest.raises(PolicyError) as info:
        policy.write_text_atomic(str(tmp_path / "input.md"), "overwrite")
    assert info.value.code in {"absolute_path", "escape"}


def test_protected_relative(policy):
    policy.add_protected(policy.root / "input.md")
    with pytest.raises(PolicyError) as info:
        policy.write_text_atomic("input.md", "x")
    assert info.value.code == "protected"


def test_credential_names_blocked(policy):
    for name in (".env", "id_rsa", "secret.pem", "secrets.json"):
        with pytest.raises(PolicyError):
            policy.write_text_atomic(name, "secret")


def test_size_limit(policy):
    with pytest.raises(PolicyError) as info:
        policy.write_text_atomic("big.txt", "x" * 2048)
    assert info.value.code == "too_large"


def test_state_dir_not_readable(policy):
    (policy.root / ".agent_state").mkdir()
    (policy.root / ".agent_state" / "x.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PolicyError) as info:
        policy.read_text(".agent_state/x.json")
    assert info.value.code == "state_read"


def test_binary_read_rejected(policy):
    (policy.root / "bin.dat").write_bytes(b"\x00\x01\x02")
    with pytest.raises(PolicyError) as info:
        policy.read_text("bin.dat")
    assert info.value.code == "binary"


def test_chinese_path(policy):
    result = policy.write_text_atomic("文档/说明.md", "# 中文")
    assert result["path"] == "文档/说明.md"
    assert policy.read_text("文档/说明.md")[0] == "# 中文"


def test_junction_escape_rejected(policy, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = policy.root / "link"
    try:
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        pytest.skip("cannot create junction")
    if proc.returncode != 0:
        pytest.skip(f"junction unavailable: {proc.stderr[:100]}")
    with pytest.raises(PolicyError) as info:
        policy.write_text_atomic("link/evil.txt", "x")
    assert info.value.code == "escape"


def test_iter_files_skips_state_and_respects_glob(policy):
    policy.write_text_atomic("a.txt", "a")
    policy.write_text_atomic("src/b.js", "b")
    (policy.root / ".agent_state").mkdir(exist_ok=True)
    (policy.root / ".agent_state" / "hidden.json").write_text("{}", encoding="utf-8")
    names = [entry["path"] for entry in policy.iter_files(".", "**/*")]
    assert "a.txt" in names
    assert "src/b.js" in names
    assert not any("agent_state" in name for name in names)
