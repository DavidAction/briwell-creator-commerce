"""Dual discount-code + UTM-link creator attribution (audit finding #7).

Discount codes are the primary signal (an active, deliberate checkout-time
input), UTM link clicks are the secondary signal (a last-click session marker
that is more easily polluted by link re-sharing in LATAM WhatsApp groups).

Pure decision function -- no DB access -- so the priority table can be unit
tested without a running PostgreSQL instance. app/repositories/commerce.py
and app/routers/commerce.py turn this decision into an order_attribution row
(and, when `should_accrue` is True, a commission_ledger accrual entry).

Decision table (see design doc section 4):
  1. exactly one code match, no UTM match (or UTM points at the SAME creator)
     -> discount_code / high / active / should_accrue=True
  2. no code match, one UTM match
     -> utm_link / medium / active / should_accrue=True
  3. exactly one code match, UTM points at a DIFFERENT creator
     -> discount_code / medium / needs_review / conflict_kind=code_vs_utm / should_accrue=False
  4. two or more code matches for DIFFERENT creators
     -> discount_code / low / needs_review / conflict_kind=multi_code / should_accrue=False
  5. no code match, no UTM match
     -> no attribution decision (caller should not create a row)
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CodeMatch:
    id: str
    creator_id: str
    commission_rate: str  # kept as str/Decimal-compatible; caller controls type


@dataclass(frozen=True)
class UtmMatch:
    id: str
    creator_id: str
    commission_rate: str


@dataclass(frozen=True)
class AttributionDecision:
    creator_id: str | None
    method: Literal["discount_code", "utm_link", "manual"] | None
    confidence: Literal["high", "medium", "low"] | None
    status: Literal["active", "needs_review"] | None
    conflict_kind: Literal["code_vs_utm", "multi_code"] | None
    matched_discount_code_id: str | None
    matched_utm_link_id: str | None
    competing_creator_id: str | None
    commission_rate: str | None
    should_accrue: bool


_NO_ATTRIBUTION = AttributionDecision(
    creator_id=None,
    method=None,
    confidence=None,
    status=None,
    conflict_kind=None,
    matched_discount_code_id=None,
    matched_utm_link_id=None,
    competing_creator_id=None,
    commission_rate=None,
    should_accrue=False,
)


def decide_attribution(
    code_matches: Sequence[CodeMatch],
    utm_match: UtmMatch | None,
) -> AttributionDecision:
    distinct_code_creators = {match.creator_id for match in code_matches}

    if len(distinct_code_creators) >= 2:
        # Rule 4: multiple codes for different creators on the same order.
        # Deterministic pick: the first matched code, flagged for review.
        first = code_matches[0]
        return AttributionDecision(
            creator_id=first.creator_id,
            method="discount_code",
            confidence="low",
            status="needs_review",
            conflict_kind="multi_code",
            matched_discount_code_id=first.id,
            matched_utm_link_id=utm_match.id if utm_match else None,
            competing_creator_id=None,
            commission_rate=first.commission_rate,
            should_accrue=False,
        )

    if len(distinct_code_creators) == 1:
        code_match = code_matches[0]
        if utm_match is not None and utm_match.creator_id != code_match.creator_id:
            # Rule 3: single code creator vs. a different UTM creator -- conflict.
            return AttributionDecision(
                creator_id=code_match.creator_id,
                method="discount_code",
                confidence="medium",
                status="needs_review",
                conflict_kind="code_vs_utm",
                matched_discount_code_id=code_match.id,
                matched_utm_link_id=utm_match.id,
                competing_creator_id=utm_match.creator_id,
                commission_rate=code_match.commission_rate,
                should_accrue=False,
            )
        # Rule 1: single code creator, no UTM or UTM agrees.
        return AttributionDecision(
            creator_id=code_match.creator_id,
            method="discount_code",
            confidence="high",
            status="active",
            conflict_kind=None,
            matched_discount_code_id=code_match.id,
            matched_utm_link_id=utm_match.id if utm_match else None,
            competing_creator_id=None,
            commission_rate=code_match.commission_rate,
            should_accrue=True,
        )

    if utm_match is not None:
        # Rule 2: UTM-only attribution. Accrue immediately (medium confidence)
        # -- this is the fix for LATAM creator under-crediting (finding #7).
        return AttributionDecision(
            creator_id=utm_match.creator_id,
            method="utm_link",
            confidence="medium",
            status="active",
            conflict_kind=None,
            matched_discount_code_id=None,
            matched_utm_link_id=utm_match.id,
            competing_creator_id=None,
            commission_rate=utm_match.commission_rate,
            should_accrue=True,
        )

    # Rule 5: no signal at all.
    return _NO_ATTRIBUTION
