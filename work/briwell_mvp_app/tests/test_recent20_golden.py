from scripts.evaluate_recent20_golden import evaluate_all
from scripts.smoke_gemini_recent20_live import preflight_errors


def test_recent20_golden_dataset_passes_dry_run_contract() -> None:
    result = evaluate_all()

    assert result["status"] == "passed"
    assert result["case_count"] >= 4


def test_live_smoke_preflight_blocks_without_explicit_confirmation(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ALLOW_LIVE_PROVIDER_CALLS", "true")
    monkeypatch.setenv("AI_DRY_RUN", "false")

    errors = preflight_errors(confirm_live_cost=False, persist_result=False)

    assert any("--confirm-live-cost" in error for error in errors)
    assert "GEMINI_API_KEY is required" in errors
