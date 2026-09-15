from __future__ import annotations

from decimal import Decimal

import pytest

from app.controlling import metrics as m

D = Decimal


def test_eac_convention_never_adds_commitments_twice():
    actual, commitments, etc = D(500000), D(400000), D(700000)  # ETC already covers the 400000 commitments
    assert m.eac(actual, etc) == D(1200000)
    assert m.uncommitted_etc(etc, commitments) == D(300000)
    assert m.eac(actual, etc) != actual + commitments + etc


def test_unknown_etc_propagates_unknown_not_zero():
    assert m.eac(D(130000), None) is None
    assert m.uncommitted_etc(None, D(50000)) is None
    assert m.margin(D(400000), None) is None
    assert m.cost_variance_at_completion(None, D(300000)) is None


def test_open_commitment_floors_over_billing():
    assert m.open_commitment(D(150000), D(75000)) == (D(75000), False)
    assert m.open_commitment(D(100000), D(120000)) == (D(0), True)


def test_cost_variance_sign_positive_is_unfavourable():
    assert m.cost_variance_at_completion(D(1764000), D(1600000)) == D(164000)
    assert m.cost_variance_at_completion(D(1500000), D(1600000)) == D(-100000)


def test_ratio_of_sums_and_zero_denominator():
    assert m.ratio_pct(D(236000), D(2000000)) == D("11.80")
    assert m.ratio_pct(D(1), D(0)) is None
    assert m.ratio_pct(None, D(10)) is None
    # portfolio margin % is the ratio of sums, not the average of project ratios
    margins, revenues = [D(10), D(90)], [D(100), D(300)]
    assert m.ratio_pct(sum(margins), sum(revenues)) == D("25.00")
    assert (m.ratio_pct(margins[0], revenues[0]) + m.ratio_pct(margins[1], revenues[1])) / 2 != D("25.00")


@pytest.mark.parametrize(
    ("days", "bucket"),
    [(0, None), (1, "1-30"), (30, "1-30"), (31, "31-90"), (90, "31-90"), (91, "91-180"), (180, "91-180"),
     (181, "181-365"), (365, "181-365"), (366, "above-365")],
)
def test_ageing_boundaries(days, bucket):
    assert m.ageing_bucket(days) == bucket


def test_fixed_project_rate_conversion():
    assert m.to_eur(D(1100000), "USD", D("1.10")) == D("1000000.00")
    assert m.to_eur(D(5), "EUR", None) == D(5)
    assert m.to_eur(D(5), "USD", None) is None


def test_display_format():
    assert m.fmt(D("1.25E+3"), "h") == "1250"
    assert m.fmt(D("2000000.000000")) == "2000000.00"
    assert m.fmt(None) is None
