from dataclasses import dataclass
from typing import Mapping


ALLOWED_SOURCE_RISK_LEVELS = {"low", "low_medium", "medium"}
REQUIRES_ADMIN_APPROVAL = {"low_medium", "medium"}
BLOCKED_SOURCE_RISK_LEVELS = {"high", "not_allowed"}
BLOCKED_CREATOR_STATUSES = {"quarantined", "do_not_contact", "removed", "avoided"}
ALLOWED_COLLECTION_SOURCE_TYPES = {
    "manual",
    "official_api",
    "approved_provider",
    "creator_provided",
}
BLOCKED_COLLECTION_SOURCE_TYPES = {
    "automated_scrape",
    "browser_automation",
    "bulk_scrape",
    "captcha_bypass",
    "login_bypass",
    "public_page_scrape",
    "scraper",
}


class PolicyError(ValueError):
    """Raised when a request violates MVP v0.1 policy."""


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str | None = None
    approval_required: bool = False


def normalize_source_risk(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "low_to_medium": "low_medium",
        "lowmedium": "low_medium",
        "notallowed": "not_allowed",
    }
    return aliases.get(normalized, normalized)


def normalize_source_type(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def is_allowed_source_risk(value: str) -> bool:
    return normalize_source_risk(value) in ALLOWED_SOURCE_RISK_LEVELS


def source_risk_decision(value: str) -> PolicyDecision:
    level = normalize_source_risk(value)
    if level in ALLOWED_SOURCE_RISK_LEVELS:
        return PolicyDecision(
            allowed=True,
            approval_required=level in REQUIRES_ADMIN_APPROVAL,
        )
    if level in BLOCKED_SOURCE_RISK_LEVELS:
        return PolicyDecision(
            allowed=False,
            reason="source_risk_not_allowed",
        )
    return PolicyDecision(
        allowed=False,
        reason="unknown_source_risk_level",
    )


def require_allowed_source_risk(value: str) -> str:
    level = normalize_source_risk(value)
    decision = source_risk_decision(level)
    if not decision.allowed:
        raise PolicyError(decision.reason or "source_risk_not_allowed")
    return level


def require_allowed_collection_source_type(value: str) -> str:
    source_type = normalize_source_type(value)
    if not source_type:
        raise PolicyError("missing_source_type")
    if source_type in BLOCKED_COLLECTION_SOURCE_TYPES:
        raise PolicyError("collection_source_type_not_allowed")
    if source_type not in ALLOWED_COLLECTION_SOURCE_TYPES:
        raise PolicyError("collection_source_type_not_approved")
    return source_type


def requires_admin_approval(value: str) -> bool:
    return normalize_source_risk(value) in REQUIRES_ADMIN_APPROVAL


def import_status_for_creator(source_risk_level: str) -> str:
    level = normalize_source_risk(source_risk_level)
    if level in ALLOWED_SOURCE_RISK_LEVELS:
        return "active"
    if level in BLOCKED_SOURCE_RISK_LEVELS:
        return "quarantined"
    raise PolicyError("unknown_source_risk_level")


def can_generate_dm(creator: Mapping[str, object]) -> PolicyDecision:
    source_risk = normalize_source_risk(str(creator.get("source_risk_level", "")))
    status = str(creator.get("status", "active"))

    if source_risk not in ALLOWED_SOURCE_RISK_LEVELS:
        return PolicyDecision(False, "source_risk_not_allowed")
    if bool(creator.get("do_not_contact", False)):
        return PolicyDecision(False, "do_not_contact")
    if creator.get("removal_requested_at"):
        return PolicyDecision(False, "removal_requested")
    if status in BLOCKED_CREATOR_STATUSES:
        return PolicyDecision(False, f"blocked_creator_status:{status}")
    return PolicyDecision(True)


def require_dm_allowed(creator: Mapping[str, object]) -> None:
    decision = can_generate_dm(creator)
    if not decision.allowed:
        raise PolicyError(decision.reason or "dm_not_allowed")


def can_advance_to_dm_sent(outreach: Mapping[str, object]) -> PolicyDecision:
    if outreach.get("claims_check_status") != "passed":
        return PolicyDecision(False, "claims_check_required")
    if not outreach.get("do_not_contact_checked_at"):
        return PolicyDecision(False, "do_not_contact_check_required")
    return PolicyDecision(True)
