# Lifelyn AI

Private FastAPI service for evidence-bound clinical record processing. It authenticates every internal request with a short-lived service JWT plus an HMAC body signature and never makes authorization decisions; `lifelyn-api` supplies only evidence that the current actor may access.

The ingestion path validates the versioned request, extracts native PDF text first, invokes a configured private OCR/vision endpoint only when needed, creates stable page spans, classifies the document, and emits conservative structured events only when a source date and citation are present. The query path revalidates evidence hashes and authorized record-version IDs, refuses diagnosis/prescription requests, ranks evidence with lexical and private-provider embedding signals, generates extractive atomic claims, distinguishes patient-reported evidence, exposes conflicts, and cites every returned claim. No fixture response is used by a runtime endpoint.

## Run privately

1. Copy `.env.example` to `.env` and supply a random `SERVICE_JWT_SECRET` of at least 32 bytes. It must exactly match the API's `AI_SERVICE_JWT_SECRET`.
2. Configure `VISION_PROVIDER_URL` and `VISION_PROVIDER_TOKEN` for image or scanned-PDF OCR. Those inputs fail closed when OCR is unavailable.
3. Configure the OpenAI-compatible private embedding endpoint using `EMBEDDING_PROVIDER_URL`, `EMBEDDING_PROVIDER_TOKEN`, and `EMBEDDING_MODEL`. It is mandatory when `ENVIRONMENT=production`; provider failures never fall back silently.
4. Run `uv sync --frozen`.
5. Start with `uv run uvicorn lifelyn_ai.main:app --host 127.0.0.1 --port 8000` on a private network.

Only `/internal/v1/health`, `/ingest`, `/reindex`, `/query`, and `/evaluate` exist. Interactive API documentation is disabled. Run `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run mypy src`, `uv run pytest`, and `uv build` before release.

The deterministic extractive implementation is intentionally conservative and does not need a generative model. Development can run lexical-only retrieval; production requires the private embedding service and still subjects every selected passage and claim to the same evidence checks.
