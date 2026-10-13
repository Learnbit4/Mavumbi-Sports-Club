from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget

from ..services import auth
from .equipment_tab import EquipmentTab
from .events_tab import EventsTab
from .football_tab import FootballTab
from .finance_tab import FinanceTab, ReportsTab
from .members_tab import MembersTab
from .store_tab import StoreTab

TABS = (("members", "Members", MembersTab), ("store", "Store & merchandise", StoreTab),
        ("events", "Events & fees", EventsTab), ("equipment", "Equipment", EquipmentTab),
        ("football", "Football ops", FootballTab),
        ("finance", "Finance", FinanceTab), ("reports", "Reports", ReportsTab))


class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.setWindowTitle("Mavumbi Sports Club")
        self.resize(1250, 780)
        self.tabs = QTabWidget()
        for perm, label, cls in TABS:
            if auth.can(user.role, perm):
                self.tabs.addTab(cls(user), label)
        self.tabs.currentChanged.connect(lambda _i: getattr(self.tabs.currentWidget(), "refresh", lambda: None)())
        self.setCentralWidget(self.tabs)
        self.statusBar().addPermanentWidget(QLabel(f"Signed in: {user.username} ({user.role})"))
