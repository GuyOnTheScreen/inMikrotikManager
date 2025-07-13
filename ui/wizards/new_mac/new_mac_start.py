# ui/wizards/new_mac/new_mac_start.py
"""
New-MAC Wizard  · 3 stacked pages
0  Input   —— CIDR / MAC / creds
1  Review  —— lease + queue options
2  Summary —— copy-able results
"""
from __future__ import annotations
import ipaddress, json, pathlib
from typing import Dict

from PyQt6.QtCore    import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QLabel,
    QPushButton, QHBoxLayout, QMessageBox, QStackedLayout
)

from widgets.credentials_panel                 import CredentialsPanel
from ui.wizards.new_mac.lease_fetcher          import LeaseFetcher
from ui.wizards.new_mac.lease_review_panel     import LeaseReviewPanel
from ui.wizards.new_mac.lease_summary_page     import LeaseSummaryPage
from core.new_mac_controller                   import NewMacController
from core.client                               import MikrotikClient


# ─────────────────────────────────────────────────────────── main widget
class NewMacStartPage(QWidget):
    finished = pyqtSignal(str)          # emitted with summary text

    # ------------------------------------------------------ init
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._pending : Dict = {}
        self._prev_gw : str | None = None

        self._controller  = NewMacController()
        self._fetcher_ref = None        # keep LeaseFetcher alive

        self._controller.error.connect(
            lambda m: QMessageBox.critical(self, "Controller Error", m)
        )

        # ── stacked pages
        self._stack        = QStackedLayout(self)
        self._page_input   = self._build_input_page()
        self._page_review  = QWidget()
        self._page_summary = QWidget()
        self._stack.addWidget(self._page_input)
        self._stack.addWidget(self._page_review)
        self._stack.addWidget(self._page_summary)

    # -------------------------------------------------- build INPUT page
    def _build_input_page(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)

        self.creds_panel = CredentialsPanel()

        # ── CIDR row with live-gateway label
        cidr_row = QHBoxLayout()
        self.le_ip  = QLineEdit(placeholderText="192.168.0.27/24")
        self.lbl_gw = QLabel("Gateway: —")
        self.lbl_gw.setAlignment(Qt.AlignmentFlag.AlignRight |
                                 Qt.AlignmentFlag.AlignVCenter)
        cidr_row.addWidget(self.le_ip, 2)
        cidr_row.addWidget(self.lbl_gw, 1)

        # new-MAC line-edit
        self.le_mac = QLineEdit(placeholderText="AA:BB:CC:DD:EE:FF")

        # form layout
        form = QFormLayout()
        form.addRow("Client IP /CIDR:", cidr_row)
        form.addRow("New MAC address:", self.le_mac)
        form.addWidget(self.creds_panel)
        v.addLayout(form)

        # signals
        self.le_ip.textChanged.connect(self._on_ip_changed)
        self.le_ip.editingFinished.connect(self._on_ip_finished)

        # Next button
        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(self._validate_and_fetch)
        v.addWidget(self.btn_next, alignment=Qt.AlignmentFlag.AlignRight)
        return w

    # -------------------------------------------------- helpers
    @staticmethod
    def _calc_gateway(ip_cidr: str) -> str | None:
        try:
            iface = ipaddress.IPv4Interface(ip_cidr)
            return str(iface.network.network_address + 1)
        except Exception:
            return None

    def _config_limit_at(self) -> str:
        cfg = pathlib.Path(__file__).resolve().parents[3] / "config" / "settings.json"
        return json.loads(cfg.read_text())["limit_at_default"]

    # -------------- live update while typing (label only)
    def _on_ip_changed(self, txt: str) -> None:
        gw = self._calc_gateway(txt.strip())
        self.lbl_gw.setText(f"Gateway: {gw or '—'}")
        self._prev_gw = gw

    # -------------- ALWAYS update Host when leaving CIDR box
    def _on_ip_finished(self) -> None:
        if self._prev_gw:
            self.creds_panel.le_host.setText(self._prev_gw)

    # -------------------------------------------------- Step-1: validate → fetch lease
    def _validate_and_fetch(self) -> None:
        ip_text = self.le_ip.text().strip()
        mac_raw = self.le_mac.text().strip()
        if not ip_text or not mac_raw:
            QMessageBox.warning(self, "Missing Fields", "IP/CIDR and MAC required.")
            return

        mac_clean = mac_raw.replace("-", ":").replace(".", ":").upper()
        creds = self.creds_panel.current_credentials()
        if not all(creds.values()):
            QMessageBox.warning(self, "Missing Fields", "Host, user and password required.")
            return

        self._pending = {"ip_text": ip_text, "new_mac": mac_clean, "creds": creds}
        self.btn_next.setEnabled(False)

        fetcher = LeaseFetcher(
            host      = creds["host"],
            port      = creds["port"],
            user      = creds["user"],
            password  = creds["password"],
            client_ip = ip_text.split("/")[0]
        )
        fetcher.lease_loaded.connect(self._show_review)
        fetcher.error.connect(
            lambda m: (QMessageBox.critical(self, "Fetch Error", m),
                       self.btn_next.setEnabled(True))
        )
        self._fetcher_ref = fetcher
        fetcher.run_async()

    # -------------------------------------------------- Step-2: review page
    def _show_review(self, lease: dict) -> None:
        creds = self._pending["creds"]
        panel = LeaseReviewPanel(
            lease,
            creds             = creds,
            new_mac           = self._pending["new_mac"],
            default_limit_at  = self._config_limit_at(),
            parent            = self,
        )
        panel.accepted.connect(self._run_controller)        # queue_action, enable_lease
        panel.cancelled.connect(lambda: self._stack.setCurrentIndex(0))

        self._stack.removeWidget(self._page_review)
        self._page_review = panel
        self._stack.insertWidget(1, panel)
        self._stack.setCurrentIndex(1)
        self.btn_next.setEnabled(True)

    # -------------------------------------------------- Step-3: run controller
    def _run_controller(self, queue_action: str, enable_lease: bool) -> None:
        p      = self._pending
        params = {
            "host":             p["creds"]["host"],
            "port":             p["creds"]["port"],
            "user":             p["creds"]["user"],
            "password":         p["creds"]["password"],
            "cidr":             p["ip_text"],
            "new_mac":          p["new_mac"],
            "queue_action":     queue_action,
            "enable_lease":     enable_lease,
            "default_limit_at": self._config_limit_at(),
        }

        self.btn_next.setEnabled(False)
        try:
            with MikrotikClient(
                params["host"], params["user"], params["password"], params["port"]
            ) as cli:
                summary = self._controller._process(cli, params)
            self._show_summary(summary)
        except Exception as e:
            QMessageBox.critical(self, "Controller Error", str(e))
        finally:
            self.btn_next.setEnabled(True)
            self._pending.clear()

    # -------------------------------------------------- summary page
    def _show_summary(self, info: dict) -> None:
        text = (
            f"Gateway : {info.get('gateway','—')}\n"
            f"IP      : {info.get('ip','—')}\n"
            f"Old MAC : {info.get('old_mac','—')}\n"
            f"New MAC : {info.get('new_mac','—')}\n"
            f"Queue   : {info.get('queue_msg','—')}\n"
        )
        page = LeaseSummaryPage(text, self)
        page.finished.connect(self._reset_input)

        self._stack.removeWidget(self._page_summary)
        self._page_summary = page
        self._stack.insertWidget(2, page)
        self._stack.setCurrentIndex(2)
        self.finished.emit(text)

    # -------------------------------------------------- reset wizard
    def _reset_input(self) -> None:
        self.le_ip.clear()
        self.le_mac.clear()
        self.creds_panel.le_host.clear()
        self.lbl_gw.setText("Gateway: —")
        self._prev_gw = None
        self._stack.setCurrentIndex(0)
