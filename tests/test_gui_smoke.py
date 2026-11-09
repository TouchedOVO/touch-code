"""GUI smoke test (headless Qt)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

from space_code_agent.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_main_window_constructs(app):
    window = MainWindow()
    try:
        assert "SpaceCode Agent" in window.windowTitle()
        assert window.model_combo.currentText() == "deepseek-v4-pro"
        assert window.effort_combo.currentText() == "high"
        assert window.run_btn.isEnabled()
        assert window.stop_btn.isEnabled() is False
        assert window.tabs.count() == 5
        window.key_edit.setText("sk-abcdef123456")
        assert window.key_edit.echoMode().name == "Password"
        window.show_key.setChecked(True)
        assert window.key_edit.echoMode().name == "Normal"
    finally:
        window.close()


def test_basic_input_validation_reports_missing_files(app):
    window = MainWindow()
    try:
        issues = window._basic_input_issues()
        assert any("架构文档" in issue for issue in issues)
        assert any("输出目录" in issue for issue in issues)
    finally:
        window.close()
