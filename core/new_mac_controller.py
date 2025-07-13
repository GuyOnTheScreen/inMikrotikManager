"""
NewMacController
────────────────
• swap the DHCP-lease MAC
• (optionally) enable the lease
• hand off ALL queue work to QueueConverter + QueueConversionController
  so history & inverse cmds are recorded exactly once.
"""
from __future__ import annotations
import ipaddress
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool

from core.client                      import MikrotikClient
from core.queue_converter             import QueueConverter, QueueConversionError
from core.queue_conversion_controller import QueueConversionController
from utils.action_manager             import manager as action_manager
from core.log                         import append as log_append
from utils.universal_parser           import parse_detail_blocks


class NewMacController(QObject, QRunnable):
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        QRunnable.__init__(self); self.setAutoDelete(True)
        self._p: dict = {}

    # ───────────────────────────────── public
    def start_async(self, **kwargs) -> None:
        self._p = kwargs
        QThreadPool.globalInstance().start(self)

    # ───────────────────────────────── worker
    def run(self) -> None:
        try:
            with MikrotikClient(
                self._p["host"], self._p["user"],
                self._p["password"], self._p["port"]
            ) as cli:
                summary = self._process(cli, self._p)
            self.finished.emit(summary)
        except Exception as exc:
            self.error.emit(str(exc))

    # ───────────────────────────────── helpers
    @staticmethod
    def _find_lease(cli: "MikrotikClient", ip_addr: str) -> Optional[dict]:
        raw = cli.cmd(f"/ip dhcp-server lease print detail without-paging where address={ip_addr}").splitlines()
        recs = parse_detail_blocks(raw, "ip dhcp-server lease")
        return next((r for r in recs if r.get("address") == ip_addr), None)

    # core algorithm ----------------------------------------------------------
    def _process(self, cli: "MikrotikClient", p: dict) -> dict:
        ip_only = p["cidr"].split("/")[0]

        # 1) pull lease once, capture old MAC & rate
        lease = self._find_lease(cli, ip_only)
        if lease is None:
            raise RuntimeError(f"No DHCP lease found for {ip_only}")
        old_mac     = lease.get("mac-address", "")
        lease_rate  = lease.get("rate-limit", "").strip('"')

        # 2) swap MAC
        cli.cmd(f'/ip dhcp-server lease set [find address="{ip_only}"] mac-address={p["new_mac"]}')

        # 3) enable?
        if p["enable_lease"]:
            cli.cmd(f'/ip dhcp-server lease set [find address="{ip_only}"] disabled=no')

        # 4) queue / rate-limit handling
        qc     = QueueConversionController(cli, p["default_limit_at"])
        q_msg  = "No queue action"
        try:
            conv = QueueConverter(cli, p["default_limit_at"]).convert(ip_only, ip_only)
            # convert() has ALREADY cleared the lease's rate-limit
            lease_rate = conv["lease_rate"] or lease_rate
            conflict   = conv.get("conflict")
            if p["queue_action"] == "overwrite":
                if conflict:
                    qc._handle_conflict_direct(conflict, dhcp_name=ip_only,
                                               ip=ip_only, lease_rate=lease_rate)
                    q_msg = f"Overwrote static queue for {ip_only}"
                else:
                    qc._add_static_queue_direct(ip_only, ip_only, lease_rate)
                    q_msg = f"Added static queue for {ip_only}"
            elif p["queue_action"] == "remove_rate":
                # convert() already cleared rate; nothing else to do
                q_msg = f"Cleared DHCP rate-limit for {ip_only}"
            # else no_action → keep q_msg default
        except QueueConversionError as err:
            raise RuntimeError(f"Queue conversion error: {err}") from err

        # 5) summary
        gw = str(ipaddress.IPv4Interface(p["cidr"]).network.network_address + 1)
        return {"gateway": gw,
                "ip": ip_only,
                "old_mac": old_mac,
                "new_mac": p["new_mac"],
                "queue_msg": q_msg,
                }
