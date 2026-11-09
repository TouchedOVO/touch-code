"""UI-independent event model.

The controller emits plain dataclasses; the Qt worker translates them into
signals.  This keeps the whole agent testable without a display server.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Event:
    kind: str                      # phase|log|progress|file|task|validation|done|error|usage|report
    message: str = ""
    data: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    level: str = "info"            # info|warn|error|success

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "message": self.message,
            "data": self.data,
            "ts": self.ts,
            "level": self.level,
        }


class EventSink:
    """Collects events; useful for tests and for replay after a run."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)

    def of(self, kind: str) -> list[Event]:
        return [e for e in self.events if e.kind == kind]
