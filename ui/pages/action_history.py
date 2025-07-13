# ui/pages/action_history.py

import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt
from utils.action_manager import manager as action_manager

class ActionHistoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.ssh_client = None  # will be set by MainTestWindow

        # -------------------------------------------------- widgets
        self.refresh_btn = QPushButton("Refresh")
        self.undo_btn    = QPushButton("Undo Selected")
        self.clear_btn   = QPushButton("Clear History")

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Timestamp", "Action", "Details"]
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        # -------------------------------------------------- layout
        root = QHBoxLayout(self)

        # 1) sidebar
        sidebar = QVBoxLayout()
        for btn in (self.refresh_btn, self.undo_btn, self.clear_btn):
            btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Fixed)
            sidebar.addWidget(btn)
        sidebar.addStretch(1)
        root.addLayout(sidebar)

        # separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        # 2) main content
        content = QVBoxLayout()
        content.addWidget(self.table)
        root.addLayout(content, 1)

        # -------------------------------------------------- wire signals
        self.refresh_btn.clicked.connect(self.load_history)
        self.clear_btn.clicked.connect(self.clear_history)
        self.undo_btn.clicked.connect(self.undo_selected)

        # initial load
        self.load_history()

    def set_ssh_client(self, ssh_client):
        """Called by MainTestWindow to pass in the active SSHClient."""
        self.ssh_client = ssh_client

    def load_history(self):
        actions = action_manager.list_actions()
        self.table.setRowCount(len(actions))
        for row, entry in enumerate(actions):
            self.table.setItem(row, 0, QTableWidgetItem(str(entry["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(entry["timestamp"]))
            self.table.setItem(row, 2, QTableWidgetItem(entry["action"]))

            details_json = json.dumps(entry["details"], indent=2)
            item = QTableWidgetItem(details_json)
            item.setToolTip(details_json)
            # allow selection so user can copy/paste
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 3, item)

        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

    def clear_history(self):
        resp = QMessageBox.question(
            self, "Confirm Clear",
            "Are you sure you want to wipe the entire action history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            action_manager.clear()
            self.load_history()

    def undo_selected(self):
        if not self.ssh_client:
            QMessageBox.warning(self, "No Connection",
                                "Connect to a router first.")
            return

        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "No Selection",
                                "Select at least one action to undo.")
            return

        for idx in rows:
            action_id = int(self.table.item(idx.row(), 0).text())
            try:
                action_manager.undo(action_id, self.ssh_client)
            except Exception as e:
                QMessageBox.critical(self, "Undo Failed", str(e))
                return

        QMessageBox.information(self, "Undone", "Selected actions have been undone.")
        self.load_history()

        # if the Queues tab exists, refresh it so the UI reflects the change
        if hasattr(self.parent(), "queues"):
            self.parent().queues.refresh_queues()
            
        self.load_history()
