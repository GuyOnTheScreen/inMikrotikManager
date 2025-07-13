# ui/wizards/new_mac/lease_summary_page.py
"""
Lease-Summary page  (wizard step 3)
───────────────────────────────────
 • Shows Operation-complete details (read-only)
 • Lets the operator choose a Radio-Type
 • Generates two copy-ready text blocks
      ↳ Reply  (Teams/Slack message back to installer)
      ↳ Information  (ticket / calendar notes – wrapped in ***)
"""

from __future__ import annotations
import re

from PyQt6.QtCore    import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QTextEdit, QPushButton, QRadioButton
)


# ─────────────────────────────────────────────────────────────────────────────
class LeaseSummaryPage(QWidget):
    finished = pyqtSignal()                      # “Finished” button

    # ---------------------------------------------------------------- init
    def __init__(self, summary_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._summary_raw = summary_text

        root = QVBoxLayout(self)

        # ── 1) Operation complete (always on top) ─────────────────────────
        op_box = QGroupBox("Operation Complete"); root.addWidget(op_box)
        op_lay = QVBoxLayout(op_box)
        op_lay.addWidget(QLabel("<b>✅  Operation complete</b>"))

        self.txt_summary = QTextEdit(readOnly=True, maximumHeight=110)
        self.txt_summary.setPlainText(summary_text)
        op_lay.addWidget(self.txt_summary)

        # ── 2) Radio-type selector ────────────────────────────────────────
        sel_box = QGroupBox("Radio Type"); root.addWidget(sel_box)
        sel_lay = QHBoxLayout(sel_box)
        self.rb_ubnt    = QRadioButton("UBNT");    sel_lay.addWidget(self.rb_ubnt)
        self.rb_tarana  = QRadioButton("Tarana");  sel_lay.addWidget(self.rb_tarana)
        self.rb_cambium = QRadioButton("Cambium"); sel_lay.addWidget(self.rb_cambium)
        self.rb_ubnt.setChecked(True)             # default
        for rb in (self.rb_ubnt, self.rb_tarana, self.rb_cambium):
            rb.toggled.connect(self._update_blocks)

        # ── 3) Reply block ────────────────────────────────────────────────
        self.reply_box  = QGroupBox("Reply (copy to installer)"); root.addWidget(self.reply_box)
        self.txt_reply  = QTextEdit(readOnly=True, maximumHeight=110)
        rb_lay          = QVBoxLayout(self.reply_box); rb_lay.addWidget(self.txt_reply)

        # ── 4) Information block ─────────────────────────────────────────
        self.info_box  = QGroupBox("Information (ticket / calendar)"); root.addWidget(self.info_box)
        self.txt_info  = QTextEdit(readOnly=True, maximumHeight=140)
        inf_lay        = QVBoxLayout(self.info_box); inf_lay.addWidget(self.txt_info)

        # ── 5) Done button ───────────────────────────────────────────────
        btn = QPushButton("Finished"); btn.clicked.connect(self.finished.emit)
        root.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)

        # Initial fill-in
        self._update_blocks()

    # ---------------------------------------------------------------- helper extractors
    @staticmethod
    def _grab(label: str, blob: str) -> str:
        """Return the value after 'Label :'  (case-insensitive)."""
        m = re.search(rf"{re.escape(label)}\s*:\s*(.+)", blob, re.I)
        return m.group(1).strip() if m else "—"

    # ---------------------------------------------------------------- (re)build blocks
    def _update_blocks(self) -> None:
        gw    = self._grab("Gateway", self._summary_raw)
        ip    = self._grab("IP", self._summary_raw)
        omac  = self._grab("Old MAC", self._summary_raw)
        nmac  = self._grab("New MAC", self._summary_raw)

        # Default placeholders – installer will overwrite AFTER paste
        placeholders = {
            "radio_ip"  : "RADIO_IP",
            "serial"    : "SERIAL_NUMBER",
            "access"    : "RADIO_HTTPS_URL",
        }

        # Which radio-type is chosen?
        if self.rb_tarana.isChecked():
            reply = (
                f"Radio Serial:  {placeholders['serial']}\n"
                f"WAN IP:        {ip}\n"
                f"New MAC:       {nmac}"
            )
            info = (
                f"***\n"
                f"Radio Serial:  {placeholders['serial']}\n"
                f"WAN IP:        {ip}\n"
                f"New MAC:       {nmac}\n"
                f"Old MAC:       {omac}\n"
                f"Note:\n\n***"
            )

        elif self.rb_cambium.isChecked():
            reply = (
                f"Radio Access:  {placeholders['access']}\n"
                f"WAN IP:        {ip}\n"
                f"New MAC:       {nmac}"
            )
            info = (
                f"***\n"
                f"Radio Access:  {placeholders['access']}\n"
                f"WAN IP:        {ip}\n"
                f"New MAC:       {nmac}\n"
                f"Old MAC:       {omac}\n"
                f"Note:\n\n***"
            )

        else:  # UBNT (default)
            reply = (
                f"Radio IP:      {placeholders['radio_ip']}\n"
                f"WAN IP:        {ip}\n"
                f"New MAC:       {nmac}"
            )
            info = (
                f"***\n"
                f"Radio IP:      {placeholders['radio_ip']}\n"
                f"WAN IP:        {ip}\n"
                f"New MAC:       {nmac}\n"
                f"Old MAC:       {omac}\n"
                f"Note:\n\n***"
            )

        self.txt_reply.setPlainText(reply)
        self.txt_info.setPlainText(info)
