from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from ..db import session_scope
from ..services import commercial, reports
from .widgets import DataTable, guarded


class FinanceTab(QWidget):
    """Income summary + sponsors."""

    def __init__(self, user):
        super().__init__()
        self.user = user
        self.start, self.end = QDateEdit(QDate(date.today().year, 1, 1)), QDateEdit(QDate.currentDate())
        for d in (self.start, self.end):
            d.setCalendarPopup(True)
        go = QPushButton("Refresh")
        go.clicked.connect(self.refresh)
        sp1, sp2 = QPushButton("Add sponsor…"), QPushButton("Record sponsorship received…")
        sp1.clicked.connect(self._sponsor)
        sp2.clicked.connect(self._payment)
        self.table = DataTable()
        top = QHBoxLayout()
        for w in (QLabel("From"), self.start, QLabel("To"), self.end, go, sp1, sp2):
            top.addWidget(w)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.table)
        self.refresh()

    def refresh(self):
        def work():
            with session_scope() as s:
                rep = reports.income_summary(s, self.start.date().toPython(), self.end.date().toPython())
            self.table.load(rep.headers, rep.rows)
        guarded(self, work)

    def _sponsor(self):
        name, ok = QInputDialog.getText(self, "Sponsor", "Sponsor name:")
        if ok:
            contact, _ = QInputDialog.getText(self, "Sponsor", "Contact person (optional):")

            def work():
                with session_scope() as s:
                    commercial.add_sponsor(s, name, contact)
            guarded(self, work, "Sponsor added.")

    def _payment(self):
        with session_scope() as s:
            sps = commercial.list_sponsors(s)
        if not sps:
            QMessageBox.information(self, "No sponsors", "Add a sponsor first.")
            return
        who, ok = QInputDialog.getItem(self, "Sponsorship", "Sponsor:", [x.name for x in sps], 0, False)
        if not ok:
            return
        amt, ok = QInputDialog.getDouble(self, "Sponsorship", "Amount received (Ksh):", 10000, 1, 1e9, 2)
        if not ok:
            return
        purpose, _ = QInputDialog.getText(self, "Sponsorship", "Purpose (e.g. season kit):")

        def work():
            with session_scope() as s:
                commercial.record_sponsorship(s, next(x.id for x in sps if x.name == who), amt, purpose=purpose,
                                              user_id=self.user.id)
        if guarded(self, work, "Sponsorship recorded as income."):
            self.refresh()


class ReportsTab(QWidget):
    def __init__(self, user):
        super().__init__()
        self.pick = QComboBox()
        self.pick.addItems(list(reports.REGISTRY))
        self.start, self.end = QDateEdit(QDate(date.today().year, 1, 1)), QDateEdit(QDate.currentDate())
        for d in (self.start, self.end):
            d.setCalendarPopup(True)
        run, csv_, xl = QPushButton("Run"), QPushButton("Export CSV"), QPushButton("Export Excel")
        run.clicked.connect(self.run)
        csv_.clicked.connect(lambda: self.export("csv"))
        xl.clicked.connect(lambda: self.export("xlsx"))
        self.table, self.report = DataTable(), None
        top = QHBoxLayout()
        for w in (self.pick, QLabel("From"), self.start, QLabel("To"), self.end, run, csv_, xl):
            top.addWidget(w)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.table)

    def refresh(self):
        pass

    def run(self):
        def work():
            with session_scope() as s:
                self.report = reports.REGISTRY[self.pick.currentText()](s, self.start.date().toPython(),
                                                                       self.end.date().toPython())
            self.table.load(self.report.headers, self.report.rows)
        guarded(self, work)

    def export(self, kind: str):
        if self.report is None:
            self.run()
        if self.report is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export", f"{self.report.title}.{kind}", f"*.{kind}")
        if path:
            guarded(self, lambda: (reports.export_csv if kind == "csv" else reports.export_xlsx)(self.report, path),
                    f"Saved {path}")
