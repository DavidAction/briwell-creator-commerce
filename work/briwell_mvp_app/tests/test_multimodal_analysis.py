from app.workers.multimodal_analysis import FrameSample
from app.workers.multimodal_analysis import MultimodalAnalysisRequest
from app.workers.multimodal_analysis import MultimodalVideoSnapshot
from app.workers.multimodal_analysis import run_multimodal_analysis


def test_multimodal_analysis_dry_run_scores_video_context() -> None:
    result = run_multimodal_analysis(
        MultimodalAnalysisRequest(
            source_risk_level="low",
            video=MultimodalVideoSnapshot(
                video_id="video-1",
                caption="Rutina de piel con protector solar coreano SPF.",
                transcript="Me gusta este protector porque se siente ligero.",
                view_count=25000,
            ),
            frame_samples=[
                FrameSample(
                    timestamp_seconds=1.2,
                    description="Creator holds a sunscreen tube near the camera.",
                )
            ],
        )
    )

    assert result.status == "success"
    assert result.result.status == "ok"
    assert result.result.output["product_visibility_score"] >= 70
    assert "sunscreen" in result.result.output["visible_product_types"]
    assert result.invocation_log["task_type"] == "multimodal_analysis"


def test_multimodal_analysis_blocks_high_risk_source() -> None:
    result = run_multimodal_analysis(
        MultimodalAnalysisRequest(
            source_risk_level="high",
            video=MultimodalVideoSnapshot(video_id="video-1"),
        )
    )

    assert result.status == "skipped"
    assert result.result.status == "rejected"
    assert result.invocation_log["error_message"] == "source_risk_not_allowed"
