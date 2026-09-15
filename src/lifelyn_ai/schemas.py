"""Versioned internal schemas. Authorization decisions remain in lifelyn-api."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_version_id: str = Field(min_length=1, max_length=100)
    page: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=20_000)
    text_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_kind: Literal["provider", "patient", "import"] = "provider"


class IngestEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str = Field(min_length=1, max_length=100)
    occurred_at: datetime
    certainty: Literal["confirmed", "probable", "possible", "unknown"]
    source_kind: Literal["provider", "patient", "import"]
    self_reported: bool = False
    display: str = Field(min_length=1, max_length=500)
    source_span_ids: list[str] = Field(min_length=1, max_length=20)


class IngestEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: Literal[
        "Condition",
        "MedicationStatement",
        "Allergy",
        "Observation",
        "Encounter",
        "Procedure",
        "Immunization",
    ]
    name: str = Field(min_length=1, max_length=200)
    value_text: str | None = Field(default=None, max_length=500)
    value_numeric: float | None = None
    unit: str | None = Field(default=None, max_length=40)
    occurred_at: datetime | None = None
    status: str = Field(default="unknown", min_length=1, max_length=50)
    source_span_ids: list[str] = Field(min_length=1, max_length=20)


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    record_version_id: str = Field(min_length=1, max_length=100)
    authorized_patient_id: str = Field(min_length=1, max_length=100)
    mime_type: Literal["application/pdf", "image/png", "image/jpeg"]
    document_base64: str = Field(min_length=4, max_length=40_000_000)
    source_kind: Literal["provider", "patient", "import"] = "provider"


class IngestCitation(BaseModel):
    span_id: str
    record_version_id: str
    page: int
    start: int
    end: int
    text: str
    text_hash: str


class IngestResponse(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    record_version_id: str
    events: list[IngestEvent]
    entities: list[IngestEntity] = Field(default_factory=list)
    citations: list[IngestCitation]
    warnings: list[str] = Field(default_factory=list)
    model_trace: dict[str, str]


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    authorized_patient_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=2_000)
    authorized_record_version_ids: set[str] = Field(min_length=1, max_length=5_000)
    evidence: list[EvidenceSpan] = Field(default_factory=list, max_length=5_000)
    structured_facts: list[StructuredFact] = Field(default_factory=list, max_length=5_000)


class StructuredFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_id: str = Field(min_length=1, max_length=100)
    fact_type: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=500)
    occurred_at: datetime
    source_kind: Literal["provider", "patient", "import"]
    source_span_ids: list[str] = Field(min_length=1, max_length=20)
    patient_corrected: bool = False


class Citation(BaseModel):
    record_version_id: str
    page: int
    span_id: str
    relevance_score: float = Field(ge=0, le=1)


class Claim(BaseModel):
    text: str
    support_status: Literal["SUPPORTED"] = "SUPPORTED"
    citations: list[Citation]
    occurred_at: datetime | None = None
    source_kind: Literal["provider", "patient", "import"] | None = None
    fact_id: str | None = None
    provenance: Literal["record", "patient-correction"] = "record"


class QueryResponse(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    answer: str
    claims: list[Claim] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False
    safety_notice: str = "This is a record summary, not a diagnosis or prescription."


class EvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    response: QueryResponse
