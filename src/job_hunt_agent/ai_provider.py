"""Bounded local reasoning providers with a deterministic fallback."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Classification:
    source_kind: str
    needs_review: bool
    reason: str
    confidence: float

    def validate(self) -> None:
        if self.source_kind not in {"job_alert", "public_job_page", "image", "blocked", "unknown"}:
            raise ValueError("invalid source_kind")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not self.reason.strip():
            raise ValueError("reason is required")


@dataclass(frozen=True)
class ExtractionProposal:
    """Evidence proposal; never a command to submit or contact anyone."""

    title: str | None = None
    company_name: str | None = None
    location: str | None = None
    work_mode: str | None = None
    description: str | None = None
    links: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()

    def validate(self) -> None:
        if not any((self.title, self.company_name, self.location, self.description, self.links)):
            raise ValueError("extraction must contain at least one evidence field")
        for link in self.links:
            if not link.startswith(("http://", "https://")):
                raise ValueError("extracted links must be HTTP(S)")


class AIProvider(Protocol):
    def health(self) -> bool: ...
    def classify(self, text: str, url: str | None = None) -> Classification: ...
    def extract(self, text: str, url: str | None = None) -> ExtractionProposal: ...


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        match = re.search(r"\{.*\}", value, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
    raise ValueError("provider response was not a JSON object")


class DeterministicProvider:
    """Offline fallback for predictable classification and light extraction."""

    provider_name = "deterministic"
    model = "rules-v1"

    def health(self) -> bool:
        return True

    def classify(self, text: str, url: str | None = None) -> Classification:
        lowered = text.lower()
        if any(token in lowered for token in ("captcha", "sign in", "log in", "login", "private")):
            result = Classification("blocked", True, "Possible access control or private content detected.", 0.95)
        elif url and url.startswith(("http://", "https://")) and any(token in lowered for token in ("apply", "job description", "responsibilities", "qualifications")):
            result = Classification("public_job_page", False, "Public job-page indicators found; verify extracted evidence.", 0.78)
        elif any(token in lowered for token in ("job alert", "new job", "hiring", "career opportunity")):
            result = Classification("job_alert", False, "Job-alert indicators found in source text.", 0.72)
        elif re.search(r"https?://", text):
            result = Classification("unknown", True, "A link was found but source purpose is unclear.", 0.55)
        else:
            result = Classification("unknown", True, "No reliable source classification signal found.", 0.40)
        result.validate()
        return result

    def extract(self, text: str, url: str | None = None) -> ExtractionProposal:
        links = tuple(dict.fromkeys(re.findall(r"https?://[^\s)<>]+", text)))
        title = None
        for line in text.splitlines():
            clean = line.strip().lstrip("#*- ")
            if clean and len(clean) <= 120 and any(word in clean.lower() for word in ("engineer", "developer", "analyst", "manager", "specialist", "designer")):
                title = clean
                break
        proposal = ExtractionProposal(title=title, description=text[:4000] or None, links=links, uncertainty=("Deterministic extraction requires human review.",))
        proposal.validate()
        return proposal


class OllamaProvider:
    """Minimal Ollama HTTP connector; disabled unless explicitly configured."""

    def __init__(self, model: str = "llama3.2", base_url: str = "http://127.0.0.1:11434", timeout: float = 3.0):
        self.provider_name = "ollama"
        self.model, self.base_url, self.timeout = model, base_url.rstrip("/"), timeout

    def _request(self, prompt: str) -> dict[str, Any]:
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False, "format": "json"}).encode()
        request = Request(self.base_url + "/api/generate", data=body, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return _json_object(payload.get("response", payload))

    def health(self) -> bool:
        try:
            request = Request(self.base_url + "/api/tags")
            with urlopen(request, timeout=self.timeout):
                return True
        except (OSError, URLError):
            return False

    def classify(self, text: str, url: str | None = None) -> Classification:
        prompt = f"Return JSON only with source_kind, needs_review, reason, confidence. Allowed source_kind: job_alert, public_job_page, image, blocked, unknown. Never recommend external actions. URL: {url or ''}\nTEXT:\n{text[:12000]}"
        data = self._request(prompt)
        result = Classification(str(data.get("source_kind", "unknown")), bool(data.get("needs_review", True)), str(data.get("reason", "Model gave no reason.")), float(data.get("confidence", 0.0)))
        result.validate()
        return result


class GeminiProvider:
    """Gemini REST connector using a key supplied only through the environment."""

    def __init__(self, model: str = "gemini-2.5-flash", api_key: str | None = None, timeout: float = 10.0):
        self.provider_name = "gemini"
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.timeout = timeout

    def _request(self, prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured")
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}).encode()
        request = Request(endpoint, data=body, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        return _json_object(text)

    def health(self) -> bool:
        return bool(self.api_key)

    def classify(self, text: str, url: str | None = None) -> Classification:
        prompt = f"Return JSON only with source_kind, needs_review, reason, confidence. Allowed source_kind: job_alert, public_job_page, image, blocked, unknown. Never recommend external actions. URL: {url or ''}\nTEXT:\n{text[:12000]}"
        data = self._request(prompt)
        result = Classification(str(data.get("source_kind", "unknown")), bool(data.get("needs_review", True)), str(data.get("reason", "Model gave no reason.")), float(data.get("confidence", 0.0)))
        result.validate()
        return result

    def extract(self, text: str, url: str | None = None) -> ExtractionProposal:
        prompt = f"Return JSON only with title, company_name, location, work_mode, description, links, uncertainty. Extract evidence only; do not invent values and do not submit anything. URL: {url or ''}\nTEXT:\n{text[:12000]}"
        data = self._request(prompt)
        result = ExtractionProposal(data.get("title"), data.get("company_name"), data.get("location"), data.get("work_mode"), data.get("description"), tuple(data.get("links") or ()), tuple(data.get("uncertainty") or ()))
        result.validate()
        return result

    def extract(self, text: str, url: str | None = None) -> ExtractionProposal:
        prompt = f"Return JSON only with title, company_name, location, work_mode, description, links, uncertainty. Extract evidence only; do not invent values and do not submit anything. URL: {url or ''}\nTEXT:\n{text[:12000]}"
        data = self._request(prompt)
        result = ExtractionProposal(data.get("title"), data.get("company_name"), data.get("location"), data.get("work_mode"), data.get("description"), tuple(data.get("links") or ()), tuple(data.get("uncertainty") or ()))
        result.validate()
        return result


def select_provider(prefer_ollama: bool = True, prefer_gemini: bool = False, model: str = "llama3.2", base_url: str = "http://127.0.0.1:11434", gemini_model: str = "gemini-2.5-flash") -> AIProvider:
    """Select configured providers in order, otherwise use the offline fallback."""
    if prefer_ollama:
        candidate = OllamaProvider(model=model, base_url=base_url)
        if candidate.health():
            return candidate
    if prefer_gemini:
        candidate = GeminiProvider(model=gemini_model)
        if candidate.health():
            return candidate
    return DeterministicProvider()
