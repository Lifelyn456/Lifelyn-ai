"""Extended golden ingest cases (all synthetic, all fictional).

These pin the behaviour of the deterministic extractor on lab values, header blocks, dates and
multi-fact pages. Several were written after probing found real defects: labels containing digits
("HbA1c", "Vitamin B12") were silently dropped, a "Date: 2025-04-03" header became an
Observation with the unit "-04-03", and a "Phone:" line became an Observation and a timeline
event. Each of those cases fails against the extractor as it was before the fix.
"""

from collections.abc import Callable
from hashlib import sha256
from typing import Any

from .types import IngestCase

Check = Callable[[dict[str, Any]], list[str]]


def _of_type(result: dict[str, Any], entity_type: str) -> list[dict[str, Any]]:
    return [e for e in result["entities"] if e["entity_type"] == entity_type]


def _citation(result: dict[str, Any], span_id: str) -> dict[str, Any] | None:
    return next((c for c in result["citations"] if c["spanId"] == span_id), None)


def _cited_text_ok(result: dict[str, Any], entity: dict[str, Any], needle: str) -> list[str]:
    """The entity must cite a real span whose text holds the fact and whose hash is intact."""
    if len(entity["source_span_ids"]) != 1:
        return [f"expected exactly 1 source span, got {len(entity['source_span_ids'])}"]
    citation = _citation(result, entity["source_span_ids"][0])
    if citation is None:
        return ["entity cites a span that is not in the returned citations"]
    failures = []
    if needle not in citation["text"]:
        failures.append(f"cited text {citation['text']!r} does not contain {needle!r}")
    if sha256(citation["text"].encode()).hexdigest() != citation["textHash"]:
        failures.append("citation textHash does not match sha256(text)")
    return failures


def _observation(name: str, value: float, unit: str | None) -> Check:
    def check(result: dict[str, Any]) -> list[str]:
        observations = _of_type(result, "Observation")
        if len(observations) != 1:
            return [f"expected exactly 1 Observation, got {len(observations)}"]
        obs = observations[0]
        failures = []
        if obs["name"] != name:
            failures.append(f"expected name {name!r}, got {obs['name']!r}")
        if obs["value_numeric"] != value:
            failures.append(f"expected value {value!r}, got {obs['value_numeric']!r}")
        if obs["unit"] != unit:
            failures.append(f"expected unit {unit!r}, got {obs['unit']!r}")
        if len(result["events"]) != 1:
            failures.append(f"expected exactly 1 timeline event, got {len(result['events'])}")
        return failures + _cited_text_ok(result, obs, name)

    return check


def _nothing_extracted(result: dict[str, Any]) -> list[str]:
    failures = []
    if result["entities"]:
        failures.append(
            "expected no entities, got "
            f"{[(e['entity_type'], e['name'], e.get('value_numeric'), e.get('unit')) for e in result['entities']]}"
        )
    if result["events"]:
        failures.append(
            f"expected no timeline events, got {[e['display'] for e in result['events']]}"
        )
    return failures


def _header_block_ignored(result: dict[str, Any]) -> list[str]:
    # Only the clinical fact (Glucose) may survive; patient, provider, laboratory, date, address,
    # phone, MRN and ID lines describe the page or the person.
    failures = []
    names = [e["name"] for e in result["entities"]]
    if names != ["Glucose"]:
        failures.append(f"expected only the Glucose observation, got entities {names}")
    displays = [e["display"] for e in result["events"]]
    if displays != ["Glucose: 5.4 mmol/L"]:
        failures.append(f"expected only the Glucose timeline event, got {displays}")
    return failures


def _dose_preserved_verbatim(result: dict[str, Any]) -> list[str]:
    medications = _of_type(result, "MedicationStatement")
    if len(medications) != 1:
        return [f"expected exactly 1 MedicationStatement, got {len(medications)}"]
    failures = []
    if medications[0]["name"] != "Metformin 500 mg twice daily":
        failures.append(f"dose text was altered: {medications[0]['name']!r}")
    if medications[0]["value_numeric"] is not None:
        failures.append("a structured dose was invented from free text")
    return failures + _cited_text_ok(result, medications[0], "Metformin 500 mg twice daily")


