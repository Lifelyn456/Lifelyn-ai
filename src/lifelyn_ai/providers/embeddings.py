"""Private embedding-provider boundary; no route imports a vendor SDK."""

import math
import os
from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class HttpEmbeddingProvider:
    def __init__(self, url: str, token: str, model: str) -> None:
        self.url = url
        self.token = token
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                self.url,
                headers={"authorization": f"Bearer {self.token}"},
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
        body = response.json()
        rows = body.get("data") if isinstance(body, dict) else None
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise ValueError("Embedding provider returned an invalid row count")
        vectors: list[list[float]] = []
        expected_dimension: int | None = None
        for row in rows:
            raw = row.get("embedding") if isinstance(row, dict) else None
            if not isinstance(raw, list) or not raw:
                raise ValueError("Embedding provider returned an invalid vector")
            vector = [float(value) for value in raw]
            if not all(math.isfinite(value) for value in vector):
                raise ValueError("Embedding provider returned a non-finite vector")
            expected_dimension = expected_dimension or len(vector)
            if len(vector) != expected_dimension:
                raise ValueError("Embedding provider returned inconsistent dimensions")
            vectors.append(vector)
        return vectors


def configured_provider() -> EmbeddingProvider | None:
    url = os.environ.get("EMBEDDING_PROVIDER_URL", "").strip()
    token = os.environ.get("EMBEDDING_PROVIDER_TOKEN", "").strip()
    model = os.environ.get("EMBEDDING_MODEL", "").strip()
    configured = bool(url and token and model)
    if os.environ.get("ENVIRONMENT", "development").casefold() == "production" and not configured:
        raise RuntimeError("Private embedding provider configuration is required in production")
    if not configured:
        return None
    return HttpEmbeddingProvider(url, token, model)
