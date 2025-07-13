"""
Lease-Review panel (wizard step 1½)
──────────────────────────────────
Shows the current DHCP lease, any conflicting static queue,
and lets the user choose queue action + enable-lease option.

Emits: accepted(queue_action:str, enable_lease:bool) or cancelled()
"""

from __future__ import annotations
import html
from typing import Optional

from PyQt6.QtCore    import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QRadioButton,
    QHBoxLayout, QCheckBox, QPushButton, QTextEdit, QMessageBox
)

from utils.universal_parser import parse_detail_blocks
from core.client            import MikrotikClient


# ───────────────────────── helper HTML builders
def _kv(key: str, val: str, *, rich: bool = False) -> str:
    """
    Grey key + value.  If rich=True we trust caller (no escaping),
    otherwise we escape the value.
    """
    val_html = val if rich else html.escape(val or "—")
    return f'<span style="color:#888;">{key}: </span><code>{val_html}</code>'


def _yes_no(flag: bool) -> str:
    return "Yes" if flag else "No"


# ────────────────────────────── main widget
class LeaseReviewPanel(QWidget):
    accepted  = pyqtSignal(str, bool)   # queue_action, enable_lease
    cancelled = pyqtSignal()

    # ─────────────────────────────────────────────────────────── init
    def __init__(
        self,
        lease: dict,
        *,
        creds: dict,
        new_mac: str,
        default_limit_at: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.creds            = creds
        self.lease            = lease
        self.new_mac          = new_mac
        self.default_limit_at = default_limit_at

        self._conflict = self._find_conflict()
        self._build_ui()
        self._refresh_preview()

    # ─────────────────────────────────────────────────────────── UI
    def _build_ui(self) -> None:
        v = QVBoxLayout(self)

        # ── CURRENT LEASE ────────────────────────────────────────
        flags         = self.lease.get("_flags", "")
        coloured_flag = flags.replace("X", '<span style="color:red;"><b>X</b></span>')
        is_disabled   = "X" in flags

        cur_box = QGroupBox("Current DHCP Lease"); v.addWidget(cur_box)
        cv = QVBoxLayout(cur_box)
        cur_html = "<div style='line-height:150%'>" + "<br>".join([
            _kv("Flags", coloured_flag or "—", rich=True),
            _kv("Address", self.lease.get("address", "")),
            _kv("Host-Name", self.lease.get("host-name", "")),
            _kv("Rate-Limit", self.lease.get("rate-limit", "").strip('"')),
            _kv("Comment", self.lease.get("comment", "")),
            _kv("MAC",
                f'{self.lease.get("mac-address","")} '
                f'→ <b>{self.new_mac}</b>',
                rich=True),
            _kv("Disabled", _yes_no(is_disabled)),
        ]) + "</div>"
        lbl_cur = QLabel(cur_html); lbl_cur.setTextFormat(Qt.TextFormat.RichText)
        cv.addWidget(lbl_cur)

        # ── CONFLICTING QUEUE ────────────────────────────────────
        if self._conflict:
            q_box = QGroupBox("Existing Static Queue (conflict)")
            q_box.setStyleSheet("QGroupBox::title{color:#d28500;}")  # orange
            v.addWidget(q_box)
            qv = QVBoxLayout(q_box)
            q_html = "<div style='line-height:150%'>" + "<br>".join([
                _kv("Name"     , self._conflict.get("name", "")),
                _kv("Target"   , self._conflict.get("target", "")),
                _kv("Max-Limit", self._conflict.get("max-limit", "")),
                _kv("Limit-At" , self._conflict.get("limit-at", "")),
                _kv("Comment"  , self._conflict.get("comment", "")),
            ]) + "</div>"
            lbl_conf = QLabel(q_html); lbl_conf.setTextFormat(Qt.TextFormat.RichText)
            qv.addWidget(lbl_conf)

        # ── ACTION RADIOs ───────────────────────────────────────
        action_box = QGroupBox("Queue Action"); v.addWidget(action_box)
        av = QVBoxLayout(action_box)
        self.rb_overwrite   = QRadioButton("Overwrite / add static queue")
        self.rb_remove_rate = QRadioButton("Remove DHCP rate-limit only")
        self.rb_none        = QRadioButton("No queue action")
        self.rb_overwrite.setChecked(True)
        for rb in (self.rb_overwrite, self.rb_remove_rate, self.rb_none):
            rb.toggled.connect(self._refresh_preview)
            av.addWidget(rb)

        # ── ENABLE CHECKBOX ─────────────────────────────────────
        self.cb_enable = QCheckBox("Enable this DHCP lease")
        self.cb_enable.setChecked(is_disabled)          # default tick
        self.cb_enable.stateChanged.connect(self._refresh_preview)
        v.addWidget(self.cb_enable)

        # ── PREVIEW ─────────────────────────────────────────────
        prev_box = QGroupBox("Proposed Changes"); v.addWidget(prev_box)
        pv = QVBoxLayout(prev_box)
        self.preview = QTextEdit(readOnly=True); self.preview.setMaximumHeight(160)
        pv.addWidget(self.preview)

        # ── BUTTONS ─────────────────────────────────────────────
        btns = QHBoxLayout(); v.addLayout(btns)
        back = QPushButton("← Back"); back.clicked.connect(self.cancelled.emit)
        run  = QPushButton("Run");    run.clicked.connect(self._on_run)
        btns.addWidget(back); btns.addStretch(1); btns.addWidget(run)

    # ────────────────────────────────────────── preview logic
    def _refresh_preview(self) -> None:
        bullets: list[str] = []

        # MAC change always
        bullets.append(f"MAC → <code>{html.escape(self.new_mac)}</code>")

        # lease enable / disable
        if self.cb_enable.isChecked():
            bullets.append("Enable this DHCP lease")

        # queue branch
        if self.rb_overwrite.isChecked():
            lease_rate = self.lease.get("rate-limit", "").strip('"') or "0/0"
            comment    = (self._conflict or {}).get("comment") or self.lease.get("comment", "")
            queue_lines = [
                f"Target: <code>{self.lease['address']}</code>",
                f"Max-Limit: <code>{lease_rate}</code>",
                f"Limit-At: <code>{self.default_limit_at}</code>",
                f"Comment: <code>{html.escape(comment or '—')}</code>",
            ]
            bullets.append("Static queue")
            # indent sub-list
            bullets.extend(f"&emsp;• {ln}" for ln in queue_lines)

        elif self.rb_remove_rate.isChecked():
            bullets.append("Clear DHCP lease rate-limit")

        # compose HTML
        html_ul = "<ul style='margin-left:-18px;'>" + \
                  "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"
        self.preview.setHtml(html_ul)

    # ────────────────────────────────────────── find conflict
    def _find_conflict(self) -> Optional[dict]:
        try:
            with MikrotikClient(
                self.creds["host"], self.creds["user"],
                self.creds["password"], self.creds["port"]
            ) as cli:
                raw = cli.cmd("/queue simple print detail without-paging")
        except Exception as err:
            QMessageBox.warning(self, "Warning",
                                f"Could not fetch queue list:\n{err}")
            return None
        ip = self.lease.get("address", "")
        return next(
            (r for r in parse_detail_blocks(raw.splitlines(), "/queue simple")
             if r.get("target", "").split("/")[0] == ip),
            None
        )

    # ────────────────────────────────────────── Run clicked
    def _on_run(self) -> None:
        action = (
            "overwrite"   if self.rb_overwrite.isChecked()   else
            "remove_rate" if self.rb_remove_rate.isChecked() else
            "no_action"
        )
        self.accepted.emit(action, self.cb_enable.isChecked())
