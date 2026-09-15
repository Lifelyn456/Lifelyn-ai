import pytest

from lifelyn_ai.fhir import export_bundle, validate_bundle


def test_fhir_import_preserves_payload_and_rejects_unknown_resources():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "o1",
                    "valueQuantity": {"value": 13.8},
                }
            },
            {"resource": {"resourceType": "Unknown", "id": "x"}},
        ],
    }
    mapped = validate_bundle(bundle)
    assert (
        mapped[0]["resource_type"] == "Observation"
        and mapped[0]["original_payload"]["valueQuantity"]["value"] == 13.8
    )
    with pytest.raises(ValueError):
        validate_bundle({"resourceType": "Unknown"})


def test_fhir_export_is_a_collection():
    assert export_bundle([{"resourceType": "Patient", "id": "p1"}])["type"] == "collection"
