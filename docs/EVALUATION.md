# Evaluation harness

Lifelyn answers questions about a person's health history, so a regression in extraction or citation is a safety problem, not a cosmetic one. The **golden evaluation suite** is the gate that catches it. It runs as part of `pytest`, so CI blocks any change that makes it fail.

## What it runs

| Part | File | What it checks |
| --- | --- | --- |
| Ingest cases | `src/lifelyn_ai/evals/datasets/ingest_cases.py`, `ingest_cases_extended.py` | Fixed page text goes through the real ingestion pipeline (`run_ingestion`). Each case checks the structured output |
| Query cases | `src/lifelyn_ai/evals/datasets/query_cases.py` | Fixed evidence and a question go through the real `/internal/v1/query` route over HTTP, authenticated the way `Lifelyn-api` calls it. Each case checks the answer |
| Runner | `src/lifelyn_ai/evals/golden_runner.py` | Runs every case, catches a crashing case as a failing case, and builds the report |
| Metric | `src/lifelyn_ai/evals/metrics.py` | `grounding_score`: the share of claims in an answer that carry at least one citation. An answer with no claims scores 1 only if it says it has insufficient evidence |
| Gate | `tests/test_golden_eval.py` | The suite must pass at `GROUNDING_THRESHOLD = 1.0` (every case) and must cover every required category |

All data is synthetic and fictional. Never add a real or realistic-looking person.

### Required categories

Eight categories are required by the product spec, and the test fails if any has no case: `extraction_accuracy`, `dates_units`, `source_span_fidelity`, `conflicting_records`, `no_evidence_query`, `unsupported_diagnosis_request`, `citation_entailment` and `self_reported_distinction`.

## Running it

```bash
uv sync --frozen
uv run pytest tests/test_golden_eval.py          # the CI gate
uv run python -c "from lifelyn_ai.evals.golden_runner import run_golden_suite; print(run_golden_suite().summary())"
```

The second command prints a report like this (counts change as cases are added):

```text
Golden eval: 26/26 passed
  citation_entailment: 1/1
  dates_units: 10/10
  extraction_accuracy: 6/6
  ...
  [PASS] dates_units/ingest-lab-label-with-digits-hba1c
```

A failing case lists what it expected and what it got, for example `expected unit '%', got None`.

## Adding a case

1. Pick a category from the list above.
2. Write the smallest synthetic input that shows the behaviour. For an ingest case that is the text of one or more pages; the first line of a page is usually the date (`2025-04-03`).
3. Add an `IngestCase` to `ingest_cases_extended.py`. Its `check` function receives the pipeline output and returns a list of failure messages; an empty list means the case passed.
4. Reuse the helpers: `_observation(name, value, unit)` checks one lab value and its citation, `_nothing_extracted` checks that a line produced no fact, and `_cited_text_ok` checks that an entity cites a real span whose text and hash are intact.
5. **Prove the case can fail.** Run it against the code without your fix. A case that cannot fail protects nothing. For example, the five cases that cover the 9 October 2026 extractor fixes all fail against the previous extractor.
6. Run the full checks: `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run mypy src`, `uv run pytest`.

## What the extractor does, and what it deliberately does not

The extractor is deterministic and conservative. It reads explicit `Label: value` lines and never infers clinical meaning.

| Behaviour | Why |
| --- | --- |
| A fact with no ISO date (`YYYY-MM-DD`) on its page gets no timeline event | A date is never invented. A date like `03/04/2025` is ambiguous (3 April or 4 March) and is not guessed |
| Labels may contain digits (`HbA1c`, `Vitamin B12`) | They were silently dropped before 9 October 2026 |
| A unit must start with a letter, `%`, `µ` or `/` | Otherwise `2025-04-03` reads as the quantity 2025 with the unit `-04-03` |
| Header and identifier lines (patient, provider, laboratory, date, address, phone, mobile, fax, email, MRN, ID) are never facts | They describe the page or the person. A phone number must never become a measurement |
| A medication line keeps its text verbatim (`Metformin 500 mg twice daily`) | No structured dose is guessed from free text |
| A flagged result such as `Potassium: 5.9 mmol/L (H)` keeps its text and gets no structured value | The flag is not interpreted yet. This is a known limitation |
| Every entity cites a span whose text and `sha256` hash match | Citations are checkable evidence |

### Known limitations (open issues)

- Abnormal flags (`(H)`, `(L)`) stop a value from being structured.
- Compound values such as blood pressure `120/80 mmHg` are not structured.
- A line that carries its own date is dated with the first date on its page.
