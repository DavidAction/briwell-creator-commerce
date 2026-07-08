from dataclasses import dataclass

from scripts.shopify_golive_preflight import (
    STATUS_INFO,
    STATUS_MISSING,
    STATUS_READY,
    STATUS_WARN,
    evaluate_preflight,
)


@dataclass
class FakeConfig:
    shopify_shop_domain: str = ""
    shopify_admin_api_token: str = ""
    shopify_api_version: str = "2026-01"
    shopify_webhook_secret: str = ""
    shopify_dry_run: bool = True
    allow_live_shopify_calls: bool = False
    shopify_fx_rates_raw: str = ""
    use_database: bool = False


def by_name(checks):
    return {check.name: check for check in checks}


def test_unconfigured_env_reports_all_required_items_missing() -> None:
    checks = by_name(evaluate_preflight(FakeConfig()))
    for name in ("shop domain", "admin API token", "webhook HMAC secret", "FX rates", "database"):
        assert checks[name].status == STATUS_MISSING, name
    assert checks["API version"].status == STATUS_READY
    assert checks["live gates"].status == STATUS_INFO
    assert "closed" in checks["live gates"].detail


def test_fully_configured_env_has_no_missing_items() -> None:
    checks = evaluate_preflight(
        FakeConfig(
            shopify_shop_domain="briwell-mx.myshopify.com",
            shopify_admin_api_token="shpat_0123456789abcdef",
            shopify_webhook_secret="whsec",
            shopify_fx_rates_raw="MXN:0.058,PEN:0.27",
            use_database=True,
        )
    )
    assert [check for check in checks if check.status == STATUS_MISSING] == []
    assert [check for check in checks if check.status == STATUS_WARN] == []


def test_custom_domain_and_non_shpat_token_warn_instead_of_pass() -> None:
    checks = by_name(
        evaluate_preflight(
            FakeConfig(
                shopify_shop_domain="shop.briwell.co",
                shopify_admin_api_token="some-other-token",
                shopify_webhook_secret="whsec",
                shopify_fx_rates_raw="MXN:0.058,PEN:0.27",
                use_database=True,
            )
        )
    )
    assert checks["shop domain"].status == STATUS_WARN
    assert "myshopify" in checks["shop domain"].detail
    assert checks["admin API token"].status == STATUS_WARN


def test_fx_rates_missing_pilot_currency_warns() -> None:
    checks = by_name(evaluate_preflight(FakeConfig(shopify_fx_rates_raw="MXN:0.058")))
    assert checks["FX rates"].status == STATUS_WARN
    assert "PEN" in checks["FX rates"].detail


def test_fx_rates_parse_error_is_missing_with_reason() -> None:
    checks = by_name(evaluate_preflight(FakeConfig(shopify_fx_rates_raw="MXN:not-a-number")))
    assert checks["FX rates"].status == STATUS_MISSING
    assert "Invalid FX rate" in checks["FX rates"].detail


def test_open_live_gates_are_reported_loudly() -> None:
    checks = by_name(
        evaluate_preflight(FakeConfig(shopify_dry_run=False, allow_live_shopify_calls=True))
    )
    assert checks["live gates"].status == STATUS_INFO
    assert "OPEN" in checks["live gates"].detail
