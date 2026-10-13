"""The single financial ledger. Total income is a query over this table, nowhere else."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from .. import rules
from ..errors import NotFound, ValidationError
from ..models import LedgerEntry

INCOME = ("membership", "store_sale", "merchandise", "facilitation", "surcharge", "ticket", "sponsorship")
EXPENSE = ("patron_commission", "wages")


def post(session, direction: str, category: str, amount, description: str = "", ref_type=None,
         ref_id=None, entry_date: date | None = None, user_id=None, _reversal_of=None) -> LedgerEntry:
    amount = rules.money(amount)
    if amount <= 0:
        raise ValidationError("Ledger amount must be positive")
    if _reversal_of is None:
        ok = (direction == "IN" and category in INCOME) or (direction == "OUT" and category in EXPENSE)
        if not ok:
            raise ValidationError(f"Invalid ledger entry: {direction} / {category}")
    e = LedgerEntry(entry_date=entry_date or date.today(), direction=direction, category=category,
                    amount=amount, description=description[:255], ref_type=ref_type, ref_id=ref_id,
                    reversal_of=_reversal_of, created_by=user_id)
    session.add(e)
    session.flush()
    return e


def reverse(session, entry_id: int, user_id=None, reason: str = "") -> LedgerEntry:
    e = session.get(LedgerEntry, entry_id)
    if e is None:
        raise NotFound(f"Ledger entry {entry_id} not found")
    if e.reversal_of is not None:
        raise ValidationError("A reversal cannot itself be reversed")
    if session.scalar(select(LedgerEntry.id).where(LedgerEntry.reversal_of == entry_id)):
        raise ValidationError("Entry already reversed")
    opposite = "OUT" if e.direction == "IN" else "IN"
    return post(session, opposite, e.category, e.amount, f"Reversal of #{e.id}: {reason}",
                e.ref_type, e.ref_id, user_id=user_id, _reversal_of=e.id)


def summary(session, start: date | None = None, end: date | None = None) -> dict:
    """Net per category (reversals net off automatically)."""
    q = select(LedgerEntry.category, LedgerEntry.direction, func.sum(LedgerEntry.amount)).group_by(
        LedgerEntry.category, LedgerEntry.direction)
    if start:
        q = q.where(LedgerEntry.entry_date >= start)
    if end:
        q = q.where(LedgerEntry.entry_date <= end)
    raw: dict[tuple[str, str], Decimal] = {(c, d): rules.money(t) for c, d, t in session.execute(q)}
    zero = Decimal("0.00")
    income = {c: raw.get((c, "IN"), zero) - raw.get((c, "OUT"), zero) for c in INCOME}
    expense = {c: raw.get((c, "OUT"), zero) - raw.get((c, "IN"), zero) for c in EXPENSE}
    gross, costs = sum(income.values(), zero), sum(expense.values(), zero)
    return {"income": income, "expenses": expense, "gross_income": gross,
            "total_expenses": costs, "net_income": gross - costs}
