"""
LeaseFetcher  (QObject run in its own QThread)
---------------------------------------------
Connect .lease_loaded(dict) or .error(str) to your slots.

Start with:

    fetcher = LeaseFetcher(..., parent_gui)
    fetcher.run_async()          # thread-safe, no COM crashes
"""

from __future__ import annotations
from typing import Optional, List, Dict

from PyQt6.QtCore import QObject, pyqtSignal, QThread
from core.client  import MikrotikClient
from utils.universal_parser import parse_detail_blocks


class LeaseFetcher(QObject):
    lease_loaded = pyqtSignal(dict)
    error        = pyqtSignal(str)

    # ---------------------------------------------------------------- init
    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        client_ip: str,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.host      = host
        self.port      = port
        self.user      = user
        self.password  = password
        self.client_ip = client_ip
        self._thread: QThread | None = None

    # ---------------------------------------------------------------- public
    def run_async(self):
        """Spin up a QThread, move self to it, start processing."""
        th = QThread()
        self._thread = th
        self.moveToThread(th)
        th.started.connect(self._process)
        # auto-cleanup
        self.lease_loaded.connect(th.quit)
        self.error.connect(th.quit)
        th.finished.connect(self.deleteLater)
        th.start()

    # ---------------------------------------------------------------- worker slot
    def _process(self):
        try:
            with MikrotikClient(self.host, self.user, self.password, self.port) as cli:
                lease = self._fetch_lease(cli, self.client_ip)
            if lease is None:
                self.error.emit("No matching lease found.")
            else:
                self.lease_loaded.emit(lease)
        except Exception as exc:                         # pragma: no cover
            self.error.emit(str(exc))

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _extract_index(first_line: str) -> str:
        import re
        m = re.match(r"\s*(?:#)?(\d+)", first_line.strip())
        return m.group(1) if m else ""

    @classmethod
    def _fetch_lease(cls, cli: "MikrotikClient", ip: str) -> Optional[dict]:
        cmd = f"/ip dhcp-server lease print detail without-paging where address={ip}"
        raw = cli.cmd(cmd).splitlines()

        blocks: List[Dict[str, str]] = parse_detail_blocks(raw, "ip dhcp-server lease")
        blk = next((b for b in blocks if b.get("address") == ip), None)
        if blk is None:
            return None

        lease_id = blk.get(".id", "").strip()
        if not lease_id:
            first = next((ln for ln in raw if ln.strip()), "")
            lease_id = cls._extract_index(first)

        lease = dict(blk)
        lease.update({"id": lease_id, "address": ip})
        return lease
