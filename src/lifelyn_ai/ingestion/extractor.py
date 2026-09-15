"""Deterministic conservative extraction; provider-backed models can implement the same interface."""

import re
from datetime import UTC, datetime
from typing import Literal

from ..schemas import IngestEntity, IngestEvent

DATE = re.compile(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b")
FACT = re.compile(r"(?im)^[ \t]*([A-Za-z][A-Za-z /()-]{2,80})[ \t]*:[ \t]*([^\r\n]{1,200})$")
QUANTITY = re.compile(r"^(-?\d+(?:\.\d+)?)\s*([A-Za-z%/µμ0-9.^-]{0,30})$")


def extract(
    page_text: str,
    span_id: str,
    document_type: str,
    source_kind: Literal["provider", "patient", "import"],
) -> list[IngestEvent]:
    date_match = DATE.search(page_text)
    # A missing source date is not replaced with processing time: doing so would
    # fabricate clinical chronology. Undated facts remain in the original source
    # and can be reviewed, but are not emitted as timeline events.
    if not date_match:
        return []
    occurred = datetime.fromisoformat("-".join(date_match.groups())).replace(tzinfo=UTC)
    events: list[IngestEvent] = []
    for match in FACT.finditer(page_text):
        label = match.group(1).strip()
        if label.casefold() in {"patient", "provider", "laboratory", "date", "address"}:
            continue
        events.append(
            IngestEvent(
                event_type=document_type,
                occurred_at=occurred,
                certainty="confirmed",
                source_kind=source_kind,
                self_reported=source_kind == "patient",
                display=match.group(0).strip(),
                source_span_ids=[span_id],
            )
        )
    return events


def extract_entities(page_text: str, span_id: str) -> list[IngestEntity]:
    """Normalize only explicit label/value facts without inferring clinical meaning."""
    date_match = DATE.search(page_text)
    occurred = (
        datetime.fromisoformat("-".join(date_match.groups())).replace(tzinfo=UTC)
        if date_match
        else None
    )
    entities: list[IngestEntity] = []
    for match in FACT.finditer(page_text):
        label, value = match.group(1).strip(), match.group(2).strip()
        normalized = label.casefold()
        if normalized in {"allergy", "allergies"}:
            entities.append(
                IngestEntity(
                    entity_type="Allergy",
                    name=value,
                    occurred_at=occurred,
                    source_span_ids=[span_id],
                )
            )
        elif normalized in {"medication", "medicine", "drug"}:
            entities.append(
                IngestEntity(
                    entity_type="MedicationStatement",
                    name=value,
                    occurred_at=occurred,
                    source_span_ids=[span_id],
                )
            )
        elif normalized in {"condition", "diagnosis"}:
            entities.append(
                IngestEntity(
                    entity_type="Condition",
                    name=value,
                    occurred_at=occurred,
                    source_span_ids=[span_id],
                )
            )
        elif normalized == "encounter" and occurred:
            entities.append(
                IngestEntity(
                    entity_type="Encounter",
                    name=value,
                    occurred_at=occurred,
                    source_span_ids=[span_id],
                )
            )
        elif normalized == "procedure":
            entities.append(
                IngestEntity(
                    entity_type="Procedure",
                    name=value,
                    occurred_at=occurred,
                    source_span_ids=[span_id],
                )
            )
        elif normalized in {"immunization", "vaccination", "vaccine"}:
            entities.append(
                IngestEntity(
                    entity_type="Immunization",
                    name=value,
                    occurred_at=occurred,
                    source_span_ids=[span_id],
                )
            )
        else:
            quantity = QUANTITY.fullmatch(value)
            if quantity and occurred:
                entities.append(
                    IngestEntity(
                        entity_type="Observation",
                        name=label,
                        value_numeric=float(quantity.group(1)),
                        unit=quantity.group(2) or None,
                        occurred_at=occurred,
                        source_span_ids=[span_id],
                    )
                )
    return entities
