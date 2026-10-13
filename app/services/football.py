"""Football operations: squads, contracts and wages, injuries, match results and stats.

Players are Members. Wages are the only new money flow: an OUT 'wages' ledger entry per contract per month.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import func, or_, select

from .. import rules
from ..errors import NotFound, PermissionDenied, ValidationError
from ..models import (Contract, Event, EventRoster, Injury, MatchResult, Member, Person, PlayerMatchStat, Sport,
                      Squad, SquadPlayer, User, WagePayment)
from . import audit, auth, ledger

SEASON = re.compile(r"^\d{4}(/\d{2})?$")
PERIOD = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
CONTRACT_TYPES = ("amateur", "youth", "professional")


# ------------------------------------------------------------------ squads
def create_squad(session, sport_id: int, season: str) -> Squad:
    if session.get(Sport, sport_id) is None:
        raise NotFound("Sport not found")
    if not SEASON.match(season or ""):
        raise ValidationError("Season must look like 2026/27 or 2026")
    if session.scalar(select(Squad.id).where(Squad.sport_id == sport_id, Squad.season == season)):
        raise ValidationError("That squad already exists")
    sq = Squad(sport_id=sport_id, season=season)
    session.add(sq)
    session.flush()
    return sq


def add_to_squad(session, squad_id: int, member_id: int, shirt_number: int | None = None, position: str = "",
                 joined_on: date | None = None) -> SquadPlayer:
    if session.get(Squad, squad_id) is None:
        raise NotFound("Squad not found")
    if session.get(Member, member_id) is None:
        raise NotFound("Member not found")
    if session.get(SquadPlayer, (squad_id, member_id)):
        raise ValidationError("Player is already in this squad")
    if shirt_number is not None:
        if not 1 <= shirt_number <= 99:
            raise ValidationError("Shirt number must be 1-99")
        if session.scalar(select(SquadPlayer.member_id).where(SquadPlayer.squad_id == squad_id,
                                                              SquadPlayer.shirt_number == shirt_number)):
            raise ValidationError(f"Shirt {shirt_number} is taken")
    sp = SquadPlayer(squad_id=squad_id, member_id=member_id, shirt_number=shirt_number,
                     position=position or None, joined_on=joined_on or date.today())
    session.add(sp)
    session.flush()
    return sp


def remove_from_squad(session, squad_id: int, member_id: int) -> None:
    sp = session.get(SquadPlayer, (squad_id, member_id))
    if sp is None:
        raise NotFound("Player is not in this squad")
    session.delete(sp)


# ------------------------------------------------------------------ contracts and wages
def _effective_end(c: Contract) -> date:
    return c.terminated_on or c.end_date


def sign_contract(session, member_id: int, sport_id: int, contract_type: str, start: date, end: date,
                  monthly_wage=0, notes: str = "", user_id=None) -> Contract:
    if session.get(Member, member_id) is None:
        raise NotFound("Member not found")
    if session.get(Sport, sport_id) is None:
        raise NotFound("Sport not found")
    if contract_type not in CONTRACT_TYPES:
        raise ValidationError(f"Contract type must be one of {CONTRACT_TYPES}")
    if end <= start:
        raise ValidationError("Contract must end after it starts")
    wage = rules.money(monthly_wage)
    if wage < 0:
        raise ValidationError("Wage cannot be negative")
    if contract_type == "amateur" and wage != 0:
        raise ValidationError("Amateur contracts carry no wage")
    if contract_type == "professional" and wage <= 0:
        raise ValidationError("Professional contracts need a monthly wage")
    for c in session.scalars(select(Contract).where(Contract.member_id == member_id)):
        if c.start_date <= end and _effective_end(c) >= start:
            raise ValidationError(f"Overlaps an existing contract (#{c.id}, {c.start_date} to {_effective_end(c)})")
    c = Contract(member_id=member_id, sport_id=sport_id, contract_type=contract_type, start_date=start,
                 end_date=end, monthly_wage=wage, notes=notes or None)
    session.add(c)
    session.flush()
    audit.log(session, user_id, "contract_signed", f"contract {c.id} member {member_id} {contract_type} {wage}/month")
    return c


def terminate_contract(session, contract_id: int, on: date | None = None, user_id=None) -> Contract:
    c = session.get(Contract, contract_id)
    if c is None:
        raise NotFound("Contract not found")
    on = on or date.today()
    if c.terminated_on:
        raise ValidationError("Contract already terminated")
    if not c.start_date <= on <= c.end_date:
        raise ValidationError("Termination date must fall within the contract period")
    c.terminated_on = on
    audit.log(session, user_id, "contract_terminated", f"contract {contract_id} on {on}")
    return c


def pay_wage(session, contract_id: int, period: str, user_id, paid_on: date | None = None) -> WagePayment:
    """Pay one calendar month (YYYY-MM) of a contract's wage. Needs a signed-in user with finance rights."""
    user = session.get(User, user_id) if user_id else None
    if user is None:
        raise PermissionDenied("A signed-in user is required to pay wages")
    auth.require(user.role, "finance")
    c = session.get(Contract, contract_id)
    if c is None:
        raise NotFound("Contract not found")
    if not PERIOD.match(period or ""):
        raise ValidationError("Period must look like 2026-11")
    if c.monthly_wage <= 0:
        raise ValidationError("This contract carries no wage")
    y, m = (int(x) for x in period.split("-"))
    if not c.start_date.replace(day=1) <= date(y, m, 1) <= _effective_end(c).replace(day=1):
        raise ValidationError("That month is outside the contract period")
    if session.scalar(select(WagePayment.id).where(WagePayment.contract_id == contract_id, WagePayment.period == period)):
        raise ValidationError(f"{period} has already been paid")
    wp = WagePayment(contract_id=contract_id, period=period, amount=c.monthly_wage, paid_on=paid_on or date.today())
    session.add(wp)
    session.flush()
    ledger.post(session, "OUT", "wages", wp.amount, f"Wage {period}, contract #{c.id}", "wage_payment", wp.id,
                entry_date=wp.paid_on, user_id=user_id)
    audit.log(session, user_id, "wage_paid", f"contract {contract_id} {period} {wp.amount}")
    return wp


