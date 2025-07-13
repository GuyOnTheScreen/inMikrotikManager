# ui/pages/queue_management.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QDialog, QLineEdit, QLabel,
    QComboBox, QFormLayout, QInputDialog, QHeaderView,
    QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QModelIndex
from utils.ssh import SSHClient
import datetime
from utils.text import clean_field, quote_field
from utils.settings import get_limit_at_default, set_limit_at_default
from utils.universal_parser import parse_detail_blocks
from core.taskrunner import CommandRunner
from typing import List
from core.queue_converter import QueueConversionError
from core.log import append as log_append
from utils.action_manager import manager as action_manager
from core.queue_conversion_controller import QueueConversionController

LOG_FILE = "mikrotik_action_log.txt"

# Predefined speed packages
SPEED_PACKAGES = {
    "3200k/30900k": "3 / 30",
    "6200k/61600k": "6 / 60",
    "8300k/82100k": "8 / 80",
    "10300k/102500k": "10 / 100",
    "14400k/143500k": "14 / 140",
    "22600k/184500k": "22 / 180",
    "27700k/225400k": "27 / 220",
    "32900k/266400k": "32 / 260",
    "38000k/307300k": "37 / 300",
    "43100k/348300k": "42 / 340",
}

HEADERS = [
    "Flags", "Name", "Target", "Limit-At",
    "Max-Limit", "Queue Type", "Comment",
]

