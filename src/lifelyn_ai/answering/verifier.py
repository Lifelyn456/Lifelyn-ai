"""Deterministic entailment gate for extractive claims."""

from hashlib import sha256

from ..schemas import Claim, EvidenceSpan


def is_supported(claim: Claim, evidence: list[EvidenceSpan]) -> bool:
    """Accept only claims whose complete text is present in a cited source span."""
    sources = {
        sha256(
            f"{span.record_version_id}:{span.page}:{span.start}:{span.end}:{span.text_hash}".encode()
        ).hexdigest()[:32]: span
        for span in evidence
    }
    claim_text = (
        claim.text.removeprefix("Self-reported: ").removeprefix("Patient-corrected: ").strip()
    )
    if not claim.citations:
        return False
    for citation in claim.citations:
        span = sources.get(citation.span_id)
        if (
            span is None
            or span.record_version_id != citation.record_version_id
            or span.page != citation.page
        ):
            return False
        if claim.provenance != "patient-correction" and claim_text not in " ".join(
            span.text.split()
        ):
            return False
    return True
