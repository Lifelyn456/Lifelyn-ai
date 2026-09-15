from lifelyn_ai.ingestion.extractor import extract, extract_entities


def test_undated_source_does_not_fabricate_timeline_date():
    assert extract("Allergy: penicillin", "span-1", "clinical_note", "provider") == []


def test_dated_source_emits_cited_provider_fact():
    events = extract("2025-04-03\nAllergy: penicillin", "span-1", "clinical_note", "provider")
    assert len(events) == 1
    assert events[0].occurred_at.isoformat().startswith("2025-04-03")
    assert events[0].source_span_ids == ["span-1"]
    assert events[0].self_reported is False


def test_normalizes_explicit_allergy_medication_and_observation_without_inference():
    entities = extract_entities(
        "2025-04-03\nAllergy: penicillin\nMedication: aspirin\nHaemoglobin: 13.8 g/dL",
        "span-1",
    )
    assert [entity.entity_type for entity in entities] == [
        "Allergy",
        "MedicationStatement",
        "Observation",
    ]
    assert entities[2].value_numeric == 13.8
    assert entities[2].unit == "g/dL"
    assert all(entity.source_span_ids == ["span-1"] for entity in entities)
