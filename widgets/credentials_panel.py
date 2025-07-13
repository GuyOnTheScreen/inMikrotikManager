# widgets/credentials_panel.py

from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox
)

from utils.profiles import load_all_profiles


class CredentialsPanel(QWidget):
    """
    Host / user / pass fields + inline profile selector.

    •  Selecting a profile fills USER, PASSWORD (and port=22) only.
    •  It never alters the Host / IP field.
    """
    # ────────────────────────────────────────────────────────────── init
    def __init__(self, defaults: dict | None = None, parent=None):
        super().__init__(parent)

        # entry fields
        self.le_host = QLineEdit();  self.le_host.setPlaceholderText("Host / IP")
        self.le_user = QLineEdit();  self.le_user.setPlaceholderText("Username")
        self.le_pass = QLineEdit();  self.le_pass.setPlaceholderText("Password")
        self.le_pass.setEchoMode(QLineEdit.EchoMode.Password)

        # profile drop-down
        self.cmb_profiles = QComboBox()
        self._profiles: dict[str, dict] = load_all_profiles()
        self.cmb_profiles.addItem("— choose profile —")
        self.cmb_profiles.addItems(sorted(self._profiles))
        self.cmb_profiles.currentTextChanged.connect(self._profile_selected)

        # layout
        frm = QFormLayout(self)
        frm.addRow("Host",    self.le_host)
        frm.addRow("User",    self.le_user)
        frm.addRow("Pass",    self.le_pass)
        frm.addRow("Profile", self.cmb_profiles)

        if defaults:
            self.set_credentials(defaults)

    # ────────────────────────────────────────────────────────────── public
    def current_credentials(self) -> dict:
        return {
            "host": self.le_host.text().strip(),
            "user": self.le_user.text().strip(),
            "password": self.le_pass.text(),
            "port": 22,
        }

    def set_credentials(self, d: dict):
        """Populate USER / PASS (never HOST)."""
        self.le_user.setText(d.get("user", ""))
        self.le_pass.setText(d.get("password", ""))

    def clear_host(self):
        self.le_host.clear()

    # ────────────────────────────────────────────────────────────── private
    def _profile_selected(self, name: str):
        if name in self._profiles:
            self.set_credentials(self._profiles[name])
