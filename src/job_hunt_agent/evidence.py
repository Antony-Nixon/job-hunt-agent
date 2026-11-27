"""Bounded public-link evidence collection for the review-first pipeline."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from .ai_provider import AIProvider, Classification, ExtractionProposal


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip and data.strip():
            self.parts.append(" ".join(data.split()))


@dataclass(frozen=True)
class EvidenceResult:
    url: str
    final_url: str | None
    status: str
    content_type: str | None
    retrieved_bytes: int
    text: str
    classification: Classification
    extraction: ExtractionProposal | None = None
    error: str | None = None
    error_category: str | None = None
    structured_fields: dict[str, str] | None = None
    provider_name: str | None = None
    provider_model: str | None = None


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("only absolute HTTP(S) URLs are allowed")


def _text_from_html(raw: bytes) -> str:
    parser = _TextParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return "\n".join(parser.parts)


def _jobposting_fields(raw: bytes) -> dict[str, str] | None:
    """Extract only explicit JobPosting JSON-LD fields from public HTML."""
    html = raw.decode("utf-8", errors="replace")
    for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I | re.S):
        try:
            payload = json.loads(match.group(1).strip())
        except (TypeError, ValueError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for item in candidates:
            item_type = item.get("@type") if isinstance(item, dict) else None
            if not isinstance(item, dict) or not (item_type == "JobPosting" or isinstance(item_type, list) and "JobPosting" in item_type):
                continue
            fields: dict[str, str] = {}
            if isinstance(item.get("title"), str) and item["title"].strip():
                fields["title"] = item["title"].strip()
            org = item.get("hiringOrganization")
            if isinstance(org, dict) and isinstance(org.get("name"), str) and org["name"].strip():
                fields["company_name"] = org["name"].strip()
            location = item.get("jobLocation")
            if isinstance(location, list):
                location = next((candidate for candidate in location if isinstance(candidate, dict)), None)
            address = location.get("address") if isinstance(location, dict) else None
            if isinstance(address, dict):
                parts = [address.get(key, "").strip() for key in ("addressLocality", "addressRegion", "addressCountry") if isinstance(address.get(key), str) and address.get(key).strip()]
                if parts:
                    fields["location"] = ", ".join(parts)
            if fields:
                return fields
    return None


def inspect_public_link(
    url: str,
    provider: AIProvider,
    *,
    max_bytes: int = 1_000_000,
    timeout: float = 8.0,
    max_attempts: int = 2,
    opener: Callable[..., object] = urlopen,
) -> EvidenceResult:
    """Fetch one public page and return reviewable evidence, never an action."""
    _validate_url(url)
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    request = Request(url, headers={"User-Agent": "JobHuntAgent/0.2 (review-first; public pages only)"})
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            with opener(request, timeout=timeout) as response:  # type: ignore[arg-type]
                chunks: list[bytes] = []
                total = 0
                while total < max_bytes:
                    chunk = response.read(min(65536, max_bytes - total))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                raw = b"".join(chunks)
                content_type = response.headers.get("Content-Type")
                final_url = response.geturl()
            provider_name = getattr(provider, "provider_name", type(provider).__name__)
            provider_model = getattr(provider, "model", None)
            if content_type and content_type.lower().startswith("image/"):
                classification = Classification("image", True, "Image evidence requires explicit visual review; no OCR or external action was performed.", 1.0)
                classification.validate()
                return EvidenceResult(url, final_url, "ok", content_type, total, "", classification,
                                      provider_name=provider_name, provider_model=provider_model)
            text = _text_from_html(raw) if not content_type or "html" in content_type.lower() else raw.decode("utf-8", errors="replace")
            structured_fields = _jobposting_fields(raw) if not content_type or "html" in content_type.lower() else None
            classification = provider.classify(text, final_url)
            extraction = None if classification.source_kind == "blocked" or not text.strip() else provider.extract(text, final_url)
            return EvidenceResult(url, final_url, "ok", content_type, total, text, classification, extraction, structured_fields=structured_fields, provider_name=provider_name, provider_model=provider_model)
        except HTTPError as exc:
            last_error = exc
            break
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < max_attempts:
                continue
    classification = Classification("unknown", True, "Page could not be safely fetched; review the source manually.", 0.0)
    classification.validate()
    category = "http" if isinstance(last_error, HTTPError) else "network"
    return EvidenceResult(url, None, "error", None, 0, "", classification, error=str(last_error), error_category=category,
                          provider_name=getattr(provider, "provider_name", type(provider).__name__), provider_model=getattr(provider, "model", None))
