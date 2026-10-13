from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy import select

from app import rules
from app.errors import ClubError, StockError, ValidationError
from app.models import Equipment, Item, LedgerEntry, Person, Sport, StockMovement
from app.services import auth, commercial, equipment, events, ledger, membership, reports, store


def item(session, name):
    return session.scalar(select(Item).where(Item.name == name))


# ------------------------------------------------------------ membership
def test_individual_member_pays_1000_and_hits_ledger(session, make_member):
    m = make_member()
    assert m.fee_charged == D("1000.00")
    assert ledger.summary(session)["income"]["membership"] == D("1000.00")
    assert membership.member_category(m, date(2026, 10, 12)) == "Middle"


@pytest.mark.parametrize("dob", [date(2015, 1, 1), date(1980, 1, 1)])
def test_enrolment_rejects_out_of_range_ages(session, make_member, dob):
    with pytest.raises(ValidationError):
        make_member(date_of_birth=dob)


def test_rejects_bad_phone_duplicate_games_and_no_games(session, make_member):
    for bad in ({"phone": "abc"}, {"games": ["Chess", "Chess"]}, {"games": []}, {"games": ["Curling"]}):
        with pytest.raises(ClubError):
            make_member(**bad)


def test_group_members_pay_500_each_all_or_nothing(session, make_member):
    base = dict(gender="Female", date_of_birth=date(2008, 3, 3), phone="0712345678", next_of_kin_name="P",
                next_of_kin_contact="0722345678", games=["Netball"], on=date(2026, 10, 12))
    g, ms = membership.register_group(session, "Mavumbi High", "School",
                                      [dict(base, full_name="A"), dict(base, full_name="B")])
    assert [m.fee_charged for m in ms] == [D("500.00")] * 2
    assert ledger.summary(session)["income"]["membership"] == D("1000.00")
    before = session.scalar(select(Person.id).order_by(Person.id.desc()))
    with pytest.raises(ClubError):  # 2nd member invalid -> whole group rolled back
        membership.register_group(session, "Bad School", "School",
                                  [dict(base, full_name="C"), dict(base, full_name="D", phone="x")])
    assert session.scalar(select(Person.id).order_by(Person.id.desc())) == before
    assert ledger.summary(session)["income"]["membership"] == D("1000.00")


# ------------------------------------------------------------ store
def test_sale_decrements_stock_logs_movement_and_posts_ledger(session, make_member):
    m = make_member()
    shorts = item(session, "Games shorts")
    r = store.sell(session, [{"item_id": shorts.id, "qty": 4}], "cash", person_id=m.person_id)
    assert r.sale.total == D("3000.00") and shorts.stock_qty == 96
    mv = session.scalars(select(StockMovement).where(StockMovement.item_id == shorts.id)
                         .order_by(StockMovement.id.desc())).first()
    assert (mv.change, mv.resulting_qty, mv.reason) == (-4, 96, "sale")
    assert ledger.summary(session)["income"]["store_sale"] == D("3000.00")


def test_discount_applies_above_10000_in_a_real_sale(session, make_member):
    m = make_member()
    stick = item(session, "Hockey stick")  # 2000 each
    r = store.sell(session, [{"item_id": stick.id, "qty": 6}], "cash", person_id=m.person_id)
    assert (r.sale.subtotal, r.sale.discount, r.sale.total) == (D("12000.00"), D("600.00"), D("11400.00"))


def test_insufficient_stock_blocks_sale_and_changes_nothing(session, make_member):
    m = make_member()
    socks = item(session, "Socks")
    with pytest.raises(StockError):
        store.sell(session, [{"item_id": socks.id, "qty": 151}], "cash", person_id=m.person_id)
    assert socks.stock_qty == 150 and ledger.summary(session)["gross_income"] == D("1000.00")


def test_low_stock_alert_fires_at_20_percent(session, make_member):
    m = make_member()
    wrapper = item(session, "Wrapper")  # max 100
    assert store.sell(session, [{"item_id": wrapper.id, "qty": 79}], "cash", person_id=m.person_id).alerts == []
    res = store.sell(session, [{"item_id": wrapper.id, "qty": 1}], "cash", person_id=m.person_id)
    assert [i.name for i in res.alerts] == ["Wrapper"] and wrapper.stock_qty == 20
    assert wrapper in store.low_stock(session)


