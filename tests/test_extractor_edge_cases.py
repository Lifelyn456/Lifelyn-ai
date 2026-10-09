"""Direct tests for the deterministic extractor. All inputs are synthetic and fictional."""

import pytest

from lifelyn_ai.evals.datasets.types import REQUIRED_CATEGORIES
from lifelyn_ai.evals.golden_runner import run_golden_suite
from lifelyn_ai.ingestion.extractor import HEADER_LABELS, extract, extract_entities
from lifelyn_ai.ingestion.pipeline import run_ingestion

SPAN = "fact-test"


def _observations(text: str):
    return [e for e in extract_entities(text, SPAN) if e.entity_type == "Observation"]


@pytest.mark.parametrize(
    ("text", "name", "value", "unit"),
    [
        ("2025-04-03\nHbA1c: 6.1 %", "HbA1c", 6.1, "%"),
        ("2025-04-03\nVitamin B12: 410 pg/mL", "Vitamin B12", 410.0, "pg/mL"),
        ("2025-04-03\nFactor VIII: 95 IU/dL", "Factor VIII", 95.0, "IU/dL"),
        ("2025-04-03\nLDL-C: 3.2 mmol/L", "LDL-C", 3.2, "mmol/L"),
        ("2025-04-03\nBase excess: -2.1 mmol/L", "Base excess", -2.1, "mmol/L"),
        ("2025-04-03\nCreatinine: 88 µmol/L", "Creatinine", 88.0, "µmol/L"),
        ("2025-04-03\nWhite cell count: 6.4 x10^9/L", "White cell count", 6.4, "x10^9/L"),
        ("2025-04-03\nWeight: 70", "Weight", 70.0, None),
    ],
)
def test_lab_values_are_extracted_with_their_units(text, name, value, unit):
    (observation,) = _observations(text)
    assert (observation.name, observation.value_numeric, observation.unit) == (name, value, unit)


@pytest.mark.parametrize(
    "text",
    [
        "2025-04-03\nDate: 2025-04-03",
        "2025-04-03\nPhone: 5551234567",
        "2025-04-03\nMRN: 00012345",
        "2025-04-03\nPatient ID: 99887766",
        "2025-04-03\nEmail: someone@example.invalid",
        "2025-04-03\nAddress: 1 Example Street",
    ],
)
def test_header_and_identifier_lines_never_become_facts(text):
    assert extract_entities(text, SPAN) == []
    assert extract(text, SPAN, "CLINICAL_DOCUMENT", "provider") == []


@pytest.mark.parametrize(
    "value",
    ["2025-04-03", "5.9 mmol/L (H)", "120/80 mmHg", "12 / 14", "- 3"],
)
def test_values_that_are_not_a_plain_quantity_are_not_structured(value):
    assert _observations(f"2025-04-03\nSomething: {value}") == []


def test_every_header_label_is_lowercase_so_matching_is_case_insensitive():
    assert all(label == label.casefold() for label in HEADER_LABELS)
    assert _observations("2025-04-03\nPHONE: 5551234567") == []


def test_a_fact_without_a_date_produces_no_timeline_event():
    assert extract("HbA1c: 6.1 %", SPAN, "LAB_RESULT", "provider") == []


def test_dates_in_other_formats_are_not_guessed():
    for text in ("03/04/2025\nCondition: Asthma", "2025.04.03\nCondition: Asthma"):
        assert run_ingestion("record", [text], "provider")["events"] == []


def test_pipeline_citations_have_matching_hashes_for_new_label_shapes():
    from hashlib import sha256

    result = run_ingestion("record", ["2025-04-03\nHbA1c: 6.1 %"], "provider")
    assert result["citations"]
    for citation in result["citations"]:
        assert sha256(citation["text"].encode()).hexdigest() == citation["textHash"]


def test_golden_report_has_a_score_for_every_required_category(monkeypatch):
    report = run_golden_suite(monkeypatch)
    scores = report.category_scores
    assert REQUIRED_CATEGORIES <= set(scores)
    assert all(passed == total for passed, total in scores.values()), report.summary()
    assert sum(total for _, total in scores.values()) == len(report.results)
