import asyncio
import json

from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest

from app.main import app, handle_unexpected_error


def _fake_request() -> StarletteRequest:
    return StarletteRequest(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("test", 80),
            "path": "/boom",
            "headers": [],
            "query_string": b"",
        }
    )


def test_exception_handler_returns_clean_json_without_leaking_internals() -> None:
    response = asyncio.run(
        handle_unexpected_error(_fake_request(), ValueError("secret db password in stack trace"))
    )
    assert response.status_code == 500
    body = json.loads(response.body)
    assert body["detail"]["code"] == "INTERNAL_SERVER_ERROR"
    assert body["detail"]["request_id"]
    # The internal exception text must never appear in the client-facing response.
    assert "secret db password" not in response.body.decode()
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_unhandled_endpoint_error_is_caught_as_500(monkeypatch) -> None:
    from app.routers import ops as ops_module

    def _boom(*_a, **_k):
        raise RuntimeError("internal detail that must not leak")

    monkeypatch.setattr(ops_module, "evaluate_readiness", _boom)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/ops/readiness", headers={"X-User-Role": "admin"})
    assert response.status_code == 500
    body = response.json()
    assert body["detail"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "internal detail" not in response.text
    assert response.headers.get("X-Request-ID")


def test_readiness_reports_real_middleware_state() -> None:
    client = TestClient(app)
    response = client.get("/ops/readiness", headers={"X-User-Role": "admin"})
    assert response.status_code == 200
    checks = response.json()["checks"]
    assert checks["security_headers_enabled"] is True
    assert checks["request_id_middleware_enabled"] is True
    assert checks["global_exception_handler_enabled"] is True
