# Security policy

This repository is the private evidence-extraction and history-answer service behind Lifelyn's patient records. It is **unaudited**. Do not point it at real patient data until an independent security review and the jurisdiction-specific legal review described in the root `BUILD_STATUS.md` are complete.

## Scope

This service never faces the public internet directly — it's called only by `lifelyn-api` over a short-lived signed service token (`SERVICE_JWT_SECRET`). In scope for this policy: the extraction/citation pipeline, the service-to-service auth boundary, and provider adapters in `src/lifelyn_ai/providers/` (which must never embed a vendor SDK call directly in a route handler).

## Reporting a vulnerability

Please **do not** open a public GitHub issue for a security finding.

- Preferred: use this repository's [GitHub Security Advisories](https://github.com/Lifelyn456/Lifelyn-ai/security/advisories/new) ("Report a vulnerability" under the Security tab).
- Alternative: contact **@precious1joe** on Telegram with a clear description, reproduction steps, and impact. Never include real patient data in a report.

We aim to acknowledge reports within 5 business days.

## What's in scope

- Auth bypass on the internal service boundary
- A clinical claim surfacing without a verifiable citation
- Prompt injection that causes unsupported medical advice to be returned instead of a refusal
- Extraction that mixes provider-issued and self-reported data without distinguishing them

## What's out of scope

- Findings that require an already-compromised `SERVICE_JWT_SECRET`
- Model output quality issues that aren't security-relevant (file those as regular issues with a golden-eval case instead)
