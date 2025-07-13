# widgets/address.py
# ---------------------------------------------------------------------------
# DHCP-Lease / Address tools page
# ---------------------------------------------------------------------------

from __future__ import annotations
import json, ipaddress, re
from pathlib import Path
from typing import List, Dict, Any

from PyQt6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, pyqtSignal, QObject
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QComboBox
)

from core.client import MikrotikClient
from core.taskrunner import CommandRunner          # QThread subclass
from core.log import log_cmd                       # shared log util

# ---------- Utilities -------------------------------------------------------
def resource_path(rel: str) -> Path:
    base = Path(__file__).resolve().parents[1]      # project root
    return base / rel

def load_speed_packages() -> List[Dict[str, Any]]:
    with open(resource_path("data/speeds.json"), "r", encoding="utf-8") as fh:
        return json.load(fh)

# ---------- Table Model -----------------------------------------------------
class LeaseTableModel(QAbstractTableModel):
    HEADERS = ["#", "MAC", "IP", "Hostname", "Comment", "Status"]

    def __init__(self, rows: List[Dict[str, str]] | None = None, parent=None):
        super().__init__(parent)
        self._rows = rows or []

    # Qt overrides ...........................................................
    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row = self._rows[index.row()]
        return list(row.values())[index.column()]

    def headerData(self, section, orientation, role):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    # helpers .................................................................
    def replace_all(self, rows: List[Dict[str, str]]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_dict(self, row: int) -> Dict[str, str]:
        return self._rows[row]

# ---------- Main Page Widget ------------------------------------------------
class AddressPage(QWidget):
    staticAssigned = pyqtSignal(str, str, str)   # IP, MAC, rate

    def __init__(self, client: MikrotikClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.client = client
        self.speed_packages = load_speed_packages()
        self._setup_ui()
        self._connect_signals()

        # keep references to live workers
        self._workers: list[CommandRunner] = []

    # ---- UI -----------------------------------------------------------------
    def _setup_ui(self):
        self.tbl = QTableView(self)
        self.tbl_model = LeaseTableModel()
        self.tbl.setModel(self.tbl_model)

        # buttons
        self.btn_refresh       = QPushButton("Refresh")
        self.btn_find_free     = QPushButton("Find Free IP")
        self.btn_assign_static = QPushButton("Assign Static")
        self.btn_add           = QPushButton("Add")
        self.btn_edit          = QPushButton("Edit")
        self.btn_remove        = QPushButton("Remove")

        btn_row = QHBoxLayout()
        for b in (
            self.btn_refresh, self.btn_find_free, self.btn_assign_static,
            self.btn_add, self.btn_edit, self.btn_remove
        ):
            btn_row.addWidget(b)
        btn_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(btn_row)
        layout.addWidget(self.tbl)

    # ---- Signals ------------------------------------------------------------
    def _connect_signals(self):
        self.btn_refresh.clicked.connect(self.refresh_leases)
        self.btn_find_free.clicked.connect(self.handle_find_free)
        self.btn_assign_static.clicked.connect(self.handle_assign_static)
        self.btn_add.clicked.connect(lambda: self._crud_dialog("add"))
        self.btn_edit.clicked.connect(lambda: self._crud_dialog("edit"))
        self.btn_remove.clicked.connect(lambda: self._crud_dialog("remove"))

    # ---- Core Actions -------------------------------------------------------
    def refresh_leases(self):
        # Avoid launching a second job if one is still running
        if any(w.isRunning() for w in self._workers):
            QMessageBox.information(self, "Busy", "Still fetching leases …")
            return

        cmd = "/ip dhcp-server lease print as-value"
        runner = CommandRunner(self.client, cmd, parent=self)
        runner.finished.connect(self._on_leases_fetched)

        # lifetime-guard: own the runner until it finishes
        def _cleanup():
            self._workers.remove(runner)
            runner.deleteLater()
        runner.finished.connect(_cleanup)

        self._workers.append(runner)
        runner.start()

    def _on_leases_fetched(self, cmd: str, lines: List[str]):
        rows = self._parse_lease_lines(lines)
        self.tbl_model.replace_all(rows)

    # quick-n-dirty parser (unchanged) .......................................
    def _parse_lease_lines(self, lines: List[str]) -> List[Dict[str, str]]:
        leases = []
        for ln in lines:
            if "address=" in ln:
                fields = dict(item.split("=", 1) for item in ln.split(" ") if "=" in item)
                leases.append({
                    "#":        fields.get(".id", ""),
                    "MAC":      fields.get("mac-address", ""),
                    "IP":       fields.get("address", ""),
                    "Hostname": fields.get("host-name", ""),
                    "Comment":  fields.get("comment", ""),
                    "Status":   fields.get("status", ""),
                })
        return leases

    # ---- Find-Free-IP placeholder ------------------------------------------
    def handle_find_free(self):
        QMessageBox.information(self, "Free IP", "Feature coming soon!")

    # ---- Assign Static Wizard ----------------------------------------------
    def handle_assign_static(self):
        row = self.tbl.currentIndex().row()
        if row < 0:
            QMessageBox.warning(self, "No row", "Select a lease first.")
            return
        lease = self.tbl_model.row_dict(row)
        dlg = StaticWizard(lease, self.speed_packages, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            ip, mac, rate = dlg.result()
            self.staticAssigned.emit(ip, mac, rate)

    # ---- CRUD stubs ---------------------------------------------------------
    def _crud_dialog(self, mode: str):
        QMessageBox.information(self, "TODO", f"{mode.capitalize()} dialog TBD")

    # ---- Graceful shutdown --------------------------------------------------
    def closeEvent(self, event):
        for w in self._workers:
            if w.isRunning():
                w.quit()
                w.wait()
        super().closeEvent(event)

# ---------- Static Wizard Dialog (unchanged) -------------------------------
class StaticWizard(QDialog):
    def __init__(self, lease: Dict[str, str], speeds: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assign Static")
        self._lease = lease
        self._speeds = speeds
        self._build_ui()

    def _build_ui(self):
        form = QFormLayout(self)
        self.le_ip  = QLineEdit(self._lease["IP"])
        self.le_mac = QLineEdit(self._lease["MAC"])
        self.cb_rate = QComboBox()
        self.cb_rate.addItems([p["name"] for p in self._speeds])
        form.addRow("IP Address:", self.le_ip)
        form.addRow("MAC Address:", self.le_mac)
        form.addRow("Speed Package:", self.cb_rate)

    def result(self):
        return (
            self.le_ip.text().strip(),
            self.le_mac.text().strip(),
            self.cb_rate.currentText().strip(),
        )
