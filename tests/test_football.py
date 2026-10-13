from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy import select

from app import rules
from app.errors import PermissionDenied, ValidationError
from app.models import Sport
from app.services import auth, events, football, ledger, reports
from tests.test_services import external_event

TODAY = date(2026, 12, 1)


def sport(session, name="Football"):
    return session.scalar(select(Sport).where(Sport.name == name))


# ------------------------------------------------------------ rules
def test_match_outcome_and_points():
    assert [rules.match_outcome(2, 1), rules.match_outcome(1, 1), rules.match_outcome(0, 3)] == ["W", "D", "L"]
    assert rules.league_points(3, 2) == 11


# ------------------------------------------------------------ squads
def test_squad_rules(session, make_member):
    fb = sport(session)
    sq = football.create_squad(session, fb.id, "2026/27")
    with pytest.raises(ValidationError):
        football.create_squad(session, fb.id, "2026/27")           # duplicate
    with pytest.raises(ValidationError):
        football.create_squad(session, fb.id, "next year")         # bad season
    a, b = make_member(), make_member()
    football.add_to_squad(session, sq.id, a.person_id, 9, "Forward")
    with pytest.raises(ValidationError):
        football.add_to_squad(session, sq.id, a.person_id, 10)     # already in squad
    with pytest.raises(ValidationError):
        football.add_to_squad(session, sq.id, b.person_id, 9)      # shirt taken
    with pytest.raises(ValidationError):
        football.add_to_squad(session, sq.id, b.person_id, 100)    # shirt out of range
    football.add_to_squad(session, sq.id, b.person_id)             # no shirt is fine
    assert len(reports.squad_register(session).rows) == 2


# ------------------------------------------------------------ contracts and wages
def test_contract_validation_and_overlap(session, make_member):
    m, fb = make_member(), sport(session)
    s, e = date(2026, 11, 1), date(2027, 10, 31)
    with pytest.raises(ValidationError):
        football.sign_contract(session, m.person_id, fb.id, "amateur", e, s)                   # ends before start
    with pytest.raises(ValidationError):
        football.sign_contract(session, m.person_id, fb.id, "amateur", s, e, monthly_wage=500)  # amateur wage
    with pytest.raises(ValidationError):
        football.sign_contract(session, m.person_id, fb.id, "professional", s, e, 0)            # pro needs wage
    c = football.sign_contract(session, m.person_id, fb.id, "professional", s, e, 30000)
    with pytest.raises(ValidationError):                                                         # overlap
        football.sign_contract(session, m.person_id, fb.id, "youth", date(2027, 6, 1), date(2028, 6, 1))
    football.terminate_contract(session, c.id, date(2027, 1, 31))
    football.sign_contract(session, m.person_id, fb.id, "youth", date(2027, 2, 1), date(2028, 1, 31))  # frees the slot
    assert football.contract_status(c, TODAY) == "active"                   # termination not yet effective
    assert football.contract_status(c, date(2027, 3, 1)) == "terminated"


def test_wage_payment_permissions_period_and_ledger(session, make_member):
    m, fb = make_member(), sport(session)
    c = football.sign_contract(session, m.person_id, fb.id, "professional", date(2026, 11, 1), date(2027, 1, 31), 30000)
    clerk = auth.create_user(session, "clerk", "password123", "clerk")
    boss = auth.create_user(session, "manager1", "password123", "manager")
    with pytest.raises(PermissionDenied):
        football.pay_wage(session, c.id, "2026-11", clerk.id)
    with pytest.raises(PermissionDenied):
        football.pay_wage(session, c.id, "2026-11", None)
    with pytest.raises(ValidationError):
        football.pay_wage(session, c.id, "2026-10", boss.id)       # before contract
    with pytest.raises(ValidationError):
        football.pay_wage(session, c.id, "2026-13", boss.id)       # bad period
    football.pay_wage(session, c.id, "2026-11", boss.id)
    with pytest.raises(ValidationError):
        football.pay_wage(session, c.id, "2026-11", boss.id)       # paid once only
    s = ledger.summary(session)
    assert s["expenses"]["wages"] == D("30000.00")
    assert s["net_income"] == s["gross_income"] - D("30000.00")
    assert reports.wages_paid(session).rows[0][3] == D("30000.00")


