from app.discovery.planner import DiscoveryPlanInput
from app.discovery.planner import build_discovery_plan
from app.discovery.planner import load_keyword_seed


def test_keyword_seed_loads_three_launch_countries() -> None:
    rows = load_keyword_seed()
    countries = {row.country for row in rows}

    assert {"MX", "PE", "EC"}.issubset(countries)


def test_discovery_plan_builds_country_product_platform_tasks() -> None:
    result = build_discovery_plan(
        DiscoveryPlanInput(
            countries=["MX", "PE"],
            product_categories=["sunscreen"],
            platforms=["tiktok"],
            max_keywords_per_country_category=2,
        )
    )

    assert result.status == "planned"
    assert result.planned_count == 4
    assert {item.country for item in result.items} == {"MX", "PE"}
    assert {item.product_category for item in result.items} == {"sunscreen"}
    assert all(item.platform == "tiktok" for item in result.items)
    assert all("manual" in item.source_type_options for item in result.items)
    assert result.coverage_audit
    assert result.recall_safeguards


def test_discovery_plan_exposes_blocked_scraping_sources() -> None:
    result = build_discovery_plan(
        DiscoveryPlanInput(
            countries=["EC"],
            product_categories=["cleanser"],
            platforms=["tiktok"],
            max_keywords_per_country_category=1,
        )
    )

    assert "browser_automation" in result.blocked_collection_source_types
    assert "captcha_bypass" in result.blocked_collection_source_types
    assert "public_page_scrape" in result.blocked_collection_source_types
    assert result.manual_review_checklist


def test_discovery_plan_balances_intent_types_when_budget_allows() -> None:
    result = build_discovery_plan(
        DiscoveryPlanInput(
            countries=["MX"],
            product_categories=["sunscreen"],
            platforms=["tiktok"],
            max_keywords_per_country_category=4,
        )
    )

    assert {item.intent_type for item in result.items} == {
        "discovery",
        "concern",
        "format",
        "commerce",
    }
    audit = result.coverage_audit[0]
    assert audit.missing_intent_types == []
    assert any("follower-count" in item for item in result.recall_safeguards)


def test_discovery_plan_warns_about_false_negative_risk_when_budget_is_small() -> None:
    result = build_discovery_plan(
        DiscoveryPlanInput(
            countries=["PE"],
            product_categories=["sunscreen"],
            platforms=["tiktok"],
            max_keywords_per_country_category=2,
        )
    )

    audit = result.coverage_audit[0]
    assert audit.selected_count == 2
    assert audit.missing_intent_types
    assert audit.false_negative_risks
    assert any("second-pass expansion" in item for item in audit.recommended_actions)
