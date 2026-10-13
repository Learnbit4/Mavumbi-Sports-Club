from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)

from .. import rules
from ..db import session_scope
from ..services import membership, reports
from .widgets import DataTable, guarded


class MembersTab(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.name, self.phone, self.nok, self.nok_phone = QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit()
        self.sub_county, self.institution, self.needs = QLineEdit(), QLineEdit(), QLineEdit()
        self.gender = QComboBox()
        self.gender.addItems(membership.GENDERS)
        self.dob = QDateEdit(QDate(2008, 1, 1))
        self.dob.setCalendarPopup(True)
        self.weight, self.height = QDoubleSpinBox(), QDoubleSpinBox()
        self.weight.setRange(0, 200)
        self.height.setRange(0, 250)
        self.games = [QComboBox() for _ in range(3)]
        self.group = QComboBox()
        form = QFormLayout()
        for label, w in (("Full name", self.name), ("Gender", self.gender), ("Date of birth", self.dob),
                         ("Phone", self.phone), ("Next of kin", self.nok), ("Next of kin phone", self.nok_phone),
                         ("Sub-county", self.sub_county), ("School / college / church", self.institution),
                         ("Weight (kg)", self.weight), ("Height (cm)", self.height), ("Special needs", self.needs),
                         ("1st game (required)", self.games[0]), ("2nd game", self.games[1]),
                         ("3rd game", self.games[2]), ("Group (Ksh 500 each)", self.group)):
            form.addRow(label, w)
        reg = QPushButton("Register member")
        reg.clicked.connect(self._register)
        newg = QPushButton("New group…")
        newg.clicked.connect(self._new_group)
        box = QGroupBox("Enrol a member")
        lay = QVBoxLayout(box)
        lay.addLayout(form)
        row = QHBoxLayout()
        row.addWidget(reg)
        row.addWidget(newg)
        lay.addLayout(row)
        self.fee_hint = QLabel("Individual: Ksh 1,000. Group member: Ksh 500. Ages 12-35 only.")
        self.fee_hint.setWordWrap(True)
        lay.addWidget(self.fee_hint)
        self.table = DataTable()
        self.filter = QComboBox()
        self.filter.addItems(["All categories", "Minor", "Middle", "Senior", "Over-age"])
        self.filter.currentIndexChanged.connect(self.refresh)
        right = QVBoxLayout()
        right.addWidget(self.filter)
        right.addWidget(self.table)
        main = QHBoxLayout(self)
        main.addWidget(box, 0)
        main.addLayout(right, 1)
        self.refresh()

    def refresh(self):
        def work():
            with session_scope() as s:
                sports = membership.list_sports(s)
                groups = membership.list_groups(s)
                rep = reports.members_list(s)
            cur = [g.currentData() for g in self.games], self.group.currentData()
            for i, g in enumerate(self.games):
                g.clear()
                if i:
                    g.addItem("—", None)
                for sp in sports:
                    g.addItem(sp.name, sp.name)
            self.group.clear()
            self.group.addItem("Individual (Ksh 1,000)", None)
            for gr in groups:
                self.group.addItem(gr.name, gr.id)
            want = self.filter.currentText()
            rows = [r for r in rep.rows if want.startswith("All") or r[4] == want]
            self.table.load(rep.headers, rows)
        guarded(self, work)

    def _new_group(self):
        name, ok = QInputDialog.getText(self, "New group", "Group name (school, college, church…):")
        if not ok or not name.strip():
            return
        kind, ok = QInputDialog.getItem(self, "New group", "Type:", list(membership.ORG_TYPES), 0, False)
        if ok:
            def work():
                with session_scope() as s:
                    membership.create_group(s, name, kind)
            if guarded(self, work):
                self.refresh()

    def _register(self):
        chosen = [g.currentData() for g in self.games if g.currentData()]

        def work():
            with session_scope() as s:
                membership.register_member(
                    s, full_name=self.name.text(), gender=self.gender.currentText(),
                    date_of_birth=self.dob.date().toPython(), phone=self.phone.text().strip(),
                    next_of_kin_name=self.nok.text(), next_of_kin_contact=self.nok_phone.text().strip(),
                    games=chosen, sub_county=self.sub_county.text(), institution=self.institution.text(),
                    weight_kg=self.weight.value() or None, height_cm=self.height.value() or None,
                    special_needs=self.needs.text(), group_id=self.group.currentData(), user_id=self.user.id)
        if guarded(self, work, "Member registered and fee posted to the ledger."):
            for w in (self.name, self.phone, self.nok, self.nok_phone, self.sub_county, self.institution, self.needs):
                w.clear()
            self.refresh()

