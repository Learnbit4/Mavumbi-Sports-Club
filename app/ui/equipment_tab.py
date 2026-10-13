from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QLabel, QPushButton, QVBoxLayout, QWidget
from sqlalchemy import select

from ..db import session_scope
from ..models import Equipment, EquipmentIssue, EquipmentIssueLine, Event, Person, Sport, Surcharge
from ..services import equipment
from .widgets import DataTable, guarded, need_selection


class EquipmentTab(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.eq_table, self.issue_table, self.sur_table = DataTable(), DataTable(), DataTable()
        row = QHBoxLayout()
        for label, fn in (("Add equipment…", self._add), ("Issue to event captain…", self._issue),
                          ("Return selected issue…", self._return), ("Mark surcharge paid", self._pay)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay = QVBoxLayout(self)
        for title, tbl in (("Club equipment", self.eq_table), ("Equipment issues (out = not yet returned)", self.issue_table),
                           ("Outstanding surcharges", self.sur_table)):
            lay.addWidget(QLabel(title))
            lay.addWidget(tbl)
        lay.addLayout(row)
        self.refresh()

    def refresh(self):
        def work():
            with session_scope() as s:
                eq = [[e.id, e.name, n, e.market_value, e.qty_available, e.qty_total]
                      for e, n in s.execute(select(Equipment, Sport.name).join(Sport, Sport.id == Equipment.sport_id)
                                            .order_by(Sport.name, Equipment.name))]
                iss = [[i.id, ev, p, "returned" if i.returned_at else "OUT",
                        ", ".join(f"{ln.equipment.name} x{ln.qty_out}" for ln in i.lines)]
                       for i, ev, p in s.execute(select(EquipmentIssue, Event.title, Person.full_name)
                                                 .join(Event, Event.id == EquipmentIssue.event_id)
                                                 .join(Person, Person.id == EquipmentIssue.captain_id)
                                                 .order_by(EquipmentIssue.id.desc()))]
                sur = [[x.id, n, amt] for x, n, amt in
                       ((x, n, x.amount) for x, n in s.execute(select(Surcharge, Person.full_name)
                        .join(Person, Person.id == Surcharge.member_id).where(Surcharge.paid_on.is_(None))))]
            self.eq_table.load(["ID", "Item", "Game", "Market value", "Available", "Total"], eq)
            self.issue_table.load(["ID", "Event", "Captain", "Status", "Items"], iss)
            self.sur_table.load(["ID", "Member", "Amount"], sur)
        guarded(self, work)

    def _add(self):
        with session_scope() as s:
            sports = list(s.scalars(select(Sport).order_by(Sport.name)))
        sp, ok = QInputDialog.getItem(self, "Add equipment", "Game:", [x.name for x in sports], 0, False)
        if not ok:
            return
        name, ok = QInputDialog.getText(self, "Add equipment", "Name:")
        if not ok:
            return
        val, ok = QInputDialog.getDouble(self, "Add equipment", "Market value (Ksh):", 1000, 1, 10_000_000, 2)
        if not ok:
            return
        qty, ok = QInputDialog.getInt(self, "Add equipment", "Quantity:", 5, 1, 100000)
        if ok:
            def work():
                with session_scope() as s:
                    equipment.add_equipment(s, name, next(x.id for x in sports if x.name == sp), val, qty)
            if guarded(self, work):
                self.refresh()

    def _issue(self):
        eid = self.eq_table.selected_id()
        if not need_selection(self, eid, "equipment row"):
            return
        with session_scope() as s:
            evs = s.execute(select(Event.id, Event.title, Event.event_date).order_by(Event.event_date.desc())).all()
        if not evs:
            return
        pick, ok = QInputDialog.getItem(self, "Issue", "Event:", [f"{t} {d} (#{i})" for i, t, d in evs], 0, False)
        if not ok:
            return
        event_id = int(pick.rsplit("#", 1)[1].rstrip(")"))
        qty, ok = QInputDialog.getInt(self, "Issue", "Quantity:", 1, 1, 100000)
        if ok:
            def work():
                from ..models import EventRoster
                with session_scope() as s:
                    cap = s.scalar(select(EventRoster.member_id).where(EventRoster.event_id == event_id,
                                                                      EventRoster.is_captain.is_(True)))
                    if cap is None:
                        from ..errors import ValidationError
                        raise ValidationError("Select the event's team and captain first")
                    equipment.issue(s, event_id, cap, [(eid, qty)], self.user.id)
            if guarded(self, work, "Equipment issued to the event captain."):
                self.refresh()

    def _return(self):
        iid = self.issue_table.selected_id()
        if not need_selection(self, iid, "issue"):
            return
        with session_scope() as s:
            lines = [(ln.id, ln.equipment.name, ln.qty_out) for ln in s.get(EquipmentIssue, iid).lines]
        losses = {}
        for lid, name, out in lines:
            lost, ok = QInputDialog.getInt(self, "Return", f"{name}: how many LOST (of {out})?", 0, 0, out)
            if not ok:
                return
            dmg, ok = QInputDialog.getInt(self, "Return", f"{name}: how many DAMAGED (of {out - lost})?", 0, 0, out - lost)
            if not ok:
                return
            losses[lid] = (lost, dmg)

        def work():
            with session_scope() as s:
                equipment.return_issue(s, iid, losses, self.user.id)
        if guarded(self, work, "Return recorded. Any surcharge is split across the team and listed below."):
            self.refresh()

    def _pay(self):
        sid = self.sur_table.selected_id()
        if not need_selection(self, sid, "surcharge"):
            return

        def work():
            with session_scope() as s:
                equipment.pay_surcharge(s, sid, user_id=self.user.id)
        if guarded(self, work, "Payment recorded as income."):
            self.refresh()
