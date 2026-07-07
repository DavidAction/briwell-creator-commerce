import os

import pytest

from app.workers.job_queue import process_one


db_tests_only = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="Set RUN_DB_TESTS=1 with a live PostgreSQL DATABASE_URL to run DB integration tests.",
)


@db_tests_only
def test_enqueue_and_claim_flips_status_to_processing() -> None:
    import psycopg
    from psycopg.rows import dict_row

    from app.core.config import settings
    from app.repositories.jobs import claim_next_job, enqueue_job

    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        job_id = enqueue_job(conn, "audit_event.persist", {"foo": "bar"})
        claimed = claim_next_job(conn, job_types=["audit_event.persist"])

        assert claimed is not None
        assert claimed["id"] == job_id
        assert claimed["status"] == "processing"
        assert claimed["started_at"] is not None


@db_tests_only
def test_mark_job_done_leaves_status_done() -> None:
    import psycopg
    from psycopg.rows import dict_row

    from app.core.config import settings
    from app.repositories.jobs import claim_next_job, enqueue_job, mark_job_done

    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        job_id = enqueue_job(conn, "audit_event.persist", {})
        claim_next_job(conn, job_types=["audit_event.persist"])
        mark_job_done(conn, job_id)

        with conn.cursor() as cur:
            cur.execute("SELECT status, finished_at FROM jobs WHERE id = %(id)s", {"id": job_id})
            row = cur.fetchone()

        assert row["status"] == "done"
        assert row["finished_at"] is not None


@db_tests_only
def test_mark_job_failed_requeues_under_max_attempts_and_fails_at_max() -> None:
    import psycopg
    from psycopg.rows import dict_row

    from app.core.config import settings
    from app.repositories.jobs import claim_next_job, enqueue_job, mark_job_failed

    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        job_id = enqueue_job(conn, "audit_event.persist", {})

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET max_attempts = 2 WHERE id = %(id)s",
                {"id": job_id},
            )
        conn.commit()

        claim_next_job(conn, job_types=["audit_event.persist"])
        mark_job_failed(conn, job_id, "boom")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, attempts, last_error FROM jobs WHERE id = %(id)s",
                {"id": job_id},
            )
            row = cur.fetchone()

        assert row["status"] == "pending"
        assert row["attempts"] == 1
        assert row["last_error"] == "boom"

        claim_next_job(conn, job_types=["audit_event.persist"])
        mark_job_failed(conn, job_id, "boom again")

        with conn.cursor() as cur:
            cur.execute("SELECT status, attempts FROM jobs WHERE id = %(id)s", {"id": job_id})
            row = cur.fetchone()

        assert row["status"] == "failed"
        assert row["attempts"] == 2


@db_tests_only
def test_process_one_dispatches_to_registered_handler_and_marks_done() -> None:
    import psycopg
    from psycopg.rows import dict_row

    from app.core.config import settings
    from app.repositories.jobs import enqueue_job
    from app.workers.job_handlers import JOB_HANDLERS

    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_events (event_type, aggregate_type, aggregate_id) "
                "SELECT 'noop', 'noop', 'noop' WHERE FALSE"
            )
        conn.commit()

        payload = {
            "event_type": "job_queue.smoke_test",
            "aggregate_type": "job",
            "aggregate_id": "smoke",
            "actor_role": None,
            "actor_email": None,
            "payload": {},
        }
        enqueue_job(conn, "audit_event.persist", payload)

        processed = process_one(conn, JOB_HANDLERS)

        assert processed is True

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM jobs WHERE job_type = 'audit_event.persist' "
                "ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()

        assert row["status"] == "done"


def test_enqueue_job_wraps_payload_as_jsonb_for_live_postgres() -> None:
    # Raw dict params fail on live psycopg with "cannot adapt type 'dict'";
    # the payload must be wrapped in psycopg's Jsonb (same fix as audit_events).
    from psycopg.types.json import Jsonb

    from app.repositories import jobs

    captured: dict = {}

    class FakeCursor:
        def execute(self, query, params):
            captured.update(params)

        def fetchone(self):
            return {"id": 42}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

    job_id = jobs.enqueue_job(FakeConn(), "audit_event.persist", {"foo": "bar"})

    assert job_id == 42
    assert isinstance(captured["payload"], Jsonb)
    assert captured["payload"].obj == {"foo": "bar"}


