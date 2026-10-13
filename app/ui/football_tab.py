from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget, QTabWidget,
                               QVBoxLayout, QWidget)
from sqlalchemy import select

from ..db import session_scope
from ..models import Event, EventRoster, MatchResult, Member, Person, Sport, Squad
from ..services import auth, football, reports
from .widgets import DataTable, fmt, guarded, need_selection


def _members(s):
    return s.execute(select(Person.id, Person.full_name).join(Member, Member.person_id == Person.id)
                     .order_by(Person.full_name)).all()


def _pick_member(parent, title, people):
    who, ok = QInputDialog.getItem(parent, title, "Player:", [f"{n} (#{p})" for p, n in people], 0, False)
    return int(who.rsplit("#", 1)[1].rstrip(")")) if ok else None


def _season_now() -> str:
    t = date.today()
    return f"{t.year}/{(t.year + 1) % 100:02d}" if t.month >= 7 else f"{t.year - 1}/{t.year % 100:02d}"


class SquadsPanel(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.sport, self.season, self.squad = QComboBox(), QLineEdit(_season_now()), QComboBox()
        self.squad.currentIndexChanged.connect(self._show)
        self.table = DataTable()
        make = QPushButton("Create squad")
        make.clicked.connect(self._create)
        add, rem = QPushButton("Add player…"), QPushButton("Remove selected")
        add.clicked.connect(self._add)
        rem.clicked.connect(self._remove)
        top = QHBoxLayout()
        for w in (QLabel("Game"), self.sport, QLabel("Season"), self.season, make, QLabel("Squad"), self.squad):
            top.addWidget(w)
        bot = QHBoxLayout()
        bot.addWidget(add)
        bot.addWidget(rem)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.table)
        lay.addLayout(bot)
        self.refresh()

    def refresh(self):
        def work():
            with session_scope() as s:
                sports = list(s.scalars(select(Sport).order_by(Sport.name)))
                squads = s.execute(select(Squad, Sport.name).join(Sport, Sport.id == Squad.sport_id)
                                   .order_by(Sport.name, Squad.season.desc())).all()
            self.sport.clear()
            for sp in sports:
                self.sport.addItem(sp.name, sp.id)
            self.squad.blockSignals(True)
            self.squad.clear()
            for sq, n in squads:
                self.squad.addItem(f"{n} {sq.season}", sq.id)
            self.squad.blockSignals(False)
            self._show()
        guarded(self, work)

    def _show(self):
        sid = self.squad.currentData()

        def work():
            with session_scope() as s:
                rep = reports.squad_register(s)
            rows = [[r[3], r[4], r[5], r[6]] for r in rep.rows if r[0] == sid]
            self.table.load(["Shirt", "Player", "Position", "Status"], rows)
        if sid is not None:
            guarded(self, work)
        else:
            self.table.load(["Shirt", "Player", "Position", "Status"], [])

    def _create(self):
        def work():
            with session_scope() as s:
                football.create_squad(s, self.sport.currentData(), self.season.text().strip())
        if guarded(self, work):
            self.refresh()

    def _add(self):
        sid = self.squad.currentData()
        if not need_selection(self, sid, "squad"):
            return
        with session_scope() as s:
            people = _members(s)
        mid = _pick_member(self, "Add player", people)
        if mid is None:
            return
        shirt, ok = QInputDialog.getInt(self, "Add player", "Shirt number (0 = none):", 0, 0, 99)
        if not ok:
            return
        pos, _ = QInputDialog.getText(self, "Add player", "Position (optional):")

        def work():
            with session_scope() as s:
                football.add_to_squad(s, sid, mid, shirt or None, pos)
        if guarded(self, work):
            self._show()

    def _remove(self):
        sid, row = self.squad.currentData(), self.table.currentRow()
        if sid is None or row < 0:
            return
        name = self.table.item(row, 1).text()

        def work():
            with session_scope() as s:
                mid = s.scalar(select(Person.id).where(Person.full_name == name))
                football.remove_from_squad(s, sid, mid)
        if guarded(self, work):
            self._show()


