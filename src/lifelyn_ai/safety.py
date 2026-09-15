UNSUPPORTED_TERMS = (
    "diagnose",
    "diagnosis",
    "prescribe",
    "prescription",
    "treatment",
    "should i take",
    "dose",
)


def is_unsupported(question: str) -> bool:
    lowered = question.casefold()
    return any(term in lowered for term in UNSUPPORTED_TERMS)


def insufficient(question: str) -> str:
    if is_unsupported(question):
        return "This service summarizes recorded history only. Diagnosis and treatment decisions require clinical judgment."
    return (
        "There is not enough authorized evidence in the provided records to answer that question."
    )
