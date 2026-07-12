"""Server-side text extraction for ZIP-based document uploads (P12).

docx / pptx / hwpx / xlsx are all ZIP containers holding XML parts, so their
text is extractable with the standard library alone — no third-party parser,
no new dependency surface on partner-supplied files. Extracted text feeds
the live AI classification/extraction paths, upgrading those formats from
"filename-only" honesty caveats to real content analysis.

HWP 5.x (OLE compound files) is deliberately NOT parsed here: a hand-rolled
OLE reader on hostile input is a security liability, and the vetted parsers
target Python versions we don't run. `.hwp` stays metadata-only with its
existing honest caveat until a maintained library is adopted.

Extraction is defensive by design: any parse failure returns None (the
caller keeps the metadata-only path and says so) — a malformed document must
never take the ingestion pipeline down.
"""

import io
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

# Upload validation already caps files at settings.partner_upload_max_bytes,
# but decompressed XML can be much larger (zip bombs) — cap what we read.
MAX_PART_BYTES = 4_000_000
MAX_PARTS = 200
MAX_TEXT_CHARS = 40_000

EXTRACTABLE_SUFFIXES = {".docx", ".pptx", ".hwpx", ".xlsx"}

# Which archive parts carry body text, per format.
_PART_PATTERNS = {
    ".docx": re.compile(r"^word/(document|header\d*|footer\d*)\.xml$"),
    ".pptx": re.compile(r"^ppt/(slides/slide\d+|notesSlides/notesSlide\d+)\.xml$"),
    ".hwpx": re.compile(r"^Contents/section\d+\.xml$"),
    ".xlsx": re.compile(r"^xl/sharedStrings\.xml$"),
}

# Text-bearing XML localnames per format (namespace-agnostic matching):
# w:t (docx), a:t (pptx), hp:t (hwpx), si//t (xlsx sharedStrings).
_TEXT_LOCALNAME = "t"


def _part_sort_key(name: str) -> tuple[str, int]:
    match = re.search(r"(\d+)\.xml$", name)
    return (re.sub(r"\d+\.xml$", "", name), int(match.group(1)) if match else 0)


def _text_from_xml(data: bytes) -> list[str]:
    """Collect text nodes from one XML part, paragraph-ish per element."""

    chunks: list[str] = []
    # Office XML parts never carry a DTD; a document that does is hostile
    # (entity-expansion / billion-laughs) — skip the part, keep the rest.
    # Scan the whole part: a prolog can legally be pushed past any fixed
    # prefix with comments/whitespace, and parts are already size-capped.
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        return chunks
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        return chunks
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == _TEXT_LOCALNAME and element.text:
            chunks.append(element.text)
    return chunks


def extract_document_text(storage_path: str | Path, filename: str) -> dict[str, Any] | None:
    """Extract readable text from a stored ZIP-based document.

    Returns {"text", "suffix", "part_count", "truncated"} or None when the
    format is out of scope or the file cannot be parsed (caller falls back
    to the metadata-only path and says so honestly)."""

    suffix = Path(filename or "").suffix.lower()
    pattern = _PART_PATTERNS.get(suffix)
    if pattern is None:
        return None
    path = Path(storage_path)
    if not path.is_file():
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as archive:
            names = [name for name in archive.namelist() if pattern.match(name)]
            names.sort(key=_part_sort_key)
            chunks: list[str] = []
            for name in names[:MAX_PARTS]:
                info = archive.getinfo(name)
                if info.file_size > MAX_PART_BYTES:
                    continue
                with archive.open(name) as part:
                    chunks.extend(_text_from_xml(part.read(MAX_PART_BYTES)))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError):
        return None

    text = "\n".join(chunk.strip() for chunk in chunks if chunk.strip())
    if not text:
        return None
    truncated = len(text) > MAX_TEXT_CHARS
    return {
        "text": text[:MAX_TEXT_CHARS],
        "suffix": suffix,
        "part_count": len(names),
        "truncated": truncated,
    }