def _flagged_result_not_misparsed(result: dict[str, Any]) -> list[str]:
    # "(H)" is a laboratory flag the extractor does not interpret. The source text must stay
    # visible verbatim and no structured value may be guessed from it.
    failures = []
    if _of_type(result, "Observation"):
        failures.append("a flagged result was converted into a structured Observation")
    displays = [e["display"] for e in result["events"]]
    if displays != ["Potassium: 5.9 mmol/L (H)"]:
        failures.append(f"expected the source line to stay verbatim, got {displays}")
    return failures


def _ambiguous_date_not_guessed(result: dict[str, Any]) -> list[str]:
    # 03/04/2025 is 3 April or 4 March depending on locale. It must not be guessed.
    failures = []
    if result["events"]:
        failures.append("a timeline event was created from an ambiguous date")
    conditions = _of_type(result, "Condition")
    if len(conditions) != 1:
        return failures + [f"expected exactly 1 Condition, got {len(conditions)}"]
    if conditions[0]["occurred_at"] is not None:
        failures.append(f"a date was guessed: {conditions[0]['occurred_at']!r}")
    return failures


def _import_is_not_self_reported(result: dict[str, Any]) -> list[str]:
    if len(result["events"]) != 1:
        return [f"expected exactly 1 timeline event, got {len(result['events'])}"]
    event = result["events"][0]
    failures = []
    if event["source_kind"] != "import":
        failures.append(f"expected source_kind 'import', got {event['source_kind']!r}")
    if event["self_reported"] is not False:
        failures.append("an imported record was marked self-reported")
    return failures


def _multi_fact_spans(result: dict[str, Any]) -> list[str]:
    failures = []
    expected = {
        "MedicationStatement": "Metformin",
        "Allergy": "penicillin",
        "Observation": "Glucose",
    }
    spans = []
    for entity_type, needle in expected.items():
        found = _of_type(result, entity_type)
        if len(found) != 1:
            failures.append(f"expected exactly 1 {entity_type}, got {len(found)}")
            continue
        failures.extend(_cited_text_ok(result, found[0], needle))
        spans.extend(found[0]["source_span_ids"])
    if len(set(spans)) != len(spans):
        failures.append("different facts share one source span instead of citing their own line")
    return failures


def _pages_cite_their_own_page(result: dict[str, Any]) -> list[str]:
    failures = []
    for entity_type, page in (("Condition", 1), ("Allergy", 2)):
        found = _of_type(result, entity_type)
        if len(found) != 1:
            failures.append(f"expected exactly 1 {entity_type}, got {len(found)}")
            continue
        citation = _citation(result, found[0]["source_span_ids"][0])
        if citation is None or citation["page"] != page:
            failures.append(f"{entity_type} should cite page {page}, got {citation}")
    return failures


def _entity_types(*expected: str) -> Check:
    def check(result: dict[str, Any]) -> list[str]:
        got = sorted(e["entity_type"] for e in result["entities"])
        return (
            [] if got == sorted(expected) else [f"expected entities {sorted(expected)}, got {got}"]
        )

    return check


