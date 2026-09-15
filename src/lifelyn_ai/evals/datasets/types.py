"""Shared types for the golden eval dataset. A case pairs a fixed input with an
independent check of the pipeline's actual output — the same shape a human reviewer
would use to grade a golden example by hand."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

# The eight categories PRD section 20 requires the golden dataset to cover.
REQUIRED_CATEGORIES = frozenset(
    {
        "extraction_accuracy",
        "dates_units",
        "source_span_fidelity",
        "conflicting_records",
        "no_evidence_query",
        "unsupported_diagnosis_request",
        "citation_entailment",
        "self_reported_distinction",
    }
)


@dataclass(frozen=True)
class IngestCase:
    id: str
    category: str
    pages: list[str]
    source_kind: Literal["provider", "patient", "import"]
    # Returns a list of human-readable failure messages; empty means the case passed.
    check: Callable[[dict[str, Any]], list[str]]


@dataclass(frozen=True)
class QueryCase:
    id: str
    category: str
    question: str
    evidence: list[dict[str, Any]]
    authorized_record_version_ids: list[str]
    structured_facts: list[dict[str, Any]] = field(default_factory=list)
    check: Callable[[dict[str, Any]], list[str]] = lambda _response: []


@dataclass(frozen=True)
class CaseResult:
    id: str
    category: str
    passed: bool
    failures: list[str]
