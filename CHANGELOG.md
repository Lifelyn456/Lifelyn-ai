# Changelog

## Unreleased

### Fixed
- **Extraction silently dropped common labs.** Labels containing digits (`HbA1c`, `Vitamin B12`) did not match the fact pattern, so those results produced no timeline event and no entity at all.
- **A `Date:` header became an Observation** with value 2025 and unit `-04-03`, because a unit could start with a digit or `-`. Units must now start with a letter, `%`, `µ` or `/`.
- **Identifier lines became clinical facts.** `Phone: 5551234567` produced an Observation (value 5,551,234,567) and a timeline event. Header and identifier labels (patient, provider, laboratory, date, address, phone, mobile, fax, email, MRN, ID) are now excluded from entities as well as events.

### Added
- 16 new golden ingest cases (21 ingest and 5 query cases, 26 in total). Five fail against the previous extractor.
- 24 direct extractor tests (`tests/test_extractor_edge_cases.py`); the suite grows from 16 to 40 tests.
- Per-category results in the golden report.
- `docs/EVALUATION.md`: how the harness works and how to add a case.
- MIT license.

## v0.1.0

- Evidence extraction, citation-verified answers, FHIR mapping and the golden evaluation gate.
