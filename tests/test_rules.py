from datetime import date
from decimal import Decimal as D

import pytest

from app import rules


@pytest.mark.parametrize("age,cat", [(12, "Minor"), (17, "Minor"), (18, "Middle"), (25, "Middle"),
                                     (26, "Senior"), (35, "Senior")])
def test_age_category_boundaries(age, cat):
    assert rules.age_category(age) == cat


@pytest.mark.parametrize("age", [11, 36, 0, 80])
def test_age_outside_range_rejected_when_strict(age):
    with pytest.raises(ValueError):
        rules.age_category(age)


def test_age_outside_range_labelled_when_reporting():
    assert rules.age_category(36, strict=False) == "Over-age"
    assert rules.age_category(11, strict=False) == "Under-age"


def test_age_on_birthday_edges():
    assert rules.age_on(date(2000, 10, 12), date(2026, 10, 12)) == 26
    assert rules.age_on(date(2000, 10, 13), date(2026, 10, 12)) == 25


def test_membership_fees():
    assert rules.membership_fee(False) == D("1000.00")
    assert rules.membership_fee(True, 20) == D("10000.00")


def test_discount_only_when_strictly_above_10000():
    assert rules.purchase_totals([(1, D("10000"))]) == (D("10000.00"), D("0.00"), D("10000.00"))
    sub, disc, tot = rules.purchase_totals([(1, D("10000.01"))])
    assert disc == D("500.00") and tot == D("9500.01")
    assert rules.purchase_totals([(5, D("2000")), (3, D("1000"))])[1] == D("650.00")


def test_commission_and_facilitation():
    assert rules.facilitation_total(11) == D("5500.00")
    assert rules.patron_commission(D("5500")) == D("1100.00")


def test_surcharge_is_market_value_plus_ten_percent():
    assert rules.surcharge(D("2000"), 1) == D("2200.00")
    assert rules.surcharge(D("2000"), 3) == D("6600.00")


@pytest.mark.parametrize("amount,n", [(2200, 3), (100, 7), (0.05, 3), (5500, 11)])
def test_split_sums_exactly(amount, n):
    shares = rules.split_evenly(D(str(amount)), n)
    assert sum(shares) == rules.money(amount) and len(shares) == n
    assert max(shares) - min(shares) <= D("0.01")


def test_reorder_boundary_is_inclusive_at_20_percent():
    assert rules.needs_reorder(20, 100) and rules.needs_reorder(0, 100)
    assert not rules.needs_reorder(21, 100)
