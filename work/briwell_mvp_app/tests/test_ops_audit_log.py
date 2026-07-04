from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.main import app
from app.routers import ops as ops_router


client = TestClient(app)


@contextmanager
def _fake_connection():
    yield object()


def test_audit_log_rejects_viewer_role() -> None:
    response = client.get("/ops/audit-log", headers={"X-User-Role": "viewer"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_audit_log_returns_empty_items_when_database_disabled() -> None:
    response = client.get("/ops/audit-log", headers={"X-User-Role": "admin"})

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_audit_log_allows_admin_and_operator_with_expected_shape(monkeypatch) -> None:
    monkeypatch.setattr(ops_router, "database_enabled", lambda: True)
    monkeypatch.setattr(ops_router, "connection", _fake_connection)

    captured: dict[str, object] = {}

    def fake_list_events(conn, aggregate_type=None, aggregate_id=None, event_type=None, limit=50):
        captured["aggregate_type"] = aggregate_type
        captured["aggregate_id"] = aggregate_id
        captured["event_type"] = event_type
        captured["limit"] = limit
        return [
            {
                "id": 1,
                "event_type": "outreach.status_changed",
                "aggregate_type": "outreach",
                "aggregate_id": "outreach-1",
                "actor_role": "operator",
                "actor_email": "operator@briwell.test",
                "payload": {"old_status": "approved", "new_status": "dm_sent"},
                "occurred_at": "2026-07-01T00:00:00+00:00",
            }
        ]

    monkeypatch.setattr(ops_router.audit_events_repository, "list_events", fake_list_events)

    for role in ("admin", "operator"):
        response = client.get("/ops/audit-log", headers={"X-User-Role": role})

        assert response.status_code == 200
        body = response.json()
        assert body["items"][0]["event_type"] == "outreach.status_changed"
        assert body["items"][0]["aggregate_type"] == "outreach"
        assert body["items"][0]["actor_role"] == "operator"


def test_audit_log_passes_filters_through(monkeypatch) -> None:
    monkeypatch.setattr(ops_router, "database_enabled", lambda: True)
    monkeypatch.setattr(ops_router, "connection", _fake_connection)

    captured: dict[str, object] = {}

    def fake_list_events(conn, aggregate_type=None, aggregate_id=None, event_type=None, limit=50):
        captured["aggregate_type"] = aggregate_type
        captured["aggregate_id"] = aggregate_id
        captured["event_type"] = event_type
        captured["limit"] = limit
        return []

    monkeypatch.setattr(ops_router.audit_events_repository, "list_events", fake_list_events)

    response = client.get(
        "/ops/audit-log",
        headers={"X-User-Role": "admin"},
        params={
            "aggregate_type": "outreach",
            "aggregate_id": "outreach-1",
            "event_type": "outreach.status_changed",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert captured["aggregate_type"] == "outreach"
    assert captured["aggregate_id"] == "outreach-1"
    assert captured["event_type"] == "outreach.status_changed"
    assert captured["limit"] == 10


def test_audit_log_passes_uncapped_limit_through_to_repository_for_capping(monkeypatch) -> None:
    monkeypatch.setattr(ops_router, "database_enabled", lambda: True)
    monkeypatch.setattr(ops_router, "connection", _fake_connection)

    captured: dict[str, object] = {}

    def fake_list_events(conn, aggregate_type=None, aggregate_id=None, event_type=None, limit=50):
        captured["limit"] = limit
        assert limit == 5000
        return []

    monkeypatch.setattr(ops_router.audit_events_repository, "list_events", fake_list_events)

    response = client.get(
        "/ops/audit-log",
        headers={"X-User-Role": "admin"},
        params={"limit": 5000},
    )

    assert response.status_code == 200
    assert response.json() == {"items": []}
    assert captured["limit"] == 5000


def test_audit_events_repository_list_events_caps_limit_at_200() -> None:
    from app.repositories import audit_events as audit_events_repository

    class FakeCursor:
        def __init__(self) -> None:
            self.executed_params: dict[str, object] | None = None

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, query: str, params: dict[str, object]) -> None:
            self.executed_params = params

        def fetchall(self) -> list[dict[str, object]]:
            return []

    class FakeConnection:
        def __init__(self) -> None:
            self.cursor_obj = FakeCursor()

        def cursor(self) -> FakeCursor:
            return self.cursor_obj

        def commit(self) -> None:
            return None

    fake_conn = FakeConnection()

    audit_events_repository.list_events(fake_conn, limit=5000)  # type: ignore[arg-type]

    assert fake_conn.cursor_obj.executed_params["limit"] == 200
