from typing import Literal
import unicodedata

from pydantic import BaseModel, Field


ClaimsCheckStatus = Literal["passed", "needs_review", "failed"]


class ClaimsCheckIssue(BaseModel):
    severity: Literal["info", "review", "block"]
    code: str
    matched_text: str
    message: str


class ClaimsCheckInput(BaseModel):
    dm_message: str = Field(min_length=1, max_length=3000)
    product_category: str = Field(min_length=1)
    product_name: str | None = None
    key_claims_allowed: list[str] = Field(default_factory=list, max_length=20)
    claims_disallowed: list[str] = Field(default_factory=list, max_length=20)
    country: Literal["MX", "PE", "EC"] | None = None
    strict_mode: bool = True


class ClaimsCheckResult(BaseModel):
    status: ClaimsCheckStatus
    issues: list[ClaimsCheckIssue] = Field(default_factory=list)
    safe_to_send: bool
    human_review_required: bool
    normalized_message: str
    recommendation: str


BLOCKED_MEDICAL_PATTERNS = {
    "cure": "Medical cure claims are not allowed in MVP DM drafts.",
    "cures": "Medical cure claims are not allowed in MVP DM drafts.",
    "curar": "Medical cure claims are not allowed in MVP DM drafts.",
    "cura": "Medical cure claims are not allowed in MVP DM drafts.",
    "treat acne": "Acne treatment claims are not allowed in MVP DM drafts.",
    "treats acne": "Acne treatment claims are not allowed in MVP DM drafts.",
    "trata acne": "Acne treatment claims are not allowed in MVP DM drafts.",
    "trata el acne": "Acne treatment claims are not allowed in MVP DM drafts.",
    "elimina acne": "Acne elimination claims are not allowed in MVP DM drafts.",
    "elimina el acne": "Acne elimination claims are not allowed in MVP DM drafts.",
    "dermatitis": "Medical skin-condition claims need regulatory review.",
    "eczema": "Medical skin-condition claims need regulatory review.",
    "psoriasis": "Medical skin-condition claims need regulatory review.",
    "rosacea": "Medical skin-condition claims need regulatory review.",
}

BLOCKED_GUARANTEE_PATTERNS = {
    "guaranteed": "Guaranteed-result claims are not allowed.",
    "guarantee": "Guaranteed-result claims are not allowed.",
    "garantizado": "Guaranteed-result claims are not allowed.",
    "garantiza": "Guaranteed-result claims are not allowed.",
    "resultados inmediatos": "Immediate-result claims require review.",
    "instant results": "Immediate-result claims require review.",
    "para siempre": "Permanent-result claims are not allowed.",
    "permanent": "Permanent-result claims are not allowed.",
    "permanente": "Permanent-result claims are not allowed.",
}

REVIEW_PATTERNS = {
    "anti aging": "Anti-aging claims require review.",
    "antiage": "Anti-aging claims require review.",
    "anti edad": "Anti-aging claims require review.",
    "arrugas": "Wrinkle claims require review.",
    "manchas": "Spot or pigmentation claims require review.",
    "blanquea": "Whitening claims require review.",
    "whitening": "Whitening claims require review.",
    "spf": "SPF claims should be checked against product-approved claims.",
}


def run_claims_check(payload: ClaimsCheckInput) -> ClaimsCheckResult:
    normalized = normalize_text(payload.dm_message)
    allowed_claims = [normalize_text(claim) for claim in payload.key_claims_allowed]
    issues: list[ClaimsCheckIssue] = []

    for claim in payload.claims_disallowed:
        normalized_claim = normalize_text(claim)
        if normalized_claim and normalized_claim in normalized:
            issues.append(
                ClaimsCheckIssue(
                    severity="block",
                    code="DISALLOWED_PRODUCT_CLAIM",
                    matched_text=claim,
                    message="The draft contains a product-specific disallowed claim.",
                )
            )

    issues.extend(
        issue_for_patterns(
            normalized=normalized,
            patterns=BLOCKED_MEDICAL_PATTERNS,
            code="MEDICAL_OR_TREATMENT_CLAIM",
            severity="block",
        )
    )
    issues.extend(
        issue_for_patterns(
            normalized=normalized,
            patterns=BLOCKED_GUARANTEE_PATTERNS,
            code="GUARANTEED_OR_PERMANENT_RESULT_CLAIM",
            severity="block",
        )
    )
    issues.extend(
        issue_for_patterns(
            normalized=normalized,
            patterns=REVIEW_PATTERNS,
            code="COSMETIC_CLAIM_REQUIRES_REVIEW",
            severity="review",
            allowed_claims=allowed_claims,
        )
    )

    return result_from_issues(
        issues=dedupe_issues(issues),
        normalized_message=normalized,
        strict_mode=payload.strict_mode,
    )


def issue_for_patterns(
    normalized: str,
    patterns: dict[str, str],
    code: str,
    severity: Literal["review", "block"],
    allowed_claims: list[str] | None = None,
) -> list[ClaimsCheckIssue]:
    issues: list[ClaimsCheckIssue] = []
    allowed_claims = allowed_claims or []
    for pattern, message in patterns.items():
        if pattern not in normalized:
            continue
        if any(pattern in allowed for allowed in allowed_claims):
            continue
        issues.append(
            ClaimsCheckIssue(
                severity=severity,
                code=code,
                matched_text=pattern,
                message=message,
            )
        )
    return issues


def result_from_issues(
    issues: list[ClaimsCheckIssue],
    normalized_message: str,
    strict_mode: bool,
) -> ClaimsCheckResult:
    has_block = any(issue.severity == "block" for issue in issues)
    has_review = any(issue.severity == "review" for issue in issues)
    if has_block:
        status: ClaimsCheckStatus = "failed"
        safe_to_send = False
        human_review_required = True
        recommendation = "Rewrite the draft before human approval."
    elif has_review:
        status = "needs_review"
        safe_to_send = False
        human_review_required = True
        recommendation = "Human review is required for cosmetic claim language."
    elif strict_mode:
        status = "passed"
        safe_to_send = True
        human_review_required = False
        recommendation = "No blocked claims detected. Human approval is still required before sending."
    else:
        status = "passed"
        safe_to_send = True
        human_review_required = False
        recommendation = "No blocked claims detected."

    return ClaimsCheckResult(
        status=status,
        issues=issues,
        safe_to_send=safe_to_send,
        human_review_required=human_review_required,
        normalized_message=normalized_message,
        recommendation=recommendation,
    )


def dedupe_issues(issues: list[ClaimsCheckIssue]) -> list[ClaimsCheckIssue]:
    seen: set[tuple[str, str]] = set()
    deduped: list[ClaimsCheckIssue] = []
    for issue in issues:
        key = (issue.code, issue.matched_text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    normalized = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(normalized.split())
