from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from .. import rules
from ..errors import NotFound, ValidationError
from ..models import Event, EventRoster, EquipmentIssue, Member, Person, Sport, Surcharge, TicketSale
from . import audit, football, ledger, membership


def create_event(session, sport_id: int, title: str, event_date: date, venue: str = "",
                 opponent: str = "", ticket_price=0) -> Event:
    if session.get(Sport, sport_id) is None:
        raise NotFound("Sport not found")
    if not title.strip():
        raise ValidationError("Event title required")
    price = rules.money(ticket_price)
    if price < 0:
        raise ValidationError("Ticket price cannot be negative")
    ev = Event(sport_id=sport_id, title=title.strip(), event_date=event_date, venue=venue or None,
               opponent=opponent.strip() or None, is_external=bool(opponent.strip()), ticket_price=price)
    session.add(ev)
    session.flush()
    return ev


def set_roster(session, event_id: int, member_ids: list[int], captain_id: int) -> list[EventRoster]:
    """Pick the team. Facilitation fee (Ksh 500 each) applies only to external fixtures."""
    ev = session.get(Event, event_id)
    if ev is None:
        raise NotFound("Event not found")
    if not member_ids:
        raise ValidationError("A team needs at least one member")
    if captain_id not in member_ids:
        raise ValidationError("The captain must be part of the team")
    if len(set(member_ids)) != len(member_ids):
        raise ValidationError("A member was listed twice")
    existing = list(session.scalars(select(EventRoster).where(EventRoster.event_id == event_id)))
    if any(r.fee_paid_on for r in existing):
        raise ValidationError("Roster is locked: facilitation fees have already been collected")
    for r in existing:
        session.delete(r)
    session.flush()
    fee = rules.FACILITATION_FEE if ev.is_external else rules.money(0)
    rows = []
    for mid in member_ids:
        if session.get(Member, mid) is None:
            raise NotFound(f"Member {mid} not found")
        if football.is_injured(session, mid, ev.event_date):
            name = session.get(Person, mid).full_name
            raise ValidationError(f"{name} is injured and cannot be selected for this event")
        r = EventRoster(event_id=event_id, member_id=mid, is_captain=(mid == captain_id), fee_amount=fee)
        session.add(r)
        rows.append(r)
    membership.assign_role(session, captain_id, "Captain", ev.sport_id)
    session.flush()
    return rows


def roster(session, event_id: int) -> list[EventRoster]:
    return list(session.scalars(select(EventRoster).where(EventRoster.event_id == event_id)
                                .order_by(EventRoster.is_captain.desc(), EventRoster.member_id)))


def collect_facilitation(session, event_id: int, member_id: int, paid_on: date | None = None, user_id=None):
    r = session.get(EventRoster, (event_id, member_id))
    if r is None:
        raise NotFound("That member is not on this event's roster")
    if r.fee_amount <= 0:
        raise ValidationError("No facilitation fee applies to this event")
    if r.fee_paid_on:
        raise ValidationError("Fee already collected")
    r.fee_paid_on = paid_on or date.today()
    ledger.post(session, "IN", "facilitation", r.fee_amount, f"Facilitation, event #{event_id}, member #{member_id}",
                "event", event_id, entry_date=r.fee_paid_on, user_id=user_id)
    return r


def settle_event(session, event_id: int, user_id=None):
    """Post the patron's 20% commission on facilitation fees collected. Runs once per event."""
    ev = session.get(Event, event_id)
    if ev is None:
        raise NotFound("Event not found")
    if not ev.is_external:
        raise ValidationError("Only external fixtures carry facilitation fees")
    if ev.commission_posted:
        raise ValidationError("Commission already posted for this event")
    sport = session.get(Sport, ev.sport_id)
    if sport.patron_id is None:
        raise ValidationError(f"Assign a patron to {sport.name} before settling")
    collected = session.scalar(select(func.coalesce(func.sum(EventRoster.fee_amount), 0)).where(
        EventRoster.event_id == event_id, EventRoster.fee_paid_on.is_not(None)))
    if collected <= 0:
        raise ValidationError("No facilitation fees collected yet")
    commission = rules.patron_commission(collected)
    ledger.post(session, "OUT", "patron_commission", commission, f"Patron commission, event #{event_id}",
                "event", event_id, user_id=user_id)
    ev.patron_commission, ev.commission_posted = commission, True
    audit.log(session, user_id, "event_settled", f"event {event_id} commission {commission}")
    return ev


def sell_tickets(session, event_id: int, qty: int, person_id: int | None = None, user_id=None) -> TicketSale:
    ev = session.get(Event, event_id)
    if ev is None:
        raise NotFound("Event not found")
    if qty <= 0:
        raise ValidationError("Quantity must be positive")
    if ev.ticket_price <= 0:
        raise ValidationError("This event has no ticket price")
    total = rules.money(ev.ticket_price * qty)
    t = TicketSale(event_id=event_id, person_id=person_id, qty=qty, unit_price=ev.ticket_price, total=total)
    session.add(t)
    session.flush()
    ledger.post(session, "IN", "ticket", total, f"{qty} ticket(s), event #{event_id}", "ticket_sale", t.id,
                user_id=user_id)
    return t


def event_financials(session, event_id: int) -> dict:
    zero = rules.money(0)
    due = session.scalar(select(func.coalesce(func.sum(EventRoster.fee_amount), 0)).where(EventRoster.event_id == event_id))
    paid = session.scalar(select(func.coalesce(func.sum(EventRoster.fee_amount), 0)).where(
        EventRoster.event_id == event_id, EventRoster.fee_paid_on.is_not(None)))
    tickets = session.scalar(select(func.coalesce(func.sum(TicketSale.total), 0)).where(TicketSale.event_id == event_id))
    ev = session.get(Event, event_id)
    sur = session.execute(select(func.coalesce(func.sum(Surcharge.amount), 0)).join(
        EquipmentIssue, Surcharge.issue_id == EquipmentIssue.id).where(EquipmentIssue.event_id == event_id)).scalar()
    return {"facilitation_due": rules.money(due), "facilitation_collected": rules.money(paid),
            "patron_commission": ev.patron_commission or zero, "ticket_revenue": rules.money(tickets),
            "surcharges_charged": rules.money(sur)}
