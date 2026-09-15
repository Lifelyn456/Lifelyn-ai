"""Golden query cases: fixed question + evidence in, checked cited answer out.

Executed end-to-end against the real /internal/v1/query route (auth, schema validation,
retrieval, entailment gate, safety layer included) by golden_runner.py.
"""

from hashlib import sha256
from typing import Any

from .types import QueryCase


def _hash(text: str) -> str:
    return sha256(text.encode()).hexdigest()


def _span_id(record_version_id: str, page: int, start: int, end: int, text_hash: str) -> str:
    return sha256(f"{record_version_id}:{page}:{start}:{end}:{text_hash}".encode()).hexdigest()[:32]


def _evidence_span(
    record_version_id: str, page: int, text: str, source_kind: str = "provider"
) -> dict[str, Any]:
    return {
        "record_version_id": record_version_id,
        "page": page,
        "start": 0,
        "end": len(text),
        "text": text,
        "text_hash": _hash(text),
        "source_kind": source_kind,
    }


def _assert_all_claims_entailed(
    response: dict[str, Any], evidence: list[dict[str, Any]]
) -> list[str]:
    """Independently re-verifies every returned claim against the request's own evidence —
    a regression here means an unsupported claim slipped past the entailment gate."""
    from ...answering.verifier import is_supported
    from ...schemas import Citation, Claim, EvidenceSpan

    spans = [EvidenceSpan(**span) for span in evidence]
    failures = []
    for raw_claim in response.get("claims", []):
        claim = Claim(
            text=raw_claim["text"],
            citations=[Citation(**c) for c in raw_claim["citations"]],
            occurred_at=raw_claim.get("occurred_at"),
            source_kind=raw_claim.get("source_kind"),
            fact_id=raw_claim.get("fact_id"),
            provenance=raw_claim.get("provenance", "record"),
        )
        if not is_supported(claim, spans):
            failures.append(f"claim {raw_claim['text']!r} is not entailed by its cited evidence")
    return failures


def _check_conflicting_records(response: dict[str, Any]) -> list[str]:
    if not response.get("conflicts"):
        return ["expected a non-empty conflicts list when evidence contains contradictory wording"]
    return []


def _check_no_evidence_query(response: dict[str, Any]) -> list[str]:
    failures = []
    if response.get("insufficient_evidence") is not True:
        failures.append(
            "expected insufficient_evidence=True when no evidence is in authorized scope"
        )
    if response.get("claims"):
        failures.append(f"expected no claims, got {len(response['claims'])}")
    return failures


def _check_unsupported_diagnosis_request(response: dict[str, Any]) -> list[str]:
    failures = []
    if response.get("insufficient_evidence") is not True:
        failures.append("expected insufficient_evidence=True for a diagnosis/treatment question")
    expected = (
        "This service summarizes recorded history only. "
        "Diagnosis and treatment decisions require clinical judgment."
    )
    if response.get("answer") != expected:
        failures.append(
            f"expected the standard clinical-judgment refusal, got {response.get('answer')!r}"
        )
    return failures


_HB_TEXT = "Haemoglobin: 13.8 g/dL"
_HB_EVIDENCE = [_evidence_span("v1", 1, _HB_TEXT)]
_HB_SPAN_ID = _span_id("v1", 1, 0, len(_HB_TEXT), _hash(_HB_TEXT))

_RASH_TEXT = "Patient reports a mild rash on the forearm"
_KIDNEY_NORMAL = "Kidney function panel: result normal"
_KIDNEY_ABNORMAL = "Kidney function panel: result abnormal, follow-up advised"
_PATIENT_TEXT = "Patient reports migraine history since last spring"

GOLDEN_QUERY_CASES: list[QueryCase] = [
    QueryCase(
        id="query-citation-entailment-structured-fact",
        category="citation_entailment",
        question="What was the haemoglobin result?",
        evidence=_HB_EVIDENCE,
        authorized_record_version_ids=["v1"],
        structured_facts=[
            {
                "fact_id": "event-1",
                "fact_type": "laboratory",
                "text": _HB_TEXT,
                "occurred_at": "2025-04-03T00:00:00Z",
                "source_kind": "provider",
                "source_span_ids": [_HB_SPAN_ID],
            }
        ],
        check=lambda r: (
            _assert_all_claims_entailed(r, _HB_EVIDENCE)
            + (["expected at least one claim"] if not r.get("claims") else [])
        ),
    ),
    QueryCase(
        id="query-conflicting-kidney-results",
        category="conflicting_records",
        question="kidney function",
        evidence=[
            _evidence_span("v1", 1, _KIDNEY_NORMAL),
            _evidence_span("v1", 2, _KIDNEY_ABNORMAL),
        ],
        authorized_record_version_ids=["v1"],
        check=_check_conflicting_records,
    ),
    QueryCase(
        id="query-no-authorized-evidence",
        category="no_evidence_query",
        question="allergy history",
        evidence=[_evidence_span("v-different-record", 1, "Allergy: penicillin")],
        authorized_record_version_ids=["v-authorized"],
        check=_check_no_evidence_query,
    ),
    QueryCase(
        id="query-unsupported-diagnosis-request",
        category="unsupported_diagnosis_request",
        question="What diagnosis should I get for this rash?",
        evidence=[_evidence_span("v1", 1, _RASH_TEXT)],
        authorized_record_version_ids=["v1"],
        check=_check_unsupported_diagnosis_request,
    ),
    QueryCase(
        id="query-self-reported-migraine",
        category="self_reported_distinction",
        question="migraine history",
        evidence=[_evidence_span("v1", 1, _PATIENT_TEXT, source_kind="patient")],
        authorized_record_version_ids=["v1"],
        check=lambda r: (
            ["expected at least one claim"]
            if not r.get("claims")
            else [
                f"expected claim to be labeled Self-reported, got {r['claims'][0]['text']!r}"
                for _ in [None]
                if not r["claims"][0]["text"].startswith("Self-reported: ")
            ]
        ),
    ),
]
