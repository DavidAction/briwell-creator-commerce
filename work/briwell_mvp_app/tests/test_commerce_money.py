from decimal import Decimal

from app.commerce.money import quantize2, to_usd


def test_quantize2_half_up_rounds_up_at_boundary() -> None:
    assert quantize2(Decimal("0.005")) == Decimal("0.01")
    assert quantize2(Decimal("1.005")) == Decimal("1.01")


def test_quantize2_rounds_down_below_half() -> None:
    assert quantize2(Decimal("0.004")) == Decimal("0.00")


def test_quantize2_already_two_decimals_unchanged() -> None:
    assert quantize2(Decimal("42.10")) == Decimal("42.10")


def test_to_usd_applies_fx_rate_and_rounds() -> None:
    assert to_usd(Decimal("150.00"), Decimal("0.054")) == Decimal("8.10")


def test_to_usd_usd_currency_identity_rate() -> None:
    assert to_usd(Decimal("42.00"), Decimal("1")) == Decimal("42.00")


def test_to_usd_boundary_rounding() -> None:
    # 1.005 exactly at the half-up boundary after multiplication.
    assert to_usd(Decimal("100.50"), Decimal("0.01")) == Decimal("1.01")
