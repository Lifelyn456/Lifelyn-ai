"""Deterministic grounding metrics used by CI."""

from ..schemas import QueryResponse


def grounding_score(response: QueryResponse) -> float:
    if not response.claims:
        return 1.0 if response.insufficient_evidence else 0.0
    return sum(bool(claim.citations) for claim in response.claims) / len(response.claims)
