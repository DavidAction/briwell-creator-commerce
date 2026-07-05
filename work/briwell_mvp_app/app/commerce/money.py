"""Decimal-only money primitives for the Shopify commerce ledger.

Policy (see db/migrations/008_shopify_commerce_schema.sql and the audit design
for finding #6): all monetary amounts are decimal.Decimal in the order's
presentment currency (MXN / PEN / USD). float is never used for money -- it
introduces representation error that compounds across accrual/reversal
arithmetic and corrupts an append-only ledger. USD is always a derived value:
`amount * fx_rate_usd`, rounded HALF_UP to 2 decimal places.
"""

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")

SUPPORTED_CURRENCIES = {"MXN", "PEN", "USD"}


def quantize2(value: Decimal) -> Decimal:
    """Round a Decimal to 2 decimal places using ROUND_HALF_UP.

    ROUND_HALF_UP (not banker's rounding) matches standard commercial/invoice
    rounding conventions and is what operators and creators expect on a
    payout statement.
    """
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def to_usd(amount: Decimal, fx_rate_usd: Decimal) -> Decimal:
    """Derive the USD value of `amount` units of a currency at `fx_rate_usd`.

    fx_rate_usd is defined as: 1 unit of the source currency = fx_rate_usd USD.
    This mirrors the `total_usd` / `amount_usd` GENERATED ALWAYS columns in
    migration 008, so Python-side previews (validated_not_persisted responses)
    match what the database would compute once persisted.
    """
    return quantize2(amount * fx_rate_usd)
