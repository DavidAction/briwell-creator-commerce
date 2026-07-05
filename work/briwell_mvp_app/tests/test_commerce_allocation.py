from decimal import Decimal

from app.commerce.allocation import compute_accrual, compute_refund_reversal
from app.commerce.money import to_usd


def test_normal_order_accrual() -> None:
    result = compute_accrual(
        commissionable_base=Decimal("1000.00"),
        commission_rate=Decimal("0.15"),
        currency="MXN",
        fx_rate_usd=Decimal("0.054"),
    )
    assert result.amount == Decimal("150.00")
    assert result.currency == "MXN"
    assert to_usd(result.amount, result.fx_rate_usd) == Decimal("8.10")


def test_full_refund_reversal_zeroes_out_usd_balance() -> None:
    base = Decimal("1000.00")
    fx = Decimal("0.054")
    accrual = compute_accrual(base, Decimal("0.15"), "MXN", fx)

    reversal = compute_refund_reversal(
        accrual_amount=accrual.amount,
        commissionable_base=base,
        cumulative_refunded_before=Decimal("0"),
        refund_commissionable_amount=base,
    )

    assert reversal == Decimal("-150.00")
    net_usd = to_usd(accrual.amount, fx) + to_usd(reversal, fx)
    assert net_usd == Decimal("0.00")


def test_partial_refund_cumulative_proportional_rounding() -> None:
    base = Decimal("999.99")
    accrual = compute_accrual(base, Decimal("0.1"), "MXN", Decimal("0.054"))
    assert accrual.amount == Decimal("100.00")

    refunds = [Decimal("333.33"), Decimal("333.33"), Decimal("333.33")]
    cumulative = Decimal("0")
    reversals = []
    for refund in refunds:
        reversal = compute_refund_reversal(
            accrual_amount=accrual.amount,
            commissionable_base=base,
            cumulative_refunded_before=cumulative,
            refund_commissionable_amount=refund,
        )
        reversals.append(reversal)
        cumulative += refund

    assert sum(reversals) == Decimal("-100.00")
    for reversal in reversals:
        # Every step still quantized to cents; no fractional cent drift.
        assert reversal == reversal.quantize(Decimal("0.01"))


def test_shipping_only_refund_produces_no_reversal() -> None:
    base = Decimal("1000.00")
    accrual = compute_accrual(base, Decimal("0.15"), "MXN", Decimal("0.054"))

    reversal = compute_refund_reversal(
        accrual_amount=accrual.amount,
        commissionable_base=base,
        cumulative_refunded_before=Decimal("0"),
        refund_commissionable_amount=Decimal("0"),
    )

    assert reversal == Decimal("0.00")


def test_zero_commissionable_base_is_defensive_no_reversal() -> None:
    reversal = compute_refund_reversal(
        accrual_amount=Decimal("0.00"),
        commissionable_base=Decimal("0"),
        cumulative_refunded_before=Decimal("0"),
        refund_commissionable_amount=Decimal("0"),
    )
    assert reversal == Decimal("0.00")


def test_reversal_never_exceeds_accrual_even_with_over_refund_input() -> None:
    base = Decimal("500.00")
    accrual = compute_accrual(base, Decimal("0.2"), "MXN", Decimal("0.054"))
    assert accrual.amount == Decimal("100.00")

    # Defensive: upstream refund total somehow exceeds the commissionable base.
    reversal = compute_refund_reversal(
        accrual_amount=accrual.amount,
        commissionable_base=base,
        cumulative_refunded_before=Decimal("0"),
        refund_commissionable_amount=Decimal("999.00"),
    )
    assert reversal == Decimal("-100.00")
