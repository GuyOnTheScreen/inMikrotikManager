#core/taskrunner.py

"""
CommandRunner – runs a single MikroTik command in a worker thread
so the GUI stays responsive.  Emits: finished(cmd: str, lines: list[str])
"""

from __future__ import annotations

from typing import List

from PyQt6.QtCore import QThread, pyqtSignal

from .client import MikrotikClient
from .log import append


class CommandRunner(QThread):
    finished = pyqtSignal(str, list)  # command, output lines

    def __init__(self, client: MikrotikClient, command: str, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.command = command
        self._result: List[str] = []

    # ----------------------------------------------- worker thread entrypoint
    def run(self) -> None:  # noqa: D401
        try:
            append(f"TASK {self.command} -> {self.client.host}")
            self._result = self.client.run(self.command)
        except Exception as exc:  # pylint: disable=broad-except
            self._result = [f"ERROR: {exc}"]
            append(f"TASK-ERR {exc}")
        finally:
            self.finished.emit(self.command, self._result)
