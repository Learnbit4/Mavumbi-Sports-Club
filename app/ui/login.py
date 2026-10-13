from dataclasses import dataclass

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from ..db import session_scope
from ..services import auth
from .widgets import guarded


@dataclass
class CurrentUser:
    id: int
    username: str
    role: str


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mavumbi Sports Club: Sign in")
        self.user: CurrentUser | None = None
        self.name, self.pw = QLineEdit(), QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.msg = QLabel("")
        self.msg.setStyleSheet("color:#b00020")
        form = QFormLayout()
        form.addRow("Username", self.name)
        form.addRow("Password", self.pw)
        btn = QPushButton("Sign in")
        btn.setDefault(True)
        btn.clicked.connect(self._go)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.msg)
        lay.addWidget(btn)
        self.setMinimumWidth(320)

    def _go(self):
        def work():
            with session_scope() as s:
                u = auth.authenticate(s, self.name.text().strip(), self.pw.text())
                self.user = CurrentUser(u.id, u.username, u.role) if u else None
        if guarded(self, work):
            if self.user:
                self.accept()
            else:
                self.msg.setText("Wrong username or password")
                self.pw.clear()
