"""Exact source provenance primitives. A hash alone does not prove claim entailment."""

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class SourceSpan:
    record_version_id: str
    page: int
    start: int
    end: int
    text: str
    text_hash: str


def create_span(record_version_id: str, page: int, text: str, start: int, end: int) -> SourceSpan:
    if not record_version_id or page < 1 or not 0 <= start < end <= len(text):
        raise ValueError("INVALID_SOURCE_SPAN")
    excerpt = text[start:end]
    return SourceSpan(
        record_version_id, page, start, end, excerpt, sha256(excerpt.encode("utf-8")).hexdigest()
    )


def validate_span(span: SourceSpan, source_text: str, authorized_versions: set[str]) -> bool:
    if span.record_version_id not in authorized_versions:
        return False
    if span.page < 1 or not 0 <= span.start < span.end <= len(source_text):
        return False
    actual = source_text[span.start : span.end]
    return actual == span.text and sha256(actual.encode("utf-8")).hexdigest() == span.text_hash
