# widgets/net_tool_panel.py
from __future__ import annotations
import ipaddress, itertools, textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Iterable

from PyQt6.QtCore    import pyqtSignal, QTimer, QObject, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QPushButton, QMessageBox
)

from utils.text import clean_field
from utils.universal_parser import parse_detail_blocks


MAX_WORKERS = 100         # how many *Python* threads ping in parallel


# ──────────────────────────────────────────────────────────────────────
class NetToolPanel(QWidget):
    """
    Ping-Net  /  Ping-All-Nets widget
    ---------------------------------
    • Uses a global ThreadPoolExecutor (max 100 workers by default).
    • No QThreads are created ⇒ no ‘destroyed while running’ crashes.
    • Summary pop-ups list every scanned subnet and its usable-host range.
    """
    networkPingsDone = pyqtSignal(str, int)      # subnet / "ALL", count

    _pool: ThreadPoolExecutor | None = None      # singleton per process

    def __init__(self, ssh_client: Optional[object] = None, parent=None):
        super().__init__(parent)
        self._ssh = ssh_client

        # ---------- UI
        self.le_net  = QLineEdit(placeholderText="Network (e.g. 192.168.1.0/24)")
        self.btn_net = QPushButton("Ping Net")
        self.btn_all = QPushButton("Ping All Nets")

        lay = QVBoxLayout(self)
        lay.addWidget(self.le_net)
        lay.addWidget(self.btn_net)
        lay.addWidget(self.btn_all)
        lay.addStretch(1)

        # ---------- signals
        self.btn_net.clicked.connect(self._run_single)
        self.btn_all.clicked.connect(self._run_all)

        # make sure executor exists exactly once
        if NetToolPanel._pool is None:
            NetToolPanel._pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    # ------------------------------------------------------------------
    def set_ssh_client(self, ssh_client):
        self._ssh = ssh_client

    # ------------------------------------------------------------------
    # helpers
    def _host_span(self, net: ipaddress._BaseNetwork) -> str:
        hosts = list(net.hosts())
        return f"{hosts[0]}–{hosts[-1]}" if hosts else str(net.network_address)

    def _ssh_ping(self, host: str) -> tuple[str, str]:
        """Runs in pool-thread; returns (host, raw_output)."""
        out, err = self._ssh.execute(f"ping count=2 {host}")
        return host, (err or out).strip()

    # ------------------------------------------------------------------
    # actions
    def _run_single(self):
        subnet_txt = clean_field(self.le_net.text())
        if not subnet_txt:
            QMessageBox.information(self, "Ping Net", "Enter a subnet first.")
            return
        self._scan_subnets([subnet_txt], all_mode=False)

    def _run_all(self):
        if not self._ssh:
            QMessageBox.warning(self, "No Connection", "Connect first.")
            return
        raw, err = self._ssh.execute("/ip address print detail without-paging")
        if err:
            QMessageBox.critical(self, "Error", err)
            return

        recs   = parse_detail_blocks(raw.splitlines(), "/ip address")
        subnets = set()
        for r in recs:
            if "address" in r:
                net = ipaddress.ip_network(r["address"], strict=False)
                subnets.add(f"{net.network_address}/{net.prefixlen}")

        if not subnets:
            QMessageBox.information(self, "Ping All Nets", "Router has no subnets.")
            return

        self._scan_subnets(sorted(subnets), all_mode=True)

    # ------------------------------------------------------------------
    def _scan_subnets(self, subnets: Iterable[str], *, all_mode: bool):
        if not self._ssh:
            return

        self.btn_net.setEnabled(False)
        self.btn_all.setEnabled(False)

        summary_lines: list[str] = []
        remaining = len(subnets)

        # lambda that runs after each subnet
        def _one_done(net_str: str):
            nonlocal remaining
            rng = self._host_span(ipaddress.ip_network(net_str, strict=False))
            summary_lines.append(f"{net_str}   ({rng})")
            remaining -= 1
            if remaining == 0:
                title = "Ping All Nets Complete" if all_mode else "Ping Net Complete"
                QMessageBox.information(self, title, "\n".join(summary_lines))
                self.networkPingsDone.emit("ALL" if all_mode else net_str,
                                           len(summary_lines))
                self.btn_net.setEnabled(True)
                self.btn_all.setEnabled(True)

        # schedule each subnet sequentially so UI remains responsive
        # but inside each subnet hosts go in parallel
        for net_str in subnets:
            self._run_subnet_async(net_str, on_complete=_one_done)

    # ------------------------------------------------------------------
    def _run_subnet_async(self, net_str: str, *, on_complete):
        """
        Kick host-pings for *net_str* in the executor. When *every* host
        returned / errored we invoke *on_complete* in the Qt main thread.
        """
        try:
            net = ipaddress.ip_network(net_str, strict=False)
            hosts = list(net.hosts())
        except Exception as exc:
            QMessageBox.critical(self, "Invalid Network", f"{net_str}: {exc}")
            on_complete(net_str)
            return

        if not hosts:
            on_complete(net_str)
            return

        pool = NetToolPanel._pool
        futures = [pool.submit(self._ssh_ping, str(h)) for h in hosts]

        # poll futures with a tiny QTimer so we stay in Qt thread
        check = QTimer(self)
        check.setInterval(50)

        def _poll():
            done_now = [f for f in futures if f.done()]
            for f in done_now:
                futures.remove(f)
            if not futures:
                check.stop()
                on_complete(net_str)

        check.timeout.connect(_poll)
        check.start()
