"""Executes the golden eval dataset against the real pipeline and scores the result.

Ingest cases call run_ingestion() directly (PDF/OCR decoding has its own dedicated tests).
Query cases go through the actual /internal/v1/query route over HTTP, service-authenticated
exactly as lifelyn-api would call it, so the eval also proves the auth/schema boundary holds.
"""

import hmac
import json
import time
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4

from fastapi.testclient import TestClient

from ..ingestion.pipeline import run_ingestion
from ..main import app
from .datasets.ingest_cases import GOLDEN_INGEST_CASES
from .datasets.query_cases import GOLDEN_QUERY_CASES
from .datasets.types import REQUIRED_CATEGORIES, CaseResult

EVAL_SERVICE_SECRET = "golden-eval-service-secret-long-enough-for-hmac-use"


def _encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode().rstrip("=")


def _service_headers(path: str, body: dict) -> dict[str, str]:
    nonce = str(uuid4())
    now = int(time.time())
    head = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = _encode(
        json.dumps(
            {
                "capability": "lifelyn-ai:invoke",
                "path": path,
                "correlationId": f"golden-eval-{nonce}",
                "nonce": nonce,
                "sub": "lifelyn-api",
                "iss": "lifelyn-api",
                "aud": "lifelyn-ai",
                "iat": now,
                "exp": now + 60,
            },
            separators=(",", ":"),
        ).encode()
    )
    secret = EVAL_SERVICE_SECRET.encode()
    signature = _encode(hmac.new(secret, f"{head}.{claims}".encode(), sha256).digest())
    raw = json.dumps(body, separators=(",", ":")).encode()
    return {
        "authorization": f"Bearer {head}.{claims}.{signature}",
        "x-lifelyn-nonce": nonce,
        "x-lifelyn-signature": hmac.new(secret, nonce.encode() + b"." + raw, sha256).hexdigest(),
        "content-type": "application/json",
    }


@dataclass(frozen=True)
class GoldenReport:
    results: list[CaseResult]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def score(self) -> float:
        return (
            sum(result.passed for result in self.results) / len(self.results)
            if self.results
            else 0.0
        )

    @property
    def categories_covered(self) -> set[str]:
        return {result.category for result in self.results}

    def summary(self) -> str:
        lines = [f"Golden eval: {sum(r.passed for r in self.results)}/{len(self.results)} passed"]
        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"  [{status}] {result.category}/{result.id}")
            for failure in result.failures:
                lines.append(f"           - {failure}")
        missing = REQUIRED_CATEGORIES - self.categories_covered
        if missing:
            lines.append(f"  MISSING REQUIRED CATEGORIES: {sorted(missing)}")
        return "\n".join(lines)


def run_golden_suite(monkeypatch=None) -> GoldenReport:
    if monkeypatch is not None:
        monkeypatch.setenv("SERVICE_JWT_SECRET", EVAL_SERVICE_SECRET)
    else:
        import os

        os.environ["SERVICE_JWT_SECRET"] = EVAL_SERVICE_SECRET

    results: list[CaseResult] = []

    for case in GOLDEN_INGEST_CASES:
        try:
            output = run_ingestion("golden-eval-record", case.pages, case.source_kind)
            failures = case.check(output)
        except Exception as error:  # noqa: BLE001 - a crashing case is a failing case
            failures = [f"raised {error!r}"]
        results.append(CaseResult(case.id, case.category, not failures, failures))

    client = TestClient(app)
    for query_case in GOLDEN_QUERY_CASES:
        body = {
            "authorized_patient_id": "golden-eval-patient",
            "question": query_case.question,
            "authorized_record_version_ids": query_case.authorized_record_version_ids,
            "evidence": query_case.evidence,
            "structured_facts": query_case.structured_facts,
        }
        raw = json.dumps(body, separators=(",", ":"))
        try:
            response = client.post(
                "/internal/v1/query",
                headers=_service_headers("/internal/v1/query", body),
                content=raw,
            )
            if response.status_code != 200:
                failures = [f"HTTP {response.status_code}: {response.text}"]
            else:
                failures = query_case.check(response.json())
        except Exception as error:  # noqa: BLE001 - a crashing case is a failing case
            failures = [f"raised {error!r}"]
        results.append(CaseResult(query_case.id, query_case.category, not failures, failures))

    return GoldenReport(results)
