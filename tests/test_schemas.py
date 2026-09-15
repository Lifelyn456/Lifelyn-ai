import hmac
import json
import time
from base64 import urlsafe_b64encode
from hashlib import sha256
from uuid import uuid4

from fastapi.testclient import TestClient

from lifelyn_ai.answering.verifier import is_supported
from lifelyn_ai.main import app
from lifelyn_ai.schemas import Citation, Claim, EvidenceSpan

SECRET = "test-only-service-secret-that-is-long-enough"


def encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode().rstrip("=")


def headers(path: str, body: dict) -> dict[str, str]:
    nonce = str(uuid4())
    now = int(time.time())
    head = encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = encode(
        json.dumps(
            {
                "capability": "lifelyn-ai:invoke",
                "path": path,
                "correlationId": "test",
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
    signature = encode(hmac.new(SECRET.encode(), f"{head}.{claims}".encode(), sha256).digest())
    raw = json.dumps(body, separators=(",", ":")).encode()
    return {
        "authorization": f"Bearer {head}.{claims}.{signature}",
        "x-lifelyn-nonce": nonce,
        "x-lifelyn-signature": hmac.new(
            SECRET.encode(), nonce.encode() + b"." + raw, sha256
        ).hexdigest(),
        "content-type": "application/json",
    }


def post(client: TestClient, path: str, body: dict):
    raw = json.dumps(body, separators=(",", ":"))
    return client.post(path, headers=headers(path, body), content=raw)


def test_internal_routes_fail_closed_without_service_token():
    client = TestClient(app)
    assert client.get("/internal/v1/health").status_code == 200
    assert client.post("/internal/v1/query", json={}).status_code == 401


def test_query_rejects_unsupported_request(monkeypatch):
    monkeypatch.setenv("SERVICE_JWT_SECRET", SECRET)
    client = TestClient(app)
    text = "Patient reports a rash"
    body = {
        "authorized_patient_id": "p1",
        "question": "What diagnosis should I get?",
        "authorized_record_version_ids": ["v1"],
        "evidence": [
            {
                "record_version_id": "v1",
                "page": 1,
                "start": 0,
                "end": len(text),
                "text": text,
                "text_hash": sha256(text.encode()).hexdigest(),
                "source_kind": "patient",
            }
        ],
    }
    response = post(client, "/internal/v1/query", body)
    assert response.status_code == 200
    assert response.json()["insufficient_evidence"] is True
    assert response.json()["claims"] == []


def test_query_returns_only_cited_authorized_claims(monkeypatch):
    monkeypatch.setenv("SERVICE_JWT_SECRET", SECRET)
    client = TestClient(app)
    text = "Haemoglobin: 13.8 g/dL"
    body = {
        "authorized_patient_id": "p1",
        "question": "What was the haemoglobin result?",
        "authorized_record_version_ids": ["v1"],
        "evidence": [
            {
                "record_version_id": "v1",
                "page": 1,
                "start": 0,
                "end": len(text),
                "text": text,
                "text_hash": sha256(text.encode()).hexdigest(),
            }
        ],
        "structured_facts": [
            {
                "fact_id": "event-1",
                "fact_type": "laboratory",
                "text": text,
                "occurred_at": "2025-04-03T00:00:00Z",
                "source_kind": "provider",
                "source_span_ids": [
                    sha256(
                        f"v1:1:0:{len(text)}:{sha256(text.encode()).hexdigest()}".encode()
                    ).hexdigest()[:32]
                ],
            }
        ],
    }
    response = post(client, "/internal/v1/query", body)
    assert response.status_code == 200
    assert response.json()["claims"][0]["citations"][0]["record_version_id"] == "v1"
    assert response.json()["claims"][0]["text"] == text
    assert response.json()["answer"].startswith("2025-04-03:")


def test_query_discards_tampered_and_out_of_scope_evidence(monkeypatch):
    monkeypatch.setenv("SERVICE_JWT_SECRET", SECRET)
    client = TestClient(app)
    text = "Allergy: penicillin"
    body = {
        "authorized_patient_id": "p1",
        "question": "allergy",
        "authorized_record_version_ids": ["allowed"],
        "evidence": [
            {
                "record_version_id": "blocked",
                "page": 1,
                "start": 0,
                "end": len(text),
                "text": text,
                "text_hash": "0" * 64,
            }
        ],
    }
    response = post(client, "/internal/v1/query", body)
    assert response.json()["insufficient_evidence"] is True


def test_verifier_matches_the_exact_span_when_pages_have_multiple_spans():
    target = EvidenceSpan(
        record_version_id="v1",
        page=1,
        start=0,
        end=19,
        text="Allergy: penicillin",
        text_hash=sha256(b"Allergy: penicillin").hexdigest(),
    )
    other = EvidenceSpan(
        record_version_id="v1",
        page=1,
        start=20,
        end=34,
        text="Pulse: 72 bpm",
        text_hash=sha256(b"Pulse: 72 bpm").hexdigest(),
    )
    span_id = sha256(f"v1:1:0:19:{target.text_hash}".encode()).hexdigest()[:32]
    claim = Claim(
        text=target.text,
        citations=[Citation(record_version_id="v1", page=1, span_id=span_id, relevance_score=1)],
    )
    assert is_supported(claim, [target, other]) is True
    claim.citations[0].span_id = "0" * 32
    assert is_supported(claim, [target, other]) is False


def test_evaluate_scores_the_submitted_response(monkeypatch):
    monkeypatch.setenv("SERVICE_JWT_SECRET", SECRET)
    client = TestClient(app)
    body = {
        "response": {
            "answer": "Unsupported assertion",
            "claims": [
                {
                    "text": "Unsupported assertion",
                    "support_status": "SUPPORTED",
                    "citations": [],
                }
            ],
        }
    }
    response = post(client, "/internal/v1/evaluate", body)
    assert response.status_code == 200
    assert response.json()["groundingScore"] == 0
    assert response.json()["status"] == "FAIL"
