from app.compliance.claims import ClaimsCheckInput, run_claims_check


def test_claims_check_passes_safe_collaboration_draft() -> None:
    result = run_claims_check(
        ClaimsCheckInput(
            dm_message=(
                "Hola Creator, somos Briwell. Queremos compartir detalles de una "
                "colaboracion de K-beauty para una resena honesta."
            ),
            product_category="sunscreen",
        )
    )

    assert result.status == "passed"
    assert result.safe_to_send is True
    assert result.issues == []


def test_claims_check_fails_disallowed_product_claim() -> None:
    result = run_claims_check(
        ClaimsCheckInput(
            dm_message="Este producto cures acne rapido.",
            product_category="calming_serum",
            claims_disallowed=["cures acne"],
        )
    )

    assert result.status == "failed"
    assert result.safe_to_send is False
    assert {issue.code for issue in result.issues} >= {
        "DISALLOWED_PRODUCT_CLAIM",
        "MEDICAL_OR_TREATMENT_CLAIM",
    }


def test_claims_check_flags_cosmetic_claim_for_review() -> None:
    result = run_claims_check(
        ClaimsCheckInput(
            dm_message="Este serum ayuda con manchas y arrugas.",
            product_category="calming_serum",
        )
    )

    assert result.status == "needs_review"
    assert result.safe_to_send is False
    assert result.human_review_required is True
    assert {issue.matched_text for issue in result.issues} == {"arrugas", "manchas"}


def test_claims_check_allows_review_pattern_when_product_claim_is_allowed() -> None:
    result = run_claims_check(
        ClaimsCheckInput(
            dm_message="Podemos hablar de una rutina SPF diaria.",
            product_category="sunscreen",
            key_claims_allowed=["SPF routine"],
        )
    )

    assert result.status == "passed"
    assert result.issues == []