def expiring_contracts(session, within_days: int = 90, today: date | None = None) -> list[Contract]:
    today = today or date.today()
    limit = today + timedelta(days=within_days)
    return [c for c in session.scalars(select(Contract).where(Contract.terminated_on.is_(None),
                                                              Contract.end_date >= today, Contract.end_date <= limit)
                                       .order_by(Contract.end_date))]


def contract_status(c: Contract, today: date | None = None) -> str:
    today = today or date.today()
    if c.terminated_on and c.terminated_on <= today:
        return "terminated"
    if c.start_date > today:
        return "upcoming"
    return "expired" if c.end_date < today else "active"


# ------------------------------------------------------------------ injuries
def record_injury(session, member_id: int, description: str, injured_on: date, expected_return: date | None = None,
                  today: date | None = None) -> Injury:
    if session.get(Member, member_id) is None:
        raise NotFound("Member not found")
    if not description.strip():
        raise ValidationError("Describe the injury")
    if injured_on > (today or date.today()):
        raise ValidationError("Injury date cannot be in the future")
    if expected_return and expected_return < injured_on:
        raise ValidationError("Expected return cannot be before the injury")
    inj = Injury(member_id=member_id, description=description.strip(), injured_on=injured_on,
                 expected_return=expected_return)
    session.add(inj)
    session.flush()
    return inj


def clear_injury(session, injury_id: int, cleared_on: date | None = None) -> Injury:
    inj = session.get(Injury, injury_id)
    if inj is None:
        raise NotFound("Injury not found")
    if inj.cleared_on:
        raise ValidationError("Injury already cleared")
    cleared_on = cleared_on or date.today()
    if cleared_on < inj.injured_on:
        raise ValidationError("Cannot clear before the injury date")
    inj.cleared_on = cleared_on
    return inj


def is_injured(session, member_id: int, on: date | None = None) -> bool:
    on = on or date.today()
    return session.scalar(select(Injury.id).where(
        Injury.member_id == member_id, Injury.injured_on <= on,
        or_(Injury.cleared_on.is_(None), Injury.cleared_on > on))) is not None


