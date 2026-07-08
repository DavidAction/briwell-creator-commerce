from dataclasses import dataclass

import pytest

from app.trends import news_rss
from app.trends.news_rss import (
    NewsQuery,
    build_queries,
    fetch_news_signals,
    live_blockers,
    parse_rss_items,
)


@dataclass
class FakeConfig:
    news_rss_dry_run: bool = True
    allow_live_news_rss_calls: bool = False


@dataclass
class FakeResponse:
    status_code: int
    text: str


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Google News</title>
  <item>
    <title>K-beauty crece en Mexico</title>
    <link>https://example-news.test/articulo-1</link>
    <pubDate>Tue, 07 Jul 2026 12:00:00 GMT</pubDate>
    <source url="https://example-news.test">Example News</source>
  </item>
  <item>
    <title>Protector solar coreano: lo que hay que saber</title>
    <link>https://example-news.test/articulo-2</link>
    <pubDate>Mon, 06 Jul 2026 09:00:00 GMT</pubDate>
    <source url="https://example-news.test">Example News</source>
  </item>
  <item>
    <title></title>
    <link>https://example-news.test/sin-titulo</link>
  </item>
</channel></rss>"""


@pytest.fixture(autouse=True)
def clear_cache():
    news_rss.reset_cache()
    yield
    news_rss.reset_cache()


def make_query() -> NewsQuery:
    return build_queries(["MX"], ["sunscreen"])[0]


def test_build_queries_adds_generic_kbeauty_query_per_country() -> None:
    queries = build_queries(["MX", "PE"], ["sunscreen"])
    assert len(queries) == 4  # (sunscreen + generic) x 2 countries
    assert {q.country for q in queries} == {"MX", "PE"}
    assert any(q.product_category == "kbeauty_general" for q in queries)
    assert all(q.feed_url.startswith("https://news.google.com/rss/search?q=") for q in queries)
    assert all("hl=es-419" in q.feed_url for q in queries)


def test_build_queries_skips_unknown_countries_and_categories() -> None:
    queries = build_queries(["US", "MX"], ["unknown_category"])
    assert {q.country for q in queries} == {"MX"}
    assert [q.product_category for q in queries] == ["kbeauty_general"]


def test_parse_rss_items_extracts_titled_items_and_skips_untitled() -> None:
    items = parse_rss_items(SAMPLE_RSS, make_query(), max_items=10)
    assert [item.title for item in items] == [
        "K-beauty crece en Mexico",
        "Protector solar coreano: lo que hay que saber",
    ]
    assert items[0].source == "Example News"
    assert items[0].published_at.startswith("Tue, 07 Jul 2026")
    assert items[0].country == "MX"


def test_parse_rss_items_rejects_malformed_xml() -> None:
    with pytest.raises(ValueError, match="Invalid RSS XML"):
        parse_rss_items("<rss><channel><item>", make_query(), max_items=5)


def test_dry_run_returns_labeled_samples_without_network() -> None:
    def explode(*_args, **_kwargs):
        raise AssertionError("dry-run must not touch the network")

    result = fetch_news_signals(["MX"], ["sunscreen"], config=FakeConfig(), http_get=explode)
    assert result["status"] == "dry_run_completed"
    assert result["mode"] == "dry_run"
    assert result["source_type"] == "public_news_rss"
    assert result["item_count"] > 0
    assert all(item["source"] == "Briwell dry-run sample" for item in result["items"])
    assert "NEWS_RSS_DRY_RUN is true" in result["live_blockers"]


def test_live_fetch_parses_feeds_and_caches_within_ttl() -> None:
    calls = {"count": 0}

    def fake_get(_url, **_kwargs):
        calls["count"] += 1
        return FakeResponse(200, SAMPLE_RSS)

    clock = {"now": 100.0}
    cfg = FakeConfig(news_rss_dry_run=False, allow_live_news_rss_calls=True)
    first = fetch_news_signals(
        ["MX"], ["sunscreen"], config=cfg, http_get=fake_get, now=lambda: clock["now"]
    )
    assert first["status"] == "live_completed"
    assert first["mode"] == "live"
    assert first["item_count"] == 4  # 2 items x 2 queries (sunscreen + generic)
    first_calls = calls["count"]

    clock["now"] += 10  # inside TTL -> served from cache
    second = fetch_news_signals(
        ["MX"], ["sunscreen"], config=cfg, http_get=fake_get, now=lambda: clock["now"]
    )
    assert calls["count"] == first_calls
    assert second["item_count"] == first["item_count"]

    clock["now"] += news_rss.CACHE_TTL_SECONDS + 1  # past TTL -> refetch
    fetch_news_signals(["MX"], ["sunscreen"], config=cfg, http_get=fake_get, now=lambda: clock["now"])
    assert calls["count"] == first_calls * 2


def test_live_fetch_with_all_queries_failing_reports_blocked() -> None:
    def failing_get(_url, **_kwargs):
        return FakeResponse(503, "unavailable")

    cfg = FakeConfig(news_rss_dry_run=False, allow_live_news_rss_calls=True)
    result = fetch_news_signals(["MX"], ["sunscreen"], config=cfg, http_get=failing_get)
    assert result["status"] == "blocked"
    assert result["item_count"] == 0
    assert len(result["errors"]) == 2


def test_live_blockers_follow_dual_gate() -> None:
    assert live_blockers(FakeConfig()) == [
        "NEWS_RSS_DRY_RUN is true",
        "ALLOW_LIVE_NEWS_RSS_CALLS is false",
    ]
    assert live_blockers(FakeConfig(news_rss_dry_run=False, allow_live_news_rss_calls=True)) == []
