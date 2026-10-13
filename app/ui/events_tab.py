from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)
from sqlalchemy import select

from .. import rules
from ..db import session_scope
from ..models import Event, EventRoster, Member, Person, Sport
from ..services import equipment, events, membership
from .widgets import DataTable, guarded, need_selection


class RosterDialog(QDialog):
    """Tick the team. The highlighted (current) row becomes captain."""

    def __init__(self, parent, people: list[tuple[int, str]]):
        super().__init__(parent)
        self.setWindowTitle("Select team")
        self.list = QListWidget()
        for pid, name in people:
            it = QListWidgetItem(f"{name} (#{pid})")
            it.setData(Qt.ItemDataRole.UserRole, pid)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(it)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Tick team members. Click a ticked name to mark the CAPTAIN."))
        lay.addWidget(self.list)
        lay.addWidget(box)

    def result_ids(self):
        ids = [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
               if self.list.item(i).checkState() == Qt.CheckState.Checked]
        cur = self.list.currentItem()
        cap = cur.data(Qt.ItemDataRole.UserRole) if cur else None
        return ids, cap


class EventsTab(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.sport, self.title, self.venue, self.opp = QComboBox(), QLineEdit(), QLineEdit(), QLineEdit()
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.price = QDoubleSpinBox()
        self.price.setRange(0, 100000)
        self.opp.setPlaceholderText("Leave blank for an internal event")
        form = QFormLayout()
        for label, w in (("Game", self.sport), ("Title", self.title), ("Date", self.date), ("Venue", self.venue),
                         ("Opponent (external)", self.opp), ("Ticket price", self.price)):
            form.addRow(label, w)
        create = QPushButton("Create event")
        create.clicked.connect(self._create)
        self.events_table, self.roster_table = DataTable(), DataTable()
        self.events_table.itemSelectionChanged.connect(self._show_roster)
        btns = []
        for label, fn in (("Select team…", self._team), ("Collect fee from selected player", self._collect),
                          ("Settle (post patron commission)", self._settle), ("Sell tickets…", self._tickets),
                          ("Assign patron to game…", self._patron)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            btns.append(b)
        self.summary = QLabel("")
        left = QVBoxLayout()
        left.addLayout(form)
        left.addWidget(create)
        left.addStretch()
        left.addWidget(self.summary)
        mid = QVBoxLayout()
        mid.addWidget(QLabel("Events"))
        mid.addWidget(self.events_table)
        mid.addWidget(QLabel("Team for selected event"))
        mid.addWidget(self.roster_table)
        row = QHBoxLayout()
        for b in btns:
            row.addWidget(b)
        mid.addLayout(row)
        main = QHBoxLayout(self)
        main.addLayout(left, 0)
        main.addLayout(mid, 1)
        self.refresh()

    def refresh(self):
        def work():
            with session_scope() as s:
                sports = membership.list_sports(s)
                rows = s.execute(select(Event, Sport.name).join(Sport, Sport.id == Event.sport_id)
                                 .order_by(Event.event_date.desc())).all()
                data = [[e.id, e.event_date, n, e.title, e.opponent or "internal", e.ticket_price,
                         "yes" if e.commission_posted else ""] for e, n in rows]
            self.sport.clear()
            for sp in sports:
                self.sport.addItem(sp.name, sp.id)
            self.events_table.load(["ID", "Date", "Game", "Title", "Opponent", "Ticket", "Settled"], data)
        guarded(self, work)

    def _eid(self):
        eid = self.events_table.selected_id()
        return eid if need_selection(self, eid, "event") else None

    def _show_roster(self):
        eid = self.events_table.selected_id()
        if eid is None:
            return

        def work():
            with session_scope() as s:
                rows = s.execute(select(EventRoster, Person.full_name).join(Person, Person.id == EventRoster.member_id)
                                 .where(EventRoster.event_id == eid)
                                 .order_by(EventRoster.is_captain.desc(), Person.full_name)).all()
                data = [[r.member_id, n, "Captain" if r.is_captain else "", r.fee_amount, r.fee_paid_on or "unpaid"]
                        for r, n in rows]
                f = events.event_financials(s, eid)
            self.roster_table.load(["Member", "Name", "Role", "Fee", "Paid"], data)
            self.summary.setText(f"Facilitation due {f['facilitation_due']:,.2f}\nCollected {f['facilitation_collected']:,.2f}\n"
                                 f"Patron commission {f['patron_commission']:,.2f}\nTickets {f['ticket_revenue']:,.2f}\n"
                                 f"Surcharges {f['surcharges_charged']:,.2f}")
        guarded(self, work)

    def _create(self):
        def work():
            with session_scope() as s:
                events.create_event(s, self.sport.currentData(), self.title.text(), self.date.date().toPython(),
                                    self.venue.text(), self.opp.text(), self.price.value())
        if guarded(self, work):
            self.title.clear()
            self.refresh()

    def _team(self):
        eid = self._eid()
        if eid is None:
            return
        with session_scope() as s:
            people = s.execute(select(Person.id, Person.full_name).join(Member, Member.person_id == Person.id)
                               .order_by(Person.full_name)).all()
        dlg = RosterDialog(self, [(p, n) for p, n in people])
        if dlg.exec():
            ids, cap = dlg.result_ids()

            def work():
                with session_scope() as s:
                    events.set_roster(s, eid, ids, cap)
            if guarded(self, work):
                self._show_roster()

    def _collect(self):
        eid, mid = self._eid(), self.roster_table.selected_id()
        if eid is None or not need_selection(self, mid, "player in the team list"):
            return

        def work():
            with session_scope() as s:
                events.collect_facilitation(s, eid, mid, user_id=self.user.id)
        if guarded(self, work):
            self._show_roster()

    def _settle(self):
        eid = self._eid()
        if eid is None:
            return

        def work():
            with session_scope() as s:
                events.settle_event(s, eid, self.user.id)
        if guarded(self, work, "Patron commission posted to the ledger."):
            self.refresh()
            self._show_roster()

    def _tickets(self):
        eid = self._eid()
        if eid is None:
            return
        qty, ok = QInputDialog.getInt(self, "Sell tickets", "Number of tickets:", 1, 1, 100000)
        if ok:
            def work():
                with session_scope() as s:
                    events.sell_tickets(s, eid, qty, user_id=self.user.id)
            if guarded(self, work, f"{qty} ticket(s) sold."):
                self._show_roster()

    def _patron(self):
        with session_scope() as s:
            sports = membership.list_sports(s)
            people = s.execute(select(Person.id, Person.full_name).order_by(Person.full_name)).all()
        sp, ok = QInputDialog.getItem(self, "Patron", "Game:", [x.name for x in sports], 0, False)
        if not ok:
            return
        who, ok = QInputDialog.getItem(self, "Patron", "Person:", [f"{n} (#{p})" for p, n in people], 0, False)
        if ok:
            pid = int(who.rsplit("#", 1)[1].rstrip(")"))
            sid = next(x.id for x in sports if x.name == sp)

            def work():
                with session_scope() as s:
                    membership.assign_role(s, pid, "Patron", sid)
            guarded(self, work, "Patron assigned.")
