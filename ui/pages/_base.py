# ui/pages/_base.py
from __future__ import annotations

from typing import List, Callable, Sequence, Optional
from PyQt6.QtCore    import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton,
    QSizePolicy, QTableWidget, QHeaderView, QMessageBox
)

from core.taskrunner import CommandRunner       # already threaded
from core.client     import MikrotikClient


# ──────────────────────────────────────────────────────────────────────────
class BasePage(QWidget):
    """
    • Adds a vertical *sidebar* with buttons you pass in.
    • Keeps a single long-running CommandRunner.
    • Provides .set_ssh_client() + thread cleanup.
    """

    def __init__(
        self,
        buttons: Sequence[tuple[str, Callable[[], None]]],
        content: QWidget,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        # ---- build sidebar ------------------------------------------------
        sidebar = QVBoxLayout()
        for text, slot in buttons:
            b = QPushButton(text, self)
            b.clicked.connect(slot)
            b.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed)
            sidebar.addWidget(b)
        sidebar.addStretch(1)

        # optional separator
        vline = QFrame()
        vline.setFrameShape(QFrame.Shape.VLine)
        vline.setFrameShadow(QFrame.Shadow.Sunken)

        # ---- final layout --------------------------------------------------
        root = QHBoxLayout(self)
        root.addLayout(sidebar)
        root.addWidget(vline)
        root.addWidget(content, 1)        # stretch = 1  → takes the rest

        # -------------------------------------------------------------------
        self._client : MikrotikClient | None = None
        self._runner : CommandRunner   | None = None

    # ---------------------------------------------------------------- I/O --
    def set_ssh_client(self, cli: MikrotikClient | None):
        self._client = cli

    # ---------------------------------------------------------------- util -
    def _runner_active(self) -> bool:
        return self._runner is not None and self._runner.isRunning()

    def _start_runner(self, cmd: str, finished_slot):
        if not self._client:
            QMessageBox.warning(self, "No connection", "Connect first.")
            return
        if self._runner_active():
            QMessageBox.information(self, "Busy", "Still working…")
            return
        self._runner = CommandRunner(self._client, cmd, parent=self)
        self._runner.finished.connect(finished_slot)
        self._runner.finished.connect(self._runner.deleteLater)
        self._runner.start()

    # ---------------------------------------------------------------- clean-up
    def closeEvent(self, ev):
        if self._runner_active():
            self._runner.quit()
            self._runner.wait()
        super().closeEvent(ev)



# ──────────────────────────────────────────────────────────────────────────
class TableMixin:
    """
    Drop-in helper for pages that display a QTableWidget and need
    the “fit comment column” behaviour.
    """

    @staticmethod
    def fit_comment_column(tbl: QTableWidget, col: int, max_px: int = 400):
        hdr = tbl.horizontalHeader()
        tbl.resizeColumnsToContents()
        if tbl.columnWidth(col) > max_px:
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            tbl.setColumnWidth(col, max_px)
            tbl.setWordWrap(True)
        else:
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        tbl.resizeRowsToContents()
