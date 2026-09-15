"""Page-text-to-structured-facts pipeline, decoupled from PDF/OCR parsing so it can be
exercised directly by golden eval cases and by the ingest route."""

import os
import re
from typing import Literal

from .citations import fact_citations, page_citation
from .classifier import classify
from .extractor import extract, extract_entities

DATE_IN_TEXT = re.compile(r"\b20\d{2}[-/](?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])\b")


def run_ingestion(
    record_version_id: str,
    pages: list[str],
    source_kind: Literal["provider", "patient", "import"] = "provider",
) -> dict:
    citations = []
    citation_context: dict[str, str] = {}
    for index, page_text in enumerate(pages, 1):
        if not page_text:
            continue
        page_facts = fact_citations(record_version_id, index, page_text)
        if not page_facts:
            page_facts = [page_citation(record_version_id, index, page_text)]
        date_match = DATE_IN_TEXT.search(page_text)
        for citation in page_facts:
            citations.append(citation)
            citation_context[citation.span_id] = (
                f"{date_match.group(0)}\n{citation.text}" if date_match else citation.text
            )
    document_type = classify("\n".join(pages))
    events = []
    entities = []
    for citation in citations:
        context = citation_context[citation.span_id]
        events.extend(extract(context, citation.span_id, document_type, source_kind))
        entities.extend(extract_entities(context, citation.span_id))
    valid_ids = {citation.span_id for citation in citations}
    events = [
        event
        for event in events
        if event.source_span_ids and all(span in valid_ids for span in event.source_span_ids)
    ]
    entities = [
        entity
        for entity in entities
        if entity.source_span_ids and all(span in valid_ids for span in entity.source_span_ids)
    ]
    return {
        "schemaVersion": "1.0",
        "recordVersionId": record_version_id,
        "events": [event.model_dump(mode="json") for event in events],
        "entities": [entity.model_dump(mode="json") for entity in entities],
        "citations": [
            {
                "spanId": citation.span_id,
                "recordVersionId": citation.record_version_id,
                "page": citation.page,
                "start": citation.start,
                "end": citation.end,
                "text": citation.text,
                "textHash": citation.text_hash,
            }
            for citation in citations
        ],
        "warnings": []
        if events
        else ["No conservative structured facts were extracted; manual review is required."],
        "modelTrace": {
            "provider": "deterministic-extractive",
            "model": "native-text-first",
            "promptVersion": os.environ.get("PROMPT_VERSION", "history-v1"),
        },
    }
