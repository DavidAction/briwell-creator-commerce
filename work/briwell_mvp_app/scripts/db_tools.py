from __future__ import annotations

from pathlib import Path
import shutil
from urllib.parse import parse_qsl
from urllib.parse import quote
from urllib.parse import urlencode
from urllib.parse import urlsplit
from urllib.parse import urlunsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORTABLE_PG_BIN = ROOT.parent / "postgresql-17.10-portable" / "pgsql" / "bin"


def resolve_pg_tool(tool_name: str, pg_bin_dir: str | None = None) -> str:
    candidates: list[Path] = []
    if pg_bin_dir:
        candidates.append(Path(pg_bin_dir) / executable_name(tool_name))
    candidates.append(DEFAULT_PORTABLE_PG_BIN / executable_name(tool_name))

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    found = shutil.which(executable_name(tool_name)) or shutil.which(tool_name)
    if found:
        return found
    raise FileNotFoundError(f"Could not find PostgreSQL tool: {tool_name}")


def executable_name(tool_name: str) -> str:
    if tool_name.endswith(".exe"):
        return tool_name
    return f"{tool_name}.exe"


def database_name_from_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    name = parsed.path.lstrip("/")
    if not name:
        raise ValueError("Database URL must include a database name.")
    return name


def database_url_for_name(database_url: str, database_name: str) -> str:
    parsed = urlsplit(database_url)
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            f"/{quote(database_name)}",
            parsed.query,
            parsed.fragment,
        )
    )


def maintenance_database_url(database_url: str) -> str:
    return database_url_for_name(database_url, "postgres")


def redact_database_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if "@" not in parsed.netloc:
        return database_url
    credentials, host = parsed.netloc.rsplit("@", 1)
    if ":" in credentials:
        user, _password = credentials.split(":", 1)
        redacted_netloc = f"{user}:***@{host}"
    else:
        redacted_netloc = f"***@{host}"
    return urlunsplit((parsed.scheme, redacted_netloc, parsed.path, parsed.query, parsed.fragment))


def database_url_with_param(database_url: str, key: str, value: str) -> str:
    parsed = urlsplit(database_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[key] = value
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )
