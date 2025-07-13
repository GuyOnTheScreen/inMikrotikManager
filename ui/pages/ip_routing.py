# ui/pages/ip_routing.py

from __future__ import annotations
from typing import List, Optional

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox,
    QHeaderView, QSizePolicy, QFrame
)

from core.client import MikrotikClient
from core.taskrunner import CommandRunner
from utils.universal_parser import parse_detail_blocks
from widgets.ip_tool_panel import IpToolPanel

__all__ = ["RoutingPage"]


class RoutingPage(QWidget):
    """
    Displays `/ip route` table with flags & comments,
    plus a reusable Ping/Trace panel.
    """

    # Emits raw (command, lines) if you need them
    toolFinished = pyqtSignal(str, list)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._client: Optional[MikrotikClient] = None
        self._runner = None
        self._build_ui()
        self._wire()

    def _build_ui(self):
        headers = [
            "Flags", "Dst-Address", "Gateway", "Reachable",
            "Distance", "Scope", "Comment",
        ]

        # ── Sidebar ─────────────────────────────────────────────
        sidebar = QVBoxLayout()
        self.btn_refresh = QPushButton("Refresh Routes")
        sidebar.addWidget(self.btn_refresh)

        # shared Ping/Trace panel
        self.ip_tools = IpToolPanel(parent=self)
        sidebar.addWidget(self.ip_tools)
        sidebar.addStretch(1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)

        # ── Table ────────────────────────────────────────────────
        self.tbl = QTableWidget(0, len(headers))
        self.tbl.setHorizontalHeaderLabels(headers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.horizontalHeader().setStretchLastSection(True)

        root = QHBoxLayout(self)
        root.addLayout(sidebar)
        root.addWidget(sep)
        root.addWidget(self.tbl, 1)

    def _wire(self):
        self.btn_refresh.clicked.connect(self.refresh_routes)
        # forward ping/trace results
        self.ip_tools.toolFinished.connect(self.toolFinished.emit)
        # double-click → populate IP box
        self.tbl.doubleClicked.connect(self._row_double_clicked)

    def set_ssh_client(self, client: MikrotikClient | None):
        self._client = client
        self.ip_tools.set_ssh_client(client)

    def _runner_active(self) -> bool:
        return getattr(self, "_runner", None) and self._runner.isRunning()

    def refresh_routes(self):
        if not self._client:
            QMessageBox.warning(self, "No connection", "Connect to a router first.")
            return
        if self._runner_active():
            QMessageBox.information(self, "Busy", "Still fetching…")
            return

        cmd = "/ip route print detail without-paging"
        print(f"DEBUG: refreshing routes with `{cmd}`")
        self._runner = CommandRunner(self._client, cmd, parent=self)
        self._runner.finished.connect(self._on_done)
        self._runner.finished.connect(self._runner.deleteLater)
        self._runner.start()

    def _on_done(self, cmd: str, lines: List[str]):
        print(f"DEBUG: routes done `{cmd}`, {len(lines)} lines")
        recs = parse_detail_blocks(lines, "/ip route")
        self._fill_table(recs)
        self._runner = None

    def _fill_table(self, recs: List[dict]):
        self.tbl.setRowCount(0)
        for rec in recs:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)

            flags   = rec.get("_flags", "")
            decoded = ", ".join(rec.get("_decoded_flags", {}))

            self._set(r, 0, flags, decoded)
            self._set(r, 1, rec.get("dst-address", ""))
            self._set(r, 2, rec.get("gateway", ""))
            self._set(r, 3, rec.get("gateway-status", ""))
            self._set(r, 4, rec.get("distance", ""))
            self._set(r, 5, rec.get("scope", ""))
            self._set(r, 6, rec.get("comment", ""))

        self._fit_comment_column(self.tbl, 6)

    def _set(self, row: int, col: int, text: str, tooltip: str | None = None):
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        if tooltip:
            item.setToolTip(tooltip)
        self.tbl.setItem(row, col, item)

    def _fit_comment_column(self, table: QTableWidget, col: int, max_px: int = 400):
        hdr = table.horizontalHeader()
        table.resizeColumnsToContents()
        if table.columnWidth(col) > max_px:
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(col, max_px)
            table.setWordWrap(True)
        else:
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        table.resizeRowsToContents()

    def _row_double_clicked(self, idx):
        gw  = self.tbl.item(idx.row(), 2).text()
        dst = self.tbl.item(idx.row(), 1).text()
        self.ip_tools.le_target.setText((gw or dst).split("/")[0])

    def closeEvent(self, ev):
        self.ip_tools.cleanup()
        if self._runner_active():
            self._runner.quit(); self._runner.wait()
        super().closeEvent(ev)
