from app.core.db_contract import MINIMUM_SEED_COUNTS
from app.core.db_contract import REQUIRED_ENUMS
from app.core.db_contract import REQUIRED_TABLES
from scripts.bootstrap_db import file_checksum
from scripts.bootstrap_db import sql_files


def test_bootstrap_sql_files_include_migration_and_seed() -> None:
    without_seeds = [path.name for path in sql_files(include_seeds=False)]
    with_seeds = [path.name for path in sql_files(include_seeds=True)]

    assert "001_initial_schema.sql" in without_seeds
    assert "003_keyword_seed_uniqueness.sql" in without_seeds
    assert "001_seed_data.sql" not in without_seeds
    assert "001_seed_data.sql" in with_seeds


def test_db_contract_tracks_required_runtime_objects() -> None:
    assert "creator" in REQUIRED_TABLES
    assert "outreach" in REQUIRED_TABLES
    assert "ai_model_config" in REQUIRED_TABLES
    assert "country_code" in REQUIRED_ENUMS
    assert "source_risk_level" in REQUIRED_ENUMS
    assert MINIMUM_SEED_COUNTS["scoring_rule"] >= 8


def test_file_checksum_is_stable_for_seed_file() -> None:
    first = file_checksum(sql_files(include_seeds=True)[0])
    second = file_checksum(sql_files(include_seeds=True)[0])

    assert first == second
    assert len(first) == 64
