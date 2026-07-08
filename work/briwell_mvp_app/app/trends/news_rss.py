"""Public Google News RSS fetcher for LATAM K-beauty market signals.

Slimmed-C step (b) (briefing 0.0.12 next / 0.0.8 tier-1): surfaces "what is
moving in the market" headlines on the discovery screen. This is a legal
source lane — Google News publishes these RSS feeds for consumption, no
anti-bot bypass and no platform scraping is involved.

Compliance note: news items are market signals only. They are never stored as
creator/video workflow inputs, so the ALLOWED_COLLECTION_SOURCE_TYPES policy
(manual/official_api/approved_provider/creator_provided) does not apply to
them; responses are labeled ``source_type="public_news_rss"`` so they cannot
be confused with a creator-intake lane.

House gating pattern (same shape as AI/TikTok/Shopify): dry-run by default
returns deterministic sample items so the UI and tests work offline. Live
fetches require BOTH ``NEWS_RSS_DRY_RUN=false`` and
``ALLOW_LIVE_NEWS_RSS_CALLS=true``. Live results are cached in-process for
``CACHE_TTL_SECONDS`` per query to keep request volume polite.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import quote

import httpx

from app.core.config import settings

REQUEST_TIMEOUT_SECONDS = 10.0
CACHE_TTL_SECONDS = 900.0
MAX_ITEMS_PER_QUERY_CAP = 10

SOURCE_TYPE = "public_news_rss"
SOURCE_RISK_LEVEL = "low"

# Country -> Google News locale parameters (Spanish, Latin America).
_COUNTRY_LOCALES = {
    "MX": {"hl": "es-419", "gl": "MX", "ceid": "MX:es-419"},
    "PE": {"hl": "es-419", "gl": "PE", "ceid": "PE:es-419"},
    "EC": {"hl": "es-419", "gl": "EC", "ceid": "EC:es-419"},
}

# Product category -> Spanish query stems. Combined with a country market term
# so headlines skew toward the launch markets rather than global K-beauty news.
_PRODUCT_QUERY_STEMS = {
    "sunscreen": "protector solar coreano",
    "calming_serum": "serum coreano piel sensible",
    "cleanser": "limpiador facial coreano",
    "sheet_mask": "mascarilla coreana",
    "cushion_foundation": "base cushion coreana",
}

_MARKET_TERMS = {"MX": "Mexico", "PE": "Peru", "EC": "Ecuador"}


@dataclass(frozen=True)
class NewsQuery:
    country: str
    product_category: str
    query: str
    feed_url: str


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    source: str
    published_at: str | None
    country: str
    product_category: str
    query: str


@dataclass
class _CacheEntry:
    fetched_at: float
    items: list[NewsItem] = field(default_factory=list)


_cache: dict[str, _CacheEntry] = {}


def live_blockers(config: Any = None) -> list[str]:
    cfg = config or settings
    blockers: list[str] = []
    if cfg.news_rss_dry_run:
        blockers.append("NEWS_RSS_DRY_RUN is true")
    if not cfg.allow_live_news_rss_calls:
        blockers.append("ALLOW_LIVE_NEWS_RSS_CALLS is false")
    return blockers


def build_queries(countries: list[str], product_categories: list[str]) -> list[NewsQuery]:
    """One query per (country, product) plus one generic K-beauty query per country."""

    queries: list[NewsQuery] = []
    for country in countries:
        if country not in _COUNTRY_LOCALES:
            continue
        stems = [
            (category, _PRODUCT_QUERY_STEMS[category])
            for category in product_categories
            if category in _PRODUCT_QUERY_STEMS
        ]
        stems.append(("kbeauty_general", "k-beauty cosmetica coreana"))
        for category, stem in stems:
            query = f"{stem} {_MARKET_TERMS[country]}"
            queries.append(
                NewsQuery(
                    country=country,
                    product_category=category,
                    query=query,
                    feed_url=_feed_url(query, country),
                )
            )
    return queries


def _feed_url(query: str, country: str) -> str:
    locale = _COUNTRY_LOCALES[country]
    return (
        "https://news.google.com/rss/search?q=" + quote(query)
        + f"&hl={locale['hl']}&gl={locale['gl']}&ceid={quote(locale['ceid'])}"
    )


def parse_rss_items(xml_text: str, query: NewsQuery, max_items: int) -> list[NewsItem]:
    """Parse Google News RSS XML into NewsItem rows. Raises ValueError on bad XML."""

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid RSS XML for query {query.query!r}: {exc}") from exc

    items: list[NewsItem] = []
    for node in root.findall("./channel/item")[:max_items]:
        title = (node.findtext("title") or "").strip()
        url = (node.findtext("link") or "").strip()
        if not title or not url:
            continue
        source_node = node.find("source")
        items.append(
            NewsItem(
                title=title,
                url=url,
                source=(source_node.text or "").strip() if source_node is not None else "",
                published_at=(node.findtext("pubDate") or "").strip() or None,
                country=query.country,
                product_category=query.product_category,
                query=query.query,
            )
        )
    return items


def _sample_items(query: NewsQuery, max_items: int) -> list[NewsItem]:
    """Deterministic dry-run rows so the panel renders offline (clearly labeled)."""

    samples = [
        (
            f"[샘플] Tendencias K-beauty en {_MARKET_TERMS[query.country]}: rutinas coreanas en alza",
            "https://news.google.com/rss/search?q=" + quote(query.query),
            "Briwell dry-run sample",
        ),
        (
            f"[샘플] {query.query} — cobertura de mercado y lanzamientos recientes",
            query.feed_url,
            "Briwell dry-run sample",
        ),
    ]
    return [
        NewsItem(
            title=title,
            url=url,
            source=source,
            published_at=None,
            country=query.country,
            product_category=query.product_category,
            query=query.query,
        )
        for title, url, source in samples[:max_items]
    ]


def _fetch_feed(query: NewsQuery, max_items: int, http_get: Callable[..., httpx.Response]) -> list[NewsItem]:
    response = http_get(query.feed_url, timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True)
    if response.status_code >= 400:
        raise RuntimeError(f"News RSS fetch failed for {query.query!r}: HTTP {response.status_code}")
    return parse_rss_items(response.text, query, max_items)


def fetch_news_signals(
    countries: list[str],
    product_categories: list[str],
    max_items_per_query: int = 5,
    config: Any = None,
    http_get: Callable[..., httpx.Response] | None = None,
    now: Callable[[], float] | None = None,
) -> dict[str, Any]:
    """Fetch (or dry-run) market news signals. ``http_get``/``now`` are injectable for tests."""

    cfg = config or settings
    clock = now or time.monotonic
    max_items = max(1, min(MAX_ITEMS_PER_QUERY_CAP, max_items_per_query))
    queries = build_queries(countries, product_categories)
    blockers = live_blockers(cfg)
    errors: list[str] = []
    items: list[NewsItem] = []

    if blockers:
        for query in queries:
            items.extend(_sample_items(query, max_items))
        mode = "dry_run"
        status = "dry_run_completed"
    else:
        get = http_get or httpx.get
        for query in queries:
            cache_key = f"{query.feed_url}|{max_items}"
            cached = _cache.get(cache_key)
            if cached and clock() - cached.fetched_at < CACHE_TTL_SECONDS:
                items.extend(cached.items)
                continue
            try:
                fetched = _fetch_feed(query, max_items, get)
            except (RuntimeError, ValueError, httpx.HTTPError) as exc:
                errors.append(str(exc))
                continue
            _cache[cache_key] = _CacheEntry(fetched_at=clock(), items=fetched)
            items.extend(fetched)
        mode = "live"
        # Partial results still count as a live completion; only an all-queries
        # failure with nothing to show is a blocked run.
        status = "live_completed" if items or not errors else "blocked"

    return {
        "status": status,
        "mode": mode,
        "source_type": SOURCE_TYPE,
        "source_risk_level": SOURCE_RISK_LEVEL,
        "query_count": len(queries),
        "item_count": len(items),
        "queries": [query.__dict__ for query in queries],
        "items": [item.__dict__ for item in items],
        "live_blockers": blockers,
        "errors": errors,
        "next_actions": _next_actions(blockers),
    }


def _next_actions(blockers: list[str]) -> list[str]:
    if blockers:
        return [
            "Dry-run sample items shown. Open the live gates (NEWS_RSS_DRY_RUN=false, "
            "ALLOW_LIVE_NEWS_RSS_CALLS=true) to fetch real headlines.",
            "News items are market signals only — never import them as creator workflow inputs.",
        ]
    return [
        "Use rising themes to refine discovery keywords and campaign angles.",
        "News items are market signals only — never import them as creator workflow inputs.",
    ]


def reset_cache() -> None:
    """Test helper: clear the in-process feed cache."""

    _cache.clear()
