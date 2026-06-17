from __future__ import annotations

import csv
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "db" / "seeds"

ALLOWED_COUNTRIES = {"MX", "PE", "EC"}
ALLOWED_PRODUCT_CATEGORIES = {
    "sunscreen",
    "calming_serum",
    "cleanser",
    "sheet_mask",
    "cushion_foundation",
}
ALLOWED_INTENTS = {"discovery", "concern", "format", "commerce"}
ALLOWED_SOURCE_RISK = {"low", "low_medium", "medium"}

EXPECTED_HEADERS = {
    "keyword_seed_v0.csv": [
        "country",
        "language",
        "product_category",
        "intent_type",
        "keyword",
        "hashtag",
        "priority",
        "notes",
    ],
    "briwell_creator_import_template.csv": [
        "country",
        "username",
        "profile_url",
        "source_type",
        "source_url",
        "source_risk_level",
        "collected_at",
        "display_name",
        "bio",
        "language",
        "follower_count",
        "following_count",
        "total_likes",
        "contact_email",
        "instagram_url",
        "whatsapp",
        "category_tags",
        "notes",
    ],
    "briwell_video_import_template.csv": [
        "creator_username",
        "url",
        "source_type",
        "source_url",
        "source_risk_level",
        "collected_at",
        "platform_video_id",
        "caption",
        "hashtags",
        "posted_at",
        "view_count",
        "like_count",
        "comment_count",
        "share_count",
        "save_count",
        "duration_seconds",
        "thumbnail_url",
        "notes",
    ],
    "briwell_comment_sample_template.csv": [
        "creator_username",
        "video_url",
        "comment_text",
        "sample_method",
        "source_risk_level",
        "collected_at",
        "comment_language",
        "like_count",
        "reply_count",
        "notes",
    ],
}


class CsvValidationError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise CsvValidationError(f"{path.name}: missing header")
        expected = EXPECTED_HEADERS.get(path.name)
        if expected is not None and reader.fieldnames != expected:
            raise CsvValidationError(
                f"{path.name}: header mismatch. expected={expected} actual={reader.fieldnames}"
            )
        return list(reader)


def validate_keyword_seed(path: Path) -> list[str]:
    rows = read_csv(path)
    errors: list[str] = []
    seen: set[tuple[str, str, str, str]] = set()

    for index, row in enumerate(rows, start=2):
        country = row["country"]
        category = row["product_category"]
        intent = row["intent_type"]
        keyword = row["keyword"]
        hashtag = row["hashtag"]

        if country not in ALLOWED_COUNTRIES:
            errors.append(f"{path.name}:{index}: invalid country {country}")
        if category not in ALLOWED_PRODUCT_CATEGORIES:
            errors.append(f"{path.name}:{index}: invalid product_category {category}")
        if intent not in ALLOWED_INTENTS:
            errors.append(f"{path.name}:{index}: invalid intent_type {intent}")
        if not keyword and not hashtag:
            errors.append(f"{path.name}:{index}: keyword or hashtag required")
        try:
            priority = int(row["priority"])
        except ValueError:
            errors.append(f"{path.name}:{index}: priority must be integer")
        else:
            if priority < 1 or priority > 5:
                errors.append(f"{path.name}:{index}: priority must be 1-5")

        key = (country, category, keyword.lower(), hashtag.lower())
        if key in seen:
            errors.append(f"{path.name}:{index}: duplicate keyword/hashtag seed {key}")
        seen.add(key)

    return errors


def validate_template(path: Path) -> list[str]:
    rows = read_csv(path)
    errors: list[str] = []
    for index, row in enumerate(rows, start=2):
        risk = row.get("source_risk_level", "")
        if risk and risk not in ALLOWED_SOURCE_RISK:
            errors.append(f"{path.name}:{index}: source_risk_level not allowed: {risk}")
    return errors


def validate_all() -> list[str]:
    errors: list[str] = []
    errors.extend(validate_keyword_seed(SEEDS / "keyword_seed_v0.csv"))

    output_dir = ROOT.parents[1] / "outputs"
    for name in (
        "briwell_creator_import_template.csv",
        "briwell_video_import_template.csv",
        "briwell_comment_sample_template.csv",
    ):
        errors.extend(validate_template(output_dir / name))
    return errors


def main() -> int:
    errors = validate_all()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("CSV validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
