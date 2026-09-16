<p align="center">
  <img src="https://raw.githubusercontent.com/Lifelyn456/lifelyn-web/main/public/logo.png" alt="Lifelyn" width="120" />
</p>

<h1 align="center">Lifelyn AI</h1>
<p align="center"><strong>Every clinical claim, cited or refused.</strong></p>

<p align="center">
  <a href="https://github.com/Lifelyn456/Lifelyn-ai/actions/workflows/ci.yml"><img src="https://github.com/Lifelyn456/Lifelyn-ai/actions/workflows/ci.yml/badge.svg" alt="AI checks" /></a>
  <img src="https://img.shields.io/badge/stack-FastAPI%20%2F%20Python%203.14-009688" alt="FastAPI / Python 3.14" />
  <img src="https://img.shields.io/badge/access-private%2C%20service--to--service%20only-7C3AED" alt="Private, service-to-service only" />
  <img src="https://img.shields.io/badge/license-unlicensed-lightgrey" alt="Unlicensed" />
</p>

<p align="center">📖 <a href="https://cjay-1.gitbook.io/lifelyn-docs/">Documentation</a></p>

Private FastAPI service for evidence-bound clinical record processing behind [Lifelyn](https://github.com/Lifelyn456/lifelyn-web). It never faces the public internet and never makes an authorization decision — [`lifelyn-api`](https://github.com/Lifelyn456/Lifelyn-api) authenticates every request with a short-lived service JWT and supplies only the evidence the current actor is already authorized to see.

## Table of contents

- [Maintainers](#maintainers)
- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Testing](#testing)
- [Contributing](#contributing)
- [Contributors](#contributors)

## Maintainers

| | Name | Role | Contact |
| --- | --- | --- | --- |
| 🧑‍💻 | Chijioke | Maintainer | [@precious1joe](https://t.me/precious1joe) on Telegram · [@Cjay-Cyber-2](https://github.com/Cjay-Cyber-2) on GitHub |

## What it does

**Ingestion**: validates the versioned request, extracts native PDF text first, invokes a configured private OCR/vision endpoint only when needed, creates stable page spans, classifies the document, and emits a structured event only when it has a source date and citation.

**Query ("Ask History")**: revalidates evidence hashes and authorized record-version IDs, refuses diagnosis/prescription requests, ranks evidence with lexical and private-provider embedding signals, generates extractive atomic claims, distinguishes patient-reported from provider-issued evidence, surfaces conflicts, and cites every returned claim.

No fixture response is ever used by a runtime endpoint. Only `/internal/v1/health`, `/ingest`, `/reindex`, `/query`, and `/evaluate` exist — interactive API docs are disabled.

## Architecture

```
Lifelyn API ──signed service JWT──▶ Lifelyn AI (this repo)
                                          │
                        ┌─────────────────┼─────────────────┐
                        ▼                 ▼                 ▼
                 PDF text extraction  Vision/OCR provider  Embedding provider
                 (native, first)      (private endpoint,   (private endpoint,
                                       only when needed)     mandatory in prod)
```

Provider/model code stays behind an interface — no vendor SDK ever appears in a route handler. Development can run lexical-only retrieval; production requires the private embedding service and still subjects every selected passage and claim to the same evidence checks.

## Quick start

```bash
uv sync --frozen
cp .env.example .env   # SERVICE_JWT_SECRET must exactly match the API's AI_SERVICE_JWT_SECRET
uv run uvicorn lifelyn_ai.main:app --host 127.0.0.1 --port 8000
```

Run this on a private network only — it is not meant to be reachable from the public internet.

## Testing

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest
uv build
```

Golden synthetic evals cover dates, units, conflicts, no-evidence questions, unsupported clinical advice, self-report distinction, and citation fidelity — a grounding regression blocks merge.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Found a security issue? See [`SECURITY.md`](SECURITY.md) instead of opening a public issue.

## Contributors

<a href="https://github.com/Lifelyn456/Lifelyn-ai/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Lifelyn456/Lifelyn-ai" alt="Contributors" />
</a>
