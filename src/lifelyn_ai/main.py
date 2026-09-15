"""Private parsing and evidence service. It never decides user authorization."""

import hmac
import json
import os
import re
import time
from base64 import urlsafe_b64decode
from hashlib import sha256

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError

from .answering.generator import build_claim, build_structured_claim
from .answering.verifier import is_supported
from .evals.metrics import grounding_score
from .ingestion.citations import fact_citations, page_citation
from .ingestion.classifier import classify
from .ingestion.extractor import extract, extract_entities
from .ingestion.parser import parse_document
from .providers.embeddings import configured_provider
from .retrieval.hybrid_search import search
from .retrieval.question_classifier import classify_question
from .safety import insufficient, is_unsupported
from .schemas import EvaluateRequest, IngestRequest, QueryRequest, QueryResponse

app = FastAPI(title="Lifelyn internal AI", version="1.0", docs_url=None, redoc_url=None)
_nonces: dict[str, int] = {}


def _decode(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def require_service_auth(request: Request, body: bytes, path: str) -> str:
    secret = os.environ.get("SERVICE_JWT_SECRET", "").encode()
    raw = request.headers.get("authorization", "")
    nonce = request.headers.get("x-lifelyn-nonce", "")
    signature = request.headers.get("x-lifelyn-signature", "")
    if len(secret) < 32 or not raw.startswith("Bearer ") or not nonce:
        raise HTTPException(status_code=401, detail="Service authentication required")
    try:
        head, payload, jwt_signature = raw[7:].split(".")
        expected_jwt = hmac.new(secret, f"{head}.{payload}".encode(), sha256).digest()
        header = json.loads(_decode(head))
        claims = json.loads(_decode(payload))
        expected_body = hmac.new(secret, nonce.encode() + b"." + body, sha256).hexdigest()
        now = int(time.time())
        if not hmac.compare_digest(expected_jwt, _decode(jwt_signature)) or not hmac.compare_digest(
            expected_body, signature
        ):
            raise ValueError
        if (
            not isinstance(header, dict)
            or header.get("alg") != "HS256"
            or header.get("typ") != "JWT"
            or not isinstance(claims, dict)
            or claims.get("iss") != "lifelyn-api"
            or claims.get("aud") != "lifelyn-ai"
            or claims.get("sub") != "lifelyn-api"
            or claims.get("path") != path
            or claims.get("nonce") != nonce
            or claims.get("capability") != "lifelyn-ai:invoke"
            or not claims.get("correlationId")
            or not now - 5 <= int(claims.get("iat", 0)) <= now + 5
            or int(claims.get("exp", 0)) <= now
            or int(claims.get("exp", 0)) > now + 65
        ):
            raise ValueError
        for used, expiry in list(_nonces.items()):
            if expiry <= now:
                _nonces.pop(used, None)
        if nonce in _nonces:
            raise ValueError
        _nonces[nonce] = int(claims["exp"])
        return str(claims.get("correlationId", ""))
    except ValueError, TypeError, KeyError, json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="Invalid service authentication") from None


