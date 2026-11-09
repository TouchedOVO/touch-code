"""Workspace confinement policy for every file operation.

Rules implemented here (and unit-tested):
  * only relative paths inside the chosen output workspace;
  * absolute paths, drive letters, UNC and extended-length prefixes rejected;
  * any ``..`` segment rejected before resolution;
  * canonicalisation + real-path containment defeats symlinks/junctions;
  * input documents and credential-shaped files are protected from writes;
  * Windows device names / trailing dots / alternate data streams rejected;
  * per-file size cap and atomic replacement.
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path, PureWindowsPath

_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_DEVICE_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_PROTECTED_NAMES = {
    ".env", "id_rsa", "id_ed25519", "credentials", "credentials.json",
    "secrets.json", "api_key.txt", "apikey.txt",
}
_PROTECTED_SUFFIXES = {".pem", ".key", ".pfx", ".p12"}
_IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".agent_state", "node_modules", "__pycache__",
    ".venv", "venv", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", ".next", ".cache",
}


class PolicyError(Exception):
    def __init__(self, code: str, message: str, path: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "path": self.path}


class WorkspacePolicy:
    def __init__(
        self,
        root: str | Path,
        *,
        max_file_bytes: int = 1024 * 1024,
        protected_paths: list[str | Path] | None = None,
        state_dir: str = ".agent_state",
        ignored_dirs: set[str] | None = None,
    ) -> None:
        self.root = Path(root).expanduser()
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PolicyError("workspace_error", f"无法创建输出工作区：{exc}", str(root)) from exc
        self.root = self.root.resolve()
        self.max_file_bytes = max_file_bytes
        self.state_dir = state_dir
        self.ignored_dirs = set(_IGNORED_DIRS) | {state_dir} | set(ignored_dirs or set())
        self.protected: set[str] = set()
        for path in protected_paths or []:
            self.add_protected(path)

    def add_protected(self, path: str | Path) -> None:
        try:
            self.protected.add(os.path.normcase(str(Path(path).expanduser().resolve())))
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # path resolution
    # ------------------------------------------------------------------ #
    @property
    def root_str(self) -> str:
        return str(self.root)

    def relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except (ValueError, OSError):
            return str(path)

    def resolve_dir(self, relative_path: str | Path = ".") -> Path:
        raw = str(relative_path or ".").strip()
        if raw in {"", "."}:
            return self.root
        target = self._resolve(raw)
        if not target.exists():
            raise PolicyError("not_found", f"目录不存在：{raw}", raw)
        if not target.is_dir():
            raise PolicyError("not_a_directory", f"不是目录：{raw}", raw)
        return target

    def resolve_read(self, relative_path: str | Path) -> Path:
        raw = str(relative_path).strip()
        if not raw:
            raise PolicyError("invalid_path", "路径不能为空。")
        target = self._resolve(raw)
        self._reject_protected_read(raw, target)
        if not target.exists():
            raise PolicyError("not_found", f"文件不存在：{raw}", raw)
        if not target.is_file():
            raise PolicyError("not_a_file", f"不是普通文件：{raw}", raw)
        return target

    def resolve_write(self, relative_path: str | Path, *, overwrite: bool) -> Path:
        raw = str(relative_path).strip()
        if not raw:
            raise PolicyError("invalid_path", "路径不能为空。")
        target = self._resolve(raw)
        self._reject_protected_write(raw, target)
        if target.exists():
            if target.is_dir():
                raise PolicyError("is_directory", f"目标是目录：{raw}", raw)
            if target.is_symlink():
                raise PolicyError("symlink_write", f"拒绝对符号链接/联接点写入：{raw}", raw)
            if not overwrite:
                raise PolicyError("exists", f"文件已存在且未授权覆盖：{raw}", raw)
        parent = target.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PolicyError("parent_error", f"无法创建父目录：{exc}", raw) from exc
        # Re-check after creating parents (a junction could appear concurrently).
        resolved_parent = parent.resolve()
        if not self._is_within(resolved_parent):
            raise PolicyError("escape", f"路径越界：{raw}", raw)
        return target

    def _resolve(self, raw: str) -> Path:
        self._check_raw(raw)
        candidate = Path(raw)
        if candidate.is_absolute():
            raise PolicyError("absolute_path", f"拒绝绝对路径：{raw}", raw)
        target = (self.root / candidate)
        try:
            resolved = target.resolve(strict=False)
        except OSError as exc:
            raise PolicyError("invalid_path", f"路径无法解析：{raw}", raw) from exc
        if not self._is_within(resolved):
            raise PolicyError("escape", f"路径越界：{raw}", raw)
        return resolved

    def _is_within(self, path: Path) -> bool:
        root = os.path.normcase(str(self.root))
        target = os.path.normcase(str(path))
        return target == root or target.startswith(root + os.sep)

    def _check_raw(self, raw: str) -> None:
        if "\x00" in raw:
            raise PolicyError("invalid_path", "路径包含空字符。", raw)
        if raw.startswith(("\\\\", "//", "\\?\\", "\\\\.\\")):
            raise PolicyError("unc_path", f"拒绝 UNC/扩展路径：{raw}", raw)
        if raw.startswith(("/", "\\")):
            raise PolicyError("absolute_path", f"拒绝绝对路径：{raw}", raw)
        if _DRIVE_RE.match(raw):
            raise PolicyError("absolute_path", f"拒绝盘符路径：{raw}", raw)
        if ":" in raw:
            raise PolicyError("ads_path", f"拒绝备用数据流/冒号路径：{raw}", raw)
        parts = PureWindowsPath(raw).parts
        if any(part == ".." for part in parts):
            raise PolicyError("parent_traversal", f"拒绝包含 .. 的路径：{raw}", raw)
        for part in parts:
            if part in {"", "."}:
                continue
            if part != part.rstrip(" ."):
                raise PolicyError("windows_name", f"路径段以点/空格结尾：{raw}", raw)
            if part.split(".")[0].upper() in _DEVICE_NAMES:
                raise PolicyError("device_name", f"拒绝 Windows 设备名：{raw}", raw)
            if re.search(r'[<>"|?*]', part):
                raise PolicyError("invalid_chars", f"路径包含非法字符：{raw}", raw)

    def _reject_protected_write(self, raw: str, target: Path) -> None:
        key = os.path.normcase(str(target))
        if key in self.protected:
            raise PolicyError("protected", f"拒绝覆盖输入/受保护文件：{raw}", raw)
        name = target.name.lower()
        if name in _PROTECTED_NAMES:
            raise PolicyError("protected", f"拒绝写入凭据类文件：{raw}", raw)
        if target.suffix.lower() in _PROTECTED_SUFFIXES:
            raise PolicyError("protected", f"拒绝写入密钥文件：{raw}", raw)

    def _reject_protected_read(self, raw: str, target: Path) -> None:
        relative_parts = PureWindowsPath(raw).parts
        if any(part.lower() == self.state_dir.lower() for part in relative_parts):
            raise PolicyError("state_read", "不允许读取 .agent_state 内部状态。", raw)
        if target.name.lower() in {".env", "id_rsa", "id_ed25519"}:
            raise PolicyError("secret_read", f"拒绝读取凭据文件：{raw}", raw)

    # ------------------------------------------------------------------ #
    # IO
    # ------------------------------------------------------------------ #
    def read_text(self, relative_path: str | Path, *, max_chars: int = 40_000) -> tuple[str, Path]:
        target = self.resolve_read(relative_path)
        size = target.stat().st_size
        if size > self.max_file_bytes * 4:
            raise PolicyError("too_large", f"文件过大，拒绝读取：{size} bytes", str(relative_path))
        data = target.read_bytes()
        if b"\x00" in data[:8192]:
            raise PolicyError("binary", f"拒绝读取二进制文件：{relative_path}", str(relative_path))
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise PolicyError("encoding", f"文件不是 UTF-8：{relative_path}", str(relative_path)) from exc
        return text[:max_chars], target

    def write_text_atomic(
        self,
        relative_path: str | Path,
        content: str,
        *,
        overwrite: bool = False,
        max_bytes: int | None = None,
    ) -> dict:
        data = content.encode("utf-8")
        limit = max_bytes if max_bytes is not None else self.max_file_bytes
        if len(data) > limit:
            raise PolicyError("too_large", f"内容超过单文件上限 {limit} bytes。", str(relative_path))
        target = self.resolve_write(relative_path, overwrite=overwrite)
        existed = target.exists()
        temp = target.with_name(f".{target.name}.tmp-{uuid.uuid4().hex[:8]}")
        try:
            with open(temp, "xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, target)
        except OSError as exc:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise PolicyError("write_error", f"写入失败：{exc}", str(relative_path)) from exc
        return {
            "path": self.relative(target),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "created": not existed,
            "overwritten": existed,
        }

    def delete_file(self, relative_path: str | Path) -> None:
        target = self.resolve_read(relative_path)
        try:
            target.unlink()
        except OSError as exc:
            raise PolicyError("delete_error", f"删除失败：{exc}", str(relative_path)) from exc

    # ------------------------------------------------------------------ #
    # enumeration
    # ------------------------------------------------------------------ #
    def iter_files(self, base: str = ".", pattern: str = "**/*", limit: int = 5000):
        start = self.resolve_dir(base)
        regex = _glob_to_regex(pattern)
        count = 0
        for dirpath, dirnames, filenames in os.walk(start, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if d.lower() not in self.ignored_dirs)
            for filename in sorted(filenames):
                full = Path(dirpath) / filename
                rel = full.relative_to(self.root).as_posix()
                if not regex.match(rel) and not regex.match(full.name):
                    continue
                try:
                    stat = full.stat()
                except OSError:
                    continue
                if full.is_symlink():
                    continue
                yield {"path": rel, "size": stat.st_size}
                count += 1
                if count >= limit:
                    return


def _glob_to_regex(pattern: str) -> re.Pattern:
    pattern = pattern.replace("\\", "/")
    translated = ""
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                translated += ".*"
                index += 2
                if index < len(pattern) and pattern[index] == "/":
                    index += 1
                continue
            translated += "[^/]*"
        elif char == "?":
            translated += "[^/]"
        else:
            translated += re.escape(char)
        index += 1
    return re.compile(translated, re.IGNORECASE)


def default_ignored_dirs() -> set[str]:
    return set(_IGNORED_DIRS)
