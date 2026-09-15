"""Conservative document classification."""


def classify(text: str) -> str:
    lowered = text.casefold()
    if any(term in lowered for term in ("reference interval", "laboratory", "lab result")):
        return "LAB_RESULT"
    if any(term in lowered for term in ("prescription", "medication")):
        return "MEDICATION"
    if any(term in lowered for term in ("consultation", "assessment")):
        return "CONSULTATION"
    return "CLINICAL_DOCUMENT"
