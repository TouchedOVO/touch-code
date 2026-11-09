"""SpaceCode Agent desktop entry point.

Modes:
  (default)          launch the PySide6 GUI
  --mock-run <dir>   headless deterministic demo (no API key required)
  --run <dir>        headless real DeepSeek run (key from env or --api-key)
  --smoke-test       headless Qt start-up check used by the packaging pipeline
  --version          print version and exit

The GUI process never performs blocking API work on the main thread.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _version() -> str:
    from . import __version__

    return f"SpaceCode Agent {__version__} (Python {sys.version.split()[0]})"


def _safe_print(text: str) -> None:
    """Windowed PyInstaller builds have sys.stdout=None; never crash on logging."""
    try:
        if sys.stdout is not None:
            print(text, flush=True)
    except Exception:
        pass


def _print_event(event) -> None:
    prefix = {
        "phase": "[phase]",
        "log": "[log]",
        "tool": "[tool]",
        "file": "[file]",
        "validation": "[check]",
        "error": "[error]",
        "done": "[done]",
        "report": "[report]",
    }.get(event.kind, f"[{event.kind}]")
    _safe_print(f"{prefix} {event.message}")


def _headless(argv: list[str]) -> int | None:
    if "--mock-run" not in argv and "--run" not in argv:
        return None
    parser = argparse.ArgumentParser(prog="space-code-agent", add_help=False)
    parser.add_argument("--mock-run", metavar="OUTPUT_DIR")
    parser.add_argument("--run", metavar="OUTPUT_DIR")
    parser.add_argument("--doc", default="")
    parser.add_argument("--uml", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--allow-tests", action="store_true")
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--max-repair-rounds", type=int, default=-1)
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--allow-model-override", action="store_true")
    parser.add_argument("--effort", default="high")
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        print(f"未知参数: {unknown}", file=sys.stderr)
        return 2
    if not args.mock_run and not args.run:
        return None
    if not args.doc or not args.uml:
        print("--doc 与 --uml 必填。", file=sys.stderr)
        return 2
    from .app.config import DEFAULT_MODEL, AppConfig
    from .app.controller import Controller, RunRequest

    if args.model != DEFAULT_MODEL and not args.allow_model_override:
        print(f"正式模式必须使用 {DEFAULT_MODEL}；如确需实验模型，请显式加 --allow-model-override。",
              file=sys.stderr)
        return 2
    config = AppConfig(
        model=args.model,
        allow_model_override=args.allow_model_override,
        reasoning_effort=args.effort,
    )
    if args.max_steps:
        config.max_agent_steps = args.max_steps
    if args.max_repair_rounds >= 0:
        config.max_repair_rounds = args.max_repair_rounds
    config.allow_command_execution = args.allow_tests
    api_key = ""
    if args.run:
        api_key = args.api_key or os.environ.get(args.api_key_env, "")
        if not api_key:
            print(f"真实模式需要 API Key：--api-key 或环境变量 {args.api_key_env}", file=sys.stderr)
            return 2
    else:
        config.mock_mode = True

    controller = Controller(emit=_print_event)
    request = RunRequest(
        doc_path=args.doc,
        view_path=args.uml,
        output_dir=args.mock_run or args.run,
        config=config,
        api_key=api_key,
        approve=(lambda name, message: True) if args.allow_tests else None,
    )
    result = controller.run(request)
    summary = json.dumps(result.as_dict(), ensure_ascii=False, indent=2)
    _safe_print(summary)
    # Windowed builds have no console: persist the result next to the output root.
    try:
        base = Path(args.mock_run or args.run).expanduser()
        target = base.parent / f"{base.name}-agent-result.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(summary, encoding="utf-8")
    except OSError:
        pass
    if result.status == "completed":
        return 0
    return 2 if result.status in {"partial", "cancelled"} else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--version" in argv:
        print(_version())
        return 0

    headless = _headless(argv)
    if headless is not None:
        return headless

    smoke = "--smoke-test" in argv
    if smoke:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    # Imported lazily so --version/headless work even if Qt is unavailable.
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from .ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("SpaceCode Agent")
    app.setOrganizationName("SpaceCodeAgent")
    app.setApplicationDisplayName("SpaceCode Agent")
    if sys.platform == "win32":
        app.setFont(QFont("Microsoft YaHei UI", 9))

    window = MainWindow()
    window.show()

    if smoke:
        QTimer.singleShot(250, app.quit)
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
