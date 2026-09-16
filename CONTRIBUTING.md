# Contributing to Lifelyn AI

Thanks for looking at this. A few ground rules before you send a PR.

## Ground rules

- **No real patient data, ever.** Test fixtures must be synthetic.
- Keep provider/model code behind an interface in `src/lifelyn_ai/providers/`. Never import a vendor SDK in a route handler.
- Every material clinical fact needs a citation with a stable page/span identifier and a verified hash — no unsupported claims.
- Distinguish provider-issued information from self-reported information; never blur the two.
- Refuse diagnosis/prescription/treatment requests with a safe summary and a clinical-judgment notice — don't try to be helpful past that line.

## Getting set up

```bash
uv sync
cp .env.example .env   # fill in SERVICE_JWT_SECRET (must match the API's AI_SERVICE_JWT_SECRET) and PROMPT_VERSION
uv run uvicorn lifelyn_ai.main:app --host 127.0.0.1 --port 8000
```

## Before you open a PR

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest
uv build
```

All must pass locally; CI runs the same checks and will block merge otherwise.

## Golden evals

If your change touches extraction, citation, or grounding logic, add or update a golden synthetic eval case in `src/lifelyn_ai/evals/datasets/` (dates, units, conflicts, no-evidence questions, unsupported clinical advice, self-report distinction). A grounding regression blocks merge.

## Commit style

Conventional commits: `type(scope): description`. Keep commits scoped to one logical change.

## Reporting bugs vs. security issues

Regular bugs: open a GitHub issue. Security vulnerabilities: see `SECURITY.md` — do not file those as public issues.