def test_variable_shoe_price_enforced(session, make_member):
    m = make_member()
    shoes = item(session, "Sports shoes")
    for bad in (500, 4500):
        with pytest.raises(ValidationError):
            store.sell(session, [{"item_id": shoes.id, "qty": 1, "unit_price": bad}], "cash", person_id=m.person_id)
    r = store.sell(session, [{"item_id": shoes.id, "qty": 1, "unit_price": 3200}], "cash", person_id=m.person_id)
    assert r.sale.total == D("3200.00")


def test_sale_rules_payment_channel_and_member_requirement(session, make_member):
    m = make_member()
    shorts, jersey = item(session, "Games shorts"), item(session, "Club jersey")
    with pytest.raises(ValidationError):   # mobile money needs a reference
        store.sell(session, [{"item_id": shorts.id, "qty": 1}], "mobile_money", person_id=m.person_id)
    with pytest.raises(ValidationError):   # member channel needs a member
        store.sell(session, [{"item_id": shorts.id, "qty": 1}], "cash")
    with pytest.raises(ValidationError):   # wrong channel for item
        store.sell(session, [{"item_id": jersey.id, "qty": 1}], "cash", person_id=m.person_id)
    r = store.sell(session, [{"item_id": jersey.id, "qty": 2}], "mobile_money", channel="fan", payment_ref="QJK123")
    assert r.sale.total == D("7000.00") and ledger.summary(session)["income"]["merchandise"] == D("7000.00")


def test_restock_cannot_exceed_max(session):
    socks = item(session, "Socks")
    with pytest.raises(ValidationError):
        store.restock(session, socks.id, 1)


# ------------------------------------------------------------ events, facilitation, commission
def external_event(session, make_member, n=3):
    football = session.scalar(select(Sport).where(Sport.name == "Football"))
    patron = make_member(full_name="Patron Pat")
    membership.assign_role(session, patron.person_id, "Patron", football.id)
    team = [make_member().person_id for _ in range(n)]
    ev = events.create_event(session, football.id, "Friendly vs Kisumu", date(2026, 11, 1), opponent="Kisumu FC",
                             ticket_price=200)
    events.set_roster(session, ev.id, team, captain_id=team[0])
    return ev, team


def test_facilitation_and_patron_commission(session, make_member):
    ev, team = external_event(session, make_member, n=4)
    for mid in team:
        events.collect_facilitation(session, ev.id, mid, user_id=None)
    s = ledger.summary(session)
    assert s["income"]["facilitation"] == D("2000.00")
    events.settle_event(session, ev.id)
    s = ledger.summary(session)
    assert s["expenses"]["patron_commission"] == D("400.00")  # 20% of 2000
    assert s["net_income"] == s["gross_income"] - D("400.00")
    with pytest.raises(ValidationError):  # idempotent: cannot pay commission twice
        events.settle_event(session, ev.id)


def test_internal_event_charges_no_facilitation(session, make_member):
    football = session.scalar(select(Sport).where(Sport.name == "Football"))
    a, b = make_member().person_id, make_member().person_id
    ev = events.create_event(session, football.id, "Inter-house", date(2026, 11, 2))
    events.set_roster(session, ev.id, [a, b], a)
    with pytest.raises(ValidationError):
        events.collect_facilitation(session, ev.id, a)


def test_fee_cannot_be_collected_twice_and_roster_locks(session, make_member):
    ev, team = external_event(session, make_member)
    events.collect_facilitation(session, ev.id, team[1])
    with pytest.raises(ValidationError):
        events.collect_facilitation(session, ev.id, team[1])
    with pytest.raises(ValidationError):
        events.set_roster(session, ev.id, team[:2], team[0])


def test_captain_must_be_on_team(session, make_member):
    football = session.scalar(select(Sport).where(Sport.name == "Football"))
    a, b = make_member().person_id, make_member().person_id
    ev = events.create_event(session, football.id, "X", date(2026, 11, 3))
    with pytest.raises(ValidationError):
        events.set_roster(session, ev.id, [a], b)


