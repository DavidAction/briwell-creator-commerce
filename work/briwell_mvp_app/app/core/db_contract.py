REQUIRED_TABLES = {
    "app_user",
    "creator",
    "video",
    "comment_sample",
    "product_catalog",
    "keyword_seed",
    "scoring_rule",
    "ai_model_config",
    "analysis_job",
    "creator_analysis",
    "campaign",
    "outreach",
    "ai_invocation_log",
    "campaign_performance_snapshot",
    "creator_contract",
    "creator_payout",
    "compliance_rule",
}

REQUIRED_ENUMS = {
    "country_code",
    "source_risk_level",
    "creator_status",
    "campaign_status",
    "outreach_status",
    "claims_check_status",
    "job_status",
    "user_role",
    "contract_status",
    "payout_status",
}

MINIMUM_SEED_COUNTS = {
    "scoring_rule": 8,
    "ai_model_config": 5,
    "keyword_seed": 15,
}
