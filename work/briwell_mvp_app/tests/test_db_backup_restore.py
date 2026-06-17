from datetime import datetime
from pathlib import Path

from scripts.backup_db import build_backup_path
from scripts.db_tools import database_name_from_url
from scripts.db_tools import database_url_for_name
from scripts.db_tools import redact_database_url


def test_database_url_helpers_redact_password_and_swap_database() -> None:
    url = "postgresql://briwell:secret@127.0.0.1:55432/briwell"

    assert database_name_from_url(url) == "briwell"
    assert database_url_for_name(url, "restore_test").endswith("/restore_test")
    assert redact_database_url(url) == "postgresql://briwell:***@127.0.0.1:55432/briwell"


def test_build_backup_path_uses_database_name_and_timestamp() -> None:
    path = build_backup_path(
        Path("backups"),
        "briwell",
        datetime(2026, 6, 17, 15, 30, 45),
    )

    assert path == Path("backups") / "briwell_20260617_153045.dump"
