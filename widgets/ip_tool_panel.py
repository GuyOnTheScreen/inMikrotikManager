# widgets/ip_tool_panel.py

from typing import Optional
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QPushButton,
    QMessageBox, QSizePolicy
)
from core.taskrunner import CommandRunner

class IpToolPanel(QWidget):
    """
    IP/hostname entry + Ping & Trace buttons.
    Pops up on completion and emits `toolFinished(cmd, lines)`.
    """
    toolFinished = pyqtSignal(str, list)

    def __init__(self, ssh_client=None, parent=None):
        super().__init__(parent)
        self._ssh = ssh_client
        self._runner: Optional[CommandRunner] = None
        self._build_ui()
        self._wire()

    def _build_ui(self):
        self.le_target = QLineEdit()
        self.le_target.setPlaceholderText("IP or hostname…")
        self.le_target.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Fixed)

        self.btn_ping  = QPushButton("Ping")
        self.btn_trace = QPushButton("Trace")

        layout = QVBoxLayout(self)
        layout.addWidget(self.le_target)
        layout.addWidget(self.btn_ping)
        layout.addWidget(self.btn_trace)
        layout.addStretch(1)

    def _wire(self):
        # add a count so the tool traceroute actually completes in ~5 probes
        self.btn_ping .clicked.connect(lambda: self._run_tool("ping count=5"))
        self.btn_trace.clicked.connect(lambda: self._run_tool("tool traceroute count=5"))

    def set_ssh_client(self, ssh_client):
        self._ssh = ssh_client

    def _runner_active(self) -> bool:
        return self._runner is not None and self._runner.isRunning()

    def _run_tool(self, base_cmd: str):
        tgt = self.le_target.text().strip()
        if not self._ssh:
            QMessageBox.warning(self, "No Connection", "Connect to a router first.")
            return
        if not tgt:
            QMessageBox.information(self, "No Target", "Enter an IP or hostname first.")
            return
        if self._runner_active():
            QMessageBox.information(self, "Busy", "Still running previous task…")
            return

        cmd = f"{base_cmd} {tgt}"
        print(f"DEBUG: starting tool runner `{cmd}`")
        self._runner = CommandRunner(self._ssh, cmd, parent=self)
        self._runner.finished.connect(self._on_done)
        self._runner.finished.connect(self._runner.deleteLater)
        self._runner.start()

    def _on_done(self, cmd: str, lines: list[str]):
        print(f"DEBUG: tool done `{cmd}` -> {len(lines)} lines")
        QMessageBox.information(self, cmd, "\n".join(lines) or "<no output>")
        self.toolFinished.emit(cmd, lines)
        self._runner = None

    def cleanup(self):
        if self._runner_active():
            self._runner.quit()
            self._runner.wait()
