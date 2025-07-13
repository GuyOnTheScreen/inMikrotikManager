# ui/pages/landing.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QGroupBox
from utils.ssh import SSHClient
from PyQt6.QtCore import Qt

class LandingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.ssh_client = None
        
        layout = QVBoxLayout()

        group = QGroupBox("Quick Connect")
        form_layout = QHBoxLayout()

        # IP/Gateway input
        self.gateway_edit = QLineEdit()
        self.gateway_edit.setPlaceholderText("Gateway/IP (x.x.x.x)")

        # Username input
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Username")

        # Password input
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        # Connect button
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_ssh)

        # Disconnect button
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_ssh)
        self.disconnect_btn.setEnabled(False)

        form_layout.addWidget(QLabel("Gateway:"))
        form_layout.addWidget(self.gateway_edit)
        form_layout.addWidget(QLabel("Username:"))
        form_layout.addWidget(self.username_edit)
        form_layout.addWidget(QLabel("Password:"))
        form_layout.addWidget(self.password_edit)
        form_layout.addWidget(self.connect_btn)
        form_layout.addWidget(self.disconnect_btn)

        group.setLayout(form_layout)
        layout.addWidget(group)
        
        self.setLayout(layout)

    def connect_ssh(self):
        host = self.gateway_edit.text().strip()
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()

        if not host or not username or not password:
            self.gateway_edit.setPlaceholderText("Fill in all fields!")
            return

        self.ssh_client = SSHClient(host, username, password)
        
        try:
            self.ssh_client.connect()
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.gateway_edit.setStyleSheet("border: 2px solid green;")
        except Exception as e:
            self.gateway_edit.setText("")
            self.gateway_edit.setPlaceholderText(f"Connection Failed: {str(e)}")
            self.gateway_edit.setStyleSheet("border: 2px solid red;")

    def disconnect_ssh(self):
        if self.ssh_client:
            self.ssh_client.disconnect()
            self.ssh_client = None
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.gateway_edit.setStyleSheet("")