class FakeJobsRepository:
    def __init__(self, job: dict | None) -> None:
        self._job = job
        self.done_calls: list[int] = []
        self.failed_calls: list[tuple[int, str]] = []

    def claim_next_job(self, conn, job_types=None):
        job, self._job = self._job, None
        return job

    def mark_job_done(self, conn, job_id):
        self.done_calls.append(job_id)

    def mark_job_failed(self, conn, job_id, error):
        self.failed_calls.append((job_id, error))


def test_process_one_returns_false_when_queue_is_empty(monkeypatch) -> None:
    from app.workers import job_queue

    fake = FakeJobsRepository(job=None)
    monkeypatch.setattr(job_queue, "claim_next_job", fake.claim_next_job)
    monkeypatch.setattr(job_queue, "mark_job_done", fake.mark_job_done)
    monkeypatch.setattr(job_queue, "mark_job_failed", fake.mark_job_failed)

    processed = process_one(conn=object(), handlers={})

    assert processed is False
    assert fake.done_calls == []
    assert fake.failed_calls == []


def test_process_one_dispatches_and_marks_done_on_success(monkeypatch) -> None:
    from app.workers import job_queue

    job = {"id": 1, "job_type": "stub.job", "payload": {"n": 1}}
    fake = FakeJobsRepository(job=job)
    monkeypatch.setattr(job_queue, "claim_next_job", fake.claim_next_job)
    monkeypatch.setattr(job_queue, "mark_job_done", fake.mark_job_done)
    monkeypatch.setattr(job_queue, "mark_job_failed", fake.mark_job_failed)

    calls = []

    def stub_handler(conn, payload):
        calls.append(payload)

    processed = process_one(conn=object(), handlers={"stub.job": stub_handler})

    assert processed is True
    assert calls == [{"n": 1}]
    assert fake.done_calls == [1]
    assert fake.failed_calls == []


class FakeConnection:
    def __init__(self) -> None:
        self.rollback_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_process_one_marks_failed_when_handler_raises(monkeypatch) -> None:
    from app.workers import job_queue

    job = {"id": 2, "job_type": "stub.job", "payload": {}}
    fake = FakeJobsRepository(job=job)
    monkeypatch.setattr(job_queue, "claim_next_job", fake.claim_next_job)
    monkeypatch.setattr(job_queue, "mark_job_done", fake.mark_job_done)
    monkeypatch.setattr(job_queue, "mark_job_failed", fake.mark_job_failed)

    def stub_handler(conn, payload):
        raise ValueError("kaboom")

    conn = FakeConnection()
    processed = process_one(conn=conn, handlers={"stub.job": stub_handler})

    assert processed is True
    assert fake.done_calls == []
    assert fake.failed_calls == [(2, "kaboom")]
    assert conn.rollback_calls == 1


def test_process_one_rolls_back_before_mark_job_failed_so_it_cannot_run_on_a_poisoned_transaction(
    monkeypatch,
) -> None:
    from app.workers import job_queue

    job = {"id": 4, "job_type": "stub.job", "payload": {}}
    fake = FakeJobsRepository(job=job)
    monkeypatch.setattr(job_queue, "claim_next_job", fake.claim_next_job)
    monkeypatch.setattr(job_queue, "mark_job_done", fake.mark_job_done)

    call_order: list[str] = []

    def tracking_mark_job_failed(conn, job_id, error):
        call_order.append("mark_job_failed")
        fake.mark_job_failed(conn, job_id, error)

    monkeypatch.setattr(job_queue, "mark_job_failed", tracking_mark_job_failed)

    class TrackingConnection(FakeConnection):
        def rollback(self) -> None:
            call_order.append("rollback")
            super().rollback()

    def stub_handler(conn, payload):
        raise ValueError("boom")

    conn = TrackingConnection()
    processed = process_one(conn=conn, handlers={"stub.job": stub_handler})

    assert processed is True
    assert call_order == ["rollback", "mark_job_failed"]


def test_process_one_marks_failed_when_no_handler_registered(monkeypatch) -> None:
    from app.workers import job_queue

    job = {"id": 3, "job_type": "unknown.job", "payload": {}}
    fake = FakeJobsRepository(job=job)
    monkeypatch.setattr(job_queue, "claim_next_job", fake.claim_next_job)
    monkeypatch.setattr(job_queue, "mark_job_done", fake.mark_job_done)
    monkeypatch.setattr(job_queue, "mark_job_failed", fake.mark_job_failed)

    processed = process_one(conn=object(), handlers={})

    assert processed is True
    assert fake.done_calls == []
    assert len(fake.failed_calls) == 1
    assert fake.failed_calls[0][0] == 3
