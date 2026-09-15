"""Golden ingest cases: fixed page text in, checked structured output out.

Exercises the real ingestion pipeline (classify -> extract -> citations -> span
validation) via run_ingestion — the same function the /internal/v1/ingest route calls
after parsing a document. PDF/OCR decoding is covered separately by parser.py's own tests.
"""

from typing import Any

from .types import IngestCase


def _entities_of_type(result: dict[str, Any], entity_type: str) -> list[dict[str, Any]]:
    return [e for e in result["entities"] if e["entity_type"] == entity_type]


def _check_extraction_accuracy(result: dict[str, Any]) -> list[str]:
    failures = []
    conditions = _entities_of_type(result, "Condition")
    if len(conditions) != 1:
        failures.append(f"expected exactly 1 Condition entity, got {len(conditions)}")
    elif conditions[0]["name"] != "Type 2 Diabetes":
        failures.append(f"expected condition name 'Type 2 Diabetes', got {conditions[0]['name']!r}")
    if len(result["events"]) != 1:
        failures.append(f"expected exactly 1 timeline event, got {len(result['events'])}")
    return failures


def _check_dates_units(result: dict[str, Any]) -> list[str]:
    failures = []
    observations = _entities_of_type(result, "Observation")
    if len(observations) != 1:
        return [f"expected exactly 1 Observation entity, got {len(observations)}"]
    obs = observations[0]
    if obs["value_numeric"] != 13.8:
        failures.append(f"expected value_numeric 13.8, got {obs['value_numeric']!r}")
    if obs["unit"] != "g/dL":
        failures.append(f"expected unit 'g/dL', got {obs['unit']!r}")
    if not str(obs["occurred_at"]).startswith("2025-04-03"):
        failures.append(
            f"expected occurred_at to start with 2025-04-03, got {obs['occurred_at']!r}"
        )
    return failures


def _check_source_span_fidelity(result: dict[str, Any]) -> list[str]:
    failures = []
    allergies = _entities_of_type(result, "Allergy")
    if len(allergies) != 1:
        return [f"expected exactly 1 Allergy entity, got {len(allergies)}"]
    span_ids = allergies[0]["source_span_ids"]
    if len(span_ids) != 1:
        failures.append(f"expected exactly 1 source span id, got {len(span_ids)}")
        return failures
    citation = next((c for c in result["citations"] if c["spanId"] == span_ids[0]), None)
    if citation is None:
        failures.append(f"entity cites span {span_ids[0]!r} which is not in the returned citations")
        return failures
    if "penicillin" not in citation["text"]:
        failures.append(f"cited span text does not contain the source fact: {citation['text']!r}")
    from hashlib import sha256

    if sha256(citation["text"].encode()).hexdigest() != citation["textHash"]:
        failures.append("citation textHash does not match sha256(text) — integrity check failed")
    return failures


def _check_self_reported_distinction(result: dict[str, Any]) -> list[str]:
    failures = []
    if len(result["events"]) != 1:
        return [f"expected exactly 1 timeline event, got {len(result['events'])}"]
    event = result["events"][0]
    if event["source_kind"] != "patient":
        failures.append(f"expected source_kind 'patient', got {event['source_kind']!r}")
    if event["self_reported"] is not True:
        failures.append("expected self_reported=True for a patient-sourced event")
    return failures


def _check_undated_fact_not_fabricated(result: dict[str, Any]) -> list[str]:
    # An undated fact must never be assigned a fabricated processing-time date; it should
    # simply not become a timeline event at all (extractor.py's documented invariant).
    if result["events"]:
        return [f"expected no timeline events for an undated fact, got {len(result['events'])}"]
    return []


GOLDEN_INGEST_CASES: list[IngestCase] = [
    IngestCase(
        id="ingest-condition-basic",
        category="extraction_accuracy",
        pages=["2025-04-03\nCondition: Type 2 Diabetes"],
        source_kind="provider",
        check=_check_extraction_accuracy,
    ),
    IngestCase(
        id="ingest-observation-units",
        category="dates_units",
        pages=["2025-04-03\nHaemoglobin: 13.8 g/dL"],
        source_kind="provider",
        check=_check_dates_units,
    ),
    IngestCase(
        id="ingest-allergy-span-fidelity",
        category="source_span_fidelity",
        pages=["2025-04-03\nAllergy: penicillin"],
        source_kind="provider",
        check=_check_source_span_fidelity,
    ),
    IngestCase(
        id="ingest-patient-self-reported",
        category="self_reported_distinction",
        pages=["2025-04-03\nCondition: Migraine"],
        source_kind="patient",
        check=_check_self_reported_distinction,
    ),
    IngestCase(
        id="ingest-undated-fact-not-fabricated",
        category="dates_units",
        pages=["Allergy: penicillin"],
        source_kind="provider",
        check=_check_undated_fact_not_fabricated,
    ),
]
