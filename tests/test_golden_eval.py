"""CI gate: the golden eval suite must fully pass and cover every required category.

PRD section 20 requires a golden synthetic dataset covering extraction accuracy, dates/units,
source span fidelity, conflicting records, no-evidence queries, unsupported diagnosis requests,
citation entailment, and self-reported/provider-sourced distinction — and section 21 requires
CI to block merges on a grounding/citation regression. This test is that gate: it runs as part
of `pytest`, which CI already runs and requires to pass before merge.
"""

from lifelyn_ai.evals.datasets.types import REQUIRED_CATEGORIES
from lifelyn_ai.evals.golden_runner import run_golden_suite

GROUNDING_THRESHOLD = 1.0


def test_golden_dataset_covers_every_required_category():
    from lifelyn_ai.evals.datasets.ingest_cases import GOLDEN_INGEST_CASES
    from lifelyn_ai.evals.datasets.query_cases import GOLDEN_QUERY_CASES

    covered = {case.category for case in GOLDEN_INGEST_CASES} | {
        case.category for case in GOLDEN_QUERY_CASES
    }
    missing = REQUIRED_CATEGORIES - covered
    assert not missing, f"golden dataset is missing required categories: {sorted(missing)}"


def test_golden_suite_passes_at_or_above_threshold(monkeypatch):
    report = run_golden_suite(monkeypatch)
    assert report.score >= GROUNDING_THRESHOLD, report.summary()
