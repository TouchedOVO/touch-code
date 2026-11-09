"""Tool primitives shared by every tool module."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from ..app.config import AppConfig
from ..app.events import Event
from ..core.session import FileRegistry, SessionStore
from ..security.policy import WorkspacePolicy
from ..security.secrets import SecretRedactor


class ToolError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


@dataclass
class ToolContext:
    policy: WorkspacePolicy
    config: AppConfig
    session: SessionStore
    files: FileRegistry
    redactor: SecretRedactor
    emit: Callable[[Event], None] = lambda event: None
    cancel: threading.Event = field(default_factory=threading.Event)
    approve: Callable[[str, str], bool] | None = None
    step: int = 0
    requirements: Any = None
    plan: Any = None

    def notify(self, kind: str, message: str, **data: Any) -> None:
        try:
            self.emit(Event(kind=kind, message=message, data=data))
        except Exception:
            pass


ToolHandler = Callable[[ToolContext, dict], dict]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    handler: ToolHandler
    requires_approval: bool = False
    category: str = "filesystem"

    def schema(self) -> dict:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "strict": False,
        }
