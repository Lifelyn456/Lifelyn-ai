"""Hybrid lexical and private-provider semantic retrieval over authorized evidence."""

import math
import re

from ..providers.embeddings import EmbeddingProvider
from ..schemas import EvidenceSpan


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    return numerator / denominator if denominator else 0.0


async def search(
    question: str,
    evidence: list[EvidenceSpan],
    provider: EmbeddingProvider | None,
    limit: int = 5,
) -> list[tuple[EvidenceSpan, float]]:
    terms = {word for word in re.findall(r"[a-z0-9]+", question.casefold()) if len(word) > 2}
    lexical: list[float] = []
    for span in evidence:
        words = set(re.findall(r"[a-z0-9]+", span.text.casefold()))
        overlap = len(terms & words)
        lexical.append(min(1.0, overlap / max(1, len(terms))))
    if provider is None:
        ranked = [(span, score) for span, score in zip(evidence, lexical, strict=True) if score]
        return sorted(ranked, key=lambda item: item[1], reverse=True)[:limit]
    vectors = await provider.embed([question, *(span.text for span in evidence)])
    if len(vectors) != len(evidence) + 1:
        raise ValueError("Embedding provider returned an invalid result")
    question_vector, evidence_vectors = vectors[0], vectors[1:]
    if any(len(vector) != len(question_vector) for vector in evidence_vectors):
        raise ValueError("Embedding provider returned inconsistent dimensions")
    combined = []
    for span, lexical_score, vector in zip(evidence, lexical, evidence_vectors, strict=True):
        semantic_score = max(0.0, min(1.0, (_cosine(question_vector, vector) + 1) / 2))
        score = 0.45 * lexical_score + 0.55 * semantic_score
        combined.append((span, score))
    return sorted(combined, key=lambda item: item[1], reverse=True)[:limit]
