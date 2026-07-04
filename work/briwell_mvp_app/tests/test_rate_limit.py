from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main_module
from app.core.rate_limit import SlidingWindowRateLimiter
from app.main import app


client = TestClient(app)


def enable_rate_limiting(monkeypatch, requests_per_minute: int = 120, burst: int = 20) -> None:
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(
            rate_limit_enabled=True,
            rate_limit_requests_per_minute=requests_per_minute,
            rate_limit_burst=burst,
        ),
    )
    monkeypatch.setattr(
        main_module,
        "rate_limiter",
        SlidingWindowRateLimiter(requests_per_minute=requests_per_minute, burst=burst),
    )


def test_requests_under_threshold_are_allowed(monkeypatch) -> None:
    enable_rate_limiting(monkeypatch, requests_per_minute=120, burst=20)

    for _ in range(5):
        response = client.get("/health")
        assert response.status_code == 200


def test_requests_over_threshold_are_blocked_with_429(monkeypatch) -> None:
    enable_rate_limiting(monkeypatch, requests_per_minute=3, burst=3)

    responses = [
        client.get("/ops/security-policy", headers={"X-User-Role": "admin"}) for _ in range(3)
    ]
    for response in responses:
        assert response.status_code == 200

    blocked = client.get("/ops/security-policy", headers={"X-User-Role": "admin"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert int(blocked.headers["Retry-After"]) > 0


def test_health_endpoint_is_exempt_from_rate_limiting(monkeypatch) -> None:
    enable_rate_limiting(monkeypatch, requests_per_minute=1, burst=1)

    for _ in range(10):
        response = client.get("/health")
        assert response.status_code == 200


def test_rate_limiting_is_noop_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(
            rate_limit_enabled=False,
            rate_limit_requests_per_minute=1,
            rate_limit_burst=1,
        ),
    )

    for _ in range(10):
        response = client.get("/ops/security-policy", headers={"X-User-Role": "admin"})
        assert response.status_code == 200


def test_distinct_clients_have_independent_limits(monkeypatch) -> None:
    enable_rate_limiting(monkeypatch, requests_per_minute=1, burst=1)

    first = client.get(
        "/ops/security-policy",
        headers={"X-User-Role": "admin", "X-User-Email": "a@briwell.test"},
    )
    second = client.get(
        "/ops/security-policy",
        headers={"X-User-Role": "admin", "X-User-Email": "b@briwell.test"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
