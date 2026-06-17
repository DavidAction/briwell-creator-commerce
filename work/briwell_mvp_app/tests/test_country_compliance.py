from app.compliance.country_rules import CountryClaimsInput
from app.compliance.country_rules import evaluate_country_claims
from app.compliance.country_rules import list_country_rules


def test_country_rules_filter_by_country_and_product() -> None:
    rules = list_country_rules(country="MX", product_category="sunscreen")

    assert rules
    assert all(rule.country == "MX" for rule in rules)
    assert all(rule.product_category == "sunscreen" for rule in rules)


def test_country_claims_review_sunscreen_spf() -> None:
    result = evaluate_country_claims(
        CountryClaimsInput(
            country="MX",
            product_category="sunscreen",
            message="Este SPF es ideal para una rutina diaria.",
        )
    )

    assert result.status == "needs_review"
    assert result.legal_review_required is True


def test_country_claims_block_medical_claim() -> None:
    result = evaluate_country_claims(
        CountryClaimsInput(
            country="MX",
            product_category="calming_serum",
            message="Este serum cura acne.",
        )
    )

    assert result.status == "failed"
    assert any(issue.severity == "high" for issue in result.issues)
