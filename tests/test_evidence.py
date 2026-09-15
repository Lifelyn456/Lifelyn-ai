import asyncio
from dataclasses import replace
from hashlib import sha256

import pytest

from lifelyn_ai.evidence import create_span, validate_span
from lifelyn_ai.retrieval.hybrid_search import search
from lifelyn_ai.schemas import EvidenceSpan


def test_exact_span_and_scope():
    text = "SYNTHETIC. Allergy: penicillin."
    span = create_span("version-1", 1, text, 11, len(text))
    assert validate_span(span, text, {"version-1"})
    assert not validate_span(span, text, {"another-patient-version"})
    assert not validate_span(replace(span, text="No allergies"), text, {"version-1"})
    assert not validate_span(replace(span, text_hash="0" * 64), text, {"version-1"})


def test_invalid_boundaries():
    with pytest.raises(ValueError):
        create_span("v1", 0, "synthetic", 0, 9)
    with pytest.raises(ValueError):
        create_span("v1", 1, "synthetic", -1, 9)


def test_hybrid_search_uses_private_semantic_signal_with_lexical_score():
    class Provider:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            assert len(texts) == 3
            return [[1.0, 0.0], [-1.0, 0.0], [1.0, 0.0]]

    def span(text: str, start: int) -> EvidenceSpan:
        return EvidenceSpan(
            record_version_id="v1",
            page=1,
            start=start,
            end=start + len(text),
            text=text,
            text_hash=sha256(text.encode()).hexdigest(),
        )

    lexical_match = span("allergy result", 0)
    semantic_match = span("recorded intolerance", 20)
    ranked = asyncio.run(search("allergy", [lexical_match, semantic_match], Provider()))
    assert ranked[0][0] == semantic_match
