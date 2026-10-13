"""Pure business rules. No database, no GUI: everything here is unit-tested.

All money is Decimal rounded half-up to cents. Never use float for money.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

MIN_AGE, MAX_AGE = 12, 35
INDIVIDUAL_FEE = Decimal("1000")
GROUP_FEE_PER_PERSON = Decimal("500")
DISCOUNT_THRESHOLD = Decimal("10000")      # discount only if purchase EXCEEDS this
DISCOUNT_RATE = Decimal("0.05")
FACILITATION_FEE = Decimal("500")          # per team member, external fixtures only
PATRON_COMMISSION_RATE = Decimal("0.20")
SURCHARGE_MARKUP = Decimal("0.10")
REORDER_FRACTION = Decimal("0.20")

CENT = Decimal("0.01")
CATEGORIES = (("Minor", 12, 17), ("Middle", 18, 25), ("Senior", 26, 35))


def D(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def money(x) -> Decimal:
    return D(x).quantize(CENT, rounding=ROUND_HALF_UP)


def age_on(dob: date, on: date | None = None) -> int:
    on = on or date.today()
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def age_category(age: int, strict: bool = True) -> str:
    """Minor 12-17, Middle 18-25, Senior 26-35.

    strict=True (enrolment) raises outside 12-35. strict=False (reporting on
    existing members who have since aged out) returns 'Over-age'/'Under-age'.
    """
    for name, lo, hi in CATEGORIES:
        if lo <= age <= hi:
            return name
    if strict:
        raise ValueError(f"Age {age} is outside the enrolment range {MIN_AGE}-{MAX_AGE}")
    return "Over-age" if age > MAX_AGE else "Under-age"


def membership_fee(is_group: bool, people: int = 1) -> Decimal:
    if people < 1:
        raise ValueError("people must be >= 1")
    return money(GROUP_FEE_PER_PERSON * people) if is_group else money(INDIVIDUAL_FEE * people)


def purchase_totals(lines: Iterable[tuple[int, Decimal]]) -> tuple[Decimal, Decimal, Decimal]:
    """lines = (qty, unit_price). Returns (subtotal, discount, total)."""
    subtotal = money(sum((D(p) * q for q, p in lines), Decimal(0)))
    discount = money(subtotal * DISCOUNT_RATE) if subtotal > DISCOUNT_THRESHOLD else Decimal("0.00")
    return subtotal, discount, money(subtotal - discount)


def facilitation_total(team_size: int) -> Decimal:
    return money(FACILITATION_FEE * team_size)


def patron_commission(total_facilitation: Decimal) -> Decimal:
    return money(D(total_facilitation) * PATRON_COMMISSION_RATE)


def surcharge(market_value: Decimal, qty: int) -> Decimal:
    """Market value plus 10%, per lost or damaged unit."""
    return money(D(market_value) * (1 + SURCHARGE_MARKUP) * qty)


def split_evenly(amount: Decimal, parties: int) -> list[Decimal]:
    """Split so the shares sum EXACTLY to amount; leftover cents go to the first parties
    (callers put the captain first)."""
    if parties < 1:
        raise ValueError("parties must be >= 1")
    cents = int(money(amount) * 100)
    q, r = divmod(cents, parties)
    return [Decimal(q + (1 if i < r else 0)) / 100 for i in range(parties)]


def needs_reorder(stock: int, max_stock: int) -> bool:
    return max_stock > 0 and D(stock) <= D(max_stock) * REORDER_FRACTION


def match_outcome(score_for: int, score_against: int) -> str:
    return "W" if score_for > score_against else "L" if score_for < score_against else "D"


def league_points(wins: int, draws: int) -> int:
    """Football convention: 3 for a win, 1 for a draw. Shown as 'Pts' only; other sports may differ."""
    return 3 * wins + draws
