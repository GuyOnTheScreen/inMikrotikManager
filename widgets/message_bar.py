from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QHBoxLayout,
    QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal


class MessageBar(QWidget):
    """
    A slim, dismiss-able banner for inline messages.

    Signals
    -------
    accepted() – primary button clicked
    closed()   – banner dismissed (×)
    """
    accepted = pyqtSignal()
    closed   = pyqtSignal()

    # -------------------------------------------------------------------- init
    def __init__(
        self,
        text: str,
        primary: str = "OK",
        parent=None
    ):
        super().__init__(parent)
        self.setObjectName("MessageBar")
        self.setStyleSheet("""
            #MessageBar {
                background: #FFF7D7;
                border: 1px solid #E5C16C;
                border-radius: 3px;
            }
        """)

        lbl = QLabel(text, self)
        lbl.setWordWrap(True)

        btn_ok = QPushButton(primary, self)
        btn_ok.clicked.connect(self.accepted.emit)
        btn_ok.clicked.connect(self.close)

        btn_cls = QPushButton("×", self)
        btn_cls.setFixedWidth(22)
        btn_cls.clicked.connect(self.close)
        btn_cls.clicked.connect(self.closed.emit)

        lay = QHBoxLayout(self)
        lay.addWidget(lbl, 1)
        lay.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Policy.Expanding))
        lay.addWidget(btn_ok)
        lay.addWidget(btn_cls)
