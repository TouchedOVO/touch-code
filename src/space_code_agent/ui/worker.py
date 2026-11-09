"""Qt worker thread: runs the controller off the UI thread."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QThread, Signal

from ..app.controller import Controller, ControllerResult, RunRequest
from ..app.events import Event


class ApprovalBridge(QObject):
    """Cross-thread approval request.

    The worker blocks on an event; the GUI slot answers on the main thread.
    """

    requested = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._wait: threading.Event | None = None
        self._answer = False

    def ask(self, name: str, message: str) -> bool:
        with self._lock:
            self._wait = threading.Event()
            self._answer = False
            wait = self._wait
        self.requested.emit(name, message)
        wait.wait(timeout=180)
        return self._answer

    def respond(self, approved: bool) -> None:
        with self._lock:
            self._answer = bool(approved)
            if self._wait is not None:
                self._wait.set()


class AgentWorker(QThread):
    event = Signal(object)
    finished_run = Signal(object)

    def __init__(self, request: RunRequest, parent=None) -> None:
        super().__init__(parent)
        self.request = request

    def run(self) -> None:  # noqa: D401 - Qt entry point
        controller = Controller(emit=self.event.emit)
        try:
            result: ControllerResult = controller.run(self.request)
        except Exception as exc:  # noqa: BLE001
            result = ControllerResult(status="failed", error=f"{type(exc).__name__}: {exc}")
            self.event.emit(Event(kind="error", message=result.error, level="error"))
        self.finished_run.emit(result)

    def cancel(self) -> None:
        self.request.cancel.set()
