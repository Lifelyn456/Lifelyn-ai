"""Native-text-first parsing with an explicit private OCR provider boundary."""

import os
from base64 import b64decode
from io import BytesIO

import httpx
from pypdf import PdfReader


async def parse_document(encoded: str, mime_type: str) -> list[str]:
    raw = b64decode(encoded, validate=True)
    if mime_type == "application/pdf":
        reader = PdfReader(BytesIO(raw))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        if any(pages):
            return pages
    endpoint = os.environ.get("VISION_PROVIDER_URL")
    token = os.environ.get("VISION_PROVIDER_TOKEN")
    if not endpoint or not token:
        raise ValueError("OCR_REQUIRED_BUT_NOT_CONFIGURED")
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            endpoint,
            content=raw,
            headers={"authorization": f"Bearer {token}", "content-type": mime_type},
        )
        response.raise_for_status()
        payload = response.json()
    pages = payload.get("pages")
    if not isinstance(pages, list) or not all(isinstance(page, str) for page in pages):
        raise ValueError("INVALID_OCR_RESPONSE")
    return [page.strip() for page in pages]
