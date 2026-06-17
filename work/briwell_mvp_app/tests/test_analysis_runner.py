from app.ai.contracts import AnalysisRequest, AnalysisResult
from app.workers.analysis_runner import (
    AnalysisRunRequest,
    build_invocation_log_payload,
    estimate_analysis_cost,
    estimate_tokens,
    live_provider_call_requested,
    run_analysis,
    status_for_result,
)


def test_run_analysis_dry_run_returns_log_preview_without_database() -> None:
    result = run_analysis(
        AnalysisRunRequest(
            target_entity_type="creator",
            target_entity_id="creator-1",
            request=AnalysisRequest(
                task_type="profile_analysis",
                model_alias="low_cost_text",
                source_risk_level="low",
                prompt_version="profile_v0",
                payload={
                    "creator": {
                        "country": "MX",
                        "username": "creator_mx",
                        "profile_url": "https://example.com/@creator_mx",
                        "bio": "skincare and kbeauty reviews",
                        "language": "es",
                    }
                },
            ),
        )
    )
    assert result.status == "success"
    assert result.persistence_status == "validated_not_persisted"
    assert result.result.status == "ok"
    assert result.invocation_log["target_entity_type"] == "creator"
    assert result.invocation_log["status"] == "success"
    assert result.invocation_log["input_token_count"] > 0
    assert result.invocation_log["output_token_count"] > 0


def test_run_analysis_high_risk_is_skipped_before_provider_call() -> None:
    result = run_analysis(
        AnalysisRunRequest(
            target_entity_type="creator",
            target_entity_id="creator-1",
            request=AnalysisRequest(
                task_type="profile_analysis",
                model_alias="low_cost_text",
                source_risk_level="high",
                prompt_version="profile_v0",
                payload={"creator": {"username": "creator"}},
            ),
        )
    )
    assert result.status == "skipped"
    assert result.result.status == "rejected"
    assert result.invocation_log["status"] == "skipped"
    assert result.invocation_log["error_message"] == "source_risk_not_allowed"


def test_status_for_result_maps_adapter_statuses() -> None:
    ok = AnalysisResult(
        status="ok",
        model_alias="low_cost_text",
        prompt_version="profile_v0",
        output={"status": "ok"},
        confidence=0.7,
    )
    rejected = AnalysisResult(
        status="rejected",
        model_alias="low_cost_text",
        prompt_version="profile_v0",
        output={"status": "rejected"},
        confidence=1,
    )
    failed = AnalysisResult(
        status="error",
        model_alias="low_cost_text",
        prompt_version="profile_v0",
        output={"status": "error"},
        confidence=0,
    )
    assert status_for_result(ok) == "success"
    assert status_for_result(rejected) == "skipped"
    assert status_for_result(failed) == "failed"


def test_invocation_log_payload_includes_estimates() -> None:
    run_request = AnalysisRunRequest(
        target_entity_type="creator",
        target_entity_id="creator-1",
        request=AnalysisRequest(
            task_type="profile_analysis",
            model_alias="low_cost_text",
            source_risk_level="low",
            prompt_version="profile_v0",
            payload={"creator": {"username": "creator"}},
        ),
    )
    result = AnalysisResult(
        status="ok",
        model_alias="low_cost_text",
        prompt_version="profile_v0",
        output={"status": "ok", "evidence": ["x"], "confidence": 0.8},
        confidence=0.8,
    )
    payload = build_invocation_log_payload(run_request, result, latency_ms=12)
    assert payload["latency_ms"] == 12
    assert payload["status"] == "success"
    assert payload["model_alias"] == "low_cost_text"
    assert payload["input_token_count"] == estimate_tokens(run_request.request.model_dump())


def test_live_provider_cost_estimate_uses_alias_pricing() -> None:
    result = AnalysisResult(
        status="ok",
        model_alias="recent_posts_screen",
        prompt_version="recent_posts_screen_v0",
        output={"status": "ok", "evidence": ["x"], "confidence": 0.8},
        confidence=0.8,
    )

    assert estimate_analysis_cost(
        model_alias="recent_posts_screen",
        input_token_count=100_000,
        output_token_count=10_000,
        live_provider_call=True,
        result=result,
    ) == 0.014
    assert estimate_analysis_cost(
        model_alias="recent_posts_screen",
        input_token_count=100_000,
        output_token_count=10_000,
        live_provider_call=False,
        result=result,
    ) == 0.0


def test_live_analysis_requires_database_when_configured(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.workers import analysis_runner

    monkeypatch.setattr(
        analysis_runner,
        "settings",
        SimpleNamespace(
            ai_dry_run=False,
            allow_live_provider_calls=True,
            ai_live_require_database=True,
            ai_live_daily_call_limit=50,
            ai_live_daily_cost_limit_usd=2.0,
            ai_live_per_creator_daily_call_limit=3,
        ),
    )
    monkeypatch.setattr(analysis_runner, "database_enabled", lambda: False)

    request = AnalysisRunRequest(
        target_entity_type="creator",
        target_entity_id="creator-1",
        dry_run=False,
        allow_live_provider_calls=True,
        request=AnalysisRequest(
            task_type="profile_analysis",
            model_alias="low_cost_text",
            source_risk_level="low",
            prompt_version="profile_v0",
            payload={"creator": {"username": "creator"}},
        ),
    )

    assert live_provider_call_requested(request) is True
    result = run_analysis(request)
    assert result.status == "failed"
    assert result.result.error_code == "live_ai_database_required"


def test_live_analysis_blocks_daily_budget(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.workers import analysis_runner

    monkeypatch.setattr(
        analysis_runner,
        "settings",
        SimpleNamespace(
            ai_dry_run=False,
            allow_live_provider_calls=True,
            ai_live_require_database=True,
            ai_live_daily_call_limit=1,
            ai_live_daily_cost_limit_usd=2.0,
            ai_live_per_creator_daily_call_limit=3,
        ),
    )
    monkeypatch.setattr(analysis_runner, "database_enabled", lambda: True)
    monkeypatch.setattr(
        analysis_runner.ai_invocation_logs,
        "live_usage_summary",
        lambda **_kwargs: {"call_count": 1, "cost_usd": 0.01},
    )

    result = run_analysis(
        AnalysisRunRequest(
            target_entity_type="creator",
            target_entity_id="9c0e8b22-8e32-4e8d-bd2e-0fe275510001",
            dry_run=False,
            allow_live_provider_calls=True,
            request=AnalysisRequest(
                task_type="profile_analysis",
                model_alias="low_cost_text",
                source_risk_level="low",
                prompt_version="profile_v0",
                payload={"creator": {"username": "creator"}},
            ),
        )
    )

    assert result.status == "failed"
    assert result.result.error_code == "live_ai_daily_call_limit_reached"
