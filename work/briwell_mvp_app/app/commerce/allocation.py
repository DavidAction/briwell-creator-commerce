"""Commission accrual and refund-reversal allocation (audit findings #5, #6).

Pure functions -- no DB access -- so the money math is unit-testable without a
running PostgreSQL instance. app/repositories/commerce.py is responsible for
turning these results into commission_ledger rows.

Commissionable base = subtotal_amount - discount_amount (merchandise net of
discounts; shipping and tax are excluded from the commission base).

Partial-refund reversals use a *cumulative proportional* formula rather than
allocating each refund independently. This avoids rounding drift across many
small refunds on the same order: each reversal is computed as
`target_reversed - already_reversed`, where `target_reversed` is the ideal
(re-rounded) reversal for ALL commissionable refunds seen so far. When the
cumulative refunded amount reaches the commissionable base, `target_reversed`
equals the full accrual, so the final reversal automatically absorbs any
residual rounding -- no separate "last refund" branch is required.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.commerce.money import quantize2


@dataclass(frozen=True)
class AccrualResult:
    amount: Decimal
    currency: str
    fx_rate_usd: Decimal
    commission_rate: Decimal


def compute_accrual(
    commissionable_base: Decimal,
    commission_rate: Decimal,
    currency: str,
    fx_rate_usd: Decimal,
) -> AccrualResult:
    """Compute the commission accrual for a newly attributed order.

    amount = round(commissionable_base * commission_rate, 2)
    """
    amount = quantize2(commissionable_base * commission_rate)
    return AccrualResult(
        amount=amount,
        currency=currency,
        fx_rate_usd=fx_rate_usd,
        commission_rate=commission_rate,
    )


def compute_refund_reversal(
    accrual_amount: Decimal,
    commissionable_base: Decimal,
    cumulative_refunded_before: Decimal,
    refund_commissionable_amount: Decimal,
) -> Decimal:
    """Compute the reversal amount for one refund event on an order.

    Returns a non-positive Decimal. A return value of 0 means: do not write a
    ledger entry for this refund (e.g. the refund covered only shipping/tax,
    which are outside the commissionable base).

    `cumulative_refunded_before` is the sum of commissionable_refund_amount
    across all PRIOR refunds on this order (not including the current one).
    `refund_commissionable_amount` is the commissionable portion of the
    CURRENT refund event.
    """
    if commissionable_base <= 0:
        return Decimal("0.00")

    cumulative_refunded_after = cumulative_refunded_before + refund_commissionable_amount
    # Cannot reverse more than the full commissionable base -- a Shopify
    # refund can never exceed what was actually charged, but this clamp keeps
    # the pure function defensive against bad upstream data.
    cumulative_refunded_after = min(cumulative_refunded_after, commissionable_base)

    already_reversed = quantize2(
        accrual_amount * cumulative_refunded_before / commissionable_base
    ) if cumulative_refunded_before > 0 else Decimal("0.00")

    target_reversed = quantize2(
        accrual_amount * cumulative_refunded_after / commissionable_base
    )

    reversal = -(target_reversed - already_reversed)
    if reversal > 0:
        # Defensive: reversal must never be positive (would mean an accrual).
        return Decimal("0.00")
    return reversal
