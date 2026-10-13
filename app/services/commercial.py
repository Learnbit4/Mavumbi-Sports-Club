from __future__ import annotations

from datetime import date

from sqlalchemy import select

from .. import rules
from ..errors import NotFound, ValidationError
from ..models import Sponsor, SponsorshipPayment
from . import ledger


def add_sponsor(session, name: str, contact_person: str = "", phone: str = "", email: str = "") -> Sponsor:
    if not name.strip():
        raise ValidationError("Sponsor name required")
    if session.scalar(select(Sponsor).where(Sponsor.name == name.strip())):
        raise ValidationError("Sponsor already exists")
    s = Sponsor(name=name.strip(), contact_person=contact_person or None, phone=phone or None, email=email or None)
    session.add(s)
    session.flush()
    return s


def list_sponsors(session) -> list[Sponsor]:
    return list(session.scalars(select(Sponsor).order_by(Sponsor.name)))


def record_sponsorship(session, sponsor_id: int, amount, received_on: date | None = None, purpose: str = "",
                       sport_id: int | None = None, user_id=None) -> SponsorshipPayment:
    """Income is booked when money is RECEIVED, never when pledged."""
    if session.get(Sponsor, sponsor_id) is None:
        raise NotFound("Sponsor not found")
    amt = rules.money(amount)
    if amt <= 0:
        raise ValidationError("Amount must be positive")
    received_on = received_on or date.today()
    p = SponsorshipPayment(sponsor_id=sponsor_id, amount=amt, received_on=received_on,
                           purpose=purpose or None, sport_id=sport_id)
    session.add(p)
    session.flush()
    ledger.post(session, "IN", "sponsorship", amt, f"Sponsorship #{p.id}: {purpose}", "sponsorship", p.id,
                entry_date=received_on, user_id=user_id)
    return p
