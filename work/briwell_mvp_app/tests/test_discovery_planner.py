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
