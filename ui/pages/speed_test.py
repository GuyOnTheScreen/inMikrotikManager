# ui/pages/speed_test.py
from __future__ import annotations

import typing as _t
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QMessageBox
)

from utils.ssh import SSHClient


# ──────────────────────────────────────────────────────────────────────────────
# Worker thread – run one bandwidth-test command
# ──────────────────────────────────────────────────────────────────────────────
class BandwidthRunner(QThread):
    finished = pyqtSignal(str, str)             # stdout, stderr

    def __init__(self, ssh: SSHClient, cmd: str, parent: QObject | None = None):
        super().__init__(parent)
        self._ssh = ssh
        self._cmd = cmd

    def run(self):                              # noqa: D401
        try:
            out, err = self._ssh.execute(self._cmd)
        except Exception as exc:                # pylint: disable=broad-except
            out, err = "", str(exc)
        self.finished.emit(out, err)


# ──────────────────────────────────────────────────────────────────────────────
# Main Page
# ──────────────────────────────────────────────────────────────────────────────
class SpeedTestPage(QWidget):
    """Runs /tool bandwidth-test in the background and streams the result."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.ssh_client: SSHClient | None = None
        self._runner: BandwidthRunner | None = None
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Run button
        top = QHBoxLayout()
        self.btn_run = QPushButton("Run Bandwidth Test")
        self.btn_run.clicked.connect(self._on_run_clicked)
        top.addWidget(self.btn_run)
        layout.addLayout(top)

        # Output area
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(QLabel("Test Output:"))
        layout.addWidget(self.output)

    # ------------------------------------------------------------------ Public
    def set_ssh_client(self, ssh: SSHClient | None):
        # If we disconnect while a test is running, stop it
        if ssh is None and self._runner and self._runner.isRunning():
            self._runner.requestInterruption()      # polite cancel
            self._runner.wait(3000)
        self.ssh_client = ssh

    # ------------------------------------------------------------------ Actions
    def _on_run_clicked(self):
        if not self.ssh_client:
            QMessageBox.warning(self, "Not connected", "Connect to a router first.")
            return
        if self._runner and self._runner.isRunning():
            QMessageBox.information(self, "Busy", "A test is already running.")
            return

        cmd = (
            "/tool bandwidth-test address=127.0.0.1 duration=5 "
            "protocol=tcp direction=both user=Temp password=TempPassword123"
        )

        self.output.clear()
        self.output.setPlainText("Running speed test…")
        self.btn_run.setEnabled(False)

        # spin up worker
        self._runner = BandwidthRunner(self.ssh_client, cmd, parent=self)
        self._runner.finished.connect(self._on_test_finished)
        self._runner.start()

    def _on_test_finished(self, stdout: str, stderr: str):
        self.btn_run.setEnabled(True)
        if stderr:
            self.output.setPlainText(f"Error:\n{stderr}")
        else:
            self.output.setPlainText(stdout or "<no output>")
        # auto-delete thread object
        self._runner.deleteLater()
        self._runner = None

    # ------------------------------------------------------------------ Cleanup
    def closeEvent(self, event):
        if self._runner and self._runner.isRunning():
            self._runner.requestInterruption()
            self._runner.quit()
            self._runner.wait()
        super().closeEvent(event)
