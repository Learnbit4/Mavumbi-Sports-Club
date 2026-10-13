from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select

from .. import rules
from ..errors import NotFound, StockError, ValidationError
from ..models import Equipment, EquipmentIssue, EquipmentIssueLine, EventRoster, Sport, Surcharge
from . import audit, ledger


def add_equipment(session, name: str, sport_id: int, market_value, qty: int) -> Equipment:
    if session.get(Sport, sport_id) is None:
        raise NotFound("Sport not found")
    if qty <= 0 or rules.money(market_value) <= 0:
        raise ValidationError("Quantity and market value must be positive")
    eq = Equipment(name=name.strip(), sport_id=sport_id, market_value=rules.money(market_value),
                   qty_total=qty, qty_available=qty)
    session.add(eq)
    session.flush()
    return eq


def issue(session, event_id: int, captain_id: int, lines: list[tuple[int, int]], user_id=None) -> EquipmentIssue:
    """Captain collects equipment for an event. lines = [(equipment_id, qty)]."""
    cap = session.get(EventRoster, (event_id, captain_id))
    if cap is None or not cap.is_captain:
        raise ValidationError("Only the event's captain may collect equipment")
    if not lines:
        raise ValidationError("Choose at least one item")
    iss = EquipmentIssue(event_id=event_id, captain_id=captain_id)
    session.add(iss)
    session.flush()
    for eid, qty in lines:
        eq = session.get(Equipment, eid, with_for_update=True)
        if eq is None:
            raise NotFound("Equipment not found")
        if qty <= 0:
            raise ValidationError("Quantity must be positive")
        if eq.qty_available < qty:
            raise StockError(f"Only {eq.qty_available} x {eq.name} available")
        eq.qty_available -= qty
        session.add(EquipmentIssueLine(issue_id=iss.id, equipment_id=eid, qty_out=qty))
    audit.log(session, user_id, "equipment_issued", f"issue {iss.id}")
    return iss


def return_issue(session, issue_id: int, losses: dict[int, tuple[int, int]] | None = None, user_id=None) -> list[Surcharge]:
    """Close an issue. losses = {line_id: (lost, damaged)}; everything else is returned in good order.

    Lost and damaged units are written off. The surcharge (market value + 10%) is split evenly across the
    event's whole team, captain included; the captain takes any leftover cents.
    """
    iss = session.get(EquipmentIssue, issue_id)
    if iss is None:
        raise NotFound("Issue not found")
    if iss.returned_at:
        raise ValidationError("This issue has already been returned")
    losses = losses or {}
    charge = rules.money(0)
    for ln in iss.lines:
        lost, damaged = losses.get(ln.id, (0, 0))
        if lost < 0 or damaged < 0 or lost + damaged > ln.qty_out:
            raise ValidationError(f"Lost + damaged exceeds quantity issued for {ln.equipment.name}")
        ln.qty_lost, ln.qty_damaged, ln.qty_returned = lost, damaged, ln.qty_out - lost - damaged
        eq = ln.equipment
        eq.qty_available += ln.qty_returned
        eq.qty_total -= lost + damaged
        charge += rules.surcharge(eq.market_value, lost + damaged) if lost + damaged else 0
    iss.returned_at = datetime.now()
    out: list[Surcharge] = []
    if charge > 0:
        team = list(session.scalars(select(EventRoster).where(EventRoster.event_id == iss.event_id)
                                    .order_by(EventRoster.is_captain.desc(), EventRoster.member_id)))
        for r, share in zip(team, rules.split_evenly(charge, len(team))):
            if share > 0:
                s = Surcharge(issue_id=iss.id, member_id=r.member_id, amount=share)
                session.add(s)
                out.append(s)
    session.flush()
    audit.log(session, user_id, "equipment_returned", f"issue {issue_id} surcharge {charge}")
    return out


def pay_surcharge(session, surcharge_id: int, paid_on: date | None = None, user_id=None) -> Surcharge:
    s = session.get(Surcharge, surcharge_id)
    if s is None:
        raise NotFound("Surcharge not found")
    if s.paid_on:
        raise ValidationError("Already paid")
    s.paid_on = paid_on or date.today()
    ledger.post(session, "IN", "surcharge", s.amount, f"Surcharge #{s.id}", "surcharge", s.id,
                entry_date=s.paid_on, user_id=user_id)
    return s
