# utils/arp_controller.py

from PyQt6.QtCore import QObject, pyqtSignal
from core.taskrunner import CommandRunner
from utils.universal_parser import parse_detail_blocks

class ArpController(QObject):
    """
    Fetches /ip arp entries and emits them as parsed records.
    """
    arpReady = pyqtSignal(list)  # List[dict]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = None
        self._runner = None

    def set_ssh_client(self, client):
        # Stop any in-flight runner
        if self._runner and self._runner.isRunning():
            self._runner.quit()
            self._runner.wait()
        self._client = client

    def refresh_arp(self):
        if not self._client or (self._runner and self._runner.isRunning()):
            return
        cmd = "/ip arp print detail without-paging"
        self._runner = CommandRunner(self._client, cmd)
        self._runner.finished.connect(self._on_done)
        self._runner.start()

    def _on_done(self, cmd: str, lines: list[str]):
        recs = parse_detail_blocks(lines, "/ip arp")
        self.arpReady.emit(recs)