class ContractDialog(QDialog):
    def __init__(self, parent, people, sports):
        super().__init__(parent)
        self.setWindowTitle("Sign contract")
        self.who, self.sport, self.kind = QComboBox(), QComboBox(), QComboBox()
        for p, n in people:
            self.who.addItem(f"{n} (#{p})", p)
        for sp in sports:
            self.sport.addItem(sp.name, sp.id)
        self.kind.addItems(football.CONTRACT_TYPES)
        self.start, self.end = QDateEdit(QDate.currentDate()), QDateEdit(QDate.currentDate().addYears(1))
        for d in (self.start, self.end):
            d.setCalendarPopup(True)
        self.wage = QDoubleSpinBox()
        self.wage.setRange(0, 10_000_000)
        self.notes = QLineEdit()
        form = QFormLayout()
        for label, w in (("Player", self.who), ("Game", self.sport), ("Type", self.kind), ("Start", self.start),
                         ("End", self.end), ("Monthly wage (Ksh)", self.wage), ("Notes", self.notes)):
            form.addRow(label, w)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(box)


class ContractsPanel(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.table = DataTable()
        self.note = QLabel("")
        sign, term = QPushButton("Sign contract…"), QPushButton("Terminate selected")
        sign.clicked.connect(self._sign)
        term.clicked.connect(self._terminate)
        row = QHBoxLayout()
        row.addWidget(sign)
        row.addWidget(term)
        if auth.can(user.role, "finance"):
            pay = QPushButton("Pay wage for month…")
            pay.clicked.connect(self._pay)
            row.addWidget(pay)
        lay = QVBoxLayout(self)
        lay.addWidget(self.note)
        lay.addWidget(self.table)
        lay.addLayout(row)
        self.refresh()

    def refresh(self):
        def work():
            with session_scope() as s:
                rep = reports.contracts(s)
                exp = reports.contracts_expiring(s)
            self.table.load(rep.headers, rep.rows)
            self.note.setText(f"{len(exp.rows)} contract(s) expire within 90 days" if exp.rows else "")
            self.note.setStyleSheet("color:#b26a00;font-weight:bold")
        guarded(self, work)

    def _sign(self):
        with session_scope() as s:
            people, sports = _members(s), list(s.scalars(select(Sport).order_by(Sport.name)))
        dlg = ContractDialog(self, people, sports)
        if dlg.exec():
            def work():
                with session_scope() as s:
                    football.sign_contract(s, dlg.who.currentData(), dlg.sport.currentData(), dlg.kind.currentText(),
                                           dlg.start.date().toPython(), dlg.end.date().toPython(), dlg.wage.value(),
                                           dlg.notes.text(), self.user.id)
            if guarded(self, work):
                self.refresh()

    def _terminate(self):
        cid = self.table.selected_id()
        if not need_selection(self, cid, "contract"):
            return

        def work():
            with session_scope() as s:
                football.terminate_contract(s, cid, user_id=self.user.id)
        if guarded(self, work, "Contract terminated as of today."):
            self.refresh()

    def _pay(self):
        cid = self.table.selected_id()
        if not need_selection(self, cid, "contract"):
            return
        period, ok = QInputDialog.getText(self, "Pay wage", "Month (YYYY-MM):", text=date.today().strftime("%Y-%m"))
        if ok:
            def work():
                with session_scope() as s:
                    football.pay_wage(s, cid, period.strip(), self.user.id)
            if guarded(self, work, "Wage paid and posted to the ledger as an expense."):
                self.refresh()


class ResultDialog(QDialog):
    COLS = ("Minutes", "Scored", "Assists", "Yellow", "Red")
    MAX = (240, 99, 99, 2, 1)

    def __init__(self, parent, title, team):
        super().__init__(parent)
        self.setWindowTitle(f"Result: {title}")
        self.team = team
        self.sf, self.sa = QSpinBox(), QSpinBox()
        for s in (self.sf, self.sa):
            s.setRange(0, 999)
        self.table = QTableWidget(len(team), len(self.COLS))
        self.table.setHorizontalHeaderLabels(list(self.COLS))
        self.table.setVerticalHeaderLabels([n for _, n in team])
        for r in range(len(team)):
            for c, mx in enumerate(self.MAX):
                sp = QSpinBox()
                sp.setRange(0, mx)
                self.table.setCellWidget(r, c, sp)
        score = QHBoxLayout()
        for w in (QLabel("Club score"), self.sf, QLabel("Opponent score"), self.sa):
            score.addWidget(w)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(score)
        lay.addWidget(QLabel("Player statistics (optional)"))
        lay.addWidget(self.table)
        lay.addWidget(box)
        self.resize(560, 420)

    def values(self):
        stats = []
        for r, (mid, _n) in enumerate(self.team):
            v = [self.table.cellWidget(r, c).value() for c in range(len(self.COLS))]
            if any(v):
                stats.append({"member_id": mid, "minutes": v[0], "scored": v[1], "assists": v[2],
                              "yellow_cards": v[3], "red_cards": v[4]})
        return self.sf.value(), self.sa.value(), stats


class ResultsPanel(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.table, self.record = DataTable(), DataTable()
        btn = QPushButton("Record result for selected fixture…")
        btn.clicked.connect(self._record)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("External fixtures"))
        lay.addWidget(self.table)
        lay.addWidget(btn)
        lay.addWidget(QLabel("Club record by game"))
        lay.addWidget(self.record)
        self.refresh()

    def refresh(self):
        def work():
            with session_scope() as s:
                q = (select(Event, Sport.name, MatchResult).join(Sport, Sport.id == Event.sport_id)
                     .outerjoin(MatchResult, MatchResult.event_id == Event.id).where(Event.is_external.is_(True))
                     .order_by(Event.event_date.desc()))
                rows = []
                for ev, sp, res in s.execute(q):
                    status = f"{res.score_for}-{res.score_against}" if res else (
                        "Pending result" if ev.event_date <= date.today() else "Upcoming")
                    rows.append([ev.id, ev.event_date, sp, ev.title, ev.opponent, status])
                rec = reports.club_record_by_game(s)
            self.table.load(["ID", "Date", "Game", "Title", "Opponent", "Result"], rows)
            self.record.load(rec.headers, rec.rows)
        guarded(self, work)

    def _record(self):
        eid = self.table.selected_id()
        if not need_selection(self, eid, "fixture"):
            return
        with session_scope() as s:
            ev = s.get(Event, eid)
            team = [(m, n) for m, n in s.execute(select(EventRoster.member_id, Person.full_name)
                                                 .join(Person, Person.id == EventRoster.member_id)
                                                 .where(EventRoster.event_id == eid).order_by(Person.full_name))]
            title = ev.title
        dlg = ResultDialog(self, title, team)
        if dlg.exec():
            sf, sa, stats = dlg.values()

            def work():
                with session_scope() as s:
                    football.record_result(s, eid, sf, sa, stats, self.user.id)
            if guarded(self, work, "Result recorded."):
                self.refresh()


class InjuriesPanel(QWidget):
    def __init__(self, user):
        super().__init__()
        self.table = DataTable()
        rec, clr = QPushButton("Record injury…"), QPushButton("Clear selected (fit again)")
        rec.clicked.connect(self._record)
        clr.clicked.connect(self._clear)
        row = QHBoxLayout()
        row.addWidget(rec)
        row.addWidget(clr)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Injured players cannot be selected for events."))
        lay.addWidget(self.table)
        lay.addLayout(row)
        self.refresh()

    def refresh(self):
        def work():
            with session_scope() as s:
                rep = reports.injuries_open(s)
            self.table.load(rep.headers, rep.rows)
        guarded(self, work)

    def _record(self):
        with session_scope() as s:
            people = _members(s)
        mid = _pick_member(self, "Record injury", people)
        if mid is None:
            return
        desc, ok = QInputDialog.getText(self, "Record injury", "What is the injury?")
        if not ok:
            return
        back, ok = QInputDialog.getText(self, "Record injury", "Expected return (YYYY-MM-DD, blank if unknown):")
        if not ok:
            return

        def work():
            exp = date.fromisoformat(back.strip()) if back.strip() else None
            with session_scope() as s:
                football.record_injury(s, mid, desc, date.today(), exp)
        if guarded(self, work):
            self.refresh()

    def _clear(self):
        iid = self.table.selected_id()
        if not need_selection(self, iid, "injury"):
            return

        def work():
            with session_scope() as s:
                football.clear_injury(s, iid)
        if guarded(self, work):
            self.refresh()


class FootballTab(QWidget):
    def __init__(self, user):
        super().__init__()
        self.panels = [("Squads", SquadsPanel(user)), ("Contracts & wages", ContractsPanel(user)),
                       ("Match results", ResultsPanel(user)), ("Injuries", InjuriesPanel(user))]
        tabs = QTabWidget()
        for name, p in self.panels:
            tabs.addTab(p, name)
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)

    def refresh(self):
        for _n, p in self.panels:
            p.refresh()
