"""Deterministic question routing without making a clinical decision."""

import re
from typing import Literal

QuestionKind = Literal["record-retrieval", "trend-comparison", "timeline"]


def classify_question(question: str) -> QuestionKind:
    terms = set(re.findall(r"[a-z0-9]+", question.casefold()))
    if terms & {"trend", "change", "changed", "compare", "comparison", "higher", "lower"}:
        return "trend-comparison"
    if terms & {"timeline", "when", "chronology", "history", "recent", "latest"}:
        return "timeline"
    return "record-retrieval"
