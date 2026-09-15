"""Conservative FHIR R4 boundary. Unknown fields are retained in original_payload."""

from typing import Any

SUPPORTED = {
    "Patient",
    "Practitioner",
    "Organization",
    "Encounter",
    "Condition",
    "AllergyIntolerance",
    "MedicationRequest",
    "MedicationStatement",
    "Observation",
    "Procedure",
    "Immunization",
    "DocumentReference",
}


def validate_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    if bundle.get("resourceType") not in {"Bundle", *SUPPORTED}:
        raise ValueError("UNSUPPORTED_FHIR_RESOURCE")
    if bundle.get("resourceType") == "Bundle":
        if bundle.get("type") not in {"batch", "collection", "transaction", "document"}:
            raise ValueError("UNSUPPORTED_FHIR_BUNDLE")
        resources = [
            entry.get("resource") for entry in bundle.get("entry", []) if isinstance(entry, dict)
        ]
    else:
        resources = [bundle]
    clean = []
    for resource in resources:
        if not isinstance(resource, dict) or resource.get("resourceType") not in SUPPORTED:
            continue
        clean.append(
            {
                "resource_type": resource["resourceType"],
                "fhir_id": resource.get("id"),
                "original_payload": resource,
            }
        )
    return clean


def export_bundle(resources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": r}
            for r in resources
            if isinstance(r, dict) and r.get("resourceType") in SUPPORTED
        ],
    }