def test_ticket_sales_hit_ledger(session, make_member):
    ev, _ = external_event(session, make_member)
    events.sell_tickets(session, ev.id, 50)
    assert ledger.summary(session)["income"]["ticket"] == D("10000.00")


# ------------------------------------------------------------ equipment and surcharge
def test_loss_surcharge_split_across_team_and_booked_on_payment(session, make_member):
    ev, team = external_event(session, make_member, n=3)
    stick = session.scalar(select(Equipment).where(Equipment.name == "Football (match)"))  # 3000 sample value
    iss = equipment.issue(session, ev.id, team[0], [(stick.id, 2)])
    assert stick.qty_available == 8
    with pytest.raises(ValidationError):  # non-captain cannot collect
        equipment.issue(session, ev.id, team[1], [(stick.id, 1)])
    line = iss.lines[0]
    sur = equipment.return_issue(session, iss.id, {line.id: (1, 0)})
    assert sum(s.amount for s in sur) == D("3300.00")          # 3000 + 10%
    assert sur[0].member_id == team[0] and len(sur) == 3        # captain first, whole team shares
    assert (stick.qty_total, stick.qty_available) == (9, 9)     # 1 lost written off, 1 returned
    assert ledger.summary(session)["income"]["surcharge"] == D("0.00")   # not income until paid
    for s in sur:
        equipment.pay_surcharge(session, s.id)
    assert ledger.summary(session)["income"]["surcharge"] == D("3300.00")
    with pytest.raises(ValidationError):
        equipment.return_issue(session, iss.id)


def test_cannot_issue_more_than_available(session, make_member):
    ev, team = external_event(session, make_member)
    eq = session.scalar(select(Equipment).where(Equipment.name == "Football (match)"))
    with pytest.raises(StockError):
        equipment.issue(session, ev.id, team[0], [(eq.id, 11)])


# ------------------------------------------------------------ ledger, sponsors, auth, reports
def test_sponsorship_income_and_reversal(session):
    sp = commercial.add_sponsor(session, "Kenya Sports Co")
    commercial.record_sponsorship(session, sp.id, 50000, purpose="Kit")
    assert ledger.summary(session)["income"]["sponsorship"] == D("50000.00")
    entry = session.scalar(select(LedgerEntry).where(LedgerEntry.category == "sponsorship"))
    ledger.reverse(session, entry.id, reason="bounced cheque")
    assert ledger.summary(session)["income"]["sponsorship"] == D("0.00")
    with pytest.raises(ValidationError):
        ledger.reverse(session, entry.id)


def test_ledger_rejects_nonsense_entries(session):
    with pytest.raises(ValidationError):
        ledger.post(session, "OUT", "membership", 10)
    with pytest.raises(ValidationError):
        ledger.post(session, "IN", "membership", 0)


def test_auth_hashing_roles_and_failed_login(session):
    auth.create_user(session, "clerk1", "s3cretpass!", "clerk")
    assert auth.authenticate(session, "clerk1", "s3cretpass!").role == "clerk"
    assert auth.authenticate(session, "clerk1", "wrong") is None
    assert auth.authenticate(session, "nobody", "x") is None
    assert auth.can("clerk", "store") and not auth.can("clerk", "finance")
    with pytest.raises(ValidationError):
        auth.create_user(session, "short", "abc", "clerk")


def test_every_report_runs_and_exports(session, make_member, tmp_path):
    ev, team = external_event(session, make_member)
    events.collect_facilitation(session, ev.id, team[0])
    store.sell(session, [{"item_id": item(session, "Socks").id, "qty": 2}], "cash", person_id=team[0])
    for name, fn in reports.REGISTRY.items():
        rep = fn(session)
        assert rep.headers and all(len(r) == len(rep.headers) for r in rep.rows), name
        reports.export_csv(rep, str(tmp_path / "r.csv"))
        reports.export_xlsx(rep, str(tmp_path / "r.xlsx"))
    inc = reports.income_summary(session)
    assert ["GROSS INCOME", ledger.summary(session)["gross_income"]] in inc.rows
