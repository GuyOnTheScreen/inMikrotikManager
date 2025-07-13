# main.py
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget

from ui.pages.landing        import LandingPage
from ui.pages.queue_management import QueuePage
from ui.pages.ip_routing     import RoutingPage
from ui.pages.arp_table      import ArpTablePage
from ui.pages.speed_test     import SpeedTestPage
from ui.pages.action_history import ActionHistoryPage
from ui.pages.wizards        import WizardsPage

class MainTestWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("InNocTools – MikroTik Manager")
        self.resize(1500, 1000)

        # ---------------------------------------------------------------- tabs
        tabs = QTabWidget(self)

        self.landing  = LandingPage()
        self.queues   = QueuePage()
        self.routes   = RoutingPage()
        self.arp      = ArpTablePage()
        self.wizards  = WizardsPage()
        self.speed    = SpeedTestPage()
        self.history  = ActionHistoryPage()

        tabs.addTab(self.landing,  "Connect")
        tabs.addTab(self.queues,   "Queues")
        tabs.addTab(self.routes,   "Routes")
        tabs.addTab(self.arp,      "ARP")
        tabs.addTab(self.wizards,  "Wizards")
        tabs.addTab(self.speed,    "Speed Test")
        tabs.addTab(self.history,  "History")

        self.setCentralWidget(tabs)

        # ---------------------------------------------------------------- link / unlink
        self.landing.connect_btn.clicked  .connect(self._link_ssh)
        self.landing.disconnect_btn.clicked.connect(self._unlink_ssh)

    # .........................................................................
    def _link_ssh(self) -> None:
        client = self.landing.ssh_client
        for page in (self.queues, self.routes, self.arp,
                     self.wizards, self.speed, self.history):
            page.set_ssh_client(client)

    def _unlink_ssh(self) -> None:
        for page in (self.queues, self.routes, self.arp,
                     self.wizards, self.speed, self.history):
            page.set_ssh_client(None)

# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)
    win = MainTestWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