def test_expiring_contracts(session, make_member):
    fb = sport(session)
    soon, later = make_member(), make_member()
    football.sign_contract(session, soon.person_id, fb.id, "amateur", date(2026, 1, 1), date(2026, 12, 20))
    football.sign_contract(session, later.person_id, fb.id, "amateur", date(2026, 1, 1), date(2027, 12, 20))
    assert [c.member_id for c in football.expiring_contracts(session, 90, TODAY)] == [soon.person_id]


# ------------------------------------------------------------ injuries
def test_injured_player_cannot_be_selected_until_cleared(session, make_member):
    fb = sport(session)
    a, b = make_member(), make_member()
    inj = football.record_injury(session, a.person_id, "hamstring", date(2026, 10, 1), today=date(2026, 10, 12))
    ev = events.create_event(session, fb.id, "Cup tie", date(2026, 11, 5), opponent="X FC")
    assert football.is_injured(session, a.person_id, date(2026, 11, 5))
    with pytest.raises(ValidationError, match="injured"):
        events.set_roster(session, ev.id, [a.person_id, b.person_id], b.person_id)
    football.clear_injury(session, inj.id, date(2026, 10, 25))
    events.set_roster(session, ev.id, [a.person_id, b.person_id], b.person_id)
    with pytest.raises(ValidationError):
        football.record_injury(session, a.person_id, "x", date(2027, 1, 1), today=date(2026, 10, 12))


# ------------------------------------------------------------ results
def test_result_rules(session, make_member):
    ev, team = external_event(session, make_member, n=3)         # fixture date 2026-11-01
    with pytest.raises(ValidationError):
        football.record_result(session, ev.id, 2, 1, today=date(2026, 10, 30))          # before match date
    with pytest.raises(ValidationError):
        football.record_result(session, ev.id, 1, 0, [{"member_id": team[0], "scored": 2}], today=TODAY)  # too many goals
    with pytest.raises(ValidationError):
        football.record_result(session, ev.id, 1, 0, [{"member_id": 99999, "scored": 1}], today=TODAY)   # not on team
    with pytest.raises(ValidationError):
        football.record_result(session, ev.id, 1, 0, [{"member_id": team[0], "yellow_cards": 3}], today=TODAY)
    football.record_result(session, ev.id, 2, 1, [{"member_id": team[0], "minutes": 90, "scored": 2},
                                                  {"member_id": team[1], "minutes": 80, "assists": 1}], today=TODAY)
    with pytest.raises(ValidationError):
        football.record_result(session, ev.id, 2, 1, today=TODAY)                       # only once


def test_internal_event_has_no_result(session, make_member):
    fb = sport(session)
    a = make_member()
    ev = events.create_event(session, fb.id, "Inter-house", date(2026, 11, 2))
    with pytest.raises(ValidationError):
        football.record_result(session, ev.id, 1, 0, today=TODAY)


def test_club_record_and_top_scorers(session, make_member):
    fb = sport(session)
    team = [make_member().person_id for _ in range(2)]
    scores = [(3, 0), (1, 1), (0, 2)]
    for i, (f, a) in enumerate(scores):
        ev = events.create_event(session, fb.id, f"Match {i}", date(2026, 11, 1 + i), opponent=f"Team {i}")
        events.set_roster(session, ev.id, team, team[0])
        football.record_result(session, ev.id, f, a, [{"member_id": team[0], "minutes": 90, "scored": f}], today=TODAY)
    r = football.club_record(session, fb.id)
    assert (r["played"], r["won"], r["drawn"], r["lost"], r["for"], r["against"], r["diff"], r["points"]) == (3, 1, 1, 1, 4, 3, 1, 4)
    top = football.top_scorers(session)
    assert top[0][0] == team[0] and top[0][2] == 4 and top[0][4] == 3
    assert football.club_record(session, sport(session, "Rugby").id)["played"] == 0
    assert reports.club_record_by_game(session).rows[0][8] == 4