class QueuePage(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # -------------------------------------------------- instance fields
        self.ssh_client: SSHClient | None = None

        # -------------------------------------------------- widgets
        self.refresh_btn     = QPushButton("Refresh")
        self.delete_btn      = QPushButton("Delete Selected")
        self.add_btn         = QPushButton("Add Queue")
        self.convert_btn     = QPushButton("Convert DHCP Queue(s)")
        self.set_limit_btn   = QPushButton("Set Global Limit-At")
        self.apply_limit_btn = QPushButton("Apply Limit-At to Selected")

        self.queue_table = QTableWidget(0, len(HEADERS))
        self.queue_table.setHorizontalHeaderLabels(HEADERS)
        self.queue_table.horizontalHeader().setStretchLastSection(True)

        # -------------------------------------------------- layout
        root = QHBoxLayout(self)

        # 1) sidebar
        sidebar = QVBoxLayout()
        for b in (
            self.refresh_btn, self.delete_btn, self.add_btn,
            self.convert_btn, self.set_limit_btn, self.apply_limit_btn,
        ):
            b.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed)
            sidebar.addWidget(b)
        sidebar.addStretch(1)
        root.addLayout(sidebar)

        # separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        # 2) main content
        content = QVBoxLayout()
        content.addWidget(self.queue_table)
        root.addLayout(content, 1)

        # -------------------------------------------------- wire signals
        self.refresh_btn.clicked.connect(self.refresh_queues)
        self.delete_btn.clicked.connect(self.delete_selected_queue)
        self.add_btn.clicked.connect(self.open_add_dialog)
        self.convert_btn.clicked.connect(self.convert_dhcp_queues)
        self.set_limit_btn.clicked.connect(self.set_global_limit_at)
        self.apply_limit_btn.clicked.connect(self.apply_limit_at_to_selected)

    def _runner_active(self) -> bool:
        """True if a CommandRunner exists and is still running."""
        return getattr(self, "_runner", None) and self._runner.isRunning()

    def _fit_comment_column(self, table: QTableWidget, col: int, max_px: int = 400):
        header = table.horizontalHeader()
        table.resizeColumnsToContents()
        if table.columnWidth(col) > max_px:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(col, max_px)
            table.setWordWrap(True)
        else:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        table.resizeRowsToContents()

    def set_ssh_client(self, ssh_client):
        self.ssh_client = ssh_client

    def set_global_limit_at(self):
        current = get_limit_at_default()
        new, ok = QInputDialog.getText(
            self, "Set Global Limit-At",
            "Enter new limit-at value:", text=current
        )
        if ok and new:
            set_limit_at_default(new)
            QMessageBox.information(
                self, "Saved",
                f"New global limit-at value set:\n{new}"
            )

    def refresh_queues(self):
        if not self.ssh_client:
            QMessageBox.warning(self, "No connection", "Connect first.")
            return
        if self._runner_active():
            QMessageBox.information(self, "Busy", "Still fetching…")
            return

        cmd = "/queue simple print detail without-paging"
        self._runner = CommandRunner(self.ssh_client, cmd, parent=self)
        self._runner.finished.connect(self._on_queues_done)
        self._runner.finished.connect(self._runner.deleteLater)
        self._runner.start()

    def _on_queues_done(self, cmd: str, lines: List[str]):
        records = parse_detail_blocks(lines, "/queue simple")
        self._populate(records)
        self._runner = None

    def _populate(self, recs: list[dict]):
        tbl = self.queue_table
        tbl.setRowCount(0)

        for rec in recs:
            r = tbl.rowCount()
            tbl.insertRow(r)

            flags    = rec.get("_flags", "")
            disabled = bool(rec.get("disabled", False)) or "X" in flags

            data = [
                flags,
                rec.get("name", ""),
                rec.get("target", "").split("/")[0],
                rec.get("limit-at", ""),
                rec.get("max-limit", ""),
                rec.get("queue", ""),
                rec.get("comment", ""),
            ]
            for c, text in enumerate(data):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                if disabled:
                    item.setForeground(Qt.GlobalColor.darkGray)
                tbl.setItem(r, c, item)

        self._fit_comment_column(tbl, 6)

    def apply_limit_at_to_selected(self):
        rows = self.queue_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "No Selection", "Select at least one queue.")
            return

        limit_at = get_limit_at_default()
        failed = []

        for index in rows:
            row = index.row()
            name = clean_field(self.queue_table.item(row, 0).text())
            if not name:
                continue
            cmd = (
                f'/queue simple set '
                f'[find name={quote_field(name)}] '
                f'limit-at={limit_at}'
            )
            stdout, stderr = self.ssh_client.execute(cmd)
            if stderr or "failure" in stdout.lower():
                failed.append(name)
            else:
                log_append(f'Set limit-at={limit_at} for queue "{name}"')

        if failed:
            QMessageBox.warning(
                self, "Partial Failure",
                "Failed to update:\n" + "\n".join(failed)
            )
        else:
            QMessageBox.information(
                self, "Success",
                f"Limit-at set to {limit_at} for selected queue(s)."
            )
        self.refresh_queues()

    def convert_dhcp_queues(self):
        rows = self.queue_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(
                self, "No Selection",
                "Select at least one DHCP queue to convert."
            )
            return

        controller = QueueConversionController(
            self.ssh_client,
            get_limit_at_default(),
            parent_widget=self
        )

        for idx in rows:
            row    = idx.row()
            name   = clean_field(self.queue_table.item(row, 1).text())
            target = clean_field(self.queue_table.item(row, 2).text())

            resp = QMessageBox.question(
                self,
                "Confirm Conversion",
                f"Convert DHCP queue\n\n  Name: {name}\n"
                f"  Target: {target}\n\nto a static queue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if resp != QMessageBox.StandardButton.Yes:
                action_manager.record("convert_queue_skip", {
                    "name": name, "target": target, "action": "skipped"
                })
                log_append(f"SKIP: conversion of '{name}' ({target})")
                continue

            try:
                controller.convert_dhcp_queue(name, target)
            except QueueConversionError as e:
                QMessageBox.critical(self, "Conversion Failed", str(e))

        self.refresh_queues()

    def delete_selected_queue(self):
        row = self.queue_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a queue to delete.")
            return

        name = clean_field(self.queue_table.item(row, 0).text())
        confirm = QMessageBox.question(
            self, "Confirm Deletion",
            f"Delete queue '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        cmd = f"/queue simple remove [find name={quote_field(name)}]"
        stdout, stderr = self.ssh_client.execute(cmd)
        if stderr:
            QMessageBox.critical(self, "Error", f"Failed to delete queue:\n{stderr}")
            return

        details = {
            "name":   name,
            "target": clean_field(self.queue_table.item(row, 1).text()),
            "limit-at": clean_field(self.queue_table.item(row, 2).text()),
            "max-limit": clean_field(self.queue_table.item(row, 3).text()),
            "queue":     clean_field(self.queue_table.item(row, 4).text()),
            "comment":   clean_field(self.queue_table.item(row, 5).text()),
        }
        action_manager.record("delete_queue", details)
        log_append(f"Deleted queue: {details}")
        self.refresh_queues()

    def open_add_dialog(self):
        if not self.ssh_client:
            QMessageBox.warning(self, "Not Connected", "Connect first.")
            return

        dialog = AddQueueDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()
        cmd = (
            f'/queue simple add '
            f'name={quote_field(data["name"])} '
            f'target={quote_field(data["target"])} '
            f'limit-at={data["limit"]} '
            f'max-limit={data["max"]} '
            f'queue=default-small/default-small '
            f'comment={quote_field(data["comment"])}'
        )
        stdout, stderr = self.ssh_client.execute(cmd)
        if stderr:
            QMessageBox.critical(self, "Error", f"Failed to add queue:\n{stderr}")
            return

        action_manager.record("add_queue", data)
        log_append(f"Added queue: {data}")
        self.refresh_queues()

    def closeEvent(self, ev):
        if self._runner_active():
            self._runner.quit()
            self._runner.wait()
        super().closeEvent(ev)


class AddQueueDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Queue")

        self.name_edit = QLineEdit()
        self.target_edit = QLineEdit()
        self.comment_edit = QLineEdit()
        self.limit_edit = QLineEdit()
        self.max_edit = QLineEdit()
        self.limit_edit.setText(get_limit_at_default())

        self.package_combo = QComboBox()
        self.package_combo.addItem("Manual Entry")
        for k, v in SPEED_PACKAGES.items():
            self.package_combo.addItem(f"{v} Mbps ({k})", k)

        self.package_combo.currentIndexChanged.connect(self.update_limits)

        form = QFormLayout()
        form.addRow("Queue Name:", self.name_edit)
        form.addRow("Target IP:", self.target_edit)
        form.addRow("Comment:", self.comment_edit)
        form.addRow("Speed Package:", self.package_combo)
        form.addRow("Limit-At:", self.limit_edit)
        form.addRow("Max-Limit:", self.max_edit)

        btns = QHBoxLayout()
        ok = QPushButton("Add")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(btns)
        self.setLayout(layout)

    def update_limits(self):
        idx = self.package_combo.currentIndex()
        key = self.package_combo.currentData()
        if idx == 0 or key is None:
            self.limit_edit.clear()
            self.max_edit.clear()
        else:
            self.limit_edit.setText(key)
            self.max_edit.setText(key)

    def get_data(self):
        return {
            "name":    clean_field(self.name_edit.text()),
            "target":  clean_field(self.target_edit.text()),
            "comment": clean_field(self.comment_edit.text()),
            "limit":   clean_field(self.limit_edit.text()),
            "max":     clean_field(self.max_edit.text()),
        }