EXTENDED_INGEST_CASES: list[IngestCase] = [
    IngestCase(
        id="ingest-lab-label-with-digits-hba1c",
        category="dates_units",
        pages=["2025-04-03\nHbA1c: 6.1 %"],
        source_kind="provider",
        check=_observation("HbA1c", 6.1, "%"),
    ),
    IngestCase(
        id="ingest-lab-label-with-digits-b12",
        category="dates_units",
        pages=["2025-04-03\nVitamin B12: 410 pg/mL"],
        source_kind="provider",
        check=_observation("Vitamin B12", 410.0, "pg/mL"),
    ),
    IngestCase(
        id="ingest-lab-negative-value",
        category="dates_units",
        pages=["2025-04-03\nBase excess: -2.1 mmol/L"],
        source_kind="provider",
        check=_observation("Base excess", -2.1, "mmol/L"),
    ),
    IngestCase(
        id="ingest-lab-compound-unit",
        category="dates_units",
        pages=["2025-04-03\nWhite cell count: 6.4 x10^9/L"],
        source_kind="provider",
        check=_observation("White cell count", 6.4, "x10^9/L"),
    ),
    IngestCase(
        id="ingest-lab-micro-sign-unit",
        category="dates_units",
        pages=["2025-04-03\nCreatinine: 88 µmol/L"],
        source_kind="provider",
        check=_observation("Creatinine", 88.0, "µmol/L"),
    ),
    IngestCase(
        id="ingest-lab-value-without-unit",
        category="dates_units",
        pages=["2025-04-03\nWeight: 70"],
        source_kind="provider",
        check=_observation("Weight", 70.0, None),
    ),
    IngestCase(
        id="ingest-date-header-is-not-an-observation",
        category="dates_units",
        pages=["2025-04-03\nDate: 2025-04-03"],
        source_kind="provider",
        check=_nothing_extracted,
    ),
    IngestCase(
        id="ingest-ambiguous-date-format-not-guessed",
        category="dates_units",
        pages=["03/04/2025\nCondition: Asthma"],
        source_kind="provider",
        check=_ambiguous_date_not_guessed,
    ),
    IngestCase(
        id="ingest-identifier-lines-are-not-facts",
        category="extraction_accuracy",
        pages=["2025-04-03\nPhone: 5551234567\nMRN: 00012345\nPatient ID: 99887766"],
        source_kind="provider",
        check=_nothing_extracted,
    ),
    IngestCase(
        id="ingest-header-block-ignored",
        category="extraction_accuracy",
        pages=[
            (
                "Patient: Jane Fictional\nProvider: Example Clinic\nLaboratory: Example Labs\n"
                "Date: 2025-04-03\nAddress: 1 Example Street\nGlucose: 5.4 mmol/L"
            )
        ],
        source_kind="provider",
        check=_header_block_ignored,
    ),
    IngestCase(
        id="ingest-medication-dose-kept-verbatim",
        category="extraction_accuracy",
        pages=["2025-04-03\nMedication: Metformin 500 mg twice daily"],
        source_kind="provider",
        check=_dose_preserved_verbatim,
    ),
    IngestCase(
        id="ingest-flagged-result-not-misparsed",
        category="extraction_accuracy",
        pages=["2025-04-03\nPotassium: 5.9 mmol/L (H)"],
        source_kind="provider",
        check=_flagged_result_not_misparsed,
    ),
    IngestCase(
        id="ingest-procedure-vaccine-encounter-types",
        category="extraction_accuracy",
        pages=["2025-04-03\nProcedure: Spirometry\nVaccine: Influenza\nEncounter: Annual review"],
        source_kind="provider",
        check=_entity_types("Procedure", "Immunization", "Encounter"),
    ),
    IngestCase(
        id="ingest-multi-fact-page-cites-each-line",
        category="source_span_fidelity",
        pages=["2025-04-03\nMedication: Metformin\nAllergy: penicillin\nGlucose: 5.4 mmol/L"],
        source_kind="provider",
        check=_multi_fact_spans,
    ),
    IngestCase(
        id="ingest-multi-page-cites-its-own-page",
        category="source_span_fidelity",
        pages=["2025-04-03\nCondition: Asthma", "2025-05-01\nAllergy: penicillin"],
        source_kind="provider",
        check=_pages_cite_their_own_page,
    ),
    IngestCase(
        id="ingest-imported-record-is-not-self-reported",
        category="self_reported_distinction",
        pages=["2025-04-03\nCondition: Hypertension"],
        source_kind="import",
        check=_import_is_not_self_reported,
    ),
]
