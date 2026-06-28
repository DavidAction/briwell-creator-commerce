from typing import Any


PRODUCT_LABELS = {
    "sunscreen": "protector solar coreano",
    "calming_serum": "serum calmante coreano",
    "cleanser": "limpiador coreano",
    "sheet_mask": "mascarilla coreana",
    "cushion_foundation": "cushion foundation coreana",
}


def build_dm_drafts(
    creator: dict[str, Any],
    product_category: str,
    product_name: str | None = None,
) -> list[dict[str, Any]]:
    display_name = creator.get("display_name") or creator.get("username") or "hola"
    product_label = product_name or PRODUCT_LABELS.get(product_category, "producto K-beauty")
    evidence = _personalization_evidence(creator)

    return [
        {
            "variant": "soft_intro",
            "message": (
                f"Hola {display_name}, soy del equipo de Briwell. Nos gusto tu contenido de "
                f"belleza y estamos preparando una colaboracion de K-beauty con {product_label}. "
                "Si te interesa, puedo compartirte los detalles."
            ),
            "personalization_evidence": evidence,
            "product_angle": PRODUCT_LABELS.get(product_category, "K-beauty"),
            "claims_check_status": "needs_review",
        },
        {
            "variant": "product_review",
            "message": (
                f"Hola {display_name}, en Briwell estamos buscando creadoras en LatAm para probar "
                f"{product_label} y compartir una resena honesta si encaja con su estilo. "
                "La colaboracion seria clara, sencilla y con aprobacion previa de los detalles."
            ),
            "personalization_evidence": evidence,
            "product_angle": "resena honesta de producto",
            "claims_check_status": "needs_review",
        },
        {
            "variant": "ugc_collaboration",
            "message": (
                f"Hola {display_name}, nos encanto tu estilo y nos gustaria invitarte a crear contenido "
                f"UGC con {product_label} para las campanas de Briwell en LatAm. Tu defines el formato; "
                "nosotros coordinamos producto, brief y aprobacion previa de los detalles."
            ),
            "personalization_evidence": evidence,
            "product_angle": "contenido UGC de marca",
            "claims_check_status": "needs_review",
        },
        {
            "variant": "commerce_collaboration",
            "message": (
                f"Hola {display_name}, en Briwell preparamos una colaboracion de comercio con {product_label}: "
                "codigo de descuento y link de compra para tu comunidad, con condiciones claras y aprobacion "
                "previa. Si te interesa, te comparto los detalles de la comision."
            ),
            "personalization_evidence": evidence,
            "product_angle": "colaboracion de comercio con link",
            "claims_check_status": "needs_review",
        },
    ]


def build_ai_dm_drafts(
    creator: dict[str, Any],
    product_category: str,
    product_name: str | None = None,
    country: str | None = None,
    dry_run: bool = True,
    allow_live_provider_calls: bool = False,
    source_risk_level: str = "low",
) -> dict[str, Any]:
    """Generate personalized 3-variant Spanish DM drafts via Gemini (model alias
    ``dm_generation`` -> gemini-3.5-flash), reflecting the creator profile and target
    country tone. Falls back to the deterministic ``build_dm_drafts`` templates when the
    AI is unavailable, disabled, or returns nothing usable — so the workflow never breaks.
    """
    # Lazy import to avoid any import-time coupling with the workers/AI stack.
    from app.ai.contracts import AnalysisRequest
    from app.workers.analysis_runner import AnalysisRunRequest, run_analysis

    fallback = build_dm_drafts(creator, product_category=product_category, product_name=product_name)
    run = run_analysis(
        AnalysisRunRequest(
            target_entity_type="creator",
            target_entity_id=str(creator.get("creator_id") or creator.get("username") or ""),
            dry_run=dry_run,
            allow_live_provider_calls=allow_live_provider_calls,
            persist_log=False,
            mark_job_status=False,
            request=AnalysisRequest(
                task_type="dm_generation",
                model_alias="dm_generation",
                source_risk_level=source_risk_level,
                prompt_version="dm_generation_v0",
                payload={
                    "creator": creator,
                    "product_category": product_category,
                    "product_name": product_name,
                    "country": country or creator.get("country"),
                },
            ),
        )
    )
    if run.status != "success":
        return {
            "status": run.result.status,
            "source": "template_fallback",
            "error_code": run.result.error_code,
            "drafts": fallback,
        }

    drafts = [
        {
            "variant": variant.get("variant", "soft_intro"),
            "message": variant.get("message", ""),
            "personalization_evidence": variant.get("personalization_evidence", []),
            "product_angle": variant.get("product_angle", ""),
            "claims_check_status": "needs_review",
        }
        for variant in (run.result.output.get("variants") or [])
        if variant.get("message")
    ]
    if not drafts:
        return {"status": "empty_ai_output", "source": "template_fallback", "drafts": fallback}

    return {
        "status": "generated",
        "source": "ai_dry_run" if dry_run else "ai_live",
        "language": run.result.output.get("language", "es"),
        "country": run.result.output.get("country"),
        "drafts": drafts,
    }


def _personalization_evidence(creator: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    if creator.get("country"):
        evidence.append(f"creator_country:{creator['country']}")
    if creator.get("bio"):
        evidence.append("profile_bio_provided")
    if creator.get("follower_count") is not None:
        evidence.append("follower_count_provided")
    if not evidence:
        evidence.append("minimal_profile_context")
    return evidence[:3]
