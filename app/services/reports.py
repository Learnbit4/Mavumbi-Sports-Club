"""Reports return a Report(title, headers, rows) so the GUI and the exporters share one source."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from .. import rules
from ..models import (Contract, Equipment, EquipmentIssue, Event, EventRoster, Injury, Item, MatchResult, Member,
                      MemberSport, OrgGroup, Person, Sale, Sport, Squad, SquadPlayer, StockMovement, Surcharge)
from . import football, ledger


@dataclass
class Report:
    title: str
    headers: list[str]
    rows: list[list]


def _members(session):
    return session.execute(select(Member, Person, OrgGroup).join(Person, Person.id == Member.person_id)
                           .outerjoin(OrgGroup, OrgGroup.id == Member.group_id).order_by(Person.full_name)).all()


def members_list(session, start=None, end=None) -> Report:
    prio = {}
    for mid, name, pr in session.execute(select(MemberSport.member_id, Sport.name, MemberSport.priority)
                                         .join(Sport, Sport.id == MemberSport.sport_id).order_by(MemberSport.priority)):
        prio.setdefault(mid, []).append(name)
    rows = [[p.id, p.full_name, p.gender, rules.age_on(p.date_of_birth),
             rules.age_category(rules.age_on(p.date_of_birth), strict=False), g.name if g else "Individual",
             p.sub_county, m.institution, " > ".join(prio.get(p.id, [])), m.fee_charged]
            for m, p, g in _members(session)]
    return Report("Member register", ["ID", "Name", "Gender", "Age", "Category", "Group", "Sub-county",
                                      "Institution", "Games (priority)", "Fee"], rows)


def members_by_category(session, start=None, end=None) -> Report:
    counts: dict[str, int] = {}
    for _, p, _g in _members(session):
        c = rules.age_category(rules.age_on(p.date_of_birth), strict=False)
        counts[c] = counts.get(c, 0) + 1
    return Report("Members by age category", ["Category", "Members"], [[k, v] for k, v in sorted(counts.items())])


def members_by_sport(session, start=None, end=None) -> Report:
    q = (select(Sport.name, MemberSport.priority, func.count()).join(MemberSport, MemberSport.sport_id == Sport.id)
         .group_by(Sport.name, MemberSport.priority).order_by(Sport.name, MemberSport.priority))
    data: dict[str, dict[int, int]] = {}
    for n, pr, c in session.execute(q):
        data.setdefault(n, {})[pr] = c
    rows = [[n, d.get(1, 0), sum(d.values())] for n, d in sorted(data.items())]
    return Report("Members by game", ["Game", "First choice", "Any choice"], rows)


def sales(session, start: date | None = None, end: date | None = None) -> Report:
    q = select(Sale, Person.full_name).outerjoin(Person, Person.id == Sale.person_id).order_by(Sale.sold_at)
    if start:
        q = q.where(func.date(Sale.sold_at) >= start)
    if end:
        q = q.where(func.date(Sale.sold_at) <= end)
    rows = [[s.id, s.sold_at.strftime("%Y-%m-%d %H:%M"), s.channel, n or "Walk-in", s.subtotal, s.discount,
             s.total, s.payment_method] for s, n in session.execute(q)]
    return Report("Sales", ["Sale", "When", "Channel", "Customer", "Subtotal", "Discount", "Total", "Paid by"], rows)


def stock_levels(session, start=None, end=None) -> Report:
    rows = [[i.id, i.name, i.channel, i.stock_qty, i.max_stock,
             f"{(i.stock_qty / i.max_stock * 100):.0f}%", "REORDER" if rules.needs_reorder(i.stock_qty, i.max_stock) else ""]
            for i in session.scalars(select(Item).where(Item.active.is_(True)).order_by(Item.name))]
    return Report("Stock levels", ["ID", "Item", "Channel", "In stock", "Max", "Level", "Alert"], rows)


def stock_history(session, start=None, end=None) -> Report:
    q = select(StockMovement, Item.name).join(Item, Item.id == StockMovement.item_id).order_by(StockMovement.id)
    rows = [[m.moved_at.strftime("%Y-%m-%d %H:%M"), n, m.reason, m.change, m.resulting_qty] for m, n in session.execute(q)]
    return Report("Stock movements", ["When", "Item", "Reason", "Change", "Stock after"], rows)


def facilitation(session, start=None, end=None) -> Report:
    rows = []
    for ev, sp in session.execute(select(Event, Sport.name).join(Sport, Sport.id == Event.sport_id)
                                  .where(Event.is_external.is_(True)).order_by(Event.event_date)):
        r = session.scalars(select(EventRoster).where(EventRoster.event_id == ev.id)).all()
        due = sum((x.fee_amount for x in r), Decimal(0))
        paid = sum((x.fee_amount for x in r if x.fee_paid_on), Decimal(0))
        rows.append([ev.id, ev.event_date, sp, ev.title, ev.opponent, len(r), due, paid, ev.patron_commission or 0])
    return Report("Facilitation fees & patron commission",
                  ["Event", "Date", "Game", "Title", "Opponent", "Team", "Fees due", "Collected", "Patron commission"], rows)


def surcharges_outstanding(session, start=None, end=None) -> Report:
    q = (select(Surcharge, Person.full_name, Event.title).join(Person, Person.id == Surcharge.member_id)
         .join(EquipmentIssue, EquipmentIssue.id == Surcharge.issue_id).join(Event, Event.id == EquipmentIssue.event_id)
         .where(Surcharge.paid_on.is_(None)).order_by(Surcharge.id))
    return Report("Outstanding surcharges", ["ID", "Member", "Event", "Amount"],
                  [[s.id, n, t, s.amount] for s, n, t in session.execute(q)])


def income_summary(session, start=None, end=None) -> Report:
    s = ledger.summary(session, start, end)
    rows = [[k.replace("_", " ").title(), v] for k, v in s["income"].items()]
    rows += [["GROSS INCOME", s["gross_income"]]]
    rows += [[f"less {k.replace('_', ' ')}", v] for k, v in s["expenses"].items()]
    rows += [["NET INCOME", s["net_income"]]]
    return Report("Club income summary", ["Source", "Amount (Ksh)"], rows)


# ---------------------------------------------------------------- football operations
def squad_register(session, start=None, end=None) -> Report:
    q = (select(Squad, Sport.name, SquadPlayer, Person.full_name).join(Sport, Sport.id == Squad.sport_id)
         .join(SquadPlayer, SquadPlayer.squad_id == Squad.id).join(Person, Person.id == SquadPlayer.member_id)
         .order_by(Sport.name, Squad.season.desc(), SquadPlayer.shirt_number))
    rows = [[sq.id, sp, sq.season, pl.shirt_number, name, pl.position, "INJURED" if football.is_injured(session, pl.member_id) else ""]
            for sq, sp, pl, name in session.execute(q)]
    return Report("Squad register", ["Squad", "Game", "Season", "Shirt", "Player", "Position", "Status"], rows)


def contracts(session, start=None, end=None) -> Report:
    q = (select(Contract, Person.full_name, Sport.name).join(Person, Person.id == Contract.member_id)
         .join(Sport, Sport.id == Contract.sport_id).order_by(Contract.end_date))
    rows = [[c.id, n, sp, c.contract_type, c.start_date, c.end_date, c.monthly_wage, football.contract_status(c)]
            for c, n, sp in session.execute(q)]
    return Report("Contracts", ["ID", "Player", "Game", "Type", "Start", "End", "Monthly wage", "Status"], rows)


def contracts_expiring(session, start=None, end=None) -> Report:
    rows = []
    for c in football.expiring_contracts(session, 90):
        p, sp = session.get(Person, c.member_id), session.get(Sport, c.sport_id)
        rows.append([c.id, p.full_name, sp.name, c.end_date, (c.end_date - date.today()).days, c.monthly_wage])
    return Report("Contracts expiring within 90 days", ["ID", "Player", "Game", "Ends", "Days left", "Monthly wage"], rows)


def match_results(session, start=None, end=None) -> Report:
    q = (select(MatchResult, Event, Sport.name).join(Event, Event.id == MatchResult.event_id)
         .join(Sport, Sport.id == Event.sport_id).order_by(Event.event_date.desc()))
    if start:
        q = q.where(Event.event_date >= start)
    if end:
        q = q.where(Event.event_date <= end)
    rows = [[ev.id, ev.event_date, sp, ev.title, ev.opponent, f"{r.score_for}-{r.score_against}",
             rules.match_outcome(r.score_for, r.score_against)] for r, ev, sp in session.execute(q)]
    return Report("Match results", ["Event", "Date", "Game", "Title", "Opponent", "Score", "Result"], rows)


def club_record_by_game(session, start=None, end=None) -> Report:
    rows = []
    for sp in session.scalars(select(Sport).order_by(Sport.name)):
        r = football.club_record(session, sp.id, start, end)
        if r["played"]:
            rows.append([sp.name, r["played"], r["won"], r["drawn"], r["lost"], r["for"], r["against"], r["diff"], r["points"]])
    return Report("Club record by game", ["Game", "P", "W", "D", "L", "For", "Against", "Diff", "Pts (3-1-0)"], rows)


def top_scorers(session, start=None, end=None) -> Report:
    rows = [[i, n, s, a, c, m] for i, n, s, a, c, m in football.top_scorers(session, None, 20)]
    return Report("Top scorers", ["ID", "Player", "Scored", "Assists", "Apps", "Minutes"], rows)


def injuries_open(session, start=None, end=None) -> Report:
    q = (select(Injury, Person.full_name).join(Person, Person.id == Injury.member_id)
         .where(Injury.cleared_on.is_(None)).order_by(Injury.injured_on))
    return Report("Open injuries", ["ID", "Player", "Injury", "Since", "Expected return"],
                  [[i.id, n, i.description, i.injured_on, i.expected_return] for i, n in session.execute(q)])


def wages_paid(session, start=None, end=None) -> Report:
    from ..models import WagePayment
    q = (select(WagePayment, Person.full_name).join(Contract, Contract.id == WagePayment.contract_id)
         .join(Person, Person.id == Contract.member_id).order_by(WagePayment.paid_on.desc()))
    if start:
        q = q.where(WagePayment.paid_on >= start)
    if end:
        q = q.where(WagePayment.paid_on <= end)
    return Report("Wages paid", ["ID", "Player", "Period", "Amount", "Paid on"],
                  [[w.id, n, w.period, w.amount, w.paid_on] for w, n in session.execute(q)])


REGISTRY = {"Member register": members_list, "Members by category": members_by_category,
            "Members by game": members_by_sport, "Sales": sales, "Stock levels": stock_levels,
            "Stock movements": stock_history, "Facilitation & commission": facilitation,
            "Outstanding surcharges": surcharges_outstanding, "Income summary": income_summary,
            "Squad register": squad_register, "Contracts": contracts, "Contracts expiring": contracts_expiring,
            "Match results": match_results, "Club record by game": club_record_by_game, "Top scorers": top_scorers,
            "Open injuries": injuries_open, "Wages paid": wages_paid}


def export_csv(report: Report, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(report.headers)
        w.writerows(report.rows)


def export_xlsx(report: Report, path: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = report.title[:31]
    ws.append(report.headers)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in report.rows:
        ws.append([float(v) if isinstance(v, Decimal) else v for v in r])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(40, max(len(str(c.value or "")) for c in col) + 2)
    wb.save(path)
