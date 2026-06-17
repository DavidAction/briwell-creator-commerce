import unittest

from app.core.policy import (
    PolicyError,
    can_advance_to_dm_sent,
    can_generate_dm,
    import_status_for_creator,
    normalize_source_risk,
    normalize_source_type,
    require_allowed_collection_source_type,
    require_allowed_source_risk,
    requires_admin_approval,
    source_risk_decision,
)


class SourceRiskPolicyTests(unittest.TestCase):
    def test_normalize_source_risk_aliases(self) -> None:
        self.assertEqual(normalize_source_risk("Low to Medium"), "low_medium")
        self.assertEqual(normalize_source_risk("notallowed"), "not_allowed")

    def test_allowed_source_risks(self) -> None:
        for level in ("low", "low_medium", "medium"):
            self.assertEqual(require_allowed_source_risk(level), level)

    def test_blocked_source_risks(self) -> None:
        for level in ("high", "not_allowed"):
            with self.assertRaises(PolicyError):
                require_allowed_source_risk(level)

    def test_medium_requires_admin_approval(self) -> None:
        self.assertFalse(requires_admin_approval("low"))
        self.assertTrue(requires_admin_approval("low_medium"))
        self.assertTrue(requires_admin_approval("medium"))

    def test_import_status_quarantines_blocked_levels(self) -> None:
        self.assertEqual(import_status_for_creator("low"), "active")
        self.assertEqual(import_status_for_creator("high"), "quarantined")

    def test_source_risk_decision_unknown(self) -> None:
        decision = source_risk_decision("mystery")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "unknown_source_risk_level")

    def test_collection_source_type_normalization(self) -> None:
        self.assertEqual(normalize_source_type("Approved Provider"), "approved_provider")
        self.assertEqual(require_allowed_collection_source_type("manual"), "manual")

    def test_blocked_collection_source_type(self) -> None:
        with self.assertRaises(PolicyError):
            require_allowed_collection_source_type("public page scrape")

    def test_unapproved_collection_source_type_is_blocked(self) -> None:
        with self.assertRaises(PolicyError) as exc:
            require_allowed_collection_source_type("random vendor export")
        self.assertEqual(str(exc.exception), "collection_source_type_not_approved")


class OutreachPolicyTests(unittest.TestCase):
    def test_can_generate_dm_for_allowed_creator(self) -> None:
        decision = can_generate_dm(
            {
                "source_risk_level": "medium",
                "status": "active",
                "do_not_contact": False,
                "removal_requested_at": None,
            }
        )
        self.assertTrue(decision.allowed)

    def test_blocks_high_risk_creator(self) -> None:
        decision = can_generate_dm(
            {
                "source_risk_level": "high",
                "status": "quarantined",
                "do_not_contact": False,
                "removal_requested_at": None,
            }
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "source_risk_not_allowed")

    def test_blocks_do_not_contact(self) -> None:
        decision = can_generate_dm(
            {
                "source_risk_level": "low",
                "status": "active",
                "do_not_contact": True,
                "removal_requested_at": None,
            }
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "do_not_contact")

    def test_dm_sent_requires_claims_check_and_dnc_check(self) -> None:
        failed = can_advance_to_dm_sent(
            {
                "claims_check_status": "needs_review",
                "do_not_contact_checked_at": "2026-06-17T00:00:00Z",
            }
        )
        self.assertFalse(failed.allowed)
        self.assertEqual(failed.reason, "claims_check_required")

        failed = can_advance_to_dm_sent(
            {
                "claims_check_status": "passed",
                "do_not_contact_checked_at": None,
            }
        )
        self.assertFalse(failed.allowed)
        self.assertEqual(failed.reason, "do_not_contact_check_required")

        passed = can_advance_to_dm_sent(
            {
                "claims_check_status": "passed",
                "do_not_contact_checked_at": "2026-06-17T00:00:00Z",
            }
        )
        self.assertTrue(passed.allowed)


if __name__ == "__main__":
    unittest.main()
