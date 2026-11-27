from io import BytesIO

import pytest

from job_hunt_agent.ai_provider import DeterministicProvider
from job_hunt_agent.evidence import inspect_public_link


class FakeResponse:
    def __init__(self, body: bytes, content_type: str = "text/html"):
        self.body = BytesIO(body)
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body.read(size)

    def geturl(self):
        return "https://example.com/jobs/1"


def test_public_link_extracts_visible_text_and_caps_bytes():
    def opener(request, timeout):
        return FakeResponse(b"<html><script>ignore()</script><h1>Automation Engineer</h1><p>Apply https://example.com/jobs/1</p></html>")

    result = inspect_public_link("https://example.com/start", DeterministicProvider(), max_bytes=200, opener=opener)
    assert result.status == "ok"
    assert "ignore" not in result.text
    assert result.extraction is not None
    assert result.extraction.title == "Automation Engineer"


def test_public_link_rejects_non_http_urls():
    with pytest.raises(ValueError, match=r"HTTP\(S\)"):
        inspect_public_link("file:///private/job.html", DeterministicProvider())


def test_fetch_failure_routes_to_review():
    attempts = []
    def opener(request, timeout):
        attempts.append(1)
        raise OSError("blocked")

    result = inspect_public_link("https://example.com/job", DeterministicProvider(), opener=opener)
    assert result.status == "error"
    assert result.classification.needs_review is True
    assert len(attempts) == 2


def test_public_link_extracts_jobposting_jsonld():
    body = b'''<script type="application/ld+json">{"@type":"JobPosting","title":"CRM Engineer","hiringOrganization":{"name":"Example Co"},"jobLocation":{"address":{"addressLocality":"Pune","addressCountry":"IN"}}}</script>'''

    result = inspect_public_link("https://example.com/job", DeterministicProvider(), opener=lambda request, timeout: FakeResponse(body))

    assert result.structured_fields == {"title": "CRM Engineer", "company_name": "Example Co", "location": "Pune, IN"}


def test_evidence_records_provider_metadata():
    result = inspect_public_link("https://example.com/job", DeterministicProvider(), opener=lambda request, timeout: FakeResponse(b"<h1>Automation Engineer</h1>"))
    assert result.provider_name == "deterministic"
    assert result.provider_model == "rules-v1"


def test_image_content_is_routed_to_review_without_decoding():
    result = inspect_public_link("https://example.com/image", DeterministicProvider(), opener=lambda request, timeout: FakeResponse(b"\x89PNG\r\n", "image/png"))
    assert result.classification.source_kind == "image"
    assert result.classification.needs_review is True
    assert result.text == ""
    assert result.extraction is None


def test_jsonld_jobposting_accepts_type_list_and_location_list():
    body = b'''<script type="application/ld+json">{"@type":["Thing","JobPosting"],"title":"CRM Engineer","hiringOrganization":{"name":"Example Co"},"jobLocation":[{"address":{"addressLocality":"Pune","addressCountry":"IN"}}]}</script>'''
    result = inspect_public_link("https://example.com/job", DeterministicProvider(), opener=lambda request, timeout: FakeResponse(body))
    assert result.structured_fields["location"] == "Pune, IN"

