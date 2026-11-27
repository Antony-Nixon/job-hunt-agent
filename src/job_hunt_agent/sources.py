"""Adapters for explicitly permitted public ATS job-board APIs only."""

import json
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from .schemas import JobRecord


PUBLIC_PROVIDERS = {"greenhouse", "lever", "ashby"}


def _clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _timestamp(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _request_json(url: str) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "JobHuntAgent/0.2 (personal job search)"})
    with urlopen(request, timeout=20) as response:  # nosec B310 - fixed HTTPS provider hosts
        return json.loads(response.read().decode("utf-8"))


def greenhouse_jobs(board: str, payload: dict[str, Any]) -> list[JobRecord]:
    return [
        JobRecord(f"greenhouse:{board}:{item['id']}", item["title"], item.get("company_name") or board, "greenhouse", item["absolute_url"], _timestamp(item.get("updated_at")), _clean_html(item.get("content", "")), item.get("location", {}).get("name"), raw_content_hash=None)
        for item in payload.get("jobs", [])
    ]


def lever_jobs(site: str, payload: list[dict[str, Any]]) -> list[JobRecord]:
    return [
        JobRecord(f"lever:{site}:{item['id']}", item["text"], site, "lever", item["hostedUrl"], _timestamp(item.get("createdAt")), _clean_html(item.get("descriptionPlain") or item.get("description", "")), item.get("categories", {}).get("location"), "remote" if item.get("workplaceType") == "remote" else None, item.get("categories", {}).get("commitment"))
        for item in payload
    ]


def ashby_jobs(board: str, payload: dict[str, Any]) -> list[JobRecord]:
    return [
        JobRecord(f"ashby:{board}:{item['id']}", item["title"], board, "ashby", item["jobUrl"], _timestamp(item.get("publishedAt")), item.get("descriptionPlain") or _clean_html(item.get("descriptionHtml", "")), item.get("location"), "remote" if item.get("isRemote") else None, item.get("employmentType"))
        for item in payload.get("jobs", []) if item.get("isListed", True)
    ]


def fetch_public_board(provider: str, board: str) -> list[JobRecord]:
    """Fetch a configured public board; never logs in, submits, or bypasses controls."""
    if provider not in PUBLIC_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", board):
        raise ValueError("board may only contain letters, numbers, underscores, and hyphens")
    token = quote(board, safe="")
    if provider == "greenhouse":
        return greenhouse_jobs(board, _request_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"))
    if provider == "lever":
        return lever_jobs(board, _request_json(f"https://api.lever.co/v0/postings/{token}?mode=json"))
    return ashby_jobs(board, _request_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"))
