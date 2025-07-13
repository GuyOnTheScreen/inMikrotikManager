# ui/pages/wizards.py
"""
Wizard selection page that lists available wizards and displays
the selected one in a stacked view.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
)
from PyQt6.QtCore import Qt

# Import the actual class name from the New-MAC wizard
from ui.wizards.new_mac.new_mac_start import NewMacStartPage


class WizardsPage(QWidget):
    """
    Page that lets the user pick from multiple wizards (e.g., New-MAC)
    and shows the corresponding wizard page.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # ─── Layout ───────────────────────────────────────────────────────
        main_layout = QHBoxLayout(self)
        self.setLayout(main_layout)

        # Left: list of wizard names
        self.list = QListWidget()
        main_layout.addWidget(self.list)

        # Right: stacked widgets for each wizard
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, stretch=1)

        # ─── Add your wizards here ───────────────────────────────────────
        # 1) New-MAC wizard
        new_mac_item = QListWidgetItem("New-MAC Wizard")
        self.list.addItem(new_mac_item)
        self.stack.addWidget(NewMacStartPage())

        # (Add additional wizards here as needed…)

        # ─── Signals ──────────────────────────────────────────────────────
        # Switch the stacked widget when the user selects a different list item
        self.list.currentRowChanged.connect(self.stack.setCurrentIndex)

        # Default to the first wizard
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    # ────────────────────────────────────────────────────────────── SSH link
    def set_ssh_client(self, client) -> None:
        """
        Called by main.py after a successful login so every page can share the
        same MikrotikClient instance.  We store it and pass it to whichever
        wizard page is currently visible (if that page implements
        set_ssh_client).
        """
        self._ssh_client = client
        current = self.stack.currentWidget()
        if hasattr(current, "set_ssh_client"):
            current.set_ssh_client(client)