# widgets/wizards_side_panel.py
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QSizePolicy
)


class WizardsSidePanel(QWidget):
    """
    A vertical button bar for selecting which wizard to show.
    Emits wizardSelected(str key).
    """
    wizardSelected = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        # Register buttons here ↓  key -> text
        self._buttons: dict[str, QPushButton] = {}

        def add_btn(key: str, text: str):
            btn = QPushButton(text)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda: self.wizardSelected.emit(key))
            layout.addWidget(btn)
            self._buttons[key] = btn

        add_btn("new_mac", "Assign New MAC")
        # future wizards: add_btn("something", "Fancy Wizard")

        layout.addStretch(1)
