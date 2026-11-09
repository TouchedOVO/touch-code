"""Session persistence and file provenance registry."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..app.events import Event
from ..security.secrets import SecretRedactor


@dataclass
class FileRecord:
    path: str
    bytes: int
    sha256: str
    tool: str
    step: int
    created_at: float = field(default_factory=time.time)
    requirement_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "tool": self.tool,
            "step": self.step,
            "created_at": self.created_at,
            "requirement_ids": self.requirement_ids,
        }


class FileRegistry:
    def __init__(self) -> None:
        self.records: dict[str, FileRecord] = {}

    def record(self, result: dict, tool: str, step: int) -> FileRecord:
        record = FileRecord(
            path=result["path"],
            bytes=int(result.get("bytes", 0)),
            sha256=result.get("sha256", ""),
            tool=tool,
            step=step,
        )
        self.records[record.path] = record
        return record

    def remove(self, path: str) -> None:
        self.records.pop(path, None)

    def as_list(self) -> list[dict]:
        return [self.records[key].as_dict() for key in sorted(self.records)]

    def total_bytes(self) -> int:
        return sum(record.bytes for record in self.records.values())


class SessionStore:
    """Writes audit artefacts under ``<workspace>/.agent_state/<session>/``."""

    def __init__(self, workspace_root: str | Path, state_dir_name: str = ".agent_state",
                 session_id: str | None = None, redactor: SecretRedactor | None = None) -> None:
        self.root = Path(workspace_root)
        self.session_id = session_id or (
            datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        )
        self.dir = self.root / state_dir_name / self.session_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.redactor = redactor or SecretRedactor()
        self._events = self.dir / "events.jsonl"
        self._tools = self.dir / "tools.jsonl"
        self._history = self.dir / "history.jsonl"
        self.started_at = time.time()

    # -- generic ----------------------------------------------------------
    def _append(self, path: Path, payload: dict) -> None:
        clean = json.loads(self.redactor.redact(json.dumps(payload, ensure_ascii=False, default=str)))
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(clean, ensure_ascii=False, default=str) + "\n")

    def write_json(self, name: str, payload: Any) -> Path:
        path = self.dir / name
        clean = json.loads(self.redactor.redact(json.dumps(payload, ensure_ascii=False, default=str)))
        path.write_text(json.dumps(clean, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def write_text(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_text(self.redactor.redact(text), encoding="utf-8")
        return path

    def read_json(self, name: str, default: Any = None) -> Any:
        path = self.dir / name
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    # -- audit streams ----------------------------------------------------
    def log_event(self, event: Event) -> None:
        self._append(self._events, event.as_dict())

    def log_tool(self, step: int, name: str, arguments: dict, result: dict,
                 duration_ms: int) -> None:
        self._append(self._tools, {
            "ts": time.time(),
            "step": step,
            "tool": name,
            "arguments": arguments,
            "result_ok": bool(result.get("ok")),
            "summary": result.get("summary", ""),
            "duration_ms": duration_ms,
        })

    def log_history_items(self, items: list[dict]) -> None:
        for item in items:
            self._append(self._history, item)

    def artifact_index(self) -> list[dict]:
        items: list[dict] = []
        for path in sorted(self.dir.glob("*")):
            if path.is_file():
                data = path.read_bytes()
                items.append({
                    "name": path.name,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                })
        return items

    def close(self) -> None:
        self.write_json("session_index.json", {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "finished_at": time.time(),
            "artifacts": self.artifact_index(),
        })
