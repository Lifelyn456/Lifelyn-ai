"""Creates extractive atomic claims so every statement is directly grounded."""

from hashlib import sha256

from ..schemas import Citation, Claim, EvidenceSpan, StructuredFact


def build_claim(span: EvidenceSpan, _index: int, score: float) -> Claim:
    text = " ".join(span.text.split())[:500]
    if span.source_kind == "patient":
        text = f"Self-reported: {text}"
    return Claim(
        text=text,
        citations=[
            Citation(
                record_version_id=span.record_version_id,
                page=span.page,
                span_id=sha256(
                    f"{span.record_version_id}:{span.page}:{span.start}:{span.end}:{span.text_hash}".encode()
                ).hexdigest()[:32],
                relevance_score=score,
            )
        ],
    )


def build_structured_claim(
    fact: StructuredFact, evidence_by_id: dict[str, EvidenceSpan], score: float
) -> Claim:
    text = fact.text
    if fact.patient_corrected:
        text = f"Patient-corrected: {text}"
    elif fact.source_kind == "patient":
        text = f"Self-reported: {text}"
    return Claim(
        text=text,
        occurred_at=fact.occurred_at,
        source_kind=fact.source_kind,
        fact_id=fact.fact_id,
        provenance="patient-correction" if fact.patient_corrected else "record",
        citations=[
            Citation(
                record_version_id=evidence_by_id[span_id].record_version_id,
                page=evidence_by_id[span_id].page,
                span_id=span_id,
                relevance_score=score,
            )
            for span_id in fact.source_span_ids
        ],
    )
