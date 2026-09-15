"""Stable page-span construction."""

from hashlib import sha256

from ..schemas import IngestCitation
from .extractor import FACT


def page_citation(record_version_id: str, page: int, text: str) -> IngestCitation:
    return IngestCitation(
        span_id=f"page-{page}",
        record_version_id=record_version_id,
        page=page,
        start=0,
        end=len(text),
        text=text,
        text_hash=sha256(text.encode()).hexdigest(),
    )


def fact_citations(record_version_id: str, page: int, text: str) -> list[IngestCitation]:
    citations = []
    for match in FACT.finditer(text):
        start, end = match.start(1), match.end(2)
        excerpt = text[start:end]
        text_hash = sha256(excerpt.encode()).hexdigest()
        stable = sha256(f"{page}:{start}:{end}:{text_hash}".encode()).hexdigest()[:24]
        citations.append(
            IngestCitation(
                span_id=f"fact-{stable}",
                record_version_id=record_version_id,
                page=page,
                start=start,
                end=end,
                text=excerpt,
                text_hash=text_hash,
            )
        )
    return citations
