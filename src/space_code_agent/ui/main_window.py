"""Main window for SpaceCode Agent.

The window is intentionally thin: it collects inputs, starts a background
worker and renders events.  All policy, parsing and model work happens in the
application/agent layers.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..app.config import AppConfig
from ..app.controller import RunRequest
from ..core.document_parser import DocumentError, DocumentParser
from ..core.requirements import RequirementNormalizer
from ..providers.base import ProviderError
from ..providers.deepseek import DeepSeekProvider
from ..security.secrets import SecretRedactor, mask_key
from .worker import AgentWorker, ApprovalBridge

PLANTUML_BLOCK = re.compile(r"```plantuml\b.*?```", re.S | re.I)

STYLE = """
QMainWindow, QWidget { background: #f6f7fb; color: #1c2333; }
QGroupBox {
    background: #ffffff; border: 1px solid #e2e6f0; border-radius: 10px;
    margin-top: 14px; padding: 10px 12px 12px 12px; font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #3b4a66; }
QLineEdit, QComboBox, QPlainTextEdit, QListWidget, QTableWidget, QTabWidget::pane {
    background: #ffffff; border: 1px solid #dbe1ec; border-radius: 6px;
    selection-background-color: #d8e6ff; selection-color: #13233d;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border: 1px solid #4f7cff; }
QLineEdit { padding: 5px 7px; min-height: 20px; }
QPushButton {
    background: #ffffff; border: 1px solid #d4dae6; border-radius: 6px;
    padding: 6px 12px; min-height: 20px;
}
QPushButton:hover { background: #f0f4ff; border-color: #9db8ff; }
QPushButton:disabled { color: #9aa3b2; background: #f2f3f7; }
QPushButton#primary { background: #3f6fff; color: white; border: 1px solid #3f6fff; font-weight: 600; }
QPushButton#primary:hover { background: #315fdd; }
QPushButton#danger { color: #b42318; border-color: #f0c2bd; }
QPushButton#danger:hover { background: #fff2f0; }
QTabWidget::pane { border: 1px solid #dbe1ec; border-radius: 8px; top: -1px; }
QTabBar::tab {
    background: transparent; padding: 7px 14px; margin-right: 2px;
    border: 1px solid transparent; border-bottom: none; color: #5a657a;
}
QTabBar::tab:selected { background: #ffffff; border-color: #dbe1ec; border-radius: 6px 6px 0 0; color: #1c2333; }
QHeaderView::section { background: #f3f5fa; border: none; border-bottom: 1px solid #e2e6f0; padding: 5px; }
QProgressBar { background: #e9edf5; border: none; border-radius: 5px; height: 10px; text-align: center; }
QProgressBar::chunk { background: #3f6fff; border-radius: 5px; }
QStatusBar { background: #ffffff; border-top: 1px solid #e2e6f0; }
"""


class ConnectionTestThread(QThread):
    result = Signal(bool, str)

    def __init__(self, api_key: str, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self._key = api_key
        self._config = config

    def run(self) -> None:  # noqa: D401 - Qt entry point
        provider = None
        try:
            provider = DeepSeekProvider(self._key, self._config, SecretRedactor([self._key]))
            ok, message = provider.test_connection()
            self.result.emit(ok, message)
        except ProviderError as exc:
            self.result.emit(False, f"{exc.code}: {exc.message}")
        except Exception as exc:  # noqa: BLE001
            self.result.emit(False, f"连接失败：{type(exc).__name__}: {exc}")
        finally:
            if provider is not None:
                provider.close()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  v{__version__}")
        self.resize(1120, 820)
        self.setMinimumSize(940, 680)
        self.setStyleSheet(STYLE)

        self.config = AppConfig()
        self._api_key = ""
        self._conn_thread: ConnectionTestThread | None = None
        self._running = False
        self._last_output_dir: Path | None = None
        self._worker: AgentWorker | None = None
        self._file_rows: dict[str, int] = {}
        self._planned_files = 0
        self._tool_count = 0
        self.approval = ApprovalBridge(self)

        self._build_ui()
        self._wire()
        self.approval.requested.connect(self._on_approval_requested)
        self._log("就绪。请填写 API Key 并选择两份架构 Markdown。", "info")
        self._update_status("空闲")

    # ------------------------------------------------------------------ #
    # construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        title = QLabel("SpaceCode Agent")
        title.setFont(QFont("Microsoft YaHei UI", 17, QFont.Weight.Bold))
        subtitle = QLabel("架构文档驱动的智能代码生成 Agent · DeepSeek-V4-Pro")
        subtitle.setStyleSheet("color:#6b768c;")
        root.addWidget(title)
        root.addWidget(subtitle)

        self.conn_box = self._build_connection_group()
        self.io_box = self._build_io_group()
        self.progress_box = self._build_progress_group()
        root.addWidget(self.conn_box)
        root.addWidget(self.io_box)
        root.addWidget(self.progress_box, 1)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self._build_statusbar()

    def _build_connection_group(self) -> QGroupBox:
        box = QGroupBox("连接配置")
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel("DeepSeek API Key"), 0, 0)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("sk-...（仅保存在本次运行内存中）")
        grid.addWidget(self.key_edit, 0, 1, 1, 3)

        self.show_key = QCheckBox("显示")
        grid.addWidget(self.show_key, 0, 4)
        self.test_btn = QPushButton("测试连接")
        grid.addWidget(self.test_btn, 0, 5)
        self.conn_label = QLabel("未测试")
        self.conn_label.setStyleSheet("color:#8a93a6;")
        grid.addWidget(self.conn_label, 0, 6, 1, 2)

        grid.addWidget(QLabel("模型"), 1, 0)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)
        self.model_combo.addItems(["deepseek-v4-pro"])
        self.model_combo.setCurrentText(self.config.model)
        self.model_combo.setEnabled(False)
        self.model_combo.setToolTip("任务要求锁定 deepseek-v4-pro；不支持在 GUI 中替换模型。")
        grid.addWidget(self.model_combo, 1, 1)

        grid.addWidget(QLabel("思考强度"), 1, 2)
        self.effort_combo = QComboBox()
        self.effort_combo.addItems(["high", "max", "medium", "low", "none"])
        self.effort_combo.setCurrentText(self.config.reasoning_effort)
        grid.addWidget(self.effort_combo, 1, 3)

        self.mock_check = QCheckBox("Mock 模式（离线演示，不调用 API）")
        self.mock_check.setToolTip("用于自动化测试与无 Key 演示；生成结果来自内置确定性脚本。")
        grid.addWidget(self.mock_check, 1, 4, 1, 3)

        self.allow_tests_check = QCheckBox("允许运行项目测试（每次执行前授权）")
        self.allow_tests_check.setToolTip("只允许预定义测试配置（node/npm/pytest），不接受任意命令。")
        grid.addWidget(self.allow_tests_check, 2, 0, 1, 5)
        grid.setColumnStretch(1, 1)
        return box

    def _build_io_group(self) -> QGroupBox:
        box = QGroupBox("输入与输出")
        form = QGridLayout(box)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.doc_edit = QLineEdit()
        self.doc_edit.setPlaceholderText("Architecture_Documentation.md")
        self.uml_edit = QLineEdit()
        self.uml_edit.setPlaceholderText("Architecture_View.md")
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("生成的工程将写入此目录（非空时自动创建唯一子目录）")

        form.addWidget(QLabel("架构文档"), 0, 0)
        form.addWidget(self.doc_edit, 0, 1)
        doc_btn = QPushButton("浏览…")
        form.addWidget(doc_btn, 0, 2)

        form.addWidget(QLabel("UML 视图"), 1, 0)
        form.addWidget(self.uml_edit, 1, 1)
        uml_btn = QPushButton("浏览…")
        form.addWidget(uml_btn, 1, 2)

        form.addWidget(QLabel("输出目录"), 2, 0)
        form.addWidget(self.out_edit, 2, 1)
        out_btn = QPushButton("浏览…")
        form.addWidget(out_btn, 2, 2)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.check_btn = QPushButton("检查输入")
        self.run_btn = QPushButton("生成项目")
        self.run_btn.setObjectName("primary")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        self.open_btn = QPushButton("打开目录")
        self.open_btn.setEnabled(False)
        for button in (self.check_btn, self.run_btn, self.stop_btn, self.open_btn):
            buttons.addWidget(button)
        buttons.addStretch(1)
        form.addLayout(buttons, 3, 0, 1, 3)

        doc_btn.clicked.connect(lambda: self._pick_file("doc"))
        uml_btn.clicked.connect(lambda: self._pick_file("uml"))
        out_btn.clicked.connect(self._pick_output)
        return box

    def _build_progress_group(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        head = QHBoxLayout()
        self.phase_label = QLabel("阶段：空闲")
        self.phase_label.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
        self.count_label = QLabel("文件 0 / 0　工具调用 0")
        self.count_label.setStyleSheet("color:#6b768c;")
        head.addWidget(self.phase_label)
        head.addStretch(1)
        head.addWidget(self.count_label)
        layout.addLayout(head)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        layout.addWidget(self.progress)

        self.tabs = QTabWidget()
        self.task_list = QListWidget()
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setFont(QFont("Consolas", 9))
        self.files_table = QTableWidget(0, 3)
        self.files_table.setHorizontalHeaderLabels(["文件", "大小", "SHA-256 前 12 位"])
        self.files_table.horizontalHeader().setStretchLastSection(True)
        self.files_table.verticalHeader().setVisible(False)
        self.validation_view = QPlainTextEdit()
        self.validation_view.setReadOnly(True)
        self.validation_view.setFont(QFont("Consolas", 9))
        self.report_view = QPlainTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setFont(QFont("Consolas", 9))
        self.tabs.addTab(self.task_list, "任务")
        self.tabs.addTab(self.log_view, "实时日志")
        self.tabs.addTab(self.files_table, "文件清单")
        self.tabs.addTab(self.validation_view, "验证结果")
        self.tabs.addTab(self.report_view, "报告")
        layout.addWidget(self.tabs, 1)
        return widget

    def _build_statusbar(self) -> None:
        bar = self.statusBar()
        self.state_label = QLabel("状态：空闲")
        self.token_label = QLabel("Tokens：0")
        self.cost_label = QLabel("估算费用：$0.00")
        bar.addWidget(self.state_label)
        bar.addPermanentWidget(self.token_label)
        bar.addPermanentWidget(self.cost_label)
        bar.showMessage("输出仅写入你选择的目录；API Key 不会写入磁盘。")

    def _wire(self) -> None:
        self.show_key.toggled.connect(
            lambda checked: self.key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        self.test_btn.clicked.connect(self._test_connection)
        self.check_btn.clicked.connect(self._check_inputs)
        self.run_btn.clicked.connect(self._start_generation)
        self.stop_btn.clicked.connect(self._stop_generation)
        self.open_btn.clicked.connect(self._open_output)
        self.key_edit.textChanged.connect(self._on_key_changed)

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _configured(self) -> AppConfig:
        return self.config.copy(
            model=self.model_combo.currentText().strip() or self.config.model,
            reasoning_effort=self.effort_combo.currentText(),
            mock_mode=self.mock_check.isChecked(),
            allow_command_execution=self.allow_tests_check.isChecked(),
        )

    def _on_key_changed(self, text: str) -> None:
        self._api_key = text.strip()
        self.conn_label.setText("未测试")
        self.conn_label.setStyleSheet("color:#8a93a6;")

    def _log(self, message: str, level: str = "info") -> None:
        prefix = {"info": "·", "warn": "!", "error": "×", "success": "✓"}.get(level, "·")
        self.log_view.appendPlainText(f"[{self._now()}] {prefix} {message}")

    @staticmethod
    def _now() -> str:
        from datetime import datetime

        return datetime.now().strftime("%H:%M:%S")

    def _update_status(self, state: str) -> None:
        self.state_label.setText(f"状态：{state}")

    def _pick_file(self, kind: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Markdown 文档", "", "Markdown (*.md *.markdown);;所有文件 (*)"
        )
        if not path:
            return
        if kind == "doc":
            self.doc_edit.setText(path)
        else:
            self.uml_edit.setText(path)

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.out_edit.setText(path)

    # ------------------------------------------------------------------ #
    # input validation (structure only; full parse arrives in M2)
    # ------------------------------------------------------------------ #
    def _basic_input_issues(self) -> list[str]:
        issues: list[str] = []
        doc = Path(self.doc_edit.text().strip()) if self.doc_edit.text().strip() else None
        uml = Path(self.uml_edit.text().strip()) if self.uml_edit.text().strip() else None
        out = Path(self.out_edit.text().strip()) if self.out_edit.text().strip() else None

        if doc is None or not str(doc):
            issues.append("未选择架构文档。")
        elif not doc.is_file():
            issues.append(f"架构文档不存在：{doc}")
        if uml is None or not str(uml):
            issues.append("未选择 UML 视图文档。")
        elif not uml.is_file():
            issues.append(f"UML 视图文档不存在：{uml}")
        if out is None or not str(out):
            issues.append("未选择输出目录。")
        if doc and uml and doc.is_file() and uml.is_file() and doc.resolve() == uml.resolve():
            issues.append("两份输入文档不能是同一个文件。")

        for label, path in (("架构文档", doc), ("UML 文档", uml)):
            if not path or not path.is_file():
                continue
            try:
                size = path.stat().st_size
                if size == 0:
                    issues.append(f"{label}为空文件：{path.name}")
                elif size > self.config.max_input_bytes:
                    issues.append(f"{label}超过 {self.config.max_input_bytes // 1024 // 1024} MiB 上限。")
                raw = path.read_bytes()
                raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                issues.append(f"{label}不是 UTF-8 编码：{path.name}")
            except OSError as exc:
                issues.append(f"{label}无法读取：{exc}")
        return issues

    def _check_inputs(self) -> bool:
        issues = self._basic_input_issues()
        if issues:
            for issue in issues:
                self._log(issue, "error")
            QMessageBox.warning(self, "输入检查未通过", "\n".join(issues))
            return False
        doc = Path(self.doc_edit.text().strip())
        uml = Path(self.uml_edit.text().strip())
        try:
            parser = DocumentParser(self.config.max_input_bytes)
            parsed_doc = parser.parse(doc, "architecture")
            parsed_view = parser.parse(uml, "view")
            requirements = RequirementNormalizer().normalize(parsed_doc, parsed_view)
        except DocumentError as exc:
            self._log(f"解析失败（{exc.code}）：{exc.message}", "error")
            QMessageBox.critical(self, "输入解析失败", exc.message)
            return False
        except Exception as exc:  # noqa: BLE001
            self._log(f"解析异常：{type(exc).__name__}: {exc}", "error")
            QMessageBox.critical(self, "输入解析失败", f"{type(exc).__name__}: {exc}")
            return False

        blocks = len(parsed_view.diagrams)
        req_stats = requirements.summary_counts()
        conflict_lines = "\n".join(
            f"  • {conflict.id} [{conflict.severity}] {conflict.message[:80]}"
            for conflict in requirements.conflicts[:4]
        )
        message = (
            f"输入检查通过。\n\n"
            f"架构文档：{doc.name}（{parsed_doc.line_count} 行，{len(parsed_doc.sections)} 章节）\n"
            f"UML 文档：{uml.name}（{parsed_view.line_count} 行，{blocks} 个 PlantUML 块）\n"
            f"需求：{req_stats['requirements']} 条（显式 {req_stats['explicit']}，图推导 {req_stats['derived']}）\n"
            f"组件：{req_stats['components']}；冲突：{req_stats['conflicts']}；假设：{req_stats['assumptions']}\n"
        )
        if conflict_lines:
            message += f"\n主要冲突：\n{conflict_lines}\n"
        self._log(
            f"输入检查通过：{doc.name} + {uml.name}，{blocks} 个 PlantUML 块，"
            f"{req_stats['requirements']} 条需求。", "success",
        )
        QMessageBox.information(self, "输入检查通过", message)
        return True

    # ------------------------------------------------------------------ #
    # connection test
    # ------------------------------------------------------------------ #
    def _test_connection(self) -> None:
        if self.mock_check.isChecked():
            self.conn_label.setText("Mock 模式，无需连接")
            self.conn_label.setStyleSheet("color:#1a7f37;")
            return
        if not self._api_key:
            QMessageBox.warning(self, "缺少 API Key", "请先填写 DeepSeek API Key。")
            return
        if self._conn_thread is not None and self._conn_thread.isRunning():
            return
        self.test_btn.setEnabled(False)
        self.conn_label.setText("正在测试…")
        self.conn_label.setStyleSheet("color:#8a5a00;")
        self._conn_thread = ConnectionTestThread(self._api_key, self._configured(), self)
        self._conn_thread.result.connect(self._on_connection_result)
        self._conn_thread.finished.connect(lambda: self.test_btn.setEnabled(True))
        self._conn_thread.start()

    def _on_connection_result(self, ok: bool, message: str) -> None:
        self.conn_label.setText("连接成功" if ok else "连接失败")
        self.conn_label.setStyleSheet("color:#1a7f37;" if ok else "color:#b42318;")
        self._log(message, "success" if ok else "error")

    # ------------------------------------------------------------------ #
    # generation
    # ------------------------------------------------------------------ #
    def _start_generation(self) -> None:
        if self._running:
            return
        if not self._check_inputs():
            return
        config = self._configured()
        if not config.mock_mode and not self._api_key:
            QMessageBox.warning(self, "缺少 API Key", "真实模式需要 DeepSeek API Key；也可勾选 Mock 模式。")
            return
        output = self.out_edit.text().strip()
        if not output:
            QMessageBox.warning(self, "缺少输出目录", "请选择输出目录。")
            return

        self._reset_run_views()
        request = RunRequest(
            doc_path=self.doc_edit.text().strip(),
            view_path=self.uml_edit.text().strip(),
            output_dir=output,
            config=config,
            api_key=self._api_key,
            approve=self.approval.ask,
            cancel=threading.Event(),
        )
        self._running = True
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.open_btn.setEnabled(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("准备中…")
        self._update_status("运行中")
        self.tabs.setCurrentWidget(self.log_view)
        self._log(f"启动 Agent（{'Mock' if config.mock_mode else config.model}）…", "info")

        self._worker = AgentWorker(request, self)
        self._worker.event.connect(self._on_event)
        self._worker.finished_run.connect(self._on_worker_finished)
        self._worker.start()

    def _stop_generation(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self.stop_btn.setEnabled(False)
            self._update_status("正在取消…")
            self._log("已发出取消信号；将在当前工具调用结束后的安全检查点停止。", "warn")

    def _reset_run_views(self) -> None:
        self._file_rows.clear()
        self.files_table.setRowCount(0)
        self.task_list.clear()
        self.validation_view.clear()
        self.report_view.clear()
        self._tool_count = 0
        self._planned_files = 0
        self.count_label.setText("文件 0 / 0　工具调用 0")

    # ------------------------------------------------------------------ #
    # controller events (delivered on the GUI thread)
    # ------------------------------------------------------------------ #
    def _on_event(self, event) -> None:  # noqa: ANN001 - Event dataclass
        kind = event.kind
        data = event.data or {}
        if kind == "phase":
            phase = data.get("phase", "")
            self.phase_label.setText(f"阶段：{event.message}")
            self._update_status(f"运行中 · {phase}" if phase else "运行中")
            self._log(f"阶段：{event.message}", "info")
        elif kind == "plan":
            self._planned_files = len(data.get("files", []))
            self.task_list.clear()
            for task in data.get("tasks", []):
                item = QListWidgetItem(
                    f"{task.get('id', '')}  {task.get('title', '')}"
                    + (f"　[{', '.join(task.get('requirement_ids', []))}]"
                       if task.get("requirement_ids") else "")
                )
                item.setToolTip(task.get("description", ""))
                self.task_list.addItem(item)
            self._update_counts()
            self.tabs.setCurrentWidget(self.task_list)
        elif kind == "progress":
            step = int(data.get("step", 0) or 0)
            maximum = int(data.get("max_steps", 1) or 1)
            ratio = int(min(100, max(0, step * 100 / max(1, maximum))))
            self.progress.setValue(ratio)
            self.progress.setFormat(f"第 {step}/{maximum} 步")
        elif kind == "tool":
            self._tool_count += 1
            self._update_counts()
            self._log(event.message, "info" if data.get("ok", True) else "warn")
        elif kind == "file":
            self._add_file_row(data)
        elif kind == "usage":
            usage = data.get("usage", {})
            self.token_label.setText(
                f"Tokens：{usage.get('total_tokens', 0)}（入 {usage.get('input_tokens', 0)} / "
                f"出 {usage.get('output_tokens', 0)}）"
            )
            self.cost_label.setText(f"估算费用：${float(data.get('cost_usd', 0.0)):.4f}")
        elif kind == "validation":
            self.validation_view.appendPlainText(event.message)
            self._log(event.message, event.level)
        elif kind == "report":
            self._log("报告已生成，等待运行结束。", "success")
        elif kind == "error":
            self._log(event.message, "error")
        elif kind == "done":
            outcome = data.get("outcome", {})
            self._log(f"Agent 结束：{outcome.get('status')}", "info")
        elif kind in {"log", "check"}:
            self._log(event.message, event.level)
        else:
            self._log(event.message, event.level)

    def _add_file_row(self, data: dict) -> None:
        path = data.get("path", "")
        if not path:
            return
        size = int(data.get("bytes", 0) or 0)
        sha = str(data.get("sha256", ""))[:12]
        row = self._file_rows.get(path)
        if row is None:
            row = self.files_table.rowCount()
            self.files_table.insertRow(row)
            self._file_rows[path] = row
        self.files_table.setItem(row, 0, QTableWidgetItem(path))
        self.files_table.setItem(row, 1, QTableWidgetItem(self._human_bytes(size)))
        sha_item = QTableWidgetItem(sha)
        sha_item.setToolTip(data.get("sha256", ""))
        self.files_table.setItem(row, 2, sha_item)
        self.files_table.resizeColumnToContents(0)
        self._update_counts()

    @staticmethod
    def _human_bytes(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / 1024 / 1024:.2f} MB"

    def _update_counts(self) -> None:
        self.count_label.setText(
            f"文件 {len(self._file_rows)} / {self._planned_files}　工具调用 {self._tool_count}"
        )

    def _on_approval_requested(self, name: str, message: str) -> None:
        reply = QMessageBox.question(
            self,
            "需要你的授权",
            f"Agent 请求执行：{name}\n\n{message[:1600]}\n\n是否允许？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        self.approval.respond(reply == QMessageBox.StandardButton.Yes)

    def _on_worker_finished(self, result) -> None:  # noqa: ANN001 - ControllerResult
        self._running = False
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if result.output_dir:
            self._last_output_dir = Path(result.output_dir)
            self.open_btn.setEnabled(self._last_output_dir.exists())
        outcome = result.outcome
        if outcome is not None:
            usage = outcome.usage
            self.token_label.setText(
                f"Tokens：{usage.total_tokens}（入 {usage.input_tokens} / 出 {usage.output_tokens}）"
            )
            self.cost_label.setText(f"估算费用：${usage.cost_usd(self._configured()):.4f}")
            self.count_label.setText(
                f"文件 {len(self._file_rows)} / {self._planned_files}　工具调用 {outcome.tool_calls}"
            )
        if result.status == "completed":
            self.progress.setValue(100)
            self.progress.setFormat("完成")
        self._update_status({
            "completed": "完成",
            "partial": "部分完成",
            "cancelled": "已取消",
            "failed": "失败",
        }.get(result.status, result.status))
        if result.report_paths and self._last_output_dir:
            self._load_report(self._last_output_dir, result.report_paths)
        if result.status == "completed":
            coverage = result.coverage or {}
            QMessageBox.information(
                self,
                "生成完成",
                f"项目已生成并通过本地验收。\n\n输出目录：\n{result.output_dir}\n\n"
                f"文件映射：{coverage.get('percent', 0)}%（{coverage.get('mapped', 0)}/"
                f"{coverage.get('total', 0)}）\n"
                f"测试验证：{coverage.get('verified_percent', 0)}%（{coverage.get('verified', 0)}/"
                f"{coverage.get('total', 0)}）\n\n可在「报告」标签查看 GENERATION_REPORT.md。",
            )
        elif result.status == "cancelled":
            QMessageBox.information(self, "已取消", "任务已取消；已生成文件与运行状态均已保留。")
        else:
            detail = result.error or "；".join((outcome.missing if outcome else [])[:5])
            QMessageBox.warning(
                self, "生成未完全通过", f"状态：{result.status}\n\n{detail}\n\n"
                f"输出目录：{result.output_dir}\n请查看报告中的未通过项。",
            )
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _load_report(self, output_dir: Path, paths: dict) -> None:
        report_path = output_dir / paths.get("report", "")
        try:
            text = report_path.read_text(encoding="utf-8")
        except OSError:
            return
        self.report_view.setPlainText(text[:400_000])
        self.tabs.setCurrentWidget(self.report_view)

    def _open_output(self) -> None:
        target = self._last_output_dir or Path(self.out_edit.text().strip() or ".")
        if target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))
        else:
            QMessageBox.warning(self, "目录不存在", f"输出目录不存在：\n{target}")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._running and self._worker is not None:
            reply = QMessageBox.question(
                self, "任务仍在运行", "确定要退出吗？当前任务会被取消，已生成文件保留。"
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._worker.cancel()
            if not self._worker.wait(10_000):
                QMessageBox.warning(self, "仍在停止", "任务尚未到达安全检查点，请稍候再关闭窗口。")
                event.ignore()
                return
        if self._conn_thread is not None and self._conn_thread.isRunning():
            self._conn_thread.wait(1500)
        event.accept()
