# core/route_controller.py
# core/route_controller.py

from PyQt6.QtCore import QObject, pyqtSignal
from core.taskrunner import CommandRunner
from utils.universal_parser import parse_detail_blocks


class RouteController(QObject):
    """
    Handles all MikroTik I/O for /ip route, ping, and trace.
    Emits:
      - routesReady(list[dict]) when a refresh completes.
      - cmdFinished(str, list[str]) when ping/trace completes.
    """
    routesReady = pyqtSignal(list)
    cmdFinished = pyqtSignal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = None
        self._refresh_runner = None
        self._tool_runners: list[CommandRunner] = []

    def set_ssh_client(self, client):
        # Stop any in‐flight refresh
        if self._refresh_runner and self._refresh_runner.isRunning():
            self._refresh_runner.quit()
            self._refresh_runner.wait()
        # Stop any ping/trace runners
        for tn in list(self._tool_runners):
            if tn.isRunning():
                tn.quit()
                tn.wait()
        self._tool_runners.clear()
        self._client = client

    def refresh_routes(self):
        if not self._client or (self._refresh_runner and self._refresh_runner.isRunning()):
            return
        cmd = "/ip route print detail without-paging"
        self._refresh_runner = CommandRunner(self._client, cmd)
        self._refresh_runner.finished.connect(self._on_refresh_done)
        self._refresh_runner.start()

    def _on_refresh_done(self, cmd: str, lines: list[str]):
        recs = parse_detail_blocks(lines, "/ip route")
        self.routesReady.emit(recs)

    def ping(self, target: str):
        if not self._client:
            return
        runner = CommandRunner(self._client, f"ping {target}")
        self._tool_runners.append(runner)
        def _cleanup_and_emit(c, l):
            self.cmdFinished.emit(c, l)
            runner.deleteLater()
            self._tool_runners.remove(runner)
        runner.finished.connect(_cleanup_and_emit)
        runner.start()

    def trace(self, target: str):
        if not self._client:
            return
        runner = CommandRunner(self._client, f"tool traceroute {target}")
        self._tool_runners.append(runner)
        def _cleanup_and_emit(c, l):
            self.cmdFinished.emit(c, l)
            runner.deleteLater()
            self._tool_runners.remove(runner)
        runner.finished.connect(_cleanup_and_emit)
        runner.start()

    def stop(self):
        # Called on close to ensure no threads linger
        if self._refresh_runner and self._refresh_runner.isRunning():
            self._refresh_runner.quit()
            self._refresh_runner.wait()
        for tn in list(self._tool_runners):
            if tn.isRunning():
                tn.quit()
                tn.wait()
        self._tool_runners.clear()
