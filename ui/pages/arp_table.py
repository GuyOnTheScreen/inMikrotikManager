# ui/pages/arp_table.py

from typing import List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox,
    QHeaderView, QSizePolicy, QFrame
)
from core.client import MikrotikClient
from utils.universal_parser import parse_detail_blocks
from utils.text import quote_field
from core.arp_controller import ArpController
from widgets.ip_tool_panel import IpToolPanel
from widgets.net_tool_panel import NetToolPanel

__all__ = ["ArpTablePage"]

class ArpTablePage(QWidget):
    """
    ARP table viewer + shared Ping/Trace panel + Ping-Net panel.
    Double-clicking an entry fills both panels and auto-looks up the subnet.
    """

    def __init__(self, host: str, username: str, password: str, parent=None):
        super().__init__(parent)
        self.host = host
        self.username = username
        self.password = password
        self._client: Optional[MikrotikClient] = None

        # controller for fetching ARP
        self._controller = ArpController(host, username, password)  # Pass creds; removed 'self'
        self._controller.arpReady.connect(self._populate_table)

        self._build_ui()
        self._wire()

    def _build_ui(self):
        headers = ["Flags", "Address", "MAC", "Interface", "Comment"]

        # sidebar
        sidebar = QVBoxLayout()
        self.btn_refresh = QPushButton("Refresh ARP")
        sidebar.addWidget(self.btn_refresh)

        self.ip_tools = IpToolPanel(parent=self)
        sidebar.addWidget(self.ip_tools)

        self.net_tools = NetToolPanel(parent=self)
        sidebar.addWidget(self.net_tools)

        sidebar.addStretch(1)

        # separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)

        # main table
        self.tbl = QTableWidget(0, len(headers))
        self.tbl.setHorizontalHeaderLabels(headers)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)

        # compose
        root = QHBoxLayout(self)
        root.addLayout(sidebar)
        root.addWidget(sep)
        root.addWidget(self.tbl, 1)

    def _wire(self):
        self.btn_refresh.clicked.connect(self._controller.refresh_arp)
        self.tbl.doubleClicked.connect(self._on_double_click)

    def set_ssh_client(self, client: MikrotikClient | None):
        self._client = client
        self._controller.set_ssh_client(client)
        self.ip_tools.set_ssh_client(client)
        self.net_tools.set_ssh_client(client)

    def _populate_table(self, recs: List[dict]):
        self.tbl.setRowCount(0)
        for rec in recs:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            vals = [
                rec.get("_flags", ""),
                rec.get("address", ""),
                rec.get("mac-address", ""),
                rec.get("interface", ""),
                rec.get("comment", "")
            ]
            for c, txt in enumerate(vals):
                itm = QTableWidgetItem(txt)
                itm.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.tbl.setItem(r, c, itm)

        self.tbl.resizeColumnsToContents()
        self.tbl.resizeRowsToContents()

    def _on_double_click(self, idx):
        row = idx.row()
        full_addr = self.tbl.item(row, 1).text()      # e.g. "192.168.1.5/24"
        iface     = self.tbl.item(row, 3).text()

        # 1) bare IP → Ping/Trace panel
        ip_only = full_addr.split("/", 1)[0]
        self.ip_tools.le_target.setText(ip_only)

        # 2) look up interface prefix from /ip address
        if self._client:
            cmd = f'/ip address print detail where interface={quote_field(iface)}'
            out, err = self._client.execute(cmd)
            if not err:
                recs = parse_detail_blocks(out.splitlines(), "/ip address")
                if recs and "address" in recs[0]:
                    # recs[0]["address"] is like "192.168.1.1/24"
                    addr_field = recs[0]["address"]
                    # extract the network's prefix:
                    prefix = addr_field.split("/", 1)[1] if "/" in addr_field else ""
                    # recs[0]["network"] is e.g. "192.168.1.0"
                    network = recs[0].get("network", addr_field.split("/")[0])
                    if prefix:
                        net_with_prefix = f"{network}/{prefix}"
                    else:
                        net_with_prefix = network
                    self.net_tools.le_net.setText(net_with_prefix)