@app.get("/internal/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "lifelyn-ai", "schemaVersion": "1.0"}


async def ingest_request(request: Request) -> dict:
    body = await request.body()
    require_service_auth(request, body, request.url.path)
    try:
        payload = IngestRequest.model_validate_json(body)
        pages = await parse_document(payload.document_base64, payload.mime_type)
    except (ValidationError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    citations = []
    citation_context: dict[str, str] = {}
    for index, page_text in enumerate(pages, 1):
        if not page_text:
            continue
        page_facts = fact_citations(payload.record_version_id, index, page_text)
        if not page_facts:
            page_facts = [page_citation(payload.record_version_id, index, page_text)]
        date_match = re.search(
            r"\b20\d{2}[-/](?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])\b", page_text
        )
        for citation in page_facts:
            citations.append(citation)
            citation_context[citation.span_id] = (
                f"{date_match.group(0)}\n{citation.text}" if date_match else citation.text
            )
    document_type = classify("\n".join(pages))
    events = []
    entities = []
    for citation in citations:
        context = citation_context[citation.span_id]
        events.extend(extract(context, citation.span_id, document_type, payload.source_kind))
        entities.extend(extract_entities(context, citation.span_id))
    valid_ids = {citation.span_id for citation in citations}
    events = [
        event
        for event in events
        if event.source_span_ids and all(span in valid_ids for span in event.source_span_ids)
    ]
    entities = [
        entity
        for entity in entities
        if entity.source_span_ids and all(span in valid_ids for span in entity.source_span_ids)
    ]
    return {
        "schemaVersion": "1.0",
        "recordVersionId": payload.record_version_id,
        "events": [event.model_dump(mode="json") for event in events],
        "entities": [entity.model_dump(mode="json") for entity in entities],
        "citations": [
            {
                "spanId": citation.span_id,
                "recordVersionId": citation.record_version_id,
                "page": citation.page,
                "start": citation.start,
                "end": citation.end,
                "text": citation.text,
                "textHash": citation.text_hash,
            }
            for citation in citations
        ],
        "warnings": []
        if events
        else ["No conservative structured facts were extracted; manual review is required."],
        "modelTrace": {
            "provider": "deterministic-extractive",
            "model": "native-text-first",
            "promptVersion": os.environ.get("PROMPT_VERSION", "history-v1"),
        },
    }


@app.post("/internal/v1/ingest")
async def ingest(request: Request) -> dict:
    return await ingest_request(request)


@app.post("/internal/v1/reindex")
async def reindex(request: Request) -> dict:
    return await ingest_request(request)


@app.post("/internal/v1/query", response_model=QueryResponse)
async def query(request: Request) -> QueryResponse:
    body = await request.body()
    require_service_auth(request, body, request.url.path)
    try:
        payload = QueryRequest.model_validate_json(body)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    allowed = [
        span
        for span in payload.evidence
        if span.record_version_id in payload.authorized_record_version_ids
        and sha256(span.text.encode()).hexdigest() == span.text_hash
    ]
    if not allowed or is_unsupported(payload.question):
        return QueryResponse(answer=insufficient(payload.question), insufficient_evidence=True)
    try:
        ranked = await search(payload.question, allowed, configured_provider())
    except (httpx.HTTPError, RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=503, detail="Private retrieval provider unavailable"
        ) from error
    if not ranked:
        return QueryResponse(answer=insufficient(payload.question), insufficient_evidence=True)
    evidence_by_id = {
        sha256(
            f"{span.record_version_id}:{span.page}:{span.start}:{span.end}:{span.text_hash}".encode()
        ).hexdigest()[:32]: span
        for span in allowed
    }
    ranked_scores = {
        sha256(
            f"{span.record_version_id}:{span.page}:{span.start}:{span.end}:{span.text_hash}".encode()
        ).hexdigest()[:32]: score
        for span, score in ranked
    }
    question_kind = classify_question(payload.question)
    terms = {
        word for word in re.findall(r"[a-z0-9]+", payload.question.casefold()) if len(word) > 2
    }
    valid_facts = [
        fact
        for fact in payload.structured_facts
        if fact.source_span_ids
        and all(span_id in evidence_by_id for span_id in fact.source_span_ids)
        and (
            fact.patient_corrected
            or all(
                evidence_by_id[span_id].source_kind == fact.source_kind
                for span_id in fact.source_span_ids
            )
        )
        and (
            fact.patient_corrected
            or all(
                " ".join(fact.text.split()) in " ".join(evidence_by_id[span_id].text.split())
                for span_id in fact.source_span_ids
            )
        )
    ]
    fact_scores = []
    for fact in valid_facts:
        words = set(re.findall(r"[a-z0-9]+", fact.text.casefold()))
        lexical = len(terms & words) / max(1, len(terms))
        evidence_score = max(ranked_scores.get(span_id, 0.0) for span_id in fact.source_span_ids)
        if not lexical and question_kind != "timeline" and evidence_score < 0.7:
            continue
        timeline_bonus = 0.2 if question_kind == "timeline" else 0.0
        fact_scores.append((fact, min(1.0, 0.6 * evidence_score + 0.4 * lexical + timeline_bonus)))
    fact_scores.sort(key=lambda item: (item[1], item[0].occurred_at), reverse=True)
    if fact_scores:
        candidates = [
            build_structured_claim(fact, evidence_by_id, score) for fact, score in fact_scores[:5]
        ]
    else:
        candidates = [build_claim(span, index, score) for index, (span, score) in enumerate(ranked)]
    claims = [claim for claim in candidates if is_supported(claim, allowed)]
    if not claims:
        return QueryResponse(answer=insufficient(payload.question), insufficient_evidence=True)
    conflicts = []
    joined = " ".join(span.text.casefold() for span, _ in ranked)
    if "normal" in joined and "abnormal" in joined:
        conflicts.append(
            "Authorized sources contain both normal and abnormal wording; review each citation in context."
        )
    return QueryResponse(
        answer="\n".join(
            f"{claim.occurred_at.date().isoformat()}: {claim.text}"
            if claim.occurred_at
            else claim.text
            for claim in claims
        ),
        claims=claims,
        conflicts=conflicts,
    )


@app.post("/internal/v1/evaluate")
async def evaluate(request: Request) -> dict[str, float | str]:
    body = await request.body()
    require_service_auth(request, body, request.url.path)
    try:
        payload = EvaluateRequest.model_validate_json(body)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    score = grounding_score(payload.response)
    minimum = 1.0
    return {
        "schemaVersion": "1.0",
        "groundingScore": score,
        "minimumRequired": minimum,
        "status": "PASS" if score >= minimum else "FAIL",
    }