# ------------------------------------------------------------------ results and stats
def record_result(session, event_id: int, score_for: int, score_against: int, stats: list[dict] | None = None,
                  user_id=None, today: date | None = None) -> MatchResult:
    """stats: [{'member_id', 'minutes', 'scored', 'assists', 'yellow_cards', 'red_cards'}] for rostered players."""
    ev = session.get(Event, event_id)
    if ev is None:
        raise NotFound("Event not found")
    if not ev.is_external:
        raise ValidationError("Results are recorded for external fixtures (club vs an opponent)")
    if ev.event_date > (today or date.today()):
        raise ValidationError("Cannot record a result before the match date")
    if session.get(MatchResult, event_id):
        raise ValidationError("A result is already recorded for this event")
    if score_for < 0 or score_against < 0:
        raise ValidationError("Scores cannot be negative")
    roster_ids = set(session.scalars(select(EventRoster.member_id).where(EventRoster.event_id == event_id)))
    seen: set[int] = set()
    rows, total_scored = [], 0
    for st in stats or []:
        mid = st["member_id"]
        if mid not in roster_ids:
            raise ValidationError(f"Member {mid} was not on this event's team")
        if mid in seen:
            raise ValidationError(f"Member {mid} listed twice")
        seen.add(mid)
        minutes, scored, assists = st.get("minutes", 0), st.get("scored", 0), st.get("assists", 0)
        yc, rc = st.get("yellow_cards", 0), st.get("red_cards", 0)
        if not (0 <= minutes <= 240 and scored >= 0 and assists >= 0 and 0 <= yc <= 2 and 0 <= rc <= 1):
            raise ValidationError(f"Invalid stats for member {mid}")
        total_scored += scored
        rows.append(PlayerMatchStat(event_id=event_id, member_id=mid, minutes=minutes, scored=scored,
                                    assists=assists, yellow_cards=yc, red_cards=rc))
    if total_scored > score_for:
        raise ValidationError(f"Players' scoring ({total_scored}) exceeds the team score ({score_for})")
    res = MatchResult(event_id=event_id, score_for=score_for, score_against=score_against)
    session.add(res)
    session.add_all(rows)
    session.flush()
    audit.log(session, user_id, "result_recorded", f"event {event_id} {score_for}-{score_against}")
    return res


def club_record(session, sport_id: int | None = None, start: date | None = None, end: date | None = None) -> dict:
    q = select(MatchResult.score_for, MatchResult.score_against).join(Event, Event.id == MatchResult.event_id)
    if sport_id:
        q = q.where(Event.sport_id == sport_id)
    if start:
        q = q.where(Event.event_date >= start)
    if end:
        q = q.where(Event.event_date <= end)
    w = d = l = gf = ga = 0
    for f, a in session.execute(q):
        o = rules.match_outcome(f, a)
        w, d, l = w + (o == "W"), d + (o == "D"), l + (o == "L")
        gf, ga = gf + f, ga + a
    return {"played": w + d + l, "won": w, "drawn": d, "lost": l, "for": gf, "against": ga, "diff": gf - ga,
            "points": rules.league_points(w, d)}


def top_scorers(session, sport_id: int | None = None, limit: int = 10) -> list[tuple]:
    q = (select(Person.id, Person.full_name, func.sum(PlayerMatchStat.scored), func.sum(PlayerMatchStat.assists),
                func.count(), func.sum(PlayerMatchStat.minutes))
         .join(PlayerMatchStat, PlayerMatchStat.member_id == Person.id)
         .join(Event, Event.id == PlayerMatchStat.event_id)
         .group_by(Person.id, Person.full_name)
         .order_by(func.sum(PlayerMatchStat.scored).desc(), func.sum(PlayerMatchStat.assists).desc(), Person.full_name))
    if sport_id:
        q = q.where(Event.sport_id == sport_id)
    return [(i, n, int(s), int(a), int(c), int(m)) for i, n, s, a, c, m in session.execute(q.limit(limit))]
