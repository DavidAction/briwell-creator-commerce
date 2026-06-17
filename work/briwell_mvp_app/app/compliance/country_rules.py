from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field


Country = Literal["MX", "PE", "EC"]
ProductCategory = Literal[
    "sunscreen",
    "calming_serum",
    "cleanser",
    "sheet_mask",
    "cushion_foundation",
]
RuleType = Literal["allowed_claim", "review_claim", "blocked_claim", "disclosure"]
Severity = Literal["low", "medium", "high"]


class ComplianceRule(BaseModel):
    country: Country
    product_category: ProductCategory
    rule_type: RuleType
    phrase: str
    severity: Severity
    notes: str
    legal_review_required: bool = True


class CountryClaimsInput(BaseModel):
    country: Country
    product_category: ProductCategory
    message: str = Field(min_length=1, max_length=3000)


class CountryClaimsIssue(BaseModel):
    code: str
    phrase: str
    severity: Severity
    notes: str


class CountryClaimsResult(BaseModel):
    status: Literal["passed", "needs_review", "failed"]
    issues: list[CountryClaimsIssue]
    matched_rules: list[ComplianceRule]
    legal_review_required: bool


BUILT_IN_RULES: list[ComplianceRule] = [
    ComplianceRule(country="MX", product_category="sunscreen", rule_type="review_claim", phrase="spf", severity="medium", notes="SPF claims require product-label and local-market review."),
    ComplianceRule(country="PE", product_category="sunscreen", rule_type="review_claim", phrase="proteccion solar", severity="medium", notes="Sun protection claims require product support."),
    ComplianceRule(country="EC", product_category="sunscreen", rule_type="review_claim", phrase="bloqueador", severity="medium", notes="Sun protection wording requires label consistency."),
    ComplianceRule(country="MX", product_category="calming_serum", rule_type="blocked_claim", phrase="cura acne", severity="high", notes="Treatment claims are blocked for cosmetic outreach."),
    ComplianceRule(country="PE", product_category="calming_serum", rule_type="blocked_claim", phrase="trata dermatitis", severity="high", notes="Medical skin-condition claims are blocked."),
    ComplianceRule(country="EC", product_category="calming_serum", rule_type="blocked_claim", phrase="elimina rosacea", severity="high", notes="Medical skin-condition claims are blocked."),
    ComplianceRule(country="MX", product_category="cleanser", rule_type="review_claim", phrase="piel acneica", severity="medium", notes="Acne-prone language should avoid treatment claims."),
    ComplianceRule(country="PE", product_category="sheet_mask", rule_type="review_claim", phrase="anti edad", severity="medium", notes="Anti-aging language needs review."),
    ComplianceRule(country="EC", product_category="cushion_foundation", rule_type="review_claim", phrase="manchas", severity="medium", notes="Spot and pigmentation language needs review."),
    ComplianceRule(country="MX", product_category="sunscreen", rule_type="disclosure", phrase="colaboracion pagada", severity="low", notes="Paid collaboration disclosure should be clear."),
    ComplianceRule(country="PE", product_category="sunscreen", rule_type="disclosure", phrase="colaboracion pagada", severity="low", notes="Paid collaboration disclosure should be clear."),
    ComplianceRule(country="EC", product_category="sunscreen", rule_type="disclosure", phrase="colaboracion pagada", severity="low", notes="Paid collaboration disclosure should be clear."),
]


def list_country_rules(
    country: Country | None = None,
    product_category: ProductCategory | None = None,
) -> list[ComplianceRule]:
    return [
        rule
        for rule in BUILT_IN_RULES
        if (country is None or rule.country == country)
        and (product_category is None or rule.product_category == product_category)
    ]


def evaluate_country_claims(payload: CountryClaimsInput) -> CountryClaimsResult:
    normalized = normalize_text(payload.message)
    matched_rules: list[ComplianceRule] = []
    issues: list[CountryClaimsIssue] = []

    for rule in list_country_rules(payload.country, payload.product_category):
        if rule.rule_type == "disclosure":
            continue
        if re.search(rf"\b{re.escape(normalize_text(rule.phrase))}\b", normalized):
            matched_rules.append(rule)
            issues.append(
                CountryClaimsIssue(
                    code=rule.rule_type.upper(),
                    phrase=rule.phrase,
                    severity=rule.severity,
                    notes=rule.notes,
                )
            )

    if any(issue.severity == "high" for issue in issues):
        status: Literal["passed", "needs_review", "failed"] = "failed"
    elif issues:
        status = "needs_review"
    else:
        status = "passed"

    return CountryClaimsResult(
        status=status,
        issues=issues,
        matched_rules=matched_rules,
        legal_review_required=status != "passed",
    )


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_marks).strip()